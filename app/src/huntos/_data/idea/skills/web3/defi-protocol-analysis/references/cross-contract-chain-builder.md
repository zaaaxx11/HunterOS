# Cross-Contract Exploit Chain Builder Methodology

**Source:** Viction (TomoChain) chain analysis, 2026-08-16  
**Methodology:** Systematic cross-contract exploit chain construction — handoff mapping, fund flow tracing, tx simulation

---

## Purpose

When a protocol has multiple interacting contracts, individual vulnerabilities are often low-severity in isolation but become CRITICAL when chained. This methodology finds **handoff points** where Bug A's output becomes Bug B's input, traces **fund flows** to identify withdrawal checks, and produces **tx simulation steps** for each chain.

---

## Phase 1: System Contract Interaction Map

### 1.1 Identify Hardcoded System Contracts

Many chains hardcode system contract addresses at the node level. Find them:

```bash
grep -rn "SMC\|0x[0-9a-fA-F]\{40\}" common/constants.go
# Look for: RelayerRegistrationSMC, LendingRegistrationSMC, TRC21IssuerSMC, TomoXListingSMC
```

### 1.2 Build Contract Topology

For each contract, map:
- **Inbound flow:** What funds enter, from whom, under what conditions
- **Outbound flow:** What funds leave, to whom, under what conditions
- **Withdrawal checks:** What conditions must be met to withdraw

### 1.3 Fund Flow Summary Table

| Contract | Inbound Flow | Outbound Flow | Withdrawal Check |
|----------|-------------|---------------|------------------|
| Contract A | User deposits | To Contract B | `block.number >= delay` |
| Contract B | From A + fees | To Contract C | `owner == msg.sender` |
| Contract C | From B | To attacker | `signature valid` |

---

## Phase 2: Handoff Point Discovery

### 2.1 What is a Handoff?

A handoff is where **output of Contract A becomes input to Contract B**. The output could be:
- State change (e.g., `isCandidate = true`)
- Fund transfer (e.g., VIC sent to relayer)
- Identity/ownership (e.g., `msg.sender == token.issuer()`)
- Price/data (e.g., `collateralPrice` set by issuer)

### 2.2 Handoff Matrix

For each pair of contracts (A, B), ask:
1. Does A write state that B reads?
2. Does A transfer funds that B can claim?
3. Does A grant a role/identity that B checks?
4. Does A produce data that B uses?

| Bug A (Source) | Output | Bug B (Sink) | Input Required | Viability |
|----------------|--------|--------------|----------------|-----------|
| TomoRandomize timestamp manipulation | Validator controls M2 | TomoValidator voting | Validator status | ✅ HIGH |
| TRC21Issuer capacity manipulation | Issuer controls token | LendingRegistration collateral | Token in COLLATERALS | ✅ HIGH |
| RelayerRegistration reentrancy | Attacker becomes relayer owner | LendingRegistration update() | Relayer owner address | ✅ HIGH |

### 2.3 Cross-Contract Dependency Analysis

For each contract pair, trace the exact call path:

```solidity
// LendingRegistration.sol:193-194
function update(address coinbase, ...) public {
    (, address owner,,,,) = Relayer.getRelayerByCoinbase(coinbase);
    require(owner == msg.sender, "Relayer owner required"); // ← HANDOFF: RelayerRegistration → LendingRegistration
}
```

**Handoff:** `RELAYER_LIST[coinbase]._owner` (set in Registration) → `owner` check (in LendingRegistration)

**Exploit implication:** If you can manipulate `_owner` in Registration (via reentrancy in `buyRelayer`), you can pass the `owner == msg.sender` check in LendingRegistration.

---

## Phase 3: Chain Construction

### 3.1 Chain Topology Template

For each chain, document:

```
Step 1: [Entry action]
    ↓
Step 2: [State change / fund movement]
    ↓
Step 3: [Handoff to next contract]
    ↓
Step 4: [Exploit trigger]
    ↓
Step 5: [Fund extraction]
```

### 3.2 TX Simulation Steps

For each step, provide executable tx data:

```javascript
// STEP 1: Deploy TRC21 token (attacker is issuer)
const tokenTx = {
    to: null,
    data: "0x" + trc21Bytecode + encodeParams(["MyToken", "MTK", 18, 1000000e18, 0]),
    value: 0,
    from: ATTACKER
};
// → tokenAddress = deploy(tokenTx)

// STEP 2: Add token as ILO collateral (no moderator check for issuer)
const addCollateralTx = {
    to: LENDING_REGISTRATION,
    data: encodeCall("addILOCollateral(address,uint256,uint256,uint256)", [
        tokenAddress,
        100,        // depositRate (minimum)
        101,        // liquidationRate (minimum > 100)
        102         // recallRate
    ]),
    from: ATTACKER // msg.sender == token.issuer()
};
```

