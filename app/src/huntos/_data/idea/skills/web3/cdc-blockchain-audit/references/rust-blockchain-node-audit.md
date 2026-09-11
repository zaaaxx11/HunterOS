# Rust Blockchain Node Audit Patterns

## Context
When auditing a Rust-based blockchain node (Aptos, Solana, Sui, Near, Polkadot, etc.), the attack surface differs significantly from Go-based chains. Key differences:

| Aspect | Go Chains | Rust Chains |
|--------|-----------|-------------|
| Deserialization | protobuf, JSON-RPC | BCS, SCALE, Borsh, bincode |
| Concurrency | goroutines, channels | async/await, tokio, rayon |
| Admin APIs | debug_stacks, pprof | thread dumps, malloc profiling, failpoints |
| VM | EVM (go-ethereum) | Move, Solana VM, WASM |
| Network | libp2p (go-libp2p) | libp2p (rust-libp2p), custom P2P |

## Common Rust Entry Points

### 1. Admin/Diagnostic Services
Rust nodes often expose separate admin services for debugging:
- **Aptos**: `AdminService` on separate port (`admin_service.address:admin_service.port`)
- **Solana**: `rpc.requestAirdrop`, `rpc.getVoteAccounts` (JSON-RPC methods)
- **Near**: `protocol_config`, `validators` (JSON-RPC)
- **Polkadot**: `system_health`, `system_peers` (substrate RPC)

**Audit checklist:**
- [ ] Is the admin service bound to `0.0.0.0` or `127.0.0.1`?
- [ ] Is authentication configured or defaulting to none?
- [ ] What endpoints expose internal state (consensus DB, mempool, profiler)?
- [ ] Do any endpoints execute OS commands (thread dumps, profilers)?

### 2. Failpoints / Testing Hooks
Many Rust projects use the `fail` crate for testing:
```rust
fail::fail_point!("api::endpoint_submit_transaction", |_| {
    Err(InternalError::new("Failpoint triggered"))
});
```

**When enabled via config + feature flag:**
- `GET /set_failpoint?name=...&actions=panic` → crashes the node
- `GET /set_failpoint?name=...&actions=return(...)` → alters behavior

**Audit checklist:**
- [ ] Is `failpoints` feature enabled in build?
- [ ] Is `failpoints_enabled` config true?
- [ ] Are failpoint endpoints exposed on public API?
- [ ] **CRITICAL**: Failpoint endpoints often have NO auth beyond the feature flag — they are not behind the same auth middleware as other endpoints.

### 3. Deserialization Surfaces
Rust chains use various binary formats:

| Format | Used By | Key Function |
|--------|---------|--------------|
| BCS | Aptos, Sui, Diem | `bcs::from_bytes`, `bcs::from_bytes_with_limit` |
| SCALE | Polkadot, Substrate | `Decode::decode`, `parity-scale-codec` |
| Borsh | Solana, Near | `BorshDeserialize::deserialize` |
| bincode | Various | `bincode::deserialize` |

**Audit checklist:**
- [ ] Are depth limits applied (`from_bytes_with_limit`)?
- [ ] What is the limit value? Is it sufficient?
- [ ] Are there unbounded deserialization paths?
- [ ] Can recursive types cause stack overflow?

### 4. Command Execution Paths
Search for OS command execution in Rust:
```bash
grep -rn "Command::new\|std::process::Command\|system(" --include="*.rs"
```

Common locations:
- Thread dump handlers (`gdb`, `lldb`, `perf`)
- Profiler integrations (`python3`, `perf`, `valgrind`)
- CLI tooling (`cargo`, `rustfmt`)
- Network utilities (`curl`, `wget` for fetching)

### 5. External HTTP Requests (SSRF)
Search for HTTP client usage:
```bash
grep -rn "reqwest\|hyper::Client\|ureq\|curl" --include="*.rs"
```

**Audit checklist:**
- [ ] Are URLs user-controlled?
- [ ] Is there SSRF protection (allowlist, IP blocking)?
- [ ] Are responses deserialized without validation?

## Source Code Audit Methodology

When the full source code is available (e.g., `/tmp/aptos-core-mainnet`):

