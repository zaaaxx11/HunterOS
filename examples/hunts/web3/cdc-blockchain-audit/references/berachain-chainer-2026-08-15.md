# Berachain Cross-Repo Chainer — 2026-08-15

Source: `berachain/beacon-kit` (main tar.gz 18M), `polaris`, `offchain-sdk` (5.5M), `contracts` (556K), `bera-reth` (14M), `cosmos-sdk`, `cometbft`, `bera-geth`.
Host: TencentOS 4, git without `git-remote-https` → cloned via `curl -sL https://github.com/berachain/<repo>/archive/refs/heads/main.tar.gz | tar -xz`.

## Repo roles

- **beacon-kit**: CometBFT CL, SSZ (`karalabe/ssz` fork), `node-api` (Echo on `127.0.0.1:3500`, CORS *, no auth), payload builder (`NotifyForkchoiceUpdate` → `getPayload`), state processors.
- **bera-reth**: Rust EL (Reth SDK), `Prague1` at genesis (min base fee 1 gwei), custom `DEPOSIT_EVENT_SIGNATURE = keccak("Deposit(bytes,bytes,uint64,bytes,uint64)")` (5 fields), `RequestsOrHash` hash-mode.
- **polaris**: Polaris EVM↔Cosmos bridge. Keeper `ProcessPayloadEnvelope` (single Cosmos tx builds whole ETH block via `ExecutableDataToBlock` + `InsertBlockAndSetHead`). Plugins: `state` (lazy account creation, `sync.Mutex`, `snapmulti`), `precompile` (Run disables reentrancy only for that call, `MustGetAs[PolarStateDB]` → `sdk.UnwrapSDKContext` → `MsgServer`).
- **offchain-sdk**: Workers (`x/jobs/event_job.go` `EthEventSub` only filters `Addresses+keccak(event)`), KMS transactor (`core/transactor/factory` EIP-1559 + `Multicall3`/`PayableMulticall` batcher, `sender` retry), `client/eth` `SubscribeFilterLogs`.
- **contracts**: PoL/Honey/Gov/WBERA vaults, UUPS+ERC1967 via `Create2Deployer._CREATE2_FACTORY=0x4e59b44847b379578588920cA78FbF26c0B4956C`, deterministic salt `_salt(type(X).creationCode)` (often no sender binding), `foundry.toml ffi=true`.

## 7 handoffs (with evidence)

| # | Edge | Evidence |
|---|------|----------|
| H1 | p2p → beacondb | `consensus/cometbft/service/abci.go:52 PrepareProposal, 99 ProcessProposal→beacon/blockchain/process_proposal.go:162 VerifyIncomingBlock, 124 FinalizeBlock, 256 CheckTx {return &Response{}}`, `configs.go:73 Mempool.Type="nop" Recheck=false Broadcast=false Size=0` |
| H2 | CL → EL JWT | `payload/builder/payload.go:86 NotifyForkchoiceUpdate`, `execution/client/engine.go:39 NewPayload/80 ForkchoiceUpdated`, `primitives/net/jwt/`, `config/template/template.go:53 jwt-secret-path`, `execution/client/client.go:64 jwtSecret` |
| H3 | EL → Cosmos | `bera-reth/src/engine/mod.rs:120 execution_requests: Requests`, `src/engine/rpc.rs:48 V4P11 + 102 accept_execution_requests_hash + 444/477 execution_requests: RequestsOrHash`, `src/engine/validator.rs:168 validate_execution_requests`, `polaris/cosmos/x/evm/keeper/processor.go:42 ProcessPayloadEnvelope: UnmarshalJSON → ExecutableDataToBlock → spf.SetFinalizeBlockContext → InsertBlockAndSetHead` |
| H4 | EVM → Cosmos keeper | `cosmos/x/evm/plugins/precompile/plugin.go:120 Run: MustGetAs[PolarStateDB] → sdk.UnwrapSDKContext → gm=NewGasMeter(suppliedGas) → pc.Run(ctx.WithGasMeter(gm))`, `cosmos/precompile/bank/bank.go` + `staking/staking.go: Delegate → stakingtypes.NewMsgDelegate(caller, valAddr, coin)` where `caller= pvm.UnwrapPolarContext(ctx).MsgSender()` |
| H5 | log → offchain host | `offchain-sdk/x/jobs/event_job.go: Subscribe(FilterQuery{Addresses:[contract], Topics:[[keccak(event)]]})`, `client/eth/client_provider.go:317 FilterLogs`, `job/job.go Basic/HasProducer` |
| H6 | KMS → chain | `core/transactor/factory/factory.go:53 BuildTransactionFromRequests`, `batcher/multicall3.go:43 + payable_multicall.go:40 BatchRequests`, `sender/sender.go:35 retryTxWithPolicy`, `baseapp/job_manager.go` |
| H7 | deployer → proxy | `contracts/src/base/Create2Deployer.sol:114 deployProxyWithCreate2`, `base/DeployHelper.sol:56 _saltsForProxy`, `src/pol/BGTStaker.sol:78 onlyOwner`, `gov/BerachainGovernance.sol:85 onlyGovernance`, `pol/FeeCollector.sol:81 onlyRole(DEFAULT_ADMIN)`, `foundry.toml: ffi=true` |

