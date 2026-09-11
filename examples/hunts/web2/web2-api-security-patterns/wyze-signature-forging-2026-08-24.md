# Wyze Signature Forging Audit Reference
## Date: 2026-08-24

### HMAC-MD5 Signing Secrets (from my.wyze.com _app.js)

**Algorithm:**
```
key = MD5(web_app_token + endpoint_secret)
signature = HMAC-MD5(request_data, key)
Header: signature2
```

**Secret Groups:**
| Secret | Endpoints |
|--------|-----------|
| `<redacted>` | v4Event, newDevice |
| `<redacted>` | platform, aiEventFeedback |
| `<redacted>` | membershipV2, aiSubscription, eventDa |

**Live API Verification (89 requests):**
- v4Event: WITH sig = 401 UNAUTHORIZED, WITHOUT sig = 400 INVALID_PARAMETER (24/24 differentiated)
- newDevice: Same pattern (10/10 differentiated)
- platform: DNS resolution failed
- membershipV2: 404 (path not found)
- aiEventFeedback: 403 (both)
- eventDa: 404 (both)
- aiSubscription: 401 (both)

**Test Vector:**
```
endpoint="v4Event", token="test_token_123", data='{"device_id":"test","limit":10}'
→ Signature: bb19cf08cc26c29a40396aab1f31f1c1
```

### OAuth Client Credentials
```
clientId: bfc07c95-956c-4a39-a5cf-c9a740b66323
clientSecret: atob("<redacted>")
scopes: ["authcode-read", "openid", "email", "native"]
```

### Open Redirect Chains
- `state` param (callback.js): `decodeURIComponent(t)` → `router.push(f)` — post-auth only
- `redirect_uri` param (app.js): `new URL(u.query.redirect_uri)` → `u.push(e)` — post-auth only

### Services.wyze.com Login Endpoint
- POST only (GET returns 405)
- All payloads return `{"code":400,"error":"Bad Request"}` (HTTP 200)
- No schema leak (pydantic 422 masked)
- Auth via `access_token` header from SPA interceptor
- Fake session cookie (literal `...` in JWT payload)

### Shopify Store (dev.wyze.com)
- Redirects to `/password` (Shopify storefront password page)
- `/admin` → `wyze-playground.myshopify.com/admin`
- Shop ID: 59299561662
- No rate limiting on password brute force
- OAuth client_id: `7ee65a63608843c577db8b23c4d7316ea0a01bd2f7594f8a9c06ea668c1b775c`

### Spring Boot Actuator
- `app-core.cloud.wyze.com/actuator` → health: DOWN (503)
- `devicemgmt-service.wyze.com/actuator` → health: DOWN (503)
- Only `/actuator` and `/actuator/health` accessible
- Timestamp/requestId leaked in error responses

### Beta Environment
- `beta-v3.my.wyze.com` — Active Next.js app (Build ID: IC5p-y_uEhnnbtwKxf1pB)
- `beta-app-core.cloud.wyze.com/actuator` → health: DOWN
- `beta-oauth.api.wyze.com` → OIDC config leaked (internal, client-create, magic-link scopes)
- Google Analytics debug_mode: true

### Files Created
- `/home/ubuntu/wyze_sign.py` — Python signature implementation
- `/home/ubuntu/wyze_sign.js` — Node.js signature implementation
- `/home/ubuntu/wyze_exploit_chain.py` — Complete PoC exploit chain
- `/home/ubuntu/WYZE_EXPLOIT_CHAIN.md` — Attack chain documentation
- `/home/ubuntu/wyze-audit/endpoint_impact_analysis.md` — Priority ranking
