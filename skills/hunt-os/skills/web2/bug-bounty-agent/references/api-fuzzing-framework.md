# API Fuzzing Framework — Coupang Taiwan Case Study

## Overview
Comprehensive fuzzing framework built for `api-gateway.tw.coupang.com` and `cmapi.tw.coupang.com` covering 11 vulnerability classes across 423 tests per target.

## Framework Architecture (`/root/coupang_fuzzer.py`)

### Core Components
- **PayloadGenerator**: 11 static methods generating test payloads per vulnerability class
- **CoupangFuzzer**: Main orchestrator with `run_all_tests()` executing 11 test suites
- **Data Classes**: `FuzzResult` + `FuzzSummary` with JSON-serializable output

### Test Categories (11)
| Category | Tests/Target | Key Techniques |
|----------|-------------|----------------|
| Auth Bypass | 45 | JWT alg confusion (RS256→HS256, none), host header injection, X-Forwarded-* manipulation |
| HTTP Verb Tampering | 49 | PUT/DELETE/PATCH/TRACE/CONNECT on GET endpoints |
| Parameter Pollution | 32 | Duplicate params, array injection, JSON-in-form, case override |
| Rate Limiting | 50 | Burst (20 req), concurrent (30 workers × 10) |
| Business Logic | 40 | Negative/zero price, quantity overflow, coupon stacking, IDOR, race conditions |
| File Upload | 30 | PHP shells, polyglots, path traversal filenames, null bytes, oversized |
| GraphQL | 25 | Introspection, batch queries, deep nesting, alias overload, dangerous mutations |
| WebSocket | 20 | Auth bypass, message flood, malformed JSON, binary, oversized frames |
| Mobile App API | 30 | Cert pin bypass, signature replay, device ID rotation, version downgrade, UA spoofing |
| Injection (SQLi/XSS/Path/CMD) | 100 | 5 payloads × 4 classes × 5 endpoints |
| Property-Based | 2 | Idempotency, state consistency |

### Output Format
```json
{
  "target": "https://api-gateway.tw.coupang.com",
  "total_tests": 423,
  "vulnerabilities_found": 75,
  "auth_bypasses": 0,
  "logic_flaws": 40,
  "dos_vectors": 5,
  "crash_indicators": 0,
  "critical": 0, "high": 39, "medium": 11, "low": 25,
  "results": [FuzzResult objects...]
}
```

## Key Learnings & Optimizations

### SSR-Only / TanStack Start Architecture Detection (CRITICAL — Pre-Fuzzing Gate)
Before running a full fuzzing campaign, verify the target is actually fuzzable via direct HTTP:
```bash
# 1. Test with a simple POST to any page
curl -s -X POST target.com/swap -H "Content-Type: application/json" -d '{}'
# → {"error":"Only HTML requests are supported here"} = SSR-only!
# → Traditional API fuzzing will NOT work — all POST requests return SSR HTML or error

# 2. Check for TanStack Start / TanStack Router markers
curl -s target.com/ | grep -oP 'createServerFn|\\$_TSR\\.router|\\$TSS/serverfn'
# → If found, server functions go through SSR RPC, not REST endpoints

# 3. If SSR-only: extract provider API URLs from JS bundles
grep -oP 'https?://[a-zA-Z0-9.-]+/(api|v[12])\S+' bundle.js | sort -u
# → These are the real backend APIs the SSR server proxies to
# → Fuzz THESE endpoints directly, not the SSR shell wrapper
```

**Skip the framework entirely for SSR-only targets.** Instead:
1. Extract provider/broker API URLs from JS bundles
2. Fuzz provider APIs directly (ChangeNOW, HoudiniSwap, etc.)
3. Use headless browser automation for full swap-flow testing
4. Test client-side validation bypasses (SSR page may not validate what browser JS does)
5. Target `/signup` for missing CAPTCHA/rate-limit (often SSR-rendered and unvalidated)

### Performance (Critical for Real Targets)
1. **Reduce payload counts**: Slice arrays `[:5]` for injection tests, `[:8]` for pollution, `[:6]` for uploads
2. **Cap WebSocket repeats**: `min(ws.get("repeat", 1), 2)` prevents ping-flood DoS on self
3. **ThreadPoolExecutor workers**: 10 for rate tests, not 20+
4. **Single-pass business logic**: POST only (not GET+POST) — mutations are POST in real APIs
5. **Simulation mode**: `_make_request()` simulates responses when targets unreachable; swap for real `requests`/`aiohttp` in production
6. **Iterative scope reduction**: If initial run exceeds timeout, reduce endpoint count per category before reducing payloads
   - Example: `active_endpoints[:5]` instead of `[:20]`, then `headers[:8]` instead of all headers
