# trias.one — Pure Static Umi SPA, No API Handoff (2026-08-16)

Target: `https://trias.one/` (nginx 1.29.4, Umi 4.0.89) vs `trias-lab/trias-explorer` Django. Proves isolation pattern for explorer-vs-marketing-site audits.

## Fingerprint
- `GET /` → `200 text/html 456B` `<!DOCTYPE><meta viewport><link href=/umi.7e8c388d.css><div id=root><script src=/umi.fd4cb998.js>` — `Server: nginx/1.29.4`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`, `X-Content-Type-Options: nosniff`, `Access-Control-Allow-Origin: https://www.trias.one`, `methods: GET, POST, OPTIONS`.
- `GET /www.trias.one/` same 456B.
- `GET /umi.fd4cb998.js` → `515579B application/javascript` — single bundle `!function(){...redux...Un/Tn...}` with `fetch(a,{credentials:"include"})` once (umi internals), routes `/ /future /economy /aboutTrias /governance /technology /trustedFi /*→/` + `/Error`, no `explorer` refs, no `fetch("` to `/api`.
- `GET /umi.7e8c388d.css` → `89539B`.

## Isolation Proof (catch-all 200, not 404)
| Probe | Status | Body | Verdict |
|-------|--------|------|---------|
| `GET /api/`, `/api/search`, `/api/index_base_info` | 200 | 456B `<!DOCTYPE` same as `/` | SPA fallback, **no proxy** |
| `GET /health`, `/server-status`, `/nginx_status` | 200 | 456B | same fallback |
| `GET /.env`, `/package.json` | 200 | 456B | same |
| `GET /robots.txt`, `/sitemap.xml`, `/.well-known/security.txt` | 200 | 456B | same |
| Explorer domains `explorer.trias.one`, `explorer-trias.trias.one`, `explorer.trias-lab.com` | DNS `NXDOMAIN` / TLS `unrecognized_name` | — | no live explorer host found |

## Checklist for Marketing-SPA vs Explorer Audits
1. `curl -sI https://trias.one/` → record `Server:` (Gin/Caddy/nginx tells stack) + `X-Frame-Options/CORS`.
2. `curl -s https://trias.one/ | head -c 2000` → extract `<script src=` + `<link href=` + headers.
3. Fetch bundle(s) `curl -s https://trias.one/<bundle>.js | python3 -c "import re,sys;t=sys.stdin.read(); print(re.findall(r'https?://[^\\s\"\\']+',t)[:20]); print(re.findall(r'path:\"/[^\"]+\"',t)[:20])"` → routes, fetch, api bases.
4. Prove no proxy: `for p in /api /api/search /health; do curl -s https://trias.one$p | head -c 200; echo ---$p; done` — if `<!DOCTYPE` identical to `/` → fallback, not API.
5. GitHub org recon: `GET /users/trias-lab/repos?per_page=100` — trias-lab has 16 repos (trias-explorer JS, erc20, Documentation, wallet TypeScript etc.) — `trias.one` repo not under `trias-lab` (private or different org).
6. Report as: Umi version, nginx version, bundle sizes, route list, isolation table, external links (`wallet.trias.one`, `monitor.trias.one`), headers.

## Pitfall
Don't conflate `trias.one` Umi 4 SPA (marketing, isolated) with `trias-explorer` Django (explorer, 8 api groups). Task brief listed "trias.one SPA (Umi 4.0.89, nginx 1.29.4)" — those versions are from live `Server:` + bundle, not repo.
