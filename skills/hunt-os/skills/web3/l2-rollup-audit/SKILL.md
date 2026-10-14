---
name: l2-rollup-audit
description: "L2 rollup audit"
category: security
---

# L2 Rollup Security Audit

Systematic methodology for auditing Layer 2 rollup systems. L2 audits differ from L1 smart contract audits because they involve **multi-layer architecture** (L2 execution + L1 settlement) and **operational components** (sequencer, prover, bridge) that don't exist in standalone contracts.

## When to Use

- Auditing Optimistic Rollups (OP Stack, Arbitrum, etc.)
- Auditing ZK Rollups (zkSync, Starknet, Polygon zkEVM, etc.)
- Auditing Plasma chains (ethrex, etc.)
- Any L2 with bridge to L1

## L2 Architecture Primer

```
┌─────────────────────────────────────────────────────────────┐
│  L2 (Rollup Chain)                   L1 (Settlement)        │
│                                                             │
│  ┌──────────────┐                      ┌──────────────┐    │
│  │  Users/Txs   │                      │   Bridge     │    │
│  └──────┬───────┘                      │   Contract   │    │
│         │                               └──────┬───────┘    │
│  ┌──────▼───────┐                      ┌──────▼───────┐    │
│  │  Sequencer   │─── Batch ────────────►│  Verifier    │    │
│  │  (orders tx) │    Submission         │  /Proposer   │    │
│  └──────┬───────┘                      └──────┬───────┘    │
│         │                                      │            │
│  ┌──────▼───────┐                      ┌──────▼───────┐    │
│  │   Prover     │─── Proof ────────────►│  Timelock    │    │
│  │  (generate)  │    Verification       │  (delay)     │    │
│  └──────────────┘                      └──────────────┘    │
│                                                             │
│  Funds: Treasury contracts on L2     Funds: Bridge on L1   │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Role | Risk if Compromised |
|-----------|------|---------------------|
| **Sequencer** | Orders & batches L2 transactions | Can reorder, censor, or include fake txs |
| **Committer** | Submits batches to L1 | Can submit invalid state transitions |
| **Prover** | Generates ZK/validity proofs | Can generate fake proofs (ZK only) |
| **Proof Coordinator** | Manages proof generation workflow | Can submit invalid proofs |
| **OnChainProposer** | L1 contract that accepts batches | Owner can upgrade & drain bridge |
| **Timelock** | Delays upgrades (safety) | Owner can bypass via emergency functions |
| **Bridge** | Locks/unlocks funds L1↔L2 | Direct fund theft if compromised |

## Phase 1: Reconnaissance

### 1.1 Identify L2 Type

```bash
# Check chain ID and RPC
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
  https://<l2-rpc>

# Check if it's OP Stack, Arbitrum, etc.
# Look for specific system contracts or precompiles
```

### 1.2 Map the Codebase

For open-source L2s (ethrex, op-stack, etc.):

```bash
# Clone and search for key components
git clone <repo>
grep -r "private_key\|PRIVATE_KEY\|privateKey" --include="*.rs" --include="*.go" --include="*.ts"
grep -r "sequencer\|committer\|proposer\|coordinator" --include="*.rs" --include="*.go"
```

### 1.3 Identify Hardcoded Keys

**Common locations:**

| File Pattern | What to Look For |
|--------------|------------------|
| `options.rs`, `config.rs` | Default private keys for operators |
| `deployer.rs`, `deploy.ts` | Deployer keys, owner keys |
| `.env.example`, `config.toml` | Default configs with keys |
| `fixtures/keys/` | Test/fixture keys that might be reused |

**ethrex-specific:**
```
cmd/ethrex/l2/options.rs     → SPONSOR, COMMITTER, PROOF_COORD keys
cmd/ethrex/l2/deployer.rs    → ON_CHAIN_PROPOSER_OWNER key
fixtures/keys/private_keys_l1.txt → L1 keys
```

## Phase 2: Key Verification

### 2.1 Derive Addresses

```python
from eth_account import Account

def derive_address(private_key_hex):
    if private_key_hex.startswith('0x'):
        private_key_hex = private_key_hex[2:]
    account = Account.from_key(private_key_hex)
    return account.address, account.key
```

### 2.2 Check On-Chain Activity

Use the verification script:

```bash
python3 scripts/l2-key-check.py \
  --rpc https://rpc.plasma.to \
  --keys 0x1234...,0x5678...
```

Or manually:

```python
def check_address_activity(rpc_url, address):
    # Balance
    balance = eth_rpc("eth_getBalance", [address, "latest"])
    
    # Nonce (transaction count)
    nonce = eth_rpc("eth_getTransactionCount", [address, "latest"])
    
    # Code (is it a contract?)
    code = eth_rpc("eth_getCode", [address, "latest"])
    
    return {
        "balance": int(balance.get("result", "0x0"), 16),
        "nonce": int(nonce.get("result", "0x0"), 16),
        "is_contract": len(code.get("result", "0x")) > 2,
    }
