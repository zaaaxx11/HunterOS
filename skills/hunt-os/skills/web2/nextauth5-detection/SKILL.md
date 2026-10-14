---
name: nextauth5-detection
description: "detect NextAuth v5 deployments and version-specific weaknesses"
metadata:
  version: 1.0.0
  hermes:
    tags: [security, auth, nextjs, nextauth, authjs, web2, bug-bounty]
    category: security
---

# Auth.js v5 / NextAuth Admin Takeover Detection

## When to Use
- Target is a Next.js app with Auth.js v5 or NextAuth v4
- Admin panel routes found via RSC payload
- Goal: identify version, test auth bypass, or find misconfigurations

## Version Detection (Do First)
**Auth.js v5** (successor to "NextAuth v5"):
- Cookies: `__Host-authjs.csrf-token` (format: `token|hmac_signature`)
- Session: `__Secure-authjs.session-token`
- Packages: `@auth/*`
- Email provider endpoint: `/api/auth/signin/email`

**NextAuth v4**:
- Cookies: `next-auth.csrf-token`
- Session: `next-auth.session-token`
- Packages: `next-auth`

```bash
curl -4s -c /tmp/cookies.txt "https://target.com/api/auth/csrf"
cat /tmp/cookies.txt  # Check prefix → version
```

## Probe Sequence (Pre-Auth)

### 1. Identify providers
```bash
curl -4s "https://target.com/api/auth/providers"
```

### 2. Test email magic link
```bash
CSRF_COOKIE=$(mktemp)
curl -4s -c "$CSRF_COOKIE" "https://target.com/api/auth/csrf" > /tmp/csrf.json
TOKEN=$(python3 -c "import json,sys;print(json.load(sys.stdin)['csrfToken'])" < /tmp/csrf.json)
curl -4s -o /dev/null -w "HTTP %{http_code} → %{redirect_url}\n" \
  -b "$CSRF_COOKIE" -X POST "https://target.com/api/auth/signin/email" \
  -d "csrfToken=$TOKEN&email=test@example.com"
# → /api/auth/signin (no error) = Email provider functional
```

### 3. Register endpoint discovery
```bash
for ep in "/api/auth/signup" "/api/auth/register"; do
  echo -n "$ep → "
  curl -4s -w "HTTP %{http_code}\n" -X POST "https://target.com$ep" \
    -H "Content-Type: application/json" -d '{"email":"t@t.com","password":"Test12345!"}'
done
# 201 = open registration (CRITICAL)
# 400 = exists but patched/needs specific format
# 404 = not a route
```

### 4. RSC auth gate check
```bash
curl -4s "https://target.com/admin" | grep -oP '5:E\{[^}]*\}|5:I\[[0-9]+' | head -1
# 5:E{NEXT_REDIRECT...} = gated
# 5:I[xxxx = bypassed

# Also check route existence:
curl -4s "/admin/users" -o /dev/null -w "HTTP %{http_code} size:%{size_download}b\n"
# 200 >20KB = route exists (even if gated by middleware)
# 404 ~6.7KB = doesn't exist
```

### 5. Hidden endpoints from JS bundles
```bash
grep -rohE '"/api/[a-z_/]+"' chunks/*.js | sort -u
# Common: /api/checkout, /api/get-mobile-wallet, /api/register, /api/auth/signup
```

## CSRF Cookie Jar Pattern (Auth.js v5)
```bash
CSRF_COOKIE=$(mktemp)
curl -4s -c "$CSRF_COOKIE" "https://target.com/api/auth/csrf" > /tmp/csrf.json
TOKEN=$(python3 -c "import json,sys;print(json.load(sys.stdin)['csrfToken'])" < /tmp/csrf.json)
curl -4s -b "$CSRF_COOKIE" "https://target.com/api/auth/callback/credentials" \
  -X POST -d "csrfToken=$TOKEN&email=admin@target.com&password=admin123" \
  -o /tmp/resp.html
```

## Response Code Cheat Sheet (Auth.js v5)
| HTTP | Location / Body | Meaning |
|------|----------------|---------|
| 302 → `/auth/signin?error=CredentialsSignin` | Bad creds OR user doesn't exist |
| 302 → `/` + `Set-Cookie: __Secure-authjs.session-token` | **LOGIN SUCCESS** |
| 302 → `/auth/signin?error=MissingCSRF` | CSRF cookie missing/mismatch |
| 302 → `/api/auth/signin` (no error) | Email magic link accepted |
| 200 + `null` | `/api/auth/session` → unauth |
| 200 + `{"user":{...}}` | `/api/auth/session` → authed |
| 200 + HTML (40-80KB) | Admin page rendered — check for data |
| 400 + `"Bad request."` | `/api/auth/register` exists but patched |
| RSC `5:E{NEXT_REDIRECT...}` | Unauthenticated — gated |
| RSC `5:I[xxxx` | Admin component rendered — BYPASS |

## Pitfalls
- **`curl -4` IS REQUIRED** for Cloudflare-backed hosts — IPv6 fails silently
- Auth.js v5 CSRF tokens are **signed** (`token|hmac`) — cannot be forged without `AUTH_SECRET`
- `CredentialsSignin` error is **same for all emails** — no user enumeration
- RSC `NEXT_REDIRECT` still contains data in body — **always grep the full response**
- Keep agent scope to **3-5 objectives max** — 15+ per agent wastes tokens
- Registration returning 400 doesn't mean the endpoint is gone — may be disabled server-side

## Reference Files
- `examples/hunts/web2/nextauth5-detection/everlyn-case-study.md` — Full Everlyn.ai probe results from 2026-07-29 (post-patch snapshot) including admin route map, JS bundle secrets scan, and patch timeline