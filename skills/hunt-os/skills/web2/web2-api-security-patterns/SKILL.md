---
name: web2-api-security-patterns
description: "HMAC/OAuth/CORS/Shopify API security patterns"
tags: [security, web2, api, signature, oauth, cors]
version: 1.0.0
---

# Web2 API Security Patterns

## Triggers
- "audit API", "test signature", "forge request", "HMAC exposed"
- "Shopify recon", "staging environment", "actuator endpoint"
- "CORS misconfiguration", "OAuth flow analysis"
- Multi-target web2 audit where API auth mechanisms need verification

## Pattern

```
Phase 1: Secret Extraction (JS bundle analysis)
Phase 2: Algorithm Reconstruction (reverse-engineer signing)
Phase 3: Live API Verification (prove signature runs before token validation)
Phase 4: Impact Assessment (what data is protected by forged signatures)
```

## Phase 1: Secret Extraction

### JS Bundle Secret Hunt
1. Download all JS chunks: `_app-*.js`, page-specific chunks
2. Search for: `HMAC`, `MD5`, `signature`, `secret`, `key`, `token`, `encrypt`, `sign`
3. Look for endpoint to secret mappings (switch statements, config objects)
4. Extract base64-decoded values (`atob()` patterns)
5. Check for API key patterns: `apiKey`, `api_key`, `authkey`, `clientSecret`

### Common Secret Patterns
| Pattern | Example | Risk |
|---------|---------|------|
| `atob("...")` | `atob("<redacted-oauth-client-secret>")` | Base64 client secret in JS |
| `HMAC-MD5(data, key)` | `a().HmacMD5(t, o)` | Signing algorithm exposed |
| `MD5(token + secret)` | `a().MD5(web_app_token + n)` | Key derivation exposed |
| `switch(endpoint)` | `case endpoints.v4Event: n="..."` | Per-endpoint secrets |

## Phase 2: Algorithm Reconstruction

### Reconstruct Exact Signature Function
From minified JS, extract:
1. The hash function (MD5, SHA256, HMAC-MD5, etc.)
2. The key derivation (how token + secret becomes signing key)
3. The data format (JSON body, query string, specific fields)
4. The header name (usually `signature2`, `X-Signature`, etc.)

### Build Standalone Implementation
- Python: `hashlib` + `hmac` modules
- Node.js: `crypto` module
- Browser: CryptoJS or Web Crypto API

### Test Vector Verification
- Use a known input/output pair from the JS code
- Verify Python and JS produce identical signatures
- If mismatch, check encoding (UTF-8 vs Latin1), padding, case

## Phase 3: Live API Verification

### Differential Response Test
The KEY test - does the API differentiate between WITH and WITHOUT a forged signature?

```bash
# WITH signature
curl -X POST endpoint -H "signature2: forged" -H "access_token: test" -d body

# WITHOUT signature  
curl -X POST endpoint -H "access_token: test" -d body
```

### Interpreting Results
| With Sig | Without Sig | Meaning |
|----------|-------------|---------|
| 401 UNAUTHORIZED | 400 INVALID_PARAMETER | Signature verified FIRST - exploit possible with valid token |
| 401 UNAUTHORIZED | 401 UNAUTHORIZED | Token checked first - signature not the gate |
| 400 INVALID_PARAMETER | 400 INVALID_PARAMETER | Signature not checked - dead end |
| 200 + data | 200 + data | No auth at all - fully exposed |

## Phase 4: Impact Assessment

### Attack Chain
1. Entry: Open redirect via OAuth state/redirect_uri (post-auth)
2. Token Theft: Steal web_app_token from localStorage
3. Signature Forging: Use exposed secrets + algorithm
4. Data Extraction: Call protected APIs with forged signatures

## Shopify Store Recon Pattern

When a target redirects to a Shopify store:
1. Check `/admin` - redirects to `https://shop.myshopify.com/admin`
2. Check `/meta.json` - leaks Shop ID, name, location, domain
3. Check `/robots.txt` - may leak Shop ID in Disallow rules
4. Password page: test for rate limiting on brute force

## Spring Boot Actuator Pattern

When Spring Boot services are detected:
1. Test `/actuator` and `/actuator/health` first
2. If accessible, test `/actuator/env`, `/actuator/mappings`, `/actuator/heapdump`
3. Check for timestamp/requestId in error responses (info disclosure)
4. Test `/actuator/shutdown` (if enabled = RCE potential)

## Pitfalls

- Signature is NOT authentication: Forged signature passes signature layer, but token validation still runs. Need BOTH valid signature AND valid token.
- Post-auth only: Open redirects via OAuth state parameter only fire after successful login (gated by isLogin check).
- No javascript: in router.push: Next.js router.push() with URL objects does NOT execute javascript: protocol.
- CORS * without credentials: Access-Control-Allow-Origin: * does NOT allow cookies. Only token-based auth works cross-origin.
- Fake JWT session cookies: Some services issue placeholder JWT cookies that are not real session tokens.
