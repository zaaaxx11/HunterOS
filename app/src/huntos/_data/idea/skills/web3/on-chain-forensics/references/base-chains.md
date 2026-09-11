# Base Chain Specific Notes for On-Chain Forensics

## Base Chain Info
- **Chain ID**: 8453 (0x2107)
- **RPC**: https://mainnet.base.org / https://base.llamarpc.com / https://base.llamarpc.com
- **Explorer**: https://basescan.org / https://base.blockscout.com
- **USDC**: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 (6 decimals)
- **WETH**: 0x4200000000000000000000000000000000000006
- **Native**: ETH (18 decimals)

## BaseScan API
- **V1 (Deprecated)**: `https://api.basescan.org/api` - requires API key
- **V2 (Etherscan V2)**: `https://api.etherscan.io/v2/api?chainid=8453` - requires paid plan for full coverage
- **Web Search**: `https://basescan.org/search?q=<query>` - blocks automated, use with proper headers

### Working Endpoints (V1 - limited)
```bash
# Get contract source (if verified)
https://api.basescan.org/api?module=contract&action=getsourcecode&address=0x...&apikey=YOUR_KEY

# Get contract creation
https://api.basescan.org/api?module=contract&action=getcontractcreation&contractaddresses=0x...&apikey=YOUR_KEY

# Token holders (limited)
https://api.basescan.org/api?module=token&action=tokenholderlist&contractaddress=0x...&apikey=YOUR_KEY
```

### Web Scraping (blocked by Cloudflare)
```bash
# Search contracts
https://basescan.org/search?q=<query>

# Contract page
https://basescan.org/address/0x...
```

### Base RPC Methods
```bash
# Latest block
curl -X POST $RPC -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Block with full txs
curl -X POST $RPC -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["0x...",true],"id":1}'

# Contract code
curl -X POST $RPC -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["0x...","latest"],"id":1}'

# Storage at slot
curl -X POST $RPC -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getStorageAt","params":["0x...","0x0","latest"],"id":1}'

# Token balance (USDC)
curl -X POST $RPC -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913","data":"0x70a08231000000000000000000000000<address>"},"latest"],"id":1}'
```

## Common Contract Patterns on Base

### PoolTogether V5
- **PrizePool**: Main prize logic
- **Vault**: ERC4626 yield vault
- **TwabController**: Time-weighted average balance
- **PrizeDistributor**: Prize claiming
- **RNG**: Chainlink VRF or custom

### Aave v3
- **Pool**: Main entry (supply/borrow/liquidate)
- **BToken (aToken)**: Supply receipt
- **VariableDebtToken**: Variable debt
- **StableDebtToken**: Stable debt
- **PoolConfigurator**: Risk params
- **ACLManager**: Permissions

### Common Base Contracts
- **USDC**: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
- **WETH**: 0x4200000000000000000000000000000000000006
- **cbETH**: 0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22
- **cbBTC**: 0xcbB7C0000aB88B473b1f5aFd9ef80844eeeed33B

### Useful BaseScan Queries
```bash
# Search verified contracts
https://basescan.org/search?q=prize%20pool

# Search by deployer
https://basescan.org/address/<deployer>#code

# Token holders
https://basescan.org/token/<token>#balances
```

## Common Function Selectors

### ERC20
| Function | Selector |
|----------|----------|
| `totalSupply()` | `0x18160ddd` |
| `balanceOf(address)` | `0x70a08231` |
| `transfer(address,uint256)` | `0xa9059cbb` |
| `approve(address,uint256)` | `0x095ea7b3` |
| `allowance(address,address)` | `0xdd62ed3e` |
| `transferFrom(address,address,uint256)` | `0x23b872dd` |

### ERC4626
| Function | Selector |
|----------|----------|
| `deposit(uint256,address)` | `0xd0e30db0` |
| `mint(uint256,address)` | `0x40c10f19` |
| `withdraw(uint256,address,address)` | `0x2e1a7d4d` |
| `redeem(uint256,address,address)` | `0xdb006a75` |
| `totalAssets()` | `0x...` |
| `convertToShares(uint256)` | `0x...` |
| `convertToAssets(uint256)` | `0x...` |
| `maxDeposit(address)` | `0x...` |
| `maxWithdraw(address)` | `0x...` |

### ERC4626 Vault
| Function | Selector |
|----------|----------|
| `deposit(uint256,address)` | `0xd0e30db0` |
| `mint(uint256,address)` | `0x40c10f19` |
| `withdraw(uint256,address,address)` | `0x2e1a7d4d` |
| `redeem(uint256,address,address)` | `0xdb006a75` |

