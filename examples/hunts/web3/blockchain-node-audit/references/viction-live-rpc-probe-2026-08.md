# Viction Live RPC Probe — 2026-08-16

**Target:** `https://rpc.viction.xyz` (Chain ID: 88)  
**Infrastructure:** Cloudflare-protected (error 1015 rate limiting after ~15 requests)  
**DNS:** 104.20.40.244, 172.66.154.101

---

## Probe Results

### JSON-RPC Method Matrix

| Method | Response | Status |
|--------|----------|--------|
| `net_version` | `"88"` | ✅ Enabled |
| `eth_chainId` | error 1015 (Cloudflare) | ⚠️ Rate-limited |
| `eth_blockNumber` | error 1015 | ⚠️ Rate-limited |
| `eth_accounts` | `["0x3e03bc621579b2cc6b9d2aeb2691896471ccf905"]` | 🔶 **ENABLED — LEAKS WALLET** |
| `eth_gasPrice` | error 1015 | ⚠️ Rate-limited |
| `eth_mining` | error 1015 | ⚠️ Rate-limited |
| `eth_hashrate` | error 1015 | ⚠️ Rate-limited |
| `eth_protocolVersion` | error 1015 | ⚠️ Rate-limited |
| `eth_getBalance` | error 1015 | ⚠️ Rate-limited |
| `eth_sendTransaction` | `-32000 insufficient funds` | ✅ Method enabled (rejected on funds) |
| `web3_clientVersion` | error 1015 | ⚠️ Rate-limited |
| `net_peerCount` | error 1015 | ⚠️ Rate-limited |

### Private/Admin/Debug Methods (All Gated)

| Method | Response | Status |
|--------|----------|--------|
| `admin_nodeInfo` | `-32601 does not exist` | ✅ Gated |
| `txpool_status` | `-32601 does not exist` | ✅ Gated |
| `personal_listWallets` | `-32601 does not exist` | ✅ Gated |
| `miner_setEtherbase` | `-32601 does not exist` | ✅ Gated |
| `debug_getHead` | `-32601 does not exist` | ✅ Gated |
| `debug_traceTransaction` | `-32601 does not exist` | ✅ Gated |
| `trace_transaction` | `-32601 does not exist` | ✅ Gated |

### Alternate Ports (No Response)

| Port | Service | Status |
|------|---------|--------|
| 8545 | WebSocket RPC | ❌ Blocked |
| 8546 | WebSocket RPC | ❌ Blocked |
| 8547 | WebSocket RPC | ❌ Blocked |
| 27017 | MongoDB | ❌ Blocked |
| 2375 | Docker API | ❌ Blocked |
| 6379 | Redis | ❌ Blocked |
| 30303 | Ethereum P2P | ❌ Blocked |
| 26657 | Cosmos Tendermint | ❌ Blocked |
| 1317 | Cosmos LCD | ❌ Blocked |

### Stats Server (`stats.viction.xyz`)

- **Frontend:** Public AngularJS netstats dashboard (expected)
- **API endpoints:** All require WebSocket upgrade (`Upgrade Required`)
- **Socket.IO:** Returns HTML 404 for polling transport
- **Config files:** `.env`, `config.js`, `config.json` all return 404
- **No sensitive data leakage**

### Metrics/Debug Paths (All 404)

| Path | Status |
|------|--------|
| `/metrics` | 404 |
| `/debug/pprof` | 404 |
| `/debug` | 404 |
| `/health` | 404 |
| `/server-status` | Cloudflare blocked |

---

## Key Finding

### 🔶 MEDIUM: `eth_accounts` Wallet Address Leakage

**Leaked address:** `0x3e03bc621579b2cc6b9d2aeb2691896471ccf905`

**Why this matters:**
- `eth_accounts` is part of the `eth` namespace (enabled on virtually all public RPCs)
- Returns node-managed account addresses without authentication
- Enables targeted phishing, balance tracking, tx history analysis
- Distinct from `personal_*` exposure — this is the PUBLIC namespace

**Live proof:**
```bash
curl -s -X POST https://rpc.viction.xyz \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_accounts","params":[],"id":1}'
# => {"jsonrpc":"2.0","id":1,"result":["0x3e03bc621579b2cc6b9d2aeb2691896471ccf905"]}
```

---

## Cloudflare Rate Limiting

After ~15 JSON-RPC requests, Cloudflare returned error 1015 (rate limited). This is a **mitigating factor** — limits automated enumeration but does not prevent manual probing of individual methods.

---

## Recommendations

1. **Disable `eth_accounts`** on public RPC endpoints (it's rarely needed publicly)
2. **Application-level rate limiting** (not just Cloudflare)
3. **Monitor** the exposed wallet address for suspicious activity
4. **Regular audits** of RPC method availability on public endpoints

---

*Probe conducted 2026-08-16 via Hermes Agent. Cloudflare rate limiting prevented full enumeration.*
