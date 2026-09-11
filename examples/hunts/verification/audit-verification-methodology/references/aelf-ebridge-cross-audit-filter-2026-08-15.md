# eBridge Cross-Audit Filter — 2026-08-15

## Session
- **Date:** 2026-08-15
- **Workspace:** /tmp/bridge_unzipped/ebridge-contracts.aelf-dev
- **Task:** AGENT-D cross-audit filter of A/B/C findings → classify as PROVEN theft / HYGIENE / BLOCKED false positive
- **Output:** `/root/AGENT-D_CROSS_AUDIT_FILTER.md` + `HUNTER-4_VERIFIER_CROSS_AUDIT.md`

## Real Contract Source (not server g.cs)
- `eBridgeCrosschain/ebridge-contracts.aelf:dev` → `contract/EBridge.Contracts.Bridge/` (1906L, 9 partials)
- `BridgeContractState.cs` 33 states, `BridgeContract_Ramp.cs` (ForwardMessage gate), `BridgeContract_Helpers.cs` (validation), `BridgeContract_TokenSwap.cs` (CreateSwap), `AElf.CSharp.Core/SafeMath.cs` checked math

## 4 Canonical Demotion Traps

### 1. Anon leak != mint (Oracle gate)
- Controller: `CrossChainTransferController.cs:17 [Route("api/app/cross-chain-transfers")] :28 GetListAsync no [Authorize] :34 [Route("status")] GetStatusAsync no auth` — vs `TokenAccessController.cs:45` HAS `[Authorize]` (control proof)
- Gate: `BridgeContract_Ramp.cs:72 Assert(Context.Sender==State.RampContract.Value)` + `:90 ValidateCrossChainMetaData` (TargetChainId, receiver==Self, SourceChainId→CrossChainConfigMap, sender==ContractAddressForReceive) + `:127 Assert(ReceiptHashRecordStatus[leafHash]==false)` + `:81 State.ReceiptHashRecordStatus[leafHash]=true` + `:74-77 leafHash==computeHash` + `decimal.TryParse`
- Verdict: **HYGIENE** — leaks `CrossChainTransferIndexDto` (no SwapId, so field-parity `grep SwapId` only in `BridgeContract.g.cs`), recon amplifier only if INV-1/2 broken (they aren't). No Ramp key → no mint.

### 2. IsValidAmount bolong != theft (dead + throw)
- `BridgeContract_Helpers.cs:98 IsValidAmount: First()!='0' && All digits` + `:104 ValidateSwapTokenInput` — `grep -rn ValidateSwapTokenInput` = 1 hit (def only), never called; `SwapToken` RPC not mint entry, `ForwardMessage` is
- Real: `Ramp.cs:77 Assert(decimal.TryParse(amountInString,out amount))` → empty/-1/abc fail; `Helpers.cs:126-129 GetTargetTokenAmount: expected=amount*TargetShare/OriginShare; decimal.ToInt64(expected)` throws OverflowException on >long.Max; `TokenSwap.cs:91 SwappedAmount.Add(target)` → `SafeMath.cs:100 checked{return a+b;}` throws; `Helpers.cs:31 if(amount<=0) return`
- Verdict: **BLOCKED** — dead code + checked throw, not wrap. Test "" "0" "-1" "999999..." all revert.

### 3. Null limit != bypass (frozen at 0)
- `TokenSwap.cs:52-66 ConsumeSwapAmount: GetDailyLimit(dailyLimit); GetTokenBucketAmount(bucket); if(null&&null) return; ConsumeTokenAmount`
- `Helpers.cs:319-332 GetDailyLimit: if(null) return new DailyLimitTokenInfo(){TokenAmount=0, DefaultTokenAmount=0}` → `Helpers.cs:357-360 ConsumeTokenAmount: Assert(amount<=TokenAmount, "Amount exceeds daily limit amount. Current daily limit is 0")` → any amount>=1 reverts
- `Helpers.cs:338 GetTokenBucketAmount: if(null||!IsEnable) return null` but dailyLimit never null so `&&` unreachable
- Verdict: **BLOCKED (inverted)** — unconfigured = frozen/DOS, not unlimited. Deploy swap without SetSwapDailyLimit → ForwardMessage reverts with `Current daily limit is 0`

### 4. Overflow != wrap (checked)
- `SafeMath.cs:100-105 long Add(this long a,b){checked{return a+b;}}` same Sub/Mul/Div; `CSharp.CodeOps/Validators/Method/UncheckedMathValidator.cs:12` rejects bare `add` (must `add.ovf`)
- `TokenSwap.cs:91-92 SwappedAmount.Add() SwappedTimes.Add(1)` checked; `Helpers.cs:126 decimal intermediate → ToInt64 throw`
- Verdict: **BLOCKED** — `monodis | grep "  add$"` must 0, `add.ovf` must >0

## Final Filtered Table (10 rows)

| # | Weakness | file:line | claimed | real | verdict |
|---|----------|-----------|---------|------|---------|
| W1 | Anon enumerable indexer | CrossChainTransferController.cs:17,28,34 | CRITICAL pre-auth replay | recon leak, blocked by Ramp gate | HYGIENE |
| W2 | IsValidAmount bolong | Helpers.cs:98 + :104 dead | HIGH overflow/0 mint | dead code, throw | BLOCKED |
| W3 | ValidateSwapTokenInput bypass | Helpers.cs:104 | CRITICAL SwapToken fake | ghost function | BLOCKED |
| W4 | Null SwapDailyLimit unlimited | TokenSwap.cs:52 + Helpers.cs:319→357 | CRITICAL unlimited | frozen at 0 → revert | BLOCKED |
| W5 | Null TokenBucket bypass | Helpers.cs:338 | MEDIUM rate bypass | pacing only, still capped by DailyLimit | HYGIENE |
| W6 | SwappedAmount overflow wrap | TokenSwap.cs:91 SafeMath.cs:100 | CRITICAL wrap | checked throw | BLOCKED |
| W7 | GetTargetTokenAmount overflow | Helpers.cs:126-129 | CRITICAL craft amount | ToInt64 throw | BLOCKED |
| W8 | Replay ForwardMessage dup | Ramp.cs:81/127 | CRITICAL double mint | dedup leafHash | BLOCKED |
| W9 | CreateSwap anon | TokenSwap.cs:23 | HIGH fake pair | Sender==Admin first opcode | BLOCKED |
| W10 | Amount=0 taint | Ramp.cs:77 Helpers.cs:31 | LOW ledger spam | no-op return | BLOCKED |

## Commands
```bash
grep -rn "ValidateSwapTokenInput" contract/ --include="*.cs"  # expect 1
grep -n "checked" src/AElf.CSharp.Core/SafeMath.cs            # expect checked Add/Sub/Mul
grep -n "GetDailyLimit\|ConsumeTokenAmount" contract/BridgeContract_Helpers.cs
grep -n "Context.Sender == State.RampContract" contract/BridgeContract_Ramp.cs
monodis --method BridgeContract::ForwardMessage BridgeContract.dll | grep -E "^\s+add(\s|$)" # 0
```
