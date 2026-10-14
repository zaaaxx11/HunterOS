# REAL-WORLD EXPLOIT CASE STUDIES
## Deep technical analysis of major hacks — Root cause code + lessons

---

### 1. EULER FINANCE — $200M (March 2023)
**Root Cause**: `donateToReserves()` + `borrow()` + precision loss + oracle manipulation

#### VULNERABLE CONTRACTS
- `EToken.sol` - lending token with `donateToReserves()`
- `EulerLens.sol` - oracle

#### ATTACK FLOW
```
1. Attacker deposits 100M DAI as collateral
2. Calls donateToReserves(100M DAI) 
   → Increases totalCash without increasing totalBorrows
   → exchangeRate = totalCash / totalBorrows SKYROCKETS
3. Borrow against inflated collateral value
   → borrow(DAI) using fake high exchangeRate
   → Gets massive loan with small collateral
4. Liquidate own position at manipulated oracle price
   → Repays debt at wrong price
   → Profits from difference
```

#### KEY CODE (EToken.sol)
```solidity
function donateToReserves(uint256 amount) external {
    // NO CHECK: amount can be ANY size
    // NO CHECK: caller must have deposited first
    totalCash += amount;  // INFLATES EXCHANGE RATE
    // totalBorrows unchanged!
}
```

#### PRECISION LOSS IN SHARE CALCULATION
```solidity
function mint(uint256 assets) external returns (uint256 shares) {
    // shares = assets * totalShares / totalAssets
    // If totalAssets inflated by donateToReserves
    // shares = 0 for small deposits!
    shares = assets * totalSupply / totalAssets;  // ROUNDS DOWN
    // Attacker: deposit 1 wei → shares = 0 → withdraw → profit
}
```

#### ORACLE MANIPULATION
- Euler used Uniswap V3 TWAP
- Attacker flashloan swapped to move price
- Liquidation used manipulated price

#### LESSONS
1. **Donations must be bounded** - max % of reserves
2. **Exchange rate manipulation** - validate `totalCash` changes
3. **Share rounding** - minimum deposit, round up for users
4. **Oracle circuit breakers** - max price change per block

---

### 2. NOMAD BRIDGE — $190M (August 2022)
**Root Cause**: Uninitialized root = `0x0` allowed any message

#### VULNERABLE CONTRACT
- `Replica.sol` - message processing

#### THE BUG
```solidity
// During initialization, root was set to 0x0 instead of proper Merkle root
bytes32 public trustedRoot = 0x0;  // SHOULD BE: keccak256(emptyTree)

// process() function:
function process(bytes calldata message) external {
    bytes32 messageHash = keccak256(message);
    
    // PROOF VERIFICATION:
    // verify(messageHash, proof, trustedRoot)
    // If trustedRoot = 0x0:
    // Empty tree has root = 0x0
    // Empty proof = valid for ANY messageHash!
    if (verify(messageHash, proof, trustedRoot)) {
        // Accept message
    }
}
```

#### EXPLOIT
```
1. Anyone could call process(anyMessage, emptyProof)
2. verify(anyHash, [], 0x0) → TRUE (empty tree matches 0x0)
3. No signature verification needed
4. 1000+ attackers drained bridge in hours
```

#### WHY IT HAPPENED
- Routine upgrade changed initialization
- `initialize()` called `setTrustedRoot(0x0)` by mistake
- No validation that root != 0x0
- No emergency pause

#### LESSONS
1. **Zero is dangerous** - `require(root != 0x0)`
2. **Upgrade testing** - test initialization on fork
3. **Invariant: `trustedRoot` must be valid Merkle root**
4. **Emergency pause** on bridge contracts

---

### 3. WORMHOLE — $325M (February 2022)
**Root Cause**: `verifySignatures` missing guardian set check

#### VULNERABLE CONTRACT
- `SolanaBridge.sol` / `EthereumBridge.sol`

