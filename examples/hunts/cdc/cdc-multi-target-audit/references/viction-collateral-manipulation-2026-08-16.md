# Viction Collateral Manipulation via Array/Mapping Mismatch

## Vulnerability

When `addILOCollateral()` pushes to `ILO_COLLATERALS` array but NOT `COLLATERALS` array, while setting `COLLATERAL_LIST[token]` mapping, `setCollateralPrice()` takes the wrong access control path.

## Source Code

```solidity
// LendingRegistration.sol

function addILOCollateral(address token, uint256 depositRate, uint256 liquidationRate, uint256 recallRate) public {
    require(t.issuer() == msg.sender);  // Only issuer check, no moderator!
    COLLATERAL_LIST[token] = Collateral({...});
    ILO_COLLATERALS.push(token);  // Pushes to ILO_COLLATERALS, NOT COLLATERALS!
}

function setCollateralPrice(address token, address quote, uint256 price) public {
    if (indexOf(COLLATERALS, token)) {  // Checks ARRAY, not mapping!
        require(msg.sender == ORACLE_PRICE_FEEDER);
    } else {
        require(t.issuer() == msg.sender);  // Attacker passes!
    }
    COLLATERAL_LIST[token]._price[quote]._price = price;  // NO PRICE CAP!
}
```

## Exploit Chain

```
1. Deploy TRC21 token (attacker = issuer)
2. List token on TOMOXListing (1000 VIC fee)
3. Call addILOCollateral() — NO MODERATOR CHECK
4. Call setCollateralPrice(type(uint256).max) — NO PRICE CAP
5. All lending positions instantly liquidatable
6. Steal victim collateral
```

## Cost & Profit

- **Cost:** ~1000 VIC (listing fee) + gas
- **Profit:** All victim collateral (potentially 100s-1000s VIC)

## Detection

```bash
# Check if COLLATERALS array is populated
grep -n "COLLATERALS.push" LendingRegistration.sol
grep -n "ILO_COLLATERALS.push" LendingRegistration.sol
```

## Mitigation

- Use mapping for `indexOf` check instead of array
- Add moderator check to `addILOCollateral()`
- Add price cap validation
