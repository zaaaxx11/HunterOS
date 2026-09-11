# Berachain Beacon-Kit + Polaris + Bera-Reth — Trust Graph Reference
Source: 2026-08-15 tarball inspection (`/tmp/bk_full/beacon-kit-main` 58M, `polaris-main` 4.5M, `bera-reth-main` 49M) — git `remote-https` missing, used `curl -sL .../archive/refs/heads/main.tar.gz | tar -xz`.
Report: `/root/Berachain_Trust_Graph.md` (34KB, 25+ boundaries)

## Architecture
- **beacon-kit (Go, CL)**: `node-api` (Echo) + `beacon/blockchain` (ProcessProposal/FinalizeBlock) + `beacon/validator` (BlockBuilder) + `state-transition/core` (StateProcessor) + `execution/{client,engine}` + `storage (IAVL)` + `consensus/cometbft/service` (ABCI++). Chain uses forked `berachain/karalabe-ssz v0.3.0-alpha.0` and `berachain/cometbft v1.0.1`.
- **bera-reth (Rust, EL, reth v1.11.4 fork)**: `jsonrpsee` Engine API (`newPayloadV1..V4P11`, `forkchoiceUpdatedV1..V3P11`, `getPayloadV1..V4P11`, `exchangeCapabilities`) + `BerachainEngineValidator` + `BerachainEngineTypes::block_to_payload` (rewrites PolTx `from=SYSTEM_ADDRESS`).
- **polaris (Go, EVM on Cosmos)**: `eth/core/vm` + `cosmos/x/evm` keeper + `lib/registry mapRegistry[Address]StatefulImpl` + `cosmos/precompile/{bank,distribution,staking,governance}` (EVM `msg.sender` → Cosmos signer without Cosmos sig).

## Trust Boundaries (unauth → auth → state)
| # | Boundary | Auth | Key File |
|---|----------|------|----------|
| A-1 | Beacon API 60+ routes (`/eth/v1/beacon/*`, `/eth/v1/validator/*`, `/eth/v1/builder/*`, `/eth/v1/debug/*`) — read-only but leaks validator set/balances/randao | UNAUTH, CORS `*` (`DefaultCORSConfig`) | `node-api/middleware/middleware.go:25-45`, `node-api/handlers/beacon/routes.go` |
| A-2..A-5 | Same Echo instance, no RateLimit/BodyLimit, `CustomValidator` tag checks (`state_id`, `block_id`, `validator_id`) only | UNAUTH | `node-api/middleware/request.go:75-150` |
| B-1 | Engine JWT CL↔EL: 32B hex file `./jwt.hex` → `HS256 {iat: now}` refresh 30s → `Authorization: Bearer` | JWT HS256 (symmetric, no `exp`) | `primitives/net/jwt/jwt.go:25-85`, `execution/client/ethclient/rpc/client.go:55-135` |
| B-2 | Secret file perm sole guard; `http://localhost:8551` no TLS, `http.DefaultClient` | file | `node-core/components/jwt_secret.go:18-35` |
| C-3 | `Blockchain.ProcessProposal` — SSZ `DecodeFromBytes` + `ValidateAfterDecodingSSZ` → fork version PBTS → KZG len/MaxBlobs → sidecar sig == block sig → BLS `DOMAIN_BEACON_PROPOSER` → `VerifySidecars` (KZG) → `StateProcessor.Transition` → `CacheLatestVerifiedPayload` LRU 10 | SSZ+BLS+KZG | `beacon/blockchain/process_proposal.go:30-220` |
| C-4 | `FinalizeBlock` — `WithinDAPeriod` → `ProcessSidecars` + `IsDataAvailable` → `CatchupFuluDeposits` → `executeStateTransition` → `BlockStore.Set` → `sendPostBlockFCU` dedup → `CacheLatestVerifiedPayload(nil)` | CometBFT SSF | `beacon/blockchain/finalize_block.go:20-200` |
| C-6 | SSZ codec: `SignedBeaconBlock.DefineSSZ` (`DefineDynamicObjectOffset(BeaconBlock)` + `DefineStaticBytes(Sig[96])`) → `Unmarshal[T]` → `ssz.DecodeFromBytes` → `ValidateAfterDecodingSSZ` | length prefix | `consensus-types/types/signed_beacon_block.go:50-110`, `primitives/encoding/ssz/utils.go:15-60` |
| E-2 | bera-reth `new_payload_v4_p11` — `validate_prague1_requirements(ts, BlsPublicKey)` → `is_prague1_active_at_timestamp` else `UnsupportedFork` → `BerachainHeader::from_header_with_proposer` → `validate_hardfork_fields(shanghai/cancun/prague/prague1)` → `hash == expected` | JWT+fork | `src/engine/rpc.rs:200-450`, `src/engine/validator.rs:30-140` |
| F-1 | Polaris `CALL precompileAddr(abi)` → `mapRegistry.Get(addr)` → `ABIMethods[selector]` → `bank.Contract.Send(ctx, to, coins)` → `banktypes.MsgServer.Send{from: evmCaller}` | EVM `msg.sender` ECDSA (no Cosmos Ante) | `cosmos/precompile/bank/bank.go:60-180`, `eth/core/precompile/base_contract.go` |
| F-3 | Reentrancy `Plugin.EnableReentrancy/DisableReentrancy` — precompile can callback `evm.Call` | flag | `eth/core/precompile/interfaces.go:20-60` |

