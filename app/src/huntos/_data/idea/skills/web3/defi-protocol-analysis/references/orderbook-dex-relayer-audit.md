# Orderbook DEX + Relayer Architecture Audit (Viction/TomoX Pattern)

**Source:** Viction (TomoChain) repo analysis, 2026-08-16  
**Architecture:** Orderbook DEX with relayer operators, built as go-ethereum fork extensions (TomoX + TomoX Lending)  
**Contract version:** Solidity 0.4.24 (pre-0.5 safety features)

---

## Architecture Overview

| Component | Layer | Description |
|-----------|-------|-------------|
| `Registration.sol` | Contract | Relayer registration, deposit management, relayer marketplace (buy/sell relayers) |
| `TOMOXListing.sol` | Contract | Token listing with 1000 TOMO deposit gate |
| `LendingRegistration.sol` | Contract | Lending relayer registration, collateral management, price feeds |
| `order_processor.go` (tomox) | Go node | Order matching engine, market/limit orders, settlement |
| `order_processor.go` (lending) | Go node | Lending order matching, liquidation price calc, trade lifecycle |
| `posv.go` | Go node | Proof-of-Stake-Voting consensus, validator set, epoch logic |

**Key difference from AMM:** Orders are stored off-chain (in node state trie), matched by relayers, settled on-chain. Relayers are permissioned operators who post deposits and earn fees.

---

## Vulnerability Patterns

### 1. Issuer-Controlled Collateral Pricing (HIGH)

**Pattern:** Lending protocols where collateral prices can be set by the token issuer rather than an oracle.

```solidity
// LendingRegistration.sol:126-146
function setCollateralPrice(address token, address lendingToken, uint256 price) public {
    // ...
    if (indexOf(COLLATERALS, token)) {
        require(msg.sender == ORACLE_PRICE_FEEDER, "Oracle Price Feeder required");
    } else {
        LAbstractTokenTRC21 t = LAbstractTokenTRC21(token);
        require(t.issuer() == msg.sender, "Required token issuer");  // ← ISSUER CONTROLS PRICE
    }
    COLLATERAL_LIST[token]._price[lendingToken] = Price({_price: price, _blockNumber: block.number});
}
```

**Attack chain:**
1. Attacker deploys token, becomes issuer
2. Calls `addILOCollateral()` (no access control — anyone can add ILO collateral if issuer)
3. Sets inflated collateral price via `setCollateralPrice()`
4. Opens lending position with overvalued collateral
5. Price oracle doesn't catch it because issuer is authorized
6. Liquidation triggers at wrong price → lender loses funds

**Detection:**
```bash
grep -n "issuer() == msg.sender\|addILOCollateral\|setCollateralPrice" contracts/
```

**Mitigation:** Require oracle/moderator for ALL price updates. Issuer should never self-price collateral.

---

### 2. Relayer Deposit Reentrancy (HIGH)

**Pattern:** `.transfer()` calls in relayer deposit/withdrawal functions.

```solidity
// Registration.sol:262
function refund(address coinbase) public ... {
    // ... state updates ...
    msg.sender.transfer(amount);  // ← REENTRANCY AFTER STATE UPDATE
    emit RefundEvent(true, 0, amount);
}

// Registration.sol:301
function buyRelayer(address coinbase) public payable ... {
    // ... state updates ...
    seller.transfer(price);  // ← REENTRANCY
    emit BuyEvent(true, coinbase, msg.value);
}
```

**Note:** `buyRelayer` deletes `RELAYER_ON_SALE_LIST[coinbase]` before transfer (good), but updates `_owner` before transfer (bad — re-entrant call could buy again).

**Detection:**
```bash
grep -n "\.transfer(\|\.call\.value\|\.send(" contracts/
```

**Mitigation:** Use checks-effects-interactions. Consider `ReentrancyGuard`.

---

### 3. `selfdestruct` as Overdraft Penalty (CRITICAL)

**Pattern:** Chequebook contract destroys itself on overdraft.

