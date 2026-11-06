# eth_call False Positives: Critical Testing Methodology

## The Problem

When testing access-controlled smart contract functions via `eth_call` (RPC), **always specify the `from` parameter explicitly**. The default `msg.sender` for `eth_call` without `from` is `0x0` (zero address).

If the contract's `owner()` returns `0x0`, calls without `from` will **appear to succeed** (return `0x` empty success) even though the function has proper `onlyOwner` access control.

## Why This Happens

```
eth_call without "from" → msg.sender = 0x0000...0000
Contract: require(msg.sender == owner()) → require(0x0 == 0x0) → TRUE
Result: Call succeeds (false positive)
```

This is NOT a vulnerability in the contract. It's an artifact of how `eth_call` simulates transactions.

## Correct Testing Methodology

### ❌ WRONG - Creates False Positives
```bash
# Missing "from" parameter
cast call 0xContract "transferOwnership(address)" 0xAttacker
# Returns: 0x (SUCCESS) - FALSE POSITIVE if owner=0x0
```

```python
# web3.py - missing from
w3.eth.call({
    "to": contract_address,
    "data": "0xf2fde38b...attacker_address"
})
# Returns: "0x" (success) - FALSE POSITIVE
```

### ✅ CORRECT - Always Specify Sender
```bash
# Explicit from address
cast call 0xContract "transferOwnership(address)" 0xAttacker --from 0xAttacker
# Returns: error if access control works
```

```python
# web3.py - with from
w3.eth.call({
    "to": contract_address,
    "from": attacker_address,  # CRITICAL
    "data": "0xf2fde38b...attacker_address"
})
# Returns: revert if access control works
```

```javascript
// Foundry test - explicit sender
vm.prank(attacker);
vm.expectRevert();
contract.transferOwnership(attacker);
```

## Real-World Case: T3tris Protocol Token (2026-07-25)

### Contract: `0x0000000000d42633987b6ca188ec6d72dfadabef`

**Initial Test (WRONG):**
```bash
cast call 0x0000000000d42633987b6ca188ec6d72dfadabef \
  "transferOwnership(address)" 0xfD5B757d5826576645985FCa79d1c5E8312d80E1
# Result: 0x (SUCCESS) - FALSE POSITIVE
```

**Correct Test (with from):**
```bash
cast call 0x0000000000d42633987b6ca188ec6d72dfadabef \
  "transferOwnership(address)" 0xfD5B757d5826576645985FCa79d1c5E8312d80E1 \
  --from 0xfD5B757d5826576645985FCa79d1c5E8312d80E1
# Result: REVERT - OwnableUnauthorizedAccount(0xfD5B...)
```

**RPC with explicit from:**
```json
{
  "jsonrpc": "2.0",
  "method": "eth_call",
  "params": [{
    "to": "0x0000000000d42633987b6ca188ec6d72dfadabef",
    "from": "0xfD5B757d5826576645985FCa79d1c5E8312d80E1",
    "data": "0xf2fde38b000000000000000000000000fd5b757d5826576645985fca79d1c5e8312d80e1"
  }, "latest"],
  "id": 1
}
```

**Result:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": 3,
    "message": "execution reverted",
    "data": "0x118cdaa7000000000000000000000000fd5b757d5826576645985fca79d1c5e8312d80e1"
  }
}
```

Error `0x118cdaa7` = `OwnableUnauthorizedAccount(address)` - **Access control IS working**.

## Functions That MUST Be Tested with Explicit `from`

| Function | Selector | Why Critical |
|----------|----------|--------------|
| `transferOwnership(address)` | `0xf2fde38b` | Full contract control |
| `renounceOwnership()` | `0x715018a6` | Permanent loss of admin |
| `pause()` / `unpause()` | `0x8456cb59` / `0x3f4ba83a` | Protocol halt |
| `setFee()` / `setFeeRecipient()` | Various | Economic manipulation |
| `withdraw()` / `emergencyWithdraw()` | Various | Fund extraction |
| `upgradeTo()` / `upgradeToAndCall()` | `0x3659cfe6` / `0x4fdf49c1` | Logic replacement |
| `setOperator()` / `setAdmin()` | Various | Access control changes |
| `setValidator()` / `setOracle()` | Various | Trust anchor changes |

## Automated Testing Checklist

```bash
#!/bin/bash
# test-access-control.sh
CONTRACT=$1
ATTACKER=$2

# List of owner-only function selectors
declare -A FUNCS=(
  ["f2fde38b"]="transferOwnership(address)"
  ["715018a6"]="renounceOwnership()"
  ["8456cb59"]="pause()"
  ["3f4ba83a"]="unpause()"
  ["3659cfe6"]="upgradeTo(address)"
  ["4fdf49c1"]="upgradeToAndCall(address,bytes)"
)

for sel in "${!FUNCS[@]}"; do
  echo "Testing ${FUNCS[$sel]}..."
  RESULT=$(cast call $CONTRACT $sel --from $ATTACKER 2>&1)
  if [[ $RESULT == *"0x"* && $RESULT != *"REVERT"* && $RESULT != *"Error"* ]]; then
    echo "  ⚠️  POTENTIAL VULN: ${FUNCS[$sel]} returned success!"
    echo "     Result: $RESULT"
  else
    echo "  ✅ Protected: ${FUNCS[$sel]} reverted"
  fi
done
```

## RPC-Level Testing (Raw JSON-RPC)

### Test Template
```json
{
  "jsonrpc": "2.0",
  "method": "eth_call",
  "params": [{
    "to": "0xCONTRACT",
    "from": "0xATTACKER",
    "data": "0xSELECTOR + PADDED_ARGS"
  }, "latest"],
  "id": 1
}
```

### Error Decoding
```bash
# Common revert selectors
0x08c379a0  # Error(string) - decode string after 0x08c379a0 + 64 bytes
0x4e487b71  # Panic(uint256) - decode panic code
0x118cdaa7  # OwnableUnauthorizedAccount(address) - decode address after 32 bytes
0xda1f7d5c  # AccessControlUnauthorizedAccount(address,bytes32) - address + role
```

## Why This Matters for Bug Bounty

| Scenario | Without `from` | With `from` | Risk |
|----------|----------------|-------------|------|
| Owner = 0x0 | ✅ SUCCESS (false) | ❌ REVERT (true) | **Critical false positive** |
| Owner = 0xABC | ❌ REVERT (true) | ❌ REVERT (true) | Correct |
| No access control | ✅ SUCCESS (true) | ✅ SUCCESS (true) | Both correct |

**Impact**: Reporting false positives wastes triager time, damages reputation, and misses real bugs because you're investigating artifacts instead of vulnerabilities.

## Best Practices

1. **ALWAYS** specify `from` in `eth_call` for access-controlled functions
2. **Test with multiple addresses**: `0x0`, attacker, legitimate user
3. **Verify owner first**: `cast call CONTRACT "owner()"` before testing
4. **Document the test**: Include the exact RPC call in reports
5. **Never report** a finding based solely on `eth_call` without `from`

## Related Files
- `references/smart-contract-testing.md` - Complete testing methodology
- `references/foundry-testing.md` - Foundry test patterns
- `references/eth-call-api.md` - RPC reference

## Version History
| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-25 | Initial: Documented T3tris false positive case |