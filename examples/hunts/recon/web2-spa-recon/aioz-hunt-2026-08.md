# AIOZ Hunt 2026-08 — SPA Decoy, Open-Proxy, Token Capped-Mint

**Target:** `aioz.network` + `AIOZNetwork` GitHub (40 repos) + `0x626e8036...BF18` (ETH) / `0x33d08d8c...3741D` (BSC) + `aioz_168-1` native | **Date:** 2026-08-15 | **Tools:** `web2-deep.py v3`, curl, `1rpc.io`, `lcd-dataseed.aioz.network`, CodeQL on `mediamtx`

## 1. SPA Catch-All 200 Trap (Expanded)

- `aioz.network` Next.js 23 chunks (903k), `explorer.aioz.network` 21 chunks (2.4M), `bridge.aioz.network` Vite `index-CMmtxisG.js` (500k), `wallet.aioz.network` similar.
- Every `GET /api/*`, `/admin`, `/swagger`, `/graphql`, `/.env` probes returned **200 `text/html` <!DOCTYPE** on wallet/bridge — Next.js fallback. `web2-deep.py v3` flagged 13 🔥 on `explorer.aioz.network` but all were HTML decoys.
- **Real JSON APIs only on backend domain `api-explorer.aioz.network`:** 4 endpoints `200` JSON (`/api/status` `{"success":true,"total_block":24755k,"total_transaction":3.1M}`, `/api/blocks`, `/api/transactions`, `/api/token/aioz/all` 200 with token list `0x492...MGD` etc.); rest (`/api/admin`, `/api/auth/login`, `/swagger`, `/graphql`, `/api/debug/vars`, `/api/env`) → `404 {"message":"Not Found"}` or `403 Cloudflare` for `/.env`.
- **Discovery:** `grep -oE 'https://[^\s"'`]'` on chunks leaked: `api-explorer`, `api-depin-monitor` (404 private), `pricing-data` (404), `nft-data`, `eth-dataseed.aioz.network` (`eth_blockNumber 0x179bcb7` ~24M), `lcd-dataseed.aioz.network` (height `24755381`), `wallet.aioz.stream`, `rpc-proxy.aioz.services/rpc?q=`. Main-domain probe misses these — always dump chunks first.
- **Rule:** `200` alone is worthless. Validate `Content-Type: application/json` + `{"success":true}`. `explorer.aioz.network/swagger` returned HTML 200 but `api-explorer/swagger` is `404 Not Found` — opposite domains matter.
- **Explorer server code `server/main.go:179`:** `//auth := middleware.NewAuthRepo`, `//e.Use(mdl.Authorize)` commented + `CORS AllowOrigins *` — unauth but not exploitable for admin; paired with `mediamtx` RCE chain earlier (`externalcmd/cmd.go:45 os.Expand($MTX_QUERY)` → `shellquote.Split` → `exec.Command`, `path_test.go:284` `sh -c 'echo "$MTX_QUERY"'`).

## 2. `rpc-proxy.aioz.services/rpc?q=URL` — Open Proxy vs Internal SSRF Matrix

| `q` | Response | Meaning |
|---|---|---|
| `https://example.com`, `https://api-explorer.../api/status` | `Example Domain` HTML / `{"success":true}` JSON ✅ | open proxy fetches public internet |
| `http://google.com`, `http://aioz.network` | `301 Moved` / Next.js HTML ✅ | same |
| `http://127.0.0.1:80/3000/8080/1317/8545/26657/9090/9997`, `::1:3000` | `dial tcp 127.0.0.1:XX: connection refused` | container has no localhost listeners |
| `http://10.0.0.1:80`, `172.17.0.1:80` | `connection refused` / empty | private net unreachable |
| `http://169.254.169.254/latest/meta-data/` | `not found` | no AWS IMDS |
| `http://metadata.google.internal/...` | `no such host` (67.207.67.3) | no GCP |
| `http://internal.aioz.network` | `no such host` | no internal DNS |
| `http://127.0.0.1:2375/v1.24/...`, `file:///etc/passwd` | `connection refused` | no Docker, no file handler |
| URL-encoded `http://127.0.0.1%2Fapi%2Fadmin`, `http://%30%2E%30%2E%30%2E%31:3000` | not decoded, treated literal | no decode bypass |

Payload list throttled 0.6–0.7s. Hidden-admin brute 20 paths (`/api/admin`, `/api/auth/login`, `/swagger`, `/graphql`, `/.env`, `/api/debug/vars` etc.) all 404/HTML. Only `/api/status` real.

**Classification:** **Public CORS-bypass proxy** for `wallet.aioz.network` (`?q=https://rpc.osmosis.zone`, `?q=https://rpc.cosmoshub...`), **not VPC/internal SSRF**. `connection refused` = pod empty, not WAF `403`. Reporting "SSRF to admin" on external-success alone is false positive. True internal SSRF requires `127.0.0.1:8545` → `{"jsonrpc":...}` or `169.254` → `ami-id`.

## 3. Firebase

- `explorer.aioz.network` → `aioz-blockchain` (`AIzaSy…ytvc`), `wallet` → `wallet-cbada` (`AIzaSy…qerI`) — public config from chunks. Not secrets; triage via open Firestore rules / Storage `storage/` exploit, not key report.
- XSS sinks `dangerouslySetInnerHTML` / `innerHTML` in chunks — no verified user-controlled path in this hunt.

## 4. $AIOZ Token — Capped Ownable (Same Bytecode Both Chains, 3747 bytes, 30 selectors, Not Proxy)

