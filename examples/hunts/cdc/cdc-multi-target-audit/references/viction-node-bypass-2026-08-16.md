# Viction Node EVM Bypass Pattern

## Overview

In TomoX/TomoChain-style L1s, trading and lending transactions may be routed to `ApplyEmptyTransaction()` which **never executes contract bytecode**. The node directly reads/writes contract storage slots.

## Detection

```bash
# In node code
grep -rn "ApplyEmptyTransaction\|CallContractWithState" tomox/ core/
grep -rn "statedb.GetState\|statedb.SetState" tomox/ tomoxlending/
```

## Key Files

- `tomox/order_processor.go` — Trading order processing
- `tomoxlending/tomoxlending.go:830` — `ProcessLiquidationData()`
- `core/state_processor.go` — State transitions

## Impact

- Bypasses ALL Solidity modifiers (`onlyActiveRelayer`, `relayerOwnerOnly`, `nonReentrant`)
- Node operator can manipulate contract state without contract logic
- Validator controls liquidation timing and pricing
- **Systemic centralization risk** — node operator = privileged actor

## Mitigation

- Add validation layer that re-executes contract bytecode
- Multi-sig for state-changing operations
- Decentralize node operation
