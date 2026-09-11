# Plasma (ethrex) Node Audit — Session Reference

## Target

- **Project:** Plasma (plasma.org) — stablecoin L1 chain
- **Execution client:** ethrex (PlasmaLaboratories/ethrex) — Rust, fork of reth
- **Consensus client:** PlasmaLaboratories/plasma-consensus-public
- **Node templates:** PlasmaLaboratories/non-validator-templates (Docker Compose)
- **Mainnet:** Chain ID 9745, RPC: `https://rpc.plasma.to`
- **Testnet:** Chain ID 9746, RPC: `https://testnet-rpc.plasma.to`

## Findings

### Finding 1: Hardcoded Private Keys in CLI Defaults

**File:** `cmd/ethrex/l2/options.rs`

Three private keys shipped as `default_value` in clap argument definitions:

```rust
// Line 44 — Sponsor private key (gas sponsor for L2 txs)
#[arg(long, default_value = "<REDACTED-PRIVATE-KEY:SPONSOR>",
    env = "SPONSOR_PRIVATE_KEY", ...)]
pub sponsor_private_key: SecretKey,

// Line 661 — Committer L1 private key (submits batches to L1)
"<REDACTED-PRIVATE-KEY:COMMITTER>"

// Line 795 — Proof coordinator L1 private key (submits proofs to L1)
"<REDACTED-PRIVATE-KEY:PROOF-COORD>"
```

**Derived addresses:**
| Role | Address |
|------|---------|
| Sponsor | `0x000e73282F60E2CdE0D4FA9B323B6D54d860f330` |
| Committer | `0x3D1e15a1a55578f7c920884a9943b3B35D0D885b` |
| Proof Coordinator | `0xE25583099BA105D9ec0A67f5Ae86D90e50036425` |

**Impact:** Any deployment that doesn't override `SPONSOR_PRIVATE_KEY`, `ETHREX_COMMITTER_L1_PRIVATE_KEY`, or `ETHREX_PROOF_COORDINATOR_L1_PRIVATE_KEY` env vars uses these keys. An attacker can sign L1 transactions as the operator (batch submissions, proof verifications, fee claims).

### Finding 2: Unauthenticated Admin Server

**File:** `crates/l2/sequencer/admin_server.rs`

The admin server registers routes with `.with_state(admin.clone())` but NO auth middleware:

```rust
let http_router = Router::new()
    .route("/committer/start", get(start_committer_default))
    .route("/committer/start/{delay}", get(start_committer))
    .route("/committer/stop", get(stop_committer))
    .route("/admin/health", get(admin_health))
    .route("/health", get(health))
    .route("/state-updater/stop-at/{block_number}", post(set_sequencer_stop_at))
    .with_state(admin.clone())  // ← no .layer(auth_middleware)
```

**Default bind:** `127.0.0.1:5555` (configurable via `ETHREX_ADMIN_SERVER_LISTEN_ADDRESS`)

**Endpoints:**
| Endpoint | Method | Effect |
|----------|--------|--------|
| `/health` | GET | Component health (info leak) |
| `/admin/health` | GET | Simple "OK" |
| `/committer/start` | GET | Start L1 batch committer |
| `/committer/start/{delay}` | GET | Start with custom delay |
| `/committer/stop` | GET | **Stop L1 batch submission** |
| `/state-updater/stop-at/{n}` | POST | **Freeze state at block N** |

**Impact:** Attacker with network access to admin port can halt L1 commitments (chain stops finalizing), freeze state transitions, and restart committers with attacker-controlled delays.

### Finding 3: JWT Expiration Validation Disabled

**File:** `crates/networking/rpc/authentication.rs`, line 45

```rust
let mut validation = Validation::new(Algorithm::HS256);
validation.validate_exp = false;  // ← expired tokens accepted forever
validation.set_required_spec_claims(&["iat"]);
```

Only the `iat` (issued-at) claim is checked. No `exp` claim validation. Tokens are valid indefinitely as long as `iat` is within ±60 seconds of current time — but since `validate_exp = false`, even tokens with an `exp` claim are not checked for expiration.

### Finding 4: Permissive CORS on L2 RPC

**File:** `crates/l2/networking/rpc/rpc.rs`, line 135

```rust
let cors = CorsLayer::permissive();
```

All origins, methods, and headers allowed. Combined with any auth weakness, this enables cross-origin attacks.

### Finding 5: Deployment Config Exposure

**Repo:** `PlasmaLaboratories/non-validator-templates`

The Docker Compose setup exposes:
- Execution RPC on configurable port (default 8545 mainnet, 8547 devnet)
- Execution auth RPC on 8551 (internal, not port-mapped)
- Consensus P2P on 34070
- Metrics on 9001 (exposed via `expose`, not `ports`)
- Internal node addresses in `EXECUTION_TRUSTED_PEERS`
- S3 bucket name for snapshots: `plasma-{network}-db-backups` (us-east-2, requester-pays)

The `.env.secret.example` files only contain `VALIDATOR_KEYSTORE_PASSWORD=` (empty), suggesting operators may not set it.

## Methodology Used

1. **Subdomain enum:** Only `docs.plasma.org` alive (308 → Mintlify docs)
2. **GitHub org recon:** `PlasmaLaboratories` org — 7 repos, ethrex is the key target
3. **Tarball fetch:** Used GitHub API tarball endpoint (git HTTPS not available in environment)
4. **Source grep:** Searched for private keys, admin endpoints, auth code
5. **Address derivation:** Used `eth_account` to derive addresses from found keys
6. **Config review:** Read Docker Compose, .env files, README for deployment context

## Tools That Worked

- `curl` + GitHub API for repo discovery and tarball download
- `tar` for extraction (no git HTTPS available)
- `grep -rn` for source code searching
- `python3` + `eth_account` for address derivation
- Standard Unix tools (sed, cat, find)

## Confidence Assessment

| Finding | Confidence | Scope |
|---------|-----------|-------|
| Hardcoded keys | PROVEN (in-code) | All deployments using defaults |
| Unauth admin server | PROVEN (in-code) | Requires network access to admin port |
| JWT no-exp validation | PROVEN (in-code) | Engine API only (consensus↔execution) |
| Permissive CORS | PROVEN (in-code) | L2 RPC endpoint |
| Deployment exposure | PROVEN (in-code) | Public repo, any node operator |

**Not proven live:** No live Plasma sequencer node was probed. Findings are proven in source code. Actual exploitability depends on deployment configuration (whether operators override defaults, firewall rules, etc.).
