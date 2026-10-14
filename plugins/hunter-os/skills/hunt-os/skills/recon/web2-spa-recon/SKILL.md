---
name: web2-spa-recon
description: "SPA-decoy Next/Nuxt/Vite: catch-all traps, real-API extraction from JS chunks, Firebase triage (Colb/Nuxaris/BC Swap/Alltoscan/Bityuan/VersatizeCoin cases)"
metadata:
  version: 1.0.0
  hermes:
    tags: [web2, spa, nextjs, ssrf, recon, firebase, api-discovery]
    category: security
---

# Web2 SPA Recon — Next.js Catch-All & Open-Proxy Triage

## When to Use
- Target is Next.js / Vite SPA with all `/api/*` returning 200 HTML
- JS bundles hide real API bases on a different subdomain (`api-*`, `lcd-*`, `eth-*`)
- `?q=` / `url=` / `rpc?q=` proxy pattern needs SSRF vs CORS-bypass classification
- Firebase `AIzaSy…` found in chunks — need to triage public config vs real creds

## Workflow

### 1. Real API Extraction from JS Chunks
```bash
# Find chunk dir from /_next/static/chunks/*.js or /assets/*.js
python3 - <<'PY'
import re, pathlib, glob
for p in glob.glob("/tmp/deep-hunt-*/chunks/*.js"):
    t = pathlib.Path(p).read_text(errors='ignore')
    for m in re.findall(r'https://[^\s"\'`]{10,120}', t):
        if 'aioz' in m.lower() or 'api' in m.lower():
            print(m[:100])
PY
# Validate: content-type application/json + {"success"/"message"} is real; <!DOCTYPE is decoy
curl -sk -I https://api-explorer.aioz.network/api/status | head -n 10
curl -sk https://api-explorer.aioz.network/api/status | head -c 500
```

### 2. SPA Catch-All 200 Trap
- Any `200` with `<!DOCTYPE html>` is Next.js fallback — NOT an endpoint. Don't report as 🔥 without body check.
- Probe the backend domain found in bundles (`api-*`, `api-explorer`) — that's where `404 {"message":"Not Found"}` vs `200 {"success":true}` distinguishes real vs fake.

### 3. Open-Proxy (CORS Bypass) vs Internal SSRF
Test matrix for `?q=` proxies:

| `q` | Expected if open-proxy | Expected if internal SSRF |
|---|---|---|
| `https://example.com` | `Example Domain` HTML | same |
| `http://127.0.0.1:8545` / `:3000` | `connection refused` (no service in container) | `200` / `{"jsonrpc"...}` or AWS metadata |
| `http://169.254.169.254/latest/meta-data/` | `not found` | `ami-id` / IAM creds |
| `http://metadata.google.internal/...` | `no such host` | GCP token |

If external works but localhost/metadata fails with `connection refused`/`not found` → classify as **public open proxy (CORS bypass)**, not internal SSRF. URL-encoded bypass (`%30%2E%30%2E%30`) is typically not decoded — don't assume bypass.

### 4. Firebase Public Keys
`AIzaSy…` in JS is public Firebase config. Not a secret. Triage by checking `firestore.rules` / storage open reads, not by reporting the key.

(target-specific notes preserved at examples/hunts/recon/web2-spa-recon/)

## Architect Trust-Graph Checklist (Vite SPA → admin. takeover path — versatizecoin 2026-08-16)

For ARCHITECT mapping (stack → entry points → trust boundaries → data/control flow):

