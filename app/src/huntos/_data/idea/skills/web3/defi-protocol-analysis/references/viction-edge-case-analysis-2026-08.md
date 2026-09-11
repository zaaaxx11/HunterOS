# Viction (TomoChain) Edge-Case Analysis — Full Report

**Target:** `/root/_fuzz_viction` (forked go-ethereum with TomoX/TomoX Lending extensions)  
**Date:** 2026-08-16  
**Scope:** EVM contracts (`.sol`), Go node (consensus, RPC, trading, lending)

---

## 1. EVM Contract Sinks (Solidity 0.4.x)

### 1.1 `Registration.sol` — Relayer Registration

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `register()` | **0 amount** | Medium | `msg.value >= MinimumDeposit` checked, but `MinimumDeposit` can be set to 0 via `reconfigure()` (only requires `> 10000` wei — trivially satisfiable). |
| `register()` | **max uint256** | Medium | `msg.value` at `type(uint256).max` would overflow `RELAYER_LIST[coinbase]._deposit.add(msg.value)` in `depositMore`, but `register` uses raw assignment so no overflow there. |
| `update()` / `updateFee()` | **tradeFee = 0** | Low | `tradeFee >= 0` is always true for `uint16`. Fee of 0 is valid but could be used to drain relayer fee economics. |
| `buyRelayer()` | **Reentrancy** | **High** | `seller.transfer(price)` at line 301 is a low-level `.transfer()` call to an EOA/contract. If `seller` is a contract with a payable fallback, it can re-enter `buyRelayer` or `sellRelayer` before `RELAYER_ON_SALE_LIST` is deleted (actually it IS deleted before transfer, so reentrancy on sale flag is blocked — but `RELAYER_LIST[coinbase]._owner` is already updated to `msg.sender`, so a re-entrant call could buy the same relayer again or manipulate state). |
| `refund()` | **Reentrancy** | **High** | `msg.sender.transfer(amount)` at line 262 after state updates. Classic reentrancy vector — attacker can re-enter `refund` or `depositMore` before balance is updated. |
| `resign()` | **Race condition** | Medium | `RESIGN_REQUESTS[coinbase] = now + 4 weeks` — block timestamp manipulation by validator (±15s on Ethereum, exact on PoSV). |
| `deList()` | **Off-by-one / underflow** | Medium | `newToTokens.length-1` at line 412 — if `count == RELAYER_LIST[coinbase]._toTokens.length` (token not found), the `if` is false and it returns the full arrays. But if `count == length - 1` (one match found), `newToTokens.length-1` is correct. If `count == 0` (no match but length > 0), `newToTokens.length-1` creates an array one smaller than needed, and the loop copies one extra element → **out-of-bounds read** in the returned array. |
| `validateTokens()` | **Storage collision** | Low | Uses `new address[](fromTokens.length)` in memory — no storage collision, but the `tomoNative` constant `0x0000...0001` is hardcoded and could collide with a real token. |
| `changeContractOwner()` | **Null check** | Low | `owner != address(0)` checked, but no event emitted — ownership change is untraceable on-chain. |

### 1.2 `LendingRegistration.sol` — Lending Contract

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `setCollateralPrice()` | **Privilege escalation** | **High** | If a token is NOT in `COLLATERALS` list, `msg.sender` only needs to be the token **issuer** (line 139). An issuer can set arbitrary prices for their own token as collateral, then manipulate liquidation. |
| `addILOCollateral()` | **No moderator check** | **High** | Anyone can call `addILOCollateral()` if they are the token issuer. No `moderatorOnly` modifier. Combined with self-priced collateral, this is a full collateral manipulation vector. |
| `addCollateral()` | **Rate validation** | Medium | `depositRate >= 100 && liquidationRate > 100` — rates are basis-point-like but no upper bound. `liquidationRate` could be set to `type(uint256).max`, causing `liquidationPrice` overflow in `processOrderList` (line 348: `new(big.Int).Mul(collateralPrice, liquidationRate)`). |
| `update()` | **tradeFee = 0** | Low | Same as Registration — `tradeFee >= 0` is a no-op for uint16. |

### 1.3 `TOMOXListing.sol` — Token Listing

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `apply()` | **Fixed deposit** | Low | `require(msg.value == 1000 ether)` — exact match, no edge case. |
| `apply()` | **Reentrancy** | Medium | `foundation.transfer(msg.value)` before state update. `foundation` is hardcoded `0x68`. If that address is a contract, it could re-enter. |
| `apply()` | **Duplicate token** | Low | `onlyValidApplyNewToken` checks `isActive != true`, but if the same token address is pushed twice via reentrancy before `isActive` is set... actually `tokensState[token]` is set after transfer, so reentrancy could bypass. |

