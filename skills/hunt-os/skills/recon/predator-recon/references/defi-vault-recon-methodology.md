# DeFi Vault Protocol Recon Methodology

## Overview

When targeting DeFi vault protocols, standard web recon is insufficient. You need an **on-chain analysis phase** that maps the smart contract architecture and identifies exploit vectors.

## 14-Step Pattern

### Step 1: Frontend Scraping
Extract JS bundles from the frontend. Find:
- API URLs (look for `apiUrl` config, `fetch()` calls, `GET()` calls)
- Contract addresses (look for hex strings `0x...`, address patterns)
- Chain IDs (look for `chainId`, `arbitrum`, `ethereum`, etc.)
- Deployer addresses (look for `deployer`, `factory`, `creator`)

**Technique:**
```bash
# Download HTML and JS bundles
curl -s https://target.finance/vaults > vaults.html
# Extract all JS chunk URLs
grep -oP 'src="([^"]+\.js)"' vaults.html | cut -d'"' -f2

# Download and concatenate all JS
cat all_chunks.txt | xargs -I{} curl -s "https://target.finance/{}" > all_js.txt

# Extract API URLs
grep -oP 'https?://api\.[^"'\'' ]+' all_js.txt

# Extract contract addresses (hex patterns)
grep -oP '0x[0-9a-fA-F]{40}' all_js.txt | sort -u

# Extract chain IDs
grep -oP 'chainId["\s:]+[0-9]+' all_js.txt | sort -u
```

### Step 2: Extract All Contract Addresses
Identify address types by context:
- `Vault`: ERC-4626 or custom vault implementation
- `Silo`: Shared storage/strategy (single point of failure if shared)
- `Factory/Protocol`: Creates vaults via CREATE2
- `Impl`: Implementation contract (behind proxy)
- `Proxy`: ERC1967Proxy or TransparentUpgradeableProxy
- `Owner/Curator`: Admin roles

### Step 3: RPC Access Test
Try public RPCs first before requesting API keys:
```bash
# Test RPC availability
curl -s --max-time 5 'https://arb1.arbitrum.io/rpc' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Working RPCs to try (in order):
# - https://arb1.arbitrum.io/rpc
# - https://1rpc.io/arb
# - https://rpc.ankr.com/arbitrum
# - https://rpc.ankr.com/ethereum
```

### Step 4: RPC Calls
Once RPC works, run these calls:

```bash
# eth_call: Test function selectors on contracts
curl -s --max-time 10 'https://arb1.arbitrum.io/rpc' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0x...","data":"0x..."},"latest"], "id":1}'

# eth_getStorageAt: Read storage slots
curl -s --max-time 10 'https://arb1.arbitrum.io/rpc' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_getStorageAt","params":["0x...","0x...","latest"], "id":1}'

# eth_getCode: Check if address is contract or EOA
curl -s --max-time 10 'https://arb1.arbitrum.io/rpc' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["0x...","latest"], "id":1}'

# eth_getTransactionByFromAndIndex: Find deployer TX
curl -s --max-time 10 'https://arb1.arbitrum.io/rpc' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_getTransactionByFromAndIndex","params":["0xdeployer","0x0"],"id":1}'
```

### Step 5: Map Architecture
Build the contract hierarchy:
```
Protocol (Factory)
├── Implementation (behind proxy)
├── createVault(owner, salt) function
└── deployer (EOA or contract)
    ├── Vault A (proxy → impl)
    ├── Vault B (proxy → impl)
    ├── Vault C (proxy → impl)
    └── Silo (shared storage)
        └── Used by Vault A, B, C = SPOF
```

### Step 6: Check Proxy Admin
ERC1967 proxy admin is stored at a fixed slot:
```
Admin slot: 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
Impl slot:  0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
```

