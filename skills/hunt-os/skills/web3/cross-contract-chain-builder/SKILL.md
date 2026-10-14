---
name: cross-contract-chain-builder
description: "build cross-contract exploit chains"
metadata:
  version: 1.0.0
  hermes:
    tags: [cross-contract, exploit-chains, chain-builder, fund-flow, handoff, security, audit]
    category: security
    related: [smart-contract-exploit-pocs, audit-verification-methodology, business-logic-invariant-hunt, defi-protocol-analysis]
---

# Cross-Contract Chain Builder

Build exploit chains from other agents' findings or independent discovery. Map all system contract interactions. Find handoff points where contract A's output becomes contract B's input. Focus on fund flow: where does money enter, where does it exit, what checks exist at each boundary. Build chains that lead to fund theft or admin takeover.

**Output:** Complete exploit chains with tx simulation steps, required preconditions, and estimated profit.

---

## CORE PRINCIPLE

> A chain is only as strong as its weakest verified link. Never trust a prior agent's handoff claim without reading the source code at the handoff point.

---

## WORKFLOW

### Phase 1: System Contract Inventory

1. **Find all system contracts** — hardcoded addresses, factory deployments, proxy implementations
2. **Read every contract's source** — entry points, state variables, modifiers, external calls
3. **Build an interaction graph** — which contract calls which, what data flows between them
4. **Identify fund boundaries** — where does value enter? where does it exit? what checks exist?

```bash
# Quick inventory
find <target> -name "*.sol" | sort
grep -rn "address constant\|HexToAddress\|0x[0-9a-fA-F]\{40\}" <target> --include="*.go" --include="*.sol"
```

### Phase 2: Fund Flow Mapping

For each contract, document:

| Field | Description |
|-------|-------------|
| **Inbound Flow** | What value enters this contract? From where? |
| **Outbound Flow** | What value leaves? To where? Under what conditions? |
| **Withdrawal Check** | What authorization/guard exists before value leaves? |
| **State Mutations** | What storage changes happen on each path? |
| **External Calls** | What other contracts does this call? With what data? |

### Phase 3: Handoff Point Identification

A **handoff point** is where contract A's state change becomes contract B's authorization input.

Common handoff patterns:

| Pattern | Example | Risk |
|---------|---------|------|
| **Identity handoff** | A sets `_owner = msg.sender` → B checks `owner == msg.sender` | Reentrancy in A can hijack B's auth |
| **Status handoff** | A sets `isActive = true` → B checks `getTokenStatus() == true` | Reentrancy can bypass status check |
| **Price handoff** | A sets `price = X` → B uses `price` for liquidation calc | Unbounded price → forced liquidation |
| **Balance handoff** | A tracks `balance[x]` → B trusts `balance[x]` | Stale balance → overdraft |
| **Capacity handoff** | A tracks `capacity[token]` → B allows operations up to capacity | Capacity manipulation → unlimited operations |

### Phase 4: Chain Construction

For each handoff point, ask:

1. **Can I control A's output?** (What privileges do I need?)
2. **Does B trust A's output without verification?** (Is there a secondary check?)
3. **What's the impact of manipulating this handoff?** (Fund theft? Admin takeover?)
4. **What's the cost to execute?** (Deposit required? Time delay? Gas?)

Build chains: `Bug A output → Bug B input → Fund extraction`

### Phase 5: Source Verification (CRITICAL)

**Never trust a prior agent's handoff claim without reading the source code.**

Common corrections discovered this session:

| Prior Claim | Actual Code | Impact |
|-------------|-------------|--------|
| MultiSigWallet uses `.delegatecall()` | Uses `.call()` — destination executes in its own storage context | Storage hijack NOT possible |
| TomoValidator.withdraw() reentrancy | State deleted BEFORE `msg.sender.transfer()` | Double-withdraw NOT possible |
| TRC21 `_changeMinFee()` is public | `_changeMinFee()` is `internal` | Post-deployment fee changes NOT possible |

**Verification checklist for each handoff:**
- [ ] Read the actual source at the handoff point
- [ ] Verify the exact function signature and visibility
- [ ] Check state mutation ordering (what happens before/after external calls)
- [ ] Verify modifier logic (what conditions are actually checked)
- [ ] Check for array vs mapping distinctions (see Pitfalls)

---

## HANDOFF PATTERNS (Deep Dive)

### Pattern 1: Identity Handoff (Reentrancy)

