# Everlyn AI Stored XSS — 2026-08-09 Session

## Sink
- `POST /api/update-wallet-address` — accepts `metamask_address` raw, no allowlist. `GET /api/get-mobile-wallet` returns raw `metamaskAddress`.
- Throttle: 0.6-0.7s per POST/GET, sequential. Account `labxss_7268@example.com` (`9b2d5621-fc65-41f7-b105-c5fd27fd40d0`, `<REDACTED-PASSWORD>`, session `__Secure-authjs.session-token` eyJ..., expires 2026-09-07, Stripe `cs_live` orders `853582281154629`).
- Proof: `POST {"metamask_address":"<img src=x onerror=alert(1)>"}` → 200 `Wallet addresses updated successfully` → `GET /api/get-mobile-wallet` → 200 `{"metamaskAddress":"<img src=x onerror=alert(1)>","hasMobileWallet":true}`. Second payload `"><svg onload=confirm(1)>` similarly reflected raw (escaped as `\"` in JSON but raw value). No CSP (`no CSP` header). `POST /api/update-wallet-address {"metamask_address":...}` with `metamask_address` (snake) accepted; `metamaskAddress` (camel) → 400 `At least one wallet address is required`.

## Trust Boundary
- Attacker controls `metamask_address` (stored in DB). Victim is admin or any user whose page does `fetch(/api/get-mobile-wallet)` → `innerHTML` / `dangerouslySetInnerHTML` without escaping. Plain `innerHTML="<script>"` inert, but `HTMLUpdateUtility`-style revival or direct `innerHTML = data.metamaskAddress` executes `onerror`/`onload`.
- Session API `/api/get-user-info` (POST) returns `is_paid:false, left_credits:0` — low-priv user can still store payload. Admin page `/en/admin` via `x-middleware-subrequest: /en/admin` still 200 with cookie (bypass probe timed out without, 307/400 differential on `Next-Action` header: `deleteUser`/`refundOrder` → 400 vs `transfer` → 307, leaking valid action names).

## Exploitability
- **Stored XSS candidate — not proven execution in prod admin render** (admin `/en/admin` with session timed out, `__next_f` 14, refund 60 hits but `fetch("/api/refund")` absent in 33 `_next/static/chunks/*.js` — only `RiRefund` icon). No `fetch("/api/update-wallet-address")` rendering evidence in chunks; weakness is API-level raw storage + raw reflection + no CSP + no `HttpOnly` check on `__Secure-authjs.session-token` (stealable via `document.cookie` if XSS fires).
- Labour: requires attacker account (signup `name` field required, `POST /api/auth/signup {email,password,name}` → 201) + login `POST /api/auth/callback/credentials` with `csrfToken`.

## Offline Lab PoC
- `vite@5.4` + `localStorage` simulation at `/tmp/everlyn-xss-lab/dist` served via `python3 -m http.server 5173`. File `index.html` shows side-by-side `textContent` (safe) vs `innerHTML` (vuln) with payloads `<img src=x onerror=alert(1)>`. Build `vite build` → 3.6k. Evidence: `dist/assets/index-CwmI3SvI.js 1.80k`.
- Validation: input field allowlist test `^0x[a-fA-F0-9]{40}$` — fix rejects non-hex.

## Fix (one-liners)
```diff
- // POST /api/update-wallet-address — no validation
+ if (!/^0x[a-fA-F0-9]{40}$/.test(metamask_address)) return res.status(400).json({error:"invalid address"});
+ // also validate keplrAddress similarly, reject < > " '

- // GET /api/get-mobile-wallet render
- el.innerHTML = data.metamaskAddress
+ el.textContent = data.metamaskAddress
+ // or DOMPurify.sanitize(data.metamaskAddress)

+ // headers
+ res.setHeader("Content-Security-Policy","default-src 'self'; script-src 'self'");
+ // cookie
+ Set-Cookie: __Secure-authjs.session-token=...; HttpOnly; Secure; SameSite=Lax
```

## References
- Session artifacts: `/tmp/everlyn_lab_cookie.txt` (1017), `/tmp/everlyn_lab_session.json`, `/tmp/everlyn_lab_orders.json`, `/tmp/everlyn_weakness_proof.json`, `/tmp/everlyn/admin.html` (66k, 12 RSC chunks), `x-middleware-subrequest` bypass still 200 for `/en/admin`.
- Related: Sonic FT rate-limited recon (`rate-limited-chain-recon` skill) — same session, throttled `eth_getLogs` 0.9s/100k, `eth_call` 0.6s, keeper DoS `0x3d515569`.
