# WEB3 EXPLOITATION MASTERY — 2-HOUR INTENSIVE CURRICULUM
## Session: 2026-08-08 | Target: Deep technical competency for pre-auth RCE/fund theft

---

### HOUR 1: FOUNDATIONS & TRUST BOUNDARIES (0:00 - 1:00)

#### Module 1.1: EVM Internals & Opcode Edge Cases (0:00 - 0:20)
- `SELFDESTRUCT` post-EIP-6049 (Shanghai) — balance drain via `SELFDESTRUCT(to)`
- `DELEGATECALL` / `CALLCODE` — storage collision, `msg.sender` preservation
- `CREATE2` salt collision — deterministic address, `initcode` hash manipulation
- `EXTCODEHASH` / `EXTCODESIZE` / `EXTCODECOPY` — runtime code vs creation code
- `CHAINID` / `SELFBALANCE` / `BASEFEE` — environment manipulation
- Gas griefing: `CALL` with `gas=0`, `RETURNDATASIZE` bombs
- `REVERT` vs `INVALID` vs `STOP` — error handling differences

**Practical**: Write Huff/Yul snippets demonstrating each.

#### Module 1.2: Proxy Patterns & Upgrade Vulnerabilities (0:20 - 0:35)
- EIP-1967 (standard proxy storage slots) — `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`
- EIP-1822 (UUPS) — `proxiableUUID()`, upgrade authorization bypass
- Diamond (EIP-2535) — facet storage collision, `diamondCut` access control
- Beacon Proxy — `upgradeTo` on beacon, multiple proxies single point
- Storage layout collision — variable packing, inherited storage gaps
- `initialize()` reinitialization — missing `initialized` flag
- `delegatecall` to malicious implementation — `selfdestruct` in impl

**Practical**: Deploy minimal proxy + UUPS + Diamond, test upgrade exploits.

#### Module 1.3: Cross-Chain Verification & Light Clients (0:35 - 0:50)
- IBC `VerifyMembership` / `VerifyNonMembership` — ICS23 merkle proofs
- Tendermint light client — validator set, `+2/3` threshold, header verification
- CometBLS / ZK light client — BLS aggregate sig, Groth16/Plonk verifier
- Hyperlane ISM — multisig, routing, hook verification
- LayerZero — `DVN` + `Executor`, `lzReceive` gas griefing
- Wormhole — Guardian set, VAA verification, `verifySignatures`
- Optimism/Arbitrum — `L1CrossDomainMessenger`, `L2ToL1MessagePasser`

**Practical**: Read `cometbls/zk_verifier.rs`, `ibc-union` core verification.

#### Module 1.4: Oracle & Price Manipulation (0:50 - 1:00)
- TWAP manipulation — multi-block, `sqrtPriceX96` manipulation
- Chainlink — `latestRoundData`, stale answers, `minAnswer`/`maxAnswer`
- Custom oracle — median, mean, outlier removal bypass
- Flashloan + oracle — single-block price distortion
- `getPrice` in marketplace (prom-io FantomPriceFeed) — oracle registration control

---

### HOUR 2: ADVANCED EXPLOITATION & TOOLING (1:00 - 2:00)

#### Module 2.1: MEV / Front-running / Flashloan Attacks (1:00 - 1:20)
- Mempool monitoring — `eth_subscribe` newPendingTransactions
- Bundle construction — `eth_sendBundle` (Flashbots), `coinbase.transfer`
- Sandwich — `swapExactTokensForTokens` + `swapTokensForExactTokens`
- Liquidation — `liquidateBorrow` with oracle delay
- JIT liquidity — mint/burn around large swaps
- Gas golfing — `CALL` vs `STATICCALL` vs `DELEGATECALL` gas diffs

#### Module 2.2: DeFi Invariant Violations (1:20 - 1:35)
- Reentrancy — `nonReentrant` bypass via `ERC777` hooks, `ERC1155` `onERC1155Received`
- Read-only reentrancy — `view` functions reading dirty state
- Precision loss — `mulDiv`, `ray` math, `WAD`/`RAY` rounding
- Accounting mismatch — `totalSupply` vs `balanceOf(sum)`, `exchangeRate`
- Access control — `onlyOwner` vs `onlyRole`, `AccessControl` misconfig

#### Module 2.3: Real-World Exploit Case Studies (1:35 - 1:50)
- Euler Finance — `donateToReserves` + `borrow` + liquidation
- Nomad Bridge — `process` with `root=0x0` initialization
- Wormhole — `verifySignatures` missing guardian set check
- Ronin — 5/9 validator keys compromised
- Poly Network — cross-chain `EthCrossChainManager` keeper key
- Multichain — SMPC key management failure

#### Module 2.4: Tooling Mastery — Mainnet Fork Testing (1:50 - 2:00)
- `forge test --fork-url $RPC --fork-block-number N`
- `anvil --fork-url $RPC --fork-block-number N --port 8545`
- `cast storage`, `cast call`, `cast send` — state inspection
- `forge inspect` — storage layout, function selectors
- Tenderly/Alchemy simulation — tx trace, state diff
- Custom cheatcodes — `vm.startPrank`, `vm.deal`, `vm.warp`

---

### DELIVERABLES (End of 2 Hours)
1. **Cheatsheet** — `WEB3_EXPLOIT_CHEATSHEET.md` (one-pager)
2. **Exploit templates** — `/exploits/` folder with 10+ minimal PoCs
3. **Mindmap** — Trust boundary → vulnerability class mapping
4. **Next targets list** — 5 protocols with specific attack vectors to test

---

### SUCCESS CRITERIA
- Can explain any EVM opcode exploit in 30 seconds
- Can audit a proxy upgrade in 5 minutes
- Can trace IBC light client verification path
- Can build flashloan exploit on fork in <30 min
- Has 5 ready-to-test targets with specific vectors