**Selectors decoded via `cast 4byte`:** `name 06fdde03`, `symbol 95d89b41`, `decimals 313ce567`, `totalSupply 18160ddd`, `balanceOf 70a08231`, `transfer a9059cbb`, `transferFrom 23b872dd`, `approve 095ea7b3`, `allowance dd62ed3e`, `increaseAllowance 39509351`, `decreaseAllowance a457c2d7`, `mint 40c10f19`, `burn 42966c68` (self-only), `owner 8da5cb5b`, `transferOwnership f2fde38b`, `renounceOwnership 715018a6`.

Error strings (bytecode grep): `ERC20: transfer amount exceeds balance/allowance/below zero`, `AIOZ Token: mint more than the max total supply`.

**Storage (eth_getStorageAt):** `slot 2` totalSupply (ETH `0x01ea328741fa7284cd040000` = 592,612,265 AIOZ, BSC `0x053bcfe0854613c89180000` = 101,233,334), `slot 6` `_maxTotalSupply` = `0x033b2e3c9fd0803ce8000000` = **1_000_000_000 * 1e18 = 1B cap per chain**, `slot 5` owner.

Source `erc20-contracts/main/contracts/AIOZToken.sol` matches bytecode:

```
_maxTotalSupply = 1000000000e18;
function mint(address,uint) public onlyOwner { require(totalSupply()+amount <= _maxTotalSupply); _mint(account,amount); }
function burn(uint) public onlyOwner { _burn(msg.sender,amount); } // NOT burnFrom
```

Constructor mints via `TimelockFactory`: paid ignition `0x0765...658` 10.3M, private sales `0xF847...af2` 73M (25% instant + 75% lock 30d), team `0x82E8...29b` 250M lock 180d, advisors `0xBbf7...F0F` 50M lock 90d, marketing `0x9E2F...1E9` 30M, ecosystem `0xCFd6...F1e`.

**Owners:** ETH `0x62e8Af11426E49d84c77f95238377732Ea9b366A` (EOA, nonce `0x47`, balance 0), BSC `0xb7c83128b786825ee3e8b8Be95325aFC9a585b9d` (different EOA) — not multisig, not contract (`eth_getCode 0x`).

**Drain surface:** No `pause/blacklist/burnFrom/selfdestruct`. Admin can only `mint` remaining `~408M` ETH / `~898M` BSC → dump on Uniswap/Pancake. Requires owner EOA compromise (phishing/GitHub leak/malware clipboard), not pre-auth remote. `transferOwnership` instant, no timelock. Report as **centralization HIGH**, not infinite-mint RCE.

**Valuation:** CG `aioz-network` price $0.048, MC $61M (#365), FDV ~$61M (1.26B/1.27B circ 99%), 24h vol $2.6M, ATH $2.65. Theoretical mint-dump 400M*0.048=$19M but thin DEX liquidity → slippage.

**Bridge:** `bridge.aioz.network/assets/index-CMmtxisG.js` `eth_getCode` on all `0x...40` candidates = `0x` — no on-chain `lock-and-mint` bridge contract; custodial off-chain relayer. `eth-dataseed` (`eth_blockNumber 0x179bcb7`) + `lcd-dataseed` (height 24.7M) are real RPCs but not bridge contracts.

## 5. GitHub 40 Repos — Clean (No Auth Token)

- Real: `aioz-explorer` (7★ 12 forks), `erc20-contracts`/`bep20-contracts` (token source), `mainnet` (`aioz_168-1/genesis.json.gz` 17k). Rest ML papers/stubs (`w3s-gateway` 4-file README, `aioz-node` 4 files).
- Direct `.env` via `raw.githubusercontent.com/AIOZNetwork/<repo>/main/.env` + `api.github.com/contents/.env` for `aioz-node/w3s-gateway/aioz-depin-cli/mediamtx` → `404 Not Found`. `truffle-config.js` = `127.0.0.1:8545` default. Code search `PRIVATE_KEY/0x...64/password/api_key/mnemonic` → `401 Requires authentication` unauth. Need `GITHUB_TOKEN` for history + commits diff (`3b426ab initial commit` only). Without token, can't claim full clean on private history.

## Repro

```bash
# Chunks -> real backends
curl -sk https://explorer.aioz.network/_next/static/chunks/*.js 2>&1 | strings | grep -oE 'https://[^" '`]*' | grep -i aioz | sort -u
# Proxy matrix
curl -sk "https://rpc-proxy.aioz.services/rpc?q=https://example.com" | head -c 300
curl -sk "https://rpc-proxy.aioz.services/rpc?q=http://169.254.169.254/latest/meta-data/"  # not found
curl -sk "https://rpc-proxy.aioz.services/rpc?q=http://127.0.0.1:8545"  # connection refused
# Token
curl -sk https://1rpc.io/eth -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["0x626e8036deb333b408be468f951bdb42433cbf18","latest"],"id":1}' | python -c "import json,sys; print(len(json.load(sys.stdin)['result'])//2)"
curl -sk https://1rpc.io/eth -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0x626e8036deb333b408be468f951bdb42433cbf18","data":"0x8da5cb5b"},"latest"],"id":1}'
# Native supply
curl -sk https://lcd-dataseed.aioz.network/cosmos/bank/v1beta1/supply | head -c 800
```

## Pitfalls to Avoid

- 200 HTML ≠ endpoint; always `Content-Type` + body check. Count real JSON only.
- External open proxy ≠ internal SSRF; `connection refused` on localhost is pod-empty, not filtered.
- Capped mint 1B + `burn` self-only = centralization HIGH, not infinite-mint. Don't report as pre-auth drain without owner key.