```

**Key insight:** `nonce=0` means the address has NEVER sent a transaction. This could mean:
- The key is not used in production (operator overrode default)
- The key is used only for signing (not sending txs)
- The deployment hasn't happened yet

**`nonce>0` means the key IS actively used.**

### 2.3 Cryptographic Proof

```python
from eth_account import Account

def prove_key_ownership(private_key_hex):
    account = Account.from_key(private_key_hex)
    message = "Plasma.org security audit - proving key ownership"
    signed = Account.sign_message(message, account.key)
    return {
        "address": account.address,
        "signature": signed.signature.hex(),
        "verified": Account.recover_message(message, signature=signed.signature) == account.address
    }
```

## Phase 3: Bridge Architecture

### 3.1 Understand Fund Flow

```
User deposits L2:
  L2: User → Bridge (locked on L2)
  L2: Bridge emits deposit event
  L1: Verifier sees event → mints/releases on L1

User withdraws L2→L1:
  L2: User burns tokens
  L2: Withdrawal included in batch
  L1: OnChainProposer verifies proof → releases funds
```

### 3.2 Find Treasury Addresses

```python
# Treasury is often at predictable addresses
# In ethrex/Plasma: 0x0000...a11b001-005

TREASURY_ADDRESSES = [
    "0x000000000000000000000000000000000a11b001",
    "0x000000000000000000000000000000000a11b002",
    # ...
]

for addr in TREASURY_ADDRESSES:
    balance = eth_rpc("eth_getBalance", [addr, "latest"])
    code = eth_rpc("eth_getCode", [addr, "latest"])
    # Check if proxy
    impl_slot = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    impl = eth_rpc("eth_getStorageAt", [addr, impl_slot, "latest"])
```

### 3.3 Find Bridge Contract

```python
# Bridge contract stores L1 bridge address in storage
# Check system contracts for L1 address references

def find_l1_bridge_address(l2_rpc, system_contract):
    for slot in range(10):
        storage = l2_rpc("eth_getStorageAt", [system_contract, hex(slot), "latest"])
        val = storage.get("result", "0x0")
        if val and val != "0x0" * 64:
            # Could be an address
            candidate = "0x" + val[-40:]
            if is_valid_address(candidate):
                return candidate
    return None
```

## Phase 4: Attack Vector Analysis

### 4.1 Key-Based Attacks

| Key Type | Attack | Prerequisites |
|----------|--------|---------------|
| **Sequencer key** | Censorship, reordering, MEV | Key active + sequencer centralized |
| **Committer key** | Submit invalid batches | Key active + no validation |
| **Proof Coord key** | Submit fake proofs | Key active + proof verification weak |
| **OCP Owner key** | Upgrade contract, drain bridge | Key active + emergencyExecute available |

### 4.2 Why Having a Key ≠ Direct Drain

**Common misconception:** "I have the private key, I should be able to drain funds."

**Reality:**

```
┌─────────────────────────────────────────────────────────────┐
│  FUNDS ARE IN CONTRACTS, NOT EOAs                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Treasury: 0x0000...a11b004 (proxy contract)               │
│    - Not an EOA, can't just "send" from it                 │
│    - Need to call withdraw() function                       │
│    - withdraw() has access control                          │
│    - Access control = owner/admin only                      │
│    - Owner = system contract (0x0000...f000)               │
│                                                             │
│  Bridge: OnChainProposer (L1 contract)                      │
│    - Upgradeable via Timelock                               │
│    - Timelock owner = SECURITY_COUNCIL                      │
│    - SECURITY_COUNCIL can emergencyExecute (0 delay)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**To drain, you need:**
1. **Admin key** (OCP Owner) → upgrade contract → add malicious withdraw
2. **Proof manipulation** → fake withdrawal proofs
3. **Proxy admin** → upgrade treasury implementation

### 4.3 Attack Chains

```
OPTION A: Via Bridge (L1)
  1. Get OCP Owner key
  2. Call emergencyExecute() on Timelock
  3. Upgrade OnChainProposer implementation
  4. New implementation sends funds to attacker
  Time: ~30 seconds (or instant with emergencyExecute)

OPTION B: Via Proof Manipulation (L2)
  1. Get Proof Coord key
  2. Submit fake proof for fake batch
  3. Fake batch includes withdrawal to attacker
  4. Wait for verification
  Time: Depends on proof generation + verification

OPTION C: Via Treasury Proxy (L2)
  1. Get proxy admin key
  2. Upgrade treasury implementation
  3. New implementation sends funds to attacker
  Time: Depends on proxy admin access
```

