# Chia Vault GraphQL Attack Patterns (Proven 2026-08-26)

## Target: api.vault.chiatest.net
- Stack: Node.js + GraphQL (Apollo) + Cloudflare + better-auth + Next.js frontend
- Introspection: DISABLED (leaks via validation errors + JS bundle)
- Auth: **Cookie-based** (`__Secure-better_auth_session=<token>.<sig>`) — NOT Authorization header
- better-auth framework (exposed via Set-Cookie header)

## Proven Attack Chain
```
1. temp-mail → requestSignupEmailVerification (UNLIMITED)
2. verifyUserOtp(SIGNUP) → rate-limited (~25-35 req/IP)
3. userSignup → passkeyOption { id, options }
4. CDP virtual authenticator → navigator.credentials.create()
5. verifyPasskeyAssign → TOKEN + SESSION COOKIE
6. Full session access: viewer, node, mutations
```

## Key Findings
1. **Pre-auth account creation** → auto ORGANIZATION_ADMIN role
2. **IDOR deactivateUser** → accepts any User_<slug> globalId
3. **Plan enumeration** → 5 plans accessible (PRO, RECOVERY_PROVIDER, etc.)
4. **better-auth session cookie** → auth via Cookie header, not Authorization

## GlobalId Format
`User_<26-char-base36-slug>` (e.g., `User_eaf2op24xaxchyp1daeiy6t0`)

## CDP WebAuthn Setup
```bash
chromium-browser --headless=new --no-sandbox --remote-debugging-port=9223 \
  --remote-allow-origins=* --ignore-certificate-errors
```
**CRITICAL:** `WebAuthn.enable({enableUI: false})` — `enableUI: true` hangs

## better-auth Cookie Pattern
```python
import http.cookiejar
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
# Use opener for all requests — cookies handled automatically
```

## Temp Email (mail.tm)
```python
domains = requests.get("https://api.mail.tm/domains").json()["hydra:member"]
# Create account → poll /messages for OTP
```

## Rate Limits
- `requestSignupEmailVerification`: UNLIMITED
- `verifyUserOtp`: ~25-35 req/IP, 10-min cooldown
- GraphQL queries: NOT rate-limited

## PoC File
`/tmp/chia/exploit_v5.py` — full end-to-end chain
`/tmp/chia/REPORT.md` — vulnerability report