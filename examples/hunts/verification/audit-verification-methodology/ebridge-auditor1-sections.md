# eBridge CROSS-AUDIT FILTER + AUDITOR-1 RPC re-audit sections (cut from audit-verification-methodology SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/verification/audit-verification-methodology/SKILL.md`
during the S2b-2 content pass and rewritten in place target-agnostically.
Case refs moved with this skill live in
`examples/hunts/verification/audit-verification-methodology/references/`
(aelf-ebridge-cross-audit-filter-2026-08-15.md, alpenglow-audit-verification-log.md).

---

## CROSS-AUDIT FILTER — BRUTAL NO-OVERSELL (2026-08-15 eBridge Pattern)

**Four canonical traps (why A/B/C were demoted) — memorize:**

1. **Anon leak != mint (Oracle gate):** `BridgeContract_Ramp.cs:72 Assert(Context.Sender==State.RampContract.Value)` + `:90 ValidateCrossChainMetaData` + `:127 Assert(ReceiptHashRecordStatus==false)` + `:81 set true`. Anon `CrossChainTransferController.cs:17,28,34` (no `[Authorize]` vs `TokenAccessController.cs:45` which has it) leaks recon, but `ForwardMessage` needs `input.Message` bytes that pass `leafHash==computeHash` + Ramp sender. Without Ramp key/oracle compromise → no mint. Severity = LOW alone, CRITICAL-amplifier only if INV-1/2 broken (they aren't).

2. **IsValidAmount bolong != theft (ToInt64 throw + dead code):** `BridgeContract_Helpers.cs:98 IsValidAmount` + `:104 ValidateSwapTokenInput` — `grep -rn ValidateSwapTokenInput` = 1 hit (definition only), never called. `SwapToken` RPC not even the mint entry — `ForwardMessage` is. Real path `Ramp.cs:77 decimal.TryParse` + `Helpers.cs:129 decimal.ToInt64(expected)` throws `OverflowException` (not wrap), `TokenSwap.cs:91 SwappedAmount.Add()` → `SafeMath.cs:100 checked{return a+b;}` throws, `Helpers.cs:31 if(amount<=0) return`. Test `"" "0" "-1" "999..."` all revert.

3. **Null limit != bypass (frozen at 0):** `TokenSwap.cs:52-66 ConsumeSwapAmount` calls `GetDailyLimit(dailyLimit)` which at `Helpers.cs:319 if(null) return new DailyLimitTokenInfo(){TokenAmount=0}` → `ConsumeTokenAmount Helpers.cs:357 Assert(amount<=TokenAmount,"Amount exceeds daily limit...0")` reverts any `amount>=1`. `GetTokenBucketAmount Helpers.cs:338 null||!IsEnable→null` but `if(null && null) return` is dead because dailyLimit never null. Unconfigured = frozen/DOS, not unlimited. Prove by deploying swap without `SetSwapDailyLimit` → ForwardMessage reverts with `Current daily limit is 0`.

4. **Unchecked overflow != wrap (SafeMath checked + validator):** `AElf.CSharp.Core/SafeMath.cs:100-105 long Add(this long a,b){checked{return a+b;}}` (same Sub/Mul/Div). `CSharp.CodeOps/Validators/Method/UncheckedMathValidator.cs:12` rejects bare `add` (must be `add.ovf`). All `TokenSwap.cs:91-92 Add` are checked. `GetTargetTokenAmount Helpers.cs:126 decimal expected = amount*TargetShare/OriginShare; ToInt64` — decimal 128-bit intermediate, overflow throws.

**Verification commands (run before claiming theft):**
```bash
grep -rn "ValidateSwapTokenInput" contract/ --include="*.cs" # must be 1 hit = dead if claiming bolong
grep -n "checked" src/AElf.CSharp.Core/SafeMath.cs           # must show checked Add/Sub/Mul
grep -n "GetDailyLimit\|ConsumeTokenAmount" contract/BridgeContract_Helpers.cs
grep -n "Context.Sender == State.RampContract" contract/BridgeContract_Ramp.cs
monodis --method BridgeContract::ForwardMessage BridgeContract.dll | grep -E "^\s+add(\s|$)" # must 0
monodis --method BridgeContract::ForwardMessage BridgeContract.dll | grep "add.ovf"         # must >0
```

→ See `examples/hunts/verification/audit-verification-methodology/references/aelf-ebridge-cross-audit-filter-2026-08-15.md` for full table and 10-row verdict.

---

## RE-AUDIT (ADVERSARIAL) — RPC AUTH PATTERN (2026-08 AUDITOR-1)

When re-auditing a prior RPC auth bypass claim (CORS + loopback + BasicAuth + whitelist), classify every claim as **VERIFIED FACT** (file:line proven) vs **ASSUMPTION** (to disprove). Workflow that caught the `localhost` gating in bityuan (see `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/bityuan-rpc-auth-re-audit-2026-08.md`):

1. **CORS default proven, not assumed** — read `rs/cors` source (`cors.go:123-127` empty `Options{}` → `allowedOriginsAll=true`) and `geth/node/rpcstack.go:376-393` (`NewHTTPHandlerStack(["*"],["*"])`). Check `AllowedMethods`/`AllowedHeaders` defaults to see which preflights pass (`application/json` yes, `Authorization` no for `rs/cors` defaults but yes for `geth` `["*"]`).
2. **Trace handler ordering** — `rpc/http.go:Listen()` order `checkIPWhitelist → checkBasicAuth → IsLoopback skip of func WL/BL`; confirm `co.Handler(handler)` wraps inner handler and `cors.Handler` always calls `h.ServeHTTP` for actual requests (`cors.go:202-221`).
3. **Loopback vs whitelist** — verify `server.go:201 IsLoopback→true` early-return before `remoteIPWhitelist` lookup; same in `ethrpc/rpc.go:250`. Enumerate `127.0.0.0/8` vs `::1` vs `::ffff:127.0.0.1` via `net.ParseIP`. Prove `RemoteAddr` via `net.SplitHostPort(r.RemoteAddr)` not spoofable via `X-Forwarded-For`.
4. **BasicAuth empty→true vs set→mitigates** — `server.go:171-191` empty creds branch; `bityuan.toml` defaults empty (VERIFIED). Note `rs/cors` preflight blocks `Authorization` when `AllowedHeaders` lacks `*` → enabling BasicAuth mitigates CSRF for JRPC but not ethrpc (`AllowedHeaders:["*"]`). Ethrpc `ServeHTTP:218-246` has zero `checkBasicAuth`.
5. **Bind + whitelist gating** — check `bityuan.toml` + `types/defaultcfg.go:91` + `types/cfg.go:289` + `server.go:552 InitIPWhitelist` + `ethrpc/rpc.go:255 empty/["*"]→allow-all`. Default `localhost:8801` binds loopback only → remote direct BLOCKED; needs `0.0.0.0` + `whitelist=["*"]` for critical remote.
6. **Bug non-escalation** — `http.go:159 isLoopBackAddr` only handles `*net.IPNet` → always false for `*net.TCPAddr`; falls through to correct `checkIPWhitelist` so loopback still passes — classify as bug, not bypass.
7. **PoC matrix** — browser `fetch` with `Origin: evil.com` + `Content-Type: application/json` for CSRF, `curl -H Origin` for CORS `*`, `curl -H X-Forwarded-For` for no-spoof, plus `Authorization` header variants; always state prerequisites (same-host browser or `0.0.0.0` rebind).

Output: table `claim | file:line | VERIFIED FACT vs ASSUMPTION | prerequisites`, plus `curl` kill-tests and remediation (explicit `AllowedOrigins`, remove `if !IsLoopback()` bypass, config-driven `NewHTTPHandlerStack`, random `JrpcUserPasswd` on init).
