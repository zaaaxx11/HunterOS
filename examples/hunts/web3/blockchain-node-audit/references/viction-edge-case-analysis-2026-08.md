# Viction (buildonviction) Trust Graph — Security Audit

**Date:** 2026-08-16
**Scope:** 30 public repos, 6 cloned/inspected, defensive audit

---

## Repository Inventory (30 public repos)

| Repo | Language | Category | Key Content |
|------|----------|----------|-------------|
| **victionchain** | Go | Node (fork of go-ethereum) | POSV consensus, TomoX, TomoZ, TRC21, full node `tomo` |
| **vic-geth** | Go | Node (newer geth fork) | Beacon/clique consensus, no POSV — Erigon-adjacent |
| **vic-erigon** | — | Node | Erigon-based execution client (listed, not cloned) |
| **viction-contracts** | Solidity | Smart contracts | TomoValidator, TRC21, TomoX, BlockSigner, MultisigWallet |
| **vrc25** | Solidity/TS | Token standard | VRC25/VRC25Permit token spec (OpenZeppelin-style Ownable) |
| **tomomaster** | Vue/JS | Governance dApp | Masternode/voter UI, candidate management, QR login |
| **tomox-sdk** | Go | DEX SDK | Relayer/order-matching SDK for TomoX protocol |
| **tomox-sdk-ui** | JS | DEX UI | Frontend for TomoX DEX |
| **tomoscan** | Vue | Block explorer | Etherscan-like explorer |
| **dex-smart-contract** | JS | DEX contracts | DEX protocol contracts |
| **dex-protocol** | Go | DEX protocol | Go implementation of DEX logic |
| **erc20-crawler** | JS | Indexer | Token crawler |
| **tomoxjs** | JS | SDK | TomoX relayer JS SDK |
| **tomoissuer** | Solidity | Token issuance | TRC21/VRC25 issuer contracts |
| **privacy-sc** | Solidity | Privacy | Privacy smart contracts |
| **tomop** | Go | Privacy | Privacy protocol implementation |
| **privacyjs** | JS | Privacy | Privacy JS library |
| **privacy-wasm** | Go | Privacy | Privacy WASM build |
| **crosschain-transfer-demo** | JS | Bridge | Cross-chain transfer demo |
| **proxy** | Go | Proxy | Generic proxy service |
| **rpc-swagger** | HTML | API docs | RPC Swagger documentation |
| **tomochain-rosetta-gateway** | Go | Rosetta API | Rosetta-compliant gateway |
| **infrastructure** | HCL | Infra | Terraform configs |
| **docs** | JS | Docs | Documentation portal |
| **tokens** | Shell | Token lists | Token directory |
| **bug-reports** | — | Security | Bug bounty reports |
| **cloud-images** | — | Infra | VM images |
| **devp2p-network** | — | Network | P2P network configs |
| **ledger-app-eth** | — | Hardware | Ledger app |
| **skills** | — | Misc | Skills |

---

## Architecture & Data Flow

```
USER INPUT LAYER
  Wallets (MetaMask, Ledger) │ tomomaster dApp │ TomoX relayers
            │                        │
            ▼                        ▼
  tomomaster (Vue)          tomox-sdk (Go)
  - Candidate management    - Order matching
  - Voting/unvoting         - Lending market
  - QR login (sig verify)   - Price board
  - MongoDB (off-chain)     - RabbitMQ
            │                        │
            ▼                        ▼
  JSON-RPC / HTTP / WebSocket
  eth_sendRawTransaction │ custom TomoX APIs
            │
            ▼
  VICTION NODE (victionchain / vic-geth)
  ┌────────────┐  ┌──────────────┐  ┌────────────────────────────┐
  │  RPC Layer │  │  Tx Pool     │  │  Consensus (POSV)          │
  │  (http/ws) │  │  (order_pool)│  │  - Masternode signing      │
  └─────┬──────┘  └──────┬───────┘  │  - Vote snapshots          │
        │                │          │  - M1/M2 randomization     │
        ▼                ▼          └────────────┬───────────────┘
  ┌──────────────────────────────────────────────────────────────┐
  │                    STATE PROCESSOR                           │
  │  - Blacklist check (common.Blacklist map)                    │
  │  - TRC21 fee validation                                      │
  │  - TomoZ/TomoX validation                                    │
  │  - EVM execution                                             │
  └────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                    SMART CONTRACTS                           │
  │  - TomoValidator.sol (governance, voting)                    │
  │  - TRC21.sol / VRC25.sol (tokens, fees)                      │
  │  - TomoX Registration (relayer mgmt)                         │
  │  - BlockSigner.sol (consensus helper)                        │
  │  - TomoRandomize.sol (M2 assignment)                         │
  └──────────────────────────────────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                    STATE DB (LevelDB/Badger)                 │
  └──────────────────────────────────────────────────────────────┘
                           │
                           ▼
  OUTPUT LAYER
  Block explorer (tomoscan) │ dApps │ Exchanges │ Other nodes
```