### 1.4 `chequebook.sol` — Payment Channel

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `cash()` | **Reentrancy** | **High** | `beneficiary.transfer(diff)` at line 38. Classic reentrancy — beneficiary can re-enter `cash` with a higher cumulative amount before `sent[beneficiary]` is updated (actually it IS updated before transfer at line 37, so this is safe from cumulative replay, but the `selfdestruct(beneficiary)` at line 44 on overdraft is extreme and could kill the contract). |
| `cash()` | **Overflow** | Medium | `amount - sent[beneficiary]` — if `amount` is `type(uint256).max` and `sent[beneficiary]` is 0, `diff` is max uint256, which will fail the `diff <= this.balance` check and trigger `selfdestruct`. |
| `cash()` | **Signature malleability** | Medium | `ecrecover` is used with `keccak256(address(this), beneficiary, amount)`. No nonce/replay protection beyond cumulative amount. If a cheque is cashed partially, the signature can be reused with a higher amount (but `require(amount > sent[beneficiary])` prevents exact replay). |
| `cash()` | **selfdestruct** | **Critical** | On overdraft, `selfdestruct(beneficiary)` destroys the entire chequebook contract and sends all remaining balance to the beneficiary. This is a disproportionate penalty — a single bounced cheque kills the contract permanently. |

### 1.5 `MultiSigWallet.sol` — Multisig

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `executeTransaction()` | **Reentrancy** | **High** | `txn.destination.call.value(txn.value)(txn.data)` at line 233. The low-level `.call()` forwards all gas and can re-enter the wallet. The `executed` flag is set to `true` before the call (line 232), which prevents direct re-execution of the same tx, but a re-entrant call could submit a new transaction and confirm it if the wallet is the caller (`onlyWallet` modifier). |
| `executeTransaction()` | **Delegatecall** | **Critical** | If `txn.data` contains a `delegatecall` to a malicious contract, the delegate runs in the wallet's storage context. Combined with `call.value()`, this is a full wallet drain vector. |
| `submitTransaction()` | **0 value** | Low | `destination` must be non-zero, but `value` can be 0. A tx with `value=0` and malicious `data` can still execute arbitrary calls. |
| `addOwner()` / `removeOwner()` | **Race** | Medium | Owners array manipulation — `removeOwner` swaps with the last element. If two removals happen in the same block (via submitted txs), the swap could remove the wrong owner. |
| `getTransactionIds()` | **Off-by-one** | Medium | `new uint[](to - from)` at line 356 — if `to <= from`, this creates a zero-length or negative-length array ( Solidity 0.4 reverts on negative size). If `to == from`, it returns an empty array but the loop runs `from` to `to` which is empty — no crash but misleading. |

### 1.6 `TomoRandomize.sol` — Validator Randomness

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `setSecret()` | **Block timestamp manipulation** | **High** | `block.number % 900` determines the window. Validators can manipulate block production timing to land in the `[800, 850)` window. |
| `setOpening()` | **Same** | **High** | Same vector for `[850, 900)` window. A validator controlling block timing can choose which window they land in and thus whether to reveal or not. |
| `getSecret()` / `getOpening()` | **No access control** | Medium | Anyone can read any validator's secret/opening. No edge case but a design issue. |

---

## 2. Go Node Sinks

