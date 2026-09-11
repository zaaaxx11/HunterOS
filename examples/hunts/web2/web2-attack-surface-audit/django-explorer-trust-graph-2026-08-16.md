# Django 1.11 Explorer Audit — 14 Trust Boundaries (Trias 2026-08-16)

Reused from `/root/TRIAS_TRUST_GRAPH.md` + `/tmp/trias_audit/trias-explorer/*`. Use when target is Django explorer / block explorer.

## Stack
- Django 1.11.5 EOL (40+ CVEs), `django-webpack-loader 0.2.4`, `requests`, `apscheduler`, `ALLOWED_HOSTS=['*']`, `SECRET_KEY` hardcoded, `DEBUG=False`, `CSRF` commented out, `SecureRequiredMiddleware` + `AccessRestrictionsMiddleware` both commented out (disabled). `STATICFILES_DIRS=[html/static, conf]` exposes `conf/conf.json` as `/static/conf.json` → DB `192.168.1.210:3306 trias_string_9981 / 8lab:<REDACTED>` leaked (CRITICAL).
- `QtsAuthentication` sole active middleware: `if 'api' in request.path: pass else render_to_response('index.html')` — substring bypass (`/myapi` passes, `/API/` fails), not auth.
- 11 api routes = 8 logical groups: `all_blocks, block_info, block_transactions, all_transactions, transaction_info, address, address_transactions, index_base/latest/recent, serach` (typo).

## Handoffs
- `GET ?size/page/sort/block_hash/tx_hash/address/key` → `int()` fallback → `Paginator` (no upper clamp → DoS) → `order_by(sort)` where `sort` user-controlled → ordering injection field enum + DoS on TEXT sort (HIGH, `blocks.py:135`). Allowlist `id,-id,blockNumber` else 400.
- `block_info` assumes `Block.objects.get(number+1)` contiguous → `DoesNotExist` on gap/reorg.
- `address_info` loads ALL `values_list('value')` → `int()` loop + N×`Block.get(number)` → OOM on exchange address.
- `serach` sequential `filter(number=key).exists() → hash → tx hash → address` → existence oracle + timing side-channel, no rate limit.
- `block_util.url_data/simple_request` → `requests.post(url, json={jsonrpc,method,params}, timeout=1)` with `JsonConfiguration.eth_ip/port` from `conf.json` (today "" dormant SSRF).
- Frontend `Main.js` `match.params.blockID → $.ajax data:{block_hash:blockID}` no sanitize but ORM parameterized → no SQLi; React escapes → no XSS.

## Checklist
1. `curl https://raw.githubusercontent.com/<org>/<repo>/master/explorer_ui/settings.py | grep -E 'ALLOWED_HOSTS|SECRET_KEY|Csrf|SecureRequired|AccessRestrictions|STATICFILES_DIRS'`
2. `curl -s https://raw.githubusercontent.com/<org>/<repo>/master/conf/conf.json` — if 200, CRITICAL static leak.
3. `grep -rn 'order_by.*sort\|order_by.*request' app/views --include='*.py'` → ordering injection.
4. `grep -rn 'Paginator' app/views --include='*.py'` → clamp `size`.
5. Probe `GET /api/block_transactions/?block_hash=0x…&sort=nonexistent` → 500→201 oracle; `sort=tx_str` → CPU DoS.
6. Frontend `grep -rn 'dangerouslySetInnerHTML\|innerHTML\|\.html(' html --include='*.js'` → XSS.

## Fixes P0: rotate SECRET_KEY to env + BFG, remove `conf` from STATICFILES_DIRS, allowlist `sort`, clamp size≤100, length check hash≤66 addr≤42.
