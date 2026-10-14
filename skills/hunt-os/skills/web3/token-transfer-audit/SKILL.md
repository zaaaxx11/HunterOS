---
name: token-transfer-audit
description: "audit token transfer paths and hooks"
category: security
---

# Token Transfer Audit

Systematic audit of token transfer patterns in smart contracts. Identifies unsafe transfer calls, reentrancy vectors, ERC20 non-compliance, and callback vulnerabilities.

## When to Use

- Auditing ERC20/TRC21/BEP20 token contracts
- Reviewing contracts that handle token transfers or ETH withdrawals
- Checking for reentrancy via token callbacks or fallback functions
- Verifying safe transfer patterns in DeFi protocols
- Assessing multisig wallet execution safety

## Methodology

### Phase 1: Locate Target Contracts

Find all Solidity contracts in the codebase:

```bash
# Search for .sol files
find /path/to/repo -name "*.sol" -type f

# Also check for contracts embedded in Go bindings
find /path/to/repo -path "*/contract/*.sol" -type f
```

Many blockchain projects embed `.sol` files alongside generated Go bindings in `contract/` directories.

### Phase 2: Identify Transfer Patterns

Search for these patterns across all contracts:

```bash
# ETH transfer patterns
grep -rn '\.transfer(' contracts/
grep -rn '\.send(' contracts/
grep -rn '\.call\.value' contracts/
grep -rn '\.call\{' contracts/

# Token transfer patterns
grep -rn 'safeTransfer' contracts/
grep -rn 'safeApprove' contracts/
grep -rn 'transferFrom' contracts/
grep -rn '\.approve(' contracts/

# Reentrancy-related patterns
grep -rn 'nonReentrant' contracts/
grep -rn '_locked' contracts/
grep -rn 'function()' contracts/  # fallback functions
```

### Phase 3: Classify Transfer Types

For each transfer found, classify it:

| Type | Pattern | Risk Level |
|------|---------|------------|
| Internal balance manipulation | `_balances[from] -= amount; _balances[to] += amount` | Low (no external call) |
| ERC20 interface call | `IToken(token).transfer(to, amount)` | Medium (depends on token) |
| SafeERC20 wrapper | `token.safeTransfer(to, amount)` | Low (return value checked) |
| Raw ETH transfer | `addr.transfer(amount)` | Medium (2300 gas limit) |
| Low-level CALL | `addr.call{value: amount}("")` | High (full gas, no return check) |
| Arbitrary CALL | `addr.call.value(amount)(data)` | Critical (reentrancy + arbitrary execution) |

### Phase 4: Check for Reentrancy Guards

For each external call (`.transfer`, `.call.value`, `.send`):

1. Is there a `nonReentrant` modifier on the function?
2. Are state updates applied **before** the external call (checks-effects-interactions)?
3. Can the callee re-enter the same function or a related function?
4. Is the call target attacker-controlled?

**Critical pattern to flag:**
```solidity
// DANGEROUS: State update before arbitrary external call
txn.executed = true;
if (txn.destination.call.value(txn.value)(txn.data))  // REENTRANCY!
    Execution(transactionId);
```

### Phase 5: Verify Safe Transfer Usage

Check if the codebase uses OpenZeppelin's `SafeERC20`:

```solidity
using SafeERC20 for IERC20;

// Safe:
token.safeTransfer(to, amount);
token.safeApprove(spender, amount);

// Unsafe (no return value check):
token.transfer(to, amount);
token.approve(spender, amount);
```

**Non-standard ERC20 tokens** (e.g., USDT) don't return `bool` from `transfer()`. Direct calls revert or silently fail.

### Phase 6: Check ERC20 Approve Race Condition

Look for `approve()` calls without race condition mitigation:

```solidity
// Vulnerable:
function approve(address spender, uint256 amount) public {
    _allowed[msg.sender][spender] = amount;
}

// Mitigated:
function safeApprove(address spender, uint256 amount) public {
    require((_allowed[msg.sender][spender] == 0) || (amount == 0));
    _allowed[msg.sender][spender] = amount;
}
```