### 2.1 `tomox/order_processor.go` — Trading Engine

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `ApplyOrder()` | **0 quantity** | Medium | Checked at line 79: `order.Quantity.Sign() == 0` → reject. Good. |
| `ApplyOrder()` | **0 price (limit)** | Medium | Checked at line 73 for non-market orders. Good. |
| `ApplyOrder()` | **Nonce mismatch** | Low | `order.Nonce` compared against state nonce. Off-by-one in either direction is rejected. |
| `processOrderList()` | **Nil order** | Medium | `oldestOrder.Quantity == nil` checked at line 226. Good. |
| `processOrderList()` | **Nil quotePrice** | Medium | `quotePrice == nil || quotePrice.Sign() == 0` at line 242 → falls back to inverse price. If both are nil/0, `quotePrice` stays nil and `getTradeQuantity` receives nil → `GetSettleBalance` would receive nil quotePrice. |
| `getTradeQuantity()` | **Nil decimal** | Medium | `baseTokenDecimal.Sign() == 0` checked. But `quoteTokenDecimal` could be 0 if token has 0 decimals (unusual but possible for custom tokens). |
| `GetTradeQuantity()` | **Division by zero** | **High** | `makerPrice` is used as divisor at lines 443, 456, 496, 504. If `makerPrice == 0` (should be rejected earlier for limit orders, but market orders don't have a price), this causes a panic. |
| `GetTradeQuantity()` | **Overflow** | Medium | `new(big.Int).Mul(quantityToTrade, makerPrice)` — if both are `~2^256`, the product is `~2^512` which `big.Int` handles, but downstream divisions assume the result fits in token decimals. |
| `DoSettleBalance()` | **Nil settleBalance** | Medium | Called only if `quantity.Sign() > 0` and `settleBalanceResult != nil`. But if `settleBalance.Taker.InToken` or `.OutToken` is the zero address, `CheckAddTokenBalance` may behave unexpectedly. |
| `DoSettleBalance()` | **Empty exchange owner** | Medium | Checked at line 525. Good. |

### 2.2 `tomoxlending/order_processor.go` — Lending Engine

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `processOrderList()` | **Nil collateral price** | Medium | Checked at lines 285-290. Good. |
| `processOrderList()` | **Liquidation overflow** | **High** | Line 348: `new(big.Int).Mul(collateralPrice, liquidationRate)` — if `liquidationRate` is `type(uint256).max` (set via `addCollateral`), this produces a huge number. Then line 349 divides by `depositRate`. If `depositRate` is small (e.g., 100), the liquidation price is astronomical, causing immediate liquidation of all positions. |
| `processOrderList()` | **0 term** | Medium | `order.Term` is used at line 347: `header.Time.Uint64() + order.Term`. If `Term` is 0, liquidation is immediate. `addTerm` requires `term >= 60`, but lending orders might bypass this. |
| `getLendQuantity()` | **Nil prices** | Medium | Checked at line 427. Good. |

### 2.3 `consensus/posv/posv.go` — Consensus

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `Verify()` | **Epoch boundary** | Medium | `epochLength = 900` — checkpoint blocks have special signer/penalty validation. A block at exactly `number % 900 == 0` must have empty extra signer data except at checkpoint. |
| `Verify()` | **Timestamp** | Low | `ErrInvalidTimestamp` if `timestamp <= parent + period`. Period is 0 for instant chains — empty blocks are rejected. |
| `snapshot.go` | **Signer set** | Medium | `Recents` map prevents recent signers from signing consecutively. If signer count drops below `len(Recents)`, the chain could stall. |

### 2.4 `rpc/server.go` — RPC Server

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `serveRequest()` | **Panic recovery** | Low | `recover()` at line 133 catches panics in RPC handlers. Good. |
| `serveRequest()` | **Batch overflow** | Medium | No limit on batch size in `readRequest`. A massive batch could exhaust memory. |
| `RegisterName()` | **Empty name** | Low | Checked at line 89. Good. |

### 2.5 `tomox/tradingstate/statedb.go` — State DB

| Function | Edge Case | Severity | Detail |
|----------|-----------|----------|--------|
| `GetNonce()` | **Default 0** | Medium | Returns 0 for non-existent objects. If an order is submitted with nonce 0 for a new user, it's accepted. Subsequent orders must increment. |
| `SetNonce()` | **No overflow check** | Low | `nonce` is `uint64`. If it wraps, the next order with nonce 0 would be rejected as "too low" (actually it would be `ErrNonceTooHigh` since state nonce is 0 and order nonce is `2^64-1 + 1 = 0`). |

---

## 3. Summary of Critical Findings

| # | Sink | Edge Case | Impact |
|---|------|-----------|--------|
| 1 | `Registration.buyRelayer()` | Reentrancy on `.transfer()` | Wallet drain |
| 2 | `Registration.refund()` | Reentrancy on `.transfer()` | Wallet drain |
| 3 | `chequebook.cash()` | `selfdestruct` on overdraft | Contract death |
| 4 | `MultiSigWallet.executeTransaction()` | `.call()` reentrancy + delegatecall | Full wallet drain |
| 5 | `LendingRegistration.addILOCollateral()` | No access control + self-price | Collateral manipulation → liquidation exploit |
| 6 | `LendingRegistration.setCollateralPrice()` | Issuer-controlled pricing | Same as above |
| 7 | `TomoRandomize.setSecret/setOpening()` | Block timing manipulation | Randomness beacon bypass |
| 8 | `GetTradeQuantity()` | Division by `makerPrice == 0` | Node panic (DoS) |
| 9 | `processOrderList()` (lending) | `liquidationRate` overflow | Mass liquidation |
| 10 | `Registration.deList()` | Off-by-one array sizing | Out-of-bounds read |

---

## 4. Fuzzing Recommendations

**High-priority fuzz targets:**
1. `buyRelayer()` / `refund()` — reentrancy with malicious contract caller
2. `executeTransaction()` — `.call()` with delegatecall payload
3. `cash()` — max uint256 amount, overdraft path
4. `addILOCollateral()` + `setCollateralPrice()` — issuer price manipulation
5. `GetTradeQuantity()` — `makerPrice = 0` for market orders
6. `processOrderList()` (lending) — `liquidationRate = type(uint256).max`

**Edge inputs to test:**
- `amount = 0`, `amount = type(uint256).max`
- `price = 0`, `price = 1`
- `tradeFee = 0`, `tradeFee = 999`
- Empty arrays `fromTokens = []`, `toTokens = []`
- `coinbase = msg.sender`, `coinbase = CONTRACT_OWNER`, `coinbase = address(0)`
- `new_owner = msg.sender`, `new_owner = address(0)`
- `term = 0`, `term = type(uint256).max`
- `depositRate = 100`, `liquidationRate = type(uint256).max`
- `quotePrice = nil`, `quotePrice = 0`
- Reentrancy via payable fallback on recipient contracts
