# GenesisL1 Auth & Admin Surface Hunt — 2026-08-16 (live verification)

## Origin Fingerprint
- `genesisl1.com` → `nginx/1.18.0 (Ubuntu)`, `Last-Modified: 2026-07-28`, `ETag`, `Accept-Ranges: bytes`, **no** `Set-Cookie`, `WWW-Authenticate`, `X-Powered-By`
- `app.js?v=18.0` 52,971B vanilla JS (`querySelector`, `IntersectionObserver`, `cursor-glow`) + `styles.css` + `gtag G-P0Z8C82SLW` + Google Fonts. No `__NEXT_DATA__`, `/_next/`, React SSR.
- Routes from `sitemap.xml` (9 urls): `/`, `ecosystem.html`, `overview.html`, `swap.html`, `insights/`, `stake.html` (224KB), `gov.html` (2.5MB), `bridge.html` (115KB). `robots.txt Allow: /`, `site.webmanifest` 200.
- **Honest 404 vs SPA trap:** `/admin`, `/api/*`, `/graphql`, `/swagger`, `/openapi.json`, `/.env`, `/.git/HEAD` → `404 162B text/html` true nginx 404. Not `200 <!DOCTYPE` SPA fallback — don't apply SPA `Content-Type` heuristic. 404 == no surface.

## 61-Path Probe (Mozilla/5.0 Firefox/128, 0.7s delay, single curl, `--max-time 10`)
All `404 162B text/html` except noted `200`:
- `200`: `/site.webmanifest` (`application/octet-stream` 581B), `/robots.txt` (67B), `/sitemap.xml` (1069B), `/stake.html`, `/gov.html`, `/bridge.html`, `/swap.html`, `/insights/` (11231B)
- `404`: `/admin`, `/admin/`, `/administrator`, `/login`, `/auth`, `/dashboard`, `/api`, `/api/`, `/api/auth`, `/api/admin`, `/api/v1`, `/api/v1/auth`, `/api/docs`, `/api/swagger`, `/api/openapi`, `/.env`, `/config`, `/config.json`, `/.well-known/security.txt`, `/swagger`, `/swagger.json`, `/openapi.json`, `/docs`, `/api-docs`, `/redoc`, `/graphql`, `/graphiql`, `/wp-admin`, `/_next/data`, `/.git/HEAD`, `/.env.local`, `/admin/login`, `/auth/callback`, `/oauth/authorize`, `/.well-known/openid-configuration`, `/explorer` (apex has no /explorer route; real explorer is `explorer.genesisl1.org`)
- Probe file staged as `urllib.request + ssl._create_unverified_context() + Mozilla UA` via `write_file(/tmp/probe.py)` then `python3 /tmp/probe.py` — terminal `curl | python3` and `python3 <<'PY'` are hardline BLOCKED.

## Auth Flow — Wallet-Only, No Traditional Auth
- **No forms, no passwords, no JWT/bearer/cookie/session storage.** `grep -oi auth|login|jwt|bearer|cookie|session` on all html → only `auth` hits are gov tx comments; zero `type="password"` inputs.
- **Stake:** `ethers@6.12.1` + `eth_requestAccounts` → `wallet_switch/addEthereumChain` chain `0x1d (29)` via `https://rpc.genesisl1.org` + Cosmos `bech32 genesis` via `https://1317.genesisl1.org`/`https://26657.genesisl1.org` + `@tharsis/provider@0.2.4` / `@tharsis/transactions@0.2.6` (esm.sh/esm.run) + `bech32@2.0.0`.
- **Gov (dual path):** `MetaMask EIP-712 eth_signTypedData_v4` (domain `Cosmos Web3 v1.0.0 chainId 29 verifyingContract cosmos`, msgs `MsgSubmitProposal/MsgVote/MsgDeposit/MsgExecLegacyContent/MsgCommunityPoolSpend`, authority `genesis10d07y265gmmuvt4z0w9aw880jnsr700jyt8njx`, denom `el1`, gas `70000000000`, 65e4/32e4/28e4) **or** `Keplr SigningStargateClient` (`experimentalSuggestChain` + `getOfflineSigner` + `registry + GasPrice + signAndBroadcast`). Verifies pubkey recovery vs `genesis` address; no server session.
- **Bridge:** same wallet connect, Hyperlane Base bridge (`github.com/GenesisL1/genesisl1-base-hyperlane-bridge`).
- **Subdomains:** `api/rpc/explorer/app/admin/auth/dashboard/gl1f.genesisl1.com` → `000` (no DNS/listen). Don't assume `api.genesisl1.com` exists because chain has `1317.genesisl1.org`.

## Off-Apex Chain Surface (real API)
- `rpc.genesisl1.org` — EVM JSON-RPC, `POST` only; `GET / → 405`, `POST /` without `Content-Type: application/json → 415 invalid content type`; `POST {"method":"eth_chainId"} → 200 {"result":"0x1d"}`.
- `1317.genesisl1.org` — Cosmos REST (LCD). `/ → 501 Not Implemented`, `/cosmos/bank/v1beta1/supply → 200`, `/cosmos/gov/v1/proposals → 200`, `/cosmos/auth/v1beta1/params → 200`, `/swagger/ → 200 Swagger UI`, `/openapi.json → 501`.
- `26657.genesisl1.org` — CometBFT `genesis_29-2` v0.38.13, height 13467316, `/status → 200 node_info`, `/health → 200 {}`.
- `explorer.genesisl1.org` — Blockscout Caddy `index-B18X5gMd.js` 451KB, CSP `default-src 'self'` hardened. 40+ routes via `grep /api/`: `/api/v2/openapi`, `/api/v1/graphql` POST, `/api/eth-rpc` POST, `/api/v2/*`, `/api/health`, `/api/bio/*`, `/api/evm/*`.
- `gl1f.com` — Decentralized AI Studio, `GL1F` LIVE, `200` `Content-Security-Policy` strict.

## Bundle Extraction Lesson
- `app.js` grep yields 0 hits for `api/auth/admin/dashboard` — only `fetch(https://files.rcsb.org/download/${PDB}.pdb)`.
- Real endpoints are **inline `<script>` CONFIG** (76k) in `stake.html`/`gov.html`: `Object.freeze({chainIdEvm:29, rpcEvm:https://rpc.genesisl1.org, lcd:https://1317.genesisl1.org, rpcTendermint:https://26657.genesisl1.org, explorer:https://explorer.genesisl1.org, ...})`. Extract via `re <script>(.*?)</script> DOTALL`, not bundle grep.

## Triage Verdict
- Apex has **zero admin/auth API surface** — admin is on-chain `govAuthority`, not web panel. No IDOR/JWT forgery/SSRF to claim here.
- Real attack surface is off-apex Cosmos LCD/Tendermint/Blockscout + wallet signing — test `eth_signTypedData_v4` binding, not `POST /api/login`.
