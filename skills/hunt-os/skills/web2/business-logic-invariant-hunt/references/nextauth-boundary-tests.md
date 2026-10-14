# NextAuth / Auth.js Boundary-Test Checklist (class-level)

Canonical 12-probe set (a–l) for any SaaS behind NextAuth.js / Auth.js. Run with
`curl -4 -sk -i` against `https://TARGET`. Working dir `/tmp/<target>_auth/`,
log every request line + status + first 300 chars of body.

## Probes

(a) **Enumeration** — `GET /api/auth/{session,csrf,providers,signin}`. Note which
    providers exist (google, github, email, credentials). `/api/auth/providers`
    returning a JSON map is the fingerprint that NextAuth is in play.

(b) **OAuth callback confusion** — `GET /api/auth/callback/{google?code=x&state=x&error=access_denied,
    credentials,email?token=x,oauth}`. Record HTTP code + error message. A 200/
    302 on a nonsense provider name or an empty `error=` handler is Discovery.

(c) **Cookie-name variants + alg=none JWT** — try `next-auth.session-token` and
    `__Secure-next-auth.session-token`. Forge header `{"alg":"none"}` with any
    payload, `GET /api/auth/session` with it. Must return `{"user":null}` /
    401 / empty `{}` and MUST NOT accept. Any acceptance = CRITICAL.

(d) **CSRF on auth POSTs** — `POST /api/auth/signin/email` and
    `POST /api/auth/callback/credentials` WITHOUT the `next-auth.csrf-token`
    cookie AND without a matching `csrfToken` form field. NextAuth default is
    to 302→`/api/auth/signin?csrf=true` or 400; acceptance = CSRF bypass.

(e) **Open redirect via callbackUrl** — probe
    `/api/auth/signin?callbackUrl={//evil.com,https://evil.com,/\\/evil.com}`
    and `/api/auth/signout?callbackUrl=//evil.com`. Default NextAuth
    `redirect()` callback restricts to same-origin; a 302 Location pointing at
    `evil.com` = EXPLOITABLE open-redirect.

(f) **Host-header poisoning on email link** — `POST /api/auth/signin/email`
    with `X-Forwarded-Host: evil.com` (and `Host: evil.com` variant). Inspect
    JSON response and Set-Cookie; if the magic-link host is taken from
    `X-Forwarded-Host`, the outbound verification email points at attacker
    infra. Capture via webhook.site when in scope.

(g) **Email OTP rate limit** — 5 distinct `POST /api/auth/signin/email` from
    one IP within 5s. Note codes; a 429 or `Retry-After` header = BLOCKED.
    All 200s = no per-IP throttle → OTP spam / enumeration vector.

(h) **Locale/middleware bypass on admin** — probe `/en/admin`, `/zh/admin/orders`,
    `/admin/users`, `/api/admin/{users,orders,refund,invite,credits}`. Record
    all status codes + 100-char body prefix. Locale-prefixed 200 where bare
    path is 307/401 = middleware bypass (CVE-2025-29927 pattern).

(i) **Method tampering** — `TRACE`, `OPTIONS`, `PUT` on `/admin` and
    `/api/auth/session`. TRACE echoing headers (XPST), PUT store/replace,
    OPTIONS leaking `Allow: *` are all Discovery at minimum.

(j) **Version/stack leak via malformed JSON** — `POST /api/auth/signin` with
    body `{not-json` and no/wrong `Content-Type`. 500 with stack trace,
    `next-auth@X.Y.Z` string, or `PrismaClientValidationError` = version
    disclosure (EXPLOITABLE as recon).

(k) **Provider map leak** — `/api/auth/providers` returns the full strategy
    list. Presence of `credentials` provider implies username/password auth is
    enabled (spray target). Presence of `email` implies passwordless magic
    link (OTP bruteforce surface).

(l) **RSC-specific auth state leak** — `GET /admin` with header `RSC: 1` (or
    query `?_rsc=1`). Next.js App Router returns flight payload; look for
    `NEXT_REDIRECT` vs `No access` vs partial content. Different payload for
    authed vs unauth = auth-only content disclosure.

## Verdicts

- **EXPLOITABLE** — (c) accepted alg=none, (d) accepted missing-CSRF POST,
  (e) 302→evil.com, (f) Host-header-controlled outbound link, (h) locale
  bypass returns content, (l) flight payload reveals user data unauth.
- **BLOCKED** — standard NextAuth rejection (`302 /api/auth/signin?csrf=true`,
  401 `{"error":"..."}`, mismatch cookie, 429 rate-limit).
- **DISCOVERY** — provider list, version leak, method enumeration, distinct
  error strings. Useful for follow-up, not a finding yet.
- **NEEDS-AUTH** — endpoint live but session-gated. Record shape so authed
  re-test can pick up.

## Pitfalls

- Always `curl -4` — Cloudflare IPv6 hangs.
- The auth middleware's 307 to `/api/auth/signin` is a NEEDS-AUTH signal, NOT
  a BLOCKED verdict on the probe.
- Locale bypass test needs BOTH `/en/<path>` and `/<path>` in the same run —
  one without the other is meaningless.
- `alg=none` forged JWT MUST be tested against `/api/auth/session` specifically;
  testing it against an arbitrary API route proves nothing about session
  validation.
