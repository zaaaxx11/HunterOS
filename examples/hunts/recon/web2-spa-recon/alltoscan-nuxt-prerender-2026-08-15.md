# Alltoscan — Nuxt 3 Prerender + Hardened Explorer (2026-08-15)

Source: `alltoscan.com` + `scan.alltoscan.com` — Mozilla `Firefox/128.0` single-req — `188.166.44.153` DO AMS.

## Stack Fingerprints
- **Apex**: `Nuxt 3` prerender `buildId 502dc79c-3113-41f2-b7fc-4e6ccc044ca5`, `importmap {"imports":{"#entry":"/_nuxt/Bi8Ek9E7.js"}}`, `window.__NUXT__.config {public:{seo-utils, robots}, app:{buildAssetsDir:"/_nuxt/", cdnURL:""}}`, `data-ssr=true` (/) vs `false` (fallback), `/_payload.json?_b=...` static `[{"Reactive":{}}]`. Headers: `server: nginx/1.22.1`, `cache-control: no-cache`, `etag`, `last-modified: Thu,06 Aug 2026`. Missing: HSTS/CSP/X-Frame/X-Content/CORS. `OPTIONS`→405.
- **Scan**: separate buildId `31dc1368-...`, `entry.D6-lekht.css`, `C_X1aWDQ.js`, `public.Root: https://scan.alltoscan.com/` `public.ApiBase: https://scan.alltoscan.com/api`, `helmet` + `express-rate-limit` + Mongo ObjectId (`_id/__v/createdAt/updatedAt`).

## Routes (sitemap.xml 14 urls)
`/`, `/about/`, `/contact/`, `/blog/`, `/blog/what-is-a-block-explorer` etc (5 blogs), `/products/{ats-token,wats-wallet,sons-of-ton,explorer}`, `/privacy-policies`, `/faq`, `/learn` on scan. `robots.txt Allow: /`. `/_nuxt/manifest.json` 404.

## Bundles
Apex: `Bi8Ek9E7.js`(#entry), `yQ1KQDH8.js`, `DnJRI8OJ.js`, `D0onan1b.js`, `BGbz1riz.js`, `DVnI1svY.js`, `entry.69z7GHab.css`. Scan: `C_X1aWDQ.js` (ApiBase), `wy4COAZh`, `DLGSqlxX`, `20zkUUnO`, `evWO-ChZ` (only `$fetch(c+"/get_home_data")`), `CrHbVHiC`, `DlAUqK2U`, `iRfqpIby`, `Z2QKrZdz`, `Be7mfUwV` etc.

## API — Verified
- Apex: **none** — `/api`, `/.env`, `/swagger`, `/admin`, `/.well-known/security.txt` all `200 text/html` Nuxt fallback shell (`data-ssr=false`).
- Scan: `GET /api/get_home_data` → `200 {"succeeded":true,"home_data":[{chain:arb/avax/matic/op/eth/bsc/base/ftm/zkf, number, gas_price, latest_txn{hash,from,to,amount,timestamp:17868...}, txns, withdrawals:[]} …]}`. All other `/api/*` → `404 {"succeeded":false,"message":"Not found."}` with CSP/HSTS/X-Frame/COOP. Rate-limit `10;w=5` → `ratelimit-limit:10 ratelimit-remaining 429` after 10/5s burst.
- RPCs client-direct: `*.publicnode.com` (eth/bsc/arb/avax/polygon/optimism/fantom/base) + `rpc.zkfair.io`. GTM `G-WFJR4SX55B` / `G-BNNMEYS23V`.

## Inputs
- Scan search: `input Search by Address/Transaction/Block/Token Name` + `select chain ETH/BSC/MATIC/AVAX/BASE/FTM/OP/ZKF/ARB` → router `/address/:chain/:addr` etc → direct RPC; token `ca/logo/name/symbol` rendered `src:v.logo`.
- Contact: `form.grid gap-5` `c-name` text `c-email` email `c-topic` select General/Partnerships/Press/Support `c-message` textarea — no `action`/`fetch` → dead; `_payload.json` empty; future mail via `spf mailersend/mailbaby`.

## Subdomains/DNS
`alltoscan.com 188.166.44.153`, `scan 188.166.44.153 200`, `www 188.166.44.153 200`, `mail 142.93.239.31 303`, others NX. NS `carol/norman.ns.cloudflare.com` (no proxy → origin exposed). MX google + SPF google/mailbaby/mailersend.

## Recon Checklist (Nuxt prerender)
1. `curl -A Mozilla -s https://<apex>/ | grep -oE 'buildId|/_nuxt/[^"]+\.js|importmap|__NUXT__'` + `curl -s /robots.txt /sitemap.xml /_payload.json`.
2. Download `_nuxt/*.js`, `grep -oE 'ApiBase|Root|buildId'` + `grep 'c+"/' ` — expect 0-1 real API on apex.
3. Brute siblings `for s in scan api explorer app wallet admin docs www mail; do curl -A Mozilla -w "%{http_code}" https://$s.<domain>/` — sibling may hold real API.
4. Validate every `200` via `Content-Type` + `head -c 500` (`<!DOCTYPE` = fallback).
5. Respect `ratelimit 10/5s` — `sleep 2` between `/api` probes.
