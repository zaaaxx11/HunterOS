# Bityuan / Chain33 (bysomeone fork) Trust Graph — 2026-08 Case Study

> Source: `bityuan/bityuan` wrapper (14 Go files) pinned to `bysomeone/chain33@f4252a735f2d` + `bysomeone/plugin@1ef9e26f3e85` via `bityuan/go.mod:7-9`. Material at `/tmp/chain33` (659 Go files) + `/tmp/plugin` (1482 Go files). Analysis is static grep + targeted file reads; no live node.

## Architecture (what bityuan actually is)

- `bityuan/main.go` imports `_ "github.com/33cn/chain33/system"` + `_ "github.com/bityuan/bityuan/plugin"` and calls `cli.RunChain33("bityuan", bityuan)` where `bityuan` is `var bityuan = fmt.Sprintf(...)` TOML string in `bityuan/bityuan.go:9`. All consensus/p2p/mempool/executor/wallet/rpc/crypto/store comes from the two forks.
- Only wrapper content: `bityuan.toml` (dev `singleMode`/`disableShard=false` false path) vs `bityuan-fullnode.toml` (`isFullNode=true`, `isRecordBlockSequence=true`, shard prune enabled), plus `plugin/init.go` blank-importing `consensus/crypto/dapp/mempool/p2p/store` init pkgs and `cli/main.go`.
- Config merges: `types/cfg.go:275 RPC struct` + `types/defaultcfg.go:91` defaults + `bityuan.go` embedded `[fork.system]` 15 gates + per-dapp forks (e.g. `ForkAccountBlacklist=46561600`).

## 4 Listeners on one process

| # | Listener | Bind source | Code |
|---|----------|-------------|------|
| 1 | JRPC `localhost:8801` (JSON-RPC over HTTP via `net/rpc/jsonrpc`) | `rpcCfg.JrpcBindAddr` (`types/cfg.go:277`, default `localhost:0`) overridden to `localhost:8801` in both `bityuan*.toml` | `rpc/http.go:35 net.Listen("tcp",rpcCfg.JrpcBindAddr)` + `cors.New(cors.Options{})` (parent `*`) |
| 2 | gRPC `localhost:8802` | `rpcCfg.GrpcBindAddr` | `rpc/server.go:264 NewGRpcServer` + `grpc.UnaryInterceptor(auth)` at `server.go:271` + `reflection.Register` at `server.go:297` |
| 3 | ethRPC HTTP `localhost:8546` | `rpc.sub.eth.HTTPAddr` (`ethrpc/rpc.go:55 subConfig`) | `ethrpc/rpc.go:136 EnableRPC` → `node.NewHTTPHandlerStack(...["*"],["*"])` at `rpc.go:143` → `rpc.go:140 net.Listen` |
| 4 | ethRPC WS `localhost:8547` | `rpc.sub.eth.WsAddr` | `ethrpc/rpc.go:148 EnableWS` → `WebsocketHandler([]string{"*"})` at `rpc.go:154` |

Operator knob `jrpcBindAddr=0.0.0.0:*` / `grpcBindAddr=0.0.0.0:*` + `whitelist=["*"]→remoteIPWhitelist["0.0.0.0"]=true` at `server.go:543` makes all four public.

## Auth stack and the loopback bypass (critical)

Order for JRPC (`rpc/http.go:40-107`): `checkIPWhitelist` → `checkBasicAuth` → `parseJSONRpcParams` → **if not loopback** `checkJrpcFuncBlacklist || !checkJrpcFuncWhitelist` → `ServeRequest`. For gRPC (`rpc/http.go:159-187 auth` → `server.go:271` interceptor):

