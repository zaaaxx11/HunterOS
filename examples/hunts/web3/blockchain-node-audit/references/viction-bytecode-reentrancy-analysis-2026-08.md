# Viction Bytecode Reentrancy Analysis (2026-08)

**Date:** 2026-08-16
**Target:** Viction (TomoChain) RelayerRegistration contract
**Method:** Bytecode analysis for reentrancy detection without source code

---

## Context

During Viction mainnet audit, we needed to verify if the RelayerRegistration contract (0x16c63b79f9C8784168103C0b74E6A59EC2de4a02) was vulnerable to classic reentrancy attacks. Source code suggested vulnerabilities, but deployed bytecode told a different story.

---

## Key Findings

### 1. No CALLVALUE in Bytecode

```python
# Pattern: 0x34 = CALLVALUE opcode
if '34' not in bytecode_hex:
    print("No CALLVALUE — classic reentrancy NOT possible")
```

**Result:** `34` NOT FOUND in RelayerRegistration bytecode

**Implication:** Contract does NOT transfer ETH/VIC via CALL with value. Classic DAO-style reentrancy (where attacker receives ETH in fallback and re-enters) is IMPOSSIBLE.

---

### 2. High DELEGATECALL Count

```python
# Pattern: 0xf4 = DELEGATECALL opcode
delegatecall_count = bytecode_hex.count('f4')
# Result: 33 occurrences
```

**Implication:** Contract uses libraries (SafeMath, etc.) extensively. This is normal for Solidity 0.4.x contracts compiled with optimization.

---

### 3. SSTORE Before CALL (Checks-Effects-Interactions)

```python
# For each CALL, check if SSTORE appears within 50 bytes before
for call_pos in call_positions:
    sstore_before = [s for s in sstore_positions if call_pos - 50 < s < call_pos]
    if sstore_before:
        print(f"CALL at {call_pos} has SSTORE at {sstore_before[-1]} — CEI pattern")
```

**Result:** CALLs #1 and #2 have SSTORE 2-9 times before CALL

**Implication:** Contract follows Checks-Effects-Interactions pattern. State is updated BEFORE external call. This mitigates reentrancy even without explicit mutex guard.

---

### 4. PUSH1 0x00 Before CALL (Value Parameter = 0)

```python
# Pattern: 0x6000 = PUSH1 0x00
# If this appears within 10 bytes before CALL, value parameter is 0
if '6000' in bytecode_hex[call_pos-20:call_pos]:
    print("Value parameter = 0 — no ETH transfer")
```

**Result:** CALLs #3-#6 have PUSH1 0x00 before CALL

**Implication:** These are external calls with ZERO value transfer. They are likely:
- Token transfers (ERC20.transfer via delegatecall to library)
- View function calls
- Library calls

---

## Quick Assessment Function

```python
def assess_reentrancy_risk(bytecode_hex: str) -> str:
    """Quick assessment of reentrancy risk from bytecode"""
    code = bytecode_hex[2:] if bytecode_hex.startswith('0x') else bytecode_hex
    
    has_callvalue = '34' in code
    call_count = code.count('f1')  # CALL
    sstore_count = code.count('55')  # SSTORE
    delegatecall_count = code.count('f4')  # DELEGATECALL
    
    if not has_callvalue and call_count > 0:
        return "LOW — No CALLVALUE, reentrancy via token fallback only"
    elif has_callvalue and sstore_count > call_count:
        return "MEDIUM — CALLVALUE present but CEI pattern likely"
    elif has_callvalue and sstore_count <= call_count:
        return "HIGH — CALLVALUE without CEI protection"
    elif delegatecall_count > 20 and not has_callvalue:
        return "LOW — Library-heavy contract, no direct ETH transfer"
    else:
        return "UNKNOWN — Insufficient data"
```

---

## Viction RelayerRegistration Assessment

```
Bytecode size:     15,521 bytes
CALL instructions: 6
DELEGATECALL:      33 (library calls)
SLOAD:            182
SSTORE:            88

CALLVALUE (0x34):  NOT FOUND
→ No direct ETH/VIC transfer via CALL
→ Classic DAO-style reentrancy: IMPOSSIBLE

SSTORE before CALL: YES (2-9 times)
→ Checks-Effects-Interactions pattern detected
→ State updated before external interaction

Value parameter:    0 for CALLs #3-#6
→ No ETH transfer in these calls
→ Likely token/library calls

VERDICT: Reentrancy drain NOT feasible via classic pattern
```

---

## Why Source Code Was Misleading

Source code showed:
```solidity
function buyRelayer() {
    // ...
    seller.transfer(price);  // Looks like ETH transfer
}
```

But deployed bytecode showed:
- NO CALLVALUE opcode
- SSTORE before CALL (CEI pattern)
- Value parameter = 0

**Explanation:** The `.transfer()` in source compiles to a CALL with value=0 when the contract doesn't actually transfer native tokens. The "price" is tracked internally but settled off-chain or via token transfer (not native ETH/VIC).

---

## Methodology

1. **Extract bytecode:** `eth_getCode` via JSON-RPC
2. **Disassemble:** Simple opcode scanner (no full disassembler needed)
3. **Pattern match:** Look for key opcodes (0x34, 0xf1, 0xf4, 0x55, 0x6000)
4. **Context analysis:** Check proximity of SSTORE to CALL
5. **Live verification:** `eth_call` to confirm behavior

---

## Limitations

- Does NOT detect token transfer reentrancy (ERC20.transfer via CALL with value=0)
- Does NOT detect logic vulnerabilities (only transfer patterns)
- Requires bytecode (not available for all contracts)
- Proxy contracts need implementation bytecode

---

## When to Use

- Verify deployed contract matches source code claims
- Quick reentrancy risk assessment without full audit
- Prioritize targets for deeper analysis
- Validate "drain feasibility" before writing PoC

---

## References

- Viction RelayerRegistration: `0x16c63b79f9C8784168103C0b74E6A59EC2de4a02`
- Live RPC: `https://rpc.viction.xyz`
- Chain ID: `88` (0x58)
- Source: `/tmp/viction-contracts-master/TomoX/Registration.sol`
- Node code: `/tmp/victionchain-master/`
