# GenesisL1 Forest + Hyperlane Bridge Hunt — 2026-08

Source: https://github.com/GenesisL1 (GitHub **USER** id 88520218, not ORG — `/orgs/GenesisL1` returns 404, use `/users/GenesisL1/repos`). 170 repos, 130 forks, 39 originals. Focus originals only.

## Org-Level Recon Nuances

**USER vs ORG:** `curl -s https://api.github.com/orgs/GenesisL1/repos` → `{"message":"Not Found"}`. Fallback: `GET /users/GenesisL1/repos?per_page=100&page=N` (paginated, 100+70+0). Detect type: `type: User` in response. Same for raw: `codeload.github.com/GenesisL1/<repo>/tar.gz/refs/heads/main` works for user too.

**Fork filtering:** `jq -s 'add | map(select(.fork==false))'` → 39 originals. Prioritize: `Forest`, `api-registry`, `NFTMarketplace`, `genesisl1-base-hyperlane-bridge`, `MoleculeNFT`, `genesis-crypto`, `genesis-ethermint`, `genesis-parameters`. 130 forks are CometBFT/ethermint/blockscout noise — skip unless hunting L1 binary diff.

**Git broken on TencentOS 4 / hardened images:** `git clone https://...` → `git: 'remote-https' is not a git command. See 'git --help'.` + `dnf install git` → `No match for argument: git` (no git package in TencentOS Core repo). **Immediate fallback:** `curl -skL -o /tmp/<repo>.tgz "https://codeload.github.com/GenesisL1/<repo>/tar.gz/refs/heads/main" && tar xzf`. Try `main` then `master`/`genesis-v0.5.0` — some repos (genesis-ethermint) only on `genesis-v0.5.0` tag. No `git-core` package exists — don't debug, tarball.

## Primary Attack Surfaces (4 mainnet contracts)

### 1. Forest (GenesisL1 Forest / GL1F) — Highest Value

**Files:** `Forest-main/contracts/ForestRuntime.sol` (1080 lines), `ModelRegistry.sol` (536), `ModelNFT.sol` (207). ChainId 29, RPC `https://rpc.genesisl1.org`.

**`ModelRegistry.registerModel()` — unbounded params (ModelRegistry.sol:291-393):**
```solidity
// Only checks: numChunks>0, chunkSize>0, title>0, icon>0, feeWei>0
// NO check: nTrees, depth, nFeatures, baseQ, scaleQ bounds
require(numChunks > 0, "NO_CHUNKS");
require(chunkSize > 0, "CHUNK0");
// fee rules only
```
Takes: `modelId, tablePtr, chunkSize, numChunks, totalBytes, nFeatures, nTrees, depth, baseQ, scaleQ, title, description, iconPng32, featuresPacked, titleWordHashes, pricingMode, feeWei, recipient, tosVersionAccepted, licenseIdAccepted, ownerKey` payable `10 ether` (`deployFeeWei`). Any `nTrees=65535, depth=20, nFeatures=1` registers.

**`ForestRuntime._predict()` — OOM DoS (ForestRuntime.sol:614-644):**
```solidity
uint256 pow2 = uint256(1) << uint256(depth); // depth=255 → overflow/shift panics or huge
uint256 internalNodes = pow2 - 1;
uint256 perTree = internalNodes * 8 + pow2 * 4;
for (uint256 t = 0; t < nTrees; t++)           // 65535 trees
  for (uint256 lvl = 0; lvl < depth; lvl++)     // 20 depth = 1.3M iterations
    _readU16Model(tablePtr, chunkSize, nodeOff); // extcodecopy each → gas burn
```
Also `_predictMultiFromChunks` reads header `magic 0x474c3146 ("GL1F") ver==2` but doesn't validate `totalBytes == header+trees*perTree` tightly — `require(expectedLen <= totalBytes)` only (can over-allocate).

**Additional sinks:** `extcodecopy` reads from `tablePtr` (attacker-controlled GL1C contracts) via `_chunkPtrAt` → `_requireChunkMagic(ptr, 0x474c3143 "GL1C")` — only checks first 4 bytes magic, not chunk content. `feature index f` read from model bytes with no `f < nFeatures` check before `packed[ f*4 ]` — OOB read (reverts OOB, but still DoS).

**Chain:** `registerModel(any nTrees/depth) payable 10 L1 → predictView/Tx OOM` . Impact: RPC/Explorer DoS for all Forest views, 10 L1 cost. Not RCE (extcodecopy, no delegatecall).

