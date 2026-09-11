# Tizi Verification 2026-08-18 — Yield Stablecoin Hub-and-Spoke (Base)

Source: `tizimoney/Tizi-contract` 33 .sol, $223k TVL, TD (LayerZero OFT) + stTD (ERC4626 upgradeable), hub-and-spoke via LayerZero/Axelar/CCIP. Tarball bypass for missing `git-remote-https` on TencentOS.

## Claims vs Reality (file:line verified)

| # | Claimed (V8.3) | Claimed | File:Line Gate | Reality | Verdict |
|---|---|---|---|---|---|
| C1 | Strategy `tokenValue` 1M → `updateYield` mints 950k | CRITICAL drain | `Statistics/MainTokenStats.sol:154 getTokenInfo()` no oracle; `TiziDollar.sol:167 updateYield onlyAdmin` calls `calculateTotalChainValues()` | `strategiesStats onlyAdmin` (Main)/`onlyAxelarorLZ` (Sub), `StrategyManager.addStrategy:218 onlyAdmin` + `activateStrategy:246 onlyAdmin+cooldown 3d+canActivate` gated | **PARTIAL post-admin** — PROVEN if admin injects FakeStrategy, BLOCKED pre-auth |
| C2 | Sig replay no `chainId` in `(target,nonce,deadline,code)` | CRITICAL | `SubStrategyManager.sol:321 _lzReceive(Origin calldata,)` ignores Origin, `ECDSA.recover` + `hasRole(DEFAULT_ADMIN)` + `target==this` + deadline+usedNonce, no chainId. Same `MainTokenLayerZero.sol:80`. `execute:131 onlyAdmin` | Endpoint-only, OApp `peers[srcEid]` via `onlyAdmin _setPeer` blocks foreign EID. No EOA path. | **THEORETICAL/BLOCKED** |
| C3 | `setTokenMessenger` hijack bridge | CRITICAL | `Vault/MainVault.sol:257 setTokenMessenger onlyAdmin` (plus 247,252,354) | By-design onlyAdmin | **OVERRATED** — HIGH centralization |
| C4 | Single EOA total control 95% no timelock | CRITICAL | `AuthorityControl.sol:17-23` deployer EOA holds DEFAULT_ADMIN. `TimeLock/TimelockController.sol` exists (OZ v5.3) but never granted — `grep -rn Timelock` hits only contract files, no deploy script | Check wiring not file existence | **VERIFIED** centralization HIGH |
| H5 | `totalAssets()==0` → infinite shares | HIGH | `StakedTD.sol:156 totalAssets` → `187 _convertToShares mulDiv(totalShares,totalAssets)` | `div(0)` reverts; sim staked 50k < unreleased 60k → 0 → ZeroDivisionError | **FALSE** — DoS |
| H8 | NFT queue HoL blocking | HIGH | `DepositHelper.sol:384 fulfillNFT` loop `if(amount<=disposable) canWithdraw=true` else skip; `412 fulfillNFTBatch` same | Skip keeps liveness | **FALSE** |
| H7 | Stale `liquidityInfo` 7200s front-run | HIGH | `SubStrategyManager.sol:337 require(now-liquidityInfo.time<=7200)` + `StrategyManager.setLiquidityInfo:209 snapshot` | 2h TOCTOU window | **VERIFIED LOW** |

## PoC (Python fallback)

```python
class FakeStrategy:
    def getTokenInfo(self): return [TokenInfo("USDC", 1_000_000*1e18, 1e18)]
inflated = MainTokenStatsSim(vault=100_000*1e6).strategiesStats([FakeStrategy()])  # 1_100_000
yieldMint = inflated*1e18 - 150_000*1e18  # 950k via updateYield->addYield (needs admin)
totalAssets = 0; shares = 1e18*totalShares//totalAssets  # -> ZeroDivisionError (revert)
```

## Commands

```bash
curl -L -o /tmp/tizi.tar.gz https://github.com/tizimoney/Tizi-contract/archive/refs/heads/main.tar.gz
tar xzf /tmp/tizi.tar.gz -C /tmp/tizi --strip-components=1
grep -rn "onlyAdmin\|Timelock\|AuthorityControl\|_lzReceive\|usedNonce" contracts --include="*.sol"
grep -n "totalAssets\|_convertTo\|setTokenMessenger" contracts/StakedTD.sol contracts/Vault/MainVault.sol
python3 /tmp/tizi_poc_critical1.py
```

## Pitfalls

1. Self-report ≠ oracle bypass — check `onlyAdmin`/`onlyAxelarorLZ` gate on `updateFromStructs`.
2. Missing chainId ≠ replay — endpoint peer ACL may block; verify `setPeer` wiring.
3. ERC4626 zero-assets → revert not mint.
4. Queue `if skip` ≠ `require block`.
5. Timelock file ≠ enforcement — verify DEFAULT_ADMIN holder.
6. Deposit `feeBasisPoints=40` dead var — `deposit()` mints 1:1 unused.
7. Severity: admin-required drain = HIGH centralization, not CRITICAL.
