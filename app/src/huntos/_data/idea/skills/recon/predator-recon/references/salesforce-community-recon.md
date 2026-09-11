# Salesforce Community (Experience Cloud) Recon Methodology

## Overview
Salesforce Experience Cloud (formerly Community Cloud) sites expose a REST API at `/services/data/` that can leak significant information if not properly configured. This methodology covers enumeration of API versions, sobjects, and guest user access testing.

## Discovery
Identify Salesforce Communities by:
- **URL patterns**: `/s/`, `/tw/s/`, `/community/`, `/experience/`
- **Headers**: `Link` header with `auraFW`, `salesforce-experience.com`, `siteforce.com`
- **HTML**: `aura.context`, `AuraApp`, `lightning` JS bundles
- **CNAME**: `*.live.siteforce.com`, `*.force.com`, `*.salesforce-experience.com`

## API Enumeration

### 1. List API Versions (Guest Accessible)
```bash
curl -s "https://target.com/services/data/" | jq '.[] | {version: .version, label: .label}'
```
- Returns all supported API versions (v31.0 through v67.0+)
- No authentication required in default configuration
- **Risk**: Information disclosure - reveals exact Salesforce version for targeted exploits

### 2. Enumerate SObjects (Guest Accessible)
```bash
curl -s "https://target.com/services/data/v59.0/sobjects/" | jq '.sobjects[] | {name: .name, label: .label, queryable: .queryable}'
```
- Lists all objects accessible to guest user
- Test each version (v59.0, v58.0, v57.0, etc.)
- **Critical objects to check**: `Account`, `Contact`, `User`, `Lead`, `Case`, `Knowledge__kav`, `Article`, `Network`, `NetworkMember`, `Site`, `Domain`, `DomainSite`

### 3. Describe Individual SObjects
```bash
curl -s "https://target.com/services/data/v59.0/sobjects/Account/describe/" | jq '.fields[] | {name: .name, type: .type, createable: .createable, updateable: .updateable, accessible: .accessible}'
```
- Reveals field-level permissions for guest user
- Check `accessible: true` fields for data exposure

### 4. Test SOQL Injection (Guest Accessible)
```bash
curl -s "https://target.com/services/data/v59.0/query/?q=SELECT+Id,Name+FROM+Account+LIMIT+5"
```
- Test multiple versions (v59.0, v58.0, v57.0, etc.)
- Test different objects: `Knowledge__kav`, `Article`, `KnowledgeArticleVersion`
- **Risk**: Data exfiltration if guest user has read access

### 5. Test Search
```bash
curl -s "https://target.com/services/data/v59.0/search/?q=FIND+\{test\}+IN+ALL+FIELDS+RETURNING+Account(Id,Name)"
```

### 6. Recent Items / Recently Viewed
```bash
curl -s "https://target.com/services/data/v59.0/recent/"
```

## Community-Specific Endpoints

### Self-Registration
```bash
# Check multiple paths
curl -s -o /dev/null -w "%{http_code}" "https://target.com/selfreg/"
curl -s -o /dev/null -w "%{http_code}" "https://target.com/SelfRegister/"
curl -s -o /dev/null -w "%{http_code}" "https://target.com/Register/"
```

### Password Reset
```bash
curl -s -o /dev/null -w "%{http_code}" "https://target.com/ForgotPassword/"
curl -s -o /dev/null -w "%{http_code}" "https://target.com/ForgotPasswordConfirm/"
```

### Knowledge/Articles Access
```bash
# Guest access to articles
curl -s "https://target.com/s/article/Test-Article"
curl -s "https://target.com/s/articles"
```

## Information Disclosure via Headers

### Link Header Analysis
```bash
curl -sI "https://target.com/s/" | grep -i "link:"
```
Look for:
- `auraFW` - Aura framework internal paths
- `salesforce-experience.com` / `siteforce.com` - Internal CDN paths
- Version numbers in paths: `/1783705227000-1117383689/`
- Component names: `APPLICATION@markup://siteforce:communityApp`

### CSP Report-Only
```bash
curl -sI "https://target.com/s/" | grep -i "content-security-policy-report-only"
```
- Reveals allowed domains: `*.force.com`, `*.salesforce.com`, `*.visualforce.com`, `*.content.force.com`
- Check for `frame-src`, `script-src`, `connect-src` domains for takeover/customization

## Guest User Access Testing

