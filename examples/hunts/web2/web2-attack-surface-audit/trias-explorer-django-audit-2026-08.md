# trias-explorer Django 1.11 Public Explorer — Red-Team Audit 2026-08

**Repo:** `trias-lab/trias-explorer@8616f70` (157 files, `master` branch `pushed 2022-01-26`) — Python 3.4/Django 1.11 + React block explorer. 9 vectors from trust map tested via `raw.githubusercontent.com/trias-lab/trias-explorer/master` + `api.github.com/repos/*/git/trees/{sha}?recursive=1` (git `remote-https` missing on TencentOS 4).

## Route inventory (explorer_ui/urls.py — 10 GET-only endpoints)
```
^api/index_base_info/        index.index_base_info
^api/index_latest_blocks/    index.index_latest_blocks
^api/index_recent_transactions/ index.index_recent_transactions
^api/search/                 index.serach (typo, search by number/hash/tx/address)
^api/all_blocks/             blocks.all_blocks
^api/block_info/             blocks.block_info
^api/block_transactions/     blocks.block_transactions  ← sort param
^api/all_transactions/       transactions.all_transactions
^api/transaction_info/       transactions.transaction_info
^api/address/                address.address_info
^api/address_transactions/   address.address_transactions
```
No POST/PUT — explorer is intentionally read-only public.

## Finding matrix (code evidence + verdict)

| # | Vector (brief claim) | file:line | Proof | Verdict |
|---|---|---|---|---|
| 1 | CSRF disabled | `settings.py:39 # 'CsrfViewMiddleware'` | Commented out | **CONFIRMED but NOT EXPLOITABLE** — no state-changing endpoint to forge; correct for public GET explorer |
| 2 | QtsAuthentication passes `api` unchecked / auth bypass | `app/dispatcher.py:7-12` `if 'api' in request.path: pass else: render index.html` + `settings.py:46 MIDDLEWARE_CLASSES=[..., 'app.dispatcher.QtsAuthentication']` | Returns `None` for any path containing substring `api`; no credential check in any view (`grep login_required` = 0 hits) | **CONFIRMED — intentional public, name misleading**. Substring check bypassable (`/api../`), but no auth exists to bypass. Do NOT report as bypass; report as `ALLOWED_HOSTS=['*']` (L59)+ hard `SECRET_KEY` (L14) misconfig |
| 3 | `order_by(sort)` SQLi in `block_transactions` | `blocks.py:75 TransactionInfo.objects.filter(blockHash=block_hash).order_by(sort)` `sort=GET.get("sort",'-id')` | Django 1.11 `query.py:1671 add_ordering()` enforces `ORDER_PATTERN=re.compile(r'\?|[-+]?[.\w]+$')` (`sql/constants.py:35`). Space/`;`/`(`/`,` fail → `FieldError('Invalid order_by arguments')` → `except Exception: return {"code":201,"message":"ERROR"}` (L77-79) generic, no SQL exec. Valid `-id`/`hash`/`blockNumber` only reorders. | **DISPROVEN — NOT INJECTABLE** (FieldError, not SQL) |
| 4 | SQLi via `filter(number=key)` in `serach` | `index.py:91 Block.objects.filter(number=key)` `key=GET.get('key')` | ORM parameterized `WHERE number = %s` with `params=[key]` (`sql_with_params()`); payload `'1 OR 1=1'` bound as string literal. Sequential `filter(hash=key)`→`filter(hash=key)`→`filter(address=key)` is logic bug not injection | **DISPROVEN** |
| 5 | File disclosure `/static/conf.json` | `settings.py:82-85 STATICFILES_DIRS=[..., os.path.join(BASE_DIR,'conf')]` + `conf/conf.json:{"mysql_ip":"192.168.1.210","mysql_password":"8lab",...}` + `STATIC_URL='/static/'` no `static()` in `urls.py`, `DEBUG=False` | Django dev server won't serve; **standard nginx `alias STATIC_ROOT` + `collectstatic` WOULD expose at `/static/conf.json`** — creds leak is deploy-dependent. Anti-pattern: secrets in STATICFILES_DIRS | **CONFIRMED (conditional)** |
| 6 | Session poisoning via `X-Forwarded-For` | `dispatcher.py:33-44 AccessRestrictionsMiddleware: REMOTE_IP=META['HTTP_X_FORWARDED_FOR'] if present else REMOTE_ADDR; REQUEST_COUNT=session.get(REMOTE_IP); session[REMOTE_IP]=count` | Attacker controls session dict key (e.g. `XFF: _auth_user_id`). **Disabled:** `settings.py:42 # 'app.dispatcher.AccessRestrictionsMiddleware'` commented → inactive | **CODE VULNERABLE BUT DISABLED** |
| 7 | DoS via `Paginator size` | `blocks.py:18`, `transactions.py:18`, `address.py:28` `size=int(GET.get("size",50))` no max; `Paginator(total_data,size).page(page)` + `blocks.py:79 len(total_data)` (evaluates entire queryset) vs `count()` | `GET /api/all_blocks?size=1000000` or `/api/all_transactions?size=999999` loads 1M rows; `block_transactions` `len()` forces full load before slice. No rate limit (middleware disabled) → unauth memory/CPU DoS | **CONFIRMED** |
| 8 | Info disclosure via error messages | All views `except Exception: logger.error(e); return {"code":201,"message":"ERROR"}` + `DEBUG=False` | Generic ERROR, no traceback; residual `Need Block Hash`/`Block doesn't exist` existence oracle only | **MITIGATED — LOW** |
| 9 | Signature forgery / access control | `grep -rn signature\|hmac\|token` = 0 hits in app/ | No auth code — public read-only by design | **DISPROVEN** |

