# api.noise.xyz Fuzz — 2026-08-12 — Vite Privy SPA REST API

Source: `noise-xyz/brane` SDK + `api.noise.xyz` live fuzz (50+ requests, nyantai 0.8-1.2s throttle, 6 stages).
Artifacts: `/tmp/fuzz_api_noise.py`, `/tmp/fuzz_api_deep2.py`, `/tmp/fuzz_api_results.json` (34 req), `/tmp/track1_cf.py`, `/tmp/track1_api.py`.

## Target Fingerprint
- Frontend: Vite + rolldown + React vendor (not Next.js). Assets `/assets/index-*.js`, `/assets/services-WqpUQ0Yg.js`. No `/_next`.
- CSP `connect-src https://*.noise.xyz https://api.noise.xyz https://*.privy.io wss://*.privy.io` + Stripe, Plaid, Moonpay, PostHog.
- Backend: `https://api.noise.xyz/api/*` REST. `https://docs.noise.xyz` Mintlify. No `/_next`, `/api/trpc`, `/graphql`.
- Exposed env: `VITE_API_BASE_URL=https://api.noise.xyz/api`, `VITE_PRIVY_APP_ID=cmm9myejp00ug0ci8qxky5ocd`, `VITE_PRIVY_CLIENT_ID=client-WY6WjKbTDAVtj3TDMsyvpqq355bF5ZRKbugDf1E8k4z3j`.

## Endpoints (live 200 = public, 401 = Privy-gated, 404 = not found)
| Path | Status | Notes |
|------|--------|-------|
| `/api/health` | 200 `{"status":"ok"}` | cache-control public |
| `/api/trends` | 200 123720B | **ignores `?limit`/`?offset`** — limit=0,-1,999999,abc,1.5 all same body; vs `/api/posts` strict |
| `/api/trends/:idOrSlug` | 200 / 404 | id uuid OR slug (both resolve same object). Random uuid 404 `NOT_FOUND` correct. `../../etc/passwd` 400 nginx block. `<script>` reflected JSON only (CT application/json) not XSS. |
| `/api/posts` | 200 | `?limit` validated `<=100` — 999999 → 400 `HttpApiDecodeError` with schema leak (expected behavior, not RCE). |
| `/api/posts/:postId` | 200 / 404 / 400 | Strict UUID 400 refinement error, random 404 `Post not found`, valid 200. No IDOR. |
| `/api/p/:id` | 404 | dead |
| `/api/users/me`, `/api/trends/drafts` | 401 `ApiTokenUnauthorized`/`PrivyAuthUnauthorized` | no bypass via X-Original-URL, X-Forwarded-* |
| `/api/v1/*`, `/api/v2/*`, `/internal/*`, `/admin/*`, `/graphql`, `/swagger.json`, `/.well-known/openid-configuration` | 404 | no hidden surface |
| CORS `OPTIONS` | 204 `ACAO=https://noise.xyz` | evil.com empty — locked, not wildcard. `ACAC` empty. |

## Fuzz Stages (throttled 0.8-1.2s)
1. Public enumeration (8 paths) — find trends/posts public.
2. IDOR trends/:id (8 injections) — check reflection/SQL/XSS/traversal/long.
3. Posts IDOR (4 paths) — post detail strict UUID.
4. CORS/method confusion (6 methods OPTIONS/POST/PUT/DELETE/PATCH) — ACAO check.
5. Auth bypass (4 protected + 3 header tricks) — 401 stays.
6. Rate limit burst 3x + cache poison — no `x-ratelimit` / `retry-after`, 3 bursts all 200, `cache-control: public, max-age=30, s-maxage=60, stale-while-revalidate=300`.

## Differential Finding: Pagination Validation
- `GET /api/trends?limit=any` → 200 same body → missing `NumberFromString <-> int & positive & lessThanOrEqualTo(N)` refinement (compare posts which has it).
- False positive: body contains word "stack" (trend `Substack` description) — not stack leak.
- Risk LOW, but enables full dataset scrape without pagination — DoS-adjacent, fix: add `limit?: NumberFromString <-> int & positive & lessThanOrEqualTo(100)` like posts.

## UUID Validation Differential
- Posts strict: `../../etc/passwd` → 400 `UUID refinement failure` — GOOD.
- Trends lenient: `OR '1'='1` → 404 `NOT_FOUND` with id echo — lenient but not SQLi (parameterized), JSON CT prevents XSS.

## Security Verdict
- No pre-auth RCE surface. No IDOR/BOLA on tested ids. CORS locked. No header injection bypass. No rate limit observed (missing `RateLimit-*` recommendation).

## Mitigations
- Add pagination refinement to `/api/trends` matching `/api/posts`.
- Add `RateLimit-*` / `Retry-After` headers.
- Consider `X-Content-Type-Options: nosniff` already present via CSP, verify `Content-Type: application/json` on all 404 echo to prevent XSS via JSON.

## Repro (throttled, safe no-auth)
```bash
# Public
curl -H 'Origin: https://noise.xyz' https://api.noise.xyz/api/trends | jq '.data[0].id'
curl 'https://api.noise.xyz/api/trends?limit=999999' -H 'Origin: https://noise.xyz' | wc -c  # same as ?limit=1
curl https://api.noise.xyz/api/posts?limit=999999  # 400 refinement error — strict
curl https://api.noise.xyz/api/trends/playstation  # slug works
curl https://api.noise.xyz/api/trends/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee  # 404 correct
# CORS
curl -i -X OPTIONS https://api.noise.xyz/api/trends -H 'Origin: https://evil.com'  # ACAO empty
```
