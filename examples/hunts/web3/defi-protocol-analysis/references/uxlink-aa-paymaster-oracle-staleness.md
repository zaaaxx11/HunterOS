# UXLINK AA Paymaster Oracle Staleness — Case Study

## Vulnerability Class
Account Abstraction Paymaster + Stale AMM Oracle = Price Manipulation

## Target
UXLINK Protocol (Arbitrum) — UXPaymaster contracts at:
- `0x79bc8427f83736e9900494Cd04a052Fbc9bE9709` (verified, Solidity 0.8.21)
- `0xcC20A81d4fe3597a55a698D554b52620BeB1BEe9` (verified, Solidity 0.8.21)

Token: `0x1A6B3A62391ECcaaa992ade44cd4AFe6bEC8CfF1` (UXLINK, 1.23M holders)

## Attack Chain

### Step 1: Identify Oracle Source Mismatch
UXPaymaster.sol uses Uniswap V3 QuoterV2 for gas price calculation:
```solidity
// Line 81-92: getWethToTokenPrice()
IQuoterV2.QuoteExactInputSingleParams memory quoterParams;
quoterParams.tokenIn = wethAddress;
quoterParams.tokenOut = tokenAddress;
quoterParams.amountIn = wethAmount;
quoterParams.fee = defaultPoolFee; // 500 = 0.05%
(amountOut, , , ) = quoterV2.quoteExactInputSingle(quoterParams);
```

Deploy script confirms V3 QuoterV2 hardcoded at construction.

### Step 2: Verify Liquidity Migration On-Chain
Blockscout transfer analysis for UXLINK token shows primary venues:
- **Uniswap V4 PoolManager** (`0x360E68faCcca8cA495c1B759Fd9EEe466db9FB32`) — 3 transfers in last 50
- **RainbowRouter** (`0x00000000009726632680FB29d3F7A9734E3010E2`) — 4 transfers
- **UniversalRouter** (`0xA51afAFe0263b40EdaEf0Df8781eA9aa03E381a3`) — 2 transfers
- **UniswapV3Pool** (`0x05De18dF74FA430Ea0729b00768B0655486773fB`) — only 1 transfer

**Finding:** Liquidity has migrated to V4. V3 pool is stale/dead.

### Step 3: Exploit Vector
`_postOp()` (lines 120-131) calls `setNewTokenPricePerEth()` which quotes `10**12` wei through the dead V3 pool:
```solidity
function setNewTokenPricePerEth() internal {
    uint256 amountOut = getWethToTokenPrice(10**12); // TINY AMOUNT
    require(amountOut > 0, "amountOut is zero");
    defaultTokenPricePerEth = (amountOut * PRICE_DENOMINATOR) / (10**12);
}
```

Tiny quote amounts on low-liquidity pools are trivially manipulable via flash loans or sandwich attacks. Every UserOperation that uses this paymaster gets charged based on the manipulated price.

### Impact
- **Overcharge:** Users pay inflated gas fees in UXLINK tokens
- **Undercharge:** Attacker subsidizes their own ops at protocol's expense
- **Drain:** Repeated overcharges across all AA users deplete user token balances

## Detection Methodology

### Pre-Audit Checklist for AA Paymasters
1. **Identify oracle source:** Which AMM/price feed does the paymaster use?
2. **Verify live liquidity:** Check recent token transfers via Blockscout/Dune. Which venues actually have volume?
3. **Check version mismatch:** Does the oracle reference an older AMM version than where liquidity currently lives?
4. **Inspect postOp price updates:** Does `_postOp()` recalculate prices? This creates a per-tx manipulation window.
5. **Check quote amount size:** Tiny amounts (< 1e15 wei) on any pool are manipulation vectors.

### On-Chain Verification Commands
```bash
# Search for deployed paymasters
curl -s "https://arbitrum.blockscout.com/api/v2/search?q=UXPaymaster" | jq '.items[].address_hash'

# Check recent token transfers for venue identification
curl -s "https://arbitrum.blockscout.com/api/v2/tokens/TOKEN_ADDR/transfers" | \
  jq '[.items[] | {from: .from.hash, to: .to.hash, name: (.to.name // .from.name)}] | group_by(.name) | map({name: .[0].name, count: length}) | sort_by(-.count)'

# Verify paymaster source code imports
curl -s "https://arbitrum.blockscout.com/api/v2/smart-contracts/PAYMASTER_ADDR" | \
  jq '{compiler: .compiler_version, hasV3: (.source_code | contains("@uniswap/v3")), hasV4: (.source_code | contains("PoolManager"))}'
```

## Mitigation
1. Migrate oracle to V4-compatible price source or TWAP
2. Remove price recalculation from `_postOp()` — use cached/staleness-checked price
3. Add minimum quote amount threshold to prevent micro-quote manipulation
4. Implement oracle staleness check with revert on stale data

## Related Pitfalls
- P9: Account Abstraction Paymaster Oracle Staleness (added to defi-protocol-analysis SKILL.md)
- P1: Assuming TVL Claims Are Accurate (always verify on-chain)

</parameter>
</function>