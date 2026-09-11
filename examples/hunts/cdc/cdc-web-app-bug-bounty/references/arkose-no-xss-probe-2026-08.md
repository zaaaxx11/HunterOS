# Arkose Labs — No-XSS & No-Chain Verification (2026-08-22, session 2)

Session 2 added a two-agent XSS hunt to the earlier (session 1) recon. **Result: NO XSS on any target, NO exploitable chain.** This file extends `arkose-labs-case-study.md` with the XSS probe methodology and the concrete reasons every vector was inert — reusable when a future hunt hits a static iframe + SDK-loaded challenge, or an Apollo persisted-query GraphQL.

## Headless Chrome on this VPS — how to actually use it
- Binary: `/usr/bin/google-chrome` and `/usr/bin/google-chrome-stable` (both present; snap chromium also exists). DISPLAY is empty → must use `--headless=new`.
- Working headless flags proven this session:
  `google-chrome-stable --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-software-rasterizer`
- `--dump-dom` works for reflection checks but is RACY for async `postMessage`/console events (DOM is printed before messages arrive). For async captures use CDP (`--remote-debugging-port=9222` + a Python websocket client, or `--enable-logging --v=1` and grep stderr for `INFO:CONSOLE`). One agent wrote `/tmp/cdp_capture.py` against port 9222.
- Models on this stack are NOT vision-capable → `vision_analyze` on a PNG returns 400 "does not accept image input". Render proof screenshots with PIL (DejaVu Sans Mono at /usr/share/fonts/truetype/dejavu/) instead of screenshot-then-OCR.

## XSS vectors tested on iframe.arkoselabs.com — all inert
1. **public_key path injection into script src.** `getClientKey()` takes last pathname segment containing `-` and puts it into `src="//client-api.arkoselabs.com/v2/"+key+"/api.js"`. Host is HARDCODED; `setAttribute` (not HTML attr parsing) → `%22onload=%22` inert. `/../../evil.com/x` only changes the path segment, never the host.
2. **Byte-identical SDK for every key.** md5 of `/v2/{key}/api.js` = `4f7e1b1ba7ac904e328fa39db8428ea1` for FOO, C-D, evil.com, A%2f..%2fevil.com, and real UUIDs. No per-key content to hijack even if you control the segment.
3. **data/theme/mkt params not reflected.** `data` is `decodeURIComponent`'d then passed to `setConfig` as `data.blob`, but SDK never writes config.data to any DOM sink (grep api.js for innerHTML/insertAdjacentHTML/document.write = none). `theme`/`mkt` -> React/JS props, auto-escaped, and SDK dies early in headless (`TypeError: getAttribute of undefined`) before rendering.
4. **Prototype pollution via getAllUrlParams.** `?__proto__[polluted]=x&constructor[prototype][polluted2]=y` — plain local object, no merge into Object.prototype, no consuming sink. Inert.
5. **CSP nonce rotates per request.** Observed fresh nonce on every fetch. No static nonce to reuse, so injected-inline-script is dead even if an injection point existed.

## Supplementary targets — all clean
- **portal GraphQL**: Apollo persisted-query hash allowlist. POST raw query → fixed `{"errors":[{"message":"Query hash is required to process the request."}]}`. Unknown hash → fixed `"Unregistered document hash attempted..."`. Query text NEVER echoed. Manifest URLs (`/manifest.json`, `/persisted-queries.json`, `/apollo-manifest.json`, `/graphql/manifest.json`, cdn variants) all 403/404. `@apollo/persisted-query-lists` v1.1.0 in chunk 6039/8420; `loadManifest` is passed in, never a fetchable URL.
- **client-api JSONP**: `?callback=` ignored on `/fc/api/nojs`, `/v2/{key}/api.js`, `/fc/gt2/public_key/{uuid}`. Fixed loader script / `DENIED ACCESS`, never wrapped.
- **Auth0 sso-callback**: `?state=`/`?code=` reflected? No — static SPA HTML (1454 bytes), React renders nothing from URL params (marker count 0).
- **www/demo Webflow/Cloudflare**: params not reflected; Cloudflare 403 block page static; CSP nonce rotates on demo.

## Verified real finding (carry-forward, Medium)
`parent.postMessage(JSON.stringify({eventId:"challenge-*", publicKey, payload:{sessionToken}}), "*")` in 5 callbacks (complete/loaded/suppressed/shown/failed). Any embedding origin can capture a valid captcha sessionToken. **Impact is bounded**: token is per-public-key + short-lived, validated by the CUSTOMER backend, so it's a captcha-bypass primitive at customer sites — NOT a path into Arkose infra, NOT an RCE/ATO chain. No Arkose captcha on admin login (portals use Auth0 SSO), so no chainable target. Report as Medium captcha-token exfil.

## Reusable probe sequence for static-iframe + SDK challenge targets
1. md5-compare the served SDK across injected keys before claiming script hijack (byte-identical ⇒ inert).
2. Check if the path→src value flows through `setAttribute` (inert to quote-break) vs HTML attr parsing.
3. Verify CSP nonce rotation across 2 requests before assuming inline-bypass is possible.
4. Use unique ASCII marker (`XSSMRK<unique>`) not `<script>` (SPA bundles have hundreds of legit `<script>` tags → false positives). Count markers in `--dump-dom`, not curl body.
5. Look for `parent.postMessage(msg, "*")` with a secret BEFORE concluding a target is clean — origin-validation gaps are real findings even with zero XSS.

## Files
- `references/arkose-labs-case-study.md` — session 1 recon (scope, Auth0 client_id `q8CJ9rZPdnB99U3aWBCIiYeQ2jrS16Tw`, APQ lockout, portal-account-mgmt separate app, API Gateway not found, headless-client blocker).
- User's preferred finding-report format (English, human tone, no `---` separator lines, .md + PNG terminal screenshot + raw .txt proof, calls out jujur/not-oversold) — apply when writing the Arkose disclosure.