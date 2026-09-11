# Plasma.org Audit Findings

Session-specific findings from auditing PlasmaLaboratories/ethrex codebase.

## Hardcoded Keys Found

### L2 Operational Keys

| Key | File | Line | Address | Env Var |
|-----|------|------|---------|---------|
| Sponsor | `cmd/ethrex/l2/options.rs` | 44 | `0x000e73282F60E2CdE0D4FA9B323B6D54d860f330` | `SPONSOR_PRIVATE_KEY` |
| Committer | `cmd/ethrex/l2/options.rs` | 661 | `0x3D1e15a1a55578f7c920884a9943b3B35D0D885b` | `COMMITTER_PRIVATE_KEY` |
| Proof Coord | `cmd/ethrex/l2/options.rs` | 795 | `0xE25583099BA105D9ec0A67f5Ae86D90e50036425` | `PROOF_COORD_PRIVATE_KEY` |

### L1 Owner Key

| Key | File | Line | Address | Env Var |
|-----|------|------|---------|---------|
| OCP Owner | `cmd/ethrex/l2/deployer.rs` | 426 | `0x4417092b70a3e5f10dc504d0947dd256b965fc62` | `ETHREX_ON_CHAIN_PROPOSER_OWNER_PK` |

Also found in: `fixtures/keys/private_keys_l1.txt`

## On-Chain Verification Results

### L2 Addresses (Plasma mainnet, chain ID 9745)

| Address | Nonce | Balance | Status |
|---------|-------|---------|--------|
| Sponsor (`0x000e73...`) | 0 | 0 XPL | Inactive |
| Committer (`0x3D1e15...`) | 0 | 0 XPL | Inactive |
| Proof Coord (`0xE25583...`) | **1** | 0 XPL | **ACTIVE** |

**Key finding:** Proof Coord address has nonce=1, confirming the default key is actively used in production.

### L1 Address (Ethereum mainnet)

| Address | Nonce | Balance | Status |
|---------|-------|---------|--------|
| OCP Owner (`0x441709...`) | 0 | 0 ETH | Unconfirmed |

**Note:** Address has never sent a transaction on Ethereum mainnet. Could mean:
- Plasma uses different config for L1 deployment
- Ownership already transferred
- Based mode (no Timelock deployed)

## Treasury Status

| Address | Balance | Type |
|---------|---------|------|
| `0x0000...a11b004` | 5,293,895 XPL | Proxy contract (342 bytes) |
| `0x0000...a11b005` | 786,207 XPL | Proxy contract (342 bytes) |

**Total:** ~6,080,102 XPL

## Code Analysis Findings

### Timelock Configuration

From `cmd/ethrex/l2/deployer.rs` line 1145:
```rust
Value::Uint(U256::from(30)), // minDelay = 30 seconds
```

Initialization calldata:
```rust
initialize(
  30,                        // minDelay
  [committer, proof_sender], // sequencers
  0x4417092b...,             // governance (OCP Owner address)
  0x4417092b...,             // securityCouncil (SAME address!)
  OnChainProposer
)
```

**Critical:** `governance` and `securityCouncil` are the SAME address. This means:
- Single key controls both roles
- `emergencyExecute()` available (0 delay)
- No separation of duties

### Role Capabilities

| Role | Function | Delay |
|------|----------|-------|
| GOVERNANCE | `schedule()` → `execute()` | 30 seconds |
| SECURITY_COUNCIL | `emergencyExecute()` | **0 seconds (instant)** |

### EIP-7702 Delegation

Proof Coord address (`0xE25583...`) is an EIP-7702 delegated account:
```
Code: 0xef0100ef7b31f45b19ffef6f1ff5ae684b78b1a86c1c0c
Delegated to: 0xef7b31f45b19ffef6f1ff5ae684b78b1a86c1c0c
```

This is a smart contract wallet pattern — the address delegates to a contract that likely has `execute(address,uint256,bytes)` function.

## Additional Findings

### RPC Exposure

L2 RPC (`https://rpc.plasma.to`) exposes:
- `txpool_content` — pending transaction pool (front-running risk)
- `debug_traceTransaction` — internal execution traces (information leak)

### Admin Server

From code audit: Admin server has no authentication middleware. However, port 5555 was found closed on production hosts.

## Attack Scenarios

### Scenario 1: Proof Coord Exploitation (Confirmed Active)

```
1. Attacker uses Proof Coord private key
2. Submits fake proof for fabricated batch
3. Batch includes withdrawal to attacker address
4. OnChainProposer verifies proof → releases funds
```

**Prerequisites:**
- Proof verification must be bypassable
- Or proof coord has authority to skip verification

**Status:** Key confirmed active (nonce=1)

### Scenario 2: OCP Owner Exploitation (Unconfirmed)

```
1. Attacker uses OCP Owner private key
2. Calls emergencyExecute() on Timelock
3. Upgrades OnChainProposer implementation
4. New implementation sends bridge funds to attacker
```

**Prerequisites:**
- OCP Owner key must be active on Ethereum mainnet
- Timelock must be deployed with this address as owner
- emergencyExecute must be available

**Status:** Key valid but on-chain role unconfirmed (nonce=0)

### Scenario 3: Treasury Proxy Takeover

```
1. Attacker gains proxy admin access
2. Upgrades treasury implementation
3. New implementation sends funds to attacker
```

**Prerequisites:**
- Proxy admin key (`0x0000...f000`)
- Or ability to call proxy admin functions

**Status:** Proxy admin is system contract, access unclear

## Timeline

| Date | Action |
|------|--------|
| 2026-08-15 | Initial audit — discovered hardcoded keys |
| 2026-08-15 | On-chain verification — Proof Coord nonce=1 confirmed |
| 2026-08-15 | L1 verification attempted — OCP Owner nonce=0 |
| 2026-08-15 | Treasury balance check — ~6M XPL confirmed |

## Unresolved Questions

1. Is OCP Owner key active on Ethereum mainnet?
2. Is Timelock deployed with this address?
3. What is the proxy admin access control?
4. Can Proof Coord directly influence withdrawals?

## Recommendations for Plasma Team

1. **Immediate:** Rotate all hardcoded keys
2. **Immediate:** Override default keys via environment variables
3. **Short-term:** Implement key rotation mechanism
4. **Short-term:** Add multi-sig for critical operations
5. **Long-term:** Consider decentralized sequencer set

## References

- [ethrex Repository](https://github.com/PlasmaLaboratories/ethrex)
- [Plasma RPC](https://rpc.plasma.to)
- [EIP-7702 Specification](https://eips.ethereum.org/EIP-7702)
