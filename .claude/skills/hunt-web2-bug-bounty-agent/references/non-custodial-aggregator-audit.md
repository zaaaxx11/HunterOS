# Non-Custodial Aggregator Audit Methodology (July 2026 — ColibriSwap case study)

## Signal: It's a frontend-only aggregator
1. Contract address displayed everywhere but 0x bytecode on ALL chains → **no on-chain funds**
2. Claims "no wallet connect", "non-custodial", "no KYC"
3. Backend partners cited: ChangeNOW, HoudiniSwap, CEX partners
4. Stack: React/SSR frontend → Cloudflare → Partner APIs (not own chain)

## What CAN be attacked (stripped from on-chain focus)
1. **ChangeNOW API key reuse** — swap/send flows call ChangeNOW directly; do they use ColibriSwap's API key? If so, you own their swap rate
2. **Privy auth** — email OTP (6-digit, no CAPTCHA), Google OAuth, Wallet connect → brute force OTP or steal session. Full playbook: `references/privy-auth-attack-playbook.md`
3. **Tinybird analytics proxy** — `/~api/analytics` POST accepted; can inject malicious payload, detect internal API keys
4. **Server function enumeration** — TanStack Start `/_serverFn/<sha256-hash>` endpoints; try direct call with seroval protocol
5. **Cloudflare bypass** — cert transparency for origin IP, force-direct connection, subdomain enumeration
6. **Flock.js info leak** — torkey metrics leaks user path, user agent, locale to analytics endpoint

## Pivot Sequence: Non-Custodial Takeover
```
Multi-chain check → 0x-everywhere → non-custodial confirm →
  → Extract server fn hashes from bundles
  → Probe /_serverFn/ with seroval headers
  → Extract Privy integration in auth flows
  → Test ChangeNOW proxy with manipulated amounts
  → Test analytics proxy for SSRF/leaks
  → Brute force OTP (NEED PLAYWRIGHT — curl origin-blocked)
  → Try Cloudflare origin bypass
  → Check subdomain pages for .env leaks
  → Discover hidden admin panels via route manifest
  → Extract admin panel login flow -> post-login capabilities
  → If backend dead (Supabase DNS NXDOMAIN): WALK AWAY
```

## Key Bundle Extraction Commands
```bash
# Find all lazy-loaded bundles (Vite chunks)
curl -sL https://TARGET/PAGE | grep -oP '/assets/[a-zA-Z0-9_-]+\.js' | sort -u

# Extract server function hashes from index bundle
curl -sL https://TARGET/assets/INDEX-BUNDLE.js | grep -oP '[a-f0-9]{64}' 

# Extract Prviy appId from Privy-specific bundle
curl -sL https://TARGET/assets/usePrivy-*.js | grep -iEo 'cl[a-z0-9]{8,20}' 

# Find ChangNOW/other partner API calls in bundle
curl -sL https://TARGET/assets/SWAP-BUNDLE.js | grep -oP 'provider\s*:\s*\w+'
```

## Phase 2.5: Supabase Backend Discovery
If the target uses Supabase (look for `sb_publishable_*` in bundles, `.supabase.co` in network tab):
→ Full playbook: `references/supabase-backend-exploitation.md`
- Extract publishable key from JS bundles
- Probe REST API tables (RLS may be weak)
- Try RPC endpoints for admin functions
- Try Auth token endpoint with password brute

## Admin Panel Discovery in Lazy-Loaded Routes
Full methodology: `references/admin-panel-discovery.md`
1. In the route manifest (SSR barrier), look for route keys that aren't in the nav
2. ColibriSwap: `/panel-x7k9m2q3` was a lazily-loaded admin panel NOT linked anywhere
3. Pattern: `<title>Admin</title>` + `<meta name="robots" content="noindex, nofollow">`
4. Admin bundle analyzed for login flow: `queryKey=["admin-me"]`, email+password mutation
5. Route names often use non-standard patterns: `-x7k9m2q3` suggests intentional hiding
6. Post-login capabilities: swap catalog with addresses, visitor analytics, stats

## When to Walk Away After Non-Custodial Reality
- Contract address 0x bytecode on ALL chains → zero on-chain exploitable funds
- Supabase DNS NXDOMAIN → backend database is paused/deleted
- Privy origin-gates all curl/script requests → OTP brute force requires browser automation
- TanStack Start SSR-only → all non-HTML POST rejected server-side
- ChangeNOW/HoudiniSwap control all value flow → no custody
- ALL above confirmed → **DEAD PROJECT — walk away, no exploitable surface**
- Still valid for OPSEC-based bug bounty (info leak, header injection)

**Exception: NEXT.JS SPA ON VERCEL variant (e.g., POPs Finance, July 2026)**
- No DB backend, no admin panel, no contract addresses in JS bundles
- Token + DEX pair only — no vault/CDP/lending/margin contracts deployed
- DexScreener liquidity < $10K → micro-cap, PASS immediately
- True signal: "Post tokenized stocks as collateral, borrow margin" × no deployed contracts = vaporware
- 5–20 minute reality check before PASS:
  1. Download homepage HTML → extract JS chunks
  2. DexScreener search → TVL/FDV/liquidity
  3. `eth_getCode` on every 0x address found in bundles
  4. If all addresses are 0x code and DexScreener TVL < $50K → PASS