### Phase 7: Node Code Review (if applicable)

For blockchain node implementations (Go, Rust, etc.):

1. Check how token balances are settled during order matching
2. Look for external contract calls during settlement
3. Verify atomic balance updates (no external calls)

**Secure pattern:**
```go
// Direct stateDB balance adjustments - no external calls
statedb.AddBalance(user, amount)
tradingstate.SetTokenBalance(user, newBalance, token, statedb)
```

**Risky pattern:**
```go
// External contract call during matching
tokenContract.Transfer(user, amount)  // Can re-enter!
```

### Phase 8: Check for Hardcoded Addresses

Search for hardcoded addresses that receive funds:

```bash
grep -rn '0x00000000000000000000000000000000000000' contracts/
grep -rn 'constant.*address' contracts/
```

Hardcoded fee recipient addresses prevent governance updates and create single points of failure.

## Vulnerability Classes

### Critical (CVSS 9.0+)
- Reentrancy in multisig execution with arbitrary CALL
- Unprotected `.call.value()` with attacker-controlled data
- Missing safeTransfer for external token interactions
- Reentrancy enabling double-spend or fund drainage

### High (CVSS 7.0-8.9)
- Reentrancy in refund/withdrawal functions
- State updates after external calls (checks-effects-interactions violation)
- `.transfer()` to attacker-controlled addresses without guard
- Missing return value checks on token transfers

### Medium (CVSS 5.0-6.9)
- Hardcoded addresses for fee recipients
- ERC20 approve race condition not mitigated
- `.transfer()` with 2300 gas stipend (can fail on contract recipients)
- Missing event logging on fund movements

### Low (CVSS <5.0)
- Missing events on ETH deposits
- Gas optimization issues
- Style/consistency issues

## Proof of Concept Template

For reentrancy vulnerabilities, create a PoC contract:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.4.24;

interface ITarget {
    function vulnerableFunction() external;
    function withdraw() external;
}

contract ReentrancyPoC {
    ITarget public target;
    bool public attacked;
    
    constructor(address _target) public {
        target = ITarget(_target);
    }
    
    function attack() external {
        require(!attacked, "Already attacked");
        attacked = true;
        
        // Trigger the vulnerable function
        target.vulnerableFunction();
    }
    
    // Fallback for reentrancy
    function() external payable {
        if (address(target).balance > 0) {
            target.withdraw();  // Re-enter!
        }
    }
    
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
```

## Report Structure

1. **Executive Summary** - Severity distribution, key findings
2. **Transfer Patterns Analysis** - What patterns were found where
3. **Vulnerabilities Identified** - Organized by severity with CWE/CVSS
4. **Proof of Concept** - For critical/high issues
5. **Recommendations** - Prioritized remediation steps
6. **Contracts Audited** - Table with file paths, lines, patterns
7. **Methodology** - How the audit was conducted

## Tools

- `grep` / `rg` for pattern searching
- `slither` for static analysis (`slither . --detect reentrancy,erc20-index`)
- `mythril` for symbolic execution
- Manual code review with AX tree inspection

## Case Studies

- `examples/hunts/web3/token-transfer-audit/references/trias-try-simple-2026-08.md` — Trias TRYSimple.sol (sol 0.4.24): SafeMath-correct but `transfer(0)` allowed, `approve` race (front-run 100→50 drains 150), missing `_from` zero check, constructor `*10**decimals` footgun. Full live fuzz oracles + grep + fix checklist.
- `examples/hunts/web3/token-transfer-audit/references/viction-audit.md` — Viction TRC21/TomoX node audit (existing).

## Related Skills

- `defi-protocol-analysis` - Broader DeFi protocol auditing
- `smart-contract-exploit-pocs` - Building exploit proofs
- `blockchain-node-audit` - Node infrastructure security
- `reentrancy-detection` - Focused reentrancy analysis
