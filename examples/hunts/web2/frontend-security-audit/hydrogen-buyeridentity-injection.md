# Hydrogen Cart buyerIdentity Injection

## Finding
`createCartHandler()` in `@shopify/hydrogen` merges `buyerIdentity` from handler options **then** from call arguments, allowing any caller to override sensitive buyer identity fields.

## Vulnerable Code
**File:** `hydrogen/src/packages/hydrogen/src/cart/createCartHandler.ts:293-295`
```typescript
args[0].buyerIdentity = {
  ...buyerIdentity,           // handler default (from createCartHandler options)
  ...args[0].buyerIdentity,   // caller override — WINS
};
```

## Exploitable Fields
`CartBuyerIdentityInput` (Storefront API) includes:
- `companyLocationId` — **B2B**: switch purchasing company/location
- `customerAccessToken` — **Impersonation**: act as any logged-in customer
- `email` / `phone` — **PII injection**: associate cart with arbitrary contact
- `countryCode` — **Tax/shipping bypass**: override buyer country
- `deliveryAddressPreferences` — **Delivery hijack**: redirect shipments

## Exploit Scenario
```typescript
// Legitimate handler created with default buyerIdentity
const cart = createCartHandler({
  storefront,
  buyerIdentity: { countryCode: 'US' },  // default: US buyer
});

// Malicious caller (any client code with cart access)
await cart.addLines([{ merchandiseId: 'gid://Product/1', quantity: 1 }], {
  buyerIdentity: {
    companyLocationId: 'gid://CompanyLocation/999',  // override to B2B account
    customerAccessToken: 'stolen-token',              // impersonate customer
    email: 'attacker@evil.com',                       // inject PII
  }
});
// Result: cart created with attacker-controlled buyerIdentity
```

## Impact
- **B2B fraud**: Place orders on any company account with `companyLocationId`
- **Account takeover**: Use stolen `customerAccessToken` to attach cart to victim
- **Tax evasion**: Set `countryCode` to tax-free jurisdiction
- **Shipping redirect**: Inject `deliveryAddressPreferences` to reroute packages
- **Analytics poisoning**: Skew buyer analytics with fake emails/phones

## Root Cause
- Spread order is **caller-last-wins** (`...defaults, ...caller`)
- No validation of which fields caller may override
- `buyerIdentity` is passed through to Storefront API `cartCreate`/`cartBuyerIdentityUpdate` mutations without server-side verification

## Fix Options
1. **Allowlist merge** — only allow caller to override non-sensitive fields:
   ```typescript
   const allowed = ['email', 'phone', 'countryCode']; // NOT companyLocationId, customerAccessToken
   args[0].buyerIdentity = {
     ...buyerIdentity,
     ...Object.fromEntries(
       Object.entries(args[0].buyerIdentity || {}).filter(([k]) => allowed.includes(k))
     ),
   };
   ```
2. **Separate defaults vs overrides** — `handlerBuyerIdentity` + `callerBuyerIdentity` merged server-side with policy
3. **Validate on server** — Storefront API should reject `companyLocationId` without B2B session, but client shouldn't trust that

## References
- `hydrogen/src/packages/hydrogen/src/cart/createCartHandler.ts:293-295` — merge logic
- `hydrogen/src/packages/hydrogen/src/cart/queries/cartCreateDefault.ts:44-46` — mutation includes buyerIdentity
- Storefront API: `CartBuyerIdentityInput` fields