## Phase 5: Reporting

### 5.1 Evidence Requirements

| Finding | Evidence Needed |
|---------|-----------------|
| Hardcoded key | File path + line number + derived address |
| Key active on-chain | Address + nonce + balance + tx hash (if any) |
| Bridge vulnerability | Contract address + function + access control |
| Fund at risk | Treasury address + balance + access control |

### 5.2 Report Structure

```markdown
## Critical: [Finding Title]

**Status:** [Code-confirmed / Live-confirmed / Theoretical]

**Evidence:**
- File: `path/to/file.rs:line`
- Address: `0x...`
- Nonce: `X` (active/inactive)

**Impact:**
- Funds at risk: X tokens ($Y)
- Attack vector: [description]
- Time to exploit: [estimate]

**Attack Chain:**
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Proof of Concept:**
[Code or transaction details]

**Recommendation:**
[Fix suggestion]
```

## Pitfalls

### Pitfall 1: Assuming Key = Direct Access

**Wrong:** "We found a hardcoded key, attacker can drain funds."

**Right:** "We found a hardcoded key. The address has nonce=X. To drain funds, attacker would need to [specific steps]."

### Pitfall 2: Ignoring On-Chain Verification

Always check:
- Is the address actually used? (nonce > 0)
- Is the address a contract or EOA?
- What functions can this address call?

### Pitfall 3: Confusing L2 and L1 Keys

- **L2 keys** (sequencer, committer, proof coord) operate on L2
- **L1 keys** (OCP owner, timelock admin) operate on L1
- Funds on L2 ≠ funds on L1
- Bridge connects them but has its own access control

### Pitfall 4: Not Checking emergencyExecute

Timelock usually has:
- `schedule()` → delay → `execute()` (slow path)
- `emergencyExecute()` → instant (fast path)

If `emergencyExecute` exists and the key has this role, the delay is meaningless.

### Pitfall 5: Testnet vs Mainnet Confusion

- Keys might be used on testnet but not mainnet
- Always verify on the correct network
- Check chain ID, not just address

### Pitfall 6: EIP-7702 Delegation Forwarding

**New finding (2026-08-15):** EIP-7702 delegated accounts may auto-forward funds to a separate address.

**What happened:**
- Sent funds to proof coord address (`0xE25583...`)
- Funds automatically forwarded to `0x62B397AF...`
- This address is NOT derived from hardcoded keys

**Lesson:** When auditing EIP-7702 delegated accounts:
1. Check where funds actually end up
2. The forwarding address might be operator-controlled
3. Monitor the forwarding address for activity
4. The forwarding address might have its own private key exposure

**RPC Sync Issue:**
- Explorer may show balance, but RPC shows 0
- Different nodes may have different sync states
- Use explorer as source of truth when RPC lags

## Quick Reference

### ethrex/Plasma Specific

```
Default Keys (cmd/ethrex/l2/options.rs):
  SPONSOR_PRIVATE_KEY    → line 44
  COMMITTER_PRIVATE_KEY  → line 661
  PROOF_COORD_PRIVATE_KEY → line 795

Default Owner (cmd/ethrex/l2/deployer.rs):
  ETHREX_ON_CHAIN_PROPOSER_OWNER_PK → line 426

Treasury Addresses:
  0x000000000000000000000000000000000a11b001-005

Proxy Admin:
  0x000000000000000000000000000000000000f000
```

### Common L2 Patterns

| L2 Framework | Sequencer Key | Bridge Contract | Owner Pattern |
|--------------|---------------|-----------------|---------------|
| OP Stack | `sequencer-p2p-key` | `L1StandardBridge` | `ProxyAdmin` → multi-sig |
| Arbitrum | `node-keys` | `Bridge` | `UpgradeExecutor` |
| zkSync | `validator` | `ValidatorTimelock` | `Governance` |
| ethrex/Plasma | `committer` | `OnChainProposer` | `Timelock` → `SECURITY_COUNCIL` |

## References

- [ethrex Repository](https://github.com/PlasmaLaboratories/ethrex)
- [Plasma RPC](https://rpc.plasma.to)
- [EIP-7702 Specification](https://eips.ethereum.org/EIP-7702)

## Update: EIP-7702 Funds Forwarding

(The 2026-08-15 Plasma session log — forwarding-address discovery, delegated-contract analysis, RPC sync issue, live key proof, and the updated recommendations — is preserved at examples/hunts/web3/l2-rollup-audit/eip7702-session.md. The reusable lesson stays in Pitfall 6 above: EIP-7702 delegated accounts may auto-forward funds; check where funds actually end up.)
