# Nuxaris Red-Teamer — Auth & Access Control (CRA + Dual Caddy + 10/60) 2026-08-16

## Target Shape
`app.nuxaris.com` CRA Webpack on Vercel (`div#root`, `/static/js/main.040e5d2d.js` 1.78MB, `server:Vercel`, `ACAO:*` static shell) — every `/api/*` returns `200 <!DOCTYPE>` SPA fallback, not an endpoint. Real APIs off-domain via bundle:

```
REACT_APP_AUTH_API_URL || "https://auth.nuxarisapiv1.xyz"  // api-accounts, /health {"service":"api-accounts"}
BRIDGE = "https://nuxarisapiv1.xyz/api/bridge"              // /price/CC, /tokens, /routes, /premium/status etc.
Via: 1.1 Caddy, Hetzner 37.27.59.179 single IP dual vhost
Storage: localStorage access_token/refresh_token -> Authorization: Bearer <JWT>; refresh POST /api/auth/refresh {refresh_token}
```

Discovered via `grep REACT_APP_AUTH_API_URL|BRIDGE_API|authFetch|/api/auth/` in `main.040e5d2d.js`; saved to `/tmp/main.js`.

## Stealth + Rate-Limit Pacing (critical)
Auth host `ratelimit-limit:10 ratelimit-policy:10;w=60 remaining:9..0 reset:60 retry-after:X`; bridge public 60/60, balance 20/60. Parallel `requests.Session` hit burst 429 masking all signals (early tests showed `NO RESP` because reuse collapsed). Fix: sequential `curl -s -i -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"` + `sleep 3-4` between requests + `sleep 40-50` after 429 (`Retry-After` header) + check `ratelimit-remaining` before next. Python `requests` with default UA got `NO RESP`/403 on chunks; Mozilla UA required for Caddy/Vercel.

## Evidence Matrix [Trigger→Effect→TrustBoundary] — all unauth unless noted

| Trigger | Effect | Boundary | Verdict |
|---|---|---|---|
| `GET /api/auth/me` no token | `401 Missing or invalid Authorization header` | anon→authed | BLOCKED |
| `GET /bridge/wallet/balance,/orders,/account/status` no token | `401 Missing or invalid Authorization header` | anon→authed | BLOCKED |
| `Authorization: Bearer eyJhbGciOiJub25lIn0...` / `Bearer invalid` / fakesig / `null` | `401 Invalid token` on `/me` and `/wallet/init`; `POST /refresh {invalid}`→`401 Invalid or expired refresh token` | attacker token→verifier | BLOCKED (alg none rejected) |
| `GET /me?token=invalid`, `Cookie: access_token=invalid`, `X-Access-Token: invalid`, `X-HTTP-Method-Override`, `%2f..%2f` traversal | `401 Missing...` or `404 Cannot GET` | header injection→canonical | BLOCKED |
| `Origin:https://evil.com GET /api/auth/me` | `500 Internal server error` no ACAO | evil.com→session | BLOCKED (but 500 leak) |
| `Origin:https://app.nuxaris.com GET /me` | `401` + `ACAO: https://app.nuxaris.com ACAC:true` | legit | ALLOWLIST correct |
| `Origin:https://evil.com GET /bridge/price/CC` (public) | `200` price JSON no ACAO | evil→public data | BLOCKED correctly (no reflect) |
| `Origin:https://app.nuxaris.com GET /bridge/price/CC` | `200` + `ACAO: app.nuxaris.com` | legit | correct |
| `OPTIONS evil.com /api/auth/me` vs `/bridge/price/CC` | auth `500` no ACAO; bridge `204` allow-headers/methods but no ACAO | preflight | BLOCKED (no cred steal) |
| `GET /api/admin` | `403 Forbidden` ratelimit 30/60 (vs `404` for `/.env,/.git/metrics/graphql`) | anon→priv | INFO leak (existence) |
| `POST /challenge {email:any}` → `POST /login-key {nonce, sig fake}` | challenge always `200 {nonce: nuxaris-login:<uuid>}` (even nonexistent), login-key fake sig `00*64` → `401 Invalid credentials`, empty sig `400 required` | attacker→key login | BLOCKED |
| `POST /account-state` existent vs nonexistent | both `200 {step:unknown}` timing 0.56s vs 0.65s same | attacker→oracle | BLOCKED (generic) |
| `POST /login` nonexistent vs admin wrong pw | both `401 Invalid credentials` | oracle | BLOCKED |
| `Host:evil.com` / `X-Forwarded-Host:evil.com` on resend-verification | `200 If email exists...` generic, no host reflected | header→email | no evidence |
| Injection `"' OR 1=1`, `{"$ne":null}`, `;DROP` on login/challenge | `401/200` generic, no SQL leak | input→DB | BLOCKED |

## CORS Allowlist Truth
Strict: `https://app.nuxaris.com` + `https://nuxaris.com` reflected with creds; `evil.com`, `app.nuxaris.com.evil.com`, `evilapp.nuxaris.com`, `null`, `sub.app.nuxaris.com`, `https://app.nuxaris.com:443` all `500` no ACAO (Caddy CORS middleware throws on not-in-list instead of silent omit). Bridge allowlist same `app.nuxaris.com`/`nuxaris.com` only. Distinguish crash-500 (LOW info leak/DoS) from reflect+`ACAC:true` (HIGH).

## JWT / Refresh
`POST /refresh {}`→`400 refresh_token is required`; `{refresh_token:invalid alg none}`→`401 Invalid or expired`. No fallback header accepted.

## Hidden Routes (single-request validated, 1.2s gap)
All `404` except `/api/admin 403`, `/health 200`. SPA fallback on `app.nuxaris.com` masks 404 — must test direct `auth.*`/`nuxarisapiv1.xyz` hosts, not app host.

## What Remains (needs valid JWT)
Authenticated IDOR: create 2 accounts (invite_code gated → `400 Invalid invite code` without valid code, brute 8 in 60s → 429) then `GET /orders?otherUserId` / `PATCH /addresses/:id` / `GET /api/admin` with user token to test horizontal/vertical. Not disproven unauth.

## Repro (sequential, Mozilla)
```bash
curl -s -i -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0" https://auth.nuxarisapiv1.xyz/api/auth/me
curl -s -i -A "Mozilla/5.0 ..." -H "Authorization: Bearer <REDACTED-JWT>" https://auth.nuxarisapiv1.xyz/api/auth/me
curl -s -i -A "Mozilla/5.0 ..." -H "Origin: https://evil.com" https://auth.nuxarisapiv1.xyz/api/auth/me
curl -s -i -A "Mozilla/5.0 ..." -H "Origin: https://app.nuxaris.com" https://auth.nuxarisapiv1.xyz/api/auth/me
curl -s -X POST -A "Mozilla/5.0 ..." -H "Content-Type: application/json" -d '{"email":"test@example.com"}' https://auth.nuxarisapiv1.xyz/api/auth/challenge
# then login-key with got nonce + fake sig 00*64
curl -s -i https://auth.nuxarisapiv1.xyz/api/admin
sleep 4  # between each; sleep 40 after 429
```

## Issues Hit
`requests.Session` burst → 429/no-resp; f-string backslash SyntaxError; `app.nuxaris.com /api/*` always HTML not API; `curl -A Mozilla` required.
