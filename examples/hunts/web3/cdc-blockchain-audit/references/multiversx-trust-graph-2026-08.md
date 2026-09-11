# MultiversX Trust Graph — Architect Playbook (2026-08)

Source: `mx-chain-go` + `mx-chain-proxy-go` + `mx-chain-vm-go` @ master 2026-08-14.
Deliverable: `/tmp/mvx_architect.md` (31KB, 14 trust boundaries TB1-TB14).
All REST + P2P + Proxy paths are **pre-auth** — no auth middleware exists in any repo.

## 1. Repo Acquisition (git-remote-https missing)

Symptom: `git clone https://` → `git: 'remote-https' is not a git command`.
Cause: TencentOS / minimal git built without curl/openssl.
Fix: GitHub tarball via curl (not git):

```bash
curl -sL https://github.com/multiversx/mx-chain-go/archive/refs/heads/master.tar.gz -o /tmp/mx-chain-go.tar.gz
curl -sL https://github.com/multiversx/mx-chain-proxy-go/archive/refs/heads/master.tar.gz -o /tmp/mx-chain-proxy-go.tar.gz
curl -sL https://github.com/multiversx/mx-chain-vm-go/archive/refs/heads/master.tar.gz -o /tmp/mx-chain-vm-go.tar.gz
mkdir -p /root/mx-chain-go && tar xzf /tmp/mx-chain-go.tar.gz -C /root/mx-chain-go --strip-components=1
# same for proxy, vm-go
```

Do not debug `dnf install git-core` — there is no `git-core` package on TencentOS 4.

## 2. REST Facade / Groups — Full Inventory

Bootstrap: `api/gin/webServer.go:93-147` — `gin.Default()` + `cors.Default()` only global middleware. No auth.
Throttlers: `SourceThrottler` (per-IP, `api/middleware/sourceThrottler.go`) + `GlobalThrottler` (concurrency, `globalThrottler.go`) + `EndpointThrottler` from facade — DoS only.
Route gate: `api/groups/baseGroup.go:28-48 RegisterRoutes()` reads `config.ApiRoutesConfig.APIPackages[basePath].Routes[].Open` — if `Open==false` route silently dropped. No other RBAC.
Facade interfaces: `facade/interface.go` (`NodeHandler`, `ApiResolver`, `HardforkTrigger`) → `facade/nodeFacade.go` → `node/external/nodeApiResolver.go`.

### 11 groups → ~70 endpoints

| Group | Key endpoints | Risk |
|-------|--------------|------|
| **transaction** `transactionGroup.go` | `POST /transaction/send`, `/send-multiple`, `/simulate`, `/cost-scr`, `/cost`, `GET /transaction/:hash`, `/scrs-by-tx-hash/:hash`, `/pool` | **Highest** — only state-mutating pre-auth entry; `Data` carries `funcName@args` |
| **vm-values** `vmValuesGroup.go` | `POST /vm-values/hex,string,int,query` → `doGetVMValue` → `doExecuteQuery` → `createSCQuery` (hex-decodes `args[]`, bech32 decodes addresses) → `ExecuteSCQuery` | **High** — read-only but executes real WASM against live trie, no signature |
| **address** `addressGroup.go` | `GET /address/:address`, `/bulk` POST, `/balance`, `/username`, `/code-hash`, `/key/:key`, `/keys`, `/iterate-keys` POST, 7× ESDT/NFT, `/guardian-data` | Low (reads) |
| **block** `blockGroup.go` | `/by-nonce/:nonce`, `/by-hash/:hash`, `/by-round/:round`, `/altered-accounts/...` | Low |
| **internal** `internalGroup.go:70-156` | 17× `/raw|/json/metablock|shardblock|miniblock/...` raw proto+JSON dumps | **Infoleak** — dumps consensus internals unauth |
| **hardfork** `hardforkGroup.go:62` | `POST /hardfork/trigger` → `HardforkRequest{Epoch,WithEarlyEndOfEpoch}` → `node.DirectTrigger` | **Consensus-critical** if `Open==true` |
| **node** `nodeGroup.go:79-152` | `/heartbeatstatus`, `/status`, `/p2pstatus`, `/metrics`, `POST /debug`, `/peerinfo`, `/epoch-start/:epoch`, 5× `/managed-keys*` | `POST /debug` → `GetQueryHandler(name).Query(search)` — arbitrary debug handler invoke |
| **network** `networkGroup.go:81-155` | `/config`, `/status`, `/economics`, `/enable-epochs`, 4× `/esdts*`, `/genesis-*`, `/gas-configs`, `/ratings` | Low |
| proof/validator/block/internal groups follow same pattern |

Input→Output (send): `FrontendTransaction` JSON → `ShouldBindJSON` → `createTransaction(ArgsCreateTransaction{Nonce, Value(str→big.Int), Rcv/SndAddr(bech32), GasPrice/Limit, Data, Signature(hex), ChainID, Version})` → `ValidateTransaction` → `SendBulkTransactions` → sharded mempool → p2p gossip → `200 {txHash}`.

## 3. VM WASM Pipeline — mx-chain-vm-go

```
ContractCode (tx Data) → StartWasmerInstance(contract, gasLimit, newCode) @ vmhost/contexts/runtime.go:156
  → useWarmInstanceIfExists → makeInstanceFromCompiledCode (blockchain.GetCompiledCode cache)
  → makeInstanceFromContractByteCode → vmExecutor.NewInstanceWithOptions(contract, CompilationOptions{GasLimit, MaxMemoryGrow, MaxMemoryGrowDelta, Metering:true, RuntimeBreakpoints:true}) @ runtime.go:253
  → Wasmer2Instance (CGo libvmexeccapi.so) → wasmValidator: verifyMemoryDeclaration, verifyFunctions, verifyProtectedFunctions, ValidateFunctionArities @ contexts/validator.go:47-83
  → callSCMethod / callInitFunction / callUpgrade @ hostCore/execution.go
  → VMHooks ~100 host funcs @ executor/wrapper/wrapperVMHooks.go (ExecuteOnSame/DestContext, TransferValueExecute, TransferESDTExecute, StorageLoad/Store, crypto, etc.)
  → OutputContext.GetVMOutput() → VMOutput
```

