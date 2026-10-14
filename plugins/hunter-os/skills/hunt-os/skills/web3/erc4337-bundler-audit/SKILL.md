---
name: erc4337-bundler-audit
description: "ERC-4337 bundler audit"
metadata:
  version: 1.0.0
  hermes:
    tags: [security, blockchain, erc4337, account-abstraction, bundler, paymaster, entrypoint, mev, mempool, audit]
    category: security
---

# ERC-4337 Bundler Audit

## Triggers
- ERC-4337 / account abstraction / aa-bundler / EntryPoint / UserOperation / paymaster audit
- eth-infinitism bundler fork, Stackup, Alto/Pimlico, Voltaire, custom bundler in TS/Rust
- "Can the paymaster be drained / can sig check be skipped / can userOp be replayed"
- `<chain>-hunt` workspace containing an `aa-bundler` repo (U2U, etc.)

## Target map (eth-infinitism-derived layout)
- `packages/bundler/src/UserOpMethodHandler.ts` — RPC surface (`sendUserOperation`, `estimateUserOperationGas`).
- `packages/bundler/src/modules/ExecutionManager.ts` — first validation gate before mempool admission.
- `packages/validation-manager/src/ValidationManager.ts` — `validateUserOp`, sig/time-range/gas checks, unsafe-mode branch.
- `packages/bundler/src/modules/DepositManager.ts` — paymaster deposit accounting across the mempool. **Read this line-by-line; historically buggy.**
- `packages/bundler/src/modules/BundleManager.ts` — re-validation, bundle assembly, `handleOps` submission path.
- `packages/bundler/src/modules/MempoolManager.ts` + `ReputationManager.ts` — replacement rules, throttling, entity counting.
- `packages/bundler/src/DebugMethodHandler.ts` + `runBundler.ts` — debug RPC exposure, `--unsafe` / `--debugRpc` flags.
- `packages/sdk/src/calcPreVerificationGas.ts` — preVerificationGas calibration constants.

## Canonical attack checklist (work it top to bottom, file:line per answer)
1. **Signature skip**: does any admission path reach the mempool without `validateUserOp`? Check the `unsafe` branch (eth_call simulation without tracer still checks sig — not a bypass), debug RPC methods (`debug_bundler_*` can clear state / force-send bundles, but cannot forge sigs), and whether `sigFailed` derives from merged account+paymaster validation data.
2. **Paymaster drain**: who pays when an op fails *after* validation? (Answer: paymaster, by design — so audit the race window between re-validation and mining, and the deposit accounting math in DepositManager.)
3. **Gas estimation manipulation**: is `preVerificationGas` floor-checked against `calcPreVerificationGas`? Are the overhead constants chain-aware or hardcoded L1 values (nonZeroByte: 16)?
4. **Replay**: does `getUserOpHash` bind chainId + EntryPoint address? Are `validAfter`/`validUntil` enforced with a future-validity floor (`VALID_UNTIL_FUTURE_SECONDS`)?
5. **Front-running / MEV**: is the bundle submitted via public mempool (`signer.sendTransaction`) or private/conditional RPC (`eth_sendRawTransactionConditional`)? Any swap-carrying UserOp in a public-mempool bundle is sandwichable; the bundler itself can reorder.
6. **Tampering**: any field mutated between signature verification and bundle submission? Compare nonce/sender with BigNumber-aware equality, not raw `===`, when the value may arrive as number vs hex string.

## Class-level knowledge

### DepositManager wrong-variable bug (confirmed live in eth-infinitism lineage)
Pattern to grep in any fork:
```ts
for (const entry of this.mempool.getMempool()) {
  if (entry.userOp.paymaster === paymaster) {
    deposit = deposit.sub(BigNumber.from(getUserOpMaxCost(userOp)))  // BUG: userOp (the NEW op) instead of entry.userOp
  }
}
```
Two-sided impact:
- **Undercount → drain vector**: new op small (100), existing ops big (600+350), deposit 1000 → buggy check passes (700 ≥ 0), correct check fails (−50). Bundle reverts on-chain with AA31 mid-execution; bundler eats the gas up to the revert point; repeatable griefing.
- **Overcount → false-positive DoS**: new op big, many small existing ops → legit paymaster ops rejected with "paymaster deposit too low".
Verify quickly with a pure-logic PoC (no node needed): reimplement the loop and the correct loop, feed crafted cost arrays, show divergent ACCEPT/REJECT. Recipe and verified case numbers in `examples/hunts/web3/erc4337-bundler-audit/references/aa-bundler-u2u-2026-08.md`.

