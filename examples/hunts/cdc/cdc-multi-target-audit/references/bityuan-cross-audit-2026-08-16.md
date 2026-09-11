# Bityuan 4-Auditor Cross-Audit — 2026-08-16

## Context
Second-order CDC after initial 4-agent hunt (ARCHITECT/RED/FUZZ/CHAINER) proved CORS * + loopback bypass but overstated remote RCE. User: `scan dengan 4 subagent, untuk saling audit` + `jelasin santai`. Spawned AUDITOR-1..4 to adversarially re-audit each claim: `Prove this ISN'T exploitable`.

## Wrapper vs Engine
- `bityuan/bityuan` = 39 files (14 Go), `bityuan.go` embedded TOML + `plugin/init.go` blank imports. Real surface = `33cn/chain33@v1.68.2` (659 Go) pinned via `go.mod:replace bysomeone/chain33@f4252a735f2d` + `33cn/plugin@1ef9e26f3e85` (1482 Go). Fetch via `codeload.github.com/.../zip/<commit>` when `git-remote-https` missing (TencentOS 4).

## Auditor Matrix

| Auditor | Scope | Key Files | Verdict |
|---|---|---|---|
| 1 RPC-AUTH | CORS + loopback + BasicAuth + whitelist | `rpc/http.go:38,56,60-102,159-169`, `rpc/server.go:171,198-214,551-640`, `rpc/ethrpc/rpc.go:143,215-268`, `bityuan.toml:76-91`, `rs/cors@v1.7.0/cors.go:123`, `geth/node/rpcstack.go:376` | CORS `*` FACT (both stacks), loopback skip FACT, empty BasicAuth FACT, `isLoopBackAddr` bug FACT but dead code, default `localhost` bind → remote blocked, CSRF `evil.com→127.0.0.1` PROVEN |
| 2 WALLET | DumpPrivkeysFile + GetSeed/DumpPrivkey gate | `wallet/wallet_proc.go:1599-1678`, `wallet/wallet.go:111,424`, `rpc/jrpchandler.go:616,830,958,968` | `os.OpenFile(fileName,0666)` 0 filepath sanitization CONFIRMED (TOCTOU + symlink + 0666), `checkWalletStatus` gates all sinks, content = encrypted `priv&label` not arbitrary bytes, needs `UnLock` password (no rate limit) |
| 3 VM | JS otto / WASM life / EVM | `plugin/dapp/js/executor/js.go:294,125`, `plugin/dapp/wasm/executor/resolver.go`, `exec.go:146` | JS `otto.Interrupt` exists but never wired → `while(true)` halt PROVEN DoS, WASM `Memory[keyPtr:keyPtr+keyLen]` OOB PROVEN, RCE NO |
| 4 BLIND-SPOT | P2P/webhook/jsonclient/store/pprof | `cmd/webhook/main.go:93`, `p2p/pubsub WithMessageSigning(false)`, `rpc/jsonclient/rpc_ctx.go`, `common/utils/ip.go`, `store/db` | 9 blind spots: webhook `make webhook` needs Makefile control, p2p unsigned gossip, CORS * on 8801/8546, pprof :6060, jsonclient InsecureSkipVerify |

## Consolidated Chain (Survives Adversarial)
**CORS * + loopback func-WL bypass → CSRF to privileged JRPC**
`evil.com fetch 127.0.0.1:8801` → `RemoteAddr 127.0.0.1 IsLoopback→true` → skip `checkIPWhitelist` fast-path + skip `checkJrpcFuncWhitelist/Blacklist` (`http.go:96`) + `checkBasicAuth` empty→true → `Chain33.UnLock→GetSeed/DumpPrivkeysFile/CloseQueue` + eth `personal_*` zero-auth.

**Impact:** PROVEN admin takeover / wallet drain (needs password weak/brute) / arbitrary file creation 0666 / node halt. THEORETICAL OS shell (needs writable cron + root, no gadget).

## Kill-Tests
```bash
curl -H Origin:http://evil.com http://127.0.0.1:8801 -d '{"method":"Chain33.GetWalletStatus","params":[{}],"id":1}' -i # Expect Access-Control-Allow-Origin:*
curl http://127.0.0.1:8801 -d '{"method":"Chain33.CloseQueue","params":[{}],"id":1}' # 200 IsOk (loopback bypass)
curl http://192.168.1.5:8801 -d '{"method":"Chain33.CloseQueue","params":[{}],"id":1}' # 403 Address not authorized (non-loopback blocked)
grep -rn "filepath\|Clean\|HasPrefix" wallet/wallet_proc.go # 0 → unsanitized
grep -n "os.Stat\|O_EXCL\|0666" wallet/wallet_proc.go # Stat before Lock + 0666 + no O_EXCL
grep -rn "Interrupt" plugin/dapp/js --include="*.go" # 0 wired
```

## Style Signal — Jelasin Santai Runtut
Formal dense report → user `jelasin santai`. Enforce 8-step warung narrative: 1) Target apa (cabang 39 vs pusat 659), 2) Kenapa pusat susah, 3) Pintu belakang (CORS spanduk), 4) Alur 6-langkah, 5) Bukti line, 6) POC curl/fetch, 7) Dampak jujur PROVEN vs THEORETICAL, 8) Fix. Tables + short paragraphs, `lo/gue 😘💕`, honest confidence.

## Fix
1. `rpc/http.go:38` explicit `AllowedOrigins` not `*`; 2. Remove `http.go:96` loopback skip; 3. `server.go:171` random default pass + eth adds `checkBasicAuth`; 4. `bityuan.toml:88` disable `personal`; 5. `wallet_proc.go:1615` `Clean+Base+allowDir+O_EXCL|O_NOFOLLOW+0600`; 6. JS `Interrupt+2s`, WASM bounds.

## Files
- `/tmp/audit_rpc.md` 26.7KB, `/tmp/audit_wallet.md` 23KB, `/tmp/audit_blindspot.md` 24KB, `/tmp/audit_vm.md` summary (iteration cap)
- Delegation `deleg_4ab1bd64` 493s
