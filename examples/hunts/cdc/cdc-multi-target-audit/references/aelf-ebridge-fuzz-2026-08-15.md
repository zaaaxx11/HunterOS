# Fuzz IsValidAmount + DailyLimit/Bucket Bypass — eBridge BridgeContract 2026-08-15

## IsValidAmount (`BridgeContract_Helpers.cs:98`)
```cs
bool IsValidAmount(string s) => s != null && s[0]!='0' && s.All(c>='0' && c<='9');
```
- **No length cap** → 19-30 digits pass Gate 1.
- Fuzz 20-vector via `/tmp/fuzz_isvalid.py`:
  - `0/00/01/-1/0x1` → False (blocked)
  - `9223372036854775807` (max int64) → True; `9223372036854775808` (max+1) → True **LOLOS**
  - `9999999999999999999` (19), `18446744073709551615` (uint64 max), `123...30digit` → True **LOLOS**
- Gate 2: `decimal.TryParse` passes (decimal max 7.9e28).
- Gate 3: `GetTargetTokenAmount` (`Helpers.cs:129`) `decimal.ToInt64(expected)` **throws OverflowException** → revert, not wrap. Confirmed via `grep decimal.ToInt64` = hit at 129, checked `.Add()` at `TokenSwap.cs:89`. 15× `Add/Sub/Mul/Div`, 0 unchecked `+`.
- Example: `amount=9223372036854775807` + ratio `1:1000` → expected `9.22e21` → ToInt64 throw → revert.
- `ForwardMessage` (`Ramp.cs:38`) reads `amountByte[64:96]` from oracle-signed `messageByte`, not user string → attacker can't set directly; source is `CreateReceipt` which has `Assert(amount>0)` at `Helpers:270`.

**Fix:** `s.Length>0 && s.Length<=19 && s[0]!='0' && allDigits && long.TryParse(s, out _)`
**Impact:** LOW — gas grief (tx reverts), NOT fund theft.

## DailyLimit / TokenBucket (`TokenSwap.cs:61`, `Helpers.cs:340-400`)

- `GetDailyLimit(null)` → `new DailyLimitTokenInfo{TokenAmount=0}` → `if (null && null) return` is **dead code** (dailyLimit never null after transform).
- `ConsumeTokenAmount(0, null, 100)` → `Assert(100<=0)` → **REVERT** `Amount exceeds daily limit`. New `swapId` without `SetSwapDailyLimit` is **FROZEN**, not unlimited.
- `SetSwapDailyLimit` asserts `DefaultTokenAmount>0` (`Limit.cs:42`), can't set 0. `SetDailyLimit` has `useAmount = Default-TokenAmount` carry-over on mid-day update.
- `GetTokenBucketAmount(null)` → null; `IsEnable=false` → null. Only dailyLimit then. `CalculateRefill` uses `Math.Min(capacity, current+rate*timeDiff)`.
- Cross-day reset: `GetDailyLimit` refills after `DefaultDailyRefreshTime=86400` (`BridgeContractConstants.cs:5`). Spam at 23:59:59 + 00:00:00 = 2× daily limit in 2s — **by design**, not bug.

## Bypass Verdict

| Layer | Bypass? | Evidence |
|-------|---------|----------|
| Replay ReceiptId | BLOCKED | `Helpers:110 Already claimed` + `Ramp:85 ReceiptHashRecordStatus` |
| Overflow string→long | BLOCKED | `ToInt64` throw + checked `.Add()` |
| Null limit → unlimited | REVERSE: frozen (TokenAmount=0) | `Helpers:340`, `TokenSwap.cs:61` |
| Front-run ChangeSwapRatio | PRIVILEGED only | `TokenSwap.cs:118 Sender==Admin` |

## Repro

```bash
python3 /tmp/fuzz_isvalid.py  # 20-vector
grep -n "ToInt64\|(long)" contract/EBridge.Contracts.Bridge/*.cs
```
