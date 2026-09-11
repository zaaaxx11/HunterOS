# Keeta Faucet & Trusted Funding — Opening vs Successor Publish Pitfall (2026-08-12)

## Faucet Hunting (Testnet Prod — No Public Faucet)
- `explorer.test.keeta.com/api/v1/faucet` → `404 Not Found` (GET + POST)
- `publish-aid.test.network.api.keeta.com/api/publish` → `POST {} 500 {"error":"Missing blocks"}` / `GET 500 {"error":"Unrecognized request"}` — not a faucet, only `votes_and_blocks` publish proxy
- `rep1.test.network.api.keeta.com/api/publish` → `Cannot GET /api/publish` (rep publish is via `POST /node/publish` with staple, not faucet)
- `faucet.test.network.api.keeta.com` → `NameResolutionError` (DNS NX); `faucet.test.keeta.com/api/faucet` → `404` / `503 Service Unavailable`
- `/openapi.json` / `/docs` on rep & publish-aid → `404` / `500 Unrecognized request`
- Lesson: `init_supply` in `e2e.rs:81` / `node-harness/e2e-node.ts:13 handleInitSupply` is harness-only (local `keetanetwork-utils`), absent in prod. Prod testnet rep `TRUSTED=keeta_aabmvemiol5wrs67e4rfiyibopwav4e77sleiqaqvbdprbuxrifn7fgg4cchhia` already funded (`explorer GET ...?networkAlias=test → balance 90000000001, supply 1000011105199999999999991, headBlock CD09331C...`), but no public mint.

## Trusted Seed 0x77 Funding Attempt
- Harness deterministic seed `Buffer.alloc(32,0x77)` = `[0x77;32]` per `keetanetwork-client/tests/e2e.rs:170 TRUSTED_SEED_BYTE: u8=0x77`, `keetanetwork-client-wasi/host-tests/tests/java_token_supply.rs:62 TRUSTED_SEED_BYTE` and `e2e.rs:146 signing_accounts()` → `generate_ed25519_ref(0x77)` derives trusted.
- Attempt: `UserClient::from_network(Test, Some(trusted0x77))` + `KeetaClient::balance(&*trusted,&*token)` where `token = trusted.generate_identifier(TOKEN,None,0)`. Hits compile pitfalls: `SecretBox<[u8;32]>: From<[u8;32]>` not satisfied — must use `([0x77u8;32].into(), 0).into()` via `IntoSecret` + `Keyable::Seed((seed,0))` single arg, and `Arc<GenericAccount>` requires `&*` + `AccountPublicKey` trait for `balance`.
- Prod `trusted 0x77` may be rotated — explorer trusted address is parsed from `MAIN_TRUSTED`/`TEST_TRUSTED` strings, not necessarily `0x77`. Need to compare derived `trusted.to_string()` vs `keeta_aabmvemi...` to confirm match before assuming faucet.
- Fund flow if trusted valid: `UserClient::send(dummy, TOKEN, "1000")` (via `client.send` → `TransactionBuilder` → `VoteStaple` → `transmit` quorums). Without valid trusted key, fund fails.

## Opening vs Successor Publish Pitfall
- Dummy publish earlier used `BlockBuilder::as_opening()` with `previous = opening_hash` and `saldo 0` → `Main EB3319A7 len 248` and `Test 4AC7E2AD len 250` both `PUBLISH ERR Node Code "" Internal error ID f6435602... / 348d70a9...` — NOT `AmountBelowZero`, NOT `LEDGER_INSUFFICIENT_FUNDS`.
- Root cause: `opening_hash` debit with zero balance is rejected by ledger regardless of minus logic. Validates: `BlockData::validate` lolos (`validate_numeric` before cutoff) but `ledger apply` blocks.
- Correct proof requires **successor** block: `with_previous(head_hash)` after funding dummy to `1000 KTA` head, then `SEND -1_000_000 self 2024` successor. Expected: `balance = 1000 - (-1e6) = 1_001_000` ghost mint vs `LEDGER_INSUFFICIENT_FUNDS` if ledger checks `amount >0` independently.
- Disk: `poc_publish_main/target` 1.6G filled `/` to 100%; `rm -rf target` + `cargo clean` recovered 2.5G; throttle rebuild 3m24s. Always `df -h` before second fork.

## Checklist for Future Funded Successor Proof
1. Probe `GET /api/v1/account/<trusted>?networkAlias=test` to confirm trusted balance >0
2. Derive `trusted0x77` and assert `derived == TEST_TRUSTED` — if mismatch, hunt other funding (faucet not via publish-aid)
3. `UserClient::from_network(Test, Some(trusted))` → `send(dummy, "1000")` → poll `head` / `balance`
4. Build successor: `BlockTime::from_unix_millis(1717200000000)` + `Amount::from(-1_000_000i64)` + `token = KTA (trusted-derived TOKEN)` + `with_previous(head)` + `sign()` → `publish()` → observe `LEDGER_*` vs ghost balance
5. Report fee vs ghost mint distinction: fee is separate positive `Amount` via `fee_block`, ghost mint is `TokenAdminSupply`-less `balance -= (-amt)`.

## Pitfall
Never claim faucet exists from harness `init_supply` — harness-only. Always live-probe `/api/v1/faucet`, `publish-aid`, `rep /publish` with `curl`/`requests` before assuming funding. Opening block Internal error ≠ amount validation — fund first, then test successor.
