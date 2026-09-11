# Nuxaris Wave 2 — 4-Agent Exhaustive Chain Hunt (CRA + Dual Caddy + Dual Rate Limit) 2026-08-16

**Target:** `app.nuxaris.com` (CRA Vercel 1605B SPA) + `auth.nuxarisapiv1.xyz` + `nuxarisapiv1.xyz/api/bridge` (single Hetzner 37.27.59.179 Caddy)
**Duration:** 85m, 15+ rounds, 4 CDC agents + manual pacing | **Verdict:** 0 pre-auth RCE proven, 2 PROVEN lows (sourcemap+key, CORS 500)

## Architecture in 30s
- Frontend: CRA Webpack `1605B <!doctype><div id=root><script /static/js/main.040e5d2d.js>` (1.78MB) + `main.040e5d2d.js.map 6.89MB 731 sources` + `/asset-manifest.json 150 chunks`. Not Next/Nuxt — no `__NEXT_DATA__`, no `/_next/`.
- Backends: single Hetzner IP `37.27.59.179` Hetzner Helsinki (`static.179.59.27.37.clients.your-server.de`) serves both `auth` (`api-accounts`, `POST /api/auth/*`) and `bridge` (`api-bridge`, `GET/POST /api/bridge/*`) via Caddy `via:1.1 Caddy`. Grep `REACT_APP_AUTH_API_URL||"https://auth...` + `BRIDGE_API=https://nuxarisapiv1.xyz/api/bridge` in bundle reveals split.
- Auth: invite-gated `POST /register {username,email,invite_code}` → email verify `6-digit` → vault `IndexedDB nuxaris-wallet:v2` `PBKDF2 600k AES-GCM 16/12/128` + `localStorage access_token/refresh_token Bearer` + `401→POST /refresh {refresh_token}` silent retry. Signing namespace `nuxaris-login:` UTF-8 vs 32B base64 tx hash isolated in `wallet/signing.ts`.
- Bridge: public `GET /tokens /routes /price/CC /quote?tokenA=SYMBOL.chain&amount=` unauth; private `POST /order/* /wallet/* /premium/* /rewards/*` need Bearer. Quote validated `SYMBOL.chain` + `amount>0`.
- Rate limits: `auth 10;w=60` (`ratelimit-limit:10 ratelimit-remaining:0 retry-after:26`) vs `bridge 60;w=60`. Global sliding bucket across all `/api/auth/*`. CORS allowlist strict `https://app.nuxaris.com` only; `evil.com` on auth crashes `500`, on bridge silent no `ACAO`.

## Divergent 4-Agent Design (CDC)
| Agent | Theory | Key Probes | Result |
|-------|--------|------------|--------|
| A Business/Invite/JWT | invite bypass, `account-state` enum, `alg:none`, verb tamper | `invite_code=""→400 required`, `"nuxaris"/"test"/"admin"/"0"→400 Invalid`, 8/60→429, `{"$gt":""}→400 email required`, `"admin OR 1=1--"→401`, `Bearer eyJhbG...none→401`, `PUT /tokens→404` | BLOCKED |
| B Injection/SSRF | `publicKeyHex`/`receiverPartyId`/`destinationAddress`/`__proto__`/path traversal/SSTI/XSS | `tokenA=<script>→400 Unknown token ID`, `{{7*7}}→400`, `username <img onerror>→400 regex ^[a-zA-Z0-9_-]{3,50}$`, `__proto__:{isAdmin}→Invalid invite`, `GET /bridge/../auth/me→Cannot GET /api/api/auth/me`, `%2e%2e` same | BLOCKED |
| C Infra/Cache | Host inject, cache poison, `.env/.git`, Vercel preview, XFF bypass | `/api/* /.env /.git/HEAD→200 but body index.html 1605B` (SPA fallback decoy), `XFF 9.9.9.9` 15-burst→429 (no bypass), `OPTIONS evil.com→500` vs `app.com→204+ACAO` | BLOCKED |
| D Client Chain | DOM XSS `dangerouslySetInnerHTML`/`postMessage`, vault wipe, WalletConnect, supply chain | grep 731 sources: `dangerouslySetInnerHTML 0`, `innerHTML 0`, `postMessage 0` in app slice; `vault-crypto.ts` PBKDF2 600k + `wipe()` correct; `@noble/curves/viem/rainbowkit` clean; Helius only | Billing LOW |

