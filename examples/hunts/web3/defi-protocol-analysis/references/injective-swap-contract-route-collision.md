# Injective Swap Contract — Route Key Collision & Cross-Validation Findings
## Date: 2026-07-28
## Source: 4-agent adversarial analysis + manual cross-validation

### CRITICAL FINDING: Route Key Collision

**Root cause:** `state.rs` lines 56-62 — `route_key()` uses alphabetical ordering

```rust
fn route_key(source: &str, target: &str) -> (String, String) {
    if source < target {
        (source.to_string(), target.to_string())
    } else {
        (target.to_string(), source.to_string())
    }
}
```

**Bug:** Route A→B and B→A map to the SAME storage key. Admin setting B→A REPLACES A→B.

**Affected pairs:** ALL bidirectional route pairs share the same key (e.g., USDT↔ETH, INJ↔USDT, ATOM↔ETH).

**Impact:** 
- Users' swaps go through COMPLETELY DIFFERENT markets than intended
- If markets have different liquidity depth → massive slippage
- May succeed on wrong price path (silent fund loss) or revert (gas loss)

**Fix:** Use compound key `(source, target)` to preserve direction.

### Cross-Validation Methodology

This finding was discovered through systematic cross-validation:
1. Agent 4 (Red Team) initially claimed "fee overflow → i128 negative wrap → output inflation"
2. Manual source code review proved this INCORRECT — i128 won't wrap for realistic fee_multiplier values
3. Route key collision was found through independent deep reading of `state.rs`
4. FPDecimal formatting bug in Python simulations discovered: `__format__` unsupported, use `float(val)` instead

### Other Verified Findings Summary

| # | Severity | Title | Confidence |
|---|----------|-------|------------|
| 1 | CRITICAL | Route Key Collision | PROVEN |
| 2 | CRITICAL | Admin Fund Drain (withdraw_support_funds) | PROVEN |
| 3 | HIGH | No Timelock on Admin Transfer | PROVEN |
| 4 | MEDIUM | Swap State Not Cleaned on Error | THEORETICAL |
| 5 | MEDIUM | Unbounded Fee Multiplier | THEORETICAL |
| 6 | LOW | Exact Output Overestimation | PROVEN |