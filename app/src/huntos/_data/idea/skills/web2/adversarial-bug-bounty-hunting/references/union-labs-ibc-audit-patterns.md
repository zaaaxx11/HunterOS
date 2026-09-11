# Union Labs / CosmWasm IBC Audit Patterns (2026-08-08)

## Target: Union Labs (https://github.com/unionlabs)
**Audited:** ucs03-zkgm (cross-chain bridge), 11-cometbls (custom light client with ZK), core IBC contracts

---

## Key Architectural Patterns Found

### 1. ZKGM (Zero-Knowledge Generalized Messaging) Protocol
**File:** `cosmwasm/app/ucs03-zkgm/src/contract.rs` (3,556 lines)

**Core Concept:** Arbitrary cross-chain calls via IBC packets with ZK verification

**Instruction Types (OP codes):**
```rust
OP_FORWARD: 0x00   // Multi-hop routing
OP_CALL: 0x01      // Arbitrary contract call (with proxy account creation)
OP_BATCH: 0x02     // Atomic batch of CALL/TOKEN_ORDER
OP_TOKEN_ORDER: 0x03  // Token transfer (v1/v2)
```

**Packet Structure:**
```rust
struct ZkgmPacket {
    salt: bytes32,      // Replay protection + forward tracking
    path: uint256,      // Encoded channel path (32-bit per hop, max 7 hops)
    instruction: Instruction
}
```

### 2. Proxy Account Creation Pattern (CRITICAL AUDIT SURFACE)
**Lines 1500-1683** in `execute_call()`

```rust
// Predict proxy address via instantiate2
let predicted_address = predict_call_proxy_account(deps, env, &call_proxy_salt)?;

// If proxy doesn't exist AND not already created this batch:
if predicted_address == contract_address 
    && !contract_exists(predicted_address)
    && !CREATED_PROXY_ACCOUNT.exists()
{
    // Queue 3 submessages atomically:
    1. Instantiate2(dummy_code_id)     // Create dummy contract
    2. Migrate(cw_account_code_id)     // Upgrade to real account
    3. UpdateAdmin(self)               // Make account self-admin
}
```

**Attack Surface:**
- `call.sender` verified on SOURCE chain only (`verify_call()` line 3002-3006)
- Destination chain does NOT re-verify `call.sender` against light client proof
- **Theoretical gap:** If source chain compromised, arbitrary sender impersonation possible
- **Mitigated by:** Light client proof verifies entire packet integrity

### 3. Token Order V1/V2 with Market Maker Fills
**Two distinct fill mechanisms:**

**Protocol Fill (automatic):**
- Conditions: `quote_token == wrapped_token && base_amount >= quote_amount`
- Mints wrapped tokens to receiver + fee to relayer
- No external actor needed

**Market Maker Fill (intent-based):**
- `intent: bool` flag in packet
- Market maker provides `quote_token` liquidity
- Two subtypes: `FILL_TYPE_PROTOCOL` vs `FILL_TYPE_MARKETMAKER`
- **Solver Fill:** External solver contract called via `DoSolve` message

**Refund Logic (lines 861-971):**
- `refund()` for v1, `refund_v2()` for v2
- Handles both escrow (native) and wrapped token paths
- **Potential issue:** `base_token_path` used to determine origin vs wrapped

### 4. Forward Instruction (Multi-Hop Routing)
**Lines 1392-1497** `execute_forward()`

```rust
// Dequeue next hop from path
let (tail_path, prev_channel) = dequeue_channel_from_path(forward.path)?;
let (continuation_path, next_channel) = dequeue_channel_from_path(tail_path)?;

// Validate we arrived at expected channel
if packet.destination_channel_id != prev_channel { ERROR }

// Build next packet
let next_instruction = if continuation_path == 0 {
    forward.instruction  // Final hop - execute inner instruction
} else {
    // Re-wrap as FORWARD with remaining path
    Instruction::Forward(Forward { path: continuation_path, ... })
};

// Send via IBC host
PacketSend { source_channel_id: next_channel, ... }
```

**Path Encoding:** 32 bits per channel ID, packed into U256 (max 7 hops)
- `update_channel_path()` appends channel to path
- `reverse_channel_path()` reverses for return trips
- `pop_channel_from_path()` extracts highest-index channel