```solidity
// Contract A
function buyRelayer(address coinbase) public payable {
    address seller = RELAYER_LIST[coinbase]._owner;
    RELAYER_LIST[coinbase]._owner = msg.sender;  // State updated
    delete RELAYER_ON_SALE_LIST[coinbase];
    seller.transfer(price);  // ← REENTRANCY: seller fallback can call Contract B
}

// Contract B
function update(address coinbase, ...) public {
    (, address owner,,,,) = Relayer.getRelayerByCoinbase(coinbase);
    require(owner == msg.sender, "Relayer owner required");  // ← Trusts A's _owner
}
```

**Chain:** Re-enter A's `buyRelayer()` → A sets `_owner = attacker` → Attacker calls B's `update()` → B trusts `_owner` → Attacker configures B maliciously.

**Verification:** Check if `_owner` is updated before or after the external call. If before → handoff is exploitable.

### Pattern 2: Array vs Mapping Distinction

```solidity
// Contract A
mapping(address => Collateral) public COLLATERAL_LIST;  // Mapping
address[] public COLLATERALS;  // Array

function addILOCollateral(address token, ...) public {
    COLLATERAL_LIST[token] = Collateral({...});  // Sets mapping
    ILO_COLLATERALS.push(token);  // Pushes to ILO array, NOT COLLATERALS array!
}

// Contract B
function setCollateralPrice(address token, ...) public {
    if (indexOf(COLLATERALS, token)) {  // Checks ARRAY, not mapping!
        require(msg.sender == ORACLE_PRICE_FEEDER);  // Strict path
    } else {
        require(t.issuer() == msg.sender);  // Lenient path — attacker controls issuer!
    }
}
```

**Chain:** `addILOCollateral()` sets mapping but doesn't push to `COLLATERALS` array → `setCollateralPrice()` takes `else` branch → attacker (issuer) sets unbounded price.

**Verification:** Always check whether a function pushes to ALL relevant arrays, not just the mapping.

### Pattern 3: Price Handoff (Unbounded Oracle)

```solidity
// Contract A (LendingRegistration)
function setCollateralPrice(address token, address lendingToken, uint256 price) public {
    // No upper bound on price!
    COLLATERAL_LIST[token]._price[lendingToken] = Price({_price: price, ...});
}

// Contract B (Lending Engine)
function processOrderList() internal {
    uint256 liquidationPrice = collateralPrice * liquidationRate / depositRate;
    // If collateralPrice = type(uint256).max → liquidationPrice = astronomical
    // Any position is instantly liquidatable
}
```

**Chain:** Attacker sets `price = type(uint256).max` → All positions using this collateral are instantly liquidatable → Attacker liquidates and steals collateral.

**Verification:** Check if `price` parameter has any upper bound check. If not → unbounded oracle.

### Pattern 4: Selfdestruct Handoff

```solidity
// Contract A (ChequeBook)
function cash(address beneficiary, uint256 amount, ...) public {
    uint256 diff = amount - sent[beneficiary];
    if (diff <= this.balance) {
        sent[beneficiary] = amount;
        beneficiary.transfer(diff);
    } else {
        // Overdraft path
        selfdestruct(beneficiary);  // ← Kills contract, sends balance to beneficiary
    }
}
```

**Chain:** Attacker submits cheque with `amount > contract balance` → `selfdestruct(attacker)` → Contract dies → Attacker gets remaining balance → All other beneficiaries lose funds.

**Verification:** Check if `selfdestruct` is used and who the beneficiary parameter is.

---

## SOLIDITY PATTERNS THAT BREAK CHAIN ASSUMPTIONS

### 1. `.call()` vs `.delegatecall()`

| Feature | `.call()` | `.delegatecall()` |
|---------|-----------|-------------------|
| Storage context | Destination's storage | Caller's storage |
| `msg.sender` | Caller address | Preserved from original caller |
| `address(this)` | Destination address | Caller address |
| Exploit potential | Limited to destination's functions | Full storage hijack |

**Impact on chains:** If a prior analysis claims "delegatecall storage hijack" but the code uses `.call()`, the chain is broken.

### 2. State Deletion Ordering

```solidity
// SAFE: delete before transfer
delete RELAYER_LIST[coinbase];
delete RESIGN_REQUESTS[coinbase];
msg.sender.transfer(amount);  // Re-entering hits require(RESIGN_REQUESTS > 0) → REVERTS

// UNSAFE: transfer before delete
msg.sender.transfer(amount);  // Re-entering sees full state
delete RELAYER_LIST[coinbase];
delete RESIGN_REQUESTS[coinbase];
```

**Impact on chains:** If state is deleted before the external call, reentrancy into the same function reverts. But cross-function reentrancy may still be possible.

### 3. `internal` vs `public`/`external`

```solidity
function _changeMinFee(uint256 value) internal {  // internal — only callable from this contract or derived contracts
    _minFee = value;
}
```

