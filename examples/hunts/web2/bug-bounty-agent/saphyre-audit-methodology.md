# Saphyre.xyz Audit Methodology — Vite SPA + Shared API + Custom AMM + RFQ Settlement

## Target Profile
- **Domain:** https://www.saphyre.xyz/
- **Type:** Execution infrastructure (AMM + RFQ + Swap Relayer + Bridge)
- **Chains:** Sei (1329), Base (8453), Scroll (534352), Mode (34443), Ink (57073), Arbitrum (42161), Optimism (10)
- **Frontend:** Vite.js SPA on Vercel
- **Backend:** Shared DragonSwap API + Swap Relayer API

---

## Architecture Pattern
```
Frontend (Vite SPA) → Swap Relayer API → RFQ Settlement Contract → AMM Pools (DragonSwap V2 on Sei)
                      ↓
              DragonSwap Shared API (off-chain data)
```

---

## Phase 0: Identify the Real Target

**Initial assumption:** Simple AMM/DEX  
**Reality after bundle analysis:** Execution infrastructure with:
- **Swap Relayer** (`swap-relayer.saphyre.xyz/relay`) — MEV relayer for swaps
- **RFQ Settlement Contract** — 7KB custom contract with owner but NO standard admin
- **AMM Pools** — DragonSwap V2-compatible pools on Sei (shared infra)
- **Steer Periphery** — 2KB wrapper for Steer Protocol LPs
- **Bridge** — Thin frontend at `bridge.saphyre.xyz`

---

## Phase 1: Bundle Analysis (Critical for Minified SPAs)

### Methodology
```bash
# 1. Download main JS bundle
curl -s https://www.saphyre.xyz/ | grep -o '/assets/index-[^"]*\.js'
# → /assets/index-<hash>.js

# 2. Extract ALL 0x addresses
grep -oE '0x[a-fA-F0-9]{40}' bundle.js | sort -u
# Found 809 unique addresses → filter known tokens (WETH, USDC, WBTC, etc.)

# 3. Find embedded API endpoints
grep -oE 'https?://[^"\'`\s]{10,}' bundle.js | sort -u
# Found: turnkey endpoints, swap-relayer, DragonSwap API, bridge endpoints

# 4. Identify chain configs
grep -oE 'chainId[^}]*' bundle.js
# Found chainId 1329 = Sei Arctic-1

# 5. Locate function names (minified but readable)
grep -oE 'function[^{]{0,100}' bundle.js | grep -iE 'swap|relay|settle|route|fee'
```

### Saphyre-Specific Findings
| Category | Findings |
|----------|----------|
| **Contract Addresses** | RFQ Settlement: `0x6aE46fc725605f2eBb0126646f8318A069d328A2`, Steer Periphery: `0xfF42cD42d8a5812CB38fb3C0720Dfc490912f48B`, Permit2: `0xC6b7aC7Bbd8b456b67e8440694503cAC2Afb1d98` |
| **API Endpoints** | `https://swap-relayer.saphyre.xyz/relay` (POST, EIP-712 signed), `https://sei-api.dragonswap.app/api/v1/*` (pools, tokens, tiers), `https://saphyre-service-dev.saphyre.xyz/api/v1` (DEV, DNS unreachable) |
| **Wallet Infra** | Turnkey integration (project IDs in bundle) |
| **Chains** | Sei (1329), Base (8453), Scroll (534352), Mode (34443), Ink (57073), Arbitrum (42161), Optimism (10) |

---

## Phase 2: Contract Security Triage

### Bytecode Analysis
| Contract | Size | Type | Risk |
|----------|------|------|------|
| DRG/WSEI Pool | 11KB | Custom AMM | Low (no admin) |
| RFQ Settlement | 7KB | Custom | Medium (has owner) |
| Steer Periphery | 2KB | Wrapper | Low |
| Permit2 | 9KB | Uniswap Standard | Low |

### Storage Slot Analysis (Sei RPC: `https://evm-rpc.sei-apis.com`)

#### DRG/WSEI Pool (`0x481b7a494e565be3666ac34cca2fa9304611ef0a`)
```
Slot 0:  totalSupply / reserve sum
Slot 3:  DOMAIN_SEPARATOR (EIP-712)
Slot 5:  token0 (0x71f6b49ae1558357bbb5a6074f1143c46cbca03d)
Slot 6:  token1 DRG (0x0a526e425809aea71eb279d24ae22dee6c92a4fe)
Slot 7:  token1 WSEI (0xe30fedd158a2e3b13e9badaeabafc5516e95e8c7)
Slot 8:  reserve0 packed (4.8T units)
Slot 10: reserve1 packed (819K units)
Slot 9:  feeRate (34289... = ~0.3%)
```
**No owner(), no pause(), no withdraw(), no setFee()** — immutable pool.