---

## Control Flow — Who Can Access What

| Actor | Access Level | What They Control |
|-------|-------------|-------------------|
| **Regular User** | Read-only RPC + tx submission | Own transactions, votes (via TomoValidator), token transfers |
| **Masternode Operator** | Node operator + consensus signer | Block production, tx inclusion, consensus signatures |
| **Token Issuer (TRC21/VRC25)** | Contract owner | `_minFee` setting, token minting (via capacity), fee collection |
| **Relayer (TomoX)** | Registered operator | Order matching, trade execution, fee collection |
| **Foundation/Eco Fund** | Hardcoded addresses | 10% block rewards, TomoXListing fees (1000 VIC per token) |
| **Node RPC Admin** | Private RPC namespaces | `personal_*`, `admin_*`, `debug_*` APIs (if HTTP enabled) |
| **Core Dev / Multisig** | Contract deployer | Upgrade paths (if any), parameter changes via hardfork |

---

## Trust Boundaries Identified

### Boundary B1: User Transaction → Node Mempool (Blacklist Enforcement)
- **Input:** Raw signed transaction from any user
- **Transform:** `core/tx_pool.go`, `core/state_processor.go` check `common.Blacklist`
- **Storage:** Rejected at mempool entry; never reaches block
- **Admin side:** `common/constants.go` has a hardcoded `Blacklist` map (~70 addresses)
- **Risk:** Hardcoded blacklist is immutable without hardfork; no governance mechanism to add/remove. Addresses are compiled into binary.

### Boundary B2: Masternode Voting → Consensus Power (TomoValidator.sol)
- **Input:** User votes (`propose`, `vote`, `unvote`)
- **Transform:** TomoValidator contract tracks stake/capacity
- **Storage:** On-chain validator state
- **Admin side:** Top 150 candidates by stake become masternodes; they produce blocks
- **Risk:** `onlyOwner` modifier in TomoValidator; contract owner (`_firstOwner`) is hardcoded at deployment. Owner can resign candidates.

### Boundary B3: Token Issuer → Fee Parameters (TRC21/VRC25)
- **Input:** Token transfer calls
- **Transform:** `_minFee` deducted per transfer, sent to `_issuer`
- **Storage:** Contract storage `_minFee`, `_issuer`
- **Admin side:** Token owner can change `_minFee` (via `onlyOwner`), but VRC25 uses two-step ownership transfer
- **Risk:** Issuer sets fee unilaterally; no cap. VRC25 has `onlyOwner` on fee changes.

### Boundary B4: Relayer Registration → DEX Operations (TomoX)
- **Input:** Relayer applies via `RelayerRegistration.sol`
- **Transform:** Contract validates deposit (20000 VIC), owner, trade fee
- **Storage:** On-chain relayer list
- **Admin side:** `CONTRACT_OWNER` in RelayerRegistration can config max relayers, max tokens, min deposit
- **Risk:** Centralized owner controls relayer parameters. `contractOwnerOnly` modifier.

### Boundary B5: RPC API → Node Control (Private APIs)
- **Input:** JSON-RPC calls over HTTP/WebSocket
- **Transform:** `internal/ethapi/api.go` routes to `PrivateDebugAPI`, `PersonalAPI`
- **Storage:** Node keystore, chain state
- **Admin side:** `personal_importRawKey`, `personal_unlockAccount`, `debug_setHead`, `admin_addPeer`
- **Risk:** If HTTP RPC exposes private namespaces, any caller can unlock accounts, import keys, set head.

### Boundary B6: Block Import → Chain State (BadHashes + Blacklist)
- **Input:** Incoming blocks from peers
- **Transform:** `core/blockchain.go` checks `BadHashes` map + `BlacklistHFBlock`
- **Storage:** Rejected blocks never imported
- **Admin side:** Hardcoded banned hashes + address blacklist
- **Risk:** Censorship at protocol level; no appeal mechanism.

### Boundary B7: TomoMaster Login → Off-chain Identity
- **Input:** User signature for QR login
- **Transform:** `apis/auth.js` verifies signature, stores in MongoDB
- **Storage:** MongoDB `Signature` collection
- **Admin side:** MongoDB admin can read/modify login sessions
- **Risk:** No rate limiting visible; QR code reuse prevention exists but relies on DB consistency.

