# Keeta Network Deep Dive 2 — Mainnet vs Testnet, KTA Token Type, Saldo-0 Self-Send (2026-08-12)

Class: `validation.rs` cutoff bypass + token-type gate + zero-balance self-send
Session: sequential dummy-first (`Oke 1 dulu`, `Dummy dulu deh`, `Wait, token keeta?`, `saldo 0 self-send`)

## 1. Mainnet vs Testnet

### Evidence
- `validation.rs:152-167` `ValidationConfig::default()` — single `numeric_cutoff_epoch_ms: 1_763_683_200_000 (2025-11-21T00:00:00.000Z)` for all.
- `validation.rs:175-178`:
  ```rust
  pub fn for_network(network: &BigInt) -> Result<Self, BlockError> {
      Network::try_from(network)?; // only checks ID known
      Ok(Self::default())
  }
  ```
- `validation.rs:27-31` / `network.rs:47-50`:
  `TestDefault 0x0`, `Main 0x5382`, `Staging 0x538201`, `Test 0x54455354`, `Dev 0x444556`
- `block.rs:213` `let config = ValidationConfig::for_network(&self.network).ok();` — same path for all.

### Dummy Proof (`poc_negative_check` → `poc_mainnet_check.rs`)
`BigInt::from(network_id)` with `BlockBuilder::with_network`:
```
TestDefault (0x0)       BEFORE 2024: Ok("3C12F10ACA660246F414F66A65B0A25EF90D014D7B2537C8EC1C20505533B3FB") AFTER: AmountBelowZero
Main (0x5382)           BEFORE: Ok("411222E00C1E65E24A4D1144CF5B975D11009B878A4908059B589ED678DB9B7C") AFTER: AmountBelowZero
Staging (0x538201)      BEFORE: Ok("86507B93BC5980C36D2D45F24859B23977018AB11F01F379B79A87561A0FAEB6") AFTER: AmountBelowZero
Test (0x54455354)       BEFORE: Ok("0AC844E6E093036FC4A4F091F8D9B6D6D90B194024A42B5A9D2EDD1FBA48ABE8")  AFTER: AmountBelowZero
Dev (0x444556)          BEFORE: Ok("9C9F31AEDE04A27F89024E17110EDCF94DD450A361C7B90F92309BF45AAAE0FE") AFTER: AmountBelowZero
Unknown (0x3E7)         BEFORE: Err(UnknownNetwork)
```
Conclusion: **Mainnet not harder. Same calendar for all branches.**

## 2. KTA Token Type

- `operation/send.rs:38` `ctx.guard_token_amount(&self.token, amount)` → `operation/mod.rs:289 require_token`:
  ```rust
  if account.to_keypair_type() != KeyPairType::TOKEN { return Err(TokenFieldNotToken); }
  ```
- `send.rs:75` `TokenFieldNotToken` only for non-TOKEN. `operation/mod.rs:274 guard_token_amount` also calls `validate_numeric` — the only amount gate is cutoff.
- `account.rs:1209` `KeyPairType::TOKEN => create_identifier_account!(TOKEN, KeyTOKEN, Token)` — KTA = `generate_identifier(TRUSTED, TOKEN, 0)` is type TOKEN like any token.
- Dummy `generate_identifier_ref(1, TOKEN, 0)` = valid KTA simulator. Same bypass. `STORAGE/ED25519/NETWORK` → `TokenFieldNotToken` blocked.
- Fee: separate `Amount` via `fee_block` / `create_vote_quote` + `VoteStaple`, always `>0`, not source. Ghost mint: `balance -= (-1e6) → +1e6`.

## 3. Saldo-0 Self-Send

- `BlockBuilder` with `as_opening()` + `previous = opening_hash` from zero head still `BUILD OK` before cutoff. No prior balance check in `BlockData::validate` — only `validate_operations` (amount gate) and `validate_signer_field`/`validate_idempotent`.
- `0 - (-1e6) = +1e6` ghost. `SEND -1e6 to Bob` does NOT credit Bob +1e6 — `SEND` is sender debit; `Bob` needs `RECEIVE -1e6 exact=false` which decreases Bob. Profitable: **self-send** `Alice → Alice -1e6`.
- KTA verified vs custom: `token == KTA baseToken` → explorer `KTA` verified balance; `token == custom TOKEN identifier` → `UNKNOWN` but same mint. `require_token` does not distinguish.
- Ledger risk: `p2_net.rs:639` only tests positive `balance == SUPPLY - SEND`. No negative path. Live ledger may `LEDGER_INSUFFICIENT_FUNDS` or may `balance - amount >= 0` with `amount=-1e6` always true → ghost.

## 4. Next Step (Live Publish)

Generate 2 fresh `keeta_...` from `generate_ed25519_ref` (not user wallet), `BlockBuilder::with_network(Main 0x5382)` + `date 1717200000000` + `Send { token=KTA, amount=-1e6 }`, `build().sign()` → hex 247B, `transmit` to `rep1.main.network.api.keeta.com/api/publish` or via SSRF `CustomNetwork` `?host=...&networkAlias=test`. Observe `LEDGER_...` code. Dummy-first discipline prevents ban.

## 5. Dummy Accounts Used
- `alice keeta_ahwdu46hors5phjzealnyqzbt7djs4wywisvmnwzza3jtn5i253s6lfailbra` (0xAA)
- `bob   keeta_afug3jj4qr5ec24bm4inqii7rofi7ibfxpnopk7tmocm7piykqpoxc33mxmvu` (0xBB)
- `token keeta_aojtrnuoep6uaootcwopy2sliucxuxnvsviovc3bxavythh4djkcfvtyj7ksi` (1,TOKEN,0)
- `Main hash 411222E00C1E65E24A4D1144CF5B975D11009B878A4908059B589ED678DB9B7C` (247B)
