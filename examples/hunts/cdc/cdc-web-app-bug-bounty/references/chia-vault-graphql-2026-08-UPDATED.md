# GraphQL Attack Patterns — Chia Cloud Wallet (2026-08-26 Updated)

## Target
- Stack: Node.js + GraphQL + Cloudflare + Apollo Client (Next.js frontend)
- Introspection: DISABLED
- Framework: **better-auth** (Node.js)
- Auth: **Cookie-based** (`__Secure-better_auth_session`), NOT Authorization header

## GlobalId Format (CRACKED)
| Type | Format | Example |
|------|--------|---------|
| User | `User_<26-char-base36>` | `User_eaf2op24xaxchyp1daeiy6t0` |
| Organization | `Organization_<26-char-base36>` | `Organization_gd8adkpijimcjhlr33y5c4wu` |
| Plan | `Plan_<NAME>` | `Plan_PRO` |
| FeatureFlag | `FeatureFlag_<NAME>` | `FeatureFlag_USER_MANAGEMENT` |
| Passkey | `Passkey_<base64url>` | `Passkey_-NBqt1k4R8VF4qhn...` |

## Confirmed Vulnerabilities

### VULN 1: Pre-Auth Full Account Creation (CRITICAL)
Temp email → OTP → verifyUserOtp → userSignup → CDP WebAuthn → verifyPasskeyAssign → SESSION. Success 4/4, ~30s, no CAPTCHA, auto ORGANIZATION_ADMIN.

### VULN 2: BFLA on updateOrganization (HIGH)
`updateOrganization(input: {id:"Organization_<OWN>", name:"EXPLOITED_ORG", sessionDuration:3600})` — no owner validation.

### VULN 3: GraphQL Error Oracle (MEDIUM)
Full schema extraction. CreateUserInput: email, password, role, organizationId. UserRole: SYSTEM_ADMIN, SUPPORT_ADMIN.

### VULN 4: Feature Flag + Plan Info Leak (MEDIUM)
All 5 plans + FeatureFlag_<NAME> UUIDs enumerated via plans query.

### VULN 5: Auto ORGANIZATION_ADMIN (HIGH)
Every signup = ORGANIZATION_ADMIN.

## Rate Limits
- verifyUserOtp: ~25-35 req/IP then 10min cooldown
- requestSignupEmailVerification: ~1 req/30s
- Other mutations: NO rate limiting

## PoC Files
- `/tmp/chia/chain_target2.py` — Full end-to-end PoC
- `/tmp/chia/FINAL_REPORT.md` — Complete report