If admin = 0x0 → UUPS pattern (implementation controls upgrades). This means:
- The implementation contract's `upgradeTo` function handles upgrades
- Access control is in the impl, not the proxy
- If impl has a bug → ANYONE could potentially upgrade

### Step 7: Check Function Selectors
Test common selectors:
```
0xd7b28185  → totalAssets()  (ERC-4626)
0x70a08231  → balanceOf(address)
0x95d89b41  → name()
0xc52d7749  → decimals()
0x313ce567  → symbol()
0x8da5cb5b  → owner()
0xa5d37df5  → custom factory functions
0x415565e0  → deposit(uint256,address)
0x6e5333b0  → withdraw(uint256,address,address)
```

Decode results:
- `0x` result → function doesn't exist or call reverted
- Error message → check for `execution reverted` (permissioned)
- Hex data → decode: last 64 chars for uint256, or extract address from bytes

### Step 8: Check Deposit/Withdraw
Test if functions are permissioned:
```
Permissionless: eth_call returns data or empty result
Permissioned: eth_call returns "execution reverted"
```

Also test with different signatures:
```
deposit(uint256,address) → 0x415565e0
deposit(uint256,address,address) → 0x415565e0 + additional param
```

### Step 9: Check Silo Balance
Compare on-chain balance with reported TVL:
```bash
# Check vault's balance in silo
balanceOf(vault_address) on silo_contract

# Compare with reported TVL from frontend
# Discrepancy = hidden funds, accounting bug, or different chain
```

### Step 10: Check Deployer Type
```bash
# Check if deployer is EOA or contract
eth_getCode(deployer_address)

EOA → individual risk (key compromise → vault creation)
Contract → factory/governance risk (contract bug → mass creation)
```

### Step 11: Identify Shared Components
If one component (silo, oracle, strategy) is shared across multiple vaults:
- **Single point of failure** — one bug drains ALL vaults
- **Attack surface** is multiplied by the number of dependent vaults
- **Priority** = shared_component_tvl * num_dependent_vaults

### Step 12: Verify Impl vs Blockscout
```
Blockscout impl: 0x00ac46824e664881581f0E105Bb5e492
Storage slot 4:  0xd42633987b6cA188ec6d72dfAdaBef

If they don't match → possible fork, upgrade, or different chain version
```

### Step 13: Attack Path Determination
Based on findings:
| Condition | Attack Path |
|-----------|-------------|
| Permissionless silo | Direct drain via silo deposit/withdraw |
| Permissioned silo | Find permission bypass (ACL bug, reentrancy) |
| UUPS upgradeable | Replace impl with malicious contract |
| Whitelist deposit | Bypass whitelist (ACL bug) |
| Proxy admin = 0x0 | UUPS upgrade path (check impl for bugs) |
| Proxy admin = known | Direct upgrade if compromised |

### Step 14: Escalation
Start with smallest vault, escalate to largest:
1. Test on lowest-TVl vault first
2. If successful, scale to silo-level attack
3. If silo compromised → ALL vaults drained

### Step 15: Off-Chain Recon (API & Source Discovery)
Before or alongside on-chain analysis, use off-chain sources to find contract addresses and source code:

**15a. DeFiLlama API:**
- `https://api.llama.fi/protocols` — search for protocol by name, get TVL, chains, audit links, GitHub org
- `https://api.llama.fi/protocol/{slug}` — detailed protocol info including module path, audit_links, github, twitter
- DefiLlama adapter source: `https://raw.githubusercontent.com/DefiLlama/DefiLlama-Adapters/main/projects/{protocol}/index.js` — often contains contract addresses, TVL logic, chain IDs
- `tvlCodePath` field in API response points to adapter source on GitHub

**15b. Ecosystem API Discovery:**
- Many DeFi protocols expose vault/position data via subdomain APIs
- Pattern: `ecosystem.{protocol}.finance/vaults` or `api.{protocol}.finance/v1/vaults`
- Returns JSON with verified vaults, addresses, assets, TVL, chainId
- t3tris: `https://ecosystem.t3tris.finance/vaults` returned all vaults with verification status