### 5. Salt Derivation for Replay Protection
```rust
// Batch: derive_batch_salt(index, base_salt) = keccak256(index, salt)
// Forward: derive_forward_salt(salt) = tint_forward_salt(keccak256(salt))
// Forward salt magic: FORWARD_SALT_MAGIC (specific bit pattern)
fn is_forwarded_packet(salt: H256) -> bool {
    (salt & FORWARD_SALT_MAGIC) == FORWARD_SALT_MAGIC
}
```

### 6. In-Flight Packet Tracking (Critical for Forward Ack/Timeout)
**Lines 2596-2623, 724-746** `FORWARD_REPLY_ID` handler + `acknowledge_packet()`

```rust
// On forward success: store sent_packet by commitment_key
IN_FLIGHT_PACKET.save(commitment_key, sent_packet)

// On ack/timeout of forwarded packet: lookup parent, forward ack/timeout to parent
if is_forwarded_packet(zkgm_packet.salt) {
    if let Some(parent) = IN_FLIGHT_PACKET.may_load(commitment_key)? {
        // Forward to ibc_host WriteAcknowledgement with parent packet
        IN_FLIGHT_PACKET.remove(commitment_key)
    }
}
```

**Attack Surface:** If forward reply fails but packet sent, `IN_FLIGHT_PACKET` not set → ack/timeout can't find parent

---

## Light Client: 11-CometBLS (Custom ZK Light Client)

**Files:** `11-cometbls/` (Go implementation)

**Key Components:**
- `zk_verifier.go` — ZK proof verification for consensus
- `consensus_host.go` — Host functions for ZK verification
- `client_state.go` / `consensus_state.go` — State structures
- `update.go` / `misbehaviour.go` — Client update/misbehaviour logic

**Architecture:**
- CometBLS = CometBFT + BLS signature aggregation
- ZK proofs for light client state transitions
- Custom client type registered in core IBC contract

**Audit Notes:**
- ZK verification is cryptographic (not logic-based) → hard to find logical bypass
- Need to verify: trusted setup, circuit constraints, proof generation
- Client update flow: `UpdateClient` → light client `UpdateStateQuery` → proof verification

---

## CosmWasm Core IBC Contract (`cosmwasm/core/src/contract.rs`)

**Key Functions:**
- `create_client` / `update_client` / `misbehaviour` — Client lifecycle
- `connection_open_*` — IBC connection handshake
- `channel_open_*` — IBC channel handshake
- `process_receive` — Packet recv/ack/timeout processing
- `send_packet` / `write_acknowledgement` — Outbound packets

**Verification Pattern:**
```rust
// All cross-chain state changes verified via light client
query_light_client::<()>(deps, client_impl, VerifyMembershipQuery {
    client_id, height, proof, path, value
})?;
```

**Access Control:**
- `RestrictedExecuteMsg` requires `access_managed` authorization
- `Authority` type for permission checks
- `Force*` variants bypass proof verification (admin only)

---

## Audit Findings Summary (2026-08-08)

| Theory | Vector | Status | Notes |
|--------|--------|--------|-------|
| A | Cross-chain call sender verification gap | THEORETICAL | Mitigated by light client proof integrity |
| B | Token metadata injection (CreateDenomV2) | THEORETICAL | Need token minter source to confirm |
| C | Light client ZK proof bypass | BLOCKED | Cryptographically sound |

**No proven pre-auth RCE or direct fund theft vectors.**

---

## New Audit Checklist Items for CosmWasm IBC Contracts

1. **Cross-chain call sender verification:** Is `call.sender` re-verified on destination against light client proof?
2. **Proxy account creation:** Can attacker trigger proxy creation for arbitrary sender? Salt collision?
3. **Forward instruction:** Path validation, hop limits, in-flight packet cleanup on failure
4. **Salt derivation:** Forward/batch salt collision resistance, replay protection
5. **Market maker fill:** Intent packets restricted to maker fill only (line 1413-1420)
6. **Token order unescrow:** Origin path verification for unwrapping (lines 438-478)
7. **Batch execution:** All sub-instructions must produce acks (line 2521-2527)
8. **Reply handler:** Unknown reply IDs rejected (line 2735)

---

## Reference Files Created This Session
- `/tmp/unionlabs/unionlabs-union-031785b/cosmwasm/app/ucs03-zkgm/src/contract.rs` — Main bridge contract
- `/tmp/unionlabs/unionlabs-union-031785b/cosmwasm/core/src/contract.rs` — Core IBC contract
- `/tmp/unionlabs/unionlabs-union-031785b/11-cometbls/` — Custom ZK light client