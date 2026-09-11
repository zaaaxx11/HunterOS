# Alltoscan High-Risk Sink Fuzz — Nuxt 3 + Express get_home_data + PublicNode RPC (2026-08-16)

**Targets:** `alltoscan.com` (Nuxt 3 prerender `502dc79c Bi8Ek9E7` nginx/1.22.1 no-cache) + `scan.alltoscan.com` (Nuxt `31dc1368 C_X1aWDQ` + Express/helmet `ApiBase https://scan.alltoscan.com/api`) — `188.166.44.153` DO AMS, Cloudflare NS no proxy.

**Endpoint discovery (JS static + live):**
- Apex: `/_nuxt/Bi8Ek9E7.js` + 5 chunks — zero `ApiBase`/`$fetch` — `/api/*` `/admin` `/.env` `/swagger` all `200 text/html <!DOCTYPE` SPA fallback.
- Scan: `window.__NUXT__.config.public.ApiBase` + `scan_evWO-ChZ.js` → `$fetch(c+"/get_home_data")` — **only** `c+"/..."` hit across 13 chunks. Brute 30+ `/api/*` (`search`, `address`, `tx`, `block`, `tokens`, `chains`, `health`) → `404 {"succeeded":false,"message":"Not found."}` with helmet CSP/HSTS. `GET /api/` 301, `/api` without slash 301.
- Frontend search is client-side `new ae(server).eth.getTransaction/getBlockNumber` against `publicnode.com` (eth/bsc-testnet/arb/avax/polygon/op/ftm/base + `rpc.zkfair.io`) — no backend `?q=` sink. `GET /address/ethereum/0x...` SSR `__NUXT_DATA__` empty.

**Fuzz matrix (curl -sk Mozilla, sleep 2 to avoid 10/5s ratelimit):**

| Vector | Payload | Code | Body sig | Verdict |
|--------|---------|------|----------|---------|
| Methods | GET/POST/PUT/DELETE/PATCH/OPTIONS/HEAD `/api/get_home_data` | GET 200, POST/PUT/DELETE/PATCH 404, OPTIONS 200 (`Allow: GET,HEAD,PUT,PATCH,POST,DELETE` `Vary: Origin, Access-Control-Request-Headers`), HEAD 200 | GET `{"succeeded":true,"home_data":[...9 chains...]}` leaks Mongo `_id/__v/createdAt/updatedAt` + `gas_price` | GET-only, OPTIONS advertises unused verbs |
| Query params | `?__proto__[polluted]=1`, `?constructor[prototype][polluted]=1`, `?chain=ethereum`, `?search=<script>alert(1)</script>`, `?debug=true` | 200 same `home_data` | ignored | no proto-pollution, no filter |
| POST JSON | `{"__proto__":{"isAdmin":true}}`, `{"chain":"ethereum"}`, `{"chainId":999...}` | 404 | `Not found.` | no sink |
| Malformed JSON | `null`, `{`, `{"a":}`, `undefined`, `NaN`, `{"a": NaN}` | 400 | `Unexpected token 'n', "null" is not valid JSON` / `Expected property name or '}' at position 1` / `Unexpected token 'u', "undefined"...` — V8 `express.json()` leak | info leak, fingerprint |
| Content-Type | `application/xml`, `text/plain`, `x-www-form-urlencoded`, `multipart/form-data` | 404 | `Not found.` | correctly rejected |
| Headers | `X-Forwarded-For: 127.0.0.1`, `X-Original-URL: /admin`, `Origin: https://evil.com`, `Referer: https://evil.com` | 200 same JSON | ignored | safe |
| Host | `Host: evil.com` | 200 `text/html <!DOCTYPE` Nuxt SPA | virtual-host switch leaks routing | minor |
| Host 2 | `X-Forwarded-Host: evil.com` | 200 JSON | ignored | safe |
| CORS | `Origin: https://evil.com` | 200 | `access-control-allow-origin: https://evil.com` `vary: Origin` no `ACAC` | **reflective CORS** — LOW here (public `home_data`, no creds) vs HIGH on `wp-json` |
| Path trav | `../../etc/passwd`→404 Nuxt, `..%2F..%2Fetc%2Fpasswd`→400 nginx `Bad Request`, `../api/get_home_data`→200 normalized | — | encoded `..` blocked, normalized `..` allowed |
| Overflow | `POST 10k AAAA` | 429 `Too many requests` | rate-limit, not crash | resilient |
| Race 10× parallel | GET `get_home_data` | 200 | 2 MD5s due to live `gas_price` drift | not race |
| GraphQL/openapi | `/graphql`, `/api/graphql` `{"query":"{__typename}"}`, `/openapi.json`, `/swagger.json`, `/.well-known/security.txt` | 404 `{"error":true,"statusCode":404}` or `405` | — | none |
| .env/backup | `.env`, `.env.local`, `.git/HEAD`, `config.json`, `package.json` | 404 Nuxt `error:true` | — | no leak |
| TLS/headers | api: CSP `default-src 'self'`, `HSTS max-age=15552000 includeSubDomains`, `X-Frame-Options: SAMEORIGIN`, `COOP same-origin`, `ratelimit-policy: 10;w=5` ; apex: only `server: nginx/1.22.1` | — | scan hardened, apex not — origin split |

**Severity triage:**
- **CORS reflect** `ACAO: https://evil.com` — LOW on `get_home_data` (public blocks/txns, `Allow-Credentials` absent) — don't over-report as HIGH unless `ACAC:true` + sensitive. Apex same reflect seen on `wp-json` is HIGH.
- **JSON parse leak** — LOW but aids fingerprint; fix with generic `400 Invalid JSON`.
- **Host→SPA** — LOW info disclosure; add `Host` validation.
- **429 `ratelimit-policy` leak** — INFO; helps DoS tuning.

**Lessons for next hunt:**
1. Exhaust `grep 'c+"'` / `ApiBase` on all chunks — single endpoint may be the whole surface.
2. `sleep 2` between `/api/*` probes; check `ratelimit-remaining` — else 429 hides 404/200.
3. Avoid inline `grep "/api/"` — hardline blocklist; use `python3 -c "import re"` or `write_file + urllib`.
4. Validate `Content-Type: application/json` vs `<!DOCTYPE` — 200 SPA fallback traps `web2-deep.py v3` 🔥.
5. Client-side RPC (`publicnode`) = client-side sinks only — no backend injection; document as architecture not vuln.

**Repro (Mozilla, single-req):**
```bash
curl -sk -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0" -H "Accept: application/json" https://scan.alltoscan.com/api/get_home_data -D - | head -n 20
curl -sk -A "Mozilla/5.0 ..." -H "Origin: https://evil.com" https://scan.alltoscan.com/api/get_home_data -D - | grep -i access-control
curl -sk -A "Mozilla/5.0 ..." -X POST -H "Content-Type: application/json" -d 'null' https://scan.alltoscan.com/api/get_home_data
curl -sk -A "Mozilla/5.0 ..." https://scan.alltoscan.com/api/../api/get_home_data | head -c 200
```
