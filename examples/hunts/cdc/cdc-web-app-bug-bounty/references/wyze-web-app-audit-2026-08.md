# Wyze Web App Audit — CDC 4-Agent Cross-Validation Learnings
**Date:** 2026-08-23/24
**Target:** my.wyze.com, auth.wyze.com, services.wyze.com, app.wyzecam.com (+15 internal services)

---

## NEW TECHNIQUES / LEARNINGS

### 1. 4-Agent Cross-Validation Model for XSS/Client-Side Hunting

**Agent 1: DOM Sink Hunter** — Traces dangerous sinks (`innerHTML`, `outerHTML`, `eval`, `location.assign/replace`, `router.push`, `dangerouslySetInnerHTML`) from URL params to execution.

**Agent 2: Reflected XSS Hunter** — Tests all URL params, error pages, `__NEXT_DATA__` injection, Next.js router state for reflection.

**Agent 3: JS Bundle Analyst** — Searches `eval`, `document.write`, `innerHTML`, `location`, `window.open`, OAuth callback flow in minified bundles.

**Agent 4: Stored XSS & CSP Bypass** — Checks `dangerouslySetInnerHTML` contexts, third-party scripts, CSP headers, open redirect chains.

**Cross-Validation Rules:**
- Each agent works independently — NO sharing until all complete
- Finding is "PROVEN" only if ≥2 agents independently confirm OR 1 agent with live browser verification
- "NO VULN" accepted only if all 4 independently confirm negative
- Agents communicate only via final summaries — no mid-run coordination

---

### 2. Next.js Static Export Analysis

**Detection:** `__NEXT_DATA__` with `nextExport: true`, `autoExport: true`, `buildId`

**Key Insight:** Static export = **no SSR reflection** — all URL params rendered client-side only. XSS reflection only possible via client-side DOM sinks (router.push, dangerouslySetInnerHTML).

**Extraction:** 
- `buildId` from `__NEXT_DATA__` → find all `/_next/static/chunks/pages/*.js` bundles
- Download: `index.js`, `callback.js`, `redirect.js`, `login.js`, `logout.js`, `_app.js`

**Static Export = Architectural XSS Protection:**
- No server-side rendering of params → no reflected XSS via SSR
- Only client-side DOM sinks matter for XSS
- Next.js router.push() blocks `javascript:` protocol URLs

---

### 3. HMAC Signing Secret Extraction from Frontend JS

**Search Pattern in Minified Bundles:**
```javascript
case endpoints.v4Event: n="<redacted>"; break
case endpoints.platform: n="<redacted>"; break
case endpoints.membershipV2: n="<redacted>"; break
```

**Algorithm Reconstruction:**
```javascript
// Found in bundle:
let o = a().MD5(web_app_token + n).toString();
return a().HmacMD5(t, o).toString();

// Algorithm: HMAC-MD5(data, MD5(web_app_token + endpoint_secret))
```

**Attack Chain:**
1. Phish user via post-auth open redirect → steal `web_app_token`
2. Use stolen token + exposed HMAC secret → forge `signature2` headers
3. Call any protected Wyze API (`v4Event`, `platform`, `membershipV2`, etc.)

---

### 4. Post-Auth Open Redirect Detection

**Parameters to Watch:** `state`, `redirect_uri`, `referer`, `return`, `next`

**Trace Pattern:**
```javascript
// callback.js
f = t ? decodeURIComponent(t) : "/home"
y ? e.push(f) : ...  // y = isLogin (gated by auth state)

// app.js
if (pathname.includes("/user/callback") && u.query.redirect_uri) {
  let e = new URL(u.query.redirect_uri);
  u.push(e);  // full URL object → any origin
}
```

**Verification Method:**
1. Unauthenticated visit → falls to default (gated by `isLogin`)
2. Authenticated visit → fires redirect
3. `new URL()` constructor blocks `javascript:` protocol → OPEN REDIRECT, not XSS
4. Live verification: headless Chrome CDP with `router.push` monitoring

---

### 5. FastAPI Endpoint Probing (When Docs Disabled)

**Detection:** `/openapi.json`, `/docs`, `/redoc` return 404/301

**Probing Strategy:**
1. POST with malformed JSON → expect 422 (pydantic validation) for schema leak
2. If uniform `200 {"code":400}` for all payloads → validation masked by gateway/proxy
3. Map POST-only endpoints vs GET (405 = method not allowed)
4. Test `source` param variations: `webview`, `web`, `app`, `ios`, `android`
4. Test header auth: `access_token`, `Authorization`, `request_id`

**Wyze services.wyze.com Findings:**
- 5 real POST-only endpoints at `/api/v2/`: `/user/login`, `/active`, `/subscriptions/all`, `/user/status`, `/user/currency`
- All POST → `200 {"code":400}` for everything (no pydantic 422 leak)
- FastAPI validation errors completely masked by gateway

---

### 6. Client-Side OAuth Flow Reconstruction from Minified JS