- `server.go:193 checkIPWhitelist`: `if ip.IsLoopback() return true` + `if remoteIPWhitelist["0.0.0.0"] return true`
- `server.go:171 checkBasicAuth`: `if JrpcUserName=="" && JrpcUserPasswd=="" return true` (default config has no creds)
- `server.go:212 checkJrpcFuncWhitelist`: default `["*"]` → `jrpcFuncWhitelist["*"]=true` at `server.go:568` if empty; similarly `server.go:582 InitGrpcFuncWhitelist`.
- `server.go:598 InitJrpcFuncBlacklist`: default only `["CloseQueue"]` if empty. `bityuan-fullnode.toml:50` lists 12 wallet methods; `bityuan.toml` lists none.
- **Bypass 1 — `rpc/http.go:96`**: `ipaddr:=net.ParseIP(ip); if !ipaddr.IsLoopback() { if checkJrpcFuncBlacklist(...)||!checkJrpcFuncWhitelist(...) writeError }` — loopback skips func WL/BL. The JRPC handler still checks `checkIPWhitelist` + `checkBasicAuth`, but loopback always passes `checkIPWhitelist` per above.
- **Bypass 2 — `rpc/http.go:169 isLoopBackAddr`**: `if ipnet,ok:=addr.(*net.IPNet); ok && ipnet.IP.IsLoopback() return true` → `auth:169 if isLoopBackAddr(getctx.Addr) return nil` — gRPC skips both IP WL and `checkGrpcFuncValidity` on loopback. Bug: only handles `*net.IPNet`, not `*net.TCPAddr` from `peer.FromContext`.
- **ethRPC has no gate**: `ethrpc/rpc.go:215 ServeHTTP` only does `net.SplitHostPort` + `if utils.IsPublicIP(ip) log.Debug` (`common/utils/utils.go:109 IsLoopback||IsLinkLocal*` check used for logging only), then `h.httpHandler.ServeHTTP`. No whitelist/BasicAuth/func-WL call. `ErpcFuncBlacklist` (`types/cfg.go:294`) is defined but never checked.

Consequence: any loopback/SSRF reaches **84 JRPC + 80 gRPC (+2 streaming SubEvent/UnSubEvent at grpchandler.go:656/717) + CloseQueue node-kill at jrpchandler.go:1160** unauth. Remote with `whitelist=["*"]` or with the IP whitelisted reaches the same set minus the bypass distinction; under `bityuan.toml` that is all 84 remotely, under `bityuan-fullnode.toml` it is 72 remotely (12 blacklisted, but gRPC `checkGrpcFuncValidity` at `server.go:224` checks blacklist first so `CloseQueue` blocked remotely — yet loopback still bypasses).

## Dispatch — queue bus (not net/rpc)

- `queue.Client` + `types.Event*` constants (`types/event.go:9 EventTx=1, 38 EventWalletAccountList, 42 EventWalletExecutor, 193 EventAddBlacklist...`). `client/queueprotocol.go:495 ExecWalletFunc("wallet", WalletGetAccountList, req)` → `queue.Send(NewMessage("wallet", EventWalletExecutor, param))`.
- No ACL on the bus; RPC layer is the sole gate before `wallet_msg.go:14 ProcRecvMsg` / `executor/executor.go:197 procExecQuery`.

## RPC method inventory (what loopback gets)

