# Aptos Core Red-Team Audit — Session Findings (2026-08-14)

## Context
Full adversarial audit of Aptos Core (`/tmp/aptos-core-mainnet`) — a Rust-based L1 blockchain using the Move VM. Source code was available locally. This session produced verified findings across admin services, deserialization, and configuration attack surfaces.

## Key Findings Summary

| Severity | Finding | File(s) |
|----------|---------|---------|
| 🔴 HIGH | Admin Service unauthenticated by default on non-mainnet + query-param auth leakage | `crates/aptos-admin-service/src/server/mod.rs`, `config/src/config/admin_service_config.rs` |
| 🟠 MEDIUM | Heap profile path traversal / disk fill via `/malloc/dump_profile?output=` | `crates/aptos-admin-service/src/server/malloc.rs` |
| 🟠 MEDIUM | Failpoint endpoint enables API DoS (feature-gated, no auth) | `api/src/set_failpoints.rs` |
| 🟡 LOW | Thread dump spawns subprocess of itself (symlink attack surface) | `crates/aptos-system-utils/src/thread_dump.rs` |
| 🟡 LOW | Faucet IP-based rate limiting bypass via header spoofing | `crates/aptos-faucet/core/src/checkers/google_captcha.rs` |
| 🟡 LOW | View function filter uses string comparison (theoretical bypass) | `config/src/config/api_config.rs` |
| 🟡 LOW | BCS deserialization depth limits need fuzzing | `api/src/transactions.rs`, `api/types/src/move_types.rs` |

## Detailed Findings

### 🔴 HIGH — Admin Service: Unauthenticated by Default + Query-Param Auth Leakage

**Files:**
- `crates/aptos-admin-service/src/server/mod.rs` (lines 154-174)
- `config/src/config/admin_service_config.rs` (lines 21-22, 42-52)

**Issue:** The AdminService binds to `0.0.0.0:9102` by default and is **auto-enabled on all non-mainnet networks** (testnet, devnet, local). When `authentication_configs` is empty, `authenticated = true` is set unconditionally (line 156). This exposes:

- `/profilez` — CPU profiling (can trigger profiling overhead / disk writes)
- `/threadz` — Full thread dumps (information disclosure of runtime state)
- `/malloc/stats` and `/malloc/dump_profile` — Heap profiling (disk writes to `/tmp/`)
- `/debug/consensus/consensusdb` — Full consensus DB dump (validator voting state, block payloads)
- `/debug/consensus/quorumstoredb` — Quorum store dump
- `/debug/consensus/block` — Block data with transactions
- `/debug/mempool/parking-lot/addresses` — Mempool state

**Impact:** On testnet/devnet/fullnodes, any network-reachable host can dump consensus state, mempool contents, and node internals. On a validator, this leaks voting patterns, block proposals, and quorum certificates.

**Auth mechanism weakness:** `PasscodeSha256` authenticates via query parameter (`?passcode=abc`). Query parameters are logged in:
- Reverse proxy access logs (nginx, HAProxy)
- Application request logs
- TLS termination logs
- Browser history if used interactively

This violates the principle that credentials should not appear in URLs.

**PoC reasoning:**
```
# Default config on testnet: auth empty → auto-authenticated
GET http://<node>:9102/debug/consensus/consensusdb
→ Returns full consensus DB state (last votes, blocks, QCs)

# With auth enabled, passcode in URL:
GET http://<node>:9102/profilez?passcode=abc
→ Passcode visible in proxy logs, server logs, TLS termination
```

**Recommendation:**
1. Default `enabled: false` on all networks including testnet/devnet, require explicit opt-in.
2. Replace query-param auth with header-based auth (`Authorization: Bearer <token>`).
3. Bind to `127.0.0.1` by default; require explicit address config for remote access.
4. Add IP allowlisting at the service level.

---

### 🟠 MEDIUM — Heap Profile Path Traversal / Disk Fill

**File:** `crates/aptos-admin-service/src/server/malloc.rs` (lines 51-91, 93-146)

**Issue:** The `/malloc/dump_profile` endpoint accepts a user-controlled `output` query parameter that determines where the heap profile is written on disk. The `validate_output_path` function (lines 74-91) checks:
1. File does not already exist (refuses overwrite)
2. Parent directory exists

