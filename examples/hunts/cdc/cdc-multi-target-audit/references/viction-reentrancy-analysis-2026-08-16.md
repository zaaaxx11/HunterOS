# Viction Reentrancy Analysis — Possible vs Exploitable

## Key Distinction

Reentrancy is **theoretically possible** but **not exploitable for drain** if:
1. Contract uses `.transfer()` (2300 gas stipend)
2. No CALLVALUE in bytecode
3. State updated BEFORE external call (Checks-Effects-Interactions)

## Viction Analysis

### buyRelayer()

```solidity
function buyRelayer(address coinbase) public payable {
    // ...
    RELAYER_LIST[coinbase]._owner = msg.sender;  // State updated FIRST
    delete RELAYER_ON_SALE_LIST[coinbase];
    seller.transfer(price);  // External call LAST
}
```

**Assessment:** State updated before transfer, but `.transfer()` limits reentrancy to 2300 gas. Classic drain NOT possible, but state manipulation possible.

### refund()

```solidity
function refund(address coinbase) public {
    // ...
    delete RELAYER_LIST[coinbase];  // State deleted FIRST
    delete RESIGN_REQUESTS[coinbase];
    msg.sender.transfer(amount);  // Transfer LAST
}
```

**Assessment:** State deleted before transfer. Re-entering hits `require(RESIGN_REQUESTS[coinbase] > 0)` which REVERTS. NOT exploitable for double-refund.

### TomoValidator.withdraw()

```solidity
function withdraw(uint256 _blockNumber, uint _index) public {
    uint256 cap = withdrawsState[msg.sender].caps[_blockNumber];
    delete withdrawsState[msg.sender].caps[_blockNumber];  // State deleted FIRST
    delete withdrawsState[msg.sender].blockNumbers[_index];
    msg.sender.transfer(cap);  // Transfer LAST
}
```

**Assessment:** State deleted before transfer. Re-entering hits `require(caps[_blockNumber] > 0)` which REVERTS. NOT exploitable.

## Bytecode Verification

```python
# Check for CALLVALUE usage
python3 << 'EOF'
import json

with open('/tmp/contract_code.json') as f:
    data = json.load(f)

code = data['result'][2:]  # Remove 0x

# CALLVALUE = 0x34
if '34' in code:
    print("CALLVALUE found — potential value transfer")
else:
    print("No CALLVALUE — no native token transfer via CALL")
EOF
```

## Conclusion

| Contract | Function | Reentrancy | Exploitable for Drain? |
|----------|----------|------------|------------------------|
| RelayerRegistration | buyRelayer | Yes | No (2300 gas limit) |
| RelayerRegistration | refund | Yes | No (state deleted first) |
| TomoValidator | withdraw | Yes | No (state deleted first) |
| TomoValidator | unvote | Yes | Maybe (cross-function) |

**Don't oversell reentrancy findings.** Always verify:
1. Does contract transfer native token via CALL with value?
2. Is CALLVALUE used in bytecode?
3. Is state updated before external call?
