# Expo / React Native Web App Reconnaissance

## Fingerprint — 5 seconds
Expo RN-Web apps ship with these markers:
- `<script src="/_expo/static/js/web/__expo-metro-runtime-<hash>.js">`
- `<script src="/_expo/static/js/web/__common-<hash>.js">`
- `<script src="/_expo/static/js/web/entry-<hash>.js">`
- `<style id="expo-reset">` and `<style id="react-native-stylesheet">`
- `#root` div (not `__next`)

## Differences from Next.js
| Aspect | Next.js | Expo RN-Web |
|--------|---------|-------------|
| Catch-all 200 on `/api/*` | YES | NO — real 404 |
| JS bundle format | Webpack chunks in `/_next/static/chunks/` | Metro-bundled in `/_expo/static/js/web/` |
| Number of bundles | ~50+ small chunks | 3 core bundles (runtime, common, entry) |
| Entry.js size | ~100KB each | 5-10MB monolithic |
| API extraction | grep `src=` → download chunks → grep `/api/` | grep `_expo/static/js/` → download entry.js → grep |
| Routing | file-based (pages/app router) | React Navigation (opaque path names) |
| Auth pattern | NextAuth cookies | MoonX SDK, Privy, or custom postMessage iframe |

## Bundle extraction (EXPO)
```bash
mkdir -p /tmp/<target>_recon && cd /tmp/<target>_recon

# 1. Fetch homepage, extract bundle filenames
curl -s4 "https://TARGET/" -o home.html
grep -oE 'src="[^"]*\.js[^"]*"' home.html

# 2. Download entry.js (the big one — 5-10MB)
curl -s4 "https://TARGET/_expo/static/js/web/entry-<HASH>.js" -o entry.js

# 3. Extract API routes (NOT Next.js — real 404s, not catch-all)
grep -oE '/api/[a-zA-Z0-9_/-]+' entry.js | sort -u

# 4. Extract auth patterns
grep -oiE '(moonsdk|moonx|privy|magic\.link|web3auth|auth0|clerk|passkey)' entry.js | sort | uniq -c | sort -rn

# 5. Find published API keys (Expo bundles are NOT server-rendered — all client keys are in the bundle)
strings entry.js | grep -oE '[a-z_]+_live_[a-f0-9]+'  # MoonX publishable keys
strings entry.js | grep -oE 'pk_live_[a-zA-Z0-9]+'       # Stripe keys
strings entry.js | grep -oE '[A-Za-z0-9]+\.sentry\.io'   # Sentry DSN

# 6. Faucet/claim endpoint hunting
grep -oiE '(faucet|claim|reward|airdrop|usdc|mint)' entry.js | sort | uniq -c | sort -rn
```

## Key signals (Expo)
- **No catch-all 404**: API paths that return 200 are real; 404 means genuinely missing. Verify with: `curl -s4 "https://TARGET/api/nonexistent-$$"` → should return `NOT_FOUND`, not HTML shell.
- **Monolithic entry.js**: 10MB file = slow grep progress. Use `strings` first, `grep -o` second, `sort -u` last.
- **No source maps by default**: Expo Metro bundled; debugging source maps rarely shipped to production.

## Case study: Paybox.sh (MoonPay product)
- **Publishable key exposed**: `moon_pk_live_f50f6b5985795039a1315bbd09883f"`
- **Auth**: MoonX SDK with passkey (WebAuthn) + email/OAuth login
- **API**: `X-MoonX-Access-Token` header gates all calls (derived from passkey session)
- **Stack**: Expo RN-Web → Vercel → MoonX backend → Basis Theory (card vault) → MoonPay (fiat)
- **Faucet**: `/api/x/faucet/start`, `/api/x/faucet/finalize`, `/api/x/faucet/status`
- **Hard target** — MPC key material, no known bypasses for MoonX session tokens