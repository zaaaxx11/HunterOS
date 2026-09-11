# NextAuth.js Security Findings — loopin.network Case Study (2026-08-29)

## Overview
This reference captures NextAuth.js-specific security findings discovered during the loopin.network audit. These patterns are reusable for any NextAuth-protected application.

## Finding 1: Email Enumeration via `json=true`

**Severity: HIGH**

NextAuth's `/api/auth/signin/email` endpoint returns **different JSON responses** based on account existence when `json=true` is in the request body.

### Evidence
```bash
# Registered email
curl -X POST https://www.loopin.network/api/auth/signin/email \
  -d "email=admin@loopin.network&csrfToken=<token>&callbackUrl=%2F&json=true"
# Response: {"url":"/api/auth/verify-request?provider=email&type=email"}

# Unregistered email
curl -X POST https://www.loopin.network/api/auth/signin/email \
  -d "email=notareal12345xyz@loopin.network&csrfToken=<token>&callbackUrl=%2F&json=true"
# Response: {"url":"/api/auth/error?error=EmailSignin"}
```

### Impact
- User directory enumeration (confirmed registered: `admin@loopin.network`, `support@loopin.network`)
- Magic link spam (DoS to user mailbox)
- Account takeover if email is compromised (phishing, insider, mailbox hack)

### Critical Note
**Without `json=true`**, both emails return identical HTML → false BLOCKED verdict. This caused a CDC round contradiction (Round 1 CONFIRMED, Round 2 BLOCKED). Direct verification proved Round 1 correct.

### Hunt Pattern
```bash
# Extract CSRF token first
CSRF=$(curl -s https://<target>/api/auth/csrf | jq -r .csrfToken)

# Test email enumeration
curl -X POST https://<target>/api/auth/signin/email \
  -d "email=<target>&csrfToken=$CSRF&callbackUrl=%2F&json=true"
```

## Finding 2: Open Redirect via `callbackUrl`

**Severity: MEDIUM**

The `callbackUrl` query parameter is **reflected verbatim** into a hidden `<input name="callbackUrl">` on the NextAuth signin page without allowlist validation.

### Evidence
```bash
curl -s 'https://www.loopin.network/api/auth/signin?callbackUrl=https://evil.com' \
  -A 'Mozilla/5.0' | grep 'callbackUrl'
# Output: <input type="hidden" name="callbackUrl" value="https://evil.com" />
```

### Subdomain Tri Accepted
```bash
curl -s 'https://www.loopin.network/api/auth/signin?callbackUrl=https://www.loopin.network.evil.com' \
  -A 'Mozilla/5.0' | grep 'callbackUrl'
# Output: <input type="hidden" name="callbackUrl" value="https://www.loopin.network.evil.com" />
```

### Impact
- Phishing: User authenticates, then redirected to evil.com
- Combined with email enum: Targeted phishing with magic link

### Critical Note
Some CDC rounds claimed "server-side validation" — this is **WRONG**. Direct verification proves the reflection. The redirect happens after auth completes (the form submits to `/api/auth/signin/email` which processes the hidden `callbackUrl` field).

### Hunt Pattern
```bash
# Test open redirect
curl -s '<target>/api/auth/signin?callbackUrl=https://evil.com' \
  -A 'Mozilla/5.0' | grep -o 'callbackUrl[^<]*'
```

## CDC Contradiction Lesson

**Round 1** (direct probing): Email enum CONFIRMED, open redirect CONFIRMED
**Round 2** (4-agent CDC): Email enum BLOCKED, open redirect BLOCKED

**Root cause**: Round 2 agents tested without `json=true` parameter → got identical HTML → wrongly concluded BLOCKED.

**Resolution**: Direct verification with exact parameters proved Round 1 correct.

**Lesson**: When CDC rounds contradict, run verbatim reproduction of the original finding. Do not accept agent confidence over byte-for-byte evidence.

## NextAuth Attack Surface Checklist

| Endpoint | Test | Expected if Secure |
|----------|------|-------------------|
| `/api/auth/csrf` | GET | 200, returns token (by design) |
| `/api/auth/providers` | GET | 200, returns provider list (by design) |
| `/api/auth/session` | GET | 200 `{}` (unauth) |
| `/api/auth/signin/email` | POST with `json=true` | **Same response for all emails** (no enum) |
| `/api/auth/signin?callbackUrl=` | GET | **Validated/rejected** (no reflection) |
| `/api/auth/callback/email` | GET with invalid token | 302 → error page (no token leak) |
| `/api/auth/verify-request` | GET | HTML page (no token in body) |

## Related Patterns

- `references/wyze-signature-forging-2026-08.md` — Wyze signature forging, exposed HMAC secrets, post-auth open redirects
- `references/fastapi-jwt-auth-redteam.md` — JWT auth red-team, error oracles, dual-stack diff