# FlyingTulip Vault Chain 0x5922 — 3-Level Proxy & Bricked Vault (2026-08-09)

EIP-1167 clone vault 0x7127bb9d (14k FT) bricks because its `asset()` delegates to yield wrapper 0x59222220759efe35b8e46f5563151827e4114628, whose owner is itself a proxy chain.

## Chain
`7127 (proxy, 77b) → 5922 (7,743b yield wrapper) → 333a1ad484b540ecac1edfa73a066ab57275293c (172b forwarder, slot0=fb1b) → fb1bffc9d739b8d520daf37df666da4c687191ea (leaf impl)`

- `7127` storage `slot1 = 0x5922...`, `slot3 = Safe 0x1118...70Cb`, `totalSupply == FT balance` but `totalAssets/convertToShares/previewDeposit` all revert with empty data (`-32000 execution reverted`).
- `5922` sels (24): `keepers/setKeeper`, `addWrapper/removeWrapper`, `claimYield/claimYields/claimAll`, `deploy/execute`, `ideal_warn_timed`, 10× unknown `0x18d01...` custom yield logic + `_SIMONdotBLACK` obfuscated. `owner() = 0x333a...`, `slot0 = 0x333a...`, `slot1 = 0x08`. All `deploy/addWrapper` revert with `0x118cdaa7` — wrapper not initialized / access-controlled.
- `333a` (172b: `608060405273...600054167fa619...845af43d...`) `slot0 = fb1b`, proxy forwarder to `fb1b` leaf (unprobed, likely uninitialized Safe — `getOwners` unsuccessful, `masterCopy` empty).
- Healthy counterpart `0xd1e5...eb1` (43k FT) same clone pattern but `asset = 0xf7d85ec4e7710f71992752eac2111312e73e9c9c` (USDC clone `0xf47b...e1885` 13kb, 49 sels: `masterMinter/minter/blacklist/blacklister/pauser/upgradeToAndCall`), `impl 0x5aee...0e841` 23kb 69 sels. `totalAssets==totalSupply==261417254558` (261k 6dec), `previewDeposit 1→1` up to 1e21 OK, `paused=false`, `epoch=247` daily (~Aug 07-08 2026), `epochSettler` clone `0xed00...226f → impl 0xa4f83b...103aa1` (6.5kb `keepers/allowedSwapTargets/setVault/recoverTokens`). `FT()=0x5DD1`, `ASSET()=f7d8`.

## Why 7127 bricks
`7127.totalAssets()` → `asset.totalAssets()` → `5922` reverts (owner chain requires `0x333a`→`fb1b` setup). Unlike `d1e5` whose `f7d8` asset is `paused=false` and responds, `5922` yield wrapper never initialized.

## Safe nesting trap + setup() hijack blocked (2026-08-09)
- `0x333a` is itself a **Gnosis Safe Proxy** (172b forwarder): `getOwners()` → 5 owners (`0xb7b5...408bc8` proxy→`0x29fc` 24kb Safe, `0x3c42`, `0x09e2`, `0xd0ca`, `0xf9e5`), `threshold 3`, `nonce 18` — already `setup()` done. Leaf `0xfb1bffc9...91ea` (23,801b, 32 selectors) is masterCopy (`threshold 1, nonce 0, getOwners unsuccessful`) — by design never setup. Checking `eth_getStorageAt 0x3608` alone misleads to leaf; always `getOwners()` on **proxy address**. `setup()` hijack fails when proxy `nonce !=0` or `getThreshold !=0`.
- Second nesting: owner1 `0xb7b5...` → 172b proxy → `0x29fc` Safe (24,422b, `getThreshold 1, getOwners unsuccessful, nonce 0`) — 2-level Safe nesting. Recurse via `eth_getStorageAt(proxy,0x0)`.
- **Lesson**: Safe hijack only viable if `getOwners()` reverts AND `getThreshold 0` on the **proxy**, not the masterCopy.

## Custom error 0x3d515569 brute force
- `0x5922` `claimYields/claimYield` revert `0x3d515569` then fallback `0x5501aad8` — both 40 bytes apart at byte offset 5032/5072 (`PUSH32 <selector> + PUSH0 MSTORE + PUSH1 0x04 REVERT`).
- `cast disassemble 0x5922 | grep -B25 3d515569` shows shared preamble: `SLOAD 0x0 & CALLER EQ` (onlyOwner) + `SLOAD 0x04 & 0xff` (role bitmap) + `keccak(CALLER,0x03) SLOAD ISZERO` (AccessControl `hasRole(keeper)`) → `JUMPI → PUSH32 0x3d515569 REVERT`. Second path `0x5501aad8` is fallback role branch; `0x4e487b71` nearby is `Panic(0x41/0x32)` bounds check.
- `keepers(vault)` = 0 → vault not `setKeeper(vault,true)`. Fix is private admin `setKeeper`. No 4byte hit → map to private `AccessControlUnauthorizedAccount` variant, not string error.
- Resolve: `cast disassemble <code> | grep -B25 "3d515569"` — unknown selector + AccessControl preamble = private role check.

## Pitfall
- Extract EIP-1167 impl from slot `0x360894a13ba...bbc` AND from proxy bytecode `PUSH20` before `DELEGATECALL (0xf4)` — slot may be stale. In this case slot held `0x5922`/`0x5aee` correctly, but chain below it used storage slot0 forwarding, not EIP-1967.
- Don't assume all EIP-1167 clones share same owner: `d1e5` owner = Safe `0x1118`, `7127→5922` owner = `0x333a` forwarder.

## Throttled probe recipe
`eth_getCode` + `eth_getStorageAt(slot1)` + `eth_call(owner/totalSupply/asset)` at 0.6s throttle; 4byte lookup for `8063` sels; `eth_call` on proxy not impl for `totalAssets` to surface revert reason. Checkpoint to `/tmp/bal_*.json`.

## Impact
7127 holds 14k FT locked (DoS via 3-level uninitialized proxy). Stablecoin `f7d8` can `blacklist(vault)` → freeze `d1e5` 261k assets instantly (centralized `wipeBlacklistedAddress`/`pause`).
