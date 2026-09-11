# Trias Fuzz 2026-08 — Django 1.11 Paginator + ORM + TRYSimple.sol

Source: `trias-lab/trias-explorer` (Django 1.11.5, 8 API endpoints, `conf/conf.json`) + `trias-lab/erc20/TRYSimple.sol` (sol 0.4.24, SafeMath, TRY token).
Date: 2026-08-16. Harness: `/root/fuzz_harness.py` (60K, 120+ payloads), live runners `/tmp/run_fuzz3.py` + `/tmp/run_fuzz4b.py` (SQLite in-memory), results `/tmp/fuzz_live.json` (85 tests: 52 PASS / 19 CRASH / 9 INFO / 5 BYPASS). Report: `/root/FUZZ_ENGINEER_TRIAS_REPORT.md`.

## Fetch fallback (TencentOS)

`git clone https://` fails `git: 'remote-https' is not a git command` — `/usr/local/libexec/git-core` lacks `git-remote-https`.
Fallback (verified on trias + berachain 69 repos):
```bash
curl -L --max-time 60 https://github.com/trias-lab/trias-explorer/archive/refs/heads/master.tar.gz -o /tmp/trias.tar.gz && mkdir -p /tmp/trias && tar xzf /tmp/trias.tar.gz -C /tmp/trias --strip-components=1
# dir listing:
curl -s "https://api.github.com/repos/trias-lab/trias-explorer/contents/app/views?ref=master" | jq -r '.[].name'
# single file:
curl -s "https://raw.githubusercontent.com/trias-lab/trias-explorer/master/app/views/blocks.py"
```

## Django 1.11 on Python 3.11 compat

`collections.Iterator/Mapping/Sequence` moved to `collections.abc`; `DjangoTranslation.set_output_charset` removed. Before `django.setup()`:
```python
import collections, collections.abc
for attr in ['Iterator','Mapping','Sequence','MutableMapping','MutableSequence','MutableSet','Set','Counter']:
    if not hasattr(collections, attr) and hasattr(collections.abc, attr):
        setattr(collections, attr, getattr(collections.abc, attr))
```
For Paginator-only tests avoid `django.setup()` — configure minimal settings and import `Paginator` directly:
```python
from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=False, SECRET_KEY='x', USE_I18N=False, USE_TZ=False, LANGUAGE_CODE='en-us')
from django.core.paginator import Paginator, EmptyPage
```

## Oracles

