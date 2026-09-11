# Hydrogen Private Storefront Token Scope Escalation

## Finding
`createStorefrontClient()` in `@shopify/hydrogen-react` accepts `privateStorefrontToken` for server-side use, but **no runtime guard prevents client-side leakage** — only a dev-mode warning.

## Vulnerable Code
**File:** `hydrogen-react/src/storefront-client.ts:126-127`
```typescript
'Shopify-Storefront-Private-Token':
  overrideProps?.privateStorefrontToken ?? privateStorefrontToken ?? '',
```

**Dev-only warn** (`storefront-client.ts:73-78`):
```typescript
if (__HYDROGEN_DEV__ && privateStorefrontToken && globalThis.document) {
  warnOnce('You are attempting to use a private token in an environment where it can be easily accessed by anyone...');
}
```
- `__HYDROGEN_DEV__` is `process.env.NODE_ENV === 'development'`
- **No protection in production** (`NODE_ENV=production`)
- `getPrivateTokenHeaders()` is exported and callable from any client code

## Exploit Path
1. Developer imports `createStorefrontClient` in a client component (common mistake)
2. Passes `privateStorefrontToken` (thinking it's needed for auth)
3. In production build, **no warning fires** — token bundled into client JS
4. Attacker extracts token from bundle → full Storefront API access (read/write cart, customer, products)

## Impact
- **Token scope escalation**: Private token = Admin API equivalent for Storefront (higher rate limits, no IP throttling, bypasses public token restrictions)
- **Cart manipulation**: Create/update any cart, set buyerIdentity, add arbitrary lines
- **Customer PII**: Query customer data via private token if customerAccount linked
- **Inventory/pricing**: Access unpublished products, draft orders via Storefront

## Root Cause
- Architecture assumes developer discipline (server-only imports)
- No build-time enforcement (e.g., `server-only` package, separate entrypoints)
- Dev warning is **opt-out** via `__HYDROGEN_DEV__` flag — stripped in production

## Fix Options
1. **Runtime guard** — throw in `getPrivateTokenHeaders()` if `globalThis.document` exists
2. **Build-time** — use `server-only` package or React Server Components entrypoint split
3. **Separate exports** — `createStorefrontClient.server.ts` vs `createStorefrontClient.client.ts`
4. **Token format detection** — private tokens start with `shpat_` or `shpv_`; reject in client build

## References
- `hydrogen-react/src/storefront-client.ts` — full client implementation
- `hydrogen-react/src/storefront-client.example.js:6` — example shows `privateStorefrontToken: '{private token for server-side requests}'`
- Shopify docs: "Private tokens are for server-to-server communication only"