```solidity
// chequebook.sol:39-44
if (diff <= this.balance) {
    sent[beneficiary] = amount;
    beneficiary.transfer(diff);
} else {
    Overdraft(owner);
    selfdestruct(beneficiary);  // ← CONTRACT DEATH FOR BOUNCED CHEQUE
}
```

**Impact:** A single bounced cheque permanently kills the payment channel contract. Disproportionate penalty.

**Detection:**
```bash
grep -n "selfdestruct" contracts/
```

**Mitigation:** Use escrow/pause mechanism instead of selfdestruct. Allow owner to replenish.

---

### 4. Multisig `.call()` Reentrancy + Delegatecall (CRITICAL)

**Pattern:** Generic multisig executing arbitrary `.call()` with value.

```solidity
// MultiSigWallet.sol:233
txn.executed = true;
if (txn.destination.call.value(txn.value)(txn.data))  // ← LOW-LEVEL CALL, ALL GAS
    Execution(transactionId);
else {
    ExecutionFailure(transactionId);
    txn.executed = false;  // ← REENTRANT CALL COULD RE-EXECUTE
}
```

**Attack chain:**
1. Submit transaction with `destination = malicious contract`, `data = delegatecall payload`
2. If confirmed, `.call()` executes delegatecall in multisig context
3. Re-entrant call could submit new transaction (via `onlyWallet` if wallet is caller)

**Detection:**
```bash
grep -n "\.call\.value\|delegatecall" contracts/
```

**Mitigation:** Use `functionCall` from OpenZeppelin. Restrict `data` length or use allowlists.

---

### 5. Block-Timestamp Randomness Manipulation (HIGH)

**Pattern:** Validator-controlled block timing determines randomness window.

```solidity
// TomoRandomize.sol:15-18
function setSecret(bytes32[] _secret) public {
    uint secretPoint = block.number % 900;
    require(secretPoint >= 800);
    require(secretPoint < 850);
    randomSecret[msg.sender] = _secret;
}
```

**Attack:** Validator controls block production timing → chooses which window (800-850 vs 850-900) → decides whether to reveal secret or not.

**Detection:**
```bash
grep -n "block.number % \|block.timestamp" contracts/
```

**Mitigation:** Use VRF (Chainlink, drand) or commit-reveal with blockhash.

---

### 6. Go-Node Trading Engine: Division by Zero (HIGH)

**Pattern:** `makerPrice` used as divisor without zero check in matching engine.

```go
// tomox/order_processor.go:443,456,496,504
newQuantityTrade := new(big.Int).Mul(takerBalance, baseTokenDecimal)
newQuantityTrade = new(big.Int).Mul(newQuantityTrade, common.TomoXBaseFee)
newQuantityTrade = new(big.Int).Div(newQuantityTrade, new(big.Int).Add(common.TomoXBaseFee, takerFeeRate))
newQuantityTrade = new(big.Int).Div(newQuantityTrade, makerPrice)  // ← PANIC IF makerPrice==0
```

**Trigger:** Market orders don't have a price. If `processOrderList` matches against an order with `Price == 0` (shouldn't happen but no explicit guard in all paths), node panics.

**Detection:**
```bash
grep -n "big.Int).Div.*Price\|Div(.*makerPrice\|Div(.*order.Price" tomox/ tomoxlending/
```

**Mitigation:** Explicit `makerPrice.Sign() == 0` check before division. Reject orders with zero price at ingestion.

---

### 7. Go-Node Lending: Liquidation Rate Overflow (HIGH)

**Pattern:** `liquidationRate` multiplied without overflow check.

```go
// tomoxlending/order_processor.go:348-349
liquidationPrice := new(big.Int).Mul(collateralPrice, liquidationRate)
liquidationPrice = new(big.Int).Div(liquidationPrice, depositRate)
```

**Trigger:** If `liquidationRate` is set to `type(uint256).max` via `addCollateral()` (no upper bound check), `liquidationPrice` becomes astronomical → immediate liquidation of all positions.

**Detection:**
```bash
grep -n "Mul(collateralPrice, liquidationRate)\|Mul(.*liquidationRate" tomoxlending/
```

**Mitigation:** Cap `liquidationRate` in `addCollateral()` (e.g., `require(liquidationRate < 10000)`).

