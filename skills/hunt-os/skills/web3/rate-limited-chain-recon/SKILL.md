---
name: rate-limited-chain-recon
description: "rate-limited chain reconnaissance"
version: "1.0"
category: security
tags: [onchain, recon, rate-limit, throttling, defi, vault, gnosis-safe, sonic, ft, decompilation, fuzz, cdc]
author: SUPERAGENT
trigger: ["nyantai", "brutal", "rate limit", "throttle", "sonic", "holder", "vault", "keeper", "safe", "decompile", "genesis scan"]
---

# Rate-Limited Chain Recon — Class-Level Skill

## Philosophy
Brutal but nyantai: exhaustive coverage without triggering 429/timeout. Every RPC chain has a throttle sweet spot — find it and hold it for hours. This skill encodes the Sonic FT campaign (2026-08) that mapped 98% of supply despite aggressive Sonic RPC limits.

## Core Pattern: Nyantai Brutal Throttle

| RPC | Safe Window | Throttle | Strategy |
|-----|-------------|----------|----------|
| `eth_getLogs` (Sonic `rpc.soniclabs.com`) | **100k blocks** | **0.9s** per call | Sequential, no parallel. >200k → timeout. Save checkpoint every 15 chunks. |
| `eth_getLogs` (BSC `bsc-dataseed.binance.org` / `bsc-dataseed1`) | **<100 blocks still 429** | **0.75-0.9s** but hard-capped | Even 100-block window → `limit exceeded`. 500/200/100 all fail. Fallback: scan via address-supplied logs or abandon (Naoris 2026-08: governance logs impossible on public RPC). |
| `eth_getLogs` (BSC `bsc-rpc.publicnode.com`) | **requires `address` param** | **0.75s** | `Please specify an address in your request`. Without address → 32701 error. With address but no indexed contract → empty. |
| `eth_getLogs` (BSC `bsc.meowrpc.com`) | **unsupported** | — | `The method eth_getLogs is not supported.` — skip this RPC for logs. |
| `eth_getLogs` (BSC `rpc-bsc.48.club`) | **5000 blocks max** | **0.6-1.2s** | `exceed maximum block range: 5000` — 100k requested → real 5000; archive early blocks `header not found`; throttle + checkpoint; full 115M = 23000 chunks (~6h) impossible on free tier — use recent 200k window sample (Agent 2 2026-08-12: 86 holders 14.9M vs 88.7M total). |
| `eth_getLogs` (BSC `bsc.drpc.org`) | **10000→5000 max** | **0.6-1.2s** | Free 10000 then 5000, plus archive pruned before ~114688716 (`no upstreams`);`You reached Public endpoint rate limit` on burst. |
| `Etherscan V2` `chainid=56 tokentx` | **blocked free** | — | `Free API access is not supported for this chain. Please upgrade your plan.` + V1 `deprecated, switch to V2` + bscscan 403 — use `eth_getLogs` pagination instead, document UNKNOWN if no paid key. |
| `eth_getStorageAt` EIP1967 BSC public | **returns 0x0** | — | Both `0x360894…b` (impl) & `0xb53127…03` (admin) return `0x000…000` on all public RPCs despite proxy delegating (`totalSupply` succeeds, prefix `7f360894…` in 342b proxy code) — pruned/incorrect node view. Don't trust zero; verify via `eth_call` success + code prefix. |
| `eth_getCode` historical BSC public | **archive pruned** | — | `eth_getCode` at historical blocks returns `0x`; `header not found` for <~1M recent. Binary search for creation block fails — need paid archive (Alchemy/QuickNode). **Workaround:** If contract is deployed on Ethereum with same address, query `eth_getCode` on Ethereum archive nodes (`eth.drpc.org`, `rpc.ankr.com/eth`) for deployment binary search. Cross-chain verification works when both chains share the same proxy address. Naoris case: BSC deployment block UNKNOWN, but Ethereum deployment pinpointed to block 23,000,000–23,100,000. |
| `eth_getLogs` (0G `evmrpc.0g.ai` chainId 16661) | **100k blocks** | **0.6-0.7s** + `User-Agent: Mozilla/5.0` | `curl` 403 → `python urllib.request` fallback; `eth_getStorageAt` EIP-1967 `0x360894…b` → impl `7A5e…`; `curl -I` static export `etag 6a58f7c9` + `nextExport:true` → no SSR RCE surface. |
| `eth_call` / `eth_getCode` / `eth_getStorageAt` | 1 call | **0.6-0.7s** per call | Never burst; 4byte lookup 0.6s. Batch verify via `cast disassemble` offline. |
| `Solana RPC` `getAccountInfo`/`getProgramAccounts` (`api.devnet/mainnet.solana.com`) | 1 call | **0.6-1.0s** + `jsonParsed` for BPFLoaderUpgradeable Program→ProgramData, `base64` decode ProgramData `[4:12]` slot + `[12]=option` + `[13:45]` authority → b58; `curl` hardline-blocked → `python urllib.request` fallback with same throttle | Sequential; user-supplied `bump: u8` must never be trusted — validate via `ctx.bumps` (see `375ai-bump-dos-2026-08-12.md`). |
| Holder `balanceOf` scan | 1 address | **0.7s** | Probe sequentially, checkpoint every 15-20, resume from `bal_merged.json`. |