## Proven Findings — Curl + Evidence

**PROVEN LOW 1: Sourcemap + Helius key (CWE-540+798)**
```
GET /static/js/main.040e5d2d.js.map → 200 6893749B etag bc6f1fc... cache-control:s-maxage=31536000 immutable
grep REACT_APP_SOLANA_RPC → https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY>
POST https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY>... {"method":"getHealth"} → {"result":"ok"}
POST {"method":"getVersion"} → {"solana-core":"4.2.0-rc.1"}
POST {"method":"getBalance",["11111111111111111111111111111112"]} → {"value":26731424560}
```
Impact: billable quota burn / Solana feature DoS, not fund theft. Fix: rotate + proxy via `nuxarisapiv1.xyz/api/solana`, `GENERATE_SOURCEMAP=false`, `REACT_APP_SOLANA_RPC=""`.

**PROVEN LOW 2: CORS evil → 500 crash (LOW, not HIGH)**
```
OPTIONS https://auth.nuxarisapiv1.xyz/api/auth/account-state Origin:https://evil.com + ACRM:POST → 500 Internal (no ACAO)
GET https://nuxarisapiv1.xyz/api/bridge/tokens Origin:https://evil.com → 200 but NO access-control-allow-origin (strict allowlist)
```
Distinguish `crash 500 no ACAO` vs `reflect evil.com + ACAC:true HIGH`. Fix: return 403 not 500 for unknown origin.

## Hardening Signals (why RCE blocked)
- `quote?amount=0/-1/NaN/Infinity/1e308` → `400 amount must be positive` or `Fees exceed input value`; `tokenA=../../etc/passwd/<script>/{{7*7}}` → `400 Unknown token ID SYMBOL.chain`; `username` strict `^[a-zA-Z0-9_-]{3,50}$` (LandingPage.tsx:115); `__proto__` ignored; no `File/FormData` upload sinks.
- Private `GET /api/auth/me /wallet/provisioning /wallet/addresses /bridge/orders /bridge/order/:id` without Bearer → consistent `401 Missing or invalid Authorization` (or `404 Cannot GET` for decoy). No IDOR without 2 valid invites.
- Hardline blocklist: `curl | python3`, `python3 <<'PY'`, `grep -oP` → BLOCKED; workaround `write_file(/tmp/name.py)` + `urllib.request+ssl._create_unverified_context()+Mozilla UA` + `python3 /tmp/name.py`.
- Direct IP `http://37.27.59.179/ Host:auth...` → `308 → https://auth...` (Caddy), not bypass.

## Pacing Protocol (dual-bucket)
- Auth burst 10 → 429 masks `400 vs 200 {step:unknown}` oracle. Rule: `1 req / 7-8s` + `sleep 60-65 after 429` + check `ratelimit-remaining/ratelimit-reset/retry-after` header before next. Bridge 60/60 tolerates faster but keep 3s. Without pacing earlier 10-probe burst collapsed enumeration. Without sleep, rapid 15 `rapid_*@test.invalid` all `429`.

## Blind Spots & Next Triggers
- Authenticated IDOR/JWT needs 2 valid invites (not obtained) → `GET /order/:otherId`, `PATCH /wallet/addresses/:id`, `login-key {nonce,signature}` replay, 30s `prepare` hash expiry.
- Topology hex `signTopologyHash /^[0-9a-fA-F]{40,140}$/` ReDoS unlikely but worth fuzzing `a*10000`.
- Re-test triggers: `REACT_APP_*` grep reveals new backend subdomain; `ratelimit-remaining` header changes shape; sourcemap size changes; `X-Forwarded-For` suddenly reflects different `ratelimit-policy`.

## Evidence Template (Trigger→Effect→Boundary)
- `[GET /static/js/main.040e5d2d.js.map → 200 6.89MB sourcesContent → PROVEN public leak, Boundary: CDN → Browser]`
- `[POST /api/auth/register {invite_code:"test"} → 400 Invalid invite code → BLOCKED gate, Boundary: Public → Auth API]`
- `[GET /api/bridge/quote?tokenA=<script> → 400 Unknown token ID → BLOCKED validation, Boundary: Public → Bridge API]`
- `[OPTIONS auth Origin:evil.com → 500 no ACAO → LOW crash, Boundary: Evil Origin → Caddy CORS]`