#### THE BUG
```solidity
function verifySignatures(
    bytes32 messageHash,
    bytes calldata signatures,
    uint16 guardianSetIndex
) internal view returns (bool) {
    // GET GUARDIAN SET
    GuardianSet memory guardianSet = guardianSets[guardianSetIndex];
    
    // BUG: NO CHECK THAT guardianSetIndex EXISTS!
    // If guardianSetIndex = 0 and guardianSets[0] uninitialized:
    // guardianSet.keys = [] (empty array)
    // guardianSet.expirationTime = 0
    
    // VERIFY SIGNATURES
    for (uint i = 0; i < signatures.length; i++) {
        // ecrecover with guardianSet.keys[i]
        // If keys[i] = address(0), ecrecover returns address(0)
        // Attacker provides signature that recovers to address(0)!
    }
}
```

#### EXPLOIT
```
1. Attacker creates malicious VAA (Verifiable Action Approval)
2. Sets guardianSetIndex = 0 (uninitialized)
3. Creates signatures that ecrecover to address(0)
   - Sign with private key = 1 (recovers to 0x...)
   - Actually: provide malformed signature that recovers to 0x0
4. verifySignatures() sees empty guardian set
5. Empty loop = no signatures verified = returns TRUE?!
   - Actually: loop doesn't run, but returns true at end
6. Bridge accepts malicious VAA → mint 120k wETH on Ethereum
```

#### THE FIX
```solidity
function verifySignatures(...) internal view returns (bool) {
    GuardianSet memory guardianSet = guardianSets[guardianSetIndex];
    
    // ADDED:
    require(guardianSetIndex <= currentGuardianSetIndex, "invalid set");
    require(guardianSet.keys.length > 0, "empty guardian set");
    require(guardianSet.expirationTime == 0 || block.timestamp < guardianSet.expirationTime, "expired");
    
    // Must verify AT LEAST quorum signatures
    uint256 validSigs = 0;
    for (...) {
        if (verifySingle(...)) validSigs++;
    }
    require(validSigs >= QUORUM, "insufficient sigs");
}
```

#### LESSONS
1. **Always validate array bounds** - `require(index < length)`
2. **Uninitialized structs = empty arrays = dangerous**
3. **Quorum must be explicitly checked**
4. **Guardian set rotation needs timelock**

---

### 4. RONIN BRIDGE — $625M (March 2022)
**Root Cause**: 5/9 validator keys compromised (social engineering)

#### ARCHITECTURE
- 9 validators (Axie Infinity team + community)
- 5 signatures required for withdrawal
- Validators ran on same infrastructure

#### ATTACK
```
1. Attacker targeted Sky Mavis (Axie dev) employees
2. Fake LinkedIn job offer → PDF with malware
3. Malware extracted private keys from validator nodes
4. 5 validator keys compromised (out of 9)
5. Attacker signed malicious withdrawal
6. Bridge verified 5/9 signatures = VALID
7. 173,600 ETH + 25.5M USDC drained
```

#### WHY 5/9 WAS INSUFFICIENT
- All validators controlled by same entity (Sky Mavis)
- Same cloud provider, same key management
- No geographic/distribution diversity
- No hardware security modules (HSM)

#### LESSONS
1. **Validator diversity** - different entities, geographies, infra
2. **HSM required** for validator keys
3. **Social engineering** is real attack vector
4. **Multi-sig ≠ security** if keys correlated
5. **Monitor for key compromise** - anomalous signatures

---

### 5. MULTICHAIN (ANYSWAP) — $126M (July 2023)
**Root Cause**: SMPC key management failure, CEO arrested

#### ARCHITECTURE
- SMPC (Secure Multi-Party Computation) for key generation
- Keys split among nodes
- But: CEO (Zhaojun) held master key backup

#### ATTACK
```
1. CEO Zhaojun arrested by Chinese authorities
2. Authorities seized servers with SMPC nodes
3. Master key backup accessible
4. Attacker (or authorities) used key to sign withdrawals
5. $126M drained across multiple chains
4. No timelock, no multisig on withdrawals
```

