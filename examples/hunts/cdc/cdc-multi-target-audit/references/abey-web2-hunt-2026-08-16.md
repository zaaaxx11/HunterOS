# Abey web2 + live RPC sweep — 2026-08-16

## Web2 map
- `abey.com` 192.0.78.204 WordPress.com Automattic (tls.automattic.com, Batcache, WordPress.com 429/x-hacker Want root). wp-json open (page 3954, wp/v2 jetpack yoast), users 429 blocked, xmlrpc 403, wp-content 403, sitemap sitemap.xml + news-sitemap.xml, robots Allow. Impact: brochure only, managed WP, no chain.
- `abeychain.com` 34.226.131.211 CloudFront AWS 301, not RPC. Real RPCs: `rpc.abeychain.com` 34.226.131.211 (mainnet) + `testrpc` + `interrpc.abeychain.com` (from abeyscan envs.js). Dig: www.abey.com→wpcomstaging, app.abey.com→108.156.144.29 S3, docs→gitbook, app-api→122.248.204.7 (3 IPs).
- `app.abey.com` S3+CloudFront React `main.44800156.js` → `REACT_APP_SERVER_URL=https://app-api.abey.com`, `baseURL:\"https://app-api.abey.com\"`, `action:\"https://app-api.abey.com/biz/avatar/upload\"`, Sentry `o4509282153398272.ingest.de.sentry.io/4509406372298832`, WalletConnect `dd3ebb3e9700...`, `https://abitype.dev`, `https://4byte.sourcify.dev`.
- `app-api.abey.com` Spring (timestamp/status/error/path JSON). `GET /` → 404, `GET /biz/avatar/upload` → 405 Method not supported, `POST /biz/avatar/upload {}` → 502 Error uploading image: null (needs token). `GET /actuator|/swagger` → 401 Not Authorized. Gate 401 on unknown paths. Backend protected.
- `abeychain.com docs` GitBook CSP `unsafe-eval unsafe-inline`. `abeyscan.com` Blockscout v2.3.5 Next.js `window.__envs` → `NEXT_PUBLIC_NETWORK_ID 179`, `NEXT_PUBLIC_NETWORK_RPC_URL https://interrpc.abeychain.com`, `NEXT_PUBLIC_API_HOST api.abeyscan.com`, `NEXT_PUBLIC_APP_HOST abeyscan.com`.
- `api.abeyscan.com/api/v2/stats` → 33M blocks 75M tx; `api.abeyscan.com/api/v2/search?q=0x0` → address hits. `stats.abeyscan.com` empty.

## Live RPC sweep (chainId before claim)
- `rpc.abeychain.com` 0xb3 179 Gabey/v3.4.8 ✅, `testrpc` 0xb2 178 v3.4.5, `interrpc` 0xb3, `rpc.bchscan.io` 0x17ac 6060 trap ❌ discard.
- Mainnet `rpc.abeychain.com` debug_* live: `debug_writeMemProfile/BlockProfile/MutexProfile/cpuProfile/goTrace` all `result:null` (file write), `debug_stacks` leak, `debug_memStats` heap, `debug_verbosity` null, `debug_dumpBlock latest` root/accounts dump — pre-auth. Same on testrpc. personal/admin gated: `personal_listAccounts` + `admin_nodeInfo` → method not found (-32601). So only debug HIGH, not admin.

## Delegation pattern for sisir semua side
- User: `kill dulu, sisir semua side, spawn 4 agent untuk saling audit, min 30 menit sebelum nyerah` → kill gabey 8855 (block 42/208), rm data/pwn, respawn deleg_3777665e 02:49, 4 agents: ARCHITECT trust graph, RED adversarial validate result:null, FUZZ fuzz_side*.py (path 27, numeric, RLP, batch 10k, CORS*, Host, duktape), CHAINER 5 cross-side chains wallet MITM→RPC hijack. Write /tmp/abey_side_report/{architect,fuzz,chain}.md, keep /tmp/abey for agents. ETA query: wc -l task-*.log + ps aux + ls /tmp/abey_side_report.
- `sambil nunggu hunt web2 https://abey.com/` → parallel Mozilla/5.0 single-req, dig subs, JS bundle grep https://, envs.js.
- `masih lama kah?` → answer `wc -l 111/72/97/61` + ps + disk df-h + side_report ls.
- Disk: `bersiihin disk, dont hapus .hermes` → keep /root/.hermes 1.4G + /tmp/abey 269M + /tmp/go-abey 18M + /root/go/pkg/mod 2.5G, rm /tmp/*.zip selective (aelf, chain33, safe*, bridge etc) 32 files, journal 42M, 96%→91% 2.0G free.

## Pitfalls
- Don't 403-count wp-json 429 as vuln; WordPress.com managed is low-decoy vs app-api real.
- Don't parallel-curl flood abey.com wp-json (429-lb). Use -L slow + Mozilla UA single req.
- Always verify app-api 401 vs 404 before claiming open.
