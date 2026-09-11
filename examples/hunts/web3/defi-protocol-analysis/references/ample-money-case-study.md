# Ample Money Protocol - Case Study

## Protocol Overview
- **Name**: Ample Money
- **Type**: Prize-Linked Savings (Yield Lottery)
- **Category**: Yield Lottery (DeFiLlama)
- **Chains**: Base (primary), Arbitrum, BSC, Solana, Hyperliquid L1, Katana, Monad
- **TVL**: ~$4.5M peak, ~$3.6M current (Base)
- **Token**: None (USDC deposits)
- **Website**: https://ample.money/
- **App**: https://app.ample.money/ (Cloudflare)
- **Docs**: https://docs.ample.money/ (Cloudflare)
- **Twitter**: @AmpleHQ

## Protocol Mechanics
- **Deposit**: Users deposit USDC (no lockups)
- **Yield Source**: "Short-duration USD assets through onchain money markets" (Aave, Compound, Morpho, etc.)
- **Yield Pooling**: All yield pooled together
- **Distribution**: "Redistributed through payout cycles to select recipients" via "verifiable on-chain randomness"
- **No Lockups**: Principal always withdrawable

## Recon Results (2024-07-24)

### Infrastructure
| Component | Status |
|-----------|--------|
| Website | ✅ Live (Next.js, Cloudflare) |
| App | ⚠️ Cloudflare challenge |
| Docs | ⚠️ Cloudflare challenge |
| GitHub (ample-money) | ❌ 0 public repos |
| GitHub (ample-money org) | ❌ 0 public repos |
| BaseScan Verified | ❌ 0 contracts |
| BaseScan API | ❌ Deprecated V1, V2 paid |
| BaseScan Web | ❌ Cloudflare blocks |
| Etherscan V2 | ❌ Free tier no Base |
| GitHub Repos | ❌ None found |
| Audit Reports | ❌ None found |
| Bug Bounty | ❌ None listed |

### On-Chain Findings (Base)
| Address | Type | Size | USDC | Notes |
|---------|------|------|------|-------|
| 0x032a7252b4932c44bde89aee6275744376a96bff | Contract | 4,918 bytes | 9.51 USDC | Small contract |
| 0x2c6e716ab68dc81762203fab071ca146d34d9242 | Contract | 1,283 bytes | 0 USDC | Tiny contract |
| 0x9126236476efba9ad8ab77855c60eb5bf37586eb | Contract | 11,728 bytes | 0 USDC | Medium contract |

**Main Vault (holding $3.6M TVL): NOT FOUND**

### On-Chain Patterns
- **Active USDC transfers** to multiple contracts detected
- **Suspicious EOA** `0x8581784d3e598cca3482375cff2409ac9dd8c402` making many USDC transfers to contracts
- **No verified contracts** with "ample" in name on BaseScan
- **Deployer**: `0xf03a3f3b27f5c32285370ef7282b76ba12af6b81` created multiple proxy contracts
- **Proxy Pattern**: EIP-1967 (InitializableImmutableAdminUpgradeabilityProxy)

## Risk Assessment: CRITICAL

| Red Flag | Status |
|----------|--------|
| Closed Source | ✅ Yes |
| Unverified Contracts | ✅ Yes |
| No Audits | ✅ Yes |
| Anonymous Team | ✅ Yes (org empty) |
| No Bug Bounty | ✅ Yes |
| Cloudflare Everywhere | ✅ Yes |
| $3.6M TVL | ✅ Yes |

## Architecture (Inferred)
```
User USDC → Vault Factory → Strategy Vault(s) → Yield Aggregator
                                    ↓
                            Yield Pool (all yield)
                                    ↓
                            Prize Pool (RNG)
                                    ↓
                            Payout Distributor
```

## Expected Contract Types
| Contract | Expected Pattern |
|----------|------------------|
| Vault Factory | ERC4626 + create2 deploy |
| Prize Pool | PoolTogether V5 style |
| Yield Adapters | Aave/Compound/Morpho wrappers |
| RNG | Chainlink VRF / custom |
| Distributor | Merkle proof / direct claim |

## Recommendations for Audit

### Immediate (Pre-Deposit)
1. **Find main vault** - trace USDC deposit tx from app
2. **Verify all contracts** on BaseScan
3. **Audit admin keys** - check proxy admin, timelock
4. **Check oracle config** - Chainlink vs custom
5. **Verify RNG** - Chainlink VRF vs custom

### Audit Scope
1. **Vault/Factory** - ERC4626 compliance, deposit/withdraw
2. **Prize Pool** - RNG, tier distribution, claim logic
3. **Yield Adapters** - Aave/Compound/Morpho integration
4. **Prize Distributor** - claim, double-claim, Merkle
5. **Admin/Upgrade** - proxy, timelock, ACL
5. **RNG** - VRF vs custom, bias

## Red Flags Summary
| Flag | Severity |
|------|----------|
| Zero verified contracts | 🔴 CRITICAL |
| Zero public repos | 🔴 CRITICAL |
| Cloudflare everywhere | 🔴 CRITICAL |
| No audit reports | 🔴 CRITICAL |
| Anonymous team | 🔴 CRITICAL |
| $3.6M TVL unverified | 🔴 CRITICAL |
| No bug bounty | 🟠 HIGH |
| Cloudflare blocks recon | 🟠 HIGH |

## Recommendation
**DO NOT DEPOSIT** until:
1. Source code public on GitHub
2. Contracts verified on BaseScan
3. Audit by reputable firm (Trail of Bits, Spearbit, Zokyo, etc.)
4. Bug bounty program live
5. Team doxxed with track record

## For Researchers
To find main vault:
1. Make test deposit on app.ample.money → trace tx
2. Trace USDC flows from deposit → find vault
3. Trace deployer of found contracts → find factory
6. Monitor BaseScan for new verified contracts