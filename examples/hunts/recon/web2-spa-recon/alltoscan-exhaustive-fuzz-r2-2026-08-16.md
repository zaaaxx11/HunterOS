# Alltoscan Exhaustive Fuzz R2 2026-08-16 — 819 Requests Low-Noise (0.8s Sleep)

## Script: /root/fuzz_round2.py
- Wordlist 204: SecLists api-words + nitro (`/_payload.json`, `/_nuxt/builds/meta/<id>.json`) + well-known + actuator (`/actuator/health`, `/actuator/env`, `/actuator/beans`, `/actuator/mappings`) + custom chains (`chain=eth/bsc/polygon/avax/base/arb/op/ftm/zkf`) + ats cross-check (`/api/`, `/app/login.php`).
- Phases: PATH-BRUTE 204×2 hosts (408) → METHOD 15×9×2 (270) → HEADER 17×2 (38) → BODY 10+charset+large (20) → RACE 10 parallel → GRAPHQL/gRPC 27 → PARAM 32.
- Low-noise: `session=requests.Session(Mozilla UA)`, `SLEEP=0.8`, `do_req()` sleeps `retry-after+0.5` on 429 else 0.8; `TIMEOUT=12`, `allow_redirects=False`. Background `terminal(background=true, notify_on_complete=true)` prevents shell-level nohup block.
- Anomaly heuristic: 5xx, 301, 429, `x-powered-by`, `ACAO evil.com/*`, `succeeded:false non-404`, `succeeded:true` on non-get_home_data, error keywords.

## Status Distribution (819)
- 200:350 (body 9, charset 4, graphql 6, grpc 1, header 38, large 4, method 43, param 16, path-brute 221, race 8)
- 301:7 (path-brute trailing-slash)
- 400:2 (body-fuzz invalid JSON)
- 404:303 (body 9, charset 3, graphql 12, grpc 2, large 2, method 92, param 16, path-brute 167)
- 405:141 (graphql 6, method 135)
- 415:1 (charset iso-8859-1)
- 429:15 (path-brute 13, race 2)

## Path Brute Detail
- SCAN: 27×200 (real: `GET /api/get_home_data` + `?chain=*` any value → same 9-chain `home_data` `_id/__v/createdAt/updatedAt` + SPA `/address/0x…` `/token/0x…` `/block/1` `/tx/1` Nuxt 2966B), 164×404 JSON/HTML, 13×429. MAIN: 194×200 SPA catch-all (`<!DOCTYPE`, `etag 6a743cca-*`, `cache-control: no-cache`), 7×301 (`/blog→/blog/` etc). Only `succeeded:true` on scan get_home_data.

## Method Fuzz Detail (15 endpoints)
- SCAN: GET get_home_data 200; POST/PUT/PATCH/DELETE 404 except invalid JSON 400 `Unexpected token '}'`, iso-8859-1 415 `unsupported charset "ISO-8859-1"`; OPTIONS 200 `Allow-Methods: GET,HEAD,PUT,PATCH,POST,DELETE` `Vary: Origin, Access-Control-Request-Headers` (no ACAO unless Origin sent); HEAD 200 empty; TRACE/CONNECT 405 nginx. MAIN: GET/HEAD 200 SPA (3077/169780), POST/PUT/PATCH/DELETE/CONNECT 405 nginx, OPTIONS 200 empty.
- No 500.

## Header Fuzz Detail (17)
- SCAN `/api/get_home_data`: Origin evil.com → ACAO evil.com Vary Origin 200, Origin scan.alltoscan.com → ACAO scan.alltoscan.com, Origin null → ACAO null (reflective LOW, no ACAC). Host evil.com / X-Forwarded-Host / XFF 127.0.0.1/1.3.3.7 / X-Real-IP / X-Original-URL /api/admin / X-Rewrite-URL / X-Http-Method-Override PUT/DELETE / X-Forwarded-Proto / Forwarded / Referer / Cookie admin → all 200 ignored, no bypass. MAIN `Host: evil.com`, `scan.alltoscan.com.evil.com` → 200 SPA 169780 no reflection/location.

## Body/Charset/Large Detail
- POST valid/empty/nested/array/proto-pollution/xml/form/multipart/text-plain → 404; invalid JSON → 400 both POST and GET-with-body `{"test":}`; iso-8859-1 → 415; GET-with-body all 200 home_data (body ignored). Large 10k/100k POST → 404, GET `?chain=AAA…2000` → 200 4155/4138, main `?q=AAA…2000` → 200 169780.

## Race/GraphQL/gRPC/Param Detail
- Race 10 parallel: 8×200 +2×429.
- GraphQL `POST {__schema}`: scan `/api/graphql` 404 JSON (`succeeded:false`), `/graphql` etc 404 Nuxt `x-powered-by: Nuxt` `x-frame-options: DENY`; main POST 405, GET `?query={__schema}` 200 SPA.
- gRPC `application/grpc` POST `/api/get_home_data` 404, `/grpc.health.v1.Health/Check` 404 Nuxt, `/` 200 Nuxt 35793 — no `grpc-status`.
- Param 16×2: SQLi `bsc' OR`, SSTI `{{7*7}}` `${7*7}`, `__proto__`, traversal `../../../etc/passwd`, SSRF `url=http://169.254...` `http://127.0.0.1:80` `https://evil.com`, `test OR 1=1`, `__proto__[polluted]`, `constructor[prototype]`, `%0d%0a`, `ETH%00`, `<script>`, `invalid_chain` → all 200 len 4132-4155 variance = live gas_price churn (baseline 4152).

## Header Leak / Security Headers
- `server: nginx/1.22.1` all; `x-powered-by: Nuxt` on 404 HTML; `strict-transport-security: max-age=15552000; includeSubDomains` + `x-content-type-options: nosniff` + `x-frame-options: SAMEORIGIN/DENY` + `CSP default-src 'self'` on scan; `ratelimit-limit:10 ratelimit-remaining:0 retry-after:1-2 etag W/… vary: Origin`.
- No `set-cookie`, no `PHPSESSID`, no `location` on Host poison.

## Rate-Limit & JSON Error
- 15×429 HTML `Too many requests, please try again later.` (text/html not JSON) `ratelimit-limit:10 retry-after:1-2`. 2×400 +1×415 +303×404 JSON. Zero 5xx.

## Repro
```bash
curl -sk -i -A "Mozilla/5.0" -H "Origin: https://evil.com" https://scan.alltoscan.com/api/get_home_data
curl -sk -i -X POST -H "Content-Type: application/json" -d '{"test":}' https://scan.alltoscan.com/api/get_home_data #400
curl -sk -i -X POST -H "Content-Type: application/json; charset=iso-8859-1" -d '{"test":1}' https://scan.alltoscan.com/api/get_home_data #415
for i in {1..11}; do curl -sk -w "%{http_code}\n" -A "Mozilla/5.0" https://scan.alltoscan.com/api/get_home_data; done #429 after 10
```

## Artifacts
- Raw: /root/fuzz_round2_raw.json (1.6M, 819 entries)
- Scripts: /root/fuzz_round2.py, /root/FUZZ_ROUND2_FINAL_REPORT.md, /root/fuzz_round2_report.md
