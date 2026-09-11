# Yuzu Money Vault System — On-Chain Forensics & Contract Discovery

**Target Contracts:**
- yzSyrup Proxy: `0xc9854f2af89d4d26837004d1e154bd3c3c1009b1`
- yzCash Proxy: `0x224e90591a2d63fb66e677d0561ea4a6ad1f098d`

**Chain:** Ethereum Mainnet (Chain ID: 1)
**Discovery Method:** Blockscout API + Direct RPC calls via cast

---

## Contract Discovery Workflow

### 1. Proxy Detection via Storage Slots

```bash
# EIP-1967 Implementation Slot
cast storage 0xc9854f2af89d4d26837004d1e154bd3c3c1009b1 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc --rpc-url https://eth.drpc.org
# Result: 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a (YuzuILPV2 implementation)

# EIP-1967 Admin Slot  
cast storage 0xc9854f2af89d4d26837004d1e154bd3c3c1009b1 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 --rpc-url https://eth.drpc.org
# Result: 0xc3e56dcbacbaa9030c2da2988652a41b8defafe6 (ProxyAdmin - Multisig)
```

**Finding:** Both yzSyrup and yzCash use TransparentUpgradeableProxy pattern with EIP-1967 slots.

### 2. Implementation Verification

```bash
cast code 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a --rpc-url https://eth.drpc.org
# Verified on Blockscout: src/YuzuILPV2.sol
```

### 3. Protocol Discovery via Blockscout Search

```bash
curl -s "https://eth.blockscout.com/api/v2/search?q=YuzuILP"
```

**Results:** 5 verified YuzuILPV2 contracts:
- `0xabafaC41890422931f4F9EB0711B69D5F8066f97`
- `0xD6fF6F417268a80182dd1B1243c9993aabE9123a` (yzCash)
- `0xd1CA62389793FC55CD3B64B09b8D8bEF5288EE9A` (yzSyrup)
- `0xfa1136bfb444EFc5E1FEeA67F6510Fe0C409933b`
- `0x2daE19680d5E9089180F7c94b768c43d90184E39`

---

## State Analysis via RPC Calls

### Key State Variables (YuzuILPV2)

```bash
# Pool Size (reported total assets including distributions)
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "poolSize()(uint256)" --rpc-url https://eth.drpc.org

# Total Assets (ERC4626 totalAssets including phantom distributions)
cast call 0xc9854f2af89d4d26837004d1e154bd3c3c1009b1 "totalAssets()(uint256)" --rpc-url https://eth.drpc.org

# Distributed Assets Since Last Update
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "distributedSinceUpdate()(uint256)" --rpc-url https://eth.drpc.org

# Net Distributed (distributed - redeemed)
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "netDistributedSinceUpdate()(uint256)" --rpc-url https://eth.drpc.org
```

### Distribution State Tracking

```bash
# Last Distribution Amount
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "lastDistributedAmount()(uint256)" --rpc-url https://eth.drpc.org

# Last Distribution Period (seconds)
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "lastDistributionPeriod()(uint256)" --rpc-url https://eth.drpc.org

# Last Distribution Timestamp
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "lastDistributionTimestamp()(uint256)" --rpc-url https://eth.drpc.org
```

### Admin Role Verification

```bash
# POOL_MANAGER_ROLE (keccak256("POOL_MANAGER_ROLE"))
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "getRoleAdmin(bytes32)(bytes32)" 0x... --rpc-url https://eth.drpc.org

# Get role members
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "getRoleMemberCount(bytes32)(uint256)" 0x... --rpc-url https://eth.drpc.org
```

---

## Cross-Protocol Exposure Analysis

### TVL Allocation via RPC (Requires Protocol Integration Addresses)

**Note:** YuzuILPV2 doesn't expose individual protocol positions on-chain. Must trace via:
1. `updatePool()` events to infer position changes
2. Off-chain admin disclosures
3. Protocol-specific vault addresses (if published)

**Risk:** No on-chain visibility into Aave/Morpho/Euler/Fluid allocation → impossible to verify `poolSize` matches actual collateral.