### Boundary B8: TomoX SDK → Relayer Order Signing
- **Input:** Order data from traders
- **Transform:** `relayer/signer.go` signs with relayer's keystore
- **Storage:** Keystore file + passphrase on disk
- **Admin side:** Relayer operator holds private key
- **Risk:** Keystore passphrase stored in config file; file-based key management.

---

## Top 5 Trust Boundaries (Ranked by Risk)

| Rank | Boundary | Severity | Why |
|------|----------|----------|-----|
| **1** | **B5: RPC Private APIs** | 🔴 Critical | Exposing `personal_*` or `admin_*` over HTTP gives full account control. Many node operators misconfigure `--http.api`. |
| **2** | **B1/B6: Hardcoded Blacklist + BadHashes** | 🔴 Critical | Protocol-level censorship with no governance. ~70 addresses + 2 hashes hardcoded in binary. Cannot be updated without hardfork. |
| **3** | **B3: Token Issuer Fee Control** | 🟠 High | TRC21/VRC25 issuers set fees unilaterally. No cap, no timelock. User funds are subject to arbitrary fee extraction on every transfer. |
| **4** | **B2: Masternode Owner Privileges** | 🟠 High | TomoValidator contract owner can resign candidates. Initial owner is hardcoded at deploy. Governance centralization risk. |
| **5** | **B4: Relayer Registration Owner** | 🟡 Medium | RelayerRegistration `CONTRACT_OWNER` controls max relayers, token lists, deposits. Centralized parameter control over DEX infrastructure. |

---

## Key Findings Summary

### Smart Contract Attack Surface
- **TomoValidator.sol** — `onlyOwner` modifier, hardcoded initial owner, no timelock
- **TRC21.sol / VRC25.sol** — `onlyOwner` on fee changes, two-step transfer in VRC25
- **RelayerRegistration.sol** — `contractOwnerOnly` on config, `relayerOwnerOnly` on operations
- **TomoXListing.sol** — No owner; anyone can list tokens for 1000 VIC fee (goes to hardcoded foundation)

### Node-Level Censorship
- `common.Blacklist` map in `common/constants.go` — 70+ hardcoded addresses
- Checked in: `tx_pool.go`, `state_processor.go`, `order_pool.go`, `lending_pool.go`, `miner/worker.go`, `blockchain.go`, `headerchain.go`
- `BadHashes` in `core/blocks.go` — 2 hardcoded banned block hashes

### RPC Exposure
- `internal/ethapi/api.go` exposes: `personal_sign`, `personal_ecRecover`, `personal_importRawKey`, `personal_unlockAccount`, `debug_setHead`, `debug_stableState`, `admin_addPeer`, `admin_removePeer`
- All gated by API namespace configuration (`--http.api`, `--ws.api`)

### Off-chain Risks
- **tomomaster:** MongoDB stores login signatures; no visible rate limiting on auth endpoints
- **tomox-sdk:** Relayer keystore + passphrase in config file; `ApiAuthKey` in plaintext config
- **infrastructure:** Terraform configs may expose secrets if not properly managed

---

## Recommendations

1. **RPC Hardening:** Default to `eth,net,web3` only. Never expose `personal`, `admin`, `debug` over HTTP. Use IPC for private APIs.
2. **Blacklist Governance:** Move blacklist to a smart contract with multisig governance. Add timelock for additions/removals.
3. **Fee Caps:** Add maximum fee caps to TRC21/VRC25 with timelock on changes.
4. **Contract Upgradability:** Audit upgrade paths for TomoValidator and RelayerRegistration. Consider timelock + multisig.
5. **Keystore Security:** Move relayer key management to HSM or remote signer (clef). Never store passphrases in config files.
6. **Rate Limiting:** Add rate limiting to tomomaster auth endpoints to prevent brute-force login attempts.

---

## GitHub Recon Technique (Rate-Limited API Fallback)

When `api.github.com` returns 403 rate-limit:

```bash
# HTML scrape for repo list
curl -sL "https://github.com/orgs/BuildOnViction/repositories?type=all" | \
  grep -oE 'href="/BuildOnViction/[a-zA-Z0-9_.-]+"' | \
  sed 's|/BuildOnViction/||g' | sort -u

# Zip download (no git-remote-https needed)
curl -sL -o repo.zip https://github.com/<org>/<repo>/archive/refs/heads/master.zip
file repo.zip  # verify: Zip archive, not HTML
unzip -q repo.zip
```

This works when `git clone https://...` fails with `git: 'remote-https' is not a git command`.

---

*Report generated from direct code inspection of 6 cloned repositories + GitHub org reconnaissance. No git history available (shallow clones only).*
