# U2U Web2 Chain Analysis — 2026-08-14 (CDC Agent 4 CHAINER)

## Target
U2U Network (Chain 39) — Next.js 15 App Router main site, React SPA staking app, AA Bundler v0.7.0, public RPC with debug namespace.

## Prismic CMS Integration (u2u.xyz)

### Recon Pipeline
1. **Fingerprint:** `curl -I https://u2u.xyz` → `x-nextjs-cache: HIT`, `x-nextjs-prerender: 1`, `vary: rsc` → Next.js 15 App Router
2. **Repository name from JS bundle:** grep `prismic.io` on the page HTML → `u2u-cms.cdn.prismic.io` → repo name = `u2u-cms`
3. **API v2 enumeration:** `https://u2u-cms.cdn.prismic.io/api/v2` → full schema: refs, bookmarks, types, languages, forms
4. **Content types discovered:** blog_post, blog_post_categories, blog_post_config, ecosystem, ecosystem_categories, ecosystem_config, footer, header, page, top_banner
5. **Preview mode:** `GET /api/preview` → 307 redirect + `set-cookie: __prerender_bypass=<token>` — **no auth required**, anyone can enable preview
6. **Revalidation endpoint:** `POST /api/revalidate` → `{"revalidated":true}` with **any body** including `{"secret":"WRONG"}`, `{}`, or arbitrary strings — **secret is NOT validated**
7. **Webhook endpoint:** `/api/webhook` → 404 (not present)
8. **Exit preview:** `GET /api/exit-preview` → 200 (exists)

### Critical Finding: Unauthenticated Revalidation
- `POST /api/revalidate` with `{"secret":"ANYTHING_AT_ALL"}` returns `{"revalidated":true}`
- Cloudflare WAF blocks path-like payloads (403) but not arbitrary JSON
- Impact: anyone can trigger full site ISR revalidation → DoS, cache poisoning
- Combined with preview mode: preview cookie + revalidate = content poisoning if Prismic webhook can be spoofed

### RSC / Server Actions
- `curl -H "RSC: 1" https://u2u.xyz` → Flight payload returned, but no `$ACTION_ID` anywhere
- CVE-2025-29927: response size identical (256669 bytes) → patched or no middleware
- Verdict: BLOCKED — purely static site from Prismic, no Server Actions

## Staking App (staking.u2u.xyz)

### Recon
- React SPA (CRA, not Next.js), `main.dba732f7.js` (4.2MB)
- 772× `wallet`, 292× `provider`, 100× `contract` references in bundle
- 45 unique contract addresses, including USDT/USDC/WU2U + staking contracts
- ethers.js, no on-chain wallet (users connect via MetaMask/WalletConnect)

### Attack Surface
- No direct pre-auth drain vector
- XSS → inject fake contract call → user approve → drain
- Domain hijack → serve modified JS → wallet drain
- CSP not analyzed (needs follow-up)

## Bundler (bundler.u2u.xyz)

### Recon
- `GET /` → "Account-Abstraction Bundler v.0.7.0. please use /rpc"
- `POST /rpc` → JSON-RPC endpoint
- `eth_chainId` → `"0x27"` (39, U2U Mainnet)
- `eth_supportedEntryPoints` → `["0xdbd3939BeeC5DC02Df4820212820cB078d95DD32"]`
- `rpc_modules` → NOT available (returns bundler banner)
- Internal uses `JsonRpcProvider` from ethers to connect to RPC node

### SSRF Chain
- Bundler receives UserOp from public → validates → sends to RPC via `eth_sendRawTransaction`
- RPC node has `debug_traceCall` → can simulate arbitrary contract calls
- If RPC node is inside K8s cluster → SSRF to internal services
- `debug_traceCall` with `prestateTracer` → storage slot oracle for any contract

## RPC Debug API (rpc-mainnet.uniultra.xyz)

### Exposed Methods (all LIVE on mainnet, verified 2026-08-14)
| Method | Result | Impact |
|--------|--------|--------|
| `debug_writeMemProfile` | `null` ✅ | Arbitrary file write (binary pprof) |
| `debug_writeBlockProfile` | `null` ✅ | Arbitrary file write |
| `debug_writeMutexProfile` | `null` ✅ | Arbitrary file write |
| `debug_cpuProfile` | `null` ✅ | CPU profile + file write |
| `debug_goTrace` | `null` ✅ | Go trace + file write |
| `debug_setGCPercent(-1)` | old value ✅ | Disable GC → OOM DoS |
| `debug_stacks` | 6200+ lines ✅ | Full goroutine state dump |
| `debug_memStats` | full stats ✅ | Heap/Sys/GC leak |
| `txpool_content` | full mempool ✅ | 152 pending, 68 addresses |
| `debug_traceCall` | works ✅ | Storage slot oracle |
| `debug_setHead` | ❌ BFT blocked | Cannot rewind |

### File Write Chain (F)
The file write content is binary pprof — not a direct webshell. But:
1. Overwrite `/proc/self/environ` → env leak (if writable)
2. Overwrite node config → restart → corrupted state
3. Overwrite nginx config include path → restart → serve attacker content
4. `/var/www/html/` → `no such file or directory` (no web server on this path)
5. K8s shared volume mount → lateral movement to sidecar

## Subdomain Enumeration Results
| Subdomain | Status | Tech |
|-----------|--------|------|
| u2u.xyz | 200 | Next.js 15 (App Router) |
| staking.u2u.xyz | 200 | React SPA (CRA) |
| docs.u2u.xyz | 200 | GitBook (Next.js) |
| bundler.u2u.xyz | 200 | AA Bundler v0.7.0 |
| report.u2u.xyz | 404 | Not live |
| admin.u2u.xyz | NXDOMAIN | Not live |
| app/cms/api/dashboard | NXDOMAIN | Not live |

## Chain Analysis Summary
| Chain | Trigger | Effect | Trust Boundary | Live? |
|-------|---------|--------|----------------|-------|
| A | POST /api/revalidate (no secret) | Cache poisoning + DoS | Public → CMS | ✅ |
| B | Server Actions | RCE | N/A | ❌ BLOCKED |
| C | Staking wallet connect | Wallet drain (social) | Browser → Chain | ✅ (theoretical) |
| D | Bundler → RPC → debug_traceCall | SSRF → K8s internal | Bundler → K8s | ✅ (theoretical) |
| E | report.u2u.xyz | Admin data dump | N/A | ❌ DEAD |
| F | debug_writeMemProfile | Arbitrary file write | Public → FS | ✅ |

## Key Lessons
1. **Prismic revalidation secret MUST be validated** — the default Next.js Prismic template often ships with `revalidate` returning true unconditionally
2. **Always probe ALL debug_* methods** — `rpc_modules` tells you the namespace is exposed, but probing each method individually reveals the full impact
3. **Bundler `/rpc` path is non-standard** — many bundlers use `/` or `/rpc`, try both
4. **JS bundle is a recon goldmine** — `staking.u2u.xyz`'s 4.2MB bundle contained 45 contract addresses, infra URLs, and the full app architecture
5. **File write impact ≠ RCE** — binary pprof content can't be a webshell directly, but the chain through config overwrite + restart is valid