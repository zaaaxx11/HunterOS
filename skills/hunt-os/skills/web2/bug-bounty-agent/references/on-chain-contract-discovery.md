# On-Chain Contract Discovery Methodology

When protocols are closed-source, undocumented, or have no public repos, you must find and analyze contracts purely on-chain.

---

## Phase 1: Identify Candidate Addresses

### From Protocol TVL / DefiLlama
```bash
# Get protocol chains & TVL
curl "https://api.llama.fi/protocol/<protocol-name>"
# Look for chain list, then query each chain
```

### From User Transactions (Etherscan/Blockscan API)
```bash
# Get recent txs to a known address (e.g., deposit function)
cast tx-list --address <user> --chain base
# Look for contract interactions with high TVL protocols
```

### From Known Factory Patterns
- **ERC4626 Vaults**: Check `0x...` factory deployments
- **PoolTogether V5**: PrizePool factory at known addresses
- **Aave V3**: PoolAddressesProvider at known address
- **Morpho Blue**: MarketFactory at known address

### From Contract Creation Traces
```bash
# Trace deployer transactions
cast tx <deploy_tx_hash> --rpc-url <rpc>
# Look for CREATE/CREATE2 in traces
```

---

## Phase 2: Verify & Classify Contracts

### Storage Layout Analysis
```bash
# ERC1967 proxy slots
cast storage <addr> 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc  # implementation
cast storage <addr> 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103  # admin
cast storage <addr> 0x0  # owner (common in Ownable)

# ERC4626 vault
cast storage <vault> 0x0  # asset
cast storage <vault> 0x1  # totalAssets
cast storage <vault> 0x2  # totalSupply
```

### Function Selector Extraction
```bash
# Get bytecode
cast code <addr> --rpc-url <rpc>

# Search for known selectors
# balanceOf: 0x70a08231
# totalSupply: 0x18160ddd
# deposit: 0x47e7ef24
# withdraw: 0x69328dec
# supply: 0x47e7ef24 (Aave)
# borrow: 0xc5ebeaec (Aave)
# liquidationCall: 0x9b5d8c8e (Aave)
```

### Proxy Pattern Detection
```bash
# EIP-1967 (standard proxy)
cast storage <addr> 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc  # impl
cast storage <addr> 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103  # admin

# EIP-1822 (UUPS)
cast storage <addr> 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc  # impl

# EIP-1822 / ERC1822 (UUPS with beacon)
cast storage <addr> 0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50  # beacon
```

---

## Phase 3: Build Contract Map

### Create Protocol Map
```
Protocol: <name>
Chain: <chain> (Chain ID: <id>)
RPC: <rpc_url>

Contracts:
├── VaultFactory: 0x...
│   ├── Vault #1: 0x... (asset: USDC)
│   ├── Vault #2: 0x... (asset: WETH)
├── PrizePool: 0x... (impl: 0x...)
├── YieldAdapter_Aave: 0x...
├── YieldAdapter_Compound: 0x...
├── RNGProvider: 0x... (Chainlink VRF / custom)
├── PrizeDistributor: 0x...
└── Treasury: 0x...

Deployer: 0x... (tx: 0x...)
Deploy Block: <block_num>
```

---

## Phase 4: Fork & Test

### Foundry Fork Test Template
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";

contract ProtocolAudit is Test {
    address constant RPC = "https://mainnet.base.org";
    uint256 constant FORK_BLOCK = 49026128; // recent
    
    address constant VAULT = 0x...;
    address constant PRIZE_POOL = 0x...;
    address constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
    
    function setUp() public {
        vm.createSelectFork(RPC, FORK_BLOCK);
        // impersonate whale if needed
        // deal(USDC, address(this), 10000e6);
    }
    
    function test_Deposit() public {
        // Test deposit flow
    }
}
```

### Run Fork Test
```bash
forge test --fork-url https://mainnet.base.org -vvv
```

---

## Phase 5: Decompile & Analyze (If Unverified)

### Heimdall / Panoramix / EtherVM
```bash
# Download bytecode
cast code <addr> --rpc-url <rpc> > contract.bin

# Decompile
heimdall decompile contract.bin -o ./decompiled
# or
panoramix decompile contract.bin -o ./decompiled
```

### Storage Slot Mapping
```bash
# Map all storage slots
for i in {0..100}; do
  slot=$(printf "0x%064x" $i)
  val=$(cast storage <addr> $slot --rpc-url <rpc>)
  echo "$slot: $val"
done
```

---

## Phase 6: Automated Discovery Scripts

### Base Chain Contract Finder
```bash
#!/bin/bash
# find_ample.sh - Find Ample contracts on Base

RPC="https://mainnet.base.org"
AMOUNT=1000000000000000000  # 1 USDC

# Known Ample deployer (if known)
DEPLOYER="0x..."

# Search for contracts created by deployer
cast rpc --rpc-url $RPC debug_traceBlockByNumber 0x... --type json | jq ...
```

### Automated Function Finder
```python
#!/usr/bin/env python3
# find_functions.py - Find function selectors in bytecode

import sys
selectors = {
    '0x70a08231': 'balanceOf(address)',
    '0x18160ddd': 'totalSupply()',
    '0x47e7ef24': 'deposit(uint256,address)',
    '0x69328dec': 'withdraw(uint256,address,address)',
    '0x47e7ef24': 'deposit(uint256,address)',  # Aave supply
    '0xc5ebeaec': 'borrow(uint256,uint256,uint16,address,uint16)',
    '0x9b5d8c8e': 'liquidationCall(...)',
    '0x4ce38b5f': 'claimPrize(uint256,address)',
    '0x...': 'awardPrize(...)',
}

def find_in_bytecode(bytecode):
    found = {}
    for sel, name in selectors.items():
        if sel.lower() in bytecode.lower():
            found[sel] = name
    return found

if __name__ == '__main__':
    import json
    with open(sys.argv[1]) as f:
        bytecode = f.read().strip()
    found = find_in_bytecode(bytecode)
    print(json.dumps(found, indent=2))
```

---

## Red Flags During Discovery

| Flag | Meaning |
|------|---------|
| No verified contracts on any chain | Closed source / high risk |
| Single deployer, no timelock | Centralized control |
| `selfdestruct` in bytecode | Funds can be drained |
| `delegatecall` to untrusted address | Arbitrary code execution |
| No events for critical actions | Unauditable |
| Single oracle, no TWAP | Oracle manipulation |
| `block.timestamp` for randomness | Manipulable |

---

## When to Walk Away

1. **No contracts found after 2 hours of systematic search**
2. **Team unresponsive to disclosure attempts**
3. **TVL < $10K** (not worth effort)
4. **Contracts have `selfdestruct` or upgradeable with no timelock**
5. **Entire protocol behind multisig with unknown signers**

---

## Quick Commands Cheat Sheet

```bash
# Get bytecode
cast code 0x... --rpc-url https://mainnet.base.org

# Get storage
cast storage 0x... 0x0 --rpc-url https://mainnet.base.org

# Get tx details
cast tx 0x... --rpc-url https://mainnet.base.org

# Get logs
cast logs --address 0x... --from-block 1000000 --to-block latest --rpc-url https://mainnet.base.org

# Trace transaction
cast rpc debug_traceTransaction 0x... --rpc-url https://mainnet.base.org

# Fork test
forge test --fork-url https://mainnet.base.org --fork-block-number 49026128 -vvv
```