# Trias Explorer Django 1.11 + trias.one Umi SPA + TRYSimple ERC20 — Trust Graph (2026-08-16)

Source: `trias-lab/trias-explorer` (157 files, Django 1.11.5 EOL, React 16 + jQuery 1.12), `trias-lab/erc20/TRYSimple.sol` (sol 0.4.24), `trias.one` live (Umi 4.0.89, nginx 1.29.4, 515KB `umi.fd4cb998.js`).

## Topology
- `trias.one` = **pure static Umi SPA** — `index.html` 456B shell `<div id=root><script src=/umi.fd4cb998.js>` + routes `/ /future /economy /aboutTrias /governance /technology /trustedFi /*→/`. nginx `SAMEORIGIN, nosniff, XSS-block, CORS=www only, try_files → /index.html`. Every `/api/*, /.env, /health, /nginx_status` returns same 456B HTML — **no API proxy, isolated, zero handoff to explorer**. External only: `wallet.trias.one`, `monitor.trias.one`.
- `trias-explorer` Django: `html/app.js` → `Main.js/Home.js/BlockList/BlockDetail/TransactionList/TransactionDetail/Address` → `$.ajax GET /api/*` → `explorer_ui/wsgi.py get_wsgi_application()` → `QtsAuthentication` → `urls.py` 11 api routes + `"/" → index.html` → 8 logical view groups → ORM `Block/TransactionInfo/Address` → MySQL `192.168.1.210:3306 trias_string_9981 / 8lab:<REDACTED>` (from `conf/conf.json` via `CONF_JSON = STATICFILES_DIRS[1]+"/conf.json"`).
- `block_util.url_data/simple_request` → `requests.post(url, json={jsonrpc,method,params,id}, timeout=1)` → `JsonConfiguration.eth_ip:eth_port` (today `""` — dormant SSRF if ever set).
- `TRYSimple.sol` = isolated ERC20, `balances private`, `allowance public`, no owner/mint/pause.

## 14 Trust Boundaries (full map in `/root/TRIAS_TRUST_GRAPH.md`)
| # | Boundary | Source → Sink | File:line | Sev |
|---|----------|---------------|-----------|-----|
| T1 | Anon → ORM | `GET ?*` → `filter/order_by` | `app/views/*.py` | MED |
| T2 | Host → Django | `Host:` → `ALLOWED_HOSTS=['*']` | `settings.py:20` | MED |
| T3 | Conf → Public | `conf.json` → `STATICFILES_DIRS=[...,conf]` → `GET /static/conf.json` | `settings.py:82-87` | **CRIT** |
| T4 | Path substring | `'api' in path` → `pass` else SPA | `dispatcher.py:12` | LOW |
| T5a | `sort→order_by` | `GET sort=-id` → `.order_by(sort)` | `blocks.py:118,135` | HIGH |
| T5b | `size/page→Paginator` | no upper clamp | `blocks.py:19` etc | MED |
| T5c | `hash/addr→filter` | no length check (max 255) | all views | NOTE |
| T5d | `transaction_info` silent | missing→`200+[]` | `transactions.py:73` | LOW |
| T6 | `serach` oracle | `key→4×exists()` sequential | `index.py:145` | MED |
| T7 | `block_info` gap | `last().number+get(n+1)` assumes contiguous | `blocks.py:91` | LOW |
| T8 | `address*` full scan | `values_list('value')` + N×`Block.get` | `address.py:30` | HIGH |
| T9 | `XFF→session[IP]` | client-controlled XFF | `dispatcher.py:42` | HIGH(dormant) |
| T10 | `is_secure` disabled | `HTTPS_SUPPORT=False` | `dispatcher.py:18` | MED |
| T11 | `SECRET_KEY` leaked | hardcoded | `settings.py:17` | HIGH |
| T12 | URL params→`$.ajax→ORM` | `match.params→$.ajax` | `Main.js:78` | NOTE |
| T13 | `eth_ip→requests.post` | dormant SSRF | `block_util.py:9` | NOTE |
| T14 | `approve` race | `allowance= _value` overwrite | `TRYSimple.sol:102` | MED |

## Repro (git-https broken on host — `/usr/local/libexec/git-core/git-remote-https` missing)
```bash
# Trees API + raw fetch (avoid git clone https)
curl -s "https://api.github.com/repos/trias-lab/trias-explorer/git/trees/master?recursive=1" | python3 -c "import json,sys;d=json.load(sys.stdin);print([t['path'] for t in d['tree']])"
for p in explorer_ui/settings.py explorer_ui/urls.py app/dispatcher.py app/views/blocks.py app/views/index.py app/views/address.py app/views/transactions.py app/utils/block_util.py conf/conf.json; do curl -s "https://raw.githubusercontent.com/trias-lab/trias-explorer/master/$p" -o "/tmp/trias_audit/trias-explorer/$p"; done
curl -s "https://raw.githubusercontent.com/trias-lab/erc20/master/TRYSimple.sol" -o /tmp/trias_audit/erc20/TRYSimple.sol
curl -sI "https://trias.one/"  # Server: nginx/1.29.4
curl -s "https://trias.one/umi.fd4cb998.js" | wc -c  # 515579
curl -s "https://trias.one/api/search"  # also 456B SPA fallback — proves isolation
```

## Remediation P0
1. Rotate `SECRET_KEY` → env, BFG history.
2. Remove `conf` from `STATICFILES_DIRS`, `conf.json` from repo, move DB creds to env, rotate leaked DB password.
3. Allowlist `sort`: `ALLOWED_SORTS={"id","-id","blockNumber","-blockNumber"}` else 400; clamp `size≤100`, length check hash≤66/addr≤42.