## 7 chains (Trigger→Effect→Boundary)

1. **C1 SSZ bomb**: unauth beacon `node-api` :3500 or p2p → crafted `BeaconBlockBody` SSZ (over-long `executionRequests`, `depositSize=192`) bypasses `ValidateAfterDecodingSSZ` → `FinalizeBlock Transition` writes `SetLatestExecutionPayloadHeader` → registry `processValidatorSetCap` (cap 69) corrupted.
2. **C2 JWT hash-mode**: leak `jwt.hex` → `engine_newPayloadV4P11(..., RequestsOrHash::Hash)` when `accept_execution_requests_hash=true` skips full SSZ → `InsertBlockAndSetHead` with attacker `transactions` → `bank precompile SendCoins`.
3. **C3 reentrancy**: contract `CALL staking.delegate()` → precompile `disableReentrancy`/`enableReentrancy` window → re-enter `distribution` precompile in same tx, shared `ControllableMultiStore` + `GasMeter`, `readOnly` guard race.
4. **C4 offchain event poison (TOP RCE SKELETON)**: deploy contract emitting same `keccak(eventSig)` → `EthEventSub` delivers `Log{Address:attacker, Data:attackerOracle}` (no Address re-check after `SubscribeFilterLogs`) → `Execute` → `CallMsg{To, Data}` → `BatchRequests(true, reqs...)` (Multicall3) → KMS `SignTx` → privileged `multicall` to Honey/PoL vaults.
5. **C5 CREATE2 upgrade**: predictable salt → front-run/predict proxy address → leak deployer EOA (ffi) → `onlyRole(MANAGER/ADMIN)` → `upgradeToAndCall` delegatecall drains `WBERAStakerVault.totalAssets() = WBERA.balanceOf(this)-reservedAssets`.
6. **C6 deposit topic spoof**: `bera-reth/src/deposits.rs:22` custom 5-field `DEPOSIT_EVENT_SIGNATURE` with `deposit_contract=None` (devnet) → `accumulate_deposit_from_log` without `log.address` check → `processStakingDeposits` BLS sig ok, `withdrawalCredentials=0x01+attackerEOA` → fill 69-cap, eject honest.
7. **C7 ffi exfil**: `foundry.toml ffi=true` + `fs_permissions read ./test ./script/genesis` → `vm.ffi(["cat","../.env"])` in `BaseDeploy.s.sol` → leak `PRIVATE_KEY` in CI → C5.

## Top RCE skeleton detail (C4)

```
Step1 emit log (0.001 BERA, no priv)
  → Step2 bot SubscribeFilterLogs delivers to job channel (gap: does job filter Addresses=[] vs [single]?)
  → Step3 Execute decodes log.data → Request{CallMsg{To: priceOracle, Data: setPriceOracle(attacker)}} (gap: is To copied from Topics[1]?)
  → Step4 Batcher.BatchRequests(requireSuccess=true) concatenates, factory builds DynamicFeeTx ChainID from ethClient.ChainID (gap: simulation revert would drop batch?)
  → Step5 KMS Sign + Sender.SendTransaction retry (NonceTooLow → BumpGas)
  → Step6 multicall lands: PythPriceOracle/IncentivesCollector/WBERAStakerVault if bot holds MANAGER_ROLE
  → Step7 persistence via retry policy
```

Why more plausible than C2/C1/C5/C3: <30k gas entry, no validator/JWT stake, batch atomically hits 3-5 privileged targets, keeper bots actually hold MANAGER/PAUSER roles per FeeCollector/IncentivesCollector, historical `bex-sdk`/`pob` pattern.

## PoC next (unexecuted)

1. Run `offchain-sdk/examples/simple-metrics-app` locally, emit spoof from attacker contract, assert bot fires.
2. Audit each `x/jobs/*_job.go` Execute: does it `if log.Address != contractAddress { return }` — grep found none.
3. On Bepolia 80069: `cast call <FeeCollector> "hasRole(bytes32,address)" MANAGER_ROLE <bot>` etc.
4. Batch window test: emit 2 poison logs in same tick, assert single multicall tx with 2 targets.

## Grep anchors for future sessions

```
grep -R -n "CheckTx" beacon-kit/consensus/cometbft/service/abci.go
grep -R -n "Mempool" beacon-kit/consensus/cometbft/service/configs.go
grep -R -n "ProcessPayloadEnvelope|InsertBlockAndSetHead" polaris/cosmos/x/evm/keeper/
grep -R -n "MustGetAs.*PolarStateDB|UnwrapPolarContext|MsgSender" polaris/cosmos/precompile/
grep -R -n "EthEventSub|SubscribeFilterLogs" offchain-sdk/x/jobs/ offchain-sdk/client/eth/
grep -R -n "BatchRequests|Multicall" offchain-sdk/core/transactor/
grep -R -n "upgradeToAndCall|_authorizeUpgrade|Create2Deployer" contracts/src/
grep -R -n "DEPOSIT_EVENT_SIGNATURE|accept_execution_requests_hash|RequestsOrHash" bera-reth/src/
```

## Report

`/root/BERACHAIN_CHAINER_REPORT.md` — full writeup with diagram + tradeoffs. 7 handoffs, 7 chains, file:line citations.
