# Plasma (ethrex) Audit — Session Findings

**Target:** https://www.plasma.org/ (Plasma Laboratoires / ethrex)
**Date:** 2026-08-14
**Status:** Partial findings — on-chain proof UNCONFIRMED

---

## Executive Summary

Plasma is an Ethereum L2 built with ethrex (Rust-based execution client). Audit found:
- **4 hardcoded private keys** in source code (3 L2 + 1 L1)
- **L2 proof coord key ACTIVE** (nonce=1 on mainnet)
- **L2 committer key NOT active** (nonce=0 — operator rotated)
- **L1 OnChainProposer owner key** — valid but on-chain deployment UNCONFIRMED
- **Public RPC exposure** — `txpool_content`, `debug_traceTransaction` exposed

---

## Hardcoded Keys Found

### L2 Keys (check on Plasma mainnet RPC: `https://rpc.plasma.to`)

| Role | Private Key | Address | Nonce | Status |
|------|-------------|---------|-------|--------|
| **SPONSOR** | `<redacted>` | `0x000e7328...` | 0 | ❌ Not active |
| **COMMITTER** | `<redacted>` | `0x3D1e15a1...` | 0 | ❌ Not active |
| **PROOF_COORD** | `<redacted>` | `0xE2558309...` | **1** | ✅ **ACTIVE** |

### L1 Key (check on Ethereum mainnet)

| Role | Private Key | Address | Nonce | Status |
|------|-------------|---------|-------|--------|
| **OnChainProposer Owner** | `<redacted>` | `0x4417092b...` | 0 | ❓ Unconfirmed |

---

## Code Analysis: OnChainProposer Owner Role

**Source:** `cmd/ethrex/l2/deployer.rs` + `crates/l2/contracts/src/l1/Timelock.sol`

### Deployment Flow (non-based mode, default):

```
1. Deploy Timelock
   - minDelay: 30 (hardcoded in deployer.rs line 1145)
   - governance: 0x4417092b...
   - securityCouncil: 0x4417092b... (SAME address!)
   - sequencers: [committer, proof_sender]

2. Deploy OnChainProposer (proxy + implementation)

3. Transfer OnChainProposer ownership → Timelock

4. Initialize Timelock
   - governance = 0x4417092b...
   - securityCouncil = 0x4417092b...
```

### Role Capabilities:

| Role | Function | Delay |
|------|----------|-------|
| **GOVERNANCE** | `schedule()` + `execute()` | 30 seconds |
| **SECURITY_COUNCIL** | `emergencyExecute()` | **0 (INSTANT)** |

### Attack Chain (if key is active):

```
1. Sign tx: emergencyExecute(OnChainProposer, 0, upgradeCalldata)
2. Upgrade OnChainProposer → malicious implementation
3. Malicious contract sends funds to attacker
4. Total time: ~30 seconds (1 tx)
```

### Based Mode Alternative:

If `deploy_based_contracts = true`:
- No Timelock deployed
- OnChainProposerBased deployed instead
- Owner = direct control (no delay)
- `onlyLeaderSequencer` modifier instead of `onlyOwner`

---

## On-Chain Verification Attempts

### Ethereum Mainnet (`https://eth.api.onfinality.io/public`)

| Check | Result |
|-------|--------|
| `eth_getBalance` | 0 ETH |
| `eth_getTransactionCount` | nonce = 0 |
| `eth_getCode` | 0 bytes (not a contract) |
| Event log search (50K blocks) | No events involving address |
| Contract ownership search | No contracts owned by address |

### Why Verification Failed:

1. **Address nonce=0** — never sent a transaction
2. **Address balance=0** — no ETH
3. **No event logs** — no contract interactions
4. **RPC limitations** — many Ethereum RPCs return 403 Forbidden
5. **Possible causes:**
   - Plasma used different owner address in production
   - Ownership was transferred after deployment
   - Plasma uses based mode (no Timelock)
   - Timelock deployed but with different config

---

## L2 Findings (Confirmed)

### Public RPC Exposure

| Method | Status | Impact |
|--------|--------|--------|
| `txpool_content` | ✅ Exposed | Pending tx details leaked → front-running |
| `debug_traceTransaction` | ⚠️ Partial | Execution traces leaked |
| `net_peerCount` | ✅ Exposed | Network topology leaked |
| `web3_clientVersion` | ✅ Exposed | `reth/v1.8.3` |

### Devnet Exposure

| Host | Port | Status |
|------|------|--------|
| `devnet.plasmalabs.tech` (3.21.220.26) | 443 | ✅ Responds to HTTPS |
| Admin server (5555) | — | ❌ Closed |
| Consensus API (35070) | — | ❌ Closed |

Devnet exposes: `txpool_content`, `debug_traceBlockByNumber`, `eth_getProof`

---

## Key Lessons Learned

### 1. L1 vs L2 Key Verification

**L2 keys** → Check on L2 RPC (`https://rpc.plasma.to`)
**L1 keys** → Check on Ethereum mainnet

In this session:
- L2 proof coord nonce=1 → **ACTIVE** (CRITICAL)
- L1 owner nonce=0 → **UNCONFIRMED** (needs more evidence)

### 2. Based vs Non-Based Mode

Plasma can deploy in two modes:
- **Non-based (default):** Timelock with 30s delay + SECURITY_COUNCIL bypass
- **Based mode:** Direct owner control, no Timelock

The mode affects what the L1 owner key can do.

### 3. SECURITY_COUNCIL Bypass

OpenZeppelin's TimelockController has a `SECURITY_COUNCIL` role that can:
- `emergencyExecute()` — bypass delay entirely
- `emergencyExecute()` — instant control

If governance AND securityCouncil are the same address (as in default config), that address has:
- Normal path: schedule + execute (30s delay)
- Emergency path: instant execution (0 delay)

### 4. Genesis Analysis Pitfall

The `cmd/ethrex/networks/mainnet/genesis.json` file contains **Ethereum mainnet genesis** (chainId: 1), NOT Plasma L2 genesis. This is because ethrex uses the same client for L1 and L2.

Plasma L2 genesis is likely configured elsewhere or generated dynamically.

### 5. RPC Availability Issues

Many public Ethereum RPCs block requests:
- Cloudflare: 403 Forbidden
- PublicNode: 403 Forbidden
- LlamaRPC: 403 Forbidden
- drpc: 403 Forbidden

Working RPC: `https://eth.api.onfinality.io/public`

---

## Unresolved Questions

1. **Is OnChainProposer deployed on Ethereum mainnet?**
   - Address nonce=0 suggests no, or ownership transferred

2. **What mode does Plasma production use?**
   - Based or non-based? Affects key utility

3. **Was the default config used?**
   - L2 committer nonce=0 suggests operator override

4. **Where is the L2 genesis?**
   - Not in the expected location

---

## Recommendations for Future Audits

1. **Check both L1 and L2** for key activity
2. **Try multiple RPCs** — many block requests
3. **Search event logs** for contract discovery
4. **Check based vs non-based mode** — affects attack surface
5. **Look for SECURITY_COUNCIL role** — can bypass timelock
6. **Don't assume genesis location** — may be dynamic

---

## Related Files

- `cmd/ethrex/l2/deployer.rs` — Deployment logic, hardcoded keys
- `crates/l2/contracts/src/l1/Timelock.sol` — Timelock with SECURITY_COUNCIL
- `crates/l2/contracts/src/l1/OnChainProposer.sol` — Main contract
- `crates/l2/contracts/src/l1/based/OnChainProposer.sol` — Based mode variant
- `cmd/ethrex/l2/options.rs` — L2 key defaults