### Phase 1: Map Entry Points
```bash
# Find all HTTP servers
grep -rn "Server::bind\|TcpListener\|hyper::Server\|poem::Server" --include="*.rs"

# Find all route handlers
grep -rn "method.*=.*\"get\"\|method.*=.*\"post\"\|oai(path" --include="*.rs"

# Find admin/debug endpoints
grep -rn "admin\|debug\|profile\|threadz\|malloc" --include="*.rs"
```

### Phase 2: Trace Data Flow
For each entry point:
1. What deserialization happens?
2. What validation is applied?
3. What internal systems are touched?
4. What is the trust boundary?

### Phase 3: Identify Sensitive Operations
```bash
# Command execution
grep -rn "Command::new" --include="*.rs"

# File I/O
grep -rn "tokio::fs\|std::fs\|File::open" --include="*.rs"

# Network
grep -rn "TcpStream::connect\|UdpSocket" --include="*.rs"

# Process management
grep -rn "spawn\|exec\|fork" --include="*.rs"
```

### Phase 4: Authentication Analysis
For each endpoint:
- Is auth required?
- What type (none, token, signature, passcode)?
- Can it be bypassed?
- What happens if auth is missing?

## Aptos-Specific Patterns (Reference)

### Admin Service Endpoints
| Endpoint | Risk | Auth Required |
|----------|------|---------------|
| `/profilez` | CPU profiling (DoS) | Optional passcode |
| `/threadz` | Thread dump via gdb/lldb | Optional passcode |
| `/malloc/stats` | Memory profiling | Optional passcode |
| `/malloc/dump_profile` | Memory profile to disk | Optional passcode |
| `/debug/consensus/block` | Consensus state dump | Optional passcode |
| `/debug/consensus/consensusdb` | Consensus DB dump | Optional passcode |
| `/debug/consensus/quorumstoredb` | Quorum store dump | Optional passcode |
| `/debug/mempool/parking-lot/addresses` | Mempool addresses | Optional passcode |

**Critical finding**: If `authentication_configs` is empty, ALL endpoints are unauthenticated.

### REST API Endpoints
| Endpoint | Method | Risk |
|----------|--------|------|
| `/v1/transactions` | POST | BCS deserialization, mempool injection |
| `/v1/view` | POST | Arbitrary Move view function execution |
| `/v1/tables/:handle/item` | POST | State key lookup, potential arbitrary read |
| `/v1/set_failpoint` | GET | Runtime behavior modification (if enabled) |

### Key Files for Aptos Audit
- `crates/aptos-admin-service/src/server/mod.rs` — Admin service
- `api/src/runtime.rs` — API server setup
- `api/src/transactions.rs` — Transaction submission
- `api/src/view_function.rs` — View function execution
- `api/src/state.rs` — State lookups
- `api/src/set_failpoints.rs` — Failpoint configuration
- `mempool/src/shared_mempool/coordinator.rs` — Mempool processing

## Pitfalls

1. **Assuming Go patterns apply**: Rust chains don't have goroutine dumps. Look for thread dumps, malloc profiling, failpoints instead.

2. **Ignoring feature flags**: Many dangerous endpoints are feature-gated (`#[cfg(feature = "failpoints")]`). Check if features are enabled in the deployed binary.

3. **Overlooking config defaults**: Rust nodes often default to NO authentication for admin services. Always check if `authentication_configs` is empty.

4. **Missing BCS depth limits**: `bcs::from_bytes` without `_with_limit` can cause stack overflow on recursive types.

5. **Assuming EVM compatibility**: Move-based chains (Aptos, Sui) have different VM semantics than EVM. View functions can read arbitrary state.

6. **Query-param auth leakage**: When Rust nodes use query-parameter-based auth (e.g., `?passcode=abc`), credentials appear in server logs, proxy logs, and browser history. Always prefer header-based auth.

7. **Heap profile path traversal**: Admin endpoints that accept output paths from users can write to arbitrary locations. Validate paths against an allowlist.

## Related Skills
- `blockchain-consensus-audit` — Consensus protocol deep dive
- `consensus-protocol-audit` — Vote aggregation, certificate verification
- `cosmwasm-contract-audit` — For Cosmos-based Rust chains
- `solana-anchor-audit` — For Solana Anchor programs
