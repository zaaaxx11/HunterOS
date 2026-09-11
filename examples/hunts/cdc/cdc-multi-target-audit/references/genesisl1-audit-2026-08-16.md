# GenesisL1 Audit 2026-08-16 — USER not ORG + Hardened Checker + Threshold-1 Bridge

**Target:** `https://github.com/GenesisL1` (170 repos) + `https://rpc.genesisl1.org` (chainId 29) + `scan.alltoscan.com`
**Scope:** Only mainnet — `gl1-gas-faucet`/`l1coin-faucet`/testnet explicitly excluded (`hindara testnet/faucet dll. only mainnet`)

## 1. USER vs ORG Trap

`GET https://api.github.com/orgs/GenesisL1/repos` → `404 Not Found` (`documentation_url: list-organization-repositories`). GenesisL1 is a **user account**, not an org.

Fix: `GET https://api.github.com/users/GenesisL1/repos?per_page=100&page=1..2` → 170 total (page1 100 + page2 70). `api.github.com/users/GenesisL1` HTML shows `data-hovercard-type="achievement"` not repo list — use API.

## 2. 170 → 39 Non-Forks Filter

`jq -s 'add | map(select(.fork==false))'` → 39 originals. Rest 131 forks are noise (3d-multiplayer, bdjuno forks, etc.). Forks waste 909M/685M disk — filter before `tar.gz` fetch.

Non-forks that matter (contract-bearing):
`Forest` (GBDT on-chain), `api-registry` (Solidity 0.8.24 + checker.py), `genesis-crypto`, `genesis-ethermint`, `genesisl1-base-hyperlane-bridge`, `molnft`, `NFTMarketplace` (ExampleNFTMarketplace 650L), `genesis-snapshots` (GENESIS.sol 0.7.0, 21M mint only in constructor), `chaintools`, `crypto-solidity` (TEA.sol)

Forks to skip unless bridge infra: `bdjuno`, `cometbft`, `ibc-go` — only if staking/consensus surface.

## 3. TencentOS git-remote-https Missing (again)

`git clone https://` → `git: 'remote-https' is not a git command` — `/usr/local/libexec/git-core` lacks `git-remote-https` (no curl build). `dnf install git` → `No match`.

Bypass: `curl -L -o /tmp/x.tar.gz https://github.com/GenesisL1/<repo>/archive/refs/heads/main.tar.gz && tar xzf /tmp/x.tar.gz -C /tmp/x --strip-components=1` . Raw file: `https://raw.githubusercontent.com/GenesisL1/<repo>/main/<path>`. Already captured in `berachain-audit-2026-08.md` but reproducible on every TencentOS 4 host.

Disk: 20G total, delegation logs in `/root/.hermes` 1.4G must be preserved — `rm -rf /tmp/*.tar.gz` only, never `rm -rf /root/.hermes/cache/delegation`.

## 4. Hardened Checker — SSRF BLOCKED

`api-registry/bot/checker.py` 1082L — textbook SSRF defense:

- `GuardedResolver(AbstractResolver)` checks **inside connector** after `DefaultResolver().resolve()` — closes DNS rebinding window (validate-before-resolve is insufficient)
- `is_public_address()` blocks `is_private/is_loopback/is_link_local/is_multicast/is_reserved/is_unspecified` + IPv4-mapped `::ffff:127.0.0.1` + 6to4 smuggling
- `validate_url()` enforces `len<=256`, `scheme in (http,https,ws,wss,grpc,grpcs)`, `no @ creds`, literal IP via `is_public_address` before resolver
- `read_capped(response, 64*1024)` + `HTTP2 preface` + `_reject_redirect(300-400)` never follows
- `allow_private` must match resolver setting — two layers agree

Finding spoof: `registerEndpoint(url=http://169.254.169.254)` → blocked at `is_public_address` + `GuardedResolver` OSError `blocked target resolves outside public` — **PROVEN BLOCKED**, not RCE.

## 5. Hyperlane Warp Threshold-1 — Centralization HIGH

`genesisl1-base-hyperlane-bridge/config/warp-route.yaml`: `ismThreshold: 1` + `ismValidators: [0x249f...7524]` (Base) / `[0x7F35...3B80]` (GenesisL1). Single validator can forge `Base→GenesisL1` message.

But owner already migrated: `eth_call 0x8da5cb5b` on `0x05cD463228768BEC155cBE9180E95652490BECF6` (HypERC20Collateral router) and `0xE6522A891702Cd2E8CC2A5182638c9DA1DD44B22` (Mailbox on Base) → `0x6D0A429Ecd85f3edc93722C2d25090DC722601b1` (Safe 3-of-5, 5 owners listed in `validators-multisig.txt` Stage 3 PENDING docs stale). `ProxyAdmin 0x8F03945D...` same Safe. So upgrade not EOA — need 3-of-5.

Impact: **HIGH centralization** (1 validator leak → mint wL1), but not pre-auth RCE — requires validator key compromise + ISM threshold bypass. Label `HIGH` not `CRITICAL RCE`.

## 6. NFTMarketplace Vault — No RCE

`NFTMarketplace/marketplace.sol` 650L `ExampleNFTMarketplace is IERC721Receiver, ReentrancyGuard`:

- `vaultItems[]` + `vaultIndex[msg.sender][tokenId]=length` in `onERC721Received` (requires `whitelistedNFTs[msg.sender]`)
- `onlyEditor` on `vaultTransferOut`, `vaultTransferOutBatch`, `massListVaultTokens`, `setProfitCollector`
- `nonReentrant` on `listToken`, `buyToken`, `placeBid`, `cancelListing` but **not** on `vaultTransferOut` — `onlyEditor` limits to trusted role, cross-function reentrancy via `safeTransferFrom` callback blocked by `onlyEditor` gate, not `nonReentrant`

`GENESIS.sol` (genesis-snapshots) — `pragma 0.7.0`, `contract GENESISToken is ERC20 { constructor() { _mint(msg.sender, 21M*10^decimals) } }` — no `mint/onlyOwner/transferOwnership` after deploy.

## 7. Workflow Signal

User: `spawn sub agent 4 untuk saling audit, jangan menyerah minimal 1 jam, hindari testnet/faucet dll. only mainnet` — enforce 1-hour floor via `tail -f task-*.log` + `ps aux | grep fetch`, sequential per-target CDC, manual layer 2 while delegation fetches. Report only after `write_file` reports exist, honest `PROVEN/HIGH/THEORETICAL` + `BLOCKED` table.

**Next hunt:** `GenesisL1APIRegistry.sol: is_public_address` bypass via `0x7f.0.0.1`/`http://***@127.0.0.1` already blocked; `ForestRuntime` delegatecall/storage collision; `genesis-ethermint` staking/upgrade still pending.
