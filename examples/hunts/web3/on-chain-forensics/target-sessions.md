# Target session write-ups (Gimo 0G / Camp / Sonic FlyingTulip) — cut from on-chain-forensics SKILL.md 2026-09-07

Cut verbatim from `soul/skills/web3/on-chain-forensics/SKILL.md` during the 2026-09-07 S2b-2 follow-up pass (per-target session material preserved, not deleted; the forensics method — Phase 0-3 workflows, selector extraction, squatter detection, proxy/bytecode analysis, multi-chain reality check — stays in the skill body). The case refs that moved with this skill live in `examples/hunts/web3/on-chain-forensics/references/`.

---

## Gimo Finance 0G LSD Trust Graph (2026-08-12 — Proxy 0xAc06 / Impl 0x7A5e / st0G 0x7bBC)

Class-level pattern for LSD / LSaaS UUPS + rate-oracle forensics on 0G (evmrpc.0g.ai, chainId 16661):

- **Packed owner & EIP-1967**: `eth_getStorageAt proxy 0x0` is `owner<<8|0x01` (`0x...3007306646AC90a647BebC9Acc029c941db5b0Fb0001`), not a clean address — decode `int(v,16)>>8 & 2**160-1`. EIP-1967 `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` → impl `0x7A5e1b999a665f2b89e5f6eAE32dF9471De193C7`. `0x015783e9` revert + `0x010000` mask + `CALLER/EQ` is the canonical `onlyOwner` gate (`fd852c1b @0xa78` dual-guard). Always verify `ec2` impl slot vs `eth_getCode` header.
- **Selector dispatch slicing without decompiler**: regex `8063([0-9a-fA-F]{8})14(61)([0-9a-fA-F]{4})57` brute-extracts 57 selectors from `/tmp/impl_full.hex`, sorted by jumpdest. Body slice via `hexdata[dest*2:nextDest*2]` (cap 600–2500 hex chars). Shallow trait scan flags privileged sinks: `600054` (SLOAD 0) + `33` CALLER, `600555` (SSTORE slot5 rate), `6340c10f19` (st0G mint), `0x015783e9` owner revert, `0xd6d9e665` (onlyOwner alt).
- **Storage semantics 0-20 dump**: 2→86400 eraSeconds, 3→20347 era, 4→329 validators, 5→1.3259e18 rate (`12668ba79fc56de3`), 8→1e16 fee, 9→1 paused, 12→3 epoch, 13→7080 commission, 16→st0G `0x7bBC…`, 17→1e17 minStake, 18→totalPooled `1e6ec8e7…`. Proxy SLOAD set `[0,1,2,3,4,5,6,8,12,13,16,17,18]` confirms toucher slots.
- **Privileged vs relay boundary via eth_call diff**: probe every selector with `from=owner 0x300730…` vs `anon 0x1111…` vs `relay 0x3241…`. Only `fd852c1b` (dual owner) and `3ccfd60b` (`0xd6d9e665`) diff; `3659cfe6 upgradeTo`/`4f1ef286 upgradeToAndCall` expose UUPS delegatecall guard. `46f45b8d stake(string)` payable referral ("galxe") mints `msg.value*1e18/rate`; rate aliases `679aefce getRate()`/`2c4e722e rate()` share slot5. Token slot5 = proxy sole minter, `owner()` reverts.
- **Relay/oracle log recon on rate-limited 0G**: `eth_getLogs` 100k-block chunks, 0.6–0.7s `urllib.request` (curl 403 on `evmrpc.0g.ai`). Relay `0x3241549486acc64999e6b3c02c794bd7bbc71d54` → `7b207727` emits `0x02105621 ExchangeRateUpdate` (`0x1265089e73f3cc3b` ~1.325e18) — last 200k blocks = 15 proxy logs, proving centralization. Verify via `eth_getTransactionReceipt` on `0x32b0…`/`0x7d4b…` (50 A0GI stake). Detail in `examples/hunts/web3/on-chain-forensics/references/gimo-0g-trust-graph-2026-08-12.md` (storage table, 57 dispatch map, decompiled `fd852c1b` snippet, trust graph ASCII, verification cmds).

