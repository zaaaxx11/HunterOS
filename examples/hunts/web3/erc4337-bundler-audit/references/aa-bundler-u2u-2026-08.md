# U2U aa-bundler red-team session — 2026-08

Target: `/root/u2u-hunt/aa-bundler` — eth-infinitism/bundler fork, lerna version **0.6.0**, EntryPoint **v0.7** (`0x0000000071727De22E5E9d8BAf0edAc6f37da032` in BundlerConfig default). No meaningful local modifications vs upstream → findings are live upstream bugs carried by the fork.

## Verdicts on the six briefed vectors

| # | Vector | Verdict | Key evidence |
|---|--------|---------|--------------|
| 1 | Signature bypass | ❌ safe | `ExecutionManager.ts:42` mandatory `validateUserOp`; `ValidationManager.ts:227-229` sigFailed check; sigFailed derived from merged account+paymaster data (`:88`). `--unsafe` skips opcode/stake only, NOT sig. |
| 2 | Paymaster drain | ✅ **HIGH** | `DepositManager.ts:23-28` wrong-variable bug (below). Also state-race window between re-validation and mining when `conditionalRpc:false` (default). |
| 3 | Gas estimation manipulation | ⚠️ partial | PVG floor enforced (`ValidationManager.ts:308-311`) but `calcPreVerificationGas.ts:43-51` uses L1 constants (`nonZeroByte:16`) — mis-calibrated for L2/custom chains. `estimateUserOperationGas` callGasLimit via plain `estimateGas` (`UserOpMethodHandler.ts:146-153`). |
| 4 | Replay | ❌ safe | `getUserOpHash` binds chainId+EP (`utils/ERC4337Utils.ts:263-267`); EP nonce on-chain; validAfter/validUntil + 30s future floor (`ValidationManager.ts:39,231-242`). |
| 5 | Front-running / MEV | ⚠️ | Bundle via public `signer.sendTransaction` (`BundleManager.ts:104`); no private RPC by default (`conditionalRpc:false`, `BundlerConfig.ts:73`); `getSortedForInclusion` sorts ascending priorityFee (`MempoolManager.ts:199-209`). Bundler can reorder; public mempool sandwiches any swap op. |
| 6 | UserOp tampering | ❌ safe | Any field change → hash change → sig invalid. Note: `MempoolManager._findBySenderNonce:211-219` uses raw `===` for nonce, but inputs are hex-normalized at RPC layer — not exploitable in practice. |

## DepositManager bug (the headline finding)

`packages/bundler/src/modules/DepositManager.ts`:
```ts
async checkPaymasterDeposit (userOp: UserOperation): Promise<void> {
  ...
  let deposit = await this.getCachedDeposit(paymaster)
  deposit = deposit.sub(getUserOpMaxCost(userOp))
  for (const entry of this.mempool.getMempool()) {
    if (entry.userOp.paymaster === paymaster) {
      deposit = deposit.sub(BigNumber.from(getUserOpMaxCost(userOp)))  // ← should be entry.userOp
    }
  }
  requireCond(deposit.gte(0), 'paymaster deposit too low for all mempool UserOps', ...)
}
```

### Verified PoC (pure logic, no node)
```js
function checkKode(deposit, opBaru, existing) {          // buggy loop
  let d = deposit - opBaru
  for (const _ of existing) d -= opBaru
  return d >= 0
}
function checkBenar(deposit, opBaru, existing) {         // correct loop
  let d = deposit - opBaru
  for (const e of existing) d -= e
  return d >= 0
}
// drain case:  deposit=1000, existing=[600,350], opBaru=100
//   buggy:   1000-100-100-100 = 700 → ACCEPT (WRONG)
//   correct: 1000-100-600-350 = -50 → REJECT
// DoS case:    deposit=1000, existing=[400,100], opBaru=400
//   buggy:   1000-400-400-400 = -200 → REJECT (WRONG, legit paymaster blocked)
//   correct: 1000-400-400-100 =  100 → ACCEPT
```
Both directions verified by running this exact script with `node`.

### Exploit path (drain → bundler griefing)
1. Attacker controls paymaster P with deposit exactly covering intended legit ops.
2. Submit ops so that sum of maxCosts exceeds deposit but the buggy check (charging the new op's cost N times) stays ≥ 0.
3. Bundle runs; on-chain AA31 deposit check reverts mid-bundle once the paymaster deposit is exhausted.
4. Bundler pays L1/L2 gas for the reverted `handleOps` up to the revert point; only the blamed entity gets reputation-penalized (`BundleManager._findEntityToBlame:154-166`), attacker rotates paymasters.
5. Repeatable → slow drain of bundler signer balance.

### Fix
`getUserOpMaxCost(userOp)` → `getUserOpMaxCost(entry.userOp)` inside the loop. One-word patch.

## Supporting notes
- `getUserOpMaxCost` (`utils/Utils.ts:204-206`) = `(preVerificationGas + verificationGasLimit + callGasLimit + paymasterVerificationGasLimit + paymasterPostOpGasLimit) * maxFeePerGas`.
- Replacement rule: `MempoolManager.checkReplaceUserOp:187-197` requires ≥1.1× on both maxFee and maxPriorityFee; replace path does NOT re-run `checkReputation`/`checkMultipleRolesViolation` (only the fresh-add path at `:95-96` does) — second-order vector worth probing next session.
- Debug RPC auto-enables on chainId 31337/1337 (`runBundler.ts:105-110`) — check production deployment separately.
- `clientVersion()` exposes `/unsafe` suffix (`UserOpMethodHandler.ts:264-267`) — free fingerprint of unsafe-mode deployments.

## Operator style note
Brief was in Indonesian, casual register ("Bahasa Indonesia santai"), agent assigned a RED-TEAMER persona with a fixed six-vector checklist and per-vector "langkah exploit + baris kode; kalau gagal tulis kenapa". Report format that landed: per-vector verdict header (✅/⚠️/❌ + reason), numbered exploit steps with file:line, then a severity summary table + quick fixes. Reuse this format for hunt-brief deliverables.