| Sink | File:Line | Payloads | Oracle |
|------|-----------|----------|--------|
| Paginator size/page | `app/views/blocks.py:11`, `address.py`, `transactions.py` — `int(size)` guard + `size<=0` fallback | `0, -1, -99999, 9999999, 2^31, "0.5", "NaN", "Infinity", "", "   ", "\x00", "A"*10000, "0x10", "1e6", "５０", "+50", "-0", None, 0.5 float, `page=9999999` | Guard PASS (all fallback to 50/1). Raw `Paginator(data,0)` → `ZeroDivisionError`; `""`→`ValueError`; `None`→`TypeError`; `inf`→`OverflowError`; `nan`→`ValueError`; `-1`→`num_pages=-100` (no crash but nonsense) |
| Paginator empty qset | `Paginator([],50)` | empty list | `num_pages=1, allow_empty_first_page=True` → `page(1)` returns `[]` (no EmptyPage). With `allow_empty_first_page=False` → `num_pages=0` → `EmptyPage` |
| DoS len vs count | `app/views/blocks.py:block_transactions` `len(total_data)` vs `all_blocks: count()` | block with 100k txs | `len(qs)` evaluates all rows into memory; `count()` does `COUNT(*)`. Flag `len(total_data)` |
| order_by sort | `app/views/blocks.py:block_transactions` `sort=request.GET.get("sort",'-id')` → `order_by(sort)` | `id; DROP TABLE --`, `' OR '1'='1`, `id --`, `id /*`, `id) UNION SELECT`, `nonexistent_field`, `id\n`, `id\x00`, `""`, `"   "`, `A*500`, `1`, `__class__` | All SQL meta-char payloads → `FieldError: Invalid order_by arguments` (Django validates against model fields). Proved live with SQLite in-memory `FuzzBlock` model. `nonexistent_field` → `Cannot resolve keyword`. Valid `"-id"/"number"/"hash"` PASS. View swallows FieldError → generic `201 ERROR` (no field leak when DEBUG=False) |
| serach number coercion | `app/views/index.py:serach` `Block.objects.filter(number=key)` BigIntegerField | `key="abc"` | SQLite `WHERE number='abc'` → no match (strict). MySQL `WHERE number='abc'` → `0` (implicit string→int) → returns block 0 incorrectly. Verified via live SQLite comparison |
| serach very long key | `serach` 4 sequential `filter(field=key)` | `A*10000` | 4 queries with 10k param → full scans + log bloat; no length limit at view |
| block_hash/tx_hash null byte | `app/views/blocks.py:block_info` `filter(hash=block_hash)` | `0xabc\x00def` | Python preserves `\x00` but MySQL C connector truncates at null byte → prefix match bypass |
| block_hash very long | `CharField max_length=255` but no view check | `a*10000` | ORM query with huge string → large query + log bloat |
| address_info int(value) | `app/views/address.py:address_info` `sent += int(sent_value)` where `value` CharField | `""`, `"abc"`, `"1.5"`, `"0x10"`, `None` | `int("")`/`int("abc")` → `ValueError` → whole address lookup returns `201 Address Error` (DoS: single malformed tx breaks address). `int("9"*1000)` succeeds (big int); `int("-100")` succeeds (negative) |
| transaction_info orphan | `app/views/transactions.py:transaction_info` `Block.objects.get(number=number)` without try | orphan tx referencing missing block | `DoesNotExist` caught by outer `logger.error(e)` but falls through to `200 []` (inconsistent) |
| stamp2datetime | `app/utils/block_util.py:stamp2datetime` `time.localtime(int(stamp))` | `0`→`1970-01-01`, `-1`→`1969`, `9999999999999`→`318857`, `"1.5"`→`ValueError`, `"abc"`→`ValueError`, `None`→`TypeError`, `""`→`ValueError`, `"9"*20`→`OverflowError`, `"0x10"`→`ValueError` | Crashes only if DB poisoned (BigIntegerField should be int); per-item crash hides all blocks via outer ERROR |
| hex2int | `app/utils/block_util.py:hex2int` `int(hex_str,16)` | `""`→`ValueError`, `None`→`TypeError`, `"xyz"`→`ValueError`, `"0x"+"f"*100` PASS | — |
| conf.json static | `explorer_ui/settings.py: STATICFILES_DIRS=[..., conf]` | `GET /static/conf.json` | `{"mysql_ip":"192.168.1.210","mysql_user":"8lab","mysql_password":"<REDACTED>"}` — CRITICAL credential disclosure (nginx serves /static/ even with DEBUG=False) |
| url_data SSRF | `app/utils/block_util.py:url_data` `requests.post(url, json=params)` | `url` from `JsonConfiguration` (conf.json `eth_ip`) | No user-input sink in current views → PASS; latent sink if code evolves |

## TRYSimple.sol oracles

- `safeSub(0,1)` reverts (`require(b<=a)`), `safeAdd(max,1)` wraps to 0 then `require(c>=a)` reverts — correct.
- No raw `+/-` outside SafeMath — PASS. No `safeMul` (latent).
- `transfer(_value=0)` → `require(balance>=0)` always true → 0-value Transfer event (log spam, inconsistent with `transferFrom` which has `require(_value>0)`).
- `transferFrom` missing `require(_from != 0x0)`.
- `approve` race: `allowance[msg.sender][_spender]=_value` without `_value==0 || allowance==0` guard → front-run 100→50 drains 150; missing `increaseApproval/decreaseApproval`.
- `allowance` mapping `public` + `function allowance()` shadowing — confusing but safe.
- Constructor `balances[msg.sender]=_initialAmount` without `*10**decimals` — deployer must add 18 zeros manually.
- Sol 0.4.24 outdated; no pause/blacklist; no external calls → no reentrancy.

## Execution snippets

```bash
python3 /tmp/run_fuzz3.py 2>&1 | head -n 60   # Paginator + stamp + int(value) live
python3 /tmp/run_fuzz4b.py 2>&1               # order_by FieldError + MySQL coercion proof
cat /tmp/fuzz_live.json | python3 -c "import json; d=json.load(open('/tmp/fuzz_live.json')); from collections import Counter; print(Counter(x['outcome'] for x in d))"
```