### Protocol Health Monitoring (Missing On-Chain)

```bash
# Missing: No on-chain health factor for individual protocol positions
# Missing: No oracle for protocol pause/hack status
# Missing: No automatic rebalance triggers
```

---

## Upgradeability Verification

### Proxy Admin Chain

```bash
# 1. Proxy admin (EIP-1967 admin slot)
cast storage 0xc9854f2af89d4d26837004d1e154bd3c3c1009b1 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103

# 2. ProxyAdmin owner
cast call 0xc3e56dcbacbaa9030c2da2988652a41b8defafe6 "owner()(address)" --rpc-url https://eth.drpc.org

# 3. If owner is contract, check if it's a proxy
cast code <owner> --rpc-url https://eth.drpc.org
# 4. If proxy, read slot 0 of that proxy for implementation
# 5. Call owner() on implementation
```

**Finding:** Both yzSyrup and yzCash admin are multisigs (not timelocks). No upgrade delay.

### Storage Gap Analysis

```bash
# Check for storage gaps in implementation
# YuzuILPV2 has: uint256[47] private __gap;
# Base contracts (YuzuILP, YuzuProto, YuzuProtoV2, YuzuOrderBook, YuzuIssuer) need verification
```

---

## Verification Commands Summary

```bash
#!/bin/bash
# Yuzu Money Vault Forensics Quick Check

RPC="https://eth.drpc.org"

echo "=== yzSyrup ==="
cast call 0xc9854f2af89d4d26837004d1e154bd3c3c1009b1 "totalAssets()(uint256)" --rpc-url $RPC
cast storage 0xc9854f2af89d4d26837004d1e154bd3c3c1009b1 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc --rpc-url $RPC
cast storage 0xc9854f2af89d4d26837004d1e154bd3c3c1009b1 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 --rpc-url $RPC

echo "=== yzCash ==="
cast call 0x224e90591a2d63fb66e677d0561ea4a6ad1f098d "totalAssets()(uint256)" --rpc-url $RPC
cast storage 0x224e90591a2d63fb66e677d0561ea4a6ad1f098d 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc --rpc-url $RPC
cast storage 0x224e90591a2d63fb66e677d0561ea4a6ad1f098d 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 --rpc-url $RPC

echo "=== Implementation (YuzuILPV2) ==="
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "poolSize()(uint256)" --rpc-url $RPC
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "distributedSinceUpdate()(uint256)" --rpc-url $RPC
cast call 0xd1ca62389793fc55cd3b64b09b8d8bef5288ee9a "netDistributedSinceUpdate()(uint256)" --rpc-url $RPC
```

---

## Key Forensic Findings

| Finding | Evidence | Severity |
|---------|----------|----------|
| Proxy uses EIP-1967 standard | Admin slot `0xb531...`, Impl slot `0x3608...` | Info |
| Admin is Multisig (no timelock) | `owner()` on ProxyAdmin returns multisig | 🔴 CRITICAL |
| 5 verified YuzuILPV2 contracts | Blockscout search | Info |
| No on-chain protocol positions | `_totalAssets()` uses `poolSize` + distributions | 🔴 CRITICAL |
| Distribution state trackable | `lastDistributedAmount`, `lastDistributionPeriod`, `lastDistributionTimestamp` | Info |
| Storage gap in V2 only | `uint256[47] __gap` in YuzuILPV2; base contracts unknown | 🟡 MEDIUM |

---

## Methodology Notes

1. **Always verify proxy admin chain fully** — empty EIP-1967 admin slot ≠ safe; check AccessControl roles, custom storage slots 0-50
2. **Cross-reference Blockscout with direct RPC** — fork state may differ from live
3. **Trace protocol integrations off-chain** — on-chain state insufficient for multi-protocol vaults
4. **Check `reinitialize()` protection** — V2 `reinitializer(2)` requires V1 `initializer` gap verification
5. **Monitor `updatePool()` events** — only on-chain signal for poolSize changes