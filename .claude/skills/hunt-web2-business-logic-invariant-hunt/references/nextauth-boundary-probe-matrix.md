# NextAuth / Auth.js Boundary-Test Checklist

Class-level reference for the recurring "auth boundary wave" brief: an operator
hands you a target running NextAuth/Auth.js and asks you to probe each authn/authz
boundary with curl + log status + full body + verdict per item.

Use alongside `authjs-v5-endpoint-fingerprints.md` (what the endpoints look like).
This file is the *probe matrix* — what to actually fire.

## Pre-flight

- Resolve with IPv4 only: `curl -4` on every request. Note the edge IP in the report.
- Working dir: `mkdir -p /tmp/<target>_auth && cd` there. One `run()` shell helper
  tees every curl + status + body to a single report file.
- Fingerprint the SPA catch-all FIRST (see parent SKILL.md "Pre-flight") so a 200
  HTML shell on `/api/auth/whatever` is not misread as a real endpoint.

## Probe matrix (12 canonical blocks, a–l)

Verdict rubric per block: EXPLOITABLE | BLOCKED | DISCOVERY (the brief's own
labelling — `DISCOVERY` = enumeration value only, no boundary crossed).

| # | Block | What to fire | What proves what |
|---|-------|--------------|------------------|
| a | Endpoint enumeration | `GET /api/auth/{session,csrf,providers,signin}` | `providers` JSON lists exactly which strategies are configured (google / github / email / credentials). This is the single highest-value DISCOVERY row — it scopes everything downstream. |
| b | OAuth callback confusion | `GET /api/auth/callback/{google?code=x&state=x&error=access_denied, credentials, email?token=x, oauth}` | Record each distinct error JSON. A callback that redirects instead of erroring on garbage input may be mishandling state. `error=access_denied` should short-circuit before token exchange. |
| c | Cookie name variants + forged JWT | Try both `next-auth.session-token` and `__Secure-next-auth.session-token`. Craft a JWT with `header.alg=none`, empty signature, claim `{"sub":"1","email":"a@b"}`; attach as cookie to `GET /api/auth/session`. | MUST fail secure: any response containing the forged identity = EXPLOITABLE. `null` session = BLOCKED. Note which cookie name the server actually sets. |
| d | CSRF on mutation endpoints | `POST /api/auth/signin/email` with NO `X-Auth-CSRF-Token`/csrf cookie, then `POST /api/auth/callback/credentials` likewise. | 302/200 acceptance without CSRF = EXPLOITABLE. 403/400 MissingCSRF = BLOCKED. Capture the exact error body. |
| e | Open redirect via callbackUrl | `GET /api/auth/signin?callbackUrl=//evil.com`, `?callbackUrl=https://evil.com`, `?callbackUrl=/\/evil.com`, plus `/api/auth/signout?callbackUrl=…` variants. | NextAuth ≥ v4.10 blocks absolute off-host URLs by default; only allow-listed hosts redirect. Record each `Location:` header verbatim. Any `Location: https?://evil.com` = EXPLOITABLE. |
| f | Host header / X-Forwarded-Host | `curl -H "X-Forwarded-Host: evil.com" $T/api/auth/signin/email` (and a POST variant). | If the response body or `Location:` header reflects `evil.com`, password-reset / magic-link poisoning is in scope. Follow up with webhook.site endpoint as the `callbackUrl` or in the `Host`/`X-Forwarded-Host` to observe outbound traffic — but only after confirming reflection locally. |
| g | Email OTP rate limit | 5 `POST /api/auth/signin/email` from same IP within 5 s, distinct addresses. | 429 on any = rate-limited (BLOCKED but record threshold). All 200/302 = EXPLOITABLE (email-bombing / OTP brute-force primitive). Note whether the limiter is per-IP or per-recipient. |
| h | Locale / path-prefix bypass | `GET /{en,zh}/admin`, `/admin/users`, and the unauthed `/api/admin/{users,orders,refund,invite,credits}` set. Record all status codes + first 100 chars of each body. | Divergent status between `/en/admin` and `/api/admin/users` hints middleware ordering bugs. Any admin body returned unauth = EXPLOITABLE. 401/403/307 uniformly = BLOCKED. |
| i | Method tampering | `TRACE`, `OPTIONS`, `PUT` on `/admin` and `/api/auth/session`. | TRACE 200 with reflected headers = minor finding (XST). OPTIONS leaking allowed-methods is DISCOVERY. PUT that mutates session state = EXPLOITABLE. |
| j | Version/stack leak via malformed JSON | `POST /api/auth/signin` with `Content-Type: application/json` and body `{not json`. | Stack traces, `next-auth@x.y.z` strings, file paths in the response = DISCOVERY-leak. Generic 400 = BLOCKED. Cross-reference any disclosed version against the Auth.js advisory list. |
| k | Provider strategy leak | Same `GET /api/auth/providers` as (a) — call it out separately because the operator reports it as its own row. | Confirms strategies; pair with (b) — a listed provider whose callback errors differently (302 vs 400) is a soft confusion signal. |
| l | React Server Components probe | `GET /admin` with header `RSC: 1` (and optionally `?_rsc=<random>`). | RSC payload may render server-only auth state that the HTML shell hides. Look for `NEXT_REDIRECT` vs `"No access"` vs actual data in the RSC stream. Divergence between RSC and HTML responses on the same path = DISCOVERY, possibly EXPLOITABLE if data leaks. |

## Verdict rubric (this brief's variant)

- **EXPLOITABLE** — you crossed a boundary: forged session accepted, CSRF-less
  mutation accepted, off-host redirect issued, unauth admin data returned,
  X-Forwarded-Host reflected into a link, OTP limiter absent.
- **BLOCKED** — middleware / NextAuth default rejected the probe cleanly.
  Capture the exact error; "what the block looks like" is itself useful for
  the follow-up wave.
- **DISCOVERY** — enumeration outcome with no boundary crossed: provider list,
  reflected `Allow:` header, version strings, distinct errors per provider.
  DISCOVERY rows still go in the final report.

## Final report shape

End with a "Top 5 bypass leads" section ranked by:
1. Anything EXPLOITABLE in the matrix above.
2. DISCOVERY rows that chain (e.g. version-leak + a known Auth.js CVE,
   RSC leak hinting at middleware-order issues, provider-callback
   asymmetry).
3. BLOCKED rows whose error shape differs from sibling probes (asymmetry =
   implementation branching = likely bug surface).

## Pitfalls specific to this brief

- **`error=access_denied` short-circuit** — legit OAuth providers return this
  *before* state validation; do not report a 302 on `access_denied` as a
  state-confusion finding without a second probe that omits `error`.
- **NextAuth v4 vs Auth.js v5 cookie names** — v5 uses `authjs.session-token`,
  not `next-auth.session-token`. If `next-auth.session-token` is set and
  accepted, the target is v4 (pin version, check advisory list). If
  `__Secure-authjs.session-token` is set, it's v5-behind-HTTPS.
- **RSC header case** — header name is exactly `RSC: 1` (Next.js router). The
  `?_rsc=` query param is cache-bust only, not an alternative signal.
- **Webhook.site follow-up for (f)** — only fire external callbacks after you
  have local response evidence that Host/X-Forwarded-Host is reflected
  somewhere. Firing blind webhooks on every probe just feeds someone else's
  telemetry.
- **Rate-limit probe (g) burns budget** — run it LAST among the boundary
  probes so 429s from (g) don't contaminate the still-pending blocks.
