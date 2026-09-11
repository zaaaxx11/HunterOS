# Keeta Live Publish — Mainnet/Testnet Dummy Minus Block (2026-08-12)

## Dummy Build (Validation vs Ledger)
- `keetanetwork-block` dummy `keeta_ahwdu46hors.../keeta_afug3j...` token `keeta_apcpg...` (TOKEN type) via `generate_ed25519_ref(0xAA)` / `generate_identifier_ref(0xAA, TOKEN, 0)`.
- `BlockBuilder` with `date_ms=1717200000000 (2024-06-01)` + `Amount::from(-1_000_000i64)` → `BUILD OK` on ALL networks (`TestDefault 0`, `Main 0x5382 EB3319A7 len 248`, `Staging 0x538201`, `Test 0x54455354 4AC7E2AD len 250`, `Dev 0x444556`, `Unknown 0x3E7 → UnknownNetwork`). After cutoff `1767225600000 (2026-01-01)` → `AmountBelowZero` on all.
- Fix of seed error: use `generate_ed25519_ref` helpers not raw `SecretBox` seed; `KeetaClient::try_from(Network::Main)` + `BlockBuilder::with_network(Network::Main.id())`; `AccountPublicKey` trait for `to_keypair_type()`.

## Live Publish (Dummy Opening, Saldo 0)
- `KeetaClient::publish(block)` fans out `transmit` → reps `rep1.main.network.api.keeta.com` + test equivalent.
- Both `Main EB3319A7` and `Test 4AC7E2AD` → `PUBLISH ERR -> Node { Code { code: "", message: "Internal error occurred (error ID: f6435602... / 348d70a9...)" } }` — NOT `AmountBelowZero`, NOT `LEDGER_INSUFFICIENT_FUNDS`.
- Cause: `as_opening()` with `previous = opening_hash` and saldo 0 — ledger rejects opening debits without prior `publish-aid` fund, independent of minus logic. Validates that `BlockData::validate` lolos but `ledger apply` blocks zero-balance opens (with `Internal error` alias).
- Disk pressure: 20G `/` full → `cargo clean` + `rm -rf /tmp/poc_publish_main/target` recovered 2.3G; throttle rebuild 3m24s, always `df -h` before second fork.

## Saldo-0 Self-Send Clarification
- `0 - (-1e6) = +1e6` ghost mint only testable as **successor** block after funding (not opening). Self-send `Alice→Alice -1e6` profitable; `Alice→Bob -1e6` requires `Bob RECEIVE -1e6 exact=false` which **decreases** Bob.
- Fee is separate positive `Amount` via `fee_block`/`create_vote_quote`, never source of infinite — ghost mint is `TokenAdminSupply`-less inflation; `balance >= amount` with `amount=-1e6` always true if ledger checks `balance - amount >=0`.

## Next for Successor Proof
- Fund dummy via `publish-aid.test.network.api.keeta.com/api/publish` faucet to get 1000 KTA head, then `with_previous(head_hash)` minus self-send. Re-run publish to observe `LEDGER_...` vs ghost `+1e6`.