#### LESSONS
1. **No single point of failure** - even in SMPC
2. **Legal/jurisdictional risk** - key holders in same country
3. **Timelock on admin functions** - 24-48h delay
3. **Decentralized governance** for emergency pause
4. **Key ceremony transparency** - verifiable DKG

---

### 6. PLATYPUS FINANCE — $8.5M (February 2023)
**Root Cause**: `emergencyWithdraw` missing access control

#### VULNERABLE CONTRACT
- `MasterPlatypusV4.sol`

#### THE BUG
```solidity
function emergencyWithdraw(uint256 pid) external {
    // MISSING: onlyOwner / onlyEmergencyAdmin
    // MISSING: check if pool is actually emergency
    
    PoolInfo memory pool = poolInfo[pid];
    IERC20(token).safeTransfer(msg.sender, pool.amount);
    pool.amount = 0;
}
```

#### EXPLOIT
```
1. Attacker calls emergencyWithdraw(poolId)
2. No access control → anyone can call
3. Drains all pool tokens to attacker
4. Repeats for multiple pools
```

#### LESSONS
1. **Emergency functions need MORE auth, not less**
2. **`onlyOwner` or `onlyRole(EMERGENCY_ADMIN)` mandatory**
3. **Emergency state should be verifiable on-chain**

---

### 7. BEANSTALK — $182M (April 2022)
**Root Cause**: Flashloan governance attack

#### ARCHITECTURE
- On-chain governance (BIP - Beanstalk Improvement Proposal)
- `executeProposal()` calls arbitrary `target.call(data)`
- Flashloan used to acquire voting power

#### ATTACK
```
1. Attacker flashloans $1B (Bean, 3CRV, etc.)
2. Deposits into Silo → gets Stalk (voting power)
3. Proposes malicious BIP: "Send all funds to attacker"
4. Votes YES with flashloaned stake
5. Waits 1 day (voting period)
6. Executes proposal → drains protocol
7. Repays flashloan
```

#### LESSONS
1. **Flashloan-resistant governance** - snapshot voting power BEFORE proposal
2. **Timelock + veto** - emergency council can cancel
3. **Quorum requirements** - % of total supply, not just voting power
4. **Proposal validation** - reject arbitrary `call` targets

---

### COMMON PATTERNS ACROSS ALL HACKS

| Pattern | Frequency | Mitigation |
|---------|-----------|------------|
| Missing access control | 6/7 | `onlyRole`, `onlyOwner`, timelock |
| Uninitialized state | 2/7 | `require(var != 0)`, constructor init |
| Oracle/price manipulation | 3/7 | TWAP, circuit breakers, multi-source |
| Flashloan abuse | 4/7 | Snapshot voting power, min deposit time |
| Precision loss | 2/7 | Round up for users, min thresholds |
| Upgrade/initialization bug | 2/7 | Test on fork, validate post-upgrade |
| Single point of failure | 3/7 | Decentralize keys, HSM, geographic diversity |

---

### AUDIT CHECKLIST FROM CASE STUDIES

```
GOVERNANCE:
[ ] Flashloan-resistant voting (snapshot before propose)
[ ] Timelock on execution (24h+)
[ ] Veto power for emergency council
[ ] Quorum = % of total supply

BRIDGES:
[ ] Root/Merkle root != 0x0 validation
[ ] Guardian set bounds checking
[ ] Quorum explicitly verified
[ ] Emergency pause (multisig)

ORACLES:
[ ] Staleness check (updatedAt)
[ ] Min/max bounds (circuit breaker)
[ ] Deviation threshold (multi-source)
[ ] TWAP window > flashloan duration

LENDING:
[ ] Exchange rate manipulation checks
[ ] Share rounding (min deposit, round up)
[ ] Donation/bound functions
[ ] Liquidation discount > manipulation cost

UPGRADES:
[ ] Storage layout gaps
[ ] Initialize() protection
[ ] Post-upgrade invariant tests
[ ] Timelock on upgradeTo()

ACCESS CONTROL:
[ ] No tx.origin
[ ] Role hierarchy non-circular
[ ] Signature nonces (EIP-712)
[ ] Emergency functions = highest auth
```