**Search Patterns:**
- `api/v2/user/login`, `oauth/token`, `code_verifier`, `redirect_uri`, `setUser`, `user_account`
- Interceptor: `services.wyze.com` → adds `access_token`, `Authorization`, `request_id`

**Reconstructed Request:**
```javascript
POST https://services.wyze.com/api/v2/user/login?source=webview
Content-Type: application/json

// OAuth code flow:
{
  code: <auth_code>,
  redirect_uri: "https://my.wyze.com/user/callback",
  client_id: "bfc07c95-956c-4a39-a5cf-c9a740b66323",
  code_verifier: <PKCE_verifier_from_localStorage>
}

// Magic link flow:
{
  ac: <access_token>,
  vf: <verifier>,
  client_id: <client_id>,
  redirect_uri: <redirect_uri>,
  code_verifier: <verifier>
}
```

**Header Routing Logic:**
```javascript
PH (services.wyze.com) → adds access_token header
WE (services.wyze.com?) → adds token header
Sc → adds Authorization header
```

---

### 7. Headless Chrome CDP for XSS Verification

**Setup:**
```bash
google-chrome --headless=new --no-sandbox --disable-gpu \
  --remote-debugging-port=9222 --remote-allow-origins=* \
  --user-data-dir=/tmp/chrome-test
```

**CDP Client Pattern (Python + websocket-client):**
```python
ws = websocket.create_connection(page["webSocketDebuggerUrl"])
cdp(ws, mid, "Page.enable")
cdp(ws, mid, "Page.navigate", {"url": test_url})
time.sleep(wait)
cdp(ws, mid, "Runtime.evaluate", {"expression": "window.location.href", "returnByValue": True})
```

**Verification Targets:**
- `router.push(javascript:...)` execution → check `window.location.href`
- `router.push(evil.com)` redirect firing → check final URL
- Network requests monitoring → capture all outgoing requests

---

### 8. Session Cookie Analysis (JWT Decoding)

**Extraction:**
```bash
curl -s -D - "https://services.wyze.com/" | grep -i "set-cookie"
```

**Decoding:**
```python
token = "eyJ...base64url..."
parts = token.split('.')
payload = parts[1] + '=' * (-len(parts[1]) % 4)
payload = payload.replace('-', '+').replace('_', '/')
decoded = base64.b64decode(payload)

# Try zlib decompress if compressed
import zlib
zlib.decompress(decoded, -zlib.MAX_WBITS)
```

**Fake JWT Indicators:**
- 4 parts instead of 3
- Literal `...` in token
- Malformed base64url
- Decodes to empty/compressed garbage
- **Conclusion:** Cookie auth NOT used — header auth is primary

---

### 9. Wyze-Specific Findings Summary

| Finding | Severity | Confidence |
|---------|----------|------------|
| Exposed OAuth Client Credentials in JS | CRITICAL | PROVEN |
| HMAC Signing Secrets in JS (5 endpoints) | HIGH | PROVEN |
| Post-Auth Open Redirect (state param) | HIGH | PROVEN |
| Post-Auth Open Redirect (redirect_uri) | HIGH | PROVEN |
| Wide-Open CORS on 6 Services | MEDIUM | PROVEN |
| Missing Security Headers (my.wyze.com) | MEDIUM | PROVEN |
| Spring Boot Actuator Exposed (2 services) | MEDIUM | PROVEN |
| Internal URLs Leaked in JS | MEDIUM | PROVEN |
| Weak Crypto (MD5 for signatures) | MEDIUM | PROVEN |

**No Classic XSS Found (4-Agent Consensus):**
- No stored/reflected/DOM XSS
- Next.js static export + React auto-escape = architectural protection
- auth.wyze.com has WAF blocking XSS payloads (403)

---

### 10. Attack Chain Integration

**Post-Auth Open Redirect + Exposed HMAC Secrets = Full Chain:**

```
1. Phish user via post-auth open redirect (state/redirect_uri)
   → User logs in → redirected to evil.com
   → Steal web_app_token from localStorage/session

2. Use stolen web_app_token + exposed HMAC secrets
   → Forge signature2 headers for ANY Wyze API:
     - v4Event (camera streams, events)
     - platform (device settings, file upload)
     - membershipV2 (billing, subscriptions)
     - aiEventFeedback (AI data)
     - eventDa (analytics)

3. Impact: Full account takeover, video feed access, device control
```

---

## REFERENCE FILES CREATED THIS SESSION
- `/home/ubuntu/wyze-audit/XSS_FINDINGS_CROSSVALIDATED.md` — 4-agent XSS cross-validation
- `/home/ubuntu/wyze-audit/dom_xss_analysis_report.md` — Agent 1 DOM sink analysis
- `/home/ubuntu/wyze-audit/WYZE_AUDIT_FINAL.md` — Complete audit report
- Agent transcripts in `/home/ubuntu/.hermes/cache/delegation/live/deleg_*/task-0.log`