# Recon Methodology: SSR-First Crypto Swap Applications

## Pattern
TanStack Start / Vinxi apps that use SSR server functions to proxy to third-party swap providers (ChangeNOW, HoudiniSwap, Exolix, SimpleSwap). The architecture means:
- No direct REST API for swap creation
- All estimates fetched client-side via React Query + internal `$R` protocol
- Server functions return SSR HTML on POST (`"Only HTML requests are supported here"`)
- Real backend APIs are the swap providers, not the swap app itself

## Recon Workflow

### Step 1: Framework Identification
```bash
# Check for TanStack Start markers
curl -s target.com/ | grep -oP '\$_TSR\.router|createServerFn|$TSS/serverfn'
curl -s target.com/ | grep -oP '/assets/createServerFn-[^\"]*\.js'

# Confirm SSR-only guard
curl -s -X POST target.com/any-page \
  -H "Content-Type: application/json" \
  -d '{}'
# Response: {"error":"Only HTML requests are supported here"}
```

### Step 2: Download & Analyze Route Bundles
```bash
# Get main entry + route-specific bundles
curl -s target.com/ | grep -oP '"/assets/index-[^\"]*\.js"' | head -1
curl -s target.com/swap | grep -oP '"/assets/swap-[^\"]*\.js"' | head -1

# Search for provider identifiers
grep -iE 'changenow|houdiniswap|exolix|simpleswap|stealthex|changelly' bundle.js

# Extract queryKey patterns → reveals server function semantics
grep -oP "queryKey:\[`[a-z-]+`" bundle.js | sort -u
# Example output:
#   queryKey:[`cn-min`]        → ChangeNOW min amount
#   queryKey:[`cn-estimate`]   → ChangeNOW estimate
#   queryKey:[`route-status`]  → HoudiniSwap route status
#   queryKey:[`cg-prices`]     → CoinGecko price feed
```

### Phase 3: Extract Swap Flow Logic
```bash
# Find the mutation function (swap creation)
grep -boP 'mutationFn.{0,200}' swap-bundle.js

# Extract all input field names
grep -oP '(fromCurrency|fromNetwork|toCurrency|toNetwork|fromAmount|address|timezone|preferredAccount)' swap-bundle.js | sort -u

# Identify backend providers
grep -oP '__kind:`[a-z]+`' swap-bundle.js
# → __kind:`changenow` or __kind:`houdini` → tells which provider handles which route
```

### Phase 4: Wallet/Auth Extraction
```bash
# Privy
grep -oP 'privy-app-id' bundle.js
# → The appId is sent as a header; value may be obfuscated

# Check if auth is client-only
for ep in "/api/auth" "/auth/login" "/api/auth/token" "/login"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "target.com$ep")
  echo "[$code] $ep"
done
# → If ALL 404: auth is purely client-side (browser wallet SDK only)
```

### Phase 5: Contract Addresses
```bash
# Extract from HTML banner first (often more readable than bundle)
curl -s target.com/ | grep -oP '0x[a-fA-F0-9]{40}' | sort -u

# Cross-reference with bundle
curl -s target.com/assets/index-*.js | grep -oP '0x[a-fA-F0-9]{40}' | sort -u

# Filter known token addresses, check remaining
for addr in $(grep -v -f known_tokens.txt addresses.txt); do
  echo "Checking $addr..."
done
```

### Phase 6: Analytics Proxy Leakage
```bash
# Check for analytics proxy in HTML
curl -s target.com/ | grep -oP '~/api/analytics|~flock\.js|data-proxy-url'

# If Flock.js found
curl -s target.com/~flock.js | head -c 2000
# → Parcel-built, contains Tinybird API SDK
# → Check for data-token attribute (API key leak)

# Test analytics sink
curl -s -X POST target.com/~api/analytics \
  -H "Content-Type: application/json" \
  -d '{"payload":"exfil_test"}'
# → "Accepted" = open sink, no validation
```

### Phase 7: Signup / Rate Limiting Tests
```bash
# Check for CAPTCHA
curl -s target.com/signup | grep -iE 'captcha|recaptcha|hcaptcha|turnstile|proof-of-work'

# Mass signup test
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "Req $i: %{http_code}\n" \
    -X POST "target.com/signup" \
    -d "email=bot${i}@mailinator.com&password=Test123!"
done
# → If all 200 with no CAPTCHA = signup abuse vector
```

## Known Provider Backends for Crypto Swap Aggregators

| Provider | Identifier in Bundles | API Pattern |
|----------|----------------------|-------------|
| ChangeNOW | `changenow`, `__kind:'changenow'`, `cn-` prefix | Centralized swap API with `id`, `payAddress`, `payoutAddress` |
| HoudiniSwap | `houdini`, `__kind:'h had'`, private route | Private swap with lane/account selection |
| Exolix | `exolix` | Fixed-rate swaps |
| SimpleSwap | `simpleswap` | Similar to ChangeNOW |
| Stealthex | `stealthex` | Centralized exchange |

## ColibriSwap Case Study (July 2026)

### Architecture
- Framework: TanStack Start (Vinxi), React Query for all data fetching
- CDN: Cloudflare (__cf_bm cookie on first requests)
- Wallet: Privy.io (client-side only; all auth endpoints return 404)
- Swap Providers: ChangeNOW (fast route), HoudiniSwap (private route)
- Analytics: Flock.js → Tinybird proxy at `/~api/analytics`
- On-page contract: `0xDe8dA85BD1aCe3Ce9d31148F0f6F98E1549488f8`

### Server Functions Discovered (via queryKey extraction)
| queryKey | Provider | Purpose |
|----------|----------|---------|
| `cn-min` | ChangeNOW | Get minimum swap amount for pair |
| `cn-estimate` | ChangeNOW | Get live estimate |
| `cn-create` | ChangeNOW | Create swap, returns deposit address |
| `route-status` | HoudiniSwap | Check private lane availability |
| `save-order` | Internal DB | Persist swap record after creation |
| `cg-prices` | CoinGecko | Price feed for UI |
| `dex-prices` | DexScreener | DEX price fallback |

### Key Findings from Recon
1. **Signup has no CAPTCHA** — 5 rapid POSTs all returned 200; no rate limiting detected
2. **Analytics proxy open** — `POST /~api/analytics` returns "Accepted" with no validation
3. **Privy appId in bundles** — exposed via `get appId(){return this._privyInternal.appId}`
4. **No functional REST API** — all server functions SSR-only, curl returns HTML errors
5. **Cloudflare proxy active** — `__cf_bm` cookie + `cf-ray` header on all responses
6. **Quote data stored client-side** — SSR HTML is a static shell, rates fetched by React Query

### Swap Flow (from bundle analysis)
```
User inputs → React Query `cn-estimate` → server → ChangeNOW API → estimate response
User confirms → `cn-create` mutation → server → ChangeNOW API → deposit address
Deposit confirmed → webhook → server updates → React query refetches
Private route: HoudiniSwap lanes → `route-status` checks availability → `h-create` initiates
```

## Key Pitfalls for SSR-Only Targets
1. **Don't waste time on REST API fuzzing** — there are no REST endpoints
2. **Server function POST attempts return HTML errors** — not JSON, not useful
3. **Estimate data is in React state, not SSR HTML** — you can't curl it
4. **Swap creation requires real blockchain interaction** — not testable via curl
5. **Client-side validation means only frontend circuitbreaker blocks bad data** — but you can't reach the backend API directly
6. **Focus on: signup abuse, analytics exfiltration, contract analysis, provider API discovery**