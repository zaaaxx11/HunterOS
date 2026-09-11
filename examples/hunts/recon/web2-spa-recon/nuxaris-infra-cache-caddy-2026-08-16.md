# Nuxaris Infra / Cache / Caddy Hunt — Agent C (2026-08-16)

Target: `app.nuxaris.com` (Vercel CRA SPA) + `auth.nuxarisapiv1.xyz` + `nuxarisapiv1.xyz/api/bridge` (both Hetzner 37.27.59.179 Caddy via 1.1)

## Vercel Frontend Baseline
- `1605B <!doctype><div id=root><script /static/js/main.040e5d2d.js>` CRA Webpack, not Next/Nuxt. Headers: `server: Vercel`, `x-vercel-cache: HIT/MISS/BYPASS`, `age: 5349-5587` (sin1), `etag "079e29db…"`, `cache-control: public, max-age=0, must-revalidate` (HTML) vs `s-maxage=31536000, immutable` (static/js). SPA fallback: every `GET /api/*, /.env, /.git/HEAD, /api/auth/me` → 200 same 1605 SPA HIT. POST to same → `405 x-vercel-cache: BYPASS` empty (method not mapped to SPA). Preview deploys `nuxaris-91rna9dx7…` + `nuxaris-git-main…` → `302 location: https://vercel.com/sso-api?url=…&nonce=…` + `_vercel_sso_nonce` + `x-frame-options: DENY` (SSO-locked, no anon decompilation).
- Extract `REACT_APP_*` from bundle: `grep -oP 'REACT_APP_[A-Z_]+' | sort -u` → 19 vars. Values in context: `VERCEL_URL: "nuxaris-91rna9dx7-clickpaws-projects.vercel.app"`, `VERCEL_BRANCH_URL`, `PRJ prj_VQib…`, `dpl_HHMiB…`, `Clickpaw/Nuxaris 1114071140`, `23312ba…` — all public Vercel metadata. Leak check: `grep -oP 'REACT_APP_[^"]*:[^,]*'` same bundle also leaks `REACT_APP_AUTH_API_URL https://auth.nuxarisapiv1.xyz` + `REACT_APP_SOLANA_RPC https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY>` (live Helius billing) + WALLETCONNECT placeholder — no JWT_SECRET.

## Caddy Backends (Hetzner single IP dual vhost)
- `Via: 1.1 Caddy` only disclosure, no version. Security headers: `CSP default-src 'self'`, `HSTS max-age=31536000 includeSubDomains`, `X-Frame-Options SAMEORIGIN`, `alt-svc: h3=":443"`. Health: `GET /health → {status:ok,service:api-accounts}` (auth) vs `GET /api/health → {status:ok,service:api-bridge,network:mainnet,database:connected}` (bridge). Direct `curl -k https://37.27.59.179/ -H Host:auth…` → `308 Permanent Redirect → https://auth…` (Caddy redirect, not bypass). Cross-vhost `Host:auth.nuxarisapiv1.xyz` to `nuxarisapiv1.xyz` → `404 Cannot GET` (vhost isolation holds).

## Host Header Injection
- Vercel strictly rejects `Host: evil.com` → `404 x-vercel-error: DEPLOYMENT_NOT_FOUND DEPLOYMENT_NOT_FOUND 107B text/plain` (not cached). `X-Forwarded-Host: evil.com` / `X-Host: evil.com` double `Host:` → still `200 HIT` 1605 SPA (headers ignored, not cache-key). Caddy also rejects `X-Forwarded-Host: evil.com` on `/health` → still 200 correct vhost (header ignored).

## CORS 500 Crash (auth only)
- `GET /health` auth without Origin → `200 ACAO absent vary: Origin allow-credentials:true` (skips check). `Origin: https://app.nuxaris.com` → `200 ACAO: https://app.nuxaris.com`. `Origin: https://evil.com` / `null` / `OPTIONS` → `500 {"error":"Internal server error"} etag W/"21-u8tno…"` no ACAO (middleware throws before allowlist). Same crash on `/api/auth/me` + evil Origin masks `401 Invalid token` → 500. Bridge `GET /api/health Origin:evil.com` → `200 vary: Origin` no ACAO, no 500 (correct deny). Severity: LOW info-leak/DoS, not reflect+cred HIGH. Distinguish `crash 500 no ACAO` from `reflect evil.com + ACAC:true` HIGH.

