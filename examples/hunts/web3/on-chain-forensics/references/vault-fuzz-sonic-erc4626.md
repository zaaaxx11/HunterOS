# Vault Fuzz — Sonic ERC4626 (FlyingTulip d1e5 / 7127) — 2026-08-09

Throttled eth_call fuzz against ERC4626 vault clones on Sonic (0.6s delay, 12s timeout).

## Targets
- `0xd1e5a86f1005f6356bd022c587de0f430cd2aeb1` — clone impl `0x5aee4b34df62790581e2f2c31468ddfd7020e841` (69 sels, 23kb). asset `0xf7d85ec4...9c9c` (6dec USDC clone). FT `0x5DD1...082c`.
- `0x7127bb9d9ad0f47b8da9087e634d67f3946f840e` — clone impl `0x051589975909644bee7c33c037a7d2009c8f1839` (20kb). circuitBreaker().
- `0xf7d85ec4e7710f71992752eac2111312e73e9c9c` — impl `0xf47bb65fb0886be183db541afce555345e3e1885` (49 sels, USDC with blacklist).

## Fuzz Matrix (eth_call)
```
previewDeposit(0) -> 0
previewDeposit(1) -> 1   (1:1 on empty vault)
previewDeposit(1e6) -> 1e6
previewDeposit(1e15..1e21) -> OK (no overflow at 1e21)
convertToShares(1) -> 1, convertToAssets(1) ->1
maxDeposit(EOA) -> type(uint256).max  (no cap = blackswan)
maxRedeem/maxWithdraw -> 0 (zero shares)
totalAssets==totalSupply==261417254558 (261k 6dec) — vault not empty
previewDeposit(1e18) initially reverted due to bad padding (hex zfill 64 required), not logic
```

## Anomaly — 7127 revert
```
totalSupply() OK huge, totalAssets() revert, convertToShares(1) revert, previewDeposit(1) revert
```
→ circuitBreaker lag (CB-01) likely active or oracle stale. Funds 14k FT potentially locked DoS.

## Checks
- `epoch()` -> 247, `epochs(247)` packed, `epochSettler() 0xed00...226f`
- `asset()` -> f7d8, `FT()` -> 0x5DD1, `paused()` false, `decimals()` 6
- f7d8 has `masterMinter`/`blacklist`/`updateBlacklister` -> owner Safe 0x1118 can freeze vault asset (261k)
- 8997 (172 bytes) is forwarder delegating to Safe 0x29fc (24kb Gnosis Safe nonce 0, threshold 1, not setup)

## Pitfall
Zero-padding for uint256 calldata: `hex(val)[2:].zfill(64)` — missing leading zeros causes silent revert. Always 64 hex chars.
