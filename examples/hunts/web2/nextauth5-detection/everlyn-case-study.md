# Everlyn.ai — Auth.js v5 Case Study (2026-07-29)

## Target Profile
- **URL**: https://everlyn.ai
- **Stack**: Next.js App Router + Auth.js v5 + Cloudflare + Vercel
- **Pricing**: Starter $9.99/mo / Standard $34.99/mo / Pro $94.99/mo (Stripe + Crypto)
- **Plugins**: Stripe.js, GrazChain, WalletConnect, Plausible Analytics, TailwindCSS
- **Multi-locale**: en/zh/ja/ko/de/fr/it/es/pt
- **Backend**: All server-side (no DB/API keys found in JS bundles)

## Auth Detection Sequence (from live probe)

### Step 1: Version = Auth.js v5
```bash
curl -4s -c /tmp/cookies.txt "https://everlyn.ai/api/auth/csrf"
# Cookies set:
#   __Host-authjs.csrf-token  (token|hmac format)
#   __Secure-authjs.callback-url
# → Auth.js v5 (not NextAuth v4)
```

### Step 2: Providers
```bash
curl -4s "https://everlyn.ai/api/auth/providers"
# Returns:
#   credentials (email+password)
#   google (oidc)
#   github (oauth)
```

### Step 3: Email magic link — WORKING
```bash
CSRF_COOKIE=$(mktemp)
curl -4s -c "$CSRF_COOKIE" "https://everlyn.ai/api/auth/csrf" > /tmp/c.json
TOKEN=$(python3 -c "import json;print(json.load(open('/tmp/c.json'))['csrfToken'])")
curl -4s -o /dev/null -w "%{http_code} → %{redirect_url}\n" \
  -b "$CSRF_COOKIE" -X POST "https://everlyn.ai/api/auth/signin/email" \
  -d "csrfToken=$TOKEN&email=test@example.com"
# → 302 → /api/auth/signin (no error) = Email provider ACTIVE
```

### Step 4: Register endpoint — PATCHED
```bash
curl -4s -w "HTTP %{http_code}\n" -X POST "https://everlyn.ai/api/auth/register" \
  -H "Content-Type: application/json" -d '{"email":"t@t.com","password":"Test12345!"}'
# → HTTP 400 "Bad request."
# Different from earlier scan (2026-07-28) which returned 201
```

### Step 5: Admin route check
```bash
for p in /admin/users /admin/orders /admin/dashboard; do
  echo -n "$p → "
  curl -4s -o /dev/null -w "HTTP %{http_code} size:%{size_download}b\n" "https://everlyn.ai$p"
done
# /admin/users → HTTP 200 46191b (EXISTS, gate redirects)
# /admin/orders → HTTP 200 77288b (EXISTS, gate redirects)
# /admin/dashboard → HTTP 404 6749b (DOESN'T EXIST)

# RSC gate check
curl -4s "https://everlyn.ai/admin" | grep -oP '5:E\{[^}]*\}|5:I\[[0-9]+'
# → 5:E{"digest":"NEXT_REDIRECT;replace;/auth/signin;307;"}  (GATED)
```

### Step 6: Open redirect test — SAFE
```bash
curl -4s -L -o /dev/null -w "%{http_code} → %{url_effective}\n" \
  "https://everlyn.ai/api/auth/signin?callbackUrl=//evil.com"
# → 200 → https://everlyn.ai/auth/signin?callbackUrl=https%3A%2F%2Feverlyn.ai%2F%2Fevil.com
# Properly sanitized — same-domain only
```

### Step 7: Hidden API endpoints from JS bundles
```bash
grep -rohE '"/api/[a-z_/]+"' chunks/*.js | sort -u
# /api/checkout
# /api/get-mobile-wallet
# /api/register
```

## Admin Route Map (Confirmed)
| Route | Status | Notes |
|-------|--------|-------|
| `/admin` | 200, gated | (admin)/admin layout |
| `/admin/users` | 200, gated | 46KB page with users table component |
| `/admin/orders` | 200, gated | 77KB page with orders table component |
| `/admin/dashboard` | 404 | Doesn't exist |
| `/admin/api-keys` | 404 | Could be removed/chunk not loaded |
| `/admin/refunds` | 404 | Could be removed |

## JS Bundle Secrets Scan — NEGATIVE
- No NEXT_PUBLIC_* values leaked (stripped by build)
- No Stripe keys (`sk_live`, `pk_live`)
- No DB connection strings (supabase, mongodb, postgresql)
- No crypto wallet private keys
- Only crypto addresses found: library constants (WalletConnect, protobuf)

## Key Observations
1. **Email provider functional** → could be used for enumeration/magic link flooding
2. **Registration patched** → signup endpoint disabled server-side since 2026-07-28
3. **Admin middleware enforced** → RSC shows NEXT_REDIRECT, not page content
4. **No injection vectors found** → 400 on /api/auth/register for all formats
5. **No JWT secret leak** → bundles are clean
6. **No middleware bypass** → x-middleware-subrequest doesn't bypass
7. **CSRF signed** → `token|hmac` format — can't forge without AUTH_SECRET

## Links
- Live target: https://everlyn.ai
- GitHub repo: https://github.com/Everlyn-Labs/Everlyn-1 (AI video research, not web app source)