**15c. GitHub Org Enumeration:**
- `https://api.github.com/orgs/{org}/repos` — list all public repos
- Source code for specific vault types often in dedicated repos (e.g., `Aave-Vault` for Aave wrapper)
- t3tris-finance had: Aave-Vault, yield-server, dimension-adapters, DefiLlama-Adapters, mdoc-t3tris, coming-soon

**15d. Audit Report Discovery:**
- Check protocol website for audit links (often Google Drive, GitHub, or audit firm URLs)
- Common audit firms: Cyfrin, Zellic, Code4rena, Sherlock, Trail of Bits, OpenZeppelin
- Audit reports may contain contract addresses, architecture diagrams, and known issues

### Step 16: ATokenVault Pattern Recognition (Oracle-Safe Vaults)
When a vault wraps Aave V3 aTokens, it is **immune to oracle manipulation**:

**Identification:**
- Source code in `t3tris-finance/Aave-Vault` GitHub repo or similar
- `totalAssets()` returns `ATOKEN.balanceOf(address(this)) - getClaimableFees()`
- No oracle calls in any function
- Share price = aToken balance / total shares (ERC-4626 standard)

**Key Properties:**
- **NO oracle dependency** — uses direct aToken balance
- **Immune to oracle manipulation** — no Chainlink, TWAP, custom oracle
- Fees are performance-based (percentage of yield accrued)
- Attack surface limited to: Aave protocol risk, Silo admin SPOF, UUPS upgrade

**Action:** If vault is ATokenVault, DROP oracle manipulation vector from analysis. Focus on:
1. Aave protocol smart contract risk
2. Shared Silo admin compromise
3. UUPS proxy upgrade path
4. Fee parameter manipulation (if setter exists)

### Step 17: Unverified Contract Blocker Protocol
When Shared Silo / VaultImpl / Factory source code is NOT verified:

**Cannot Assess:**
- Oracle logic and price feed implementation
- `setPrice()` / `updatePrice()` functions
- Price staleness checks and heartbeat mechanisms
- Upgrade mechanism and proxy admin controls
- Cross-chain oracle design (if multi-chain)

**Action:**
1. Document as CRITICAL GAP in report
2. Recommend source verification on block explorer
3. Do NOT fabricate oracle vulnerabilities — if you can't see the code, don't invent them
4. Focus on what IS verifiable: proxy patterns, admin slots, known implementations
5. Report: "Source code not verified — oracle attack surface cannot be assessed. Estimated max extractable: unknown (up to full TVL if oracle exists)."

**Fallback Analysis:**
- PUSH4 selector extraction from bytecode
- Function signature identification via known selector databases
- Storage slot mapping for proxy admin and implementation
- Transaction tracing to identify callers and patterns

## Key Findings from T3tris.finance Analysis (2026-07-20)

### Architecture
- **Protocol**: ERC1967Proxy → Impl: 0x002d0655a32c80ba3b3074108E69ee97
- **Vault Impl**: 0x00ac46824e664881581f0E105Bb5e492 (custom ERC-4626)
- **Silo Impl**: 0xd42633987b6cA188ec6d72dfAdaBef (Silo_v1.1.0 fork)
- **Silo Proxy**: 0xcd07ed2d762b498abc68958b2458cc67e5212a4d (used by 4 vaults)
- **Total TVL**: ~$6.4M across 5 vaults

### Vault Breakdown
| Vault | Address | TVL | Deposit | Silo |
|-------|---------|-----|---------|------|
| BoLD | 0x271cbb... | $0 | TRUE | Shared |
| First-USDC | 0x98e43a... | $75K | TRUE | Shared |
| Gami USDC | 0x9984ad... | ~$6M | WHITELIST | Shared |
| Ellen BTC | 0xc84cc6... | ~$0 | Aave aToken | Ellen Silo |
| Strada | 0x5684b1... | ~$315K | TRUE | Shared |

