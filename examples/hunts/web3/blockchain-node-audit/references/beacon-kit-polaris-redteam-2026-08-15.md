# Beacon-Kit + Polaris Red-Team — 2026-08-15

Source: `/tmp/extract/beacon-kit-main` (58M, `go.mod` 273 lines) + `polaris-main` (4.5M, `go.work` 8 dirs) on TencentOS 4. `git clone` fails (`git-remote-https` missing in `/usr/local/libexec/git-core`); used `curl -L https://github.com/berachain/beacon-kit/archive/refs/heads/main.tar.gz` + `tar -xz -C /tmp/extract` (polaris: `main.tar.gz` 799K). Session report: none saved (red-team directive: report ONLY exploitable file:line).

## Findings

| # | Title | Severity | Entry | File:line | Exploit |
|---|-------|----------|-------|-----------|---------|
| 1 | Unauthenticated Beacon Node-API 60+ routes | HIGH* | unauth | `node-api/middleware/middleware.go:29-40` `NewDefaultMiddleware` → only `CORSWithConfig(DefaultCORSConfig)` + `CustomValidator`; `node-api/server/server.go:80-97` `RegisterRoutes` for beacon/debug/proof/cometbft/validator/builder/config/node; `grep -rn auth node-api` → only mocks | `curl http://victim:3500/eth/v1/beacon/states/head/validators` etc. Mitigated by `node-api/server/config.go:24` `defaultAddress=127.0.0.1:3500` + `Enabled:false`; becomes HIGH when operator flips to `0.0.0.0`+`Enabled:true`. |
| 2 | Debug full-SSZ state dump | MEDIUM/HIGH | unauth | `node-api/handlers/debug/routes.go:33` `GET /eth/v2/debug/beacon/states/:state_id` → `handlers/debug/state.go:15-35` `StateAndSlotFromHeight` → `GetMarshallable()` → `StateResponse{Data: beaconState, Finalized:true, ExecutionOptimistic:false}` | `curl .../eth/v2/debug/beacon/states/head` dumps full beacon state (validators, balances, randao) — MEV/targeting. No auth/pagination/cache. |
| 3 | `bkit/v1/proof/*` SSZ merkle DoS | MEDIUM | unauth | `node-api/handlers/proof/routes.go:20-40` `block_proposer|validator_pubkey|validator_credentials|validator_balance :timestamp_id :validator_index` → `merkle.Prove*InBlock` | Spam `timestamp_id=head&validator_index=0` to burn CPU (SSZ merkleization). |
| 4 | Wildcard CORS | MEDIUM | N/A | `node-api/middleware/middleware.go:39` `DefaultCORSConfig` (`AllowOrigins:*`); `polaris/eth/node/node.go:68-78` `DefaultGethNodeConfig()` `HTTPHost=0.0.0.0` `WSHost=0.0.0.0` `HTTPCors=["*"]` `WSOrigins=["*"]` `HTTPVirtualHosts=["*"]` | Any site → `fetch(http://victim:3500/...)` / `http://victim:8545` `eth_sendTransaction`. Requires victim with wallet/session on same host. |
| 5 | Nil `JWTSecret` panic (DoS) | MEDIUM | local | `primitives/net/jwt/jwt.go:78` `HS256 {iat: now}` (no `exp`, no `none` → not alg bypass); `execution/client/ethclient/rpc/header.go:27` `rpc.jwtSecret.BuildSignedToken()` nil deref; `node-core/components/engine.go:42` `optional:"true"` + `components/jwt_secret.go:42` `ProvideJWTSecret` | Start with `jwt-secret-path=/nonexistent` → `ethclientrpc.NewClient(nil)` → `Initialize()` panic → crash loop. |
| 6 | Polaris JWT not wired (auth bypass*) | HIGH* | unauth if `auth-addr` exposed | `polaris/cosmos/config/config.go:471` reads `polaris.node.jwt-secret` into `conf.Node.JWTSecret` (embedded `node.Config`) but no assignment to geth `node.Config.JWTSecret` found; `cosmos/config/template.go:297` `jwt-secret=""` `e2e/testapp/docker/local/config/app.toml:497` `jwt-secret=""` | If auth RPC binds non-loopback without JWT, Engine API (polaris geth) unauth. `*` because not proven wired — needs `grep -rn "JWTSecret" eth --include="*.go"` verification on live config. |
| - | Engine API hijack — NOT a finding | — | — | `beacon-kit/execution/client/ethclient/engine.go` only **calls** `engine_newPayloadV*`/`forkchoiceUpdated*` via `rpc.Client.Call`; no `engine_*` server. | Hunting should target `bera-reth` Rust `BerachainEngineApi::new_payload_v4_p11` (`src/engine/rpc.rs`). Avoid false `engine/` admin. |
| - | JWT `none` alg / hardcoded secret — NOT exploitable | — | — | `primitives/net/jwt/jwt.go:35` `HexRegexp=^(?:0x)?[0-9a-fA-F]*$` matches `""`/`"0x"` but `hex.ToBytes→IsValidHex` rejects; only test `testing/files/jwt.hex:1` `0xc4d70beb...` | No prod hardcoded `jwt.hex`. |

## Recon anchors (beacon-kit Go)

```bash
grep -rn "CORSWithConfig\|CustomValidator\|RegisterRoutes" beacon-kit/node-api --include="*.go"
grep -rn "GetState\|Prove.*InBlock" beacon-kit/node-api --include="*.go"
grep -rn "JWTSecret.*optional\|ProvideJWTSecret\|jwtSecret\|BuildSignedToken" beacon-kit --include="*.go" | grep -v pb.go
grep -rn "engine_newPayload\|forkchoiceUpdated" beacon-kit/execution --include="*.go"   # = client, not server
grep -rn "DefaultGethNodeConfig\|HTTPHost\|HTTPCors\|WSOrigins" polaris/eth --include="*.go"
# tarball fallback when git-remote-https missing (TencentOS 4)
curl -L https://github.com/berachain/beacon-kit/archive/refs/heads/main.tar.gz -o /tmp/bk.tar.gz
curl -L https://github.com/berachain/polaris/archive/refs/heads/main.tar.gz -o /tmp/polaris.tar.gz
tar -tzf /tmp/bk.tar.gz | head ; tar -xzf /tmp/bk.tar.gz -C /tmp/extract
```

## Nuance

- Beacon API mutating routes (`POST /eth/v1/beacon/pool/*`, `/eth/v1/validator/*`) are mostly `NotImplemented`/`Deprecated` stubs (`handlers/beacon/routes.go` 60+ entries, only `GetGenesis`, `GetStateValidators`, `PostStateValidators`, `GetStateValidator`, `GetBlobSidecars`, etc. implemented) — limits direct state-manipulation impact to enumeration/DoS.
- `Enabled:false` + `127.0.0.1` default is a real mitigation; report unauth as HIGH only with `Enabled:true` + non-loopback deployment evidence (compose/k8s `ports:`).