### ERC4626 View
| Function | Selector |
|----------|----------|
| `totalAssets()` | `0x...` |
| `convertToShares(uint256)` | `0x...` |
| `convertToAssets(uint256)` | `0x...` |
| `maxDeposit(address)` | `0x...` |
| `maxWithdraw(address)` | `0x...` |
| `maxMint(address)` | `0x...` |
| `maxRedeem(address)` | `0x...` |
| `previewDeposit(uint256)` | `0x...` |
| `previewMint(uint256)` | `0x...` |
| `previewWithdraw(uint256)` | `0x...` |
| `previewRedeem(uint256)` | `0x...` |

### Aave v3 Pool
| Function | Selector |
|----------|----------|
| `supply()` | `0x617ba037` |
| `withdraw()` | `0x69328d70` |
| `borrow()` | `0xc5ebeaec` |
| `repay()` | `0x573ade81` |
| `liquidationCall()` | `0x4e71d92d` |
| `flashLoan()` | `0x5cffe9de` |
| `supplyWithPermit()` | `0x...` |

### PoolTogether V5
| Function | Selector |
|----------|----------|
| `awardPrizes()` | `0x...` |
| `claimPrizes()` | `0x...` |
| `deposit()` | `0xd0e30db0` |
| `withdraw()` | `0x2e1a7d4d` |
| `depositRewards()` | `0x...` |

### ERC4626 View
| Function | Selector |
|----------|----------|
| `totalAssets()` | `0x...` |
| `convertToShares()` | `0x...` |
| `convertToAssets()` | `0x...` |
| `previewDeposit()` | `0x...` |
| `previewMint()` | `0x...` |
| `previewWithdraw()` | `0x...` |
| `previewRedeem()` | `0x...` |
| `maxDeposit()` | `0x...` |
| `maxWithdraw()` | `0x...` |
| `maxMint()` | `0x...` |
| `maxRedeem()` | `0x...` |

## Useful RPC Calls for Forensics

### Find Contract Deployer
```bash
# Get block with txs
eth_getBlockByNumber [latest, true]

# Filter to == '' (contract creation)
# from = deployer
# input = init code
```

### Trace USDC Flow
```bash
# Check USDC transfers in recent blocks
for block in $(seq $LATEST -20 $LATEST); do
  eth_getBlockByNumber [block, true]
  # Filter input == 0xa9059cbb (transfer)
  # to = recipient
  # value = amount
done
```

### Check Contract Storage
```bash
# EIP-1967 slots
# Admin: 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
# Implementation: 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
# Beacon: 0xa3f0ad74e5423aebfd80d8ef4348199e7f4c9a60464e80606c4b5a4c5e3a4e8c
```

### Proxy Detection
```bash
# Check if proxy
# 1. Code size < 100 bytes = likely proxy
# 2. Has fallback() / delegatecall
# 3. Check EIP-1967 slots
```

## Quick Forensics Commands

```bash
# 1. Find contract with USDC balance > $100k
# (requires indexer or manual checking known vaults)

# 2. Find factory contract
# Look for create2 / create calls in recent blocks

# 3. Find deployer
# Trace contract creation tx -> from = deployer
# Check deployer's other creations

# 4. Verify proxy
eth_getStorageAt [proxy, 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc]
# = implementation address

# 5. Check admin
eth_getStorageAt [proxy, 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103]
# = admin address
```

## Useful Patterns for Recon

### Find Vault Factory
```bash
# Search for create2 calls in recent blocks
# Factory typically deploys: new Vault{salt: ...}(args)
# Check tx.input for create2 pattern: 0x...ff...
```

### Find Prize Pool
```bash
# Look for Chainlink VRF calls
# fulfillRandomWords(requestId, randomWords)
# Check VRF coordinator address
```

### Find Admin/Upgrader
```bash
# Check proxy admin slot
# Check for onlyOwner / onlyAdmin modifiers
# Check timelock contract
```

## Useful Addresses on Base
| Name | Address |
|------|---------|
| USDC | 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 |
| WETH | 0x4200000000000000000000000000000000000006 |
| cbETH | 0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22 |
| cbBTC | 0xcbB7C0000aB88B473b1f5aFd9ef80844eeeed33B |
| Chainlink VRF | 0x... (check BaseScan) |
| Base Bridge | 0x... |
| L2OutputOracle | 0x... |

## Quick Recon Checklist
- [ ] DeFiLlama: protocol, TVL, chains
- [ ] GitHub: contracts repo, deploy scripts
- [ ] BaseScan: verified contracts, proxy impl, admin
- [ ] Twitter/Discord: team, deployer, audit
- [ ] RPC: latest block, recent contract creations
- [ ] USDC: large holders = potential vaults
- [ ] Deployer: other contracts by same deployer