# Auth.js v5 (NextAuth v5) Endpoint Fingerprints — Verified Live on everlyn.ai (2026-07)

Condensed knowledge bank for the FIRST 5 minutes of probing any Next.js + Auth.js
target during an invariant/auth hunt. Do not re-derive these values — they are
stable Auth.js v5 defaults and hold unless the operator overrides them.

## Cookie prefix tells you the major version

| `Set-Cookie` name seen | Implication |
|---|---|
| `__Host-authjs.csrf-token` | **Auth.js v5** (the NextAuth rewrite). Default CSRF cookie. Value = `<token>%7C<hmac>` — left of the `%7C` is the token, right is the HMAC proof of issuance. |
| `__Secure-authjs.callback-url` | Auth.js v5 callback allowlist cookie, set to the app's own origin by default. |
| `__Host-next-auth.csrf-token` | Legacy NextAuth v4. Different error page + callback handling. |

Fingerprint rule: any `authjs.*` cookie on the wire means Auth.js v5 defaults apply.

## Endpoint inventory (GET, `curl -4` mandatory on Cloudflare-fronted Next.js)

```bash
curl -4 -sS -i https://TARGET/api/auth/session
curl -4 -sS -i https://TARGET/api/auth/csrf
curl -4 -sS -i https://TARGET/api/auth/providers
curl -4 -sS -i https://TARGET/api/auth/signin
```

Verbatim expected results:

```
/session    -> HTTP 200, body: null                      (anonymous session)
/csrf       -> HTTP 200, body: {"csrfToken":"<hex64>"}   + sets __Host-authjs.csrf-token cookie
/providers  -> HTTP 200, JSON map of configured providers
/signin     -> HTTP 200 HTML (default Auth.js signin page)
Locale prefixes (en/id/zh...) on /signin all 307 -> /api/auth/signin (consistent; no locale bypass at this layer)
```

If `/providers` returns ONLY `credentials`, the OAuth-callback probe step degenerates
to 400-stub confirmation (below) — do NOT waste time trying to coerce Google/GitHub
error messages out.

## Callback stubs for unconfigured providers

Hitting a callback for a provider not present in `/providers` still routes through
Auth.js and returns the default error, NOT a 404:

```bash
GET /api/auth/callback/google?code=fake&state=fake  -> HTTP 400 (Auth.js error page)
GET /api/auth/callback/github?code=fake             -> HTTP 400
GET /api/auth/callback/credentials                  -> HTTP 400 (GET not allowed; POST-only)
```

`/providers` is the ONLY authoritative source for "is this provider configured".
A 400 on `/callback/<name>` tells you nothing about partial/mis-configuration; a 404
on a non-auth path tells you the route doesn't exist.

## CSRF enforcement on POST /api/auth/callback/credentials — the two-token rule

Auth.js v5 requires BOTH:

1. The `__Host-authjs.csrf-token` cookie, AND
2. A form field `csrfToken=<token>` whose value matches the LEFT half of the cookie
   (before `%7C`). The right half is the HMAC of `token + secret`.

Failure mode is consistent:

```
HTTP/2 302
location: /api/auth/signin?error=MissingCSRF
```

Validated matrix on everlyn.ai:

| Request shape | Result |
|---|---|
| POST with no cookie, no csrfToken field | 302 -> MissingCSRF |
| POST with `__Host-authjs.csrf-token` cookie, no csrfToken field | 302 -> MissingCSRF |
| POST with cookie + csrfToken field (matching) | proceeds — see x-auth-return-redirect below |
| POST with cookie + WRONG csrfToken | 302 -> MissingCSRF (same as missing) |

CSRF IS enforced by default. There is no missing-CSRF finding here unless an
operator explicitly disables the check. The point of probing is clean negative
confirmation, not a vuln hunt at this step.

## The quiet `x-auth-return-redirect` header

When `authorize()` rejects credentials, Auth.js v5 does NOT return 401 — it 302s
through a redirect chain. The intermediate response carries:

```
x-auth-return-redirect: /
```

Reading this correctly:
- The app customized `redirectTo`/error swallowing so failed logins land on `/`
  instead of surface `error=CredentialsSignin` back to the caller.
- Customization near the auth flow means custom code exists. Grep the JS bundle
  for `authorize`, `jwt`, `session` callbacks — that's where role-escalation /
  mass-assignment invariants usually live.

## IPv6 pitfall (already in bug-bounty-agent SKILL.md, restated — it bit us again)

Plain `curl` against a Cloudflare-fronted Next.js host can IPv6-flap mid-run and
give nondeterministic responses. Always `curl -4`. Even better, define an alias
for the session.

## What NOT to overclaim from Steps 1–3 of the playbook

- `providers: { credentials: ... }` proves the route exists. It does NOT prove
  arbitrary user signup or that `authorize()` accepts your input. Bundle analysis
  is the next step.
- 400 on `/api/auth/callback/google` means Google OAuth is NOT configured. It is
  not "partially broken OAuth".
- `MissingCSRF` 302 is expected hardening, not a finding. Report it as
  defense-in-depth confirmed, not a bug.
- Locale 307s from `/en/signin` → `/api/auth/signin` are Next.js i18n middleware
  normalization, not an open-redirect surface.
