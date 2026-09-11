# CosmWasm/Injective Smart Contract Audit Methodology

## Overview
This reference documents the static analysis methodology for CosmWasm (Rust) smart contracts on Injective, based on the Injective Swap Contract audit. The methodology adapts EVM audit patterns to CosmWasm's message-passing, storage, and execution model.

## Key CosmWasm Differences from EVM

| Aspect | EVM (Solidity) | CosmWasm (Rust) |
|--------|----------------|-----------------|
| **Entry Points** | Functions + fallback | `instantiate`, `execute`, `query`, `reply`, `migrate` |
| **Storage** | SLOAD/SSTORE (slots) | `cw-storage-plus` Map/Item (typed keys) |
| **External Calls** | `call`, `delegatecall` | SubMsg + Reply (async, no reentrancy by default) |
| **Access Control** | `onlyOwner` modifier | Manual `verify_sender_is_admin()` checks |
| **Reentrancy** | Critical (no protection) | Mitigated by SubMsg reply pattern |
| **Integer Overflow** | Panic (Solidity 0.8+) | Checked via `injective_math::FPDecimal` |
| **Gas Model** | Per-opcode | Per-contract (CosmWasm VM) |

## Endpoint Enumeration Framework

### Standard CosmWasm Entry Points
```rust
// contract.rs - always present
#[entry_point] pub fn instantiate(deps, env, info, msg) -> Result<Response, Error>
#[entry_point] pub fn execute(deps, env, info, msg) -> Result<Response, Error>
#[entry_point] pub fn query(deps, env, msg) -> Result<Binary, StdError>
#[entry_point] pub fn reply(deps, env, msg) -> Result<Response, Error>
#[entry_point] pub fn migrate(deps, env, msg) -> Result<Response, Error>
```

### Execute Message Variants (from `msg.rs`)
```rust
enum ExecuteMsg {
    // User-facing operations
    SwapMinOutput { target_denom, min_output_quantity },
    SwapExactOutput { target_denom, target_output_quantity },
    
    // Admin operations
    SetRoute { source_denom, target_denom, route: Vec<MarketId> },
    DeleteRoute { source_denom, target_denom },
    UpdateConfig { admin: Option<Addr>, fee_recipient: Option<FeeRecipient> },
    WithdrawSupportFunds { coins: Vec<Coin>, target_address: Addr },
}
```

### Query Message Variants
```rust
enum QueryMsg {
    GetRoute { source_denom, target_denom },
    GetOutputQuantity { from_quantity, source_denom, target_denom },
    GetInputQuantity { to_quantity, source_denom, target_denom },
    GetAllRoutes { start_after: Option<(String,String)>, limit: Option<u32> },
    GetConfig {},
}
```

## Source-Sink Tracing Methodology

### 1. User-Controlled Sources (28 identified in swap contract)
For each message field, trace:
- **Source**: `msg.field`, `info.sender`, `info.funds`, `env`
- **Validation**: Type checks, bounds checks, authorization checks
- **Transformation**: Arithmetic, rounding, encoding
- **Sink**: Storage (Map/Item), External (Querier/SubMsg), Events

### 2. Storage Sinks (cw-storage-plus patterns)
```rust
// Map: key -> value
pub const SWAP_ROUTES: Map<(String, String), SwapRoute> = Map::new("swap_routes");

// Item: single value
pub const CONFIG: Item<Config> = Item::new("config");
pub const SWAP_OPERATION_STATE: Item<CurrentSwapOperation> = Item::new("current_swap_cache");
```

**Trace pattern**: `msg.field` → validation → `MAP.save(key, value)` or `ITEM.save(value)`

### 3. External Sinks (InjectiveQuerier / SubMsg)
```rust
// Orderbook query (user-controlled depth)
querier.query_spot_market_orderbook(&market_id, side, Some(user_quantity), None)

// SubMsg creation (external execution)
create_spot_market_order_msg(contract, order)
SubMsg::reply_on_success(msg, REPLY_ID)
```

### 4. Deserialization Sinks (Reply Handler)
```rust
// Protobuf decode of untrusted submessage response
MsgCreateSpotMarketOrderResponse::decode(raw_bytes)
```

## Vulnerability Classification for CosmWasm

### Critical
| Pattern | Example |
|---------|---------|
| **Storage Key Collision** | `route_key(A,B) == route_key(B,A)` via lexical ordering |
| **Unrestricted Admin Fund Drain** | `WithdrawSupportFunds` with no amount/denom validation |
| **Protobuf Deserialization Panic** | `.unwrap()` on `decode()` in reply handler |

### High
| Pattern | Example |
|---------|---------|
| **TOCTOU Estimation→Execution** | Orderbook queried in `estimate_swap_result`, re-queried in `execute_swap_step` |
| **Unbounded Iteration** | `Vec<MarketId>` route with no max length → gas DoS |
| **Public Expensive Queries** | `GetOutputQuantity` does deep orderbook scans without rate limits |

### Medium
| Pattern | Example |
|---------|---------|
| **Admin Centralization** | Single admin, no timelock/multisig |
| **Missing Input Validation** | Arbitrary denom strings, no format checks |
| **Dead Code** | `DEPOSIT_REPLY_ID` defined but unhandled |

### Low
| Pattern | Example |
|---------|---------|
| **Precision Loss in Refunds** | `FPDecimal` rounding in `SwapExactOutput` |
| **Info Disclosure** | Admin/fee_recipient public via `GetConfig` |

## CosmWasm-Specific Vulnerability Patterns

### 1. Storage Key Design Flaws
```rust
// BAD: Lexical ordering loses semantic meaning
fn route_key(a: &str, b: &str) -> (String, String) {
    if a < b { (a.to_string(), b.to_string()) }
    else { (b.to_string(), a.to_string()) }
}
// SetRoute(A,B) and SetRoute(B,A) collide!
```