---

### 8. Solidity 0.4.x: `uint >= 0` is a No-Op (MEDIUM)

**Pattern:** `require(tradeFee >= 0 && tradeFee < 1000)` — the `>= 0` check is always true for `uint16`.

```solidity
// Registration.sol:121
require(tradeFee >= 0 && tradeFee < 1000, "Invalid Maker Fee");
```

**Impact:** Fee of 0 is valid. Could be used to create fee-less relayers, undermining fee economics.

**Detection:**
```bash
grep -n ">= 0\|>= *0" contracts/
```

**Mitigation:** Use `int16` if negative values are meaningful, or remove the no-op check and document that 0 is valid.

---

### 9. Array Off-by-One in `deList()` (MEDIUM)

**Pattern:** Memory array sizing error when token not found.

```solidity
// Registration.sol:398-417
function deList(address coinbase, address fromToken, address toToken) private view returns(address[], address[]) {
    address[] memory newFromTokens = new address[](RELAYER_LIST[coinbase]._toTokens.length);
    address[] memory newToTokens = new address[](RELAYER_LIST[coinbase]._toTokens.length);
    uint count = 0;
    // ... fill arrays, count < length if match found ...
    if (count != RELAYER_LIST[coinbase]._toTokens.length) {
        address[] memory fts = new address[](newToTokens.length-1);  // ← OFF-BY-ONE IF count==0
        // ... copy count elements into smaller array ...
    }
}
```

**Trigger:** If `count == 0` (no match found but arrays non-empty), `newToTokens.length-1` creates array one smaller than `newFromTokens`, and the copy loop writes one extra element → out-of-bounds.

**Detection:**
```bash
grep -n "new address\[\](" contracts/ | grep -i "length-1\|length - 1"
```

**Mitigation:** Use dynamic arrays with `push()` instead of pre-allocated fixed-size memory arrays.

---

## Audit Workflow for Orderbook DEX

### Phase 1: Contract Layer
1. **Relayer registration** — deposit logic, reentrancy, refund paths
2. **Token listing** — deposit gates, duplicate listing, foundation transfers
3. **Lending collateral** — price feed access control, rate bounds, issuer permissions
4. **Relayer marketplace** — buy/sell logic, ownership transfer, sale state

### Phase 2: Go Node Layer
1. **Order ingestion** — nonce checks, price/quantity validation, signature verification
2. **Matching engine** — division by zero, overflow, nil pointer checks
3. **Settlement** — balance updates, fee distribution, relayer fee checks
4. **Liquidation** — price calc overflow, timestamp manipulation, auto-topup logic

### Phase 3: Consensus Layer
1. **Validator set** — signer rotation, penalty logic, epoch boundaries
2. **Randomness** — block timing manipulation, commit-reveal windows
3. **State sync** — trading state root, lending state root, cross-shard consistency

---

## Grep Anchors

```bash
# Contract patterns
grep -rn "\.transfer(\|\.call\.value\|selfdestruct" contracts/ --include="*.sol"
grep -rn "block\.number % \|block\.timestamp" contracts/ --include="*.sol"
grep -rn "issuer() == msg\.sender\|addILOCollateral" contracts/ --include="*.sol"
grep -rn ">= 0 && .*< " contracts/ --include="*.sol"
grep -rn "new address\[\](" contracts/ --include="*.sol" | grep "length-1"

# Go node patterns
grep -rn "big\.Int).Div.*Price\|Div(.*makerPrice" tomox/ tomoxlending/ --include="*.go"
grep -rn "Mul(collateralPrice, liquidationRate)" tomoxlending/ --include="*.go"
grep -rn "Sign() == 0\|Sign() <= 0" tomox/ tomoxlending/ --include="*.go"
grep -rn "panic\|recover()" tomox/ tomoxlending/ --include="*.go"
```

---

## Related Patterns

- **AMM DEX** — Different model (liquidity pools, constant product). See `defi-protocol-analysis` AMM section.
- **Pool-based lending** — Aave/Compound model. Different from orderbook lending.
- **Geth-fork node audit** — RPC, CLI, deployment. See `blockchain-node-audit`.
