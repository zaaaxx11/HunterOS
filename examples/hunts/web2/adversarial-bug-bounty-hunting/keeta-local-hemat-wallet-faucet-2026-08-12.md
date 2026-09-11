# Keeta Local Hemat — Disk Budget + Wallet + Faucet (2026-08-12)

## Disk Budget (20G VPS)

| State | Free | Used | Trigger |
|-------|------|------|---------|
| Initial 3 pocs built | 909M | 96% | `aws-lc-sys ar: No space left on device` |
| After `rm -rf /tmp/poc_*/target ~/.cargo/registry/cache pip cache` | 2.5G | 88% | OK for single-crate |
| After wallet gen + `rm -rf /tmp/wallet_KTA/target` | 2.3G | 89% | keep >2G |
| Target safe | 2.5-2.9G | 86-88% | threshold for `cargo build` |

**Pre-flight mandatory:**
```bash
df -h; free -h; du -sh /tmp/* | sort -rh | head -n 30; du -sh /root/* | sort -rh | head -n 30
# also check: cargo --version; node --version; npm --version; java -version
```

- `aws-lc-sys` builds `libaws_lc_*_crypto.a` via `ar cqD` — needs ~1.6G contiguous. 909M fails deterministically.
- Full `node-harness` = `npm install 300-500M` + `cargo target 3-4G` = guaranteed OOM on 20G. Hemat single-crate `<200M` avoids it.

## Hemat POC Pattern

Single crate with only:
```toml
[dependencies]
keetanetwork-account = { path = "/tmp/keeta_src/node-rs-main/keetanetwork-account", features = ["std"] }
keetanetwork-crypto = { path = "/tmp/keeta_src/node-rs-main/keetanetwork-crypto", features = ["std","signature"] }
# no keetanetwork-client (pulls aws-lc-sys heavy), no node-harness, no java
```

Proves: `BlockBuilder::with_network(0x5382).with_date(1717200000000).with_operation(Send{amount:-1e6, token:TOKEN}) -> Ok(411222E0...)` vs `After 2026 -> AmountBelowZero`. No funded account, no `init_supply`.

## Wallet Generation (Hemat, 1-10 KTA)

```rust
use keetanetwork_account::{Account, Accountable, GenericAccount, KeyED25519, KeyPairType, Keyable};
use keetanetwork_crypto::prelude::ExposeSecret;
let seed = Account::<KeyED25519>::generate_random_seed()?;
let seed_hex = hex::encode(seed.expose_secret());
let acc: Account<KeyED25519> = Account::try_from(Accountable::KeyAndType(Keyable::Seed((seed, 0)), KeyPairType::ED25519))?;
let generic = GenericAccount::Ed25519(acc);
let token = match &generic { GenericAccount::Ed25519(a) => a.generate_identifier(KeyPairType::TOKEN, None, 0).unwrap(), _ => unreachable!() };
// universal address: same on main/test/dev
let json = format!(r#"{{"seed_hex":"{}","address":"{}","token":"{}"}}"#, seed_hex, generic, token);
std::fs::write("/tmp/wallet_KTA.json", &json)?;
```

Live example (2026-08-12):
```json
{"seed_hex":"<redacted>","address":"keeta_afen47xmyv5h7be7er37yqkowvzakxieqzcpuhofznpxm2dwippelqsvlkefk","token":"keeta_aocratkgvoh4njdmzhmmogse75v77enucomew2ac2ht56wv5klxbawvhshilq","network":"main/test universal"}
```
- `269 bytes` JSON, `1.1K` source, `target ~200M` (delete post-run).
- Fee `~0.001 KTA` per block → 1 KTA = 1000 blocks, 10 KTA comfortable. Fresh `headBlock null, tokens []` until funded.

## Faucet Test Matrix (faucet.test.keeta.com)

| Request | Response | Meaning |
|---------|----------|---------|
| `GET https://faucet.test.keeta.com` | `200 len 215620` + text `Keeta Testnet Faucet` | Frontend alive |
| `POST /api/faucet {"address": "keeta_..."}` | `503 Service Unavailable` | Backend down/rate-limited |
| `POST /api/faucet {"account":...}` | `503` | same |
| `POST /api/claim {"publicKey":...}` | `500 Server Error Google Frontend` | same |
| `POST /faucet {"address":...}` | `500` | same |
| `GET /api/faucet?address=...` | `404` | wrong method |
| `GET explorer.test/api/v1/account/keeta_...?networkAlias=test` | `200 headBlock null tokens []` | pre-balance |

**Correct parse:** HTML is favicon-heavy (`data:image/x-icon;base64,AAABAAMA...` repeated). Extract real text via:
```python
text = re.sub(r'<[^>]+>', ' ', html); text = re.sub(r'\s+', ' ', text)
# yields "Keeta Testnet Faucet"
# find api hits: re.finditer(r'/api[^\s"\'<>]+', html)
```

Try all 4 payload keys: `address`, `account`, `publicKey`, `to` — faucet may accept one. Expect `503/500` = down, not invalid address. Advise user browser + CAPTCHA, don't loop.

## Post-Cleanup Checklist (after every hemat run)

```bash
rm -rf /tmp/poc_*/target /tmp/wallet_KTA/target ~/.cargo/registry/cache
pip cache purge 2>&1 | tail -n 5; npm cache clean --force 2>&1 | tail -n 5
find /tmp -maxdepth 3 -name "target" -type d 2>&1 | head -n 20
du -sh /tmp/* | sort -rh | head -n 20; df -h | head -n 10  # verify 2.5G+
```

User mantra: `Hemat klo udh selesai hapus lagi` — automate.

## Storage Paths
- `/tmp/wallet_KTA.json` (269 bytes, redacted in logs)
- `/tmp/wallet_KTA/src/main.rs` (1.1K)
- `/tmp/keeta_zips/*` (7.8M), `/tmp/keeta_src` (40M) — keep, don't delete unless repulled
