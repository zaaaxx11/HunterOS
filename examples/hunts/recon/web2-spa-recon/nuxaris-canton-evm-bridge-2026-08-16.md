# Nuxaris Canton↔EVM Bridge — CRA Vercel + Dual-API + Sourcemap (2026-08-16)

## Target
- `https://app.nuxaris.com` — "Nuxaris - Bridge Canton Network to EVM — private, compliant, seamless" / "Privacy-First Crypto Swap"
- `https://www.nuxaris.com` — separate Vercel Next.js marketing site (60767B, `x-matched-path: /`, `vary: RSC`)
- Backend IP `37.27.59.179` (Hetzner) shared by `auth.nuxarisapiv1.xyz` + `nuxarisapiv1.xyz` (Caddy)

## Stack Fingerprint
- Create-React-App Webpack (`react-scripts`), not Next/Nuxt. Shell `1605B` `<!doctype html><div id=root><script defer src=/static/js/main.040e5d2d.js>` + `main.c6dd1741.css`.
- Infra: `server: Vercel` + `x-vercel-cache: HIT/MISS` + `x-vercel-id: sin1::…` + `cache-control: public, max-age=0, must-revalidate` + `etag` + `strict-transport-security: max-age=63072000`. DNS CNAME `dd8fdb48588832af.vercel-dns-017.com. → 216.198.79.1/64.29.17.1`.
- TLS Let's Encrypt YR1 `CN=app.nuxaris.com` `2026-07-27→2026-10-25`.
- Frontend security headers: **none** (no CSP, no X-Frame, `access-control-allow-origin: *` on static). Backend Caddy has full helmet.
- Libs from sourcemap 731 sources: `viem/wagmi/RainbowKit`, `@solana/wallet-adapter-react`, `@noble/hashes/curves/ed25519`, `@scure/bip39 SLIP-0010`, `borsh/bn.js/qrcode`.

## Entry Points (authoritative: /asset-manifest.json)
```
GET /asset-manifest.json → {files: {main.js, main.css, 150× static/js/*.chunk.js, 3× static/media, *.map}}
GET /static/js/main.040e5d2d.js (1.78 MB, .LICENSE.txt 7402B, .map 6.89 MB)
GET /static/css/main.c6dd1741.css (RainbowKit + fonts.googleapis Space Grotesk/Outfit/DM Sans/Inter Tight)
GET /static/js/main.040e5d2d.js.map → sourcesContent full leak
Images: /logo.webp, /logoeth.webp, /Canton-mainnet.webp, /ETH-BASE.webp, /ETH-ARBITRUM.webp, /USDC-ETH.webp, /USDT-ETH.webp, /AVAX-AVAXC.webp, /sollogo.webp, /HYPE-HYPEEVM-necku9.webp, /metamask.svg, /phantom.svg, /logoeth.webp
No /_next/, no __NEXT_DATA__ — CRA signal.
Vercel env in bundle: PRJ prj_VQibMGHLSmyiOiPOC7xeAKsDJDCu, repo Clickpaw/nuxaris, branch main, deploy nuxaris-91rna9dx7-clickpaws-projects.vercel.app, production app.nuxaris.com, commit c76172d2.
```

## Dual-API Topology (discovery: grep REACT_APP_AUTH_API_URL + BRIDGE_API + authFetch/apiFetch in main.js)
- Auth API: `https://auth.nuxarisapiv1.xyz` (`REACT_APP_AUTH_API_URL || https://auth.nuxarisapiv1.xyz`, `GET /health → {"status":"ok","service":"api-accounts"}`) — Caddy helmet `CSP default-src 'self'`, `X-Frame SAMEORIGIN`, `COOP same-origin`, `HSTS includeSubDomains`.
- Bridge API: `https://nuxarisapiv1.xyz/api/bridge` (`const API_BASE/BRIDGE_API = https://nuxarisapiv1.xyz/api/bridge`) — health `/health` 404.
- CORS: both `OPTIONS 204` with `allow-origin: https://app.nuxaris.com` + `allow-credentials: true` + `allow-methods: GET,HEAD,PUT,PATCH,POST,DELETE` — strict allowlist. Frontend `*` is static-asset only.
- Code wrappers: `config/api.ts authFetch(path)` `path.startsWith('http')?path:AUTH_API_URL+path` + Bearer + 401→ `POST /api/auth/refresh {refresh_token}` retry once; `services/api.ts apiFetch` same against `API_BASE`.
- Third-party direct: `api.etherscan.io/api`, `api.basescan.org/api`, `api.mainnet-beta.solana.com`, `mainnet.helius-rpc.com`, `mainnet.base.org`, `eth.merkle.io`, `fonts.googleapis.com`, `nuxaris.notion.site` incentive docs.

