# ERC-4337 Bundler (TypeScript) Architecture Map & Off-Chain Bug Bank

Source: eth-infinitism/bundler v0.2.0 (EIP-4337 EntryPoint v0.7 layout) — mapped 2026-08 at /root/u2u-hunt/aa-bundler. Packages: `bundler/` (RPC server + modules), `validation-manager/` (tracer + rule parser), `utils/`, `sdk/`.

## 1. Architecture map (file:line)

```
POST /rpc  BundlerServer.ts:45 → handleRpc:127 → handleMethod:160 (method switch)
  eth_sendUserOperation      → UserOpMethodHandler.sendUserOperation (:166)
  eth_estimateUserOperationGas → estimateUserOperationGas (:112)
  debug_bundler_* (9 methods) → DebugMethodHandler (gated by config.debugRpc only)

sendUserOperation flow:
  UserOpMethodHandler._validateParameters (:80)           — static: hex regex, entryPoint match, field presence
  ExecutionManager.sendUserOperation (modules/ExecutionManager.ts:38, Mutex)
    ValidationManager.validateInputParameters (validation-manager/ValidationManager.ts:279)
    ValidationManager.validateUserOp (:194)               — THE core: simulate + tracer + time-range + sig verdict
    DepositManager.checkPaymasterDeposit (modules/DepositManager.ts:15)
    MempoolManager.addUserOp (modules/MempoolManager.ts:70)
    BundleManager.createBundle (modules/BundleManager.ts:188) — 2nd validation :234, per-sender/paymaster rules
    BundleManager.sendBundle (:84) → entryPoint.handleOps via signer EOA
```

Validation core (ValidationManager.ts):
- Safe mode: `_geth_traceCall_SimulateValidation` (:136) → `debug_traceCall` with JS tracer `bundlerCollectorTracer` (BundlerCollectorTracer.ts) + EntryPointSimulations bytecode via stateOverride (:149-153)
- Unsafe mode (`--unsafe`): plain eth_call simulateValidation (:224) — NO opcode/storage/stake checks (:223)
- Rule enforcement: TracerResultParser.tracerResultParser (:177) — [OP-011] banned opcodes :189, [OP-052-054] no EntryPoint re-entry :199-206, [OP-061] no CALL-with-value :209, [STO-010..033] storage assoc rules :259-363, [OP-041/042] no zero-code access :385-397
- Sig verdict: `sigFailed = mergedValidation.aggregator !== AddressZero` (:88) — bundler NEVER verifies sigs locally; 100% delegated to on-chain simulateValidation
- Time range: validAfter<=now (:232), validUntil>now+30s (:240)

## 2. Off-chain bug bank (TS-side, node-independent)

### B1. DepositManager subtract-wrong-op (DepositManager.ts:23-28) ★ most concrete
```ts
deposit = deposit.sub(getUserOpMaxCost(userOp))
for (const entry of this.mempool.getMempool()) {
  if (entry.userOp.paymaster === paymaster) {
    deposit = deposit.sub(BigNumber.from(getUserOpMaxCost(userOp)))  // BUG: userOp, not entry.userOp!
  }
}
```
[EREP-010] check subtracts the NEW op's maxCost once per existing mempool entry with the same paymaster — never the existing entries' costs. Accounting is wrong in BOTH directions depending on relative sizes: with N existing small ops and 1 large new op, the check over-subtracts → false rejection; with large existing ops and small new op, it under-subtracts → paymaster can over-commit deposit → bundle contains ops the paymaster can't cover → on-chain AA31 revert → bundler eats the failed-tx gas. Also note the initial `sub` at :21 double-counts the new op when mempool already contains same-paymaster entries.

### B2. Mempool replace-bump via .toNumber() precision (MempoolManager.ts:188-196)
`checkReplaceUserOp` converts maxFeePerGas/maxPriorityFeePerGas with `.toNumber()` then requires `new >= old * 1.1`. Number is f64 — above 2^53 (~9e15 wei) precision loss makes the 1.1x comparison unreliable; near-threshold replacement can pass with <10% bump → replacement-of-underpriced rules bypass, cheap mempool churn/DoS. Same `.toNumber()` pattern in getSortedForInclusion cost() (:204).

### B3. Bundle sort order ascending (MempoolManager.ts:207)
`copy.sort((a, b) => cost(a.userOp) - cost(b.userOp))` — LOWEST priority fee first. Combined with maxBundleGas break (BundleManager.ts:256), cheap ops fill the bundle and crowd out high-fee ops. Economic-DoS / griefing: attacker floods mempool with near-min-fee valid ops, honest high-fee ops starve. (Verify against upstream — if intentional, still an economic footgun.)

