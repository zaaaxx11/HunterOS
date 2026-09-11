# Wyze Security Audit Case Study (2026-08-23)

## Target Overview
- **auth.wyze.com** - OAuth 2.0/OpenID Connect authentication server
- **my.wyze.com** - Next.js web portal (SPA)
- **api.wyzecam.com** - Backend API (IIS 8.5, ASP.NET)
- **device-signal-dev.wyze.com** - Device fingerprinting API

## Architecture
Multi-service architecture with:
- Spring Boot backend (auth.wyze.com)
- Next.js frontend (my.wyze.com)
- IIS/ASP.NET API (api.wyzecam.com)
- Separate device signal service (device-signal-dev.wyze.com)

## Critical Findings

### 1. OAuth Client Credentials Exposed (CRITICAL)
**Location:** my.wyze.com/_next/static/chunks/pages/_app-9013c156a433ee8f.js

```javascript
clientId: "bfc07c95-956c-4a39-a5cf-c9a740b66323"
clientSecret: atob("<redacted>")  // BASE64 ENCODED
```

**Pattern to hunt:**
```bash
grep -r "atob\|btoa\|base64" my.wyze.com/_next/static/chunks/
grep -r "clientSecret\|client_secret" my.wyze.com/_next/static/chunks/
```

### 2. Wide Open CORS (CRITICAL)
**Location:** api.wyzecam.com

```http
access-control-allow-origin: *
access-control-allow-methods: GET, PUT, POST, DELETE
access-control-allow-headers: authorization, Content-Type, signature, signature2, appid
```

**Pattern to hunt:**
```bash
curl -sI -H "Origin: https://evil.com" https://api.wyzecam.com/ | grep -i access-control
```

### 3. Device Signal API (HIGH)
**Location:** device-signal-dev.wyze.com

- POST /v1/events/collect - No auth required
- Returns event_id for any input
- Can be used for device spoofing

**Pattern to hunt:**
```bash
curl -X POST https://device-signal-dev.wyze.com/v1/events/collect \
  -H "Content-Type: application/json" \
  -d '{"loginSessionId":"test"}'
```

### 4. Spring Boot Actuator (MEDIUM)
**Location:** api.wyzecam.com/actuator

**Pattern to hunt:**
```bash
curl -s https://api.wyzecam.com/actuator | jq .
curl -s https://api.wyzecam.com/actuator/health | jq .
```

### 5. OpenID Configuration Disclosure (MEDIUM)
**Location:** auth.wyze.com/.well-known/openid-configuration

**Pattern to hunt:**
```bash
curl -s https://auth.wyze.com/.well-known/openid-configuration | jq .
curl -s https://auth.wyze.com/.well-known/jwks.json | jq .
```

## Attack Chains

### Chain 1: OAuth Client Impersonation → Account Takeover
1. Extract client_id and client_secret from frontend JS
2. Generate authorization URL with malicious redirect_uri
3. Victim authorizes malicious app
4. Attacker receives authorization code
5. Exchange code for access token using exposed credentials
6. Full account access

### Chain 2: Device Spoofing → Auth Bypass
1. Generate event_id via /v1/events/collect
2. Manipulate device fingerprint signals
3. Submit manipulated data with login attempt
4. Bypass device trust checks
5. Account takeover

### Chain 3: CORS Exploitation → Data Theft
1. Attacker hosts malicious website
2. Victim visits attacker's website while authenticated to Wyze
3. JavaScript on attacker's site makes cross-origin requests to api.wyzecam.com
4. Custom headers (authorization, signature) can be set
5. Data exfiltration from victim's account

## Recon Checklist for Multi-Service Architecture

1. **Identify all services:**
   - auth.wyze.com (authentication)
   - my.wyze.com (web portal)
   - api.wyzecam.com (backend API)
   - device-signal-dev.wyze.com (device fingerprinting)

2. **Check each service for:**
   - CORS configuration
   - Actuator/health endpoints
   - OpenID/OAuth configuration
   - JavaScript bundle secrets

3. **Extract secrets from JS bundles:**
   ```bash
   grep -r "clientSecret\|client_secret\|apiKey\|api_key" my.wyze.com/_next/static/chunks/
   grep -r "atob\|btoa\|base64" my.wyze.com/_next/static/chunks/
   ```

4. **Test CORS on all services:**
   ```bash
   for domain in auth.wyze.com my.wyze.com api.wyzecam.com device-signal-dev.wyze.com; do
     curl -sI -H "Origin: https://evil.com" https://$domain/ | grep -i access-control
   done
   ```

5. **Check for exposed endpoints:**
   ```bash
   for path in /actuator /health /status /.well-known/openid-configuration /.well-known/jwks.json; do
     curl -s -o /dev/null -w "%{http_code}" https://api.wyzecam.com$path
   done
   ```

## Key Learnings

1. **Multi-service architectures** often have inconsistent security configurations
2. **Frontend JavaScript bundles** can leak OAuth credentials
3. **Device fingerprinting APIs** may be accessible without authentication
4. **CORS misconfigurations** are common and impactful
5. **OpenID configuration** reveals internal scopes and endpoints
6. **Spring Boot actuator** endpoints should be restricted
7. **Next.js _buildManifest.js** reveals all routes in the application
8. **CSP headers** can leak internal endpoint information

## Files Created
- `/home/ubuntu/wyze-audit/FULL_REPORT.md` - Comprehensive audit report
- `/home/ubuntu/wyze-audit/CHAINER_FINAL_REPORT.md` - Exploit chain analysis
- `/home/ubuntu/wyze-audit/Wyze_Auth_Trust_Graph.md` - Trust graph mapping