## Recon Commands (when git broken)
```bash
# git remote-https missing (TencentOS 4, /usr/local/libexec/git-core has no git-remote-https)
# Fallback: tarball
curl -sL https://github.com/berachain/beacon-kit/archive/refs/heads/main.tar.gz | tar -tz | head -100
curl -sL https://github.com/berachain/beacon-kit/archive/refs/heads/main.tar.gz | tar -xz -C /tmp/bk_full
# Same for polaris, bera-reth
# GitHub API quickly rate-limits (403 for 43.156.23.22); use raw.githubusercontent.com per-file:
curl -s https://raw.githubusercontent.com/berachain/beacon-kit/main/go.mod | head -30
# grep anchors
grep -rn "CORSWithConfig\|CustomValidator\|RegisterRoutes" /tmp/bk_full/beacon-kit-main/node-api --include="*.go" | head
grep -rn "BuildSignedToken\|jwtSecret\|JWTSecret" /tmp/bk_full/beacon-kit-main --include="*.go" | head
grep -rn "ProcessProposal\|FinalizeBlock\|ParseBeaconBlock" /tmp/bk_full/beacon-kit-main --include="*.go" | head
grep -rn "DefineSSZ\|ValidateAfterDecodingSSZ" /tmp/bk_full/beacon-kit-main --include="*.go" | head
grep -rn "NewPrecompileContract\|mapRegistry\|EnableReentrancy" /tmp/bk_full/polaris-main --include="*.go" | head
grep -rn "new_payload_v4_p11\|BerachainEngineApi\|POL_TX_TYPE" /tmp/bk_full/bera-reth-main --include="*.rs" | head
```

## Pitfalls / Design Notes
- Beacon API `Enabled:false` default + `127.0.0.1:3500` mitigates unauth exposure; but if enabled with `*` CORS, browser CSRF enumeration trivial.
- JWT has only `iat`, no `exp`; clock skew tolerant; file perms are operator responsibility — no check in `LoadJWTFromFile`.
- State caching LRU 10: `ProcessProposal` result reused in `FinalizeBlock` without re-verify when `IsStateCachingActive=true`; cache key `req.Hash` malleability = invalid state finalization.
- `block_to_payload` PolTx `from=SYSTEM_ADDRESS` rewrite fixes `debug.etherscan` hash mismatch but is consensus-critical mutation; EL/CL hash divergence = fork risk.
- `accept_execution_requests_hash` flag: if true, EL accepts `RequestsOrHash` as 32B hash without validating list → withholding.
- Polaris `CREATE2` to precompile address shadowing not proven blocked; recommend explicit `vm` reserve check.
- Disk 91% (1.9G free) during clone — stream `tar -tz` before `tar -xz`; watch `/tmp` (1.1G) and `go/pkg/mod`.