However, it does **not**:
- Validate that the path is within an allowed directory
- Prevent writing to sensitive locations (`/etc/`, `/root/`, etc.)
- Limit the total number of profiles that can be created
- Validate path components for traversal sequences

Combined with the auth bypass above, an attacker can:
1. Write arbitrary files to any location where the node process has write permissions
2. Fill disk by creating many profiles (each to a unique path under an existing directory)

**PoC reasoning:**
```
GET /malloc/dump_profile?output=/tmp/aptos-heap-attack1&format=path
GET /malloc/dump_profile?output=/tmp/aptos-heap-attack2&format=path
... (repeat, filling disk)

# If node runs as root (common for validators):
GET /malloc/dump_profile?output=/root/.ssh/authorized_keys&format=path
→ Would fail if file exists, but could write to /root/.ssh/new_key
```

**Note:** The path is passed to `jemalloc_ctl::raw::write` via `CString::new()`, which will reject internal null bytes, limiting null-byte injection. But path traversal via `../` is not blocked.

**Recommendation:**
1. Restrict output paths to a configured directory (e.g., `/tmp/aptos-profiles/`).
2. Rate-limit profile dumps per source IP.
3. Require elevated auth for write operations.

---

### 🟠 MEDIUM — Failpoint Endpoint Enables API Denial-of-Service

**Files:**
- `api/src/set_failpoints.rs` (entire file, 52 lines)
- `api/src/failpoint.rs` (lines 11-19)
- `api/src/runtime.rs` (lines 250-251)
- `config/src/config/api_config.rs` (lines 32-34, 122, 177-179)

**Issue:** The `/set_failpoint` endpoint (when `failpoints` feature is enabled) allows any caller to configure `fail::cfg()` rules that can:
- Return arbitrary errors from any API endpoint
- Panic the API process
- Sleep/delay responses indefinitely

Failpoints are **disabled by default** (`default_disabled()`, line 122) and **sanitized off on mainnet** (lines 177-179). However:
1. On testnet/devnet, `failpoints_enabled` may be true.
2. The endpoint has **no authentication** of its own — it relies entirely on the feature flag.
3. The `fail` crate's `cfg()` function is powerful: `fail::cfg("api::endpoint_submit_transaction", "panic")` would crash every transaction submission.

**PoC reasoning:**
```
# If failpoints are enabled (testnet/devnet):
GET /set_failpoint?name=api::endpoint_submit_transaction&actions=panic
→ All subsequent transaction submissions panic

GET /set_failpoint?name=api::endpoint_get_account&actions=return(error)
→ All account queries return errors
```

**Recommendation:**
1. Never expose `/set_failpoint` on network-reachable interfaces.
2. Bind to `127.0.0.1` only, even on testnet.
3. Add explicit authentication if remote access is needed.

---

### 🟡 LOW — Faucet IP-Based Rate Limiting Bypass via Header Spoofing

**File:** `crates/aptos-faucet/core/src/checkers/google_captcha.rs` (lines 77-84)
**Related:** `crates/aptos-faucet/core/src/endpoints/fund.rs` (lines 102-119)

**Issue:** The faucet uses `RealIp` from Poem (which respects `X-Forwarded-For` and `X-Real-IP` headers) for rate limiting. An attacker behind a proxy can spoof these headers to bypass IP-based rate limits.

The Google Captcha checker sends the source IP to Google's verification endpoint, but the rate limiter uses the (spoofable) source IP for counting.

**Impact:** An attacker can drain the faucet by rotating spoofed IP addresses, exhausting the faucet's funds.

**Recommendation:**
1. Configure reverse proxies to strip/override `X-Forwarded-For` from untrusted sources.
2. Use `X-Real-IP` set by a trusted proxy only.
3. Add JWT-based or captcha-based rate limiting as primary mechanism.

---

### 🟡 LOW — View Function Filter Uses String Comparison (Case-Sensitive Exact Match)

**File:** `config/src/config/api_config.rs` (lines 230-241)

**Issue:** The `ViewFilter::allows()` function uses exact string comparison (`id.module == module && id.function_name == function`). This is correct but:
1. No normalization is applied — `0x1::coin::balance` vs `0x01::coin::balance` (leading zero differences in address) could bypass filters if the allowlist uses a different format.
2. The `ViewFunctionId` struct stores `address: AccountAddress` which has its own parsing, but the module/function are raw strings.

