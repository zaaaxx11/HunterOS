# Trias web-wallet theft-path patterns (2026-08)

Target class: Django 1.x MEW-fork backend + static conf + hot-wallet Worker (not client-only MEW).

## Live gate (this hunt)
- `trias.one` / `www` — live SPA only (nginx); `/api/*` → index.html, no backend proxy
- `wallet.trias.one`, `explorer.trias.one`, `monitor.trias.one` — NXDOMAIN
- Label code chains **PROVEN IN CODE** until DNS+HTTP prove otherwise

## Trust graph (warung)
| Node | Role |
|------|------|
| conf/ conf.json in STATICFILES_DIRS | etalase resep — MySQL + AES pass + internal RPC/UTXO |
| MySQL `address.encrpyted_private_key` | gudang kunci |
| AESCrypt CBC IV=`b"IV"*8`, key=password space-pad 16 | buka kunci |
| `is_inner=True` | brankas hot |
| Worker.sendInnerOutTransaction | kasir auto sign+broadcast |
| POST /api/swap/order | order only; payout after on-chain pay (not free drain) |
| POST /api/newCoinbase | unauth body → fixed utxo_url/broadcast_tx (mint if node dumb) |
| GET /api/files/(.*) | path join traversal; only js/css/wasm/html returned |

## Theft chain (conditional)
```
GET /static/conf.json
→ mysql_user/password + private_key_encrypt_pass
→ SELECT address, encrpyted_private_key, is_inner FROM address
→ AES-CBC decrypt → hot wallet privkey
→ sign + sendRawTransaction drain
```
**Blockers as-shipped sample conf:** `private_key_encrypt_pass=""` → AES key len 0 → decrypt fails until deploy sets password. MySQL IP often RFC1918 (need network path).

## Auth disproofs (do not overclaim)
- Django default session = **DB-backed** `sessionid` random key → leaked SECRET_KEY alone ≠ mint admin cookie
- `/admin/` mounted + empty app admin.py → still needs superuser password or DB write
- CORS `*` + CSRF off ≠ automatic admin session theft without existing cookie jar + XSS/network

## Files traversal
- `os.path.join(BASE, 'wallet/static/files/' + user)` no sanitize
- open() before Content-Type whitelist → non-whitelist ext can 500 after open (existence/FD), whitelist returns body
- Not RCE (no pickle/eval/template write)

## Git pull when remote-https missing
Use `api.github.com/.../git/trees/master?recursive=1` + `raw.githubusercontent.com` or codeload ZIP. Do not thrash on git clone.

## Parent synthesis rule
Chainer subagent may invent off-scope RCE from prior workspace reports. Parent must rebuild chain from this target’s file:line only.

## Classification cheat-sheet
| Finding | Class |
|---------|--------|
| conf static + DB + decrypt + hot sign | fund theft path (code HIGH, live if host+DB) |
| newCoinbase unauth relay | mint/DoS conditional on UTXO policy |
| files traversal | info disclosure |
| swap/order unauth | not free money if payment gate holds |
| SECRET_KEY hardcode alone | recon / secondary after DB write |
