# Rust Fuzz-Engineer Notes (Aptos Core & Similar L1s)

Session: Aptos Core FUZZ-ENGINEER audit, 2026-08-14
Target: `/tmp/aptos-core-mainnet` (Rust, ~200K+ lines)

## What This Is

Condensed knowledge from a FUZZ-ENGINEER pass on a large Rust L1 codebase. Covers patterns that look like bugs but aren't (false positives), patterns that ARE bugs, and tool quirks specific to Rust audit work.

---

## False Positives to Skip (Don't Burn Rounds)

### 1. `unwrap()` Protected by Construction Invariants

Many `unwrap()` calls in Rust L1s are **safe by construction**, not by accident. Before flagging an `unwrap()`, trace the invariant:

| Pattern | Why It's Safe | Example |
|---------|--------------|---------|
| `bucket_mins[0] == 0` enforced at `new()` | `binary_search` on sorted vec starting at 0 → `i-1` always >= 0 | `mempool/src/core_mempool/index.rs:407,488` |
| `sender_bucket = addr[last_byte] % num_buckets` | Modulo always produces value in `0..num_buckets`; HashMap initialized with exactly those keys | `mempool/src/core_mempool/transaction_store.rs:46,106-109` |
| `checked_sub().is_some()` before `.unwrap()` | The `ensure!`/`if` guard guarantees `Some` | `consensus/consensus-types/src/block.rs:477-483` |
| `barrier.wait()` after `catch_unwind` | Panic is captured, barrier is always reached, closure not dropped early | `block-executor/src/worker_pool.rs:80-89` |

**Rule:** If an `unwrap()` is preceded by a guard that establishes the precondition, it's not a bug. Trace the invariant to its source (constructor, config validation, type system).

### 2. `as` Casts That Look Dangerous But Aren't

| Pattern | Reality |
|---------|---------|
| `(last_version - first_version + 1) as u16` | **Actual bug** — truncates silently if > 65536. Flag it. |
| `i as u32` for loop indices | Safe if `i` is bounded by `vec.len()` which is < `u32::MAX` in practice |
| `duration.as_micros() as u64` | Safe — `as_micros()` returns `u128` but values are bounded by time |

**Rule:** Flag `as` casts where the source can exceed the target type's max. Loop indices and time durations are usually safe.

---

## Real Patterns to Target

### 1. BCS Deserialization of User-Controlled Bytes

**File pattern:** `bcs::from_bytes(&user_input.0)`

**Why it's a sink:**
- BCS uses varint encoding — small input can expand to huge internal structures
- Deep nesting → stack overflow
- Large varint lengths → OOM
- Custom `Deserialize` impls may contain `expect()` calls that panic on malformed input

**Fuzz inputs:**
- `vec![0xFF; 10_000]` — max varint expansion
- `[0x00, 0x00, 0x00, ...]` — deeply nested struct
- Valid BCS header + truncated payload

**Location examples:**
- `api/src/state.rs:536` — `bcs::from_bytes(&request.key.0)` (user-controlled StateKey)
- `api/src/transactions.rs:688` — `bcs::from_bytes(&values[0])` (balance from view function)

### 2. Gas Estimation Edge Cases

**File:** `api/src/transactions.rs:695-703`

```rust
let max_account_gas_units = if gas_unit_price == 0 {
    balance
} else {
    balance / gas_unit_price
};
```

**Edge cases:**
- `gas_unit_price = 0` + `balance = u64::MAX` → max gas = `u64::MAX`
- `gas_unit_price = 1` → no division, returns `balance` directly
- `std::cmp::max(min_number_of_gas_units, max_account_gas_units)` can clamp unexpectedly

**Fuzz:** Transaction with `gas_unit_price=0`, `max_gas_amount=u64::MAX`, account balance = `u64::MAX`.

### 3. Integer Truncation in API Responses

**File:** `api/src/context.rs:677`

```rust
let max_txns = std::cmp::min(
    self.node_config.api.max_block_transactions_page_size,
    (last_version - first_version + 1) as u16,
);
```

**Edge case:** `last_version - first_version + 1 > 65536` → silent truncation to small value.

**Fuzz:** `first_version = 0, last_version = u64::MAX` → `(u64::MAX + 1) as u16 = 0`.

### 4. Unsafe Lifetime Extension

**File:** `block-executor/src/worker_pool.rs:64-67`

```rust
let work_static: &'static (dyn Fn(usize) + Sync) = unsafe {
    let work_ref: &(dyn Fn(usize) + Sync) = &work;
    std::mem::transmute(work_ref)
};
```

**Safety condition:** `scope()` blocks until all workers call `barrier.wait()`. If a worker is killed externally (OS signal, `pthread_cancel`) between `catch_unwind` and `barrier.wait()`, the barrier deadlocks or `work` is dropped while another thread holds `work_static`.

**Not reachable via normal fuzzing** — requires OS-level thread termination.

---

## Tool Quirks: `search_files` (Hermes)

The `search_files` tool uses ripgrep under the hood. **Regex patterns with `\{` or `\(` fail** with "Unmatched \{" or "Unmatched ( or \(".

**Workarounds:**
- Search for literal strings: `pattern: "unwrap"` instead of `pattern: "\.unwrap\(\)"`
- Search for `pattern: "checked_div"` instead of `pattern: "\.checked_div\("`
- Use `file_glob: "*.rs"` to limit to Rust files
- If results are truncated, use `offset` to paginate

**What works:**
- `pattern: "as u64"` — finds integer casts
- `pattern: "bcs::from_bytes"` — finds BCS deserialization
- `pattern: "std::fs::"` — finds file I/O
- `pattern: "unsafe"` — finds unsafe blocks (then filter manually)
- `pattern: "binary_search"` — finds binary search patterns

---

## Rust-Specific Edge Case Checklist

When auditing Rust L1 code, check these in order:

1. **`unwrap()` / `expect()` on user-controlled data** — Trace invariants first
2. **`as` casts** — Can the source exceed the target type's max?
3. **BCS / bincode / serde deserialization** — User-controlled bytes?
4. **`unsafe` blocks** — Lifetime extension, raw pointer dereference, `transmute`
5. **Integer division / modulo** — Division by zero? Modulo by zero?
6. **`checked_*` usage** — Is it used consistently? Any gaps?
7. **File I/O with user-controlled paths** — `std::fs::read`, `std::fs::write`, `File::open`
8. **`format!` with user input** — Format string injection? (Rare in Rust, but possible)
9. **`panic!` in non-test code** — Can user input trigger it?
10. **`std::mem::transmute`** — Lifetime extension, type punning

---

## Positive Patterns (Good Signs)

- `#![forbid(unsafe_code)]` at crate root — Most of Aptos has this
- `aptos_infallible::checked!` macro — Overflow-safe arithmetic
- `checked_div`, `checked_add`, `saturating_sub` — Used extensively
- BCS errors mapped to `400/500` responses, not panics
- `catch_unwind` + `barrier.wait()` — Sound panic containment

---

## Session Artifacts

- Full report: `/root/aptos_fuzz_engineer_report.md`
- Retractions: F-1 (mempool OOB) and F-2 (missing bucket) were false positives after invariant tracing
- Downgrade: F-7 (WorkerPool UAF) from MEDIUM to LOW — requires OS-level thread kill