**Impact on chains:** If a prior analysis claims "attacker can change fee post-deployment" but the function is `internal`, the chain is broken.

### 4. Array vs Mapping (Solidity Storage)

```solidity
mapping(address => uint) public balances;  // Mapping: key → value
address[] public owners;  // Array: index → value

// Checking membership:
function isOwner(address addr) public view returns (bool) {
    return owners[addr];  // ERROR: can't index array with address
}

function isOwner(address addr) public view returns (bool) {
    return owners.indexOf(addr);  // Must iterate array
}
```

**Impact on chains:** A token might be in a mapping but not in an array (or vice versa). Always check both.

### 5. Modifier Ordering

```solidity
modifier onlyWallet() {
    require(msg.sender == address(this));  // Only wallet itself can call
    _;
}
```

**Impact on chains:** If a function has `onlyWallet`, external attackers can't call it directly. But reentrancy from `.call()` can invoke wallet functions.

---

## REPORTING FORMAT

### Chain Report Structure

```markdown
## CHAIN N: [TITLE]

**Severity:** [CRITICAL/HIGH/MEDIUM/LOW]
**Entry:** [What privileges/conditions needed to start the chain]
**Impact:** [What the attacker achieves]

#### Chain Topology
[ASCII diagram of the chain steps]

#### TX Simulation Steps
[Step-by-step transaction construction with code]

#### Fund Flow
[ASCII diagram of where money moves]

#### Checks Bypassed
- ❌ [Check 1] — [why it's bypassed, source line]
- ❌ [Check 2] — [why it's bypassed, source line]

#### Estimated Profit
- **Per execution:** [amount]
- **Total attack surface:** [scope]
- **Cost to execute:** [deposit/fees/gas]
- **ROI:** [ratio]

#### Source Verification
| Claim | File:Line | Status |
|-------|-----------|--------|
| [Claim 1] | [file:line] | ✅ VERIFIED |
| [Claim 2] | [file:line] | ⚠️ CORRECTED |
```

### Handoff Matrix

| Bug A (Source) | Output | Bug B (Sink) | Input Required | Handoff Viability | Verified |
|----------------|--------|--------------|----------------|-------------------|----------|
| [Bug A] | [What A produces] | [Bug B] | [What B needs] | ✅/⚠️/❌ | ✅/❌ |

---

## PITFALLS

### 1. Trusting Prior Analysis Without Verification

**Symptom:** Building chains on another agent's findings without reading source code.

**Fix:** Always read the source at the handoff point. Verify:
- Exact function signature and visibility
- State mutation ordering
- Modifier logic
- Array vs mapping distinctions

### 2. Assuming `.delegatecall()` When It's `.call()`

**Symptom:** Claiming storage hijack when the code uses `.call()`.

**Fix:** Check the exact call pattern. `.call()` executes in destination's storage context.

### 3. Missing Array vs Mapping Distinction

**Symptom:** Assuming a token in a mapping is also in the corresponding array.

**Fix:** Check all `push()` calls. Some functions push to one array but not another.

### 4. Overlooking `internal` Visibility

**Symptom:** Claiming an attacker can call a function that's `internal`.

**Fix:** Check function visibility. `internal` functions are only callable from within the contract or derived contracts.

### 5. Ignoring State Deletion Ordering

**Symptom:** Claiming reentrancy double-withdraw when state is deleted before transfer.

**Fix:** Check if state is deleted before or after the external call. If before, same-function reentrancy reverts.

### 6. Overlooking Prerequisites

**Symptom:** Building chains that require impossible preconditions.

**Fix:** For each chain, explicitly list:
- What privileges the attacker needs
- What deposits/deadlines apply
- What on-chain state must exist
- What the total cost is

---

## INTEGRATION WITH OTHER SKILLS

| Skill | Integration Point |
|-------|-------------------|
| `audit-verification-methodology` | Apply Truth Enforcement to every handoff claim. Classify as VERIFIED/THEORETICAL/FALSE. |
| `smart-contract-exploit-pocs` | Build PoCs for each verified chain. Run to confirm. |
| `business-logic-invariant-hunt` | Identify invariants that chains violate (e.g., "collateral price should be bounded"). |
| `defi-protocol-analysis` | Understand protocol mechanics before building chains. |
| `blockchain-consensus-audit` | For consensus-level chains (randomness manipulation, validator control). |

---

## VERSION HISTORY

- **1.0.0** (2026-08-16): Initial creation from Viction cross-contract chain building session. 6 chains identified, 3 prior claims corrected via source verification. Key patterns: array vs mapping distinction, `.call()` vs `.delegatecall()`, state deletion ordering, `internal` visibility, ILO collateral path bypass.
