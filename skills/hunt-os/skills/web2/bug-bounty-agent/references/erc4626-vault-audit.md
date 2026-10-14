# Reference: ERC-4626 Vault Reentrancy Audit

> Specific patterns for auditing ERC-4626 vaults, especially those wrapping yield-bearing
> tokens (aTokens, cTokens, stETH). Based on T3tris Finance Aave Vault audit (2026-07-23).

## Architecture Pattern

ERC-4626 vaults wrapping Aave aTokens follow this pattern:
1. User deposits underlying asset -> vault supplies to Aave -> receives aTokens
2. aTokens accrue yield continuously (balance increases)
3. Vault tracks lastVaultBalance to compute yield since last interaction
4. Yield is split: protocol fee % to accumulatedFees, rest to depositors
5. Withdrawals burn shares, withdraw from Aave, transfer to user

## Key State Variables

struct Storage {
    uint128 lastVaultBalance;      // Total aToken balance at last update (incl. fees)
    uint128 accumulatedFees;       // Fees accrued since last withdrawal
    uint64 fee;                    // Fee as fraction of 1e18 (SCALE)
    uint256[50] __gap;            // Storage gap for upgrades
}

## Reentrancy Vulnerability Patterns

### Pattern 1: _baseDeposit() - CEI Violation

Vulnerable code:
function _baseDeposit(uint256 assets, uint256 shares, address depositor, address receiver, bool asAToken) private {
    if (asAToken) {
        ATOKEN.transferFrom(depositor, address(this), assets);  // EXTERNAL CALL
    } else {
        UNDERLYING.safeTransferFrom(depositor, address(this), assets);  // EXTERNAL CALL
        AAVE_POOL.supply(address(UNDERLYING), assets, address(this), REFERRAL_CODE);  // EXTERNAL CALL
    }
    _s.lastVaultBalance = uint128(ATOKEN.balanceOf(address(this)));  // STATE UPDATE (AFTER)
    _mint(receiver, shares);
    emit Deposit(depositor, receiver, assets, shares);
}

Vulnerability: External calls (transferFrom, AAVE_POOL.supply()) occur BEFORE _s.lastVaultBalance is updated. If the external call triggers a callback (ERC-777 hook, Aave callback), the reentrant call observes stale lastVaultBalance.

Impact: Fee calculations during reentrant call use incorrect baseline, allowing fee extraction or inflation.

Fix: Update lastVaultBalance BEFORE external calls, or add nonReentrant modifier.

### Pattern 2: _baseWithdraw() - Partial CEI Violation

Vulnerable code:
function _baseWithdraw(...) private {
    _burn(owner, shares);  // STATE UPDATE (correct: before external call)
    
    if (asAToken) {
        ATOKEN.transfer(receiver, assets);  // EXTERNAL CALL
    } else {
        AAVE_POOL.withdraw(address(UNDERLYING), assets, receiver);  // EXTERNAL CALL
    }
    _s.lastVaultBalance = uint128(ATOKEN.balanceOf(address(this)));  // STATE UPDATE (AFTER)
    emit Withdraw(...);
}

Vulnerability: While shares are burned before external calls (correct), lastVaultBalance is updated AFTER the external call. Reentrant calls observe stale balance.

Impact: Less severe than deposit (shares burned first prevents share-based reentrancy), but balance-based fee calculations remain vulnerable.

### Pattern 3: withdrawFees() - CEI Violation

Vulnerable code:
function withdrawFees(address to, uint256 amount) public onlyOwner {
    _accrueYield();
    require(amount <= _s.accumulatedFees, "INSUFFICIENT_FEES");
    _s.accumulatedFees -= uint128(amount);
    ATOKEN.transfer(to, amount);  // EXTERNAL CALL
    _s.lastVaultBalance = uint128(ATOKEN.balanceOf(address(this)));  // STATE UPDATE (AFTER)
    emit FeesWithdrawn(...);
}

Vulnerability: ATOKEN.transfer(to, amount) is an external call before lastVaultBalance update. If to is a malicious contract with aToken receive hook, it can reenter.

Exploit path:
1. Attacker becomes vault owner (or compromises owner)
2. Calls withdrawFees(attackerContract, amount)
3. Attacker contract receives aTokens, immediately calls redeem() on vault
4. Vaults redeem() calls _accrueYield() which uses stale lastVaultBalance
5. Fee calculations incorrect, attacker extracts excess fees

### Pattern 4: Revenue Splitter - Cross-Function Reentrancy

