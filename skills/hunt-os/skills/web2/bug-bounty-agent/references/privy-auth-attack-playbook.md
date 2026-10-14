# Privy Auth Attack Playbook

## When to Use
- Target uses Privy for authentication (look for `usePrivy-*.js`, `PrivyProvider`, `privy-app-id` headers)
- Signup/login via email OTP, Google OAuth, wallet connect, Twitter OAuth
- Need to assess: OTP brute force feasibility, session replay, CAPTCHA bypass, admin checks

---

## Phase 1: Extract Privy AppId

```bash
# 1. Download the Privy bundle
curl -sL https://TARGET/assets/usePrivy-*.js -o privy-bundle.js

# 2. If not found there, search the main index bundle (~2-3MB)
curl -sL https://TARGET/ | grep -oP '/assets/index-[^"]+\.js' | head -1 \
  | xargs -I{} curl -sL "https://TARGET{}" -o index-bundle.js

# 3. Search for the appId assignment (Vite-inlined env or const)
#    Pattern A: var <shortname> = `cm...` (typical Vite env inlining)
grep -oP "var [a-z]{3}\s*=\s*['\x60](cl|cm)[a-z0-9]{18,30}['\x60]" index-bundle.js
#    Pattern B: in PrivyProvider JSX
grep -oP "appId:\s*['\x60](cl|cm)[a-z0-9]{18,30}" index-bundle.js
#    Pattern C: as a raw string (rare, older builds)
grep -oP "['\x60](cl|cm)[a-z0-9]{12,30}['\x60]" index-bundle.js | sort -u | head -10

# 4. Verify appId by querying the Privy app config endpoint
curl -s "https://auth.privy.io/api/v1/apps/<APP_ID>" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>"
```

## Phase 2: Read the Full Privy App Configuration

The config endpoint returns critical security settings:
```bash
curl -s "https://auth.privy.io/api/apps/<APP_ID>" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>" | jq .
```

Key fields to check:
| Field | What to look for | Risk signal |
|-------|-----------------|-------------|
| `captcha_enabled` | `true`/`false` | `false` → OTP brute force possible |
| `enabled_captcha_provider` | `null` or `turnstile`/`recaptcha` | `null` → no CAPTCHA |
| `allowed_domains` | Array of domains | Contains `localhost`, wildcards (`*`), or test/preview domains → credential reuse |
| `email_auth` | `true`/`false` | Email OTP attack surface |
| `google_oauth` | `true`/`false` | OAuth phishing/redirect surface |
| `wallet_auth` | `true`/`false` | SIWE/SIWS endpoints |
| `twitter_oauth` | `true`/`false` | X OAuth surface |
| `passwordless` | — | Check for SMS paths too |
| `embedded_wallet_config.mode` | `on-device`/`tee` | `tee` = server-side key mgmt |
| `wallet_connect_cloud_project_id` | hex string | Can be used to MITM WalletConnect |
| `verification_key` | PEM public key | Used for JWT validation |
| `data_classification` | `public`/`private` | `public` → config is world-readable |
| `mfa_methods` | Array | Empty = no MFA enforced |
| `merge_accounts_by_email` | `true`/`false` | `true` → cross-method merging |

### Example (ColibriSwap, July 2026)
```json
{
  "id": "cmrtsekqw001m0cl4gm2azhe7",
  "name": "colibriswap",
  "captcha_enabled": false,           // ← NO CAPTCHA
  "enabled_captcha_provider": null,   // ← NO CAPTCHA PROVIDER
  "email_auth": true,                 // ← OTP attack surface
  "google_oauth": true,               // ← OAuth surface
  "twitter_oauth": true,
  "wallet_auth": true,
  "solana_wallet_auth": true,
  "data_classification": "public",    // ← World-readable config
  "embedded_wallet_config": {
    "mode": "user-controlled-server-wallets-only",  // ← TEE mode
    "create_on_login": "off"
  },
  "allowed_domains": [
    "http://localhost:8080",           // ← HTTP localhost accepted!
    "https://*.lovableproject.com",    // ← Wildcard!
    "https://*.lovable.app"            // ← Wildcard!
  ]
}
```

## Phase 3: Test the Email OTP Flow

### 3a. Send OTP code — NO CAPTCHA required (BROWSER-ONLY)

**CRITICAL**: Privy strictly origin-gates the passwordless/init endpoint. curl/script-based requests are ALWAYS rejected with `{"error":"Invalid Privy app ID"}` — even with correct `privy-app-id`, `Origin`, `Referer`, and `User-Agent` headers. The `privy-ca-id` header requires a valid client-side challenge that only the official Privy SDK generates.

**This means**: OTP brute force from curl/terminal is IMPOSSIBLE. Browser automation (Playwright/Puppeteer) is REQUIRED to interact with Privy endpoints. Budget this when planning an OTP brute force attack.

```bash
# ❌ DOES NOT WORK (curl/script — always "Invalid Privy app ID")
curl -s -X POST "https://auth.privy.io/api/v1/passwordless/init" \
  -H "Content-Type: application/json" \
  -H "Origin: https://colibriswap.com" \
  -H "privy-app-id: <APP_ID>" \
  -d '{"email":"target@example.com"}'
# → {"error":"Invalid Privy app ID","code":"missing_or_invalid_privy_app_id"}

# ✅ ONLY WORKS via browser-based Privy SDK (Playwright/Puppeteer)
# The SDK generates a valid privy-ca-id challenge that curl cannot replicate
```