### Other recurring findings in this codebase class
- **`calcPreVerificationGas` L1-calibrated defaults** (`fixed:21000, perUserOp:18300, zeroByte:4, nonZeroByte:16`): on L2/custom chains with different calldata pricing the floor is systematically wrong → bundler subsidizes or over-rejects. Config overrides exist but are optional.
- **`estimateUserOperationGas.callGasLimit` via plain `estimateGas`** — no validation-context cap; state-dependent ops estimate cheap then run expensive.
- **Replacement spam**: `checkReplaceUserOp` only requires 10% fee bump; `opsSeen` reputation not decremented on replace → reputation inflation vector.
- **Mempool sort ascending by priorityFee** in `getSortedForInclusion` — cheap ops first; combined with public submission, ordering is attacker-influenceable.
- **Unsafe mode** (`--unsafe`): skips opcode/stake tracer checks but NOT sig check — report as griefing-hardener, not a sig bypass; visible in `clientVersion()` suffix.
- **Debug RPC auto-enabled on dev chains** (chainId 31337/1337) — `debug_bundler_clearState`, `sendBundleNow` etc. Fine on devnet; check it's not reachable on the production deployment.
- **Web2-level DoS — no payload size limit:** Send a large JSON-RPC body (100KB+) to `/rpc` and check if it's accepted (200 OK). Bundlers behind Express `body-parser` with default `limit: '100kb'` may accept larger payloads on newer versions. Test: `curl -d '{"jsonrpc":"2.0","method":"eth_chainId","params":["AAAA...100KB..."],"id":1}'` → 200 = no size cap. Combined with `/unsafe` mode, this amplifies griefing surface.
- **Web2-level stack trace leak:** Malformed JSON in the RPC body may trigger a full stack trace from `body-parser` or the Express error handler, revealing server paths (`/usr/src/app/node_modules/body-parser/lib/types/json.js`), framework versions, and internal module layout. Test: send syntactically invalid JSON (unbalanced braces, extra commas) and check if the response is HTML with a stack trace instead of a JSON-RPC error. This is an infrastructure finding, not a protocol bug — cross-reference with `web2-attack-surface-audit`.
- **Web2-level injection surface (JSON-RPC params):** Test command injection, SQLi, XXE, SSTI, and prototype pollution in JSON-RPC params. Most bundlers validate hex fields (blocking command injection and SSTI), but prototype pollution via `__proto__` in UserOperation objects may pass validation and reach deeper logic. Cloudflare/CDN WAF often sits in front and blocks SQLi/XXE with 1020 blocks — test each injection class once, note which are blocked by WAF vs app-level validation, and move on.

### What's usually SAFE (don't waste rounds re-proving)
- Cross-chain replay: `getUserOpHash` binds chainId + EP address (EIP-712-style domain).
- Post-signature tampering: any field change alters the hash → sig invalid.
- Same-chain replay: EP nonce enforcement on-chain.
- Sig validation itself: enforced twice (mempool admission + pre-bundle re-validation) plus on-chain.

## Report format the operator expects (red-team brief style)
Per attack vector: verdict (✅ NEMU / ⚠️ SEBAGIAN / ❌ GAGAL + why), exploit steps numbered, exact file:line, honest severity. Match the operator's language/register (e.g. Indonesian santai for the U2U hunt). End with a severity table + quick-fix recommendations.

## Pitfalls
- **Claiming sig bypass from `--unsafe` mode** — sig is still checked there; only opcode/stake checks are skipped. Overclaiming kills credibility.
- **Reporting DepositManager bug as only a drain** — it is bidirectional (drain + false-positive DoS); show both cases in the PoC.
- **Auditing the EP contract when the brief is the bundler** — on-chain EP logic is heavily battle-tested upstream; the off-chain accounting/reputation/estimation code is where forks carry live bugs.
- **Skipping the flag surface** — `runBundler.ts` options (`--unsafe`, `--debugRpc`, `--conditionalRpc`) and their defaults change the trust model; document which flags the target deployment runs before scoring severity.

## Reference Files
- `examples/hunts/web3/erc4337-bundler-audit/references/aa-bundler-u2u-2026-08.md` — U2U aa-bundler (eth-infinitism v0.6.0 fork, EP v0.7) red-team session: full six-vector verdicts, DepositManager bug analysis with PoC, gas-calibration notes, MEV exposure.

## Quality Bar
- [ ] Every "safe" verdict has the defending file:line cited, not just an assertion?
- [ ] DepositManager loop read line-by-line (not assumed correct because upstream)?
- [ ] Gas constants checked against the target chain's calldata pricing?
- [ ] Bundle submission path (public vs conditional/private RPC) identified?
- [ ] Debug/unsafe flag exposure checked for the actual deployment?