## Endpoints (from sourcemap services/api.ts + services/wallet-api.ts + config/api.ts)
- Auth `auth.nuxarisapiv1.xyz/api/auth/*`: `POST account-state {email}→{step}`, `challenge {email}→{nonce,expiresAt}`, `login-key {email,nonce,signature}`, `login {email,password}`, `register {username,email,invite_code}`, `verify-email {email,token}`, `resend-verification {email} 429`, `refresh {refresh_token}`, `GET me` Bearer; `wallet/provisioning|init {publicKeyHex}|topology-submit {signatures}|preapproval/prepare|preapproval/execute`.
- Bridge `nuxarisapiv1.xyz/api/bridge/*`: `GET tokens (200 unauth 4: ETH.ethereum/CC.canton/ETH.base/SOL.solana)`, `routes (200 unauth)`, `quote?tokenA=&tokenB=&amount=`, `POST order/erc20 {tokenA,tokenB,amount,destinationAddress}`, `order/canton {tokenA,tokenB,amount,userPartyId,destinationAddress}`, `GET order/:id`, `POST order/canton/:id/prepare→{requestId,hashB64,expiresAt 30s}`, `execute {requestId,signature}`, `GET transfer-factory?senderPartyId=`, `POST wallet/send/prepare→execute`, `GET wallet/status {partyId,preapproval}`, `account/status {banned}`, `wallet/balance {balanceCC}`, `wallet/addresses?chain=`, `price/CC`, `premium/status|subscribe/prepare|execute`, `rewards/quests|points|pot`, `GET orders?page=&limit=100`, `premium/status`.
- Live probes: `GET tokens 200 {"tokens":[...]}`, `GET routes 200 {routes:[ETH.ethereum→CC.canton 30m, CC.canton→ETH.ethereum 5m...] limits minAmount/maxAmount}`, `GET quote?ETH.ethereum&CC.canton&amount=0.01 → QuoteResponse {fees:{bridgeFee,exchangeTradingFee,withdrawFee}}`, `GET orders 401 without Bearer`, `POST account-state {"email":"test@example.com"} → {"step":"unknown"}`.

## Auth & Vault
- JWT Bearer in `localStorage access_token/refresh_token`; no cookies. Silent refresh on 401 → `POST AUTH_URL/api/auth/refresh`; on fail `removeItem` both. Ratelimit Auth `10;w=60` (remaining 5→9), Bridge `60;w=60`.
- Key login namespace isolation (`wallet/signing.ts`): `nuxaris-login:<nonce>` UTF-8 text signed vs 32-byte base64 Canton hash refused if collision — prevents challenge→tx confusion.
- Fingerprint `hex(0x1220 || sha256(BE32(12) || pubkey32))`, partyId `nuxaris-user-<12uuid>::<fingerprint>`.
- Vault `vault-crypto.ts`: PBKDF2-SHA256 600k iter, AES-256-GCM salt 16 IV 12 tag 128, WebCrypto non-extractable, AAD `nuxaris-vault:v{version}:{accountId}`. IndexedDB `nuxaris-wallet/vaults` keyed `accountId`; `localStorage nuxaris_vault_accounts` email→UUID + `nuxaris_hide_values`/`nuxaris_balance_history`.

## Hardcoded Secrets
- `REACT_APP_SOLANA_RPC=https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY>` leaked in bundle `process.env` — billable abuse surface.
- `REACT_APP_WALLETCONNECT_PROJECT_ID=PLACEHOLDER`, `REACT_APP_VERCEL_*` all `||` fallbacks in bundle.

## Recon Recipes
```bash
curl -sk -A "Mozilla/5.0 Firefox/128.0" -D headers.txt https://app.nuxaris.com/ -o body.html
curl -sk -A "Mozilla/5.0 Firefox/128.0" https://app.nuxaris.com/asset-manifest.json | python3 -m json.tool
curl -sk -A "Mozilla/5.0 Firefox/128.0" https://app.nuxaris.com/static/js/main.040e5d2d.js -o main.js
curl -sk -A "Mozilla/5.0 Firefox/128.0" https://app.nuxaris.com/static/js/main.040e5d2d.js.map -o main.js.map
python3 -c "import json; m=json.load(open('main.js.map')); print([s for s in m['sources'] if 'src/' in s and 'node_modules' not in s])"
python3 -c "import re; js=open('main.js').read(); print(set(re.findall(r'https://[^\"]{10,120}', js)))" | grep nuxaris
curl -sk -A "Mozilla/5.0 Firefox/128.0" https://nuxarisapiv1.xyz/api/bridge/tokens | head -c 1000
curl -sk -A "Mozilla/5.0 Firefox/128.0" -X POST -H "Content-Type: application/json" -d '{"email":"test@example.com"}' https://auth.nuxarisapiv1.xyz/api/auth/account-state -i
```

## Pitfalls & Triage Notes
- Don't brute `/_next/static` — CRA has `/static/js` + `/asset-manifest.json`. Missing manifest → not CRA.
- Sourcemap always present when `.LICENSE.txt` 200 — check map before manual deobf.
- Unauth `tokens/routes` are intended public but enable targeted quote crafting — report as info disclosure LOW not HIGH.
- 401 on `/orders|/wallet/status` without Bearer is expected (not 🔥); 200 on tokens/routes is expected public.
- Auth `account-state` is user-enumeration oracle but 10/min ratelimit mitigates — LOW.
- Helius key exposure is HIGH (billing) even though read-only.
- No browser cookie table — trust graph is JWT localStorage + IndexedDB split, not cookie jar.
