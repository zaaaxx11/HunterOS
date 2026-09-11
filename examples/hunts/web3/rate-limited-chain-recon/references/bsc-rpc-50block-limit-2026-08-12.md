# BSC Rate-Limited Recon — 2026-08-12 Naoris Hunt

## Verified RPC Behavior (BSC chainid 0x38, block ~115.3M)

**Working vs failing for eth_getLogs (Transfer 0xddf252ad, 50-block window):**
- `https://bsc-dataseed.binance.org` → `{"code":-32005,"message":"limit exceeded"}` even for 50 blocks (2026-08-12). Do NOT use for eth_getLogs.
- `https://1rpc.io/bnb` → WORKS for 50 blocks (verified 200 + result array, empty or hits). Use as primary.
- `https://bsc-rpc.publicnode.com` → WORKS for 50 blocks (fallback).
- `https://rpc.ankr.com/bsc` → 401 Unauthorized (needs API key).
- `https://bnb.api.onfinality.io/public` → 429 Too Many Requests (needs key).
- `https://bsc-dataseed1/2.binance.org` → same limit exceeded.

**Etherscan V2 (api.etherscan.io/v2/api?chainid=56):**
- `module=account&action=tokentx` and `txlist` and `proxy&action=eth_blockNumber` all return `{"status":"0","message":"NOTOK","result":"Free API access is not supported for this chain."}` — BSC free tier is blocked. Requires paid plan. Do not rely.

**Effective chunking:**
- Canonical public RPC max range is 50 blocks on 1rpc.io, 5000 on 48.club, not 100k. Tested: 100k → limit exceeded, 5k → limit exceeded on bsc-dataseed, 5000 → works on 48.club, 50 → works on 1rpc.io.
- Strategy: 50-block chunks throttled 0.6-0.62s sequential via `curl -4 -s --max-time 12`. Scan 500k window = ~10k requests = ~100 min. Checkpoint holders/logs/balances to `/tmp/naoris-a2/` every 500 chunks. Early-stop when logs>3000 or holders>800 for sample.

**Storage slot anomaly:**
- `eth_getStorageAt` ERC1967 impl `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` and admin `0xb53127684a568bb...` return `0x0` on all public BSC RPCs (proxy 342 bytes is minimal forwarder with hardcoded impl, not standard ERC1967). `eth_getProof` also `limit exceeded`. Need archive node / Tenderly for proper impl resolution.

**Repro command (verified 2026-08-12):**
```bash
curl -4 -s --max-time 12 -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[{"address":"0x1b379a79c91a540b2bcd612b4d713f31de1b80cc","fromBlock":"0x6e02c10","toBlock":"0x6e02c42","topics":["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]}]}' \
  https://1rpc.io/bnb
```

**Holder enum pattern:** eth_getLogs Transfer 50-block → collect topic[1]/[2] last 40 hex → set(holders) → balanceOf `0x70a08231` per holder throttled 0.25s → sort by balance → totalSupply `0x18160ddd` for concentration %.
