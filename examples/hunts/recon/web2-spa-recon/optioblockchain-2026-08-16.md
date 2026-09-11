# OptioBlockchain — React CRA SPA + FastAPI Hunt (2026-08-16)

Source: https://optioblockchain.com/ — live hunt with web2-deep.py v3 + manual Mozilla curl.

## Stack
- Frontend: React CRA SPA `main.59918b3a.js` 500KB + `buy-opt-widget.umd.js` + `buy-opt-sdk.umd.js`, `index.html` 2096B, `div#root`, Cloudflare `cf-ray …-SIN`, `via: 1.1 google` (GCP), `customer-assets.emergentagent.com` favicon, `assets.emergent.sh/scripts/debug-monitor.js` iframe trap.
- Backend: FastAPI `optiocloud-backend` same-origin `/api/*`, `GET /api/health → {"status":"healthy","service":"optiocloud-backend"}`, `REACT_APP_BACKEND_URL=https://optioblockchain.com`, Stripe `pk_live_…` + `pk_test_…` publishable only.
- Subdomains: `www` 200, `onramp.optioblockchain.com` 503 `x-render-routing: suspend-by-user`, `explore.optioblockchain.com` 403 CF, `api/admin/app/portal/dashboard/node/docs/status` 000 (no DNS).

## SPA Catch-All Trap (CRA variant)
- Every unknown path (`/.env`, `/openapi.json`, `/swagger`, `/graphql`, `/admin/api/login`, `/api/openapi.json`) returns `200 text/html 2096B <!doctype html>` identical to `/` with `cf-cache-status: DYNAMIC`, `etag: "6a678bd4-830"`. `web2-deep.py` flagged 9 🔥 but all decoy.
- Validation: `curl -sk -H "Accept: application/json" https://optioblockchain.com/.env | head -c 50` → `<!doctype html>` = SPA fallback. Real APIs return JSON `{"detail":"Not authenticated"}` / `{"status":"healthy"}` / `[]`. Also `curl -sk -I /openapi.json` vs `/api/openapi.json` — latter returns `{"detail":"Not Found"}` JSON 404 (real FastAPI 404).
- JS ground truth: `grep -oP '"/api/[^"]+"' main.59918b3a.js | sort -u` → only 10 real endpoints: `/api/admin/me`, `/api/admin/login`, `/api/auth/me|signup|login/unified|change-password|profile-picture`, `/api/cart/`, `/api/compliance/check-location`, `/api/developers/upgrade`. `grep -oP "'/api/[^']+'"` empty — double-quote only.

## Auth Boundary (Admin + User)
- Admin: React `AdminAuthProvider` → `localStorage adminToken + adminUser`, `fetch("/api/admin/login", POST {email,password}) → {access_token, admin}`, stored `Bearer`, `GET /api/admin/me` with `Authorization: Bearer <token>` validates, without → `401 {"detail":"Not authenticated"}`, method check `GET /api/admin/login → 405 Method Not Allowed`. `hasPermission` checks `admin.permissions.includes("all"|perm)`.
- User: `/api/auth/login/unified`, `/api/auth/me`, same `auth_token` localStorage pattern, `GET /api/auth/me` 401 without auth.
- No hardcoded secrets: 603,578 chars JS scan `firebase|supabase|AKIA|secret|password` clean, `dangerouslySetInnerHTML` static React only.

## Live Probe Matrix (Mozilla UA)
```
GET /api/health → 200 {"status":"healthy"}
GET /api/compliance/check-location → 200 {"ip":"43.156.23.22","country_code":"SG","is_sanctioned":false}
GET /api/admin/me → 401 Not authenticated
GET /api/admin/login → 405 Method Not Allowed (POST required)
POST /api/admin/login {test@test.com/test123} → 401 {"detail":"Invalid email or password"}
POST /api/admin/login {admin@optioblockchain.com/admin123} x3 → 401 each, no 429 → no rate-limit
GET /api/auth/me → 401
GET /api/openapi.json → 404 {"detail":"Not Found"} (real FastAPI)
GET /openapi.json → 200 HTML (SPA fallback)
```

## Headers / CORS
- `access-control-allow-origin: *` + `access-control-allow-credentials: true` + `access-control-expose-headers: *` on `/api/health` (with `Origin: https://evil.com`) + `vary: Origin` — CORS misconfig (* + credentials). Not directly exploitable without XSS, but pairs with `profile-picture` upload / `innerHTML` sink → token theft via `adminToken`.
- `strict-transport-security: max-age=63072000; includeSubDomains; preload`, `x-content-type-options: nosniff`, `referrer-policy: strict-origin-when-cross-origin`.

## SPA Router
- `to:"/"`, `to:"/dashboard"`, `to:"/demo"`, `to:"/developers/docs"`, `to:"/login"`, `to:"/products"`, `to:"/signup"` + `path:"/admin"` via `useAdminAuth`. No Next.js App/Pages Router — CRA `BrowserRouter`.

## Next Steps (Authenticated)
- `profile-picture` upload → test `.svg/.php` + XSS, `cart` price tampering, `developers/upgrade` IDOR, `compliance/check-location` `X-Forwarded-For` bypass, JWT `adminToken` alg none / forge, brute-force with `adminToken` rotation.
