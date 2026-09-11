# Nuxaris 2026-08 — Invite, Rate-Limit, Quote & JWT Deep Hunt

Source: `app.nuxaris.com` (Vercel `main.040e5d2d.js` + 6.6 MB `main.040e5d2d.js.map`), `auth.nuxarisapiv1.xyz`, `nuxarisapiv1.xyz/api/bridge`, `www.nuxaris.com` (Next _next chunks), `nuxaris.notion.site/doc`. Throttle: Caddy `Ratelimit-Limit: 10;w=60` (auth), `60;w=60` (bridge quote), `30/20/10;w=60` (wallet/order/premium). Evidence: `/tmp/agentA_evidence.jsonl` (91 req, 8 s gap).

## Sourcemap extraction (SPA-decoy bonus)
- `curl -s https://app.nuxaris.com/static/js/main.040e5d2d.js | grep -o sourceMappingURL` → `main.040e5d2d.js.map` (Vercel, `6.6M`, `6,893,749` B, `HIT`). `jq .sources / .sourcesContent` — filter out `node_modules`, save `config/api.ts`, `services/api.ts`, `services/wallet-api.ts`, `contexts/AuthContext.tsx`, `wallet/*.ts` (SLIP-10, ed25519 `nuxaris-login:` prefix), `services/wallet-api.ts` (30 s prepare-then-sign pattern). Lesson: sourcemap stays public after migration — treat as source.

## Auth surface (from sourcemap + live probe)
- `POST /api/auth/register` body `{username, email, invite_code}` → `400 Invalid invite code` (string), `400 username, email and invite_code are required` (missing), `500 Internal server error` on non-string (number/float/array — type-confusion crash, repro after cooldown, `Remaining` shows not rate-limited). Empty `""`, whitespace `"   "`, `null` → required/400; SQLi/case/common guesses (`NUXARIS`, `INVITE`, …) → `400` correctly blocked. No string bypass.
- `POST /api/auth/account-state` `{email}` → always `200 {"step":"unknown"}` — no enumeration. `POST /resend-verification` → `200 {"message":"If the email exists, a new code has been sent."}` timing 0.586 s vs 0.587 s identical — no timing oracle. `POST /login` → `401 Invalid credentials` uniform. `POST /verify-email` bogus → `400 Invalid or expired verification code`. `POST /challenge` → 429 when window full, else nonce.
- `POST /api/auth/refresh` `{refresh_token}` → empty `400 refresh_token is required`, garbage/none/array/wrong key → `401/400` — no bypass.
- Helius key `https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY>` → `{"result":"ok"}` (still valid — rotate).
- Notion docs (`nuxaris.notion.site/doc` + `6-Nuxaris-Incentive-System-…`) both return 19 381 B Notion shell, `www.nuxaris.com` 7 Next chunks 0 `invite` hits — no leak.

## Rate-limit (Caddy) — header bypass negative
- Headers: `Ratelimit-Limit`, `Ratelimit-Policy: 10;w=60`, `Ratelimit-Remaining`, `Ratelimit-Reset`, `Retry-After`. Bridge quote `60;w=60`. Replaying `POST /account-state` with `X-Forwarded-For: 1.1.1.1/8.8.8.8/127.0.0.1`, `X-Real-IP`, `X-Originating-IP`, `CF-Connecting-IP`, `True-Client-IP` → `Remaining` still decrements linearly `6→5→4→3→2` — IP-bound at Caddy, not header-overridable. Must `sleep 8` between hits; burst of ~8 before triggers `429`. Fix: single throttled loop, `ensure_gap()` with `8.0 - elapsed`, log `Retry-After`.

## Bridge quote business logic
- `GET /api/bridge/tokens` / `routes` → `200` unauthenticated (public by design — `ETH.ethereum`, `CC.canton`, `ETH.base`, `SOL.solana`; limits `ETH→CC max 5`, `CC→ETH max 100k`). Quote `GET /quote?tokenA=CC.canton&tokenB=ETH.ethereum&amount=…` also unauthenticated (`200` even with `Bearer fake`). Correct rejections: `0`/`-1`/`NaN`/`Infinity`/`null` → `400 amount must be positive`; dust `0.000000001` → `400 Fees exceed input value`. Missing token format `CC` (no `.chain`) → `400 Unknown token ID. Use format SYMBOL.chain`. Bypass: `999999999` (max 100 k) → `200 amountOut 50524`; `100 ETH→CC` (max 5) → `200 amountOut 1957572`; `1e20` → `200`; `1e24` → `200 amountIn 1e24 amountOut 5e19` — max not enforced. Param pollution `?amount=100&amount=999…` silently uses first value; `%00` truncated. `POST /order/erc20` with negative/zero/huge/invalid dest correctly `401 Missing or invalid Authorization header` — limit bypass not tradable pre-auth but quote spam/DoS surface is.

## JWT
- `GET /api/auth/me` no token → `401 Missing or invalid Authorization header`; garbage → `401 Invalid token`; `alg:none` (`eyJhbGc…`) → `401`; HS256 weak secrets (`secret`,`nuxaris`,`password`,`123456`,`auth_secret`,`jwt_secret`,`nuxarisapiv1`) → all `401`; `kid=../../../../etc/passwd`, `jku=https://evil.com`, `kid=none` → `401`. Wallet `POST /wallet/init` without auth `401`, with fake alg:none `401`.

## CORS
- `Origin: https://app.nuxaris.com` → `OPTIONS /api/auth/register` `204` + `Access-Control-Allow-Origin: https://app.nuxaris.com` + `Allow-Credentials: true`. `https://evil.com`, `https://app.nuxaris.com.evil.com`, `https://evil-app.nuxaris.com`, `null`, `http://localhost` → `500` no `ACAO` — suffix attack blocked (not `*.nuxaris.com`).

## Workflow pitfalls learned
- Must enforce `8 s` gap client-side before every rate-limited hit; `Retry-After`/`Ratelimit-Reset` tells window; parallel fan-out trips edge 429s — use `sleep 8` loop, not `xargs -P 16` for auth.
- Bridge `SYMBOL.chain` dot format required to reach real quote logic; `CC` alone always `400 Unknown token`.
- Evidence contract: every verdict needs captured `curl` + `status` + `body` in `evidence.jsonl` — no prose-only claims.
