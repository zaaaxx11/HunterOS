# Nuxaris Bridge Fuzz — app.nuxaris.com (2026-08-16)

## Target
- `app.nuxaris.com` (Vercel SPA, `main.040e5d2d.js` 1.78 MB React/Wagmi/RainbowKit)
- `auth.nuxarisapiv1.xyz` (Caddy, ratelimit 10/60s, CSP `default-src 'self'`)
- `nuxarisapiv1.xyz/api/bridge` (Caddy, ratelimit 60/60s)

## Recon
- Single bundle: `grep -oE 'https?://[^"\' ]+'` + `grep -oE '"/api/[^"]*"'` extracted 15 auth routes + 14 bridge routes (`/tokens`, `/price/CC`, `/quote?tokenA=&tokenB=&amount=`, `/orders`, `/wallet/*`, `/premium/*`). Base URLs via `REACT_APP_AUTH_API_URL || "https://auth.nuxarisapiv1.xyz"` and `"https://nuxarisapiv1.xyz/api/bridge"`.
- LS keys: `access_token`, `refresh_token`, `nuxaris_*`. `FormData/multipart/type=file` 0 hits — no upload surface.
- Live probe needs spacing: auth 429 after ~10 in 60s (`ratelimit-remaining:0 retry-after:47`), bridge 60/60s (6 parallel `price/CC` all 200). `app.nuxaris.com` Vercel `access-control-allow-origin: *` but static only; APIs return no ACAO without Origin.

## Endpoint Map (fuzzed unauth where possible)
| API | Method | Params | Auth | Outcome |
|-----|--------|--------|------|---------|
| `POST /api/auth/register` | `username` (`^[A-Za-z0-9_-]+$`), `email`, `invite_code` | no | 400 strict allowlist blocks `<script>`, `{{7*7}}`, `' OR 1=1 --`, `A*1000`, `\x00`, `__proto__`, XML, array |
| `POST /api/auth/login` | `email`,`password` | no | 401/429, no reflection, array `email:[]` 429 |
| `POST /api/auth/challenge` | `email` | no | 200 nonce `nuxaris-login:uuid` (valid email); XSS/SQLi → 429 generic |
| `POST /api/auth/account-state` | `email` | no | 400 `email is required` when empty |
| `GET /api/auth/me` | `Authorization: Bearer` | yes | 401 without token; header XSS/SQLi/`A*5000` → 401, not reflected |
| `GET /api/bridge/tokens` | `?search=` optional | no | extra `?url=`/`?search=<script>` ignored, returns 4 static tokens |
| `GET /api/bridge/price/<symbol>` | path `symbol` | no | XSS/traversal → 404 `Cannot GET ...%3Cscript%3E` (URL-encoded, not executable) |
| `GET /api/bridge/quote` | `tokenA` `SYMBOL.chain`, `tokenB`, `amount` positive | no | whitelist `SYMBOL.chain`; `tokenA[]`→400, `__proto__`→200 ignored |
| `GET /api/bridge/orders` `wallet/*` `premium/*` | various | yes | 401 before pollution logic |

## Fuzz Results
- **XSS/SSTI/SQLi/header-injection/proto-pollution/SSRF/HPP**: all BLOCKED (allowlist or ignored). 404 handler reflection is URL-encoded. No `url=` fetch sink (`?url=http://169.254.169.254` ignored).
- **Overflow/edge**: `amount=-1/0/NaN/Infinity`→400 correct; `amount=1e308`→400 `Fees exceed input value`; `A*300` token→400.
- **Business logic (MEDIUM)**: `limits: {minAmount:0.01, maxAmount:5, symbol:ETH}` returned by quote but NOT enforced. `amount=0.001` (below min)→200 `amountOut=12.44`; `amount=5.01`/`10`/`999999999999`/`1e30`→200 (`1e30`→1.94e34). Fee-dust guard works, min/max does not. `tokenA==tokenB` correctly 400.
- **Rate limit**: auth 10/60s, bridge 60/60s confirmed via `ratelimit-limit/policy/remaining/reset` headers. Parallel 5× `POST /api/auth/refresh` with fake token→all 401 identical (no race).
- **CORS/headers**: auth+bridge CSP `default-src 'self'`, `SAMEORIGIN`, `nosniff`, HSTS 31536000. Bridge no ACAO by default. `GET /api/auth/me`+`Origin: evil.com`→500 `Internal server error` (error-handler leak, not bypass).
- **Race/CORS**: 5-parallel refresh deterministic 401; `Origin: evil.com` on tokens→no ACAO leak.

## Reproduce
```bash
# should be 400 but is 200 (max not enforced)
curl -sk "https://nuxarisapiv1.xyz/api/bridge/quote?tokenA=ETH.ethereum&tokenB=CC.canton&amount=5.01" | jq .
curl -sk "https://nuxarisapiv1.xyz/api/bridge/quote?tokenA=ETH.ethereum&tokenB=CC.canton&amount=999999999999" | jq .
# register XSS blocked
curl -sk -X POST https://auth.nuxarisapiv1.xyz/api/auth/register -H 'Content-Type: application/json' -d '{"username":"<script>alert(1)</script>","email":"x@x.com","invite_code":"x"}'
# rate limit headers
curl -skI https://auth.nuxarisapiv1.xyz/api/auth/me | grep -i ratelimit
curl -skI https://nuxarisapiv1.xyz/api/bridge/tokens | grep -i ratelimit
```

## Lessons for Next Audit
- Space auth probes 2s+ or 8-10s cooldown after 429 (retry-after header tells exact wait). Bridge probes can burst 6 but auth cannot.
- Bridge `quote` min/max is client-only — always test just-over-max, huge scientific notation, and sub-min dust to prove server gap.
- Check for `500` on `Origin: evil.com`+no-auth combo (auth error + CORS path interaction).
- Verify absence of upload via `FormData`/`multipart` count in bundle before claiming no file surface.