7. **Async batching with semaphores**: Use `asyncio.Semaphore(30)` to control concurrency instead of unlimited workers
8. **Short timeouts**: 15-20s per request max; skip slow endpoints early
9. **Baseline caching**: Cache baseline responses per endpoint to avoid re-requesting for differential comparison

### Serialization Pitfalls
- **Bytes in payloads**: WebSocket binary frames produce `bytes` objects → JSON serialize fails
- **Fix**: Recursive serializer in `to_dict()` converting `bytes → utf-8` with `errors='replace'`
- **GraphQL batch queries**: Some payloads are JSON arrays, not objects → wrap in try/except `json.loads()`

### Vulnerability Detection Logic (`_analyze_result()`)
```python
# Server errors = crash/DoS
if status >= 500: crash_indicator = True, severity = "high"

# Auth bypass: 200 on auth endpoint with manipulated token
if status == 200 and "auth" in endpoint: auth_bypass = True, severity = "critical"

# Verb tampering: 200 on mutating verb for protected endpoint
if status == 200 and method in ["PUT","DELETE","PATCH"]: auth_bypass = True

# Business logic: price ≤ 0 accepted
if "price" in payload and status == 200: logic_flaw = True

# Rate limit bypass potential
if status == 429: dos_vector = True, severity = "medium"

# Info disclosure
if status == 200 and "version" in body: vulnerability = True, severity = "low"
```

### Parser Differential Detection (New — Critical for WAF/CDN Environments)
```python
# Baseline: GET /endpoint/ → 200 OK, 2554 bytes, application/json
# Test: Same endpoint with manipulated header/payload/verb
# Compare: status_code, response_length, content_type, body keywords

def check_parser_differential(baseline, current):
    diffs = []
    if baseline["status_code"] != current["status_code"]:
        diffs.append(f"status: {baseline['status_code']}->{current['status_code']}")
    if abs(baseline["response_length"] - current["response_length"]) > 500:
        diffs.append(f"length: {baseline['response_length']}->{current['response_length']}")
    if baseline.get("content_type") != current.get("content_type"):
        diffs.append(f"content_type: {baseline.get('content_type')}->{current.get('content_type')}")
    # Check for new error keywords
    baseline_text = baseline.get("response_text", "").lower()
    current_text = current.get("response_text", "").lower()
    error_keywords = ["internal server error", "stack trace", "exception", "nullpointer",
                      "syntax error", "sql syntax", "traceback", "undefined"]
    for kw in error_keywords:
        if kw in current_text and kw not in baseline_text:
            diffs.append(f"new_error_keyword: {kw}")
    return diffs if diffs else None

# Why this works on Salesforce/Cloudflare/Akamai:
# CDN-to-origin header forwarding creates request variations that the
# origin processes differently but doesn't fully block, revealing
# internal logic paths. Parser differentials = hidden attack surface.
```

### Mobile App Specifics
```python
def check_parser_differential(baseline, current):
    """Detect when same endpoint responds differently to manipulated input"""
    diffs = []
    
    # Status code change = parser/handler changed
    if baseline["status"] != current["status"]:
        diffs.append(f"status:{baseline['status']}->{current['status']}")
    
    # Significant length change = different processing
    if abs(baseline["length"] - current["length"]) > 500:
        diffs.append(f"length:{baseline['length']}->{current['length']}")
    
    # Content-Type change = different parser
    if baseline.get("content_type") != current.get("content_type"):
        diffs.append(f"ct:{baseline.get('content_type')}->{current.get('content_type')}")
    
    # Error page vs normal response = WAF/handler triggered
    if "error" in current["body"].lower() and "error" not in baseline["body"].lower():
        diffs.append("error_page")
    
    return diffs
```
**Key insight**: Parser differentials often indicate:
- Cloudflare header processing affecting origin
- Salesforce REST API accepting unexpected verbs/content-types
- WAF rule triggered vs bypassed

### Mobile App Specifics
- Certificate pinning bypass headers (`X-Certificate-Pin: bypass`)
- Request signing replay with stale timestamps
- Device ID rotation + API version downgrade
- Custom header injection in `X-Device-ID`, `X-App-Version`

## Running Against Real Targets
Replace `_make_request()` with:
```python
def _make_request(self, target, endpoint, method, **kwargs):
    url = urljoin(target, endpoint)
    resp = requests.request(method, url, timeout=self.timeout, **kwargs)
    return resp.status_code, dict(resp.headers), resp.text, resp.elapsed.total_seconds() * 1000
```

## Integration with Bug Bounty Workflow
1. **Recon phase**: Use this after subdomain enumeration + API discovery
2. **Analyze phase**: Run framework → review `high`/`critical` results manually
3. **Verify phase**: Convert each finding to minimal reproduction script
4. **Report phase**: Use `FuzzSummary` severity counts for CVSS prioritization