### B4. User-controlled stateOverride in eth_estimateUserOperationGas (UserOpMethodHandler.ts:112-135)
`stateOverride` param from RPC is passed straight into `eth_call simulateHandleOp` (:125-134). Attacker can override ANY account's balance/code/storage during estimation → make a failing op estimate fine, or vice versa (gas-grief wallets' estimation). The commented-out balance override (:127-133) shows the authors knew. No allowlist on which addresses may be overridden.

### B5. Debug namespace exposure, auto-on for testnet chainIds
runBundler.ts:104-110: chainId 31337/1337 → `config.debugRpc = true` silently. DebugMethodHandler exposes clearState/clearMempool/setReputation/clearReputation/setBundlingMode/sendBundleNow — zero auth (DebugMethodHandler.ts:45-78). `setReputation` lets anyone pre-seed opsSeen/opsIncluded → insta-ban any paymaster (crashedHandleOps-equivalent) or whitewash a malicious one. If a "test" bundler ever points at a chain reusing 1337/31337, the whole reputation system is attacker-controlled.

### B6. Loose address regex (utils/Utils.ts:80)
`requireAddressAndFields` accepts `0x[a-f0-9]{10,40}` — a 10-hex-char "address" passes static validation and flows to packing/simulation. Mostly a crash/DoS surface downstream (packUserOp hexConcat with odd lengths), but any downstream consumer trusting "passed bundler validation" inherits it.

### B7. ReputationManager decay bug (ReputationManager.ts:74-75)
`entry.opsIncluded = Math.floor(entry.opsSeen * 23 / 24)` — uses opsSeen, not opsIncluded, as the decay base. Included counts drift upward relative to intent over time → honest entities slowly accrue phantom inclusions; attacker-banned entities recover faster than intended. Subtle, but it silently weakens the only DoS defense.

### B8. TOCTOU on paymaster deposit (DepositManager.ts:44-50 + BundleManager.ts:260-271)
Deposit is cached (`getCachedDeposit`) and only re-read once per bundle; cache cleared only after a bundle attempt (ExecutionManager.ts:98) or via debug RPC. A paymaster can `withdrawStake`/`withdrawTo` on-chain between validation and bundle mining → bundle reverts on-chain, bundler pays gas, blame assignment may not fire (AA31 is paymaster's own fault but revert handling at BundleManager.ts:119-151 only blames via FailedOp reason parsing).

### B9. Blame assignment trusts revert reason strings (BundleManager.ts:154-166)
`_findEntityToBlame` pattern-matches `AA3*`/`AA2*`/`AA1*` prefixes from the FailedOp reason. Entity that can influence which AA-code surfaces (e.g. account whose validateUserOp reverts in a way that the EntryPoint attributes to a different phase) can shift the +10000 opsSeen insta-ban (ReputationManager.crashedHandleOps :180-190) onto an innocent paymaster/factory. Cross-check blame against which phase actually reverted before banning.

### B10. Simulation gas = preVerificationGas + verificationGasLimit only (ValidationManager.ts:140)
`simulationGas` for debug_traceCall ignores paymasterVerificationGasLimit/postOp — a userOp with huge paymaster gas fields but tiny account gas fields gets a simulation that OOGs or misrepresents execution vs on-chain. Also `extraGas >= 2000` check (:248-250) is computed from preOpGas-preVerificationGas; boundary ops can pass simulation yet revert in the real handleOps gas envelope.

## 3. Trust boundary summary (for agent dispatch)
- INPUT: POST /rpc body (batch arrays allowed, BundlerServer.ts:106), bodyParser default 100kb, CORS `*` (:38), no auth/rate-limit.
- STATE (all in-memory, lost on restart): mempool array + _entryCount (MempoolManager.ts:30-33), reputation entries/whitelist/blacklist (ReputationManager.ts:53-58), deposit cache (DepositManager.ts:10). **In-memory = debug_bundler_clearState wipes the entire anti-DoS posture.**
- OUTPUT: entryPoint.handleOps signed by bundler EOA (BundleManager.ts:88-108); fee data taken raw from `provider.getFeeData()` (:86) — configured `gasFactor` NOT applied in sendBundle; beneficiary falls back to signer when balance < minBalance (:310-319).
- Cross-trust: bundler trusts (a) the node's debug_traceCall JS engine, (b) on-chain simulateValidation as sole sig oracle, (c) its own in-memory reputation/deposit caches.
