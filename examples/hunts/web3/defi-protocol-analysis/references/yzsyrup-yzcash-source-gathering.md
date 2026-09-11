# yzSyrup / yzCash Vault Source Code Gathering - Case Study

## Protocol Overview
- **Protocol**: yzSyrup & yzCash vaults (ERC4626)
- **Addresses**: 
  - yzSyrup: `0xc9854f2af89d4d26837004d1e154bd3c3c1009b1`
  - yzCash: `0x224e90591a2d63fb66e677d0561ea4a6ad1f098d`
- **Chains**: Ethereum Mainnet
- **Product Branding**: "yuzu money" / "yuzu finance"

## Recon Results (2025-07-24)

### Etherscan Source Code
| Contract | Verified | API Access | Notes |
|----------|----------|------------|-------|
| yzSyrup | ✅ Yes | ❌ API Key required | V2 API only, no free tier |
| yzCash | ✅ Yes | ❌ API Key required | V2 API only, no free tier |

**Result**: Cannot programmatically fetch source - Etherscan V1 deprecated, V2 requires paid API key

### GitHub Search
| Search Query | Results | Notes |
|--------------|---------|-------|
| `yuzu money` | 0 repos | Product name ≠ org name |
| `yuzu finance` | 1 org (`yuzu-finance`) | Only UniversalToken fork + landing page |
| `yzSyrup` | 0 repos | No matches |
| `yzCash` | 0 repos | No matches |
| `yzsyrup` | 0 repos | No matches |
| `yzcash` | 0 repos | No matches |

**Key Finding**: Protocol branding ("yuzu money") does NOT match GitHub org names. The actual contracts are likely under a different legal entity name.

### Curvance Discovery
| Search | Result |
|--------|--------|
| `yuzu defi` | 8 repos (balanced-dev/yuzu-definition-cli - unrelated) |
| `curvance` | Found `curvance` org with 2 repos |
| `curvance/curvance-contracts` | 125KB Solidity, active (pushed 2026-07-14) |

**Hypothesis**: yzCash vault is part of Curvance protocol (known DeFi lending/liquidity protocol). yzSyrup source still not found - may be separate implementation or in private repo.

### Source Acquisition Methods Tried
| Method | yzSyrup | yzCash (via Curvance) |
|--------|---------|----------------------|
| Etherscan API (v1/v2) | ❌ Deprecated/paid | ❌ Deprecated/paid |
| GitHub code search (address) | ❌ Auth required | ❌ Auth required |
| GitHub repo search (brand) | ❌ 0 results | ❌ 0 results |
| GitHub org search | ❌ Wrong orgs | ✅ Found `curvance` |
| Git clone (HTTPS) | N/A | ❌ `remote-https` helper missing |
| ZIP download + unzip | N/A | ✅ **WORKED** |

**Working Method**:
```bash
curl -L -o curvance-contracts.zip "https://github.com/curvance/curvance-contracts/archive/refs/heads/develop.zip"
unzip -q curvance-contracts.zip -d curvance-contracts
```

## Architecture Inference (from Curvance contracts)

### Expected yzCash Structure (Curvance)
- **Vault Factory**: ERC4626 vaults deployed via factory (create2)
- **Strategy Adapters**: Curvance dimension adapters for yield sources
- **Proxy Pattern**: EIP-1967 / UUPS likely
- **Governance**: Timelock + multi-sig (check admin slots)

### Expected yzSyrup Structure (Unknown)
- Separate implementation from yzCash?
- Same factory or different?
- Same admin/governance?

## Risk Assessment

| Risk | yzCash | yzSyrup |
|------|--------|---------|
| Unverified source | ❌ No (verified but inaccessible) | ❌ No |
| Public repo | ⚠️ Via Curvance | ❌ No |
| Audit reports | Unknown | Unknown |
| Admin keys known | Need to check Curvance contracts | Unknown |
| Upgradeability | Need to check proxies | Unknown |

## Recommendations for Static Analysis

### For yzCash (Curvance contracts available)
1. Clone Curvance contracts locally
2. Search for ERC4626 vault implementations
3. Find factory deployment scripts
4. Trace from factory → implementation → proxy admin
5. Analyze: share calculation, oracle integration, access control, reentrancy

### For yzSyrup (source unavailable)
1. **Trace transactions**: Make test deposit on mainnet fork → trace USDC flow
2. **Decompile bytecode**: Use `cast code <address> | panoramix` or etherscan decompiler
3. **Find factory**: Trace deployer of yzSyrup contract
4. **Check similar protocols**: Other ERC4626 vaults by same team

## Lessons Learned

### 1. Brand ≠ Org Name
- "yuzu money" → NOT `yuzu-money` org
- Check DeFiLlama, CoinGecko, Twitter for actual entity name
- Curvance is the likely developer entity

### 2. Etherscan API is Not Reliable for Free Users
- V1 deprecated
- V2 requires paid tier for most chains
- **Always have fallback**: manual download, blockscout, sourcify, decompilation

### 3. GitHub Search Strategies
- Search by contract address (requires auth)
- Search by unique function selectors/event topics from decompiled bytecode
- Search by proxy implementation address (more discoverable)
- Search by deployer address
- Check audit firm reports for repo references

### 4. Git Transport Issues
- Some environments lack `git-remote-https` helper
- **Always have ZIP fallback**: `curl -L -o repo.zip "https://github.com/owner/repo/archive/refs/heads/branch.zip"`

### 5. Cross-Reference Discovery
- Found Curvance via "yuzu defi" search
- Curvance is a known protocol with public contracts
- Protocol teams often build multiple products under same infra

## Quick Reference: Source Gathering Checklist

```bash
# 1. Try Etherscan API (with key if available)
curl "https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address=<addr>&apikey=<key>"

# 2. Try GitHub code search (requires token)
curl -H "Authorization: token <gh_token>" "https://api.github.com/search/code?q=<address>+language:solidity"

# 3. Try GitHub repo search
curl "https://api.github.com/search/repositories?q=<protocol>+vault+language:solidity"

# 4. Try GitHub org search
curl "https://api.github.com/users/<suspected-org>/repos"

# 5. ZIP download fallback
curl -L -o repo.zip "https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip"
unzip -q repo.zip

# 6. On-chain tracing (if all else fails)
cast tx <deposit_tx_hash> --rpc-url <rpc> --trace
# OR
cast call <vault> "deposit(uint256,address)" <amt> <to> --rpc-url <rpc> --trace

# 7. Decompile if unverified
cast code <address> --rpc-url <rpc> | panoramix
```