# BC Launchpad (bcswap.org) Vite SPA Fuzz — 2026-08-16

**Target:** `launch.bcswap.org` (BC Launchpad token creation platform) — Agent 3 FUZZ-ENGINEER session.

## Stack
- Vite `index-DePTGhDw.js` 3,347,773 bytes (31 chunks total) + `index-Ca6B9D_d.css`
- React + wagmi/viem + Web3Modal (WalletConnect) + `@google/genai`
- Cloudflare CDN; SPA fallback `<!DOCTYPE html><div id="root">`
- Token creation: **client-side only** — wallet signs tx → factory contract `0x8122fed5Fe47776006816dD1AddDe64a4Caa40d4` (BCHMultisend v0.8.22, no optimization, 1 txn)

## Infrastructure Map (BC Hyper Chain ecosystem)

| Endpoint | Role | Discovery |
|----------|------|-----------|
| `launch.bcswap.org` | Token creation SPA | Main target |
| `mainapi.bchscan.io` | **JSON-RPC proxy** (blockchain node) | `POST {}` → `{"jsonrpc":"2.0","id":null,"error":{"code":-32600}}` |
| `bchscan.io/api/v2/` | Blockscout explorer | JS bundle extraction |
| `adminapi.bchscan.io` | Admin API (404 all paths) | JS bundle (`adminapi.bchscan.io`) |
| `bcmonitorapiv2.bchscan.io` | Monitor API (`/health` → `{"status":"OK"}`) | JS bundle |
| `plugins.bcswap.org` | Static HTML page | JS bundle |
| `airdrop.pnexplore.com` | Separate React app | JS bundle |

## JS Bundle Sink Scan (31 files, 3.3MB main)

| Pattern | Whole Bundle | App Code Only |
|---------|-------------|---------------|
| `innerHTML` | 5 hits | 2 (React internals: `case "dangerouslySetInnerHTML": a.innerHTML=u`) |
| `dangerouslySetInnerHTML` | 0 | 0 |
| `__html` | 0 | 0 |
| `eval()` | 0 | 0 |
| `new Function` | 0 | 0 |
| `postMessage` | 1 (`window.parent.postMessage(n, '*')`) | WalletConnect library, not app |
| `__proto__` | 0 | 0 |
| `constructor.prototype` | 0 | 0 |
| `location.href/assign/replace` | React internals only | 0 |
| `window.open` | 0 | 0 |

**Verdict:** No dangerous sinks in app code. All `innerHTML` hits are React hydration internals. Wildcard `postMessage` is WalletConnect/Web3Modal library code.

## JSON-RPC Proxy Fuzzing (`mainapi.bchscan.io`)

### Discovery Pattern
POST to unknown API returns `{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"invalid request"}}` — this is the signature that identifies a JSON-RPC proxy. Start fuzzing with standard Ethereum JSON-RPC methods.

### Method Fuzz Matrix

| Method | Result | Severity |
|--------|--------|----------|
| `eth_blockNumber` | `{"result":"0xd61657"}` | Info |
| `eth_getBalance` | `{"result":"0x0"}` | Info |
| `eth_getTransactionCount` | `{"result":"0x1"}` (factory) | Info |
| `txpool_content` | `{"result":{"pending":{},"queued":{}}}` | **Low** (public mempool) |
| `debug_traceBlockByNumber` | `{"result":[]}` | **Low** (debug namespace exposed) |
| `admin_nodeInfo` | `{"error":{-32601,"method does not exist"}}` | Blocked |
| `admin_getUsers` | `{"error":{-32601}}` | Blocked |
| `admin_getTokens` | `{"error":{-32601}}` | Blocked |
| `token_create` | `{"error":{-32601}}` | Blocked |

### Key Finding
`debug_traceBlockByNumber` and `txpool_content` are exposed on the public proxy without authentication. `admin_*` methods are properly blocked. This is an info-disclosure surface, not an admin bypass.

## bchscan.io API Parameter Fuzzing

### `tokens` endpoint — 500 on numeric `id`
```
[Trigger]  GET /api/v2/tokens?id=0
[Effect]   HTTP 500 "Internal server error"
[Boundary] id=0, id=-1, id=999999... all crash. id=null, id=string, id=__proto__ → 200 with default list.
```
Server crashes specifically on numeric `id` values. No rate limit observed.

### `tokens` endpoint — silent param ignore
```
[Trigger]  GET /api/v2/tokens?type=__proto__&search=<script>alert(1)</script>&admin=true&role=admin
[Effect]   HTTP 200, returns normal token list — all params silently ignored
[Boundary] No XSS reflection, no prototype pollution, no auth bypass. Safe handling.
```

### `addresses` endpoint — proper validation
```
[Trigger]  GET /api/v2/addresses/0?id=0&admin=true
[Effect]   HTTP 422 {"errors":[{"title":"Invalid value","source":{"pointer":"/address_hash_param"},"detail":"Invalid format. Expected ~r/^0x([A-Fa-f0-9]{40})$/"}]}
[Boundary] Strong regex validation on address path param. Query params ignored.
```

### `smart-contracts` endpoint — factory contract
```
GET /api/v2/smart-contracts/0x8122fed5Fe47776006816dD1AddDe64a4Caa40d4
→ Name: "BCHMultisend", Compiler: v0.8.22+commit.4fc1097e, Optimization: None, Source: 31KB
```

## Token Creation Parameter Fuzz

Token creation is **entirely on-chain** — no server API. The React form captures `name`, `symbol`, `decimals`, `initialSupply`, `supplyRecipient`, `admin`, `mintable`, `burnable` → encoded into calldata → wallet signs → factory contract. Validation layers:
1. Client-side React form validation (bypassable)
2. Solidity v0.8.22 built-in overflow checks (reliable)

No server-side fuzzing possible for token creation params.

## Repro Commands

```bash
# JSON-RPC proxy discovery
curl -sk -X POST https://mainapi.bchscan.io -H "Content-Type: application/json" -d '{}'

# Debug namespace exposure
curl -sk -X POST https://mainapi.bchscan.io -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"debug_traceBlockByNumber","params":["latest",{"tracer":"callTracer"}],"id":1}'

# Mempool exposure
curl -sk -X POST https://mainapi.bchscan.io -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"txpool_content","params":[],"id":1}'

# tokens?id=0 → 500
curl -sk -w '%{http_code}' "https://bchscan.io/api/v2/tokens?id=0"

# tokens?id=null → 200 (safe)
curl -sk -w '%{http_code}' "https://bchscan.io/api/v2/tokens?id=null"

# Factory contract info
curl -sk "https://bchscan.io/api/v2/smart-contracts/0x8122fed5Fe47776006816dD1AddDe64a4Caa40d4"

# Bundle download (all 31 chunks)
for f in $(grep -oP '/assets/[^"]+\.js' /tmp/index.html); do
  curl -sL -A "Mozilla/5.0" "https://launch.bcswap.org$f" -o "/tmp/bcswap_js/$(basename $f)"
done

# Sink sweep (app code only, after SDK slice)
grep -c 'innerHTML\|dangerouslySetInnerHTML\|eval(\|new Function\|__proto__\|postMessage' /tmp/bcswap_js/*.js
```

## Verdict
No pre-auth RCE or fund-theft. Top actionable:
1. **F1 (Medium):** Fix `tokens?id=0` → 500 crash (add input validation for numeric `id`)
2. **F2 (Low):** Restrict `debug_traceBlockByNumber` to authenticated/internal callers
3. **F3 (Low):** Consider restricting `txpool_content` to authenticated callers