- **JRPC 84** — `rpc/jrpchandler.go:24-1702`: `CreateRawTransaction(24)`, `ReWriteRawTx(49)`, `CreateRawTxGroup(67)`, `CreateNoBlanaceTxs(78)`, `CreateNoBalanceTransaction(89)`, `SendTransaction(106)` [FromHex→Decode→SendTx], `SendTransactions(128)`, `SendTransactionSync(144)` (polls QueryTransaction 100×300ms), `GetHexTxByHash(167)`, `QueryTransaction(183)`, `GetBlocks(208)`, `GetLastHeader(227)`, `GetTxByAddr(259)`, `GetTxByHashes(283)`, `GetMempool(398)`, `GetAccountsV2(425)/GetAccounts(431)`, `NewAccount(451)/NewRandAccount(462)`, `WalletTxList(489)`, `ImportPrivkey(510)`, `SendToAddress(520)` [crafts+sends tx, needs unlock], `SetTxFee(534)`, `SetLabl(548)`, `GetAccount(560)`, `MergeBalance(573)`, `SetPasswd(588)`, `Lock(602)`, `UnLock(616)` [WalletUnLock{Passwd,Timeout} no rate limit], `GetPeerInfo(630)`, `GenSeed(806)`, `SaveSeed(816)`, `GetSeed(830)` [returns mnemonic plaintext], `GetWalletStatus(840)`, `GetBalance(857)`, `ExecWallet(897)` [wcom.QueryData.DecodeJSON(Driver,FuncName,Payload)→ExecWallet — generic], `Query(926)` [LoadExecutorType(Execer).CreateQuery(FuncName,Payload)→Query — generic], `DumpPrivkey(954)`, `DumpPrivkeysFile(964)` [takes {FileName,Passwd}], `ImportPrivkeysFile(978)`, `SignRawTx(1064)`, `CloseQueue(1160)` [go c.cli.CloseQueue() after 100ms — node shutdown], `QueryChain(1528)` [same as Query], `GetChainID(1559)`, plus `AddBlacklist/DelBlacklist/ShowBlacklist/DialPeer/ClosePeer` (~1580), `SendDelayTransaction`, `GetWalletRecoverAddress/SignWalletRecoverTx`, `GetChainConfig`.
- **gRPC 80+2** — `rpc/grpchandler.go:21-656` mirrors JRPC plus `QueryRandNum(520)`, `GetFork(529)`, `SubEvent(656)/UnSubEvent(717)` streaming (`server.go:62 subCache` fan-out of `EventPushEVM/TxReceipt/BlockHeader/Block/TxResult` at `server.go:436`). `reflection.Register` leaks method list.
- **ethRPC** — `ethrpc/eth/eth.go:48` (21 eth_* incl. `eth_accounts:252`, `eth_sendRawTransaction:317`, `eth_call:273`, `eth_sign:399`), `ethrpc/personal/personal.go:30` (5 personal_* : `ListAccounts`, `NewAccount`, `UnlockAccount:69→WalletUnLock`, `ImportRawKey:80`, `Sign:92→UnlockAccount then DumpPrivkey at line 99`), `ethrpc/admin/admin.go:32` (`Peers`, `Datadir` leaks `mcfg.BlockChain.DbPath`, `NodeInfo`), `ethrpc/net` + `web3` trivial. All unauth if port reachable.

## Wallet — highest-value target

- State: `wallet/wallet.go:52 Wallet{isWalletLocked int32, Password, walletStore}` init `isWalletLocked=1` at `wallet.go:110`; `IsWalletLocked:282` via `atomic.LoadInt32`; `GetWalletStatus:840` leaks status.
- Unlock: `wallet_proc.go:972 ProcWalletUnLock` → `VerifyPasswordHash` + `WalletUnLock.Passwd==Password` + `CAS 1→0` + `resetTimeout`.
- Sign race: `wallet_proc.go:869 ProcSignRawTx` does `CAS(1,0)` around sign then restores — window where other goroutine sees unlocked.
- Secrets: `wallet_proc.go:1353 ProcDumpPrivkey(addr)`, `1561 ProcDumpPrivkeysFile(fileName,passwd)` [FileName attacker-controlled], `wallet/seed.go:98 GetSeed` (AES-GCM decrypt of `[]byte("walletseed")` at `wallet/common/keys.go:21`), `seed.go:82 SaveSeedInBatch`.
- Eth bridge: `personal/personal.go:92 Sign` does `UnlockAccount` then `DumpPrivkey` — raw key in memory even though return is sig hex.

## P2P

- Dispatch: `p2p/event.go:24 handleSysEvent` → `EventTxBroadcast/BlockBroadcast→pub2All`, others → `pub2P2P`; return `event.go:89 PubBroadCast` → `EventTx→mempool` / `EventBroadcastAddBlock→blockchain` with `Send(...,true)`.
- Auth: `plugin/p2p/gossip/common.go:267 CheckSign(*P2PPing)` → `crypto.Load("secp256k1")` + `SignatureFromBytes`; called at `gossip/p2pserver.go:70,167,506,527,551`. Failure only logs. Gossipsub scoring via `p2p.sub.dht.pubsub` D=10 etc.; stream interceptor at `gossip/listener.go:84` is pass-through.

