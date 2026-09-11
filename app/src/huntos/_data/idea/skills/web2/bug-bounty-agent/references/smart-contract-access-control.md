# Smart Contract Access Control Testing Methodology

**Date:** 2026-07-25  
**Type:** On-chain verification methodology  
**Severity:** Critical — false positives/negatives can waste hours or miss critical bugs

---

## Core Principle

**Never trust `eth_call` without explicit `from`.** The default `msg.sender = 0x0` creates false positives when owner/guardian = `0x0` and false negatives when testing from attacker.

---

## Verification Methodology

### Phase 1: State Verification (Before Testing)

```bash
# 1. Check current owner/guardian/admin
cast call $CONTRACT "owner()" --rpc-url $RPC
cast call $CONTRACT "guardian()" --rpc-url $RPC
cast call $CONTRACT "admin()" --rpc-url $RPC
cast call $CONTRACT "pauseGuardian()" --rpc-url $RPC

# 2. Check storage directly
cast storage $CONTRACT 0 --rpc-url $RPC  # Owner slot (ERC1967)
cast storage $CONTRACT 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 --rpc-url $RPC  # ERC1967 admin

# 3. Check if contract has owner functions
cast call $CONTRACT "transferOwnership(address)" 0x0000000000000000000000000000000000000000 --rpc-url $RPC
cast call $CONTRACT "renounceOwnership()" --rpc-url $RPC
```

**Decision Matrix:**
| Owner/Guardian | Test Strategy |
|----------------|---------------|
| `0x0` (zero) | Test from `0x0` (should succeed) + from attacker (should revert) |
| EOA/Contract | Test from attacker (should revert) + from owner (should succeed) |
| Multiple roles | Test each role from appropriate address |

---

### Phase 2: Access Control Testing

#### Test Matrix for Every Owner Function

| Function | Test from Owner | Test from Attacker | Test from 0x0 |
|----------|-----------------|-------------------|---------------|
| `transferOwnership(addr)` | ✅ Success | ❌ Revert | Depends on owner |
| `renounceOwnership()` | ✅ Success | ❌ Revert | ❌ Revert |
| `pause()` | ✅ Success | ❌ Revert | Depends |
| `unpause()` | ✅ Success | ❌ Revert | Depends |
| `setFee(uint)` | ✅ Success | ❌ Revert | Depends |
| `upgradeTo(addr)` | ✅ Success | ❌ Revert | Depends |

#### Correct Testing Commands

```bash
# ALWAYS specify from when testing access control
ATTACKER=0xDeadBeefDeadBeefDeadBeefDeadBeefDeadBeefDeadBeef
OWNER=$(cast call $CONTRACT "owner()" --rpc-url $RPC)

# Test from attacker (should revert)
cast call $CONTRACT "transferOwnership(address)" $ATTACKER \
  --from $ATTACKER --rpc-url $RPC

# Test from owner (should succeed)
cast call $CONTRACT "transferOwnership(address)" $ATTACKER \
  --from $OWNER --rpc-url $RPC

# If owner is 0x0, test from 0x0
cast call $CONTRACT "transferOwnership(address)" $ATTACKER \
  --from 0x0000000000000000000000000000000000000000 --rpc-url $RPC
```

```bash
# Using curl (for non-cast environments)
ATTACKER=0xDeadBeefDeadBeefDeadBeefDeadBeefDeadBeefDeadBeef
DATA=0xf2fde38b000000000000000000000000${ATTACKER#0x}

# From attacker (correct test)
curl -X POST $RPC -H "Content-Type: application/json" -d "{
  \"jsonrpc\":\"2.0\",\"method\":\"eth_call\",\"params\":[{
    \"to\":\"$CONTRACT\",\"from\":\"$ATTACKER\",\"data\":\"$DATA\"},\"latest\"],\"id\":1}"

# From 0x0 (false positive if owner=0x0)
curl -X POST $RPC -H "Content-Type: application/json" -d "{
  \"jsonrpc\":\"2.0\",\"method\":\"eth_call\",\"params\":[{
    \"to\":\"$CONTRACT\",\"from\":\"0x0000000000000000000000000000000000000000\",\"data\":\"$DATA\"},\"latest\"],\"id\":1}"
```

---

### Phase 3: Error Decoding

When access-controlled functions revert, decode the error:

```bash
# Get revert data
cast call $CONTRACT "transferOwnership(address)" $ATTACKER --from $ATTACKER --rpc-url $RPC
# Returns: 0x118cdaa7000000000000000000000000deadbeef...

# Decode error selector
ERROR_SELECTOR=0x118cdaa7  # OwnableUnauthorizedAccount(address)
cast 4byte-decode $ERROR_SELECTOR
# Or manually: 0x118cdaa7 = OwnableUnauthorizedAccount(address)
```

Common error selectors:
| Selector | Error | Contract |
|----------|-------|----------|
| `0x118cdaa7` | `OwnableUnauthorizedAccount(address)` | OpenZeppelin Ownable |
| `0x82b42900` | `AccessControlUnauthorizedAccount(address,bytes32)` | OZ AccessControl |
| `0x3f4ba83a` | `EnforcedPause()` | OZ Pausable |
| `0x5c975f63` | `Paused()` | Custom pause |
| `0x4e487b71` | `AccessControlBadConfirmation()` | OZ AccessControl |

---

## False Positive Detection Checklist

When a function appears to succeed without access control:

- [ ] **Did I specify `from` explicitly?** If not → FALSE POSITIVE
- [ ] **What is the owner/guardian address?** If `0x0` → HIGH RISK of false positive
- [ ] **Does it revert with explicit `from=attacker`?** If yes → Access control WORKS
- [ ] **Does it succeed from `from=0x0`?** If yes AND owner=0x0 → Access control WORKS
- [ ] **Decoded revert data** matches `OwnableUnauthorizedAccount` or similar

---

## Foundry Test Template

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {IOwnable} from "@openzeppelin/contracts/access/IOwnable.sol";

contract AccessControlTest is Test {
    address constant TARGET = 0x...;
    address constant ATTACKER = 0xDeadBeefDeadBeefDeadBeefDeadBeefDeadBeefDeadBeef;
    
    IOwnable target;
    
    function setUp() public {
        target = IOwnable(TARGET);
    }
    
    function test_OwnerIsZero() public {
        // Verify initial state
        assertEq(target.owner(), address(0), "Owner should be 0x0");
    }
    
    function test_TransferOwnership_FromAttacker_Reverts() public {
        vm.prank(ATTACKER);
        vm.expectRevert(
            abi.encodeWithSelector(IOwnable.OwnableUnauthorizedAccount.selector, ATTACKER)
        );
        target.transferOwnership(ATTACKER);
    }
    
    function test_TransferOwnership_FromZeroAddress_Succeeds() public {
        // When owner is 0x0, only 0x0 can call
        vm.prank(address(0));
        target.transferOwnership(ATTACKER);
        
        assertEq(target.owner(), ATTACKER);
    }
    
    function test_TransferOwnership_FromOwner_Succeeds() public {
        // First become owner from 0x0
        vm.prank(address(0));
        target.transferOwnership(ATTACKER);
        
        // Now attacker is owner, can transfer
        vm.prank(ATTACKER);
        target.transferOwnership(address(this));
        
        assertEq(target.owner(), address(this));
    }
}
```

---

## Common Contract Patterns

### Pattern 1: Renounced Ownership (Owner = 0x0)
- **Test**: Only `0x0` can call owner functions
- **Risk**: Anyone can test from `0x0` → false positive if not careful
- **Mitigation**: Always test from non-zero attacker address

### Pattern 2: EOA Owner with Low Balance
- **Test**: Verify owner is EOA, check balance
- **Risk**: Low ETH balance = compromised key likely
- **Action**: Report as SPOF (Single Point of Failure)

### Pattern 3: UUPS Proxy (Implementation Controls Upgrade)
```bash
# Check ERC1967 admin slot
cast storage $PROXY 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 --rpc-url $RPC
# If 0x0 → UUPS (implementation controls upgrade)
```

### Pattern 4: AccessControl (Roles)
```bash
# Check role holders
cast call $CONTRACT "getRoleAdmin(bytes32)" $(cast keccak "DEFAULT_ADMIN_ROLE") --rpc-url $RPC
cast call $CONTRACT "getRoleMemberCount(bytes32)" $(cast keccak "PAUSER_ROLE") --rpc-url $RPC
cast call $CONTRACT "getRoleMember(bytes32,uint256)" $(cast keccak "PAUSER_ROLE") 0 --rpc-url $RPC
```

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| No `from` in `eth_call` | False positive when owner=0x0 | Always specify `--from` |
| Testing only from attacker | Misses 0x0 owner edge case | Test from 0x0 AND attacker |
| Not decoding revert | Can't distinguish auth failure vs other | Decode error selector |
| Assuming 403 = protected | 403 may be WAF, not contract | Verify with storage read |
| Single test per function | Misses role-based access | Test all role combinations |

---

## T3tris Case Study

**Contract:** `0x0000000000d42633987b6ca188ec6d72dfadabef` (Protocol Token on Arbitrum)  
**Owner:** `0x0` (renounced)  
**Initial Finding:** `transferOwnership()` appeared to succeed from attacker  
**Root Cause:** `eth_call` without `from` → `msg.sender = 0x0 = owner`  
**Correction:** With explicit `from=attacker` → reverted with `OwnableUnauthorizedAccount`  
**Impact:** NO vulnerability — access control working correctly  
**TVL:** $0 (pre-launch) → No economic impact regardless  

**Lesson:** Always verify with explicit `from`. Pre-launch protocols with $0 TVL are not bug bounty targets.

---

## Quick Reference Card

```bash
# 1. Get owner
OWNER=$(cast call $CONTRACT "owner()" --rpc-url $RPC)

# 2. Test from attacker (REAL TEST)
cast call $CONTRACT "transferOwnership(address)" 0xDeadBeef... \
  --from 0xDeadBeef... --rpc-url $RPC

# 3. Test from owner (should succeed)
cast call $CONTRACT "transferOwnership(address)" 0xDeadBeef... \
  --from $OWNER --rpc-url $RPC

# 4. If owner=0x0, test from 0x0 (should succeed)
cast call $CONTRACT "transferOwnership(address)" 0xDeadBeef... \
  --from 0x0000000000000000000000000000000000000000 --rpc-url $RPC

# 5. If owner=EOA with balance < 0.1 ETH → Report SPOF
BALANCE=$(cast balance $OWNER --rpc-url $RPC)
```

---

## Related References
- `references/pre-launch-detection.md` — Verify TVL before deep audit
- `references/unverified-contract-audit.md` — Bytecode analysis for access control
- `references/closed-source-contract-audit.md` — On-chain forensics for access control
- `references/erc4626-vault-audit.md` — Vault-specific access control patterns
- `examples/hunts/recon/predator-recon/t3tris-finance-case-study.md` — Full case study with this false positive