## Cache Poisoning / Deception
- HTML `s-maxage=0,must-revalidate` + `ACAO:*` (frontend) + `age` long but `must-revalidate` → not long-cacheable poison. Static JS `immutable` long-cache correct. Every unknown path cached as SPA 1605 with same etag — no authenticated JSON cached. `X-Forwarded-Host` not varied (no `Vary: X-Forwarded-Host`). Test: `GET /?cachebuster=$(date +%s)` still HIT same etag; `GET /static/js/main.040e5d2d.js` HIT immutable. No param-based cache key to poison.

## Rate Limit + Header Bypass
- Auth `ratelimit-limit:10 policy:10;w=60 ratelimit-remaining:0 retry-after:NN` vs Bridge `60;w=60`. Burn 11 POST `/api/auth/account-state` → 8×200 `{"step":"unknown"}` + 3×429 JSON HTML. Header bypass matrix at true 429: `X-Forwarded-For, X-Real-IP, X-Originating-IP, CF-Connecting-IP, True-Client-IP, X-Client-IP, X-Cluster-Client-IP, Forwarded: for=9.9.9.9, Forwarded: for=" [::ffff:9.9.9.9]"` all still `429` (remoteAddr, not proxy headers). One false positive `Forwarded →200 ratelimit-remaining:9` was window-reset race (`reset:1` → 60). Confirm by re-burn 11 then same header → 429. Need `sleep 60-65` cooldown + check `ratelimit-reset` before claiming bypass.

## Hidden Vercel Functions / .env / Sourcemap
- No Vercel Functions: `GET /api/health` on Vercel → `200 SPA`, `POST →405 BYPASS` empty body same for `/api/auth/login`. `/.env /.env.local /.env.production /.git/HEAD /.git/config /api/.env` on Vercel → `200 1605 SPA` (no leak), `/static/.env →404 79`, `/%2e%2e/.env →400 33`. Caddy `/.env /.git/HEAD /api/.env /.well-known/security.txt /swagger /openapi.json →404`. Sourcemap `/static/js/main.040e5d2d.js.map 6,893,749B 731 sources`: `python json.load → len(sourcesContent) 731 joined 4748840` grep `secret|jwt_secret|private_key|invite_code|api_key|password` → 431 hits all viem/wallet `PRIVATE_KEY` false positive + `Confirm your password` UI string, no env secret after `joined.replace(None,'')` handling.

## Smuggling / Version
- `curl --http1.1 -d '{"a":1}extra' Content-Length:10` → `500 ratelimit-remaining:8` not desync (Caddy handles CL). No Caddy version in `Via` or `Server:`.

## Evidence Commands
```bash
curl -sk -i https://app.nuxaris.com/ | grep -E 'server|x-vercel-cache|age|cache-control|etag'
curl -sk -i https://app.nuxaris.com/ -H "Host: evil.com" | grep -E 'HTTP|x-vercel-error'
curl -sk -i https://app.nuxaris.com/ -H "X-Forwarded-Host: evil.com" | grep x-vercel-cache
curl -sk -i https://auth.nuxarisapiv1.xyz/health -H "Origin: https://evil.com" | head -20
curl -sk -i https://nuxarisapiv1.xyz/api/health -H "Origin: https://evil.com" | grep -E 'HTTP|access|vary'
curl -sk -i https://auth.nuxarisapiv1.xyz/api/auth/account-state -H "Content-Type: application/json" -d '{"email":"x@mail.com"}' | grep ratelimit
for h in "X-Forwarded-For: 9.9.9.9" "Forwarded: for=9.9.9.9"; do curl -sk -i -H "$h" -H "Content-Type: application/json" -d '{"email":"x"}' https://auth.nuxarisapiv1.xyz/api/auth/account-state | grep HTTP; sleep 4; done
curl -sk -w "%{http_code} %{size_download}\n" -o /tmp/x https://app.nuxaris.com/.env; wc -c /tmp/x
grep -o 'REACT_APP_[A-Z_]*' /tmp/main.js | sort -u
grep -oP 'VERCEL_URL:"[^"]*"' /tmp/main.js | head -1
curl -sk -i https://nuxaris-91rna9dx7-clickpaws-projects.vercel.app/ | head -5
```
Report: `/root/AGENT_C_INFRA_CACHE_CADDY_REPORT.md`
