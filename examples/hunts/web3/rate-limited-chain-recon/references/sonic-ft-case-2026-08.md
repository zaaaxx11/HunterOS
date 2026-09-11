# Sonic FT 2026-08 — Holder & Vault Chain Case Study (Rate-Limited Brutal Recon)

**Chain:** Sonic FT `0x5DD1A7A369e8273371d2DBf9d83356057088082c`, supply 1.98M (not 10B), OFT mesh ETH/BSC/AVAX/Base same CREATE2, owner Safe `0x1118...70Cb`, configurator EOA `0x22246a9183ce2ce6e2c2a9973f94aea91435017c` (blackswan single key).

**Holders (164 unique, 98 with bal >0, 98% coverage throttled 0.7-0.9s):**
- `0xccac` pool 1,721,811 FT — Shadow DEX FT/USDC (`token0 0x2921 USDC 6dec`, `fee 19736`, `tick 299428`, 69x imbalance 2477 USDC vs 1.72M FT).
- `0xd1e5` vault 43,597 FT — ERC4626 (impl `0x5aee...0e841` 23kb, 69 sels), asset `0xf7d8` stablecoin 320k (6dec, `masterMinter/blacklist/pauser`), `totalAssets==totalSupply=261k`, epoch 247 daily, `paused=false` — HEALTHY.
- `0x7127` vault 14,004 FT — EIP-1167 clone of `0x0515` 20kb, slot1 `0x5922` yield wrapper 7.7kb 24 sels → owner `0x333a` 172b proxy → `fb1b` Safe 23.8kb masterCopy. BRICKED: `totalAssets/convert/claim` revert `0x3d515569`.

**Wrapper 0x5922 Access Control (cast disassemble):**
- `SLOAD 0x0 == CALLER`, `SLOAD 0x04 & 0xff`, `keccak(CALLER.0x03)` → AccessControl hasRole. Errors `0x3d515569` NotKeeper + `0x5501aad8` at 0x13a7/0x13cf, `0x118cdaa7` unauthorized.
- `keepers(333a)=true`, `keepers(7127)=false` → fix `setKeeper(7127,true)` from Safe 333a succeeds (eth_call 0x), from DeaD reverts. 7127 DoS is operational miss, not RCE.

**Safe Chain:**
- `0x333a` Safe 3-of-5 (owners `b7b5→29fc`, `3c42`, `09e2`, `d0ca`, `f9e5`), nonce 18, threshold 3 — setup() already used, hijack BLOCKED. Leaf `0xfb1b` is masterCopy (threshold 1, no owners, not the Safe). `0x29fc` Safe 24kb member 1 has threshold 1, nonce 0, getOwners unsuccessful (nested Safe).

**Technique:** 100k-block eth_getLogs 0.9s, eth_call 0.6-0.7s, checkpoint every 15, PUSH4 0x63 scan + 4byte.directory 0.6s + cast disassemble for error preamble, Gnosis Safe fingerprint 32 sels.

**Verdict:** No pre-auth RCE proven (LayerZero OnlyPeer/OnlyEndpoint solid). One DoS bricked (14k), one central stablecoin blacklist risk, one pool imbalance. CDC theories T1 paused bypass / T2 1271 reentrancy / T3 LZ forge all BLOCKED after 2 rounds.

**Files:** `/tmp/bal_merged_sorted.json`, `/tmp/5922.hex`, `/tmp/05158.hex`, `/tmp/fb1b.hex`, `/tmp/bedah_6h.sh`, cast dumps.