**Mitigation:** `require(nTrees <= 256 && depth <= 10 && nFeatures <= 512 && totalBytes == 24 + nTrees*perTree)` + `require(f < nFeatures)` + gas guard `nTrees*depth < 5000`.

### 2. NFTMarketplace — Vault Donation Theft

**File:** `NFTMarketplace-main/marketplace.sol` (650 lines), inherits `ReentrancyGuard`, `IERC721Receiver`.

**`onERC721Received` (147-166):** Any `safeTransferFrom` to marketplace with whitelisted NFT → `vaultItems.push(VaultItem(msg.sender, tokenId, true)); vaultIndex[msg.sender][tokenId] = length;` — no opt-in, seller becomes `address(this)`. Then `massListVaultTokens()` / `listVaultToken()` / `vaultTransferOut()` / `vaultTransferOutBatch()` (onlyEditor) can sell/transfer. Proceeds `buyToken` when `seller==address(this)` → `profitCollector`.

**Trust boundary:** User → marketplace vault (donation) → Editor (theft). `whitelistedNFTs` set by `onlyEditor`, no timelock.

**Mitigation:** Opt-in vault: `require(data == 0x01)` or separate `depositToVault()`, don't auto-vault every safeTransfer.

### 3. Hyperlane wL1 Bridge — 1-of-1 ISM

**Config:** `genesisl1-base-hyperlane-bridge-main/config/warp-route.yaml` + `validators-multisig.txt`.

- GenesisL1 `0x05cD463228768BEC155cBE9180E95652490BECF6` ISM `0x5aD803d8635eE8a065938d3F36A85baecF517712` validator `0x249f11Ab83EE30914aDe60F47f53e854c3737524` threshold 1
- Base `0xE6522A891702Cd2E8CC2A5182638c9DA1DD44B22` ISM `0xab41b4A43F10FbDD10381fba2bb8A95a59938f7C` validator `0x7F35C6adF5254908DF6604Ee664B8e1575213B80` threshold 1
- Governance Safes 3-of-5: `0x6D0A429Ecd85f3edc93722C2d25090DC722601b1` (GenesisL1) + `0x097430cAA419Bd84aB14C0802b8DF6F01a14fCe6` (Base), owners 5 same set. On-chain `owner()` already Safe (not EOA `0xF4e1...` as doc claims Stage 3 pending) — verified via `eth_call 0x8da5cb5b` on both routers + ProxyAdmin `0x8F039...`.
- Single hot validator per direction = 1 key compromise → unlimited mint.

**Mitigation:** Threshold 2-of-2 or 3-of-5, HSM for hot keys, Safe rotation published.

### 4. GenesisL1APIRegistry — Low

**File:** `api-registry-main/contract/GenesisL1APIRegistry.sol` (852 lines). `MAX_INSTANCES_PER_OWNER=4`, `MAX_ENDPOINTS_PER_INSTANCE=24`, `MAX_WRITE_FEE=1000 ether`, `TIMELOCK_DELAY=2 days`, `MIN_QUORUM=2`. `_validateUrl` blocks `< > " ' @ \ ` control chars, requires `https:// http:// wss:// ws:// grpcs:// grpc://` via keccak8. Health checkers quorum 2. Records are pull model — not push oracle. Low RCE, storage write DoS via fee only.

## Reproduction

```bash
# USER vs ORG
curl -sk "https://api.github.com/users/GenesisL1/repos?per_page=100" | jq length
# tarball fallback (try main then fallback branch)
curl -skL -o /tmp/Forest.tgz "https://codeload.github.com/GenesisL1/Forest/tar.gz/refs/heads/main" && tar xzf /tmp/Forest.tgz

# Live bridge owner (already Safe, not EOA)
curl -sk -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":"0x05cD463228768BEC155cBE9180E95652490BECF6","data":"0x8da5cb5b"},"latest"]}' https://rpc.genesisl1.org
# → 0x000...6d0a429ecd85f3edc93722c2d25090dc722601b1

# DoS POC (anvil fork chainId 29)
# deploy MaliciousTable+Chunk (GL1C magic) → registerModel with nTrees=5000 depth=12 → predictView OOM
```

## Operational Notes
- `genesis-ethermint` only tag `genesis-v0.5.0` has content; `main` is small (4045928 vs 19731023) — fetch both.
- 170 repos → filter forks early saves 75% clone time.
- Mainnet-only per operator: ignore `gl1-gas-faucet`, `l1coin-faucet`, `testnets` repos.
