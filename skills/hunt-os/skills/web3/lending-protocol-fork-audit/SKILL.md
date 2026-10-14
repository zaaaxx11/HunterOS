---
name: lending-protocol-fork-audit
description: "lending-fork-specific audit playbook"
---

# Lending Protocol Fork Audit

## Target Identification
- Identify upstream (Aave v3, FraxLend, Compound). DIFFS = attack surface.
- Custom contracts (not upstream) = highest priority.

## Oracle Manipulation
- latestAnswer() vs latestRoundData() inconsistency
- AaveOracle uses ONLY latestAnswer() — staleness in latestRoundData is dead code
- CustomizableOracle: owner-set price, no bounds = critical
- ERC4626Adapter: convertToAssets donation-inflatable, check require(_answer > 0)
- RatioAdapter: ratio answer unchecked for zero/negative

## Swap Adapter Arbitrary Calldata
- setSwapPath NO access control + router.call(attackerCalldata) = drain
- Missing balanceBefore delta = ALL residuals swept
- amountOutMin=0 bypasses validation
- Check siblings of known-issue adapters

## P2P Lending Inputs
- abi.decode struct: check EVERY field for missing validation
- collateralAmount=0 + duration=0 = free loan, free default
- _liquidate only pushes collateral, never pulls asset = free debt wipe
- Borrower-controlled oracle = liquidation DoS

## Deployer Config
- configData decoded NO validation → malicious oracle/maxLTV/fees
- maxLTV no upper bound → unlimited utilization

## Quick Negatives
- Merkle: standard OZ = clean
- SDK/indexer: env-var = clean
- StrategyManager: owner-self-gated = clean
- Flashloan: EVM atomicity undoes theft
