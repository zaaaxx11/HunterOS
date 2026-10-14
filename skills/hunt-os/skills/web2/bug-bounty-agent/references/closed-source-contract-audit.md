# Closed-Source / Unverified Contract Audit Methodology

## When Source Code Is Unavailable

**Trigger**: Contracts are unverified on explorer, no public repo, no documentation, or team refuses to share source.

**DO NOT** waste time on:
- GitHub/docs scraping (if contracts aren't public, docs won't have addresses)
- Twitter scraping (teams rarely post contract addresses)
- Guessing factory patterns without on-chain evidence

---

## Pivot to On-Chain Forensics (Immediate)

### 1. Find the Contracts On-Chain

**Method A: Transaction Forensics (Best)**
```bash
# Get recent deposit/withdraw tx hashes from team or block explorer
cast tx <tx_hash> --rpc-url <rpc> --json
# Parse input data for contract calls
cast call <contract> "function_selector()" --rpc-url <rpc>
```

**Method B: Factory/Proxy Pattern Recognition**
```bash
# Common proxy patterns on EVM chains:
# EIP-1967: impl slot = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
# EIP-1822: impl slot = 0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7
# EIP-1167 (minimal proxy): 0x3d602d80600a3d3981f3363d3d373d3d3d363d73<20-byte-addr>5af43d82803e903d91602b57fd5bf3

cast storage <proxy> 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc --rpc-url <rpc>
```

**Method C: Function Selector Scanning**
```bash
# Scan for known function selectors in contract bytecode
# ERC20: 0x70a08231 (balanceOf), 0x18160ddd (totalSupply)
# ERC4626: 0x70a08231 + 0x47e7ef24 (totalAssets), 0x47e7ef24 (previewDeposit)
# PoolTogether PrizePool: 0x... (custom selectors)
```

**Method D: Tracing Known Interactions**
```bash
# If you have a user deposit tx, trace it:
cast trace <tx_hash> --rpc-url <rpc> --verbosity 3
# Follow all internal calls to find vault, factory, prize pool
```

---

## 2. Contract Discovery Patterns by Protocol Type

### Prize-Linked Savings (PoolTogether-style)
- **PrizePool** factory → creates PrizePools per asset
- **Vault** (ERC4626) → deposits, accrues yield
- **TwabController** → time-weighted average balance for tickets
- **DrawCalculator** → uses RNG (Chainlink VRF / custom)
- **Claimable** → prize distribution logic

**Key addresses to find**:
- PrizePool factory (often single on chain)
- TwabController (often shared)
- DrawManager (per prize tier)

### Yield Aggregator / Vault (ERC4626)
- **Vault** (ERC4626) → deposit/withdraw, shares
- **Strategy** → yield source (Aave, Compound, Morpho, etc.)
- **Keeper/Bot** → harvest, rebalance

### AMM / DEX
- **Factory** → creates pools
- **Pool** → swap, liquidity, fees
- **Router** → multi-hop swaps

---

## 3. Contract Analysis Without Source

### Bytecode Analysis
```bash
# Get full bytecode
cast code <address> --rpc-url <rpc>

# Disassemble with heimdall or ethernal
heimdall disassemble <bytecode>

# Function selector extraction
echo <bytecode> | grep -oE 'PUSH4 [0-9a-f]{8}' | sort -u
```

### Storage Slot Reading
```bash
# Common slots:
# EIP-1967 impl: 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
# EIP-1967 admin: 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
# EIP-1822 impl: 0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7

cast storage <addr> <slot> --rpc-url <rpc>
```

### Decompilation Tools
```bash
# Open-source
heimdall decompile <address> --rpc-url <rpc>
panoramix decompile <address> --rpc-url <rpc>

# Commercial (better)
ethernal.com (free tier)
tenderly.co (free tier)
```

---

## 4. Vulnerability Classes in Closed-Source

### High-Confidence Findings Without Source
1. **Storage Collisions** (proxy + impl) — check slot overlaps
2. **Reentrancy** — via external calls in `fallback`/`receive` or external calls before state updates
3. **Access Control Missing** — `onlyOwner`/`onlyAdmin` missing on critical funcs
3. **Upgradeability Risks** — `upgradeTo`, `upgradeToAndCall` callable by anyone
4. **Initialization Race** — `initialize` not protected by `initializer` modifier
4. **Oracle Manipulation** — no price freshness checks, single oracle
5. **Reentrancy in ERC4626** — `deposit`/`withdraw` calling back into vault
5. **Precision Loss** — division before multiplication in fee/interest calc
6. **Unchecked Return Values** — ERC20 `transfer`/`transferFrom` without check

### Verification Strategy
```solidity
// Foundry fork test template for closed-source
contract ExploitTest is Test {
    address target = 0x...;
    address victim = makeAddr("victim");
    address attacker = makeAddr("attacker");

    function setUp() public {
        vm.createSelectFork("https://mainnet.base.org");
        vm.deal(attacker, 10000 ether);
        vm.deal(victim, 10000 ether);
    }

    function testExploit() public {
        // 1. Setup state
        // 2. Execute exploit
        // 3. Assert impact
    }
}
```

---

## 5. Reporting Closed-Source Findings

### Required Evidence
1. **Contract address** + chain
2. **Function selector** + calldata used
3. **Storage slot** + value read
4. **Foundry fork test** that reproduces
5. **Impact calculation** with concrete numbers

### Report Template
```markdown
## [Severity] Title
**Target**: <contract_address> (Chain: <chain_id>)
**Type**: <vulnerability_class>
**Source**: Closed-source / unverified on-chain

### Proof of Concept
<Foundry test code>

### Impact
<Concrete numbers: funds at risk, users affected>

### Remediation
<Specific code fix or architectural change>
```

---

## 5. When to Walk Away

- No way to interact with contracts (no ABI, no function signatures found)
- Team unresponsive to responsible disclosure
- Protocol TVL < $10K (not worth effort)
- Contracts have `selfdestruct` or are upgradeable with no timelock
- Entire protocol behind multisig with unknown signers

---

## Quick Reference: Common Selectors

| Function | Selector | Protocol |
|----------|----------|----------|
| `balanceOf` | `0x70a08231` | ERC20 |
| `totalSupply` | `0x18160ddd` | ERC20 |
| `deposit` | `0x47e7ef24` | ERC4626 |
| `withdraw` | `0x69328dec` | ERC4626 |
| `mint` | `0x40c10f19` | Aave aToken |
| `borrow` | `0xc5ebeaec` | Aave |
| `liquidationCall` | `0x9b5d8c8e` | Aave |
| `claimPrize` | `0x...` | PoolTogether |
| `awardPrize` | `0x...` | PoolTogether |
| `draw` | `0x...` | PrizePool |

---

## Red Flags in Closed-Source Protocols

| Flag | Why It Matters |
|------|----------------|
| Single admin key (no timelock) | Rug pull / upgrade risk |
| No reentrancy guard on deposit/withdraw | Reentrancy |
| `transfer` not `safeTransfer` | ERC20 non-compliance |
| `block.timestamp` for randomness | Manipulable |
| Single oracle, no TWAP | Oracle manipulation |
| `delegatecall` to untrusted address | Arbitrary code exec |
| `selfdestruct` present | Funds can be drained |
| No events for critical actions | Unauditable |