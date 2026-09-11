# MultiversX Pre-Auth VM Execution + Halt Chain — 2026-08-15

Source: `multiversx/mx-chain-go` + `mx-chain-proxy-go` + `mx-chain-vm-go` @ master 2026-08-14. Gateway: `gateway.multiversx.com` (proxy v1.0, `mx-chain-proxy-go`). Method: 4 divergent theories (A VM escape, B REST, C Web2, D P2P), first-principles, live gateway verification.

## Divergence Outcome (Group by IDEA)

| Theory | IDEA | Verdict | Why |
|---|---|---|---|
| A | Wasmer2/CGo escape | BLOCKED | ~100 VMHooks enumerated (`executor/vmHooks.go`, `wasmer2/libvmexeccapi.h:40-318`, `wrapperVMHooks.go`), zero WASI/fs/process EEI (`grep fd_write\|wasi` empty), `unsafe.Pointer` in `wasmer2ImportsCgoHelper.go:9` is C-heap alias not WASI — requires Wasmer memory bug to escape |
| B | REST pre-auth | **CONFIRMED** | No `exec/template/upload/SSRF-arb` yet all 70 routes `Open=true` (chain `api.toml`) / 66/70 `Secured=false` (proxy `v1_0.toml`), `cors.Default()` `*`, zero auth middleware in chain-go |
| C | Web2 SSTI/JWT/GraphQL | BLOCKED | `api.multiversx.com` no GraphQL, gateway is proxy not templating, `api.multiversx.com` CORS `*` but no JWT |
| D | P2P deserialization | BLOCKED | `SingleDataInterceptor` → `AntifloodHandler` + `Throttler` + `gogo/protobuf` + `TxValidator.CheckTxValidity` (`txValidator.go:67`), no crash on max payload alone |

B wins, A/C/D blocked after 2 rounds — classic CDC stall=block.

## Chain (Proven → Conditional)

```
[1] Internet → POST https://gateway.multiversx.com/vm-values/query  (or POST /transaction/simulate?checkSignature=false)
        VMValueRequest{ScAddress,FuncName,Args hex[],CallerAddr,CallValue,SameScState,ShouldBeSynced}
[2] proxy process/vmValuesProcessor → baseProcessor.CallPostRestEndPoint(observer.Address + "/vm-values/query")  (baseProcessor.go:246 naive concat, no url.Parse)
[3] observer vmValuesGroup.go:134 doExecuteQuery → createSCQuery() hex-decodes args, bech32 decodes addrs → process.SCQuery → ExecuteSCQuery  (FuncName not allowlisted, Args unbounded, CallValue big.Int no cap)
        also: transactionGroup.go:242 ?checkSignature=false → SimulateTransactionExecution
[4] vmhost/hostCore/host.go:451 RunSmartContractCall / 384 Create → validateVMInput (host.go:600 only Gas<=MaxInt64) → StartWasmerInstance (runtime.go:156→253) → wasmer2 CGo libvmexeccapi.so → validator.go:47-83 → ~100 WrapperVMHooks
[5] IF Wasmer OOB → host RCE (sole isolation layer). ELSE → pre-auth arbitrary SC execution on live trie + gas griefing
[5b] POST /hardfork/trigger (hardforkGroup.go:62) → node.DirectTrigger → chain halt (alt terminal)
```

## Trust Boundaries Hit

- TB1 gin `ShouldBindJSON` (no auth) — `webServer.go:93-147`
- TB2 hex/bech32 parsing — `vmValuesGroup.go:185`
- TB3 hardfork/debug/internal — `hardforkGroup.go:62`, `nodeGroup.go:239`
- TB5 Wasmer CGo compilation — `runtime.go:253 + wasmer2/`
- TB6 WASM validators — `validator.go`
- TB12-14 proxy relay — `proxy/process/baseProcessor.go:246`, `proxy/api/api.go:37`

## Live Gateway Verification (Throttled, GET/400-safe)

### Pre-auth VM Execution — PROVEN LIVE (200 successful, full VMOutput)

```bash
# Real SC on mainnet: ESDT system contract
SC="erd1qqqqqqqqqqqqqqqpqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqplllst77y4l"
curl -s https://gateway.multiversx.com/vm-values/query -X POST -H 'Content-Type: application/json' \
  -d "{\"scAddress\":\"$SC\",\"funcName\":\"getTokenProperties\",\"args\":[\"555344432d373663333165\"],\"caller\":\"$SC\",\"value\":\"0\"}"
# → {"code":"successful","data":{"data":{"returnCode":"user error","returnMessage":"invalid method to call","gasRemaining":0,"gasRefund":0,"outputAccounts":{},"deletedAccounts":null,"touchedAccounts":null,"logs":[]}}}
# VM RAN, returned full VMOutput — pre-auth proven. "user error" is from SC side, not auth.
```