Vulnerable code:
function splitRevenue(address[] calldata assets) public {
    for (uint256 i = 0; i < assets.length; i++) {
        uint256 assetBalance = IERC20(assets[i]).balanceOf(address(this));
        assetBalance--;
        uint256 accumulatedAssetBalance = _previousAccumulatedBalance[assets[i]] + assetBalance;
        _previousAccumulatedBalance[assets[i]] = accumulatedAssetBalance;  // STATE UPDATE
        
        for (uint256 j = 0; j < recipients.length; j++) {
            uint256 amountForRecipient = ...;
            _amountAlreadyTransferred[assets[i]][recipients[j].addr] += amountForRecipient;  // STATE UPDATE
            IERC20(assets[i]).safeTransfer(recipients[j].addr, amountForRecipient);  // EXTERNAL CALL
        }
    }
}

Vulnerability: External safeTransfer() inside nested loops. If a recipient reenters splitRevenue() or another function reading accumulated balances, inconsistent state observed. _previousAccumulatedBalance for asset[i+1] not yet updated when reentrancy occurs during asset[i] transfer.

Fix: Use pull-over-push pattern, or complete all state updates before any transfers.

### Pattern 5: Read-Only Reentrancy - getClaimableFees() and totalAssets()

Vulnerable code:
function getClaimableFees() public view override returns (uint256) {
    uint256 newVaultBalance = ATOKEN.balanceOf(address(this));  // READS EXTERNAL STATE
    if (newVaultBalance <= _s.lastVaultBalance) {
        return _s.accumulatedFees;
    }
    uint256 newYield = newVaultBalance - _s.lastVaultBalance;
    uint256 newFees = newYield.mulDiv(_s.fee, SCALE, MathUpgradeable.Rounding.Down);
    return _s.accumulatedFees + newFees;
}

function totalAssets() public view override returns (uint256) {
    return ATOKEN.balanceOf(address(this)) - getClaimableFees();
}

Vulnerability: These view functions read external state (ATOKEN.balanceOf) that can change during reentrant calls. If called during ongoing deposit/withdrawal, returns inconsistent data.

Impact: Downstream contracts relying on these for accounting (e.g., other vaults, aggregators) make incorrect decisions.

## Detection Checklist

When auditing an ERC-4626 vault, check for:

1. State tracking pattern: Look for lastVaultBalance, lastUpdate, accruedYield variables
2. External call ordering: Are state updates before or after transferFrom, supply, withdraw, transfer?
3. ReentrancyGuard: Is nonReentrant modifier used?
4. Callback-capable tokens: Does the vault accept ERC-777 tokens (have tokensReceived hook)?
5. View function consistency: Do totalAssets(), getClaimableFees(), convertToShares() read external state that could be stale?
6. Factory pattern: If factory deploys proxies, is implementation upgradeable? Can admin be compromised?

## Foundry PoC Template

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

import "forge-std/Test.sol";
import {ATokenVault} from "../src/ATokenVault.sol";
import {IERC20} from "@openzeppelin/token/ERC20/IERC20.sol";

/// @notice Malicious ERC-777 token with reentrancy hook
contract MaliciousERC777 is IERC20 {
    ATokenVault public immutable VAULT;
    bool public attacked;
    
    constructor(address vault) {
        VAULT = ATokenVault(vault);
    }
    
    function transfer(address to, uint256 amount) external returns (bool) {
        if (!attacked && to == address(VAULT)) {
            attacked = true;
            VAULT.deposit(amount, address(this));
        }
        return true;
    }
}

/// @notice Reentrancy PoC
contract ReentrancyPoC is Test {
    function test_ReentrancyDuringDeposit() external {
        // 1. Deploy malicious token
        // 2. Deploy vault with malicious token as underlying
        // 3. Attacker calls deposit()
        // 4. Token transferFrom triggers hook
        // 5. Vault processes with stale lastVaultBalance
        // 6. Assert: fee calculations are incorrect
    }
}

## Remediation

1. Add ReentrancyGuard:
import {ReentrancyGuard} from "@openzeppelin/security/ReentrancyGuard.sol";

contract ATokenVault is ..., ReentrancyGuard {
    function _baseDeposit(...) private nonReentrant { ... }
    function _baseWithdraw(...) private nonReentrant { ... }
    function withdrawFees(...) public onlyOwner nonReentrant { ... }
}

2. Fix CEI ordering: Update ALL state variables BEFORE external calls.

3. Use pull-over-push: For revenue splitting, let recipients claim rather than pushing tokens.

## Real-World Examples

- T3tris Finance Aave Vault (2026): Multiple CEI violations in _baseDeposit, _baseWithdraw, withdrawFees. No ReentrancyGuard. ~$11.5M TVL at time of audit.
- Rari Capital Fuse (2022): Cross-function reentrancy via claimCollateral - $80M exploit.
- Cream Finance (2021): Reentrancy in liquidateBorrow - $130M exploit.

## Related References

- references/web3.md - General Web3 vulnerability classes
- references/verification-and-poc.md - PoC principles and templates
- references/bridge-architecture.md - Cross-chain reentrancy patterns