Gates:

| Check | File | Note |
|-------|------|------|
| `validateVMInput` | `vmhost/hostCore/host.go:600` | Only `GasProvided <= MaxInt64` — trivially weak |
| `MaxInstanceStack 10` | `runtime.go:159` | Anti-recursion |
| Wasmer compilation | `runtime.go:253` + `wasmer2/*` | WASM spec + metering injection |
| WASM validators | `contexts/validator.go` | `HasMemory()`, no protected exports (`internalVMErrors`, `transferValueOnly`, `writeLog`, `signalError`), `^[a-z0-9_]{1,255}` names, arity check |
| `checkUpgradePermission` | `execution.go:135` | Only deployer/owner |
| `executionTimeout >=1s` + `recover()` | `host.go:398,465,409-418` | Panic→`ErrExecutionPanicked`, timeout→`FailExecution` |
| `DeductInitialGasForExecution/Deployment` | `contexts/metering.go` | OOG halt |

Deploy vs Call: `RunSmartContractCreate (host.go:384)` uses input.ContractCode + `MustVerifyNextContractCode`; `RunSmartContractCall (451)` loads code via `GetSCCode()` from trie by code hash + `GetCode` gas check.

**WASM→Host boundary:** Wasmer instance is the sole isolation layer. Any CGo memory/bounds bug collapses it and exposes all ~100 hooks.

## 4. P2P Handling

Transport: `p2p/` wraps `mx-chain-communication-go` (libp2p). Config in `p2p/config`.

Interceptor chain (per gossip topic):
```
libp2p topic → SingleDataInterceptor @ process/interceptors/singleDataInterceptor.go:31
  → AntifloodHandler.CanProcessMessage + Throttler.CanProcess (TB8)
  → DataFactory.Create(rawBytes) (TB9 deserialization)
  → InterceptedDataVerifier.Verify
  → Processor.Validate → TxInterceptorProcessor.Validate → TxValidator.CheckTxValidity @ process/dataValidators/txValidator.go:67 (nonce gap, value+fee≤balance, gas bounds, sig)
  → Processor.Save → CheckTxWhiteList (214) (silent drop if cross-shard not whitelisted — still consumed antiflood budget) → ShardedPool.AddData @ processor/txInterceptorProcessor.go:44
```

Processors per topic: Tx, Hdr, MiniBlock, TrieNode, PeerAuth, EquivalentProofs.
Consensus: `consensus/spos/worker.go:477 ProcessReceivedMessage` → `CanProcessReceivedMessage @ consensusState.go:284` (self-sent, wrong round, job done).

## 5. Proxy → Node Forwarding

```
Client → Proxy REST (same groups) → facade/baseFacade → process/TransactionProcessor
  → ComputeShardId(senderAddr) @ baseProcessor.go:187 (TB10)
  → GetObservers(shardID, AvailabilityRecent) @ baseProcessor.go:129 → baseNodeProvider (TB11 sync filtering)
  → CallPostRestEndPoint(observer.Address, "/transaction/send", tx) @ baseProcessor.go:246 (http.Client timeout, headers Accept+User-Agent, JSON marshal) (TB12)
  → sequential retry: StatusOK success; 404/408 skip; 400 return directly without trying next observer (TB13)
```

Fan-out quirks: `SimulateTransaction @ transactionProcessor.go:183` fans to sender AND receiver shard observers (cross-shard result map). `SendMultipleTransactions:286` groups by shard. VM queries route to SC shard observer.

Proxy adds: timeout, sync filtering (`isNodeSynced` checks `nonce` vs `probableHighestNonce` threshold 10 + `areVmQueriesReady`), round-robin fallback. Does NOT add: auth, WAF, payload validation beyond `checkTransactionFields`, mTLS. Response JSON (`GenericAPIResponse`) error string proxied verbatim — compromised observer can inject error oracle.

TB10-14 summary: shard oracle controlled by user Sender address; no-observer DoS if all out-of-sync (`noStatusCheck=true` disables filter — stale reads); HTTP JSON relay trusted verbatim; storage proofs not verified by proxy.

## 6. Prioritization for Fuzz / Exploit Hunt

1. `POST /vm-values/query` — no funds/sig, only needs existing SC address, yet executes WASM on live trie. Fuzz `args[]` hex payloads under ASan/MSan first.
2. `POST /transaction/send` — full mempool→VM chain; fuzz `Data` (func@args) and gas fields.
3. `POST /hardfork/trigger` — check `config.toml` `ApiRoutesConfig` if `hardfork: trigger: Open=true`.
4. `POST /node/debug` — handler name enumeration.
5. P2P: transaction topic (same as REST but no `Open` gate).

## 7. Evidence Anchors (grep)

```bash
grep -rn "func.*CreateTransaction\|ApiRoutesConfig" mx-chain-go --include="*.go" | head
grep -rn "StartWasmerInstance\|validateVMInput" mx-chain-vm-go --include="*.go" | head
grep -rn "InterceptedDataFactory\|CheckTxValidity" mx-chain-go --include="*.go" | head
grep -rn "CallPostRestEndPoint\|ComputeShardId" mx-chain-proxy-go --include="*.go" | head
```