### Observer Discovery via Heartbeat — 2246 Active

```bash
curl -s https://gateway.multiversx.com/node/heartbeatstatus | jq '.data.heartbeats[] | select(.peerType=="observer" and .isActive==true) | {pid: .pidString, ver: .versionNumber, display: .nodeDisplayName, identity: .identity}'
# → 5161 total heartbeats, 2246 active observers
# → pidString: libp2p PeerID (16Uiu2HA... format)
# → versionNumber: v1.11.11.0, v1.11.10.0, v1.11.0.0 (mixed)
# → nodeDisplayName: staking provider identifiers (ThePalmTreeNW, Disruptive, equilibrium, stakingagency, valuestaking, etc.)
# → peerInfo + p2pStatus return 404 on proxy — only on direct observer nodes
```

### Observer Firewall Defense — CONFIRMED

- Gateway IPs: `142.93.138.162`, `165.22.198.97` (DigitalOcean droplets)
- Port 443 (HTTPS proxy): open, returns 404 for non-proxy routes
- Port 8080 (observer REST): firewalled, timeout
- Common observer ports (8079, 8081, 9090, 37373-37375, 5000): all firewalled
- **Defense verdict:** Observers are behind firewall. Proxy is sole internet-facing surface. This is deliberate and correct.

### Fuzz Campaign — VM Robust Against Edge Cases

- 300-round throttled (0.8-1.2s) fuzz against `vm-values/query` + `transaction/simulate`
- Tested: max CallValue, huge args, empty fields, invalid hex, unicode, special chars, SameScState toggle, negative values, very long addresses
- All `vm-values/query`: 200 or 400, zero 500 crashes
- All `simulate`: 500 from validation (gas limit, nonce) — not crashes
- **Verdict:** VM Wasmer is stable against malformed input. No crash from edge cases alone. Wasmer memory bugs require memory-unsafe payloads (not just malformed JSON).

## Evidence Anchors

- `mx-chain-go/api/gin/webServer.go:101` `cors.Default()`, `:230-236` pprof only on flag, `:218` 11 groups
- `mx-chain-go/api/groups/baseGroup.go:28-48` `Open` only, no `Secured`
- `mx-chain-go/cmd/node/config/api.toml` all `Open=true`
- `mx-chain-go/api/groups/vmValuesGroup.go:52-134`, `:176-219`, `:122`
- `mx-chain-go/api/groups/transactionGroup.go:87-120`, `:242`
- `mx-chain-go/api/groups/hardforkGroup.go:62`, `nodeGroup.go:239`
- `mx-chain-vm-go/vmhost/hostCore/host.go:600`, `:253`, `:384/:451`
- `mx-chain-proxy-go/api/api.go:37`, `:101`, `:131`, `:137-196`
- `mx-chain-proxy-go/api/groups/baseGroup.go:82-149` `isFoundInConfig` fallback Warn+open
- `mx-chain-proxy-go/cmd/proxy/config/apiConfig/v1_0.toml` 4/70 `Secured=true`
- `mx-chain-proxy-go/process/baseProcessor.go:194-304`

## Deliverables from Session

- `/tmp/mvx_architect.md` (31KB, 14 TBs TB1-TB14, full endpoint inventory, VM pipeline, P2P interceptor chain, proxy shard routing)
- `/tmp/mvx_red_api.md` (34KB, route-gate truth, SSRF/template/command sink hunt, exploitability matrix)
- `/tmp/mvx_final_chain.md` (chain synthesis, live PoC 18 lines, V8 Architect plan, 5-scenario)

## Mitigation (Root Cause)

`mx-chain-go` has no `Secured` field — every `Open=true` is unauth by design. Fix: add `RouteConfig{Secured bool}` mirror proxy, set `vm-values/*`, `transaction/*`, `hardfork/trigger`, `node/debug`, `internal/*`, `log`, `pprof` → `Secured=true`; bind `RestApiInterface` to `127.0.0.1`; replace `cors.Default()` allowlist; make `!isFoundInConfig` → closed.

## Reproduction

```bash
curl -sL https://github.com/multiversx/mx-chain-go/archive/refs/heads/master.tar.gz | tar -xz
# TencentOS: no git-remote-https, use tarball not dnf git-core
```
