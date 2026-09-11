# Naoris Protocol — BSC CCIP Bridge + Governance Recon (2026-08-11, 6h Throttled)

**Targets:** `Naoris-Protocol/naoris-token` (Naoris.sol 166L + Governance.sol 675L), `bridge.naorisprotocol.network` (Vite SPA + nginx `/api`), BSC proxies `0x1b379A79c91a540b2bcd612b4d713f31De1b80cc` (token) / `0x710836f5a0C2b30ed6D8D2e593574fB589BD0901` (CCIP bridge), NaoX L1 staking (not on BSC).

## Throttle Recipe That Worked
- `eth_call`/`eth_getCode`/`eth_getStorageAt` on `bsc-dataseed.binance.org` + `bsc-dataseed1` + `bsc-rpc.publicnode.com` → **0.65-0.85s per call**, sequential, never burst. 4byte lookup `api.openchain.xyz` → 0.35s.
- `eth_getLogs` on BSC public RPCs → **HARD FAIL even at 100 blocks**: `bsc-dataseed` → `limit exceeded` at 500/200/100 blocks; `publicnode` → `Please specify an address` (32701); `meowrpc` → `method not supported`. Lesson: don't brute-force governance logs on BSC without paid/archival node.
- Checkpoint before fuzz: `/tmp/fuzz/checkpoint-6h.json` + throttle 0.6-1.2s + promise 6h persistence (user: "gas 1, terus 2, audit 6 jam gapapa").

## Proxy Decode
- EIP-1967 slot `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` via `eth_getStorageAt` → token impl `0xc4e16e56ea3660110924cc06850120672b7e11ef` (38298b), bridge impl `0x8e54c114e95df4067a84b68462b7e3a726fb58d6` (22438b).
- PUSH4 scan (`63` + 8 hex) when disassembler missing → 100 selectors bridge, 43+ token. Decode via OpenChain `signature-database/v1/lookup?function=0x...`.
- Key selectors: `ccipReceive 0x85572ffb`, `bridgeToEth 0x89697ca1`, `bridgeMint 0xf661e631`, `rescueToken 0xe5711e8b`, `upgradeToAndCall 0x4f1ef286`, `quoteFee 0x2d623278`.

## On-Chain Reads (throttled)
- `paused() 0x00` both token+bridge (live), `maxBridgePerTx 12M`, `maxBridgePerWindow 100M`, `bridgeWindow 86400`, `bridgedInCurrentWindow 63740`, `totalInbound 1.59M` / `totalOutbound 32.99M`, `quoteFee 0.002765 BNB` fixed (0→max_uint256 same), `router 0x34b03cb9086d7d758ac55af71584f81a598759fe`, `ethBridge 0x49FD...`, `destGasLimit 300k`.
- Token: `Naoris Protocol / NAORIS / 18`, `totalSupply 88,596,513` (88M < cap 4B), `paused false`, impl slot verified.

## SIWE Auth Hardness (Web2)
- `encode_defunct(text=message)` + **EIP-55 checksum mandatory**: lowercase → 401 Invalid signature, checksum → 200 `{token}` HS256 `{id,address,role:"user",iat,exp:24h}`. Nonce 16 hex single-use (replay same sig → 401). JWT tamper `role:"admin"` → 401 HMAC. 29 `build-tx` fuzz vectors all 400 (`Valid 0x`, `Missing params`, `Unsupported chain`, `Insufficient balance` / `AmountZero`), zero 500/SSRF. Rate `100/900s` auth, `500/900s` bridge.

## Governance Bugs (PROVEN, no pre-auth RCE)
- `315 > maxDelegatorsLimit` should `>=` → allows 6/5 (20% weight inflation).
- `~262 hasVoted[proposalId-1]` phantom for id=1 (slot 0).
- `hasVoted=true` before `totalWeight>0` → 0-weight lock (`DelegatorCannotVote`).
- `cancelledProposalDataRemoved[proposalId]` singleton bool → only 1 voter clean.
- `stakingContract` immutable address but **logic can be upgradeable** → external `getUserTotalGovernanceWeight` at 212/232 (castVote loop) → weight manipulation + reentrancy surface. Staking source not in GH (`src/` only 2 files), not on BSC — likely NaoX L1.
- UUPS `Naoris.sol:32 _authorizeUpgrade onlyRole(DEFAULT_ADMIN_ROLE)` + mint 4B → single ADMIN = post-auth RCE.

## Workflow Correction Learned
- User: "gas 1, terus 2, audit 6 jam gapapa" → **sequential phase 1 (staking hunt) fully then phase 2 (bridge decompile + token audit)**, not parallel. Save checkpoint before fuzz, throttle brutal but nyantai, mark theory BLOCKED after 2 rounds (Teori C Web2 inject → BLOCKED).

## Files
`/tmp/fuzz/checkpoint-6h.json`, `bridge-audit.json`, `token-audit.json`, `gov-impact.json`, `staking-hunt.json`, `FINAL-CDC-REPORT.md`, hex dumps.