**Key insight:** FT deployed at ~0x4800000 (75M), not genesis. 0-4.8M scan returns 0 logs — skip to deployment zone. Latest 77M → chunk 0x4800000-0x49b0af1 holds all activity. Coverage 1.94M/1.98M = 98% with 164 unique holders (111→164 after expanding 1.6M window).

## Workflow (6h Minimum Persistence)

User directive: *"kalau lo gabisa nemuin usaha dulu gapapa, sampai nyerah, min nyerah 6 jam."* — never surrender before 6h. Mark theory BLOCKED after 2 rounds of no evidence, pivot (T1→T2→T3), don't force.

1. **Genesis scan** 0→latest in 100k chunks, 0.9s, merge holders, skip already-scanned windows.
2. **Holder probe** `balanceOf` per holder 0.7s, sort by bal, identify pools/vaults/whales.
3. **Decompile** `cast disassemble` + PUSH4 `0x63` scan when `4byte.directory` returns unknown. Map `SLOAD 0x0 == CALLER` = onlyOwner, `keccak(CALLER.0x03)` = AccessControl hasRole.
4. **Safe chain trace** `getOwners()/getThreshold()/nonce()/masterCopy()/eth_getCode` — detect proxy vs impl, 172b forwarder (`273fff...845af43d`), threshold 3/5 already-setup → setup() hijack BLOCKED.
5. **Keeper/gated DoS** `keepers(address)` + `setKeeper` simulation from Safe vs DeaD → decode `0x3d515569` (NotKeeper) + `0x5501aad8`, `0x118cdaa7` (AccessControlUnauthorizedAccount).
6. **Fuzz** `previewDeposit(0,1,1e6,1e18,1e21)`, `convertToShares`, `maxDeposit`, `paused`, epoch daily — detect `PM-01` rounding (1 wei inflation if emptied) vs bricked `totalAssets` revert.

## Decompilation & Error Decoding

- When disassembler unavailable, PUSH4 extraction: scan hex for `63` + 8 chars = selector. Found 43 vault / 111 silo selectors at t3tris, 69 at d1e5_impl, 32 at Safe.
- Custom errors back-to-back `PUSH32 0x3d515569 + MSTORE + REVERT` — read preamble via `cast disassemble` 25 lines before error for access-control check.
- Gnosis Safe fingerprint: 32 sels (`addOwnerWithThreshold`, `execTransaction`, `getOwners`), `threshold` slot4, `masterCopy` empty = impl.

## Reporting Style (User Preference)

The operator requires **"jelasin santai"** — Indonesian informal `lo/gue`, sopan, never crossing line. Format: **table + bullet points**, not formal report. Token-efficient by default, longer detail when correctness demands. After brutal recon, summarize with holder table, vault status (HEALTHY/BRICKED), and blackswan impact in that style.
When user says **"aku bingung cok, coba jelasin satu satu santai"** → switch to **one-by-one numbered sections** (1. FT apa, 2. Pool apa, 3. Vault table, 4. Kenapa bricked chain, 5. Kenapa setup gagal, 6. Stablecoin) — no formal triage, keep santai tone. After **"atur aja terserah kamu. aku terima hasil"** → run **autonomous 6h campaign** with 20-30min throttled updates, no spam, checkpoint each 15 calls.

