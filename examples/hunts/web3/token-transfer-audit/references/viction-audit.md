# Viction Token Transfer Audit - Session Reference

**Date:** 2026-08-16  
**Contracts:** TRC21.sol, Registration.sol, LendingRegistration.sol, TOMOXListing.sol  
**Node Code:** `/tmp/victionchain-master/tomox/`, `/tmp/victionchain-master/tomoxlending/`

## Critical Findings

### 1. MyTRC21.executeTransaction() - Arbitrary CALL Reentrancy

**File:** `contracts/tomox/contract/TRC21.sol` line 523

```solidity
function executeTransaction(uint transactionId) public {
    if (isConfirmed(transactionId)) {
        Transaction storage txn = transactions[transactionId];
        txn.executed = true;  // State update BEFORE external call
        
        if (txn.data.length == 0) {
            super._mint(txn.destination, txn.value);  // Safe: no external call
        } else {
            // CRITICAL: Arbitrary external call with full gas
            if (txn.destination.call.value(txn.value)(txn.data))
                Execution(transactionId);
            else {
                ExecutionFailure(transactionId);
                txn.executed = false;  // Reverted on failure
            }
        }
    }
}
```

**Exploit:** Attacker (multisig owner) submits transaction with data calling attacker contract. Attacker contract fallback re-enters `executeTransaction()` with same txId. Since `txn.executed = true` was set before the call, reentrancy check passes.

### 2. No SafeERC20 Usage

No contract uses `SafeERC20` library. All token interactions assume standard ERC20 return values.

## High Findings

### 3. Registration.refund() - ETH Transfer

**File:** `contracts/tomox/contract/Registration.sol` line 262

```solidity
msg.sender.transfer(amount);  // No reentrancy guard
```

**Mitigation:** State deleted before transfer, but `.transfer()` with 2300 gas can still trigger reentrancy in Solidity 0.4.24.

### 4. Registration.buyRelayer() - ETH Transfer to Seller

**File:** `contracts/tomox/contract/Registration.sol` line 301

```solidity
seller.transfer(price);  // seller is attacker-controlled
```

### 5. TOMOXListing.apply() - State After Transfer

**File:** `contracts/tomox/contract/TOMOXListing.sol` line 29

```solidity
foundation.transfer(msg.value);  // External call
_tokens.push(token);             // State update AFTER transfer
tokensState[token] = TokenState({isActive: true});
```

## Medium Findings

### 6. Hardcoded Foundation Address

**File:** `contracts/tomox/contract/TOMOXListing.sol` line 7

```solidity
address constant private foundation = 0x0000000000000000000000000000000000000068;
```

### 7. ERC20 Approve Race Condition

**File:** `contracts/tomox/contract/TRC21.sol` line 148

```solidity
function approve(address spender, uint256 value) public returns (bool) {
    _allowed[msg.sender][spender] = value;  // Direct overwrite, no race mitigation
}
```

## Node Code: Secure Pattern

The Go code in `order_processor.go` uses direct stateDB balance adjustments:

```go
func DoSettleBalance(...) error {
    // Check balances first
    newTakerInTotal, err := tradingstate.CheckAddTokenBalance(...)
    newTakerOutTotal, err := tradingstate.CheckSubTokenBalance(...)
    
    // Then apply all changes atomically
    tradingstate.SetTokenBalance(takerOrder.UserAddress, newTakerInTotal, ...)
    tradingstate.SetTokenBalance(takerOrder.UserAddress, newTakerOutTotal, ...)
    
    // No external contract calls - safe from reentrancy
}
```

## File Locations

| Contract | Path |
|----------|------|
| TRC21.sol | `/tmp/victionchain-master/contracts/tomox/contract/TRC21.sol` |
| Registration.sol | `/tmp/victionchain-master/contracts/tomox/contract/Registration.sol` |
| LendingRegistration.sol | `/tmp/victionchain-master/contracts/tomox/contract/LendingRegistration.sol` |
| TOMOXListing.sol | `/tmp/victionchain-master/contracts/tomox/contract/TOMOXListing.sol` |
| MultiSigWallet.sol | `/tmp/victionchain-master/contracts/multisigwallet/contract/MultiSigWallet.sol` |

## Search Commands Used

```bash
# Find .sol files (including embedded in Go bindings)
find /tmp/victionchain-master -path "*/contract/*.sol" -type f

# Search for transfer patterns
grep -rn '\.transfer(' contracts/
grep -rn '\.call\.value' contracts/
grep -rn 'safeTransfer' contracts/

# Search for reentrancy guards
grep -rn 'nonReentrant' contracts/
grep -rn '_locked' contracts/
```

## Full Report

See `/root/viction_token_transfer_audit.md` for the complete audit report with PoC.