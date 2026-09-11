# Keeta TOKEN_ADMIN Supply Bypass — Validator Ok vs Ledger/Privilege Block (2026-08-12)

## Validator
- `ValidationConfig::default() max_supply = 10^200 -1` (200 digits, `validation.rs:159`). `validate_supply` only rejects `> max_supply`.
- `guard_token_amount` + `validate_numeric_value` same cutoff `1763683200000` for all ops: `TokenAdminSupply`, `TokenAdminModifyBalance`, `SEND`, `RECEIVE`.
- Proof via `BlockBuilder::with_network(0x54455354u32)`:
  - `TokenAdminSupply Add -1 TOKEN date 2024 (1717200000000) → Ok AA066F361AEB00ACCCDE5D3B97BE9E9443C3CD0AAEF9536E197ECC80D8A6211E`
  - `same after cutoff (1763683200000) → Err AmountBelowZero`
  - `Add MAX 10^200-1 before → Ok 4D0C171A8FDBDF9538A41D5893D0EB9A6B41E6A04AE52F4D5482CF118D0CFE20`
  - `ModifyBalance Add MAX before (ED25519 alice + real_token) → Ok 1166F267BF1F6B3880C2769CB69C38FC5110D3CA2C1F279C1B2583454F316A4B`
  - `ModifyBalance NEG -1 before → Ok 74B003827257BAC4FB4C5C6C7D664AC81657AD9CAB5784F6A8155C62FC233BC5`

## Ledger / Signing Block
- `TokenAdminModifyBalance` as ED25519 `keeta_afen47...` → `hash 865AE7C8BD5A736597EC6434D5EE962C8889538EBF00578FBFFC92898F547ECC len 302` prev `012F29FC36CF1992E218247F49FCABE9115ABAFE5DE627269292167F93B294AD` → `PUBLISH ERR LEDGER_OPERATION_NOT_SUPPORTED: TOKEN_ADMIN_MODIFY_BALANCE operation not supported (retry false)` — ledger gates `account_is_token()`.
- `TokenAdminSupply` as `TOKEN` identifier `keeta_ann5sjsnii4l33da4iypp4m2mu5z5lnxlfp3rqq3coquea7ofsbkmtzhvirn6 type TOKEN` (generate_identifier_ref 77) → `unsigned AA066F36...` → `sign() → Err NoIdentifierSign` — TOKEN has no SecretBox private key. Real KTA `keeta_anyiff...` owned by trusted `keeta_aabmvemi...` (90M), not attacker.
- So validator jebol, but no signed block possible → financial impact 0.

## Repro
- Build with `keetanetwork-block` testing + `keetanetwork-account` std; `ValidationConfig::default()`; `BlockTime::from_unix_millis(1717200000000)`; `Amount::from(BigInt::from(-1))` or `cfg.max_supply`.
- Keep disk `2.9G free` — single crate <200M, no `node-harness` 4G.