**Recommendation:**
1. Normalize addresses before comparison (canonical hex representation).
2. Consider case-insensitive comparison for module/function names if Move allows it.

---

### 🟡 LOW — BCS Deserialization Limits: Depth May Be Insufficient for Complex Types

**Files:**
- `api/src/transactions.rs` (line 851): `MAX_SIGNED_TRANSACTION_DEPTH = 16`
- `api/types/src/move_types.rs` (line 685): `MAX_RECURSIVE_TYPES_ALLOWED = 8`

**Issue:** These limits protect against deeply nested BCS deserialization attacks (stack exhaustion). However:
- `MAX_SIGNED_TRANSACTION_DEPTH = 16` may be too permissive for complex nested structs.
- `MAX_RECURSIVE_TYPES_ALLOWED = 8` is quite low, which is good, but the interaction between the two limits needs verification.

**Recommendation:**
1. Verify these limits against worst-case Move type structures.
2. Consider adding a total deserialization cost metric (not just depth).
3. Fuzz test the deserializers with pathological inputs.

---

### 🟡 LOW — Thread Dump Spawns Subprocess of Itself

**File:** `crates/aptos-system-utils/src/thread_dump.rs` (lines 83-86)

**Issue:** The `/threadz` endpoint (reachable via AdminService) spawns the current executable as a subprocess with `--stacktrace`:
```rust
let exe = env::current_exe().unwrap();
let trace = TraceOptions::new()
    .snapshot(snapshot)
    .trace(Command::new(exe).arg("--stacktrace"))
```

While `exe` is derived from `env::current_exe()` (not user-controllable), this means:
1. Any user who can influence the binary path (e.g., via symlink attacks on the executable location) could redirect the subprocess.
2. The subprocess inherits the parent's environment and file descriptors.

**Impact:** Low — requires filesystem-level access to the node host. Combined with the AdminService auth bypass, an attacker could trigger resource-intensive thread dumps.

**Recommendation:**
1. Validate the executable path before spawning.
2. Consider using a dedicated tracing library instead of subprocess invocation.

---

## What Was NOT Found (Verified Negatives)

| Surface | Result | Evidence |
|---------|--------|----------|
| Command injection | NONE | `std::process::Command` usage limited to CLI/build tools and self-derived executables |
| SSRF | NONE | `reqwest` usage is config/internal only; no user-controlled URLs |
| Move VM sandbox escape | NONE | Native functions are static (`NativeFunctionTable`), no dynamic loading |
| Consensus message forgery | NONE | NOISE handshake + application-layer signatures |
| Arbitrary file read | NONE | No user-controlled path parameters in file I/O |

---

## Audit Methodology Applied

1. **Entry point mapping**: Searched for HTTP servers, route handlers, admin/debug endpoints
2. **Data flow tracing**: For each entry point, traced deserialization → validation → internal systems → trust boundary
3. **Authentication analysis**: Checked auth requirements, bypass potential, default configurations
4. **Sensitive operation hunting**: Searched for command execution, file I/O, network requests, process management
5. **Configuration review**: Examined default values, feature flags, sanitizer logic

---

## Grep Patterns Used (Reusable for Future Rust Audits)

```bash
# Admin/debug endpoints
grep -rn "admin\|debug\|AdminApi\|DebugApi" --include="*.rs"

# Deserialization
grep -rn "bcs::from_bytes\|from_bcs_bytes\|serde_json::from_str\|from_str_with_error" --include="*.rs"

# Authentication
grep -rn "auth\|token\|jwt\|api_key\|bearer\|authorization" --include="*.rs"

# Command execution
grep -rn "Command::new\|std::process::Command\|spawn\|exec\|system(" --include="*.rs"

# File I/O
grep -rn "tokio::fs\|std::fs\|File::open\|read_to_string\|write_all" --include="*.rs"

# HTTP clients (SSRF)
grep -rn "reqwest\|hyper\|ureq\|curl\|http::get\|http::post" --include="*.rs"

# Network binding
grep -rn "TcpListener\|TcpStream\|UdpSocket\|bind\|listen" --include="*.rs"

# Unsafe code
grep -rn "unsafe\|eval\|compile\|dlopen\|load_plugin\|plugin" --include="*.rs" | grep -v "test\|#\|unsafe extern\|unsafe impl\|unsafe fn\|unsafe trait"
```

---

## Full Report
The complete red-team report is saved at `/root/aptos-redteam-report.md`.
