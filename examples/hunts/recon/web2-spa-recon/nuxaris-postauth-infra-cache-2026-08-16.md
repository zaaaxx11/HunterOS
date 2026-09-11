# Nuxaris Post-Auth Infra & Client Re-check — Fake-JWT Simulation (2026-08-16)

Source: Agent D /tmp/agentD_live.py 18 req @ 8s, curl Host controls, sourcemap 731 sources 6.89 MB.

## No valid invite — simulation pattern
- No fresh invite leaked (20× `Already used` 10-hex, bundle/Notion/site 0). Real JWT gates (`wallet/init`, `topology-submit`, `preapproval`, `orders`, authenticated `destinationAddress` SSRF) stay BLOCKED — note as residual needing 1 fresh code (ideally 2 for IDOR).
- Still run full infra matrix with `Authorization: Bearer <fake>` (HS256 random + `alg:none` `eyJ...`) and diff vs no-JWT baseline. Every claim needs captured `HTTP code + ACAO/ACAC/Vary/x-vercel-cache/age/ratelimit/Via/Server`.

## CORS + JWT (8s throttled, evidence)
```
GET /api/auth/me Origin:evil.com no JWT          → 500 no ACAO (Caddy throw)
GET /api/auth/me Origin:evil.com + Bearer fake   → 500 no ACAO (unchanged)
GET /api/auth/me Origin:app.nuxaris.com + fake   → 401 Invalid token ACAO app.nuxaris.com ACAC:true Vary:Origin
GET /bridge/premium/status Origin:evil.com+fake  → 401 Vary:Origin no ACAO
GET /bridge/premium/status valid Origin+fake     → 401 ACAO app.nuxaris.com
```
JWT does not widen allowlist. Distinguish crash-500 LOW from reflect+ACAC HIGH.

## Host header + JWT (Caddy vhost isolation)
- `curl -sk -i https://auth.nuxarisapiv1.xyz/api/auth/me -H 'Host: evil.com' -H 'Authorization: Bearer fake'` → `200 content-length:0 Server:Caddy` (no `Via:1.1`) — default vhost empty, not backend JSON. Same `bridge/tokens`. Python `requests` strips Host — use curl.
- `X-Forwarded-Host: evil.com` / `X-Real-IP` / `CF-Connecting-IP` ignored (still 429 or same 200 quote).

## Cache poisoning + auth (Vercel vs Caddy)
- Vercel SPA: `GET / -H X-Forwarded-Host:evil.com` → `HIT age 7514` SPA 1605; `Authorization:fake` same HIT; `?__vercel_no_cache=1` still HIT; `/api/auth/me` via `app.nuxaris.com` → `200 HIT SPA` fallback; `static/js/main.*.js + Authorization` → `HIT s-maxage 31536000 immutable` same etag. Deception `app.nuxaris.com/api/bridge/tokens.css` → `200 HIT SPA s-maxage 0`.
- Caddy backends (`auth` 37.27.59.179 `Via:1.1`, `bridge`) — no `x-vercel-cache`, `Vary: Origin`, auth'd JSON never edge-cached; `Authorization` not cache-key. HTML `max-age 0 must-revalidate` not poisonable.

## Vault crypto (client, holds post-auth)
- `wallet__vault-crypto.ts: PBKDF2_ITERATIONS 600000`, `AES-GCM 256`, `SALT 16 IV 12 TAG 128`, AAD `nuxaris-vault:v${version}:${accountId}` (binds ciphertext to account), non-extractable.
- `wallet__storage.ts: DB nuxaris-wallet / store vaults` IndexedDB ciphertext-only, `wipe` on lock, `VaultContext.tsx: AUTO_LOCK_MS 15*60*1000`.
- `services__vault-index.ts: localStorage nuxaris_vault_accounts` email→UUID index (non-secret), plus `access_token/refresh_token`, `nuxaris_balance_history`, `nuxaris_hide_values`. Never vault plaintext in localStorage.
- `wallet__signing.ts: LOGIN_NONCE_PREFIX nuxaris-login:` — login vs prepared-tx (32B base64) namespaces disjoint.
- XSS: grep `dangerouslySetInnerHTML/innerHTML` only React internals + `Array(20).fill(...).join("<br>")` matrix-fall false; `/?xss=<svg onload=alert(1)>` not reflected in shell.

## Verify-email timing + invite reuse
- `POST /api/auth/verify-email {email, token:"000000"}` → `400 Invalid or expired verification code` `0.556s`; `"999999"` `0.553s` (Δ 3ms) then `429 Too many requests` `10;w=60` shared bucket; `"short"` same 400. `POST /resend-verification` → `200 If the email exists...` `1.17s`. No oracle; bucket throttles single-IP but not distributed.
- Double `POST /register {invite_code:"FAKECODE123"}` → both `400 Invalid invite code` (correct). Real reuse residual: `Already used` vs `Invalid` (10-hex format) + race `race_a`+`race_b` both `Already used` proves single-use lock — needs fresh code to chain `register→verify→login→JWT→admin`.

## Admin disclosure (unchanged with JWT)
- `GET /api/admin` / `/api/admin/users|orders|invites` → `403 Forbidden ratelimit 30;w=60` both no-JWT and fake-JWT (vs `404` for `/api/users/.env`). `GET /api/auth/admin` → `404 Cannot GET`. Traversal `/api/bridge/../api/admin` → `404 Cannot GET /api/api/admin`. Frontend `contexts__AuthContext.tsx: role:string` type only, no `role==='admin'` gate — admin server-only.

## Health CORS crash
- `GET /health Origin:evil.com` on `auth` → `500 Internal` (same as `/api/auth/me` crash); bridge `/api/health` evil → `200 Vary:Origin` no ACAO correct.

## Runbook (single harness)
`/tmp/agentD_live.py` — 18 probes with 8s `wait()` via `requests`, plus raw `curl -H 'Host: evil.com'` for Host. Log `/tmp/agentD_evidence.jsonl`. Check `ratelimit-remaining/reset` before each auth probe; sleep 60-65 after 429.
