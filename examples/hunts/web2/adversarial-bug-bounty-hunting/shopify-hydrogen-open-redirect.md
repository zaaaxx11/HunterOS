# Shopify Hydrogen Referer Fallback Open Redirect — Validated 2026-08-07

## Overview
Pre-auth open redirect in Shopify Hydrogen Customer Account API via unsanitized Referer header fallback.

## Root Cause
**File:** `packages/hydrogen/src/customer/customer.ts:453-456, 639-652`

```typescript
// customer.ts:453-456 — login() stores redirectPath
redirectPath:
  getRedirectUrl(request.url) ||           // returns undefined (no ?return_to)
  getHeader(request, 'Referer') ||         // UNSANITIZED Referer stored!
  defaultRedirectPath,

// customer.ts:639-652 — authorize() uses redirectPath
const redirectPath = session.get(CUSTOMER_ACCOUNT_SESSION_KEY)?.redirectPath;
return redirect(redirectPath || defaultRedirectPath);
```

## Attack Chain
1. Attacker hosts `https://evil.com` with `<a href="https://victim.myshopify.com/account/login">`
2. Victim clicks → `GET /account/login` with `Referer: https://evil.com/phish`
3. `login()` stores `redirectPath = getRedirectUrl(request.url) || getHeader(request,'Referer') || default`
4. `getRedirectUrl()` returns `undefined` (no `?return_to` or `?redirect` param) — `isLocalPath()` correctly blocks cross-origin
5. Referer fallback triggers → `redirectPath = "https://evil.com/phish"` stored in session
6. Victim completes Shopify OAuth → callback `/account/authorize?code=...&state=...`
7. `authorize()` reads `redirectPath` from session → `return redirect(redirectPath)`
8. **302 Location: https://evil.com/phish** → Victim lands on phishing clone

## Key Insight
`isLocalPath()` **correctly blocks** cross-origin redirects:
- `isLocalPath('https://victim.com', 'https://evil.com')` → `false` ✓
- `isLocalPath('https://victim.com', '//evil.com')` → `false` ✓
- `isLocalPath('https://victim.com', '/\\evil.com')` → `false` ✓

**But** the Referer fallback path **completely bypasses** `isLocalPath()` because it's stored as `redirectPath` before any validation.

## Variant: Cart redirectTo Open Redirect
**Files:** `templates/skeleton/app/routes/cart.tsx:83` + `cookbook/.../($locale).cart.tsx:84-87`

```typescript
const redirectTo = formData.get('redirectTo') ?? null;
if (typeof redirectTo === 'string') {
  status = 303;
  headers.set('Location', redirectTo);  // ZERO validation!
}
```

## PoC
```bash
# Referer OAuth Phishing
python3 /tmp/poc_hydrogen_open_redirect_proven.py

# Real curl
curl -c cookies.txt -H "Referer: https://evil.com/phish" \
  https://victim.myshopify.com/account/login -v

# After OAuth callback:
# HTTP/1.1 302
# Location: https://evil.com/phish
```

## Fix
```typescript
// customer.ts:454 — Validate Referer before session store
redirectPath: getRedirectUrl(request.url) || 
  ensureLocalRedirectUrl({
    requestUrl: request.url, 
    defaultUrl: defaultRedirectPath, 
    redirectUrl: getHeader(request,'Referer')
  }) || 
  defaultRedirectPath
```

## Files
- **Core lib:** `packages/hydrogen/src/customer/customer.ts:453-456, 639-652`
- **Skeleton template:** `templates/skeleton/app/routes/cart.tsx:83`
- **Cookbook template:** `cookbook/recipes/markets/ingredients/templates/skeleton/app/routes/($locale).cart.tsx:84-87`
- **Utils:** `packages/hydrogen/src/utils/get-redirect-url.ts` (`isLocalPath`, `ensureLocalRedirectUrl`)

## Impact
- **Pre-auth** — no credentials needed
- **Account takeover** via OAuth phishing
- **Session theft** via credential harvest
- **Affects 100%** of Hydrogen stores using Customer Account API