## Sequential Brutal Rule (User Workflow Correction)

User explicitly corrected: **"coba 1 dulu deh, baru 2"**, **"oke lanjut, nyantai aja, biar gausah request API kecepetan, tapi tetep brutal carinya"**, **"decompile dulu"**, **"probe dulu aja"**, **"coba kita setup, wkwkwk"**.
- Never burst parallel `eth_getLogs`/`eth_call`. Run **sequential 1-by-1** with 0.6-1.2s sleep, 100k-block chunks, checkpoint every 15.
- **"coba 1 dulu deh, baru 2"** = finish phase 1 (decompile/probe) fully before starting phase 2 (brutal holder scan). Don't interleave.
- **"nyantai brutal"** = throttle is the weapon — 0.9s `eth_getLogs`, 0.7s `balanceOf`, 0.6s 4byte. Faster = timeout/429 = false negative.
- When user says **"ganti target aja"** or **"apa yang masih rentan? kriterianya bagaimana?"** → pivot immediately using **Target Worth Matrix** below; don't defend stale target.

## Target Worth Matrix

(The Sonic-FT vs SaaS pivot-debate comparison matrix from the 2026-08-09 campaign — preserved at examples/hunts/web3/rate-limited-chain-recon/sonic-ft-target-worth-matrix.md.)

## LSaaS StakePool Red-Team Pattern

(Gimo 0G 2026-08-12 per-target walkthrough — live view sweep, offline decompile, rate-inflation sim, era/relay/upgrade leads, reentrancy harness with Gimo selectors — preserved at examples/hunts/web3/rate-limited-chain-recon/gimo-lsaas-stakepool-redteam.md.)

## Pitfalls

- Burst RPC → timeout/429 → false negative "no holders". Fix: throttle 0.6-1.2s, 100k chunks.
- Trusting explorer impl — Blockscout lie (`0x00ac46` vs factory slot `0x7aea44`). Always verify via `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`.
- `setup()` looks permissionless but proxy already 3/5 nonce 18 → already owned. Check `getOwners` before hijack attempt.
- `eth_call` data double `0x` → `cannot unmarshal invalid hex string`. Fix: `sel()` already `0x`, don't prepend again.
- 0G `evmrpc.0g.ai` `eth_getLogs` 429/timeout on genesis 0→latest + `curl` 403 (need `python urllib.request` fallback); EIP-1967 `eth_getStorageAt` may return 0x0 on pruned public nodes — verify via code prefix `7f360894` + successful `cast call` instead.
- StakePool `rateChangeLimit==0` is not "no limit set" but exploitable bypass — always flag `0` as HIGH (relay→arbitrary Cr). Don't dismiss `totalProtocolFee` 143k A0G as benign — cross-check vs `SELFBALANCE`.
- UUPS `upgradeTo` from attacker reverts `0x2af07d20` ≠ safe long-term — also probe `upgradeToAndCall` (`0x4f1ef286`) which at Gimo reverted empty not `0x2af07d20` (potential missing `onlyOwner`).

## References

- Case evidence from the Sonic-FT, Naoris (BSC/CCIP/architect/A2), Gimo, and BSC rate-limit sessions (6 files) is preserved at `examples/hunts/web3/rate-limited-chain-recon/references/` — moved out of the product layer 2026-09-07; body sections above cite the individual files.

## Governance Re-Read Signal

(Naoris governance 2026-08-11 second-pass findings — dead delegator sets, reentrancy via IStaking view CALL, ghost weights, weight desync — preserved at examples/hunts/web3/rate-limited-chain-recon/naoris-governance-re-read.md. Reusable rule: on a requested re-read, focus on dead code and trust assumptions — global vs proposal-level delegation sets, reentrancy on view CALLs inside voting loops, and singleton cleanup booleans.)
