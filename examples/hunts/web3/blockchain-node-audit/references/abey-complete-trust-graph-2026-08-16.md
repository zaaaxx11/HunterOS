# Abey Complete Trust Graph — First-Principles Sweep 2026-08-16 (Agent-1 ARCHITECT)

Source: local `/tmp/abey/go-abey` (807 Go, 131k code), `/tmp/abey/abey-wallet*` (210 Dart), `params/bootnodes.go`, `rpc/`, `core/vm`, `abey/tracers`, live `https://rpc.abeychain.com` (ChainID 179), testrpc 178, singlenode 176. Duration >30min, 6-surface parallel enum, mutual audit via `/tmp/abey_side_report/*.md`.

## Trust Boundary Map
```
[INTERNET] --HTTP/WS/IPC--> [rpc.Server/node.Node] --> [Registry] --> [Namespaces]
                                 |                          |- admin (Public+Private) -> addPeer/RemovePeer/nodeInfo
                                 |                          |- debug (Handler private + PublicDebugAPI public) -> **FILE-WRITE**
                                 |                          |- abey/eth (Public) -> AbeychainAPI/MinerAPI/downloader/filters
                                 |                          |- miner (Private) -> Start/Stop/Set*
                                 |                          |- net (Public)
                                 |                          |- personal (Private via internal/abeyapi) -> Unlock/Import/Sign
                                 |                          |- txpool/fruitpool/les
                                 |- [p2p :30313 rlpx+discv4/5] -> bootnodes hardcode -> dial fallback
                                 |- [consensus tbft+election + core/genesis singlenode <redacted-prefix>]
                                 |- [core/vm + tracers duktape JS Eval]
                                 |- [accounts/keystore]
[WALLET Dart] --HTTP--> [Base_Url http://54.255.45.202:8010] -> ApiManager.postConfigStatic -> Global.E_RPC.* hijack
       |- sqflite abey_identity/abey_coin (BeeEncryption md5(authKey+SEED+UDID))
       |- SharedPreferences plaintext
[SAFE fork] -> Executor DelegateCall + ModuleManager.execTransactionFromModule (no AllowAny string, semantic AllowAny via missing guard)
```

## RPC Registry
- `node/node.go:276-313` `handler.RegisterName(api.Namespace, api.Service)` branches on `Public` bool.
- `node/node.go:11-37 apis()` admin(debug.Handler Private) debug(PublicDebugAPI) web3
- `abey/backend.go:319-362` abey/eth x2 Public, miner Private, admin Private, debug Public+Private, net Public
- `internal/abeyapi/backend.go:103-162` abey/eth/txpool/fruitpool/debug/public, debug/private, personal Private, impawn

## Critical Sinks (file:line)

| Sink | File:Line | Gate | Impact |
|------|-----------|------|--------|
| `writeProfile os.Create(expandHome(file))` | `internal/debug/api.go:210-218` | debug in HTTPModules | **HIGH file-write** pre-auth |
| `StartCPUProfile os.Create` | `internal/debug/api.go:98-115` | same | holds cpuW |
| `ExportChain os.OpenFile CREATE\|WRONLY\|TRUNC` | `abey/api.go:328` | admin private -> becomes public if admin in modules | arbitrary overwrite |
| `ImportChain os.Open + InsertChain` | `abey/api.go:360` | same | file read + chain injection |
| `UnlockAccount TimedUnlock` | `internal/abeyapi/api.go:457` default 300s max MaxInt64 | personal private | indefinite unlock -> Sign |
| `ImportRawKey/NewAccount` | `internal/abeyapi/api.go:445,430` | personal | key ingestion |
| `SendTransaction/Sign*` | `internal/abeyapi/api.go:499-628` | personal | tx signing if unlocked |
| `SetElection/SetEtherbase` | `abey/api.go:284-310` | miner private | consensus hijack |
| `DumpBlock RawDump` | `abey/api.go:421` | debug public if enabled | DoS |
| `duktape EvalString(code)` | `abey/tracers/tracer.go:415` `tracer.go:310 New` | debug | JS -> DoS/escape |
| `Base_Url http` | `abey-wallet/lib/common/constant.dart:5` | wallet | MITM |
| `E_RPC hijack` | `abey-wallet/lib/common/global.dart:121-288` `postConfigStatic` | wallet | RPC redirect |
| `md5(authKey+SEED+UDID)` | `abey-wallet/lib/utils/common_util.dart:60` | wallet | weak KDF |
| `singlenode priv <redacted-prefix>` | `core/genesis.go:617-638` | `--singlenode` | committee takeover |
| `MainnetBootnodes 3.66.27.8:30313` | `params/bootnodes.go:22` | p2p | eclipse single AWS |
| `P2P :30313` | `node/defaults.go:51` | p2p | public default |
| `Safe DelegateCall` | `safe-smart-account/contracts/base/Executor.sol:28` | EVM | missing guard |

## Config Flags
- `cmd/utils/flags.go:770 setHTTP/setWS` -> `RPCListenAddr/Port/Api/CORSDomain/VHosts`, `WS*`, `IPC*`
- `cmd/utils/flags.go:492 --bootnodes` overrides hardcode
- `cmd/utils/flags.go:1100 SetAbeychainConfig` `--singlenode -> cfg.NodeType=true`
- `node/defaults.go:30-42` DefaultHTTPHost localhost:8545 safe, but `--rpcaddr 0.0.0.0` flips boundary

## Bootnodes
- Mainnet 6 enodes lead `3.66.27.8:30313` Frankfurt AWS, fallback in `p2p/dial.go:201` when `len(peers)==0 && needDynDials>0 && now.Sub(start)>fallbackInterval`
- Testnet 4x `10.0.196.x:30313` private leak, Devnet 4x `127.0.0.1:30501` etc, DiscoveryV5 2x `39.98.x`

## Wallet Crypto
- `constant.dart SEED_ABC` hardcode, `global.dart DEVICE_UDID md5(Uuid.v1)`, `getKey=md5(authKey+SEED+UDID)`, `BeeEncryption.encryptString`
- `chain_util.dart:saveIdentity` encrypts mnemonic/keystore/privateKey with user password via `getTokenId=md5(SEED+text+SEED)` -> offline brute-force
- `preferences_util.dart` SharedPreferences plaintext, `coin_model.dart/identity_model.dart` String in heap

## Blind-Spot Scanner Fixes
- Model `Public` bool + `HTTPModules` whitelist, not just `os.Create`
- Taint through `expandHome` + `filepath.Clean` still allows `../../` and `~/`
- Admin sinks not in `debug` grep
- Duktape user `code` param from `debug_trace*`, one-hop -> two-hop `Base_Url -> E_RPC`
- MD5 KDF mis-classified as crypto
- Hardcoded `<redacted-prefix>` in genesis comment, needs `--singlenode` context
- Bootnode IP not flagged, DelegateCall needs guard analysis not string search

## Verification
- `make gabey` clean, `rpc_modules` live differs from code defaults -> always probe live `eth_rpcModules`
- `debug_writeMemProfile /tmp/pwn` succeeds, `/root/.ssh` fails (non-root) -> HIGH DoS not RCE unless root/cron
- `debug_stacks` info leak, `admin_datadir` path disclosure

Source artifact: `/tmp/abey_side_report/architect_trust_graph.md` (27KB, Agent-1)
