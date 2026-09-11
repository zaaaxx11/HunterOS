# Exhaustive Weakness Sweep — eBridge 2026-08-15

## Trigger
User: `pokoknya cari weakness aja, semua di sisir, spawn 4 agent untuk saling audit`
→ 4-agent exhaustive sweep, not per-target CDC.

## Roles

| Agent | Scope | Checks |
|-------|-------|--------|
| A API/Web2 | `ebridge-server/src/HttpApi` + `aelf web2s` | anon GETs (`CrossChainTransferController.cs:18` no Authorize), CORS `*` (`appsettings.json CorsOrigins`), hardcoded secrets (`MySQL Pwd 123456`, `RabbitMQ admin/123456`, `Redis 127.0.0.1`, `StringEncryption Or7FKveUF7w9PuVs`, `Swagger 1q2w3e*`), Swagger `swagger.json` (27 paths), IDOR address enum, Elasticsearch `GetListAsync` filter injection, rate limit missing |
| B Contract | `EBridge.Contracts.Bridge/*.cs` (1906L) + `TokenPool` | every `Assert` (Amount>0 Helpers:98/270, `Already claimed` 110, `Sender==Admin` 26/118, `leafHash` Ramp:84-85), unchecked math (15× `.Add/.Sub/.Mul/.Div` vs `+`), reentrancy (`TransferFrom` before state), front-run `ChangeSwapRatio`, gas grief 30-digit → `ToInt64` throw, `Whitelist` bypass, `Pause` bypass, `CrossChainConfig` spoof |
| C Deploy/Ops | `appsettings.json`, `Dockerfile`, `nuget.config`, `Directory.Build.props` | `192.168.67.*:8000 http://` no TLS (`RequireHttpsMetadata true` but `ChainNodeApis http`), single Admin/Controller/PauseController, `Parliament/Association` org upgrade, `Serilog` leak, feed hijack |
| D Cross-audit filter | All A/B/C | Classifies each finding: **PROVEN fund theft** (pre-auth mint/drain) vs **PROVEN admin** vs **HYGIENE/info leak** vs **FALSE POSITIVE** (dead code `dailyLimit==null && bucket==null` at TokenSwap:61, blocked by `ToInt64` throw). Must explain why: `anon ReceiptId` ≠ mint (needs `RampContract` sender + `leafHash` + `ReceiptHashRecordStatus`), `IsValidAmount` lolos ≠ theft, `null limit` ⇒ frozen not unlimited |

## D Output Contract

Columns: `weakness | file:line | claimed impact | real impact | verdict OPEN/BLOCKED/HYGIENE`

Example filtered row:
```
IsValidAmount 19-digit lolos | Helpers.cs:98 | fund theft via overflow | gas grief revert | BLOCKED (ToInt64 throw at 129 + checked Add at TokenSwap:89)
```

## Exhaustive Sweep Pitfall

- Don't report `appsettings.json` `123456` as **prod fund theft** — it's `appsettings.json` dev default, not `appsettings.Production.json`. Hygiene unless proven in live `/swagger` or env.
- `ebridge-server` `BridgeContract.g.cs` (12480L) is stub — must cross-check against `ebridge-contracts.aelf:dev` real `EBridge.Contracts.Bridge` (63 .cs, 1906L) before claiming.
- `CHAINER BLOCKED` ≠ `no weakness` — daily-limit frozen is DoS, not theft, but worth reporting as governance risk.

## References

- Deleg `deleg_830a0806` (A/B/C/D)
- Prior: `aelf-ebridge-fuzz-2026-08-15.md`, `aelf-ebridge-real-contract-2026-08-15.md`, `ebridge-chainer-blocked-chain-20260815.md`
