# services.wyze.com API Enumeration — August 2026

## Overview
Enumerated the services.wyze.com API surface as part of Wyze web app audit. Found 5 POST-only endpoints with masked validation (generic 400 for all payloads).

## Endpoints Discovered
| Endpoint | GET | POST | Auth |
|----------|-----|------|------|
| `/api/v2/user/login` | 405 | 200+400 | needs valid OAuth payload |
| `/api/v2/active` | 405 | 200+400 | auth? |
| `/api/v2/subscriptions/all` | 401 | 200+400 | auth |
| `/api/v2/user/status` | 405 | 200+400 | auth? |
| `/api/v2/user/currency` | 401 | 200+400 | auth? |

## Key Findings

### 1. All Validation Masked
- Malformed JSON → `200 {"code":400,"error":"Bad Request"}`
- Extra fields → same response
- Missing fields → same response
- Wrong types → same response
- **No pydantic 422 leak** — FastAPI validation completely masked

### 2. No OpenAPI Docs
- `/openapi.json` → 404
- `/docs` → 301 to my.wyze.com
- `/redoc` → 301 to my.wyze.com

### 3. Session Cookie is Fake
- Server sets `session=eyJjdX...O9bE` cookie
- Contains literal `...` in token
- 4 parts instead of 3 (not valid JWT)
- **Conclusion:** Cookie auth NOT used — header auth is primary

### 4. Auth Flow (Reconstructed from JS)
```javascript
POST https://services.wyze.com/api/v2/user/login?source=webview
Content-Type: application/json

// OAuth code flow:
{
  code: <auth_code>,
  redirect_uri: "https://my.wyze.com/user/callback",
  client_id: "bfc07c95-956c-4a39-a5cf-c9a740b66323",
  code_verifier: <PKCE_verifier>
}

// Headers added by interceptor:
access_token: <web_app_token>
Authorization: Bearer <token>
request_id: <random_int>
```

### 5. No Auth Bypass Found
- All payload variations → 400
- IDOR attempts → 400
- JWT algorithm attacks → 400
- Parameter pollution → 400
- Mass assignment → 400

## Probing Strategy (Reusable)
1. Check `/openapi.json`, `/docs`, `/redoc` first
2. Test malformed JSON for 422 pydantic leak
3. Map GET vs POST (405 = method not allowed)
4. Test `source` param variations
5. Test header auth patterns
6. Check session cookie behavior
7. Look for verbose error messages

## Files Created
- `/home/ubuntu/wyze-audit/test_wyze_signatures.py`
- `/home/ubuntu/wyze-audit/test_wyze_signatures_extended.py`
- Agent transcripts in `/home/ubuntu/.hermes/cache/delegation/live/deleg_*/`