### 3.3 Fund Flow Trace

For each chain, trace the complete fund path:

```
Victim Lending Position
    │
    │ collateral (e.g., VIC, USDT)
    ▼
Attacker Wallet ◄──── Liquidation payout
    │
    │ (attacker now controls victim's collateral)
    ▼
DEX Swap → ETH/VIC
```

### 3.4 Checks Bypassed

List every check that the chain circumvents:

- ❌ No moderator check on `addILOCollateral()` — only requires `msg.sender == token.issuer()`
- ❌ No upper bound on collateral price — `setCollateralPrice()` accepts any uint256
- ❌ No price oracle sanity check — lending engine trusts issuer-set price
- ❌ No timelock on price changes — immediate effect

---

## Phase 4: Chain Validation

### 4.1 Verification Checklist

For each chain, verify:
- [ ] All contracts in the chain exist at known addresses
- [ ] All function signatures match actual contract ABIs
- [ ] All handoff points are source-code verified (file:line)
- [ ] Fund flow is traceable end-to-end
- [ ] All checks bypassed are documented with file:line
- [ ] TX simulation steps are executable (or logic-only if untested)

### 4.2 Confidence Classification

| Confidence | Criteria |
|------------|----------|
| **PROVEN** | Source code verified, handoff confirmed, fund flow traceable, PoC logic complete |
| **EXPLOITABLE** | Source code verified, handoff confirmed, but requires specific conditions (e.g., live relayer) |
| **THEORETICAL** | Logic sound but not source-verified or requires unverified assumptions |
| **FALSE** | Disproven by source code or live testing |

---

## Common Chain Patterns

### Pattern 1: Identity Handoff Chain

```
Contract A grants identity X → Contract B checks identity X → Attacker manipulates identity in A → B accepts attacker
```

**Example:** RelayerRegistration `_owner` → LendingRegistration `owner == msg.sender`

### Pattern 2: Fund Flow Chain

```
Contract A holds funds → Contract B can withdraw from A → Attacker compromises B → Attacker withdraws from A
```

**Example:** ChequeBook balance → `beneficiary.transfer()` → Attacker triggers selfdestruct

### Pattern 3: Data/Price Chain

```
Contract A produces data D → Contract B uses D for calculation → Attacker manipulates D in A → B calculates wrong result → Attacker profits
```

**Example:** TRC21Issuer sets collateral price → LendingRegistration uses price for liquidation → Attacker sets max price → Mass liquidation

### Pattern 4: State Dependency Chain

```
Contract A sets state S → Contract B reads S as precondition → Attacker sets S to favorable value in A → B executes under attacker conditions
```

**Example:** TomoRandomize sets secret → TomoValidator uses for randomness → Validator controls timing → Biased validator selection

---

## Grep Anchors for Handoff Discovery

```bash
# Find cross-contract calls
grep -rn "Abstract.*\.sol\|interface.*\|\.getRelayerByCoinbase\|\.getTokenStatus\|\.issuer()" contracts/ --include="*.sol"

# Find hardcoded addresses (node-level dependencies)
grep -rn "0x[0-9a-fA-F]\{40\}" common/constants.go

# Find state reads from other contracts
grep -rn "external.*view\|external.*returns" contracts/ --include="*.sol" | grep -v "function " | head -30

# Find fund withdrawal points
grep -rn "\.transfer(\|\.call\.value\|selfdestruct\|withdraw\|refund" contracts/ --include="*.sol"

# Find access control checks (potential handoff targets)
grep -rn "require(msg\.sender == \|onlyOwner\|onlyModerator\|onlyRelayerOwner" contracts/ --include="*.sol"
```

---

## Output Format

For each chain discovered, produce:

```markdown
### CHAIN N: [DESCRIPTIVE NAME]

**Severity:** [CRITICAL/HIGH/MEDIUM/LOW]
**Entry:** [Pre-auth/Post-auth/Specific role]
**Impact:** [What the attacker achieves]

#### Chain Topology
[ASCII diagram of the chain]

#### TX Simulation Steps
[Executable tx data for each step]

#### Fund Flow
[Where money goes, who can withdraw]

#### Checks Bypassed
[List of checks circumvented with file:line]
```

---

## Related Methodologies

- **`adversarial-exploit-chains`** — General exploit chain construction (GitHub Actions, deserialization, etc.)
- **`defi-protocol-analysis`** — DeFi protocol audit patterns (lending, AMM, ERC4626)
- **`orderbook-dex-relayer-audit`** — Orderbook DEX specific patterns (this file's companion)
- **`blockchain-consensus-audit`** — Consensus protocol auditing