### 3b. Test rate limiting
```bash
# Rapid-fire 5 requests
for i in $(seq 1 5); do
  curl -s -X POST "https://auth.privy.io/auth/v1/passwordless/init" \
    -H "Content-Type: application/json" \
    -H "Origin: https://TARGET" \
    -H "privy-app-id: <APP_ID>" \
    -H "privy-ca-id: $(uuidgen)" \
    -d '{"email":"ratetest@example.com"}'
done

# Response patterns to expect:
# {"success":true}           ← Accepted
# {"error":{"code":"429"}}   ← 429 → IP-based rate limit engaged
# {"error":"Too many requests..."}  ← Alternative rate limit format
```

### 3c. Validate OTP code
```bash
curl -s -X POST "https://auth.privy.io/api/v1/passwordless/authenticate" \
  -H "Content-Type: application/json" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>" \
  -H "privy-ca-id: $(uuidgen)" \
  -d '{"email":"target@example.com","code":"123456","mode":"login-or-sign-up"}'

# On valid code: returns identity token (JWT) + user data
# On invalid code: returns error
# Note: IP-based rate limiting protective against brute force from single IP
#       Distributed IP rotations → potentially bypassable
```

## Phase 4: Test Google Wallet OAuth

```bash
# Get the OAuth redirect URL
curl -s -X POST "https://auth.privy.io/api/v1/oauth/init" \
  -H "Content-Type: application/json" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>" \
  -d '{"provider":"google"}'
# → Returns redirect URL; user must complete OAuth in browser
```

## Phase 5: Test Wallet Connect (SIWE/SIWEX)

```bash
# SIWE (Ethereum wallet) init
curl -s -X POST "https://auth.privy.io/api/v1/siwe/init" \
  -H "Content-Type: application/json" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>" \
  -d '{}'

# SIWS (Solana wallet) init
curl -s -X POST "https://auth.privy.io/api/v1/siws/init" \
  -H "Content-Type: application/json" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>" \
  -d '{}'
```

## Phase 6: Session/Token Replay Tests

```bash
# Check if session endpoint leaks data without auth
curl -s "https://auth.privy.io/api/v1/sessions" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>"
# Expected: {"error":"Method not allowed"} — requires POST

# Try users/me without auth token
curl -s "https://auth.privy.io/api/v1/users/me" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>"
# Expected: {"error":"Missing a valid auth token."} — works in production

# If you obtain a token (from browser DevTools or successful login):
curl -s "https://auth.privy.io/api/v1/users/me" \
  -H "Origin: https://TARGET" \
  -H "privy-app-id: <APP_ID>" \
  -H "Authorization: Bearer <TOKEN>"
# → Yields user profile + linked accounts + embedded wallet addresses
```

## Phase 7: Check for Admin/Role Checks

```bash
# Extract all bundles and search for admin-related strings
for bundle in $(curl -sL https://TARGET/ | grep -oP '/assets/[a-zA-Z0-9_-]+\.js' | sort -u); do
  curl -sL "https://TARGET$bundle" -o "$(basename $bundle)"
done

# Search across all bundles
grep -iP '(admin|isAdmin|owner|role|superuser)(\b|[^a-z])' *.js /dev/null
# → If NO hits across all bundles: frontend doesn't even have admin concept
# → If hits found: analyze the logic — is there an email domain gate? user-id check?

# Also check the config from Phase 2 for allowlist
# → "allowlist_enabled": false → no email/domain gating
```

## Phase 8: Check /account and Post-Auth Pages

```bash
# Test server-side rendering of /account (should block or redirect without auth)
curl -sI "https://TARGET/account"
# If HTTP 200 → SSR returns page shell; actual data loaded client-side
# If HTTP 302/403 → server-side auth check working

# Fetch full page to check for session data leakage
curl -sL "https://TARGET/account" | grep -iP '(user|wallet|email|privy|token)'
```

## Exposed Privy API Endpoints (extracted from bundle)

```
POST /api/v1/passwordless/init           — Send OTP email
POST /api/v1/passwordless/authenticate   — Verify OTP + authenticate
POST /api/v1/passwordless/link           — Link email to existing session
POST /api/v1/passwordless/unlink         — Unlink email
POST /api/v1/oauth/init                 — Start Google/X OAuth flow
POST /api/v1/oauth/authenticate          — Complete OAuth
POST /api/v1/oauth/link                 — Link OAuth to session
POST /api/v1/siwe/init                  — Start Ethereum wallet login
POST /api/v1/siwe/authenticate           — Complete wallet login
POST /api/v1/siws/init                  — Start Solana wallet login
POST /api/v1/siws/authenticate           → Complete Solana login
POST /api/v1/guest/authenticate          → Guest auth (if enabled)
GET  /api/v1/users/key                  → Ferent user data (needs token)
POST /api/v1/sessions/logout            → Destroy session
```

## Checklist (before filing)

- [ ] appId extracted from main bundle
- [ ] Full config pulled from `/api/v1/apps/<APP_ID>`
- [ ] CAPTCHA status confirmed (`captcha_enabled`)
- [ ] OTP endpoint tested via browser automation only (curl ALWAYS blocked)
- [ ] Rate limit tested (single IP)
- [ ] Domain whitelist reviewed for wildcards
- [ ] Admin/role checks searched across all bundles
- [ ] `/account` page SSR guard tested
- [ ] WalletConnect project ID noted if present
- [ ] Session endpoints probed for unauthenticated access