## Live proof recipes (curl)

```bash
# order_by — valid reorder vs injection → both 200/201 generic, injection raises FieldError not SQL
curl -s "http://target/api/block_transactions?block_hash=0xabc&sort=-id"
curl -s "http://target/api/block_transactions?block_hash=0xabc&sort=id;%20DROP%20TABLE%20block;--"  # → {"code":201,"message":"ERROR"}
curl -s "http://target/api/block_transactions?block_hash=0xabc&sort=nonexistent_field"              # → FieldError path same

# search — parameterized, not injectable
curl -s "http://target/api/search/?key=1%20OR%201=1"
curl -s "http://target/api/search/?key=0%20UNION%20SELECT%20*"

# conf.json — check STATIC_ROOT deployment
curl -s -o /dev/null -w "%{http_code}" http://target/static/conf.json  # 200 = leaked, 404 = DEBUG=False direct, check nginx alias
curl -s http://target/static/conf.json | jq .

# DoS — uncapped paginator
curl -s "http://target/api/all_blocks?size=1000000&page=1" -w " time:%{time_total}s size:%{size_download}\n"
curl -s "http://target/api/all_transactions?size=999999&page=1" | head -c 500

# QtsAuthentication substring bypass (no auth to bypass, but proves middleware is vacuous)
curl -s http://target/api../admin/  # contains 'api' substring → passes if middleware were auth

# XFF session poisoning — only if middleware re-enabled
curl -s -H "X-Forwarded-For: _auth_user_id" http://target/api/all_blocks?size=1
```

## Fixes (one-liners)

```diff
# sort param — whitelist (defense-in-depth even though ORDER_PATTERN blocks injection)
- sort = request.GET.get("sort", '-id')
+ ALLOWED_SORTS = {'-id','id','-blockNumber','blockNumber','-timestamp','timestamp','hash','-hash'}
+ sort = request.GET.get("sort", '-id') if request.GET.get("sort",'-id') in ALLOWED_SORTS else '-id'

# paginator DoS
- size = int(request.GET.get("size", 50))
+ size = min(100, max(1, int(request.GET.get("size", 50))))  # cap 100

# conf.json leak — move out of STATICFILES_DIRS, load from env/secret mount
- STATICFILES_DIRS = [os.path.join(BASE_DIR, 'html/static'), os.path.join(BASE_DIR, 'conf')]
+ STATICFILES_DIRS = [os.path.join(BASE_DIR, 'html/static')]
+ CONF_JSON = os.environ.get("TRIAS_CONF_JSON", "/etc/trias/conf.json")

# XFF — never trust without trusted-proxy list
- REMOTE_IP = request.META['HTTP_X_FORWARDED_FOR'] if 'HTTP_X_FORWARDED_FOR' in request.META else request.META['REMOTE_ADDR']
+ REMOTE_IP = request.META['REMOTE_ADDR']  # or check XFF only if REMOTE_ADDR in TRUSTED_PROXIES

# Existence oracle — optional: normalize messages
- return JsonResponse({"code":201,"message":"The block doesn't exist"})
+ return JsonResponse({"code":200,"return_data":None})  # consistent shape
```

## Acquisition pitfalls encountered (capture the fix, not "tool broken")

- **git clone fails** `git: 'remote-https' is not a git command` (TencentOS 4 lacks `/usr/libexec/git-core/git-remote-https`): use `curl -L -o /tmp/repo.zip https://github.com/<org>/<repo>/archive/refs/heads/main.zip` + `unzip -q` or `tar.gz` fallback; enumerate files via `api.github.com/repos/<org>/<repo>/git/trees/{sha}?recursive=1` (60 req/hr anon).
- **Django 1.11 on Python 3.11** `from collections import Iterator` fails: shim `import collections, collections.abc; for n in ['Iterator','Mapping',...]: setattr(collections,n,getattr(collections.abc,n))` before `django.setup()`; also `mkdir -p /var/log/trias` for `RotatingFileHandler`.
- **Verify ORDER_PATTERN directly** from `raw.githubusercontent.com/django/django/1.11.5/django/db/models/sql/constants.py` (`r'\?|[-+]?[.\w]+$'`) and `query.py:1661 add_ordering` — don't assume injection.

## Quality checklist for Django public explorers

- [ ] `ORDER_PATTERN` kill-test: payload with space/`;`/`--` → `FieldError` vs SQL? Mark BLOCKED if FieldError + generic ERROR.
- [ ] `filter(field=user_input)` always parameterized — confirm `sql_with_params()` shows `%s` + params list, not string concat.
- [ ] `STATICFILES_DIRS` does NOT contain `conf/`/`secrets/`/`*.json` with creds; check `curl /static/conf.json`.
- [ ] `X-Forwarded-For` only trusted behind explicit `TRUSTED_PROXIES` list; otherwise `REMOTE_ADDR`.
- [ ] Paginator `size` capped (≤100), use `count()` not `len(queryset)`, set `MaxBytesReader`/`DATA_UPLOAD_MAX_MEMORY_SIZE`.
