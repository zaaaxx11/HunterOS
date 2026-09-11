# Trias web-wallet fund-path deep dive (2026-08)

**Repo:** `trias-lab/web-wallet` (local: `/root/web-wallet/web-wallet-master`)  
**Stack:** Django 1.9/1.11-era, MEW frontend shell + Django swap/UTXO gateway  
**Scope:** pre-auth fund theft / coin mint via `swap.py`, `tri.py`, `account_util.py`, `block_util.py`  
**Report artifact:** `/root/WEB_WALLET_FUND_PATH_DEEP_DIVE.md`

## Route table (no app auth)

| Route | View | Auth |
|-------|------|------|
| `POST /api/newCoinbase` | `tri.newCoinbase` | **None** |
| `POST /api/newKeyValue` | `tri.newKeyValue` | **None** |
| `POST /api/tri` | `tri.tri` JSON-RPC shim | **None** |
| `POST /api/swap/order` | `swap.order` | **None** |
| `GET /api/files/(.*)` | `tri.files` | **None** |
| CSRF middleware | commented out in settings | disabled |
| CORS | `CrossDomainAccess` forces `*` | open |

## Best chain (honest)

```
[Trigger] POST /api/newCoinbase (no auth, body = serialized UTXO tx)
   → [Effect] requests.post(UTXO_URL + '/broadcast_tx', {'tx': request.body})
   → [TrustBoundary] wallet validates NOTHING; UTXO node at conf utxo_url must reject illegal coinbase
```

- Client (`get_coinbase.js`) builds coinbase: Vin empty/`-1`, markers `www.8lab.cn`/`www.trias.one`, **value = 100e18**, arbitrary `to`.
- Server never calls `new_coinbase_tx` / `is_coinbase()` — pure proxy.
- **Impact class: mint** if node accepts non-miner coinbase; else **DoS** (unauth broadcast spam).
- Do **not** claim free coins without node policy evidence.

## Swap is NOT free hot-wallet drain

`swap.order` only creates `Order` + deposit address (`DBOperation.genNewAddress`).  
`Worker.checkDBPendingOrder` → `sendInnerOutTransaction` **only when** `source_coin_payment_amount >= source_amount` (on-chain inbound observed).  
Capital-in required → economic swap, not pre-auth theft.

**Coin-name footgun:** swap pairs use `TRI`/`ETH`; worker/account constants use `TRY` (`COIN_NAME_TRI = "TRY"`). Matching bugs can break payout reliability — report as integrity bug, not free mint.

## AES hot-wallet keys (design vs shipped)

- Ciphertext in MySQL `address.encrpyted_private_key`.
- KEK: `records["private_key_encrypt_pass"]` from `conf/conf.json`.
- AES-CBC, **fixed IV** `b"IV"*8`, pad key/plaintext with spaces/`-` (no KDF).
- Shipped conf: `"private_key_encrypt_pass": ""`.
- `pad(b'', b' ')` → **0-byte key** (`len % 16 == 0` skips pad) → AES init fails on pycryptodome/pycrypto modern → empty pass is **broken KEK**, not silent decrypt-all.
- If pass is non-empty + conf LFI + DB dump → full hot-wallet key recovery (theft pivot).

## files() path traversal = info, not RCE

```python
path = os.path.join(BASE_DIR, 'wallet/static/files/' + fileName)
# ../../../conf/conf.json resolves under BASE_DIR → conf leak
```

Leaks: `utxo_url`, mysql `8lab:<REDACTED>`, empty AES pass, eth RPC IP/port.  
Class: **info**. Pivot to theft only if MySQL reachable + working KEK.

Also: `STATICFILES_DIRS` includes `conf/` — if `collectstatic` + nginx serves STATIC_ROOT, `/static/conf.json` may leak without traversal (same class as trias-explorer).

## UTXO SSRF is NOT user-controlled

`UTXO_URL = records['utxo_url']` fixed. User influences query values (`address`, `hash`) and tx body content only — fixed internal host. Label **no** for classic URL-SSRF.

`eth_sendRawTransaction` recovers sender from raw tx and spends **that sender’s** UTXOs — user-fund path if they signed, **not** server hot-wallet drain.

## newKeyValue

Unauth build+broadcast of KV-shaped tx (`new_keyValue_tx`). Spam/state write; not subsidy-sized mint. Secondary to newCoinbase.

## Offline coinbase body sketch (≤40 lines concept)

Build JSON matching `Transaction.serialize` + RIPEMD160 ID, replace `"`→`'`, POST as body to `/api/newCoinbase`.  
SUBSIDY = `int(100*1e18)`. Prefer local mock of `broadcast_tx`; do not aim live infra from the skill.

## Checklist for next MEW/Django custodian wallet

1. Enumerate urls.py for `newCoinbase|broadcast|sendRaw|swap/order|files`.
2. For each mint/broadcast path: auth? body validation? node-side check assumed?
3. Trace swap order → worker payout gate (payment amount vs free).
4. Find KEK source (conf/env); test empty/default pad key lengths; fixed IV?
5. Path join on user filename → conf/DB credential LFI.
6. Classify one best chain: theft | mint | info | DoS — node-dependent mint stays conditional.
7. Coin ticker mismatches (TRI vs TRY) as integrity, not severity inflation.

## Code anchors

- `etherwallet/urls.py` — routes
- `wallet/views/tri.py:283-308` newCoinbase; `116-155` eth_sendRawTransaction; `353-372` files
- `wallet/views/swap.py:36-105` order
- `wallet/utils/tx_cli.py:12-20` SUBSIDY coinbase
- `wallet/utils/account_util.py:19-59,94-173` AES + hot sign
- `wallet/utils/block_util.py:500-566` paid-only payout
- `conf/conf.json` empty encrypt pass, internal UTXO/MySQL