### Network/Community Objects
```bash
# Check if guest can access community metadata
curl -s "https://target.com/services/data/v59.0/sobjects/Network/describe/"
curl -s "https://target.com/services/data/v59.0/sobjects/NetworkMember/describe/"
curl -s "https://target.com/services/data/v59.0/sobjects/Site/describe/"
curl -s "https://target.com/services/data/v59.0/sobjects/Domain/describe/"
curl -s "https://target.com/services/data/v59.0/sobjects/DomainSite/describe/"
```

### Query Community Data
```bash
# List communities
curl -s "https://target.com/services/data/v59.0/query/?q=SELECT+Id,Name,UrlPathPrefix+FROM+Network"

# List community members (if accessible)
curl -s "https://target.com/services/data/v59.0/query/?q=SELECT+Id,UserId,NetworkId+FROM+NetworkMember+LIMIT+10"
```

## Security Configuration Checks

### 1. API Version Restriction
- **Secure**: Only latest 1-2 versions accessible
- **Vulnerable**: All versions v31.0+ accessible (37+ versions)

### 2. Guest User Profile Permissions
- Check: `Setup → Users → Public Access Settings → CORS` → Should be empty
- Check: `Setup → Communities → Settings → Require HTTPOnly` → Should be enabled
- Check: `Setup → Session Settings → Secure and HttpOnly cookies` → Should be enabled

### 3. CORS Configuration
```bash
curl -s -X OPTIONS "https://target.com/services/data/v59.0/sobjects/" \
  -H "Origin: https://evil.com" \
  -H "Access-Control-Request-Method: GET" \
  -v
```
- Check `Access-Control-Allow-Origin` - should NOT be `*` or reflect arbitrary origins

### 4. Session Settings
```bash
# Check cookie flags
curl -sI "https://target.com/s/" | grep -i "set-cookie"
```
Look for: `HttpOnly`, `Secure`, `SameSite=Strict` or `Lax`

## Testing Checklist

| Test | Command | Expected Secure Result |
|------|---------|------------------------|
| API versions | `curl /services/data/` | 401 or only latest 1-2 versions |
| SObjects list | `curl /services/data/v59.0/sobjects/` | 401 |
| SOQL query | `curl '/services/data/v59.0/query/?q=SELECT+Id+FROM+Account'` | 401 |
| Search | `curl '/services/data/v59.0/search/?q=FIND+{test}'` | 401 |
| Self-reg | `curl -I /selfreg/` | 404 or redirect to login |
| Password reset | `curl -I /ForgotPassword/` | 404 or redirect to login |
| Link header | `curl -I /s/ | grep Link` | No internal paths |
| CSP | `curl -I /s/ | grep csp` | CSP enforced (not report-only) |

## Attack Paths

### Path 1: Guest Data Access
1. API version enumeration → 2. SObjects enumeration → 3. SOQL query on sensitive objects → 4. Data exfiltration

### Path 2: Community Takeover via Subdomain
1. Find CNAME to `*.live.siteforce.com` → 2. Check if community deleted → 3. Claim subdomain

### Path 3: IDOR in Articles/Knowledge
1. Enumerate article IDs → 2. Access `/s/article/{id}` → 3. Check for unpublished/draft content

### Path 4: SOQL Injection
1. Find user input in query parameters → 2. Inject SOQL → 3. Extract data

## Tools
```bash
# Quick enumeration script
#!/bin/bash
TARGET="https://target.com"
for ver in {59..67}.0; do
  echo "=== v$ver ==="
  curl -s "$TARGET/services/data/v$ver/sobjects/" | jq -r '.sobjects[]?.name' 2>/dev/null | head -20
done

# Batch test versions
for ver in {55..67}.0; do
  echo "Testing v$ver..."
  curl -s -o /dev/null -w "%{http_code}" "$TARGET/services/data/v$ver/sobjects/"
  echo
done
```

## Reporting Template
```
Title: Salesforce Community REST API Guest Access - Information Disclosure
Severity: Medium (CVSS 3.1: 5.3 - CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N)
Summary: Salesforce Community REST API at /services/data/ exposes 37+ API versions and sobjects list without authentication.
Impact: Attackers can enumerate all API versions, list all accessible objects, and potentially query sensitive data.
Reproduction:
1. curl https://target.com/services/data/
2. curl https://target.com/services/data/v59.0/sobjects/
3. curl "https://target.com/services/data/v59.0/query/?q=SELECT+Id,Name+FROM+Account+LIMIT+5"
Fix: Restrict API access to authenticated users only via Guest User Profile permissions.
```

## References
- Salesforce REST API Developer Guide: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/
- Experience Cloud Security Guide: https://help.salesforce.com/s/articleView?id=sf.networks_security.htm
- Guest User Security: https://help.salesforce.com/s/articleView?id=sf.guest_user_security.htm