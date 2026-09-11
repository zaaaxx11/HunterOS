# Keeta — Ledger Bypass Hunt After Minus Blocked (Receive / Fee0 / Supply)

## Context
`SEND -1M` date 2024 validator `Ok` (hash `C76CAD0E...` / `411222E0...`, unsigned `a181b53081b202045...`) → ledger `Internal error c0231a48` (successor) / `23872561` / `348d70a9` (opening). Balance `9999559600` unchanged. 10 KTA faucet `keeta_afen47...` funded, head `9408C90E...`, tiny `SEND 1` → `Ok hash true`. Minus is ledger-blocked, not just validator `AmountBelowZero`.

## 3 Ledger-Adjacent Vectors (CDC divergent after Stall)

### 1. Fee 0 optional (Hemat)
- `keetanetwork-vote/src/fee.rs:98` `required()` = `!any amount==0` → `Fees::Multiple [0,9]` = optional → `to_send()`→`None` (no SEND for fee).
- `fee.rs:362` `Fee amount -1 → MalformedFeesAmount` → minus fee blocked at validator.
- `fee.rs:151 from_entries`, `108 select`, `170 to_send` — fee selection prefers priority then base. Amount 0 saves tip `~0.00044 KTA` but does NOT bypass ledger `amount>0` on SEND.
- Live test: `UserClient::from_network(Test, generic)` + `client.client().send(&generic,&generic,&kta_arc, Amount::from(1u64)) → Ok hash true` — fee path proven without minus.
- Lesson: Fee 0 is cost saving, not mint bypass.

### 2. Supply max (Validator-only)
- `validation.rs:159` `max_supply = 10u8.pow(200)-1` (199 digits). `validate_supply` only checks `amount > max_supply → SupplyInvalid` (`token_admin_supply.rs:199`).
- `TokenAdminSupply` and `TokenAdminModifyBalance` (`token_admin_modify_balance.rs`, `token_admin_supply.rs`) use same `guard_token_amount` cutoff — before 2024, `max_supply` amount would pass validator. Ledger likely `checked_add` overflow or supply cap → `Internal` or `SupplyInvalid`.
- Test without publish: `ValidationConfig::default().validate_supply(max_supply.clone()).is_ok()` vs `max_supply+1 → SupplyInvalid` (`validation.rs:271 test_supply_validation`).
- Lesson: Supply max is wraparound hunt, not pre-auth mint without `TokenAccountRequired` + ledger cap.

### 3. Receive minus + forward (Rug not mint)
- `receive.rs:27-48` `Receive{amount, token, from, exact, forward}` → `guard_token_amount` same cutoff → `RECEIVE -1M` date 2024 also validator `Ok`.
- Gates: `forward != self (ForwardToSelf)`, `!exact + forward → ForwardRequiresExact`, `TOKEN forward != token → TokenReceiveDiffers`, `reject_token_account`, `TokenOperationForbidden` on TOKEN account.
- Ledger semantics: `SEND 100 → pending 100 → RECEIVE -1M exact=false → min(pending, -1M) = -1M → victim -1M` (loss). `exact=true` → mismatch ` -1M != 100 → reject`. `exact=true forward=Charlie → Charlie -1M`.
- Plus `external max 1024` (`validation.rs:158`) + `decimalPlaces 0-1024` (`token-batcher.ts:54`) → `Numeric *10^1024` → DoS (1024 digits) not mint.
- Lesson: No `RECEIVE` path gives attacker `+1M`; profit remains self-SEND minus which ledger blocks.

## Decision
If `Internal error` persists across SEND/RECEIVE/TokenAdmin with same ID family, mark **ledger mint BLOCKED**, report **validator bypass High** (Main `Before 2024 Ok 411222E0...` vs `After AmountBelowZero`) + **SSRF High** (`48 hits 2600:1900:0:2e02::400`, `metadata%23 → computeMetadata/` leak) without claiming ledger profit. Disk keep `2.8G free`, wallet `keeta_afen47... 9.999 KTA` held for fee-0 retest if needed.
