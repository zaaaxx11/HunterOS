# Arkose Labs Bug Bounty Case Study

**Target:** Arkose Labs (arkoselabs.com) — Bug Bounty Program
**Date:** 2026-08-21 to 2026-08-22
**Methodology:** CDC Web App Bug Bounty Hunting with 4-Agent Orchestration

## Scope Analysis

| Domain | Status | Bounty Tier | Reports |
|--------|--------|-------------|---------|
| www.arkoselabs.com | Critical Eligible | LOW (marketing) | 40 (77%) |
| verify.arkoselabs.com | Critical Eligible | HIGH | 1 (2%) |
| portal.arkoselabs.com | Critical Eligible | HIGH | 6 (12%) |
| iframe.arkoselabs.com | Critical Eligible | HIGH | 0 (0%) |
| demo.arkoselabs.com | Critical Eligible | LOW (marketing) | 0 (0%) |
| customer-sessions.arkoselabs.com | Critical Eligible | HIGH | 1 (2%) |
| client-api.arkoselabs.com | Critical Eligible | HIGH | 4 (8%) |
| cdn.arkoselabs.com | Critical Eligible | HIGH | 1 (2%) |

## Key Findings

### 1. iframe.arkoselabs.com — Captcha Token Theft (MEDIUM)
**Finding:** `parent.postMessage({sessionToken}, "*")` leaks captcha session tokens to ANY origin.
**Evidence:** iframe.arkoselabs.com source code contains 5 event handlers all posting to `"*"`
**Impact:** Any malicious site embedding the iframe can steal valid captcha tokens
**Chain Viability:** FALSE — No Arkose captcha on admin login portals (both use Auth0 SSO)

### 2. Auth0 Client ID Leak (INFO)
**Finding:** Portal client ID `q8CJ9rZPdnB99U3aWBCIiYeQ2jrS16Tw` exposed in chunk 8335.js
**Custom Domain:** `us.auth0.arkoselabs.com`
**Grants:** Only `authorization_code` + `implicit` (no `client_credentials`, no `password`)

### 3. APQ GraphQL Locked (DEFENSE)
**Finding:** `/api/graphql` requires Apollo Persisted Query hash allowlist
**Manifest URLs:** All return 403/404 (`/manifest.json`, `/persisted-queries.json`, `/apollo-manifest.json`)
**Result:** No pre-auth GraphQL entry possible

### 4. portal-account-mgmt Separate App (DEFENSE)
- Different Auth0 client (not the portal's q8CJ9rZP...)
- Only SSO grants (`authorization_code`, `implicit`)
- CSP connects to `portal-prod.arkoselabs.com` (firewalled ELB us-east-2)

### 5. API Gateway Not Found (BLOCKED)
**CSP Reference:** `*.execute-api.us-east-2.amazonaws.com/demo/verify`
**Brute-force:** 80+ common patterns all timeout/no DNS
**Conclusion:** API Gateway IDs are random AWS alphanumeric strings

### 6. client-api Headless Blocker (BLOCKED)
**Issue:** Arkose detects headless Chrome — `api.js` loads but crashes before challenge renders
**Evidence:** `arkoseLabsClientApi` never assigned, CSP violations, no challenge iframe
**Requirement:** Real browser or anti-detection setup needed

## Agent Results Summary

| Agent | Target | Status | Key Output |
|-------|--------|--------|------------|
| A (Browser) | client-api | BLOCKED | Headless detection, no valid bda/session_token |
| B (Architect) | portal GraphQL | BLOCKED | APQ airtight, Auth0 SSO only |
| C (Architect) | portal-account-mgmt | BLOCKED | Different Auth0, no admin endpoints |
| D (Red-Team) | iframe + API GW | PARTIAL | Token leak confirmed, no chain |

## Final Verdict
**No exploitable pre-auth RCE chain found.** All paths blocked by:
- APQ hash allowlist + Auth0 SSO
- Arkose bot detection (headless)
- Firewall (portal-prod)
- Missing Arkose on admin login (Auth0 SSO only)

**Actionable Finding:** iframe.arkoselabs.com `postMessage("*")` token leak — captcha token theft to any origin.