1. Fetch `index.html` (Mozilla UA), extract importmap + `/assets/*.js` + `/index.css` + headers (Cloudflare/DYNAMIC, CSP miss).
2. Download Vite bundle(s), grep `path:"/..."` (router), `fetch(`, `https://`, `0x…`, `localStorage|cookie`, `dangerouslySetInnerHTML` (slice at `XV=""` to exclude GenAI SDK noise).
3. Brute subdomains off-main (`for s in api admin docs explorer staking portal; do curl -s -o /dev/null -w "$s %{http_code}\n" "https://$s.$domain/" --max-time 4`): found `admin.versatizecoin.com 200` (Vite `index-C5PL2nl1.js` 879KB); others 000. Check crt.sh but 502 is common.
4. Trace data flow `input→transform→storage→output` and control flow `who→conditions→consequences`; list every TB where user input crosses privileged logic (versatizecoin: 12 TBs, TB-1 `localStorage vtcn_session→admin SPA` is critical).
5. Diagram: Cloudflare → www/admin SPAs → off-domain APIs (`aggrigator.bchscan.io`, `generativelanguage.googleapis.com`, CoinGecko) → React state. Cross-link admin bypass detail: `examples/hunts/recon/web2-admin-takeover/versatizecoin-admin-localstorage-bypass-2026-08.md`.

## Pitfalls — JSON-RPC Proxy Discovery (2026-08-16)

**`{"jsonrpc":"2.0","id":null,"error":{"code":-32600}}` means you found a JSON-RPC proxy, not a 404.** When `POST {}` to an unknown API returns this signature, it's a blockchain JSON-RPC proxy (likely Elixir/Phoenix or Express middleware). Immediately fuzz with standard Ethereum methods: `eth_blockNumber` (baseline), `eth_getBalance`, `txpool_content` (mempool info leak), `debug_traceBlockByNumber` (debug namespace), `admin_nodeInfo` (admin namespace). The proxy may expose debug/admin methods that the chain's own RPC endpoint blocks. On `mainapi.bchscan.io`: `debug_traceBlockByNumber` returned `[]` (exposed!), `txpool_content` returned live mempool, but `admin_*` methods were properly blocked (-32601). Always test the full method ladder — the proxy may have different access controls than the direct RPC.

## Pitfalls — API `id=0` → 500 Server Crash (2026-08-16)

**`?id=0` on list endpoints can crash the server when `?id=null` returns 200.** `bchscan.io/api/v2/tokens?id=0` → `500 Internal Server Error` while `id=null` → `200` with normal list. The server processes numeric zero differently from null/undefined — likely a database query that fails on `WHERE id = 0` but succeeds on `WHERE id IS NULL`. Also test `id=-1`, `id=9999999999999999999999999999` (overflow), and `id=NaN`. If the server crashes on any of these, it's a DoS vector — no rate limit on the endpoint means repeated requests can degrade service. This is distinct from a 400/422 validation error — it's an unhandled exception bubbling to 500.

## Red-Teamer Evidence Format — Trigger → Effect → Trust Boundary (Mozilla masquerade 2026-08-16)

Every finding from a red-team hunt (auth bypass, JWT forgery, IDOR, SSRF, SSTI, admin exposure, signature forgery) must ship as **[Trigger → Effect → Trust Boundary] + Exploitable vs Blocked + curl evidence**. Versatizecoin proved the pattern:
- `[GET /.env → 200 2519B <!DOCTYPE html> (identical to /) → BLOCKED (SPA catch-all fake 200, Boundary: Public Internet → Static CDN)]`
- `[localStorage.setItem("vtcn_session","active") → full dashboard without fetch → EXPLOITABLE pre-auth bypass, Boundary: Browser localStorage → Admin Control Plane)]`
Always masquerade as `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36` — Python urllib gets 403 on chunks. Brute sibling subdomains with `for s in api admin docs explorer staking portal; do curl -A "Mozilla/5.0 ..." "https://$s.$domain/" --max-time 4` because main SPA catch-all hides real panel on `admin.` (www/admin returned 2519 vs 879KB).

## Decision: When to Claim SSRF

Claim internal SSRF only if `127.0.0.1:8545` returns `{"jsonrpc"...}` or `169.254` returns `ami-id` / IAM JSON. `connection refused` on localhost + `Example Domain` on external = open proxy only — report as low (CORS bypass), not admin takeover. For open RPC, claim **third-party DoS/info-leak** only if `access-control-allow-origin: *` + external `POST /rpc` returns `200` with JSON result (not `<!DOCTYPE`). `CloseQueue {"isOk":true}` from internet = PROVEN external DoS.

## References

(target-specific notes preserved at examples/hunts/recon/web2-spa-recon/)
