# NextAuth / Auth.js boundary-testing checklist

Derived from a real "WAVE 1 AGENT 2 — DYNAMIC AuthN/AuthZ boundary testing" brief
against a Next.js SaaS. Reusable verbatim whenever an operator hands a numbered
(a)–(l) auth-probe list against a NextAuth-backed target.

Convention: working dir `/tmp/<target>_auth`, log every request + full response
body + status to `report.txt`. Always `curl -4 -sk -i`.

## (a) Provider enumeration
```bash
for p in session csrf providers signin; do
  curl -4 -sk -i "$B/api/auth/$p" | tee -a report.txt
done
```
Providers JSON tells you which flows are real: `google`, `github`, `email`,
`credentials`. Anything listed in `/api/auth/providers` is attack surface;
anything absent is not worth probing.

## (b) OAuth callback confusion
```bash
curl -4 -sk -i "$B/api/auth/callback/google?code=x&state=x&error=access_denied"
curl -4 -sk -i "$B/api/auth/callback/credentials"
curl -4 -sk -i "$B/api/auth/callback/email?token=x"
curl -4 -sk -i "$B/api/auth/callback/oauth"
```
Note error codes and whether the server leaks `state` validation details.

## (c) Cookie-name sniffing + forged JWT
Cookie variants to try: `next-auth.session-token`, `__Secure-next-auth.session-token`,
`<__Host->` variants. Forge a JWT with `header.alg=none` and submit against
`/api/auth/session` — secure systems MUST reject (record exact status + body).

## (d) CSRF gate
```bash
curl -4 -sk -i -X POST "$B/api/auth/signin/email" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'email=a@b.c'           # NO csrf cookie, NO csrfToken field
curl -4 -sk -i -X POST "$B/api/auth/callback/credentials" \
  --data 'username=u&password=p' # NO csrf
```
Both must reject with `400/403` and an error mentioning CSRF / missing token.

## (e) Open-redirect matrix
```bash
for cb in '//evil.com' 'https://evil.com' '/\/evil.com' '/\\evil.com' \
          '%2f%2fevil.com' '///evil.com'; do
  curl -4 -sk -i "$B/api/auth/signin?callbackUrl=$cb" | tee -a report.txt
done
curl -4 -sk -i "$B/auth/signout?callbackUrl=https://evil.com"
```
Look at `Location:` header — anything that rounds to an off-origin URL is a hit.

## (f) Host header poisoning
```bash
curl -4 -sk -i -X POST "$B/api/auth/signin/email" \
  -H 'X-Forwarded-Host: evil.com' \
  -d 'email=a@b.c&csrfToken=<fresh>'
```
Read the response body — some setups echo the host into generated magic links.
For real capture, point to a webhook.site URL via the email field later.

## (g) Rate limit probe
5 distinct `POST /api/auth/signin/email` from same IP within 5s. Watch for 429,
`Retry-After`, or monotonically increasing latency. No 429 = DISCOVERY (flag for
later brute-force follow-up).

## (h) Locale/path auth bypass — parallel sweep
Probe `/en/admin`, `/zh/admin/orders`, `/admin/users`, `/api/admin/users`,
`/api/admin/orders`, `/api/admin/refund`, `/api/admin/invite`, `/api/admin/credits`.
Record `(status, first-100-chars)`. Statuses >200 with non-shell body = signal;
all-200-shell-HTML = Next.js catch-all, no auth data.

## (i) Method tampering
`TRACE`, `OPTIONS`, `PUT` against `/admin` and `/api/auth/session` — record
`Allow:` headers and whether TRACE echoes (rare on modern Next, but cheap).

## (j) Error-stack leak
```bash
curl -4 -sk -i -X POST "$B/api/auth/signin" \
  -H 'Content-Type: application/json' -d '{bad json'
```
`500 + stack trace` = DISCOVERY. `400 + generic` = BLOCKED.

## (k) Strategy leak
`/api/auth/providers` already enumerates providers; cross-reference anything
found in JS chunks (e.g. `sendVerificationRequest`, custom `authorize()`).

## (l) RSC-specific leak
```bash
curl -4 -sk -i "$B/admin" -H 'RSC: 1' -H 'Next-Router-State-Tree: %5B%22%22%5D'
```
Compare payload to plain GET. RSC sometimes discloses server-component data
(or `NEXT_REDIRECT` internals) the HTML shell hides.

## Reporting shape

Per item, log:

```
### (x) <name>
**Command:** ...
**Response status:** ...
**Body (100 chars):** ...
**VERDICT:** EXPLOITABLE | BLOCKED | DISCOVERY
```

End with a prioritized list of the 5 most promising bypass leads, ranked by
exploitability signal in captured responses — never ranked by vibe.
