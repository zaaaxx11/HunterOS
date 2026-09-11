---
name: defi-audit-verification
description: "verify DeFi audit claims vs source"
---

# DeFi Audit Verification

## When to Use

- External report claims CRITICAL drains on yield-bearing stablecoins or hub-and-spoke protocols (Base main + sub-chain vaults via LayerZero/Axelar/CCIP).
- Need to triage claims as VERIFIED / PARTIAL / THEORETICAL / FALSE before bounty.

## Workflow

### 1. Inventory
Extract each claim's file:line, function, and boundary. Flag claims without source ref.

### 2. Gate Checks

| Claim | Gate | Rule |
|-------|------|------|
| Strategy oracle self-report | `strategiesStats` / `updateFromStructs` modifiers (`onlyAdmin` vs `onlyAxelarorLZ`) + `StrategyManager.add/activateStrategy` (onlyAdmin + cooldown + canActivate) | BLOCKED pre-auth if onlyAdmin; PARTIAL post-admin |
| Sig replay no chainId | `_lzReceive(Origin calldata,)` uses Origin? Callable by EOA? `peers[eid]` via `onlyAdmin _setPeer`? `execute() onlyAdmin`? | THEORETICAL if endpoint-only + peer ACL |
| Admin setter hijack | `setTokenMessenger` etc modifiers | OVERRATED if onlyAdmin |
| Single admin control | `AuthorityControl` deployer grant vs `TimeLock/TimelockController` wiring (deploy scripts) | File existence != enforcement |
| ERC4626 zero-assets | `totalAssets() -> _convertToShares mulDiv(...,totalAssets)` | FALSE if div0 reverts (DoS) |
| Queue HoL block | `fulfillNFT` loop: `if(skip)` vs `require(block)` | FALSE if skip keeps liveness |

### 3. Lightweight PoC (Python when forge unavailable)

```python
# inflation needs admin activation
inflated = MainTokenStatsSim(vault=100_000*1e6).strategiesStats([FakeStrategy(1_000_000*1e18)])
yieldMint = inflated*1e18 - 150_000*1e18  # 950k via updateYield->addYield
# zero-asset
totalAssets = 0
shares = 1e18 * totalShares // totalAssets  # ZeroDivisionError -> revert not mint
```

### 4. Severity
Admin-key-required drain = HIGH centralization, not CRITICAL pre-auth. TOCTOU 7200s = LOW.

## Reference

- Case study `examples/hunts/web3/defi-audit-verification/references/tizi-verification-2026-08-18.md` — Tizi 33-sol verification, 7 claims file:line table, Python sims, 7 pitfalls.

## Checklist

- [ ] Every claim has file:line via search_files/read_file
- [ ] Label VERIFIED/PARTIAL/THEORETICAL/FALSE/BLOCKED + PoC status
- [ ] No time inflation; failed vectors documented