### Key Findings
- Proxy admin slot = 0x0 → UUPS pattern (impl controls upgrade)
- First-USDC on-chain balance: 769,129 USDC (vs $75K reported)
- Deployers are all EOA addresses → individual key compromise risk
- Silo is shared across 4 vaults = single point of failure ($6.4M)
- Vault impl NOT verified on blockscout → can't audit without source
- Silo impl NOT verified on blockscout → can't audit without source
- Protocol createVault requires proxy admin (not public)
- Silo deposit/withdraw functions: REVERTED (permissioned)

### Attack Vectors Ranked
1. **First-USDC Direct Exploit** (HIGH) — $75K, no whitelist, shared silo
2. **Silo Permission Bypass** (MEDIUM) — All 4 vaults, $6.4M total
3. **UUPS Upgrade** (MEDIUM) — Needs impl source to find upgrade bug
4. **Whitelist Bypass** (LOW) — Gami USDC $6M, needs owner/curator keys
5. **CREATE2 Vault Factory** (LOW) — Needs proxy admin compromise

## RPC Selector Reference

### ERC-4626 Selectors
```
0xd7b28185  → totalAssets()
0xa6f9ae1e  → previewDeposit(uint256)
0xb6f9c9a9  → previewMint(uint256)
0xa495071d  → previewRedeem(uint256)
0x6006c3eb  → maxMint(address)
0x3659cfe6  → maxDeposit(address)
0xa4cb43e1  → maxWithdraw(address)
0x8680bb1f  → maxRedeem(address)
```

### ERC-20 Selectors
```
0x70a08231  → balanceOf(address)
0xa9059cbb  → transfer(address,uint256)
0x23b872dd  → transferFrom(address,address,uint256)
0x18160ddd  → totalSupply()
0x313ce567  → symbol()
0x95d89b41  → name()
0xc52d7749  → decimals()
```

### Proxy Selectors
```
0xb531...6103  → proxy admin (ERC1967 slot 0)
0x3608...2bbc  → implementation (ERC1967 slot 1)
0x5b1d1de2  → upgradeTo(address) (UUPS)
0xb274a710  → upgradeToAndCall(address,bytes) (UUPS)
```

### Common Custom Selectors
```
0xac946fce  → initializeVault (t3tris vault constructor)
0xa5d37df5  → createVault (t3tris factory)
0x18116376  → totalBalance (silo)
0x415565e0  → deposit(uint256,address)
0x6e5333b0  → withdraw(uint256,address,address)
0xf2fde38b  → transferOwnership(address)
0x84b0196e  → getRoleAdmin(bytes32)
0x214d377b  → grantRole(bytes32,address)
```

### Flash Loan Attack Analysis
→ see `references/flash-loan-attack-patterns.md` for complete flash loan attack methodology

**Key Flash Loan Vectors for Vaults**:
1. **Oracle Price Manipulation** — If vault uses AMM spot prices or custom oracle without TWAP
2. **Share Price Inflation** — Deposit at inflated NAV via `convertToShares()` manipulation
3. **Async Settlement Exploitation** — Deposit at stale price, withdraw after settlement updates
4. **Collateral Inflation** — If vault allows borrowing, inflate collateral value
5. **Liquidation Manipulation** — Manipulate price to trigger unfair liquidations

**Detection Steps**:
- Check vault's `oracle` address and type (Chainlink = safe, AMM spot = vulnerable)
- Look for `isSafeOracle` flag in vault metadata
- Verify TWAP implementation in oracle contract
- Check `lastSettlementTs` for async settlement windows
- Test if deposit/withdraw functions are permissioned

**Capital Required**: $5M-50M depending on AMM liquidity and vault TVL
**Max Extractable**: Full vault TVL if oracle fully manipulable
