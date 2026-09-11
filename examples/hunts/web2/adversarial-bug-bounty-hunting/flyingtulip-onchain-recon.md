# FlyingTulip On-Chain Recon — Thin Wrapper Case Study (2026-08-08)

Source: `flyingtulipdotcom` org — 4 repos: `ft`, `escrow`, `security`, `supporter-whitelist`

## Repo inventory
- `ft` (main): `contracts/FT.sol` (370 LOC, OFT+ERC20Permit+Pausable), `deploy/FT.ts`, `utils/constants.ts`, `test/hardhat/FT.test.ts` (827 LOC)
- `escrow` (master branch, not main): `src/Escrow.sol` (50 LOC), `test/Escrow.t.sol`, `foundry.toml` with empty `lib/` (submodules not fetched — archive strips git)
- `security` (master): `KNOWN_ISSUES.md` — lists private systems (PutManager, AaveStrategy, YieldClaimer, LeverageRfqEngine, CircuitBreaker, pFTMarketplace) = real TVL
- `supporter-whitelist`: CSV only

## CREATE2 multi-chain same address
```
sonic / ethereum / bsc / avalanche / base → 0x5DD1A7A369e8273371d2DBf9d83356057088082c
sonic-mainnet → 0x9B15Cce2D9C396B8B840C167374DCe873b2CcE6d (second deploy)
sepolia → 0xA92d5C6a9E73D0EA221Eb0B1fB8effE5E68ED064
```
Same CREATE2 factory — OFT mesh. Check: `cast code --rpc-url <chain>` identical bytecode length 20004 bytes on Sonic.

## Sonic mainnet live state (2026-08-08 via rpc.soniclabs.com)
```
owner:        0x1118e1c057211306a40A4d7006C040dbfE1370Cb  (Safe — FINAL_OWNER)
configurator: 0x22246a9183ce2ce6e2c2a9973f94aea91435017c  (EOA — STANDARD_FT_DELEGATE/CONFIGURATOR)
endpoint:     0x6F475642a6e85809B1c36Fa62763669b1b48DD5B  (LayerZero Sonic V2)
paused:       false
decimals:     18
totalSupply:  1,982,326 FT  (1.9M, not 10B initial mint — rest burned/bridged)
peers[30101]=ETH  → 0x5DD1... set
peers[30102]=BSC  → set
peers[30106]=AVAX → set
peers[30184]=Base → set
```
Supply calc: `hex 0x01a3c620dd65e7883c2000 / 1e18 = 1,982,326`

## Deploy script clone trap
Fetching via `github.com/.../archive/refs/heads/main.tar.gz` returns `404: Not Found` (ASCII `14 bytes`) for `escrow` and `security` — default branch is `master`. Always try both: `curl .../main.tar.gz || .../master.tar.gz && file` to detect.

## CDC theories on public code — all BLOCKED
- T1 Pause bypass: `_update` whitelists configurator as from/to/sender + endpoint, permit/approve work while paused. Needs victim allowance → not pre-auth.
- T2 ERC-1271 reentrancy: `isValidSignature` called BEFORE `_useNonce`, but outer `_useNonce != nonce` reverts atomic → no persistence.
- T3 LZ mint forgery: `OAppReceiver.lzReceive` guards `endpoint==msg.sender` + `peers[srcEid]==sender`, `OFTCore._credit → _mint` no cap. Needs endpoint compromise or owner `setPeer` key.

## Pivot signal
`AUDIT.md` 5 findings all Q/I (Medium/Info), `KNOWN_ISSUES.md` explicitly marks private systems out-of-scope. When public contracts < 400 LOC and inherit only OFT/Permit/Pausable with no strategy math → wrapper repo → pivot to on-chain forensics for private strategy addresses (docs.flyingtulip.com/contract-addresses) instead of forcing PoC.
