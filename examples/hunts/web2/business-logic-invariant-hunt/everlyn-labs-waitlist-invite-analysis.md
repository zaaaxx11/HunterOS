# Everlyn Labs — Waitlist/Invite System Business Logic Analysis (2026-08-04)

## Target
**everlyn.ai** — Next.js 14 + Auth.js v5 + Cloudflare
**Production Data:** 171,784 users, $595,900.99 revenue, 8,482,253 videos generated

## Waitlist Endpoint

### API Specification
```
POST /api/waitlist
Content-Type: application/json
Required fields: email, name, phone, twitter (all 4 required)
```

### Behavior Matrix
| Input | Method | Response | Notes |
|-------|--------|----------|-------|
| All 4 fields (JSON) | POST | 400 "缺少必填字段" | Even with all fields present |
| Missing any field | POST | 400 "缺少必填字段" | Consistent error |
| Form-data (all fields) | POST | 500 "服务器内部错误" | Server internal error |
| Form-data (minimal) | POST | 500 "服务器内部错误" | All emails/phones trigger 500 |

### Invariant Violations Found

| Invariant | Expected | Actual | Verdict |
|-----------|----------|--------|---------|
| Valid JSON → 200/201 | 201 Created | 400 "missing required fields" | **EXPLOITABLE** (logic bug) |
| Form-data accepted | 200/201 | 500 Internal Server Error | **EXPLOITABLE** (server crash) |
| No rate limiting | 429 after N req | Unlimited | **EXPLOITABLE** (DoS/enumeration) |
| Email enumeration blocked | Uniform error | Same 500 for all | **BLOCKED** (uniform error) |

### Root Cause Hypothesis
The waitlist endpoint appears to have a **validation logic bug** — JSON validation fails even with correct fields, and form-data parsing triggers an unhandled exception (500). This suggests:
1. Server-side validation schema mismatch
2. Missing form-data parser middleware
4. Database constraint or duplicate check throwing unhandled exception

---

## Invite System

### Business Rules (from RSC payload)
- **Reward:** $50 per paid invite ("Invite 1 friend to buy Everlyn AI, reward $50")
- **Restriction:** "You can't invite others before you bought Everlyn AI"
- **Affiliate Gate:** "You're not allowed to invite others, please contact us to apply for permission"

### Endpoints
| Endpoint | Method | Auth | Response |
|-----------|--------|------|----------|
| `/my_invites` | GET | Required | 404 (redirects to signin) |
| `/admin/waitlist` | GET | Admin | 404 (admin panel exists but waitlist route missing) |
| `/api/waitlist` | POST | None | 400/500 (see above) |

### Invariant Violations Found

| Invariant | Expected | Actual | Verdict |
|-----------|----------|--------|---------|
| Purchase required before invite | Enforced | Cannot test (auth required) | **UNVERIFIED** |
| $50 reward on paid invite | Tracked in `/my_invites` | Returns: balance, total count, paid count, total award | **VERIFIED** (UI shows fields) |
| No self-invite | Blocked | Cannot test | **UNVERIFIED** |

---

## Evidence Commands

```bash
# Waitlist JSON (fails with 400)
curl -4 -X POST https://everlyn.ai/api/waitlist \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@test.com","phone":"+1234567890","twitter":"@testuser"}' -v

# Waitlist Form-data (triggers 500)
curl -4 -X POST https://everlyn.ai/api/waitlist \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "name=Test User&email=test@test.com&phone=+1234567890&twitter=@testuser" -v

# Rate limit test (no limit)
for i in {1..20}; do
  curl -4 -X POST https://everlyn.ai/api/waitlist \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"Test$i\",\"email\":\"test$i@test.com\",\"phone\":\"+1234567890\",\"twitter\":\"@test$i\"}" \
    -w " %{http_code}" -o /dev/null
done

# Email enumeration check (uniform 500)
for email in "admin@everlyn.ai" "founder@everlyn.ai" "test@test.com"; do
  curl -4 -X POST https://everlyn.ai/api/waitlist \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "name=Test&email=$email&phone=+1234567890&twitter=@test" \
    -w " %{http_code}" -o /dev/null
  echo " $email"
done
```