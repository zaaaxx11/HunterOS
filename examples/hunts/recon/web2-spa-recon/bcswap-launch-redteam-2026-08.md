# BC Swap / BC Launchpad — Full Ecosystem Red-Team (2026-08-16)

## Target
- `https://launch.bcswap.org/` — BC Launchpad (ERC-20 token deployer on BC Hyper Chain)
- Canonical: `https://token.pnexplore.com/`
- Related: `https://bcswap.org/` (nginx default page)

## Architecture
- **Frontend**: Vite React SPA (3.3MB `index-DePTGhDw.js`), Cloudflare CDN
- **Auth**: WalletConnect (Web3 wallet) — no traditional JWT/session auth
- **Blockchain**: BC Hyper Chain (EVM-compatible, chain ID 6060)
- **Block Explorer**: `bchscan.io` (Next.js)

## Backend API Fleet (from JS bundle `baseURL` grep)

| Variable | Base URL | Purpose | Endpoints Found |
|----------|----------|---------|-----------------|
| `nW` | `https://bchscan.io` | Block explorer | `/api/v2/addresses/{addr}/tokens`, `/api/v2/smart-contracts/{addr}`, `/api/v2/main-page/indexing-status`, `/api/v2/search`, `/api/v2/stats`, `/api/v2/tokens` |
| `rW` | `https://bcmonitorapiv2.bchscan.io` | DEX monitor | `/api/blockchain/tokens/{addr}`, `/api/dex/token/{addr}/transactions`, `/api/pairs` |
| `iW` | `https://swapmonitapi.bchscan.io` | Swap monitor/events | `/notification/contract/get`, `/event/create`, `/event/list`, `/event/get`, `/event/transaction-hash/add`, `/event/transaction-hash/list`, `/newsletter/config/get`, `/newsletter/create` |
| `oEe` | `https://adminapi.bchscan.io` | Admin API | `/api/v1/public-api/user/contract/get?contractAddress=` |

## Discovery Technique
```bash
# 1. Download main JS bundle
curl -sL -o /tmp/index.js "https://launch.bcswap.org/assets/index-DePTGhDw.js"

# 2. Extract baseURL assignments (axios.create pattern)
grep -oP '.{0,20}(baseURL|baseUrl).{0,80}' /tmp/index.js

# 3. For each discovered API, trace the variable to its routes
grep -oP 'rW\.(get|post|put|delete)\(["\047][^"'\''\s]+["\047]' /tmp/index.js
grep -oP 'iW\.(get|post|put|delete)\(["\047][^"'\''\s]+["\047]' /tmp/index.js
grep -oP 'oEe\.(get|post|put|delete)\(["\047][^"'\''\s]+["\047]' /tmp/index.js
```

## Key Findings

### CRITICAL: IDOR on Admin API
```
GET https://adminapi.bchscan.io/api/v1/public-api/user/contract/get?contractAddress=0xANY
→ {"status":true,"data":{"isOwn":false,"isVerified":true/false,"url":null,...}}
```
No auth required. Returns contract metadata for ANY address. CORS: `access-control-allow-origin: *`.

### HIGH: No Wallet Signature Verification
`POST /event/create` only requires `connectedWalletAddress` + `tokenAddress` as body params. No signature, nonce, or JWT. Anyone can create events attributed to any wallet.

### HIGH: CORS Wildcards
- `adminapi.bchscan.io`: `access-control-allow-origin: *`
- `swapmonitapi.bchscan.io`: `access-control-allow-origin: *`
- `bcmonitorapiv2.bchscan.io`: `access-control-allow-credentials: true` + `vary: Origin`

### MEDIUM: DEX Pair Data Unauthenticated
`GET /api/pairs` returns 76 DEX pairs with full reserve amounts, token addresses, symbols.

### MEDIUM: Newsletter Telegram Bot URL Leaked
`GET /newsletter/config/get` → `{"data":{"newsletterTelegramBotUrl":"https://t.me/bcswapadminmonitornewsletter_bot"}}`

### Blocked Vectors
- .env, .env.local, .env.production: all return SPA fallback (not exposed)
- Source maps: return SPA fallback
- SSTI: Cloudflare blocks `{{7*7}}`, `<%=7*7%>` with 400
- SSRF: no URL parameters that trigger server-side fetches
- GraphQL, Swagger: not found
- Hardcoded secrets: none found in 3.3MB bundle
- JWT: no traditional auth — wallet-based only

## SPA Trap Pattern
Every path returns `200 text/html` with `<!DOCTYPE html>` + `div#root` — the Vite SPA catch-all. The `robots.txt` disallowed `/manage-token` and `/test` but these are SPA routes, not real protected endpoints. Token creation is on-chain via wallet — no backend API involved.

## `token.pnexplore.com` Express Catch-All
The Express server returns `{"success":true,"message":"API is working"}` for every path — even nonexistent ones. Don't treat this as a real endpoint.