## Executor / plugin dispatch (generic RCE-adjacent)

- `types/executor.go:80 LoadExecutorType(execName)` global map from `types.RegisterExecutor` (each `system/dapp/*` + `plugin/dapp/*` init). `executor/execenv.go:167 IsAllowExecName` + `659 proxyExecTx` (EVM↔coins friend bridge when `proxyExecAddress="0x…200005"` gated by `ForkProxyExec=29528000`).
- `jrpchandler.go:926 Query` / `1528 QueryChain` / `897 ExecWallet` — generic: attacker picks any registered `Execer/Driver+FuncName` among `ticket, evm, token, trade, paracross, autonomy, rollup, privacy, mix, storage, ...` plus 12 extra `pluginmgr.AddRPC` gRPC services (`pluginmgr/manager.go:79` → each `plugin/dapp/*/rpc/types.go:32 RegisterXxxServer(s.GRPC(),grpc)`).
- EVM: `plugin/dapp/evm/executor/evm.go:87 InitExecType` + `exec.go:31 Exec` runs `go-ethereum v1.10.22` with `state.MemoryStateDB`. Gas cap `evmGasLimit` in `bityuan.go`.

## Dangerous patterns — killed / not present

- `exec.Command` only in `cmd/webhook/main.go:77 rm -rf/git clone --depth 50/make webhook` (separate binary, not linked into `bityuan` node) + `system/dapp/commands/send.go:63` client-side + build helpers. No runtime `template` (only `x509.Certificate{template}` var), no `yaml` on RPC path (only `cryptogen.go:45` local file), no `plugin.Open`, `unsafe` only perf (`queue/client.go:188 atomic.StorePointer(&client.topic,unsafe.Pointer)`, `types/types.go:624 String↔[]byte`), `reflect` only whitelisted `MsgMap byte→Type` at `plugin/consensus/*/peer_set.go:510` + `consensus/consensus.go:29`.

## How to fetch the pinned forks (git remote-https missing)

- Wrapper: `curl -L https://codeload.github.com/bityuan/bityuan/zip/refs/heads/master -o /tmp/bityuan.zip && unzip -q -d /tmp && mv /tmp/bityuan-master /tmp/bityuan`
- Fork commits from `go.mod:replace`: `curl -L https://codeload.github.com/bysomeone/chain33/zip/f4252a735f2d -o /tmp/chain33-fork.zip && unzip -q -d /tmp && mv /tmp/chain33-f4252a735f2d /tmp/chain33` (same for `plugin@1ef9e26f3e85`). Use `unzip -o` + explicit `mv` to avoid `/tmp/chain33-master` collisions. `file` + `unzip -l` validate the zip is not HTML. `find /tmp/chain33 -name "*.go" | wc -l` sanity check (659 chain33 + 1482 plugin).
- Clean: `rm -rf /tmp/chain33-f4252a735f2d /tmp/plugin-1ef9e26f3e85` after move. Avoid bare `rm -rf /tmp/chain33 /tmp/bityuan` without checking — the session `/tmp` accumulates evidence dirs.

## Hardening notes

Loopback bypass is the design bug; ethRPC zero-auth is the second. Fix: remove `IsLoopback` short-circuits, reuse `InitIPWhitelist+checkBasicAuth` on ethRPC, enforce `ErpcFuncBlacklist`, restrict `cors.New(cors.Options{AllowedOrigins: whitelist})`, gate `reflection.Register` behind `EnableTrace`, rate-limit `UnLock`, validate `DumpPrivkeysFile.FileName ∈ wallet/`, and fix gRPC `isLoopBackAddr` to handle `*net.TCPAddr`.

## References in workspace

- Full map with tables and mermaid: `/tmp/architect_map.md` (generated 2026-08-15, 54kB)
- Chain33 queue constants: `types/event.go`; RPC types: `types/cfg.go:275`; defaults: `types/defaultcfg.go`
