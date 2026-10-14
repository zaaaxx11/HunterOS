---
name: cdc-lending-audit-foundry-poc
description: "CDC 4-agent lending-fork audit with Foundry PoC testing"
---

# CDC Lending Audit + Foundry PoC

Use when running a CDC 4-agent audit on a lending protocol fork and need to produce a Foundry-tested PoC.

## CDC Round Architecture

### Round 1: Cold Spawn (4 agents)
- Agent 1 (ARCHITECT): Map trust boundaries, identify custom vs upstream code
- Agent 2 (RED-TEAMER): Attack every oracle adapter, trace which function the consumer calls
- Agent 3 (FUZZ-ENGINEER): Edge cases on lending math — 0 amounts, 0 duration, max values
- Agent 4 (CHAINER): Build chains across swap adapters, deployer, web2 secrets

### Round 2: Knowledge-Transfer Respawn
- Write ALL Round 1 findings to a shared file (e.g. `findings_round1.md`)
- Re-spawn 4 agents with that file as context — they start deeper, skip dead ends
- This is critical: cold agents waste 30 min re-discovering what Round 1 already found

### Steering While Running
- Use `delegate_task(action='steer')` to cross-correct agents in real-time
- When Agent A finds a promising vector, immediately steer Agent B to validate/challenge it
- Key pattern: steer the CHAINER and RED-TEAMER toward each other's findings for adversarial validation

## Oracle Audit Patterns

### AaveOracle Consumption
- `AaveOracle.getAssetPrice()` calls ONLY `source.latestAnswer()` (line ~109)
- Checks ONLY `price > 0` — NEVER staleness, NEVER latestRoundData
- All staleness logic in latestRoundData = dead code for core protocol path
- Inflated positive price → passes check → over-borrow theft
- Zero/negative price → falls back to fallback oracle (NOT free borrow)

### Common False Positives (adversarial corrections)
- ratio=0 / price=0 → AaveOracle FALLS BACK, not "always solvent" / "free borrow"
- metaDecimals>6 underflow → Panic(0x11) REVERT = DoS, NOT price manipulation
- IAdapter oracles feed AaveOracle (core pool), NOT isolated pairs (which use IDualOracle.getPrices)
- Flashloan full-grab reverts (EVM atomicity) — but PARTIAL grab works (steal delta + real-swap rest)

## Swap Adapter Arbitrary Calldata
- `setSwapPath` with NO access control + `router.call(attackerCalldata)` = token drain
- Aggregator routers (GlueX, LI.FI, Squid) have `Interaction[]{target, value, callData}[]` = arbitrary-call surface
- Attacker injects `transferFrom(adapter, attacker, amountIn)` via interactions[]
- `amountOutMin=0` bypasses output check; missing `balanceBefore` delta sweeps ALL residuals
- Check ALL adapter siblings — bug bounty may list ONE but miss identical patterns in others

## P2P Lending Input Validation
- `abi.decode` of user-supplied struct → check EVERY field for missing require
- `collateralAmount=0` + `duration=0` = free loan that defaults for free
- `_liquidate` that only pushes collateral OUT but never pulls asset IN = free debt wipe
- Borrower-controlled oracle addresses = price-based liquidation DoS

## Foundry PoC Testing

### Install and Setup
```
curl -L https://foundry.paradigm.xyz | bash
export PATH="$HOME/.foundry/bin:$PATH"
foundryup
mkdir poc-foundry && cd poc-foundry
git init
forge install foundry-rs/forge-std --no-commit
forge install OpenZeppelin/openzeppelin-contracts --no-commit
```

### foundry.toml (CRITICAL)
Must set `viaIR = true` + `optimizer = true` to avoid stack-too-deep on struct destructuring:
```
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc_version = "0.8.20"
viaIR = true
optimizer = true
optimizer_runs = 200
```

### Stack-Too-Deep Workaround
Public mapping struct returns (12+ fields) cause stack-too-deep even with viaIR. Use a helper function with minimal destructuring instead of inline tuple unpack in test functions.

### PoC Structure
- Copy EXACT vulnerable contract logic into src/ — preserve original line numbers in comments
- Write test in test/ with step-by-step exploit chain and assertions
- Run: `forge test -vvv`

## Quick Negatives (skip to save time)
- Merkle distributor: standard OZ = clean
- SDK/indexer: env-var keys = clean
- StrategyManager: owner-self-gated = clean
- First-depositor inflation (isolated pairs with accounting-based totalAsset): donations strand
- Liquidate 0 debt: _isSolvent returns true then BorrowerSolvent revert

## Cross-Validation Discipline
- Every finding MUST be adversarially validated: prove it is not exploitable before keeping
- 3 false positives caught in HyperLend audit via agent cross-correction
- Honesty over claims: if chain does not work, report as negative result