**Fix**: Use semantic keys `(source, target)` or include direction in key.

### 2. SubMsg Reply Deserialization
```rust
// DANGEROUS: Multiple unwrap() on untrusted input
let first = msg_responses.first().unwrap();
MsgCreateSpotMarketOrderResponse::decode(first.value.as_slice()).unwrap()
```

**Fix**: Proper error handling with `?` operator, validate decoded fields.

### 3. State Machine Dependencies
```rust
// Reply handler assumes specific state
let swap = SWAP_OPERATION_STATE.load(deps.storage)?;  // Must exist
let step = STEP_STATE.load(deps.storage)?;            // Must match
```

**Fix**: Validate state consistency, handle missing/corrupted state gracefully.

### 4. Querier-Driven External Calls
```rust
// User input controls query depth
querier.query_spot_market_orderbook(&id, side, Some(user_qty), None)
```

**Fix**: Cap query depth, validate input bounds before passing to querier.

## Automated Analysis Checklist

### Phase 1: Contract Structure (15 min)
- [ ] Identify all `#[entry_point]` functions
- [ ] Parse `ExecuteMsg` and `QueryMsg` enums
- [ ] Map `cw-storage-plus` Items/Maps
- [ ] List all `SubMsg::reply_on_success` reply IDs

### Phase 2: Source-Sink Mapping (30 min)
- [ ] For each ExecuteMsg variant: trace every field
- [ ] For each QueryMsg variant: trace every field
- [ ] Document validation logic per field
- [ ] Identify all storage writes (save/remove)
- [ ] Identify all external calls (Querier, SubMsg, BankMsg)

### Phase 3: Vulnerability Detection (30 min)
- [ ] Check storage key design (collisions, semantic loss)
- [ ] Check reply handler deserialization safety
- [ ] Check admin authorization patterns
- [ ] Check for unbounded iterations/collections
- [ ] Check estimation→execution time gaps
- [ ] Check precision/rounding in math operations

### Phase 4: Cross-Contract Analysis (20 min)
- [ ] Identify contract dependencies (other CosmWasm contracts)
- [ ] Check IBC message handling (if applicable)
- [ ] Verify InstantiateMsg migration compatibility

## Tooling for CosmWasm Audits

| Tool | Purpose |
|------|---------|
| `cargo audit` | Dependency vulnerability scanning |
| `cargo clippy` | Linting (pedantic, nursery) |
| `cargo deny` | License/check advisory |
| `wasm-opt` | Binary size analysis |
| `cosmwasm-check` | Schema validation |
| `cw-multi-test` | Unit/integration testing |
| Custom scripts | Endpoint enumeration, source-sink tracing |

## JSON Output Schema (Standardized)

```json
{
  "contract": "ContractName",
  "endpoints": {
    "instantiate": { "params": [...], "vulns": [...] },
    "execute": { "variants": { "VariantName": { "params": [...], "sinks": [...] } } },
    "query": { "variants": { "VariantName": { "params": [...], "sinks": [...] } } },
    "reply": { "reply_ids": { "ID": { "handler": "...", "deserialization": "..." } } },
    "migrate": { "validation": "..." }
  },
  "cross_cutting_vulnerabilities": { "id": { "severity": "...", "impact": "..." } },
  "source_sink_summary": { "sources": N, "storage_sinks": N, "external_sinks": N, ... }
}
```

## Injective-Specific Patterns

### Market Operations
```rust
// Order creation
SpotOrder::new(price, quantity, OrderType::BuyAtomic, market_id, subaccount, fee_recipient, None)

// Orderbook queries
querier.query_spot_market_orderbook(market_id, OrderSide::Sell, Some(qty), None)
querier.query_spot_market_orderbook(market_id, OrderSide::Buy, None, Some(quote_qty))

// Fee multiplier
querier.query_market_atomic_execution_fee_multiplier(market_id)
```

### Fee Discount (Self-Relaying)
```rust
// In queries.rs:get_effective_fee_discount_rate
if fee_recipient == contract_address {
    market.relayer_fee_share_rate  // Discount applied
} else {
    FPDecimal::ZERO
}
```

### Protobuf Scale Factor
```rust
// All protobuf Dec values have 10^18 scale
let dec_scale = FPDecimal::ONE.scaled(18);  // 10^18
let real_price = proto_price / dec_scale;
```

## Case Study: Injective Swap Contract Findings

### Critical (3)
1. **Route Key Collision** - `route_key` uses lexical min/max, breaking bidirectional routes
2. **Unrestricted WithdrawSupportFunds** - Admin can drain all contract funds to any address
3. **Protobuf Decode Panic** - Reply handler uses `.unwrap()` on decode

### High (4)
1. **TOCTOU Estimation→Execution** - Orderbook state changes between query and submessage
2. **Unbounded Route Length** - No max steps in `SetRoute`
3. **Public Estimation DoS** - `GetOutputQuantity`/`GetInputQuantity` unbounded orderbook depth
4. **Admin Centralization** - Single admin, no timelock

### Medium (5)
1. **Missing Denom Validation** - Arbitrary strings accepted
2. **Self-Relaying Toggle** - Admin can enable fee discount for own swaps
3. **Refund Precision** - Rounding in ExactOutput mode
4. **Dead Reply ID** - `DEPOSIT_REPLY_ID` unused
5. **No Migration Path** - Only supports v1.0.1→current

---

*Generated from Injective Swap Contract audit (static analysis, source-sink tracing)*
*Methodology applicable to all CosmWasm/Injective DeFi contracts*