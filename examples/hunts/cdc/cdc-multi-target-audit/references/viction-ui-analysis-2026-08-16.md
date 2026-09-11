# Viction UI Analysis — 2026-08-16

## Finding: UI Does NOT Expose Lending Functions

**Site:** `https://viction.xyz`
**Type:** Marketing site (React/Next.js)

### Routes Available

| Route | Purpose |
|-------|---------|
| `/` | Homepage (marketing) |
| `/masternode` | Masternode info |
| `/defi` | DeFi info (not DApp) |
| `/ecosystem` | Ecosystem list |
| `/consumer-app` | Consumer app info |
| `/gaming` | GameFi info |
| `/wallet` | Wallet connect |
| `/world-wide-chain` | WWC info |
| `/stablecoins` | Stablecoin info |
| `/bridge` | Bridge info (frontend only) |

### Functions NOT Found in JS Bundles

```javascript
// Searched 3.5MB main bundle for:
- setCollateralPrice
- addILOCollateral
- buyRelayer
- refund
- liquidate
- borrow
- deposit

// Result: NONE FOUND
```

### What IS Available

```javascript
// Wallet connect only:
- MetaMask connection
- Balance view
- Basic token send (maybe)
```

### Attack Vector Assessment

| Vector | Possible? | Method |
|--------|-----------|--------|
| **UI exploitation** | ❌ NO | No contract interaction |
| **Direct contract call** | ✅ YES | web3/ethers.js script |
| **Node operator access** | ✅ YES | Masternode operation |
| **Phishing admin** | ✅ YES | Social engineering |

### Conclusion

> **Attack must be programmatic, not via UI.**

The vulnerability in `LendingRegistration.sol` (collateral manipulation) cannot be exploited through `viction.xyz` because:
1. No DApp interface for lending
2. No TomoX DEX UI
3. Only marketing + wallet connect

**Attacker needs:**
- Direct contract interaction (web3.py/ethers.js)
- OR node operator access
- OR admin credentials (phishing)

---

## Verification Method

```bash
# Download JS bundle
curl -s "https://viction.xyz/static/js/main.73f9613f.js" -o /tmp/viction_bundle.js

# Search for contract functions
grep -oE "(setCollateralPrice|addILOCollateral|buyRelayer|refund|liquidate|borrow|deposit)" /tmp/viction_bundle.js

# Result: Empty (no matches)
```

---

## Implication for Audit

When auditing L1 ecosystems:
1. **Don't assume UI exposure** — marketing sites ≠ DApps
2. **Check JS bundles** for contract function selectors
3. **Attack vector is programmatic** — need custom scripts
4. **Node operator is privileged** — systemic risk