#### RFQ Settlement (`0x6aE46fc725605f2eBb0126646f8318A069d328A2`)
```
Slot 0: owner = 0x1eaef8dc95b0f966df2fde86d1a9be6f6890a6a4
Slot 1: trustedRouter = 0x359f6fccce980736f7537999c7cb6bf2aff66981
Slot 2: paused = 1 (boolean)
Slot 3: manager = 0xe0b1e2468c687ea19652d85d89a81254d657a494
```
**Function selectors that EXIST (revert with args needed):**
- `owner()` → returns address
- `setTrustedRouter()`, `setAllowedRelayer()`, `setFee()`, `addAdmin()`, `removeAdmin()`
- `settle()`, `executeSwap()`, `cancelOrder()`, `execute()`
- `withdraw()`, `setProtocolFee()`, `bulkSend()`, `batchSend()`, `setSwapFee()`, `bulkTransfer()`, `claimRewards()`

**FUNCTIONS THAT REVERT / NOT FOUND:**
- `transferOwnership()`, `renounceOwnership()`, `pause()`, `unpause()`
- Direct token `transfer()` from contract

**Token Balances:** ALL ZERO (USDC, DRG, WSEI, WETH, WBTC)

### Key Insight
**Owner exists but cannot extract funds.** Can only configure routing/fees. No direct drain possible even with owner key. Attack surface shifts to **Swap Relayer API** (signed intent relay).

---

## Phase 3: API Layer Testing

### Swap Relayer (`POST https://swap-relayer.saphyre.xyz/relay`)
```json
{
  "swapType": "exactInput|exactOutput",
  "signer": "0x...",
  "nonce": "1",
  "signature": "0x...",
  "params": {
    "route": ["tokenIn", "tokenOut"],
    "amountIn": "1000000",
    "amountOutMin": "0",
    "recipient": "0x..."
  }
}
```

**Auth:** EIP-712 signed payload (replay-safe via nonce)  
**CORS:** `access-control-allow-origin: *` (open)  
**Rate Limit:** Unknown (not tested under load)

**Tests:**
| Test | Result |
|------|--------|
| Empty route | `INVALID_ROUTE: params.route must be non-empty array` |
| Malformed signature | `INTERNAL_ERROR: Cannot convert undefined to BigInt` |
| Valid structure, invalid sig | Expected: would fail signature verification |

### DragonSwap Shared API (`https://sei-api.dragonswap.app`)
- 39KB pool data response
- 4 pools total (DRG/WSEI, WSEI/USDC, etc.)
- No auth required for read endpoints
- TVL, volume, token metadata exposed

---

## Phase 4: Exploit Vector Prioritization

| Vector | Impact | Difficulty | Prerequisite | Status |
|--------|--------|-----------|-------------|--------|
| RFQ Settlement owner key compromise | Critical | Medium | Private key access | **MITIGATED** — owner can't drain |
| Swap relayer auth bypass | High | Low-Med | Weak sig validation | **NEEDS TEST** |
| Pool manipulation (MEV/sandwich) | Medium | Low | Flash loan capital | Standard MEV |
| Shared API cache poisoning | Medium | Medium | DragonSwap API access | Untested |
| Frontend injection (XSS/SSRF) | Low | Medium | XSS in UI | Vite SPA = low risk |

---

## Key Takeaways for Future Audits

1. **"Thin frontend, fat contracts" ≠ drainable** — Custom contracts with owner ≠ admin drain. Must verify `withdraw()`, `transfer()`, `transferOwnership()` exist.

2. **Shared infrastructure = shared risk** — Saphyre uses DragonSwap pools/API. Audit the shared layer.

3. **RFQ Settlement is the critical contract** — It settles swaps, holds NO funds, but controls routing. Owner = config only.

4. **Swap Relayer is the real attack surface** — Signed intent relay. If EIP-712 validation has bug → unauthorized swaps.

5. **DEV endpoints in production bundles** — `saphyre-service-dev.saphyre.xyz` in bundle = potential info leak / attack surface.

6. **Bundle analysis is non-negotiable** — 809 addresses, 50+ API endpoints, chain configs all in minified JS.

---

## Sei Chain Specific Notes
- **RPC:** `https://evm-rpc.sei-apis.com` (public, reliable)
- **Explorer:** `https://seitrace.com` / `https://seiscan.com`
- **Native:** SEI (18 decimals), WSEI = `0xe30fedd158a2e3b13e9badaeabafc5516e95e8c7`
- **USDC:** `0xe15fc38f6d8c56af07bbcbe3baf5708a2bf42392` (6 decimals)
- **DRG:** `0x0a526e425809aea71eb279d24ae22dee6c92a4fe` (18 decimals)

---

## References
- Full session recon: `saphyre-recon-session-2026-07-19.md` (in sessions/)
- Bundle dump: `/tmp/saphyre_bundle.js`
- Contract analysis scripts: `/tmp/saphyre_*.py`
- Bridge audit notes: `bridge-audit/references/saphyre-xyz-audit.md`