## Blockscout as RPC Proxy (Dead RPC Workaround — Camp Network 2026-08)

When the target's primary RPC is NXDOMAIN/unreachable (e.g. `rpc.camp.raas.gelato.cloud`), the Blockscout explorer usually exposes a full JSON-RPC proxy at `/api/eth-rpc`. This is enough for read-only recon (`eth_chainId`, `eth_call`, `eth_getCode`, `eth_getBalance`, `eth_getStorageAt`).

```bash
# Pattern
curl -X POST "https://<explorer-host>/api/eth-rpc" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":"0x...","data":"0x8da5cb5b"},"latest"]}'

# Live: Camp Network mainnet (chain 484) — rpc.camp.raas.gelato.cloud NXDOMAIN,
# but camp.cloud.blockscout.com/api/eth-rpc answered eth_chainId → 0x1e4
```

Also: Blockscout `/api/v2/smart-contracts/{addr}` returns full verified `source_code` + `additional_sources[]` (all imports — libraries, interfaces) + `implementations[]` + `proxy_type` + `external_libraries`. **This is the closed-GitHub workaround for verified contracts.** For Camp IpNFT it leaked 38 files including `src/libraries/Verifier.sol`.

`/api/v2/addresses/{addr}` gives `creator_address_hash`, `creation_transaction_hash`, `implementations[]`, `proxy_type`, token metadata, and balance.

## Sonic Chain (FlyingTulip FT — OFT case 2026-08-08)
- **Chain ID**: 146, **RPC**: `https://rpc.soniclabs.com`, Endpoint `0x6F475642a6e85809B1c36Fa62763669b1b48DD5B`
- **FT**: `0x5DD1A7A369e8273371d2DBf9d83356057088082c` — CREATE2 same address on ETH/BSC/AVAX/Base (OFT mesh), 20004 bytes, `OFT→OFTCore→OAppReceiver`. `peers[30101]` ETH / `[30102]` BSC / `[30106]` AVAX / `[30184]` Base all map to same `0x5DD1...` peer (EIDs are LZ V2). Verify via `peers(uint32)` selector `0xbb0b6a53`.
- **Owner vs Configurator split**: `owner()` `0x8da5cb5b` → Safe `0x1118...70Cb`; `configurator()` `0x2b507df8` → EOA `0x2224...17c` (same as delegate). `paused()` `0x5c975abb`, `totalSupply()` `0x18160ddd` = 1.9M (not 10B initial mint).
- **Archive branch trap**: `flyingtulipdotcom/escrow` + `security` default is `master`, not `main` — `.../main.tar.gz` returns 404 ASCII `14 bytes`. Probe both branches + `file` check.
- **Throttled holder enumeration (Sonic RPC is rate-limited)**: `eth_getLogs` with `Transfer` topic `0xddf252ad...` must use 100k-block chunks and 0.7-1.2s delay; >400k window times out (60s). Recent 800k blocks → 111 holders, extended 1.6M blocks → 164 holders (+53), top `0xccac...0bd` holds 1.72M (87%). Balance probing uses `balanceOf(address)` per holder with 0.6-0.7s throttle, checkpoint every 10-15 entries to `/tmp/bal_*.json` (merge-friendly list `[addr, bal]`). Resume from `seen` set on timeout — never restart from zero. See `examples/hunts/web3/on-chain-forensics/references/flyingtulip-sonic-deepdive.md` + `examples/hunts/web3/on-chain-forensics/references/flyingtulip-vault-chain-5922.md` for full checkpoint workflow.
- **Vault vs Pool disambiguation**: `0xccac8b32a958b4a59833351c430423600bae66bd` (21,890 bytes) is NOT a vault — it's a Shadow DEX V3 pool (selectors `slot0`, `liquidity`, `mint`, `burn` + 4byte maps to UniswapV3Pool). `token0=USDC 0x29219dd4 (6dec)`, `token1=FT`, `fee=19736` (custom, not 500/3000), `tick 299428` → 10.07 FT/USDC vs reserve ratio 693 FT/USDC = 69x imbalance. True ERC4626 vaults are EIP-1167 clones: `0x7127bb9d...` (14k FT, impl `0x0515...1839` 20kb, bricked — `totalAssets` reverts, `asset=0x5922...8c` yield wrapper) and `0xd1e5...eb1` (43k FT, impl `0x5aee...0e841` 23kb, healthy 1:1 `previewDeposit`/`convertToShares`, `asset=0xf7d8...9c9c` USDC clone `0xf47b...e1885` with `masterMinter/blacklist`). Proxy impl via slot `0x3608...bbc`; EIP-1967 slot may be stale — extract DELEGATECALL PUSH20 from proxy bytecode instead. Vault 7127 chain: `7127 → 5922 (7.7kb yield wrapper, owner 0x333a proxy) → 333a (172b forwarder) → fb1b` (3-level proxy) explains bricked state. See `examples/hunts/web3/on-chain-forensics/references/flyingtulip-vault-chain-5922.md`.
- `examples/hunts/web3/on-chain-forensics/references/flyingtulip-sonic-deepdive.md` (this session: pool vs vault, throttled scan, tick math) + `references/flyingtulip-onchain-recon.md` (thin wrapper detection) in `adversarial-bug-bounty-hunting`.
- `examples/hunts/web3/on-chain-forensics/references/vault-fuzz-sonic-erc4626.md` — Sonic ERC4626 vault fuzz (d1e5 43k FT 1:1 preview, 7127 revert/CB-01, f7d8 blacklist, 1e15-1e21 preview matrix, throttled 0.6s).

## Vault Chain Three-Level Proxy + Safe Nesting (2026-08-09 — FlyingTulip 7127 case)
`0x7127 vault (14k FT, bricked) → 0x5922 yield wrapper (7,743 bytes, 24 selectors, owner = 0x333a) → 0x333a proxy (172 bytes forwarder) → 0xfb1b Safe masterCopy (23,801 bytes, 32 selectors)`. Detection:
- `0x7127` `asset()` slot1 = `0x5922`; `0x5922` `owner()` = `0x333a`; `0x333a` `eth_getStorageAt 0x0` = `0xfb1b`; `cast disassemble 0x5922` shows `AccessControl` preamble (`SLOAD 0x0 == CALLER` + `SLOAD 0x04 & 0xff` + `keccak(CALLER,0x03) SLOAD`).
- `0x333a` is **already a Safe Proxy**: `getOwners()` → 5 owners, `getThreshold()` = 3, `nonce()` = 18 — NOT the leaf. Leaf `0xfb1b` is masterCopy with `threshold 1, nonce 0, getOwners() unsuccessful` (by design, impl never `setup()`). Confusing proxy vs leaf causes false `setup()` hijack hypothesis — always `getOwners()` on the **proxy address**, not the `eth_getStorageAt 0x3608` impl.
- Nested Safe: owner1 of `0x333a` is itself a 172b proxy → `0x29fc Safe (24,422 bytes, getThreshold 1, getOwners unsuccessful)` — 2-level Safe nesting. Check recursively via `eth_getStorageAt(proxy, 0x0) → target → eth_getCode`.
- Bricked vault signal: `totalAssets()/convertToAssets()` revert with custom error `0x3d515569` (onlyOwner/onlyKeeper) while `totalSupply()` succeeds. Wrapper `claimYields` reverts with same `0x3d515569` → access control mismatch: vault not `keeper` (`keepers(address)` returns 0). Need `setKeeper(vault,true)` — private admin op, not exploitable.
