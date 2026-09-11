# GraphQL Attack Patterns — Chia Cloud Wallet (api.vault.chiatest.net)

## Target: api.vault.chiatest.net
- Stack: Node.js + GraphQL + Cloudflare + Apollo Client (Next.js frontend at vault.chiatest.net)
- Introspection: DISABLED
- Auth: Bearer token (checked inside resolvers, NOT at GraphQL middleware)

## Technique 1: Schema Extraction via Validation Errors

When introspection is disabled, deliberately send invalid inputs to leak schema:
- Missing required fields → reveals input type names and field names/types
- Wrong argument names → reveals correct argument names via "Did you mean?" suggestions
- Wrong enum values → reveals valid enum values (or that an enum is expected)
- Non-null violations → reveals which fields are required

**Example probe sequence:**
```bash
# Leak mutation signature
curl -sk 'https://TARGET/graphql' -H 'Content-Type: application/json' -H 'Origin: https://TARGET' \
  -d '{"query":"mutation { logIn { __typename } }"}'
# → Reveals: argument "input" of type "LogInInput!" is required

# Leak input fields
curl -sk 'https://TARGET/graphql' -H 'Content-Type: application/json' -H 'Origin: https://TARGET' \
  -d '{"query":"mutation { logIn(input: {email: \"x\"}) { __typename } }"}'
# → Reveals: field "password" is also required

# Leak enum values (iterate until one doesn't say "does not exist in")
curl -sk 'https://TARGET/graphql' ... -d '{"query":"mutation { deactivateUser(input: {id: \"1\", reason: SPAM}) { __typename } }"}'
# → "Value SPAM does not exist in UserDeactivationReason enum" (try others until one passes)
```

**What you extract per error type:**
| Error Pattern | What It Reveals |
|---------------|-----------------|
| `argument "X" of type "Y!" is required` | Input type name + required field |
| `field "X" is not defined by type "Y"` | All valid field names for that input type |
| `Cannot query field "X" on type "Y". Did you mean "Z"?` | Correct field names via suggestions |
| `Value "X" does not exist in "Y" enum` | Enum type name (keep iterating) |
| `Unknown argument "X" on field "Y"` | Correct argument name via suggestion |
| `must not have a selection since type "X" has no subfields` | Return type (scalar, not object) |

## Technique 2: BFLA Detection — Auth in Resolver vs Middleware

**Pattern found in Chia vault:**
- ALL 18+ mutations pass GraphQL validation WITHOUT authentication
- Auth check happens INSIDE individual resolvers
- Mutations that require globalId format fail on format validation BEFORE auth check

**Detection method:**
1. Send each mutation with valid input structure but no auth token
2. If error says "Authentication required" → auth check is present (good)
3. If error says something else (format, missing field, etc.) → auth check may be AFTER validation (BFLA risk)

**Critical distinction:**
- `updateHotWalletCircuitBreaker(active: true)` → "Authentication required" (auth first)
- `deactivateUser(input: {id: VALID_ID, reason: OTHER})` → "Invalid globalId format" (auth AFTER format check)
- The second pattern means: if you crack the globalId format, the mutation may execute without auth

## Technique 3: GlobalId Format Extraction

When all mutations fail on "Invalid globalId format":
1. Check frontend JS for encoding patterns: `btoa()`, `base64url`, `Buffer.from().toString()`
2. Try: base64("TypeName:id"), base64url("TypeName:id"), plain numbers, UUIDs, hex hashes
3. Try mutations that take `$id: ID!` directly (not wrapped in `$input`) — same globalId validation applies
4. Try the signup flow to extract valid IDs from authenticated session

**Chia-specific:** GlobalId format was NOT standard Relay base64. Could not crack from client-side alone. Server uses custom format validation before auth check.

## Technique 4: Unauthenticated Mutation Survey

Systematically test ALL mutations without auth:
```bash
for mut in createOrganization deleteOrganization updateUser updatePlan createSigner; do
  resp=$(curl -sk 'https://TARGET/graphql' -H 'Content-Type: application/json' \
    -d "{\"query\":\"mutation { $mut(input: {}) { __typename } }\"}")
  # Check if error is "Authentication required" or something else
done
```

**Key insight:** If error is NOT "Authentication required", the mutation passed auth. The blocker is only input validation.

## Rate Limit Observations
- Email-related mutations (requestSignupEmailVerification, requestUserCredentialsResetLink): rate-limited ~1 req/30s per IP
- Other mutations: NO rate limiting observed
- Rate limit appears IP-based, not per-account

## Auth Flow
- `userSignup(email, code)` — 6-digit OTP, returns "Invalid code" (brute-forceable with rate limit bypass)
- `requestSignupEmailVerification(email)` — sends verification email, no auth needed
- `requestUserCredentialsResetLink(email)` — sends reset link, no auth needed
- `logIn(input: LogInInput)` — returns "Bad user input" (no user enumeration)

## Viable Attack Chains (if globalId cracked)
1. `deactivateUser(VICTIM_ID, OTHER)` → Account takeover
2. `createWallet(CustodyConfig)` → Create attacker wallet
3. `createTransaction(walletId, address, amount)` → Fund theft
4. `assignFeatureFlagToOrganization(orgId, flagId)` → Privilege escalation
5. `updateHotWalletCircuitBreaker(active: false)` → Disable hot wallet security
