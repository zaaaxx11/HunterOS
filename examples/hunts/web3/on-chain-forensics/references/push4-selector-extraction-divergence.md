# PUSH4 Selector Extraction & Implementation Divergence Detection

## When the source code lies — deployed bytecode tells the truth

### Problem
You have source code for a UUPS proxy token (e.g., `Naoris.sol` — 4B supply, no burn, no timelock). But the deployed implementation on-chain may have been upgraded to a completely different version. `getRoleMemberCount` reverts, `cap()` reverts, and `version()` returns "3.0.0" — signals that the deployed code ≠ the source you have.

### Solution: Extract all PUSH4 selectors from bytecode

```bash
cast code $IMPL_ADDR --rpc-url $RPC | python3 -c "
import sys
code = sys.stdin.read().strip()
if code.startswith('0x'): code = code[2:]
selectors = set()
i = 0
while i < len(code) - 10:
    if code[i:i+2] == '63':  # PUSH4 opcode
        sel = code[i+2:i+10]
        selectors.add(sel)
        i += 10
    else:
        i += 2
for s in sorted(selectors):
    print(f'0x{s}')
" | while read sel; do
    sig=$(cast 4byte-decode "$sel" 2>&1 || echo "unknown")
    echo "$sel $sig"
done
```

### What this reveals (Naoris BSC case study)

Source code (`Naoris.sol`) had:
- `name()`, `symbol()`, `decimals()`, `totalSupply()`, `balanceOf()`, `transfer()`, `transferFrom()`, `approve()`, `permit()`
- `pause()`, `unpause()`, `paused()`
- `DEFAULT_ADMIN_ROLE()`, `PAUSER_ROLE()`
- `hasRole()`, `getRoleAdmin()`, `grantRole()`, `renounceRole()`
- `upgradeTo()`, `upgradeToAndCall()`, `proxiableUUID()`

Deployed BSC implementation (v3.0.0) ADDED:
- `MAX_TOTAL_SUPPLY()` → 1B (not 4B like source!)
- `TIMELOCK_DELAY()` → 86400 (1 day)
- `EMERGENCY_ROLE()` → separate from PAUSER
- `emergencyPause()`, `emergencyUnpause()`, `emergencyPaused()`
- `mintCooldown()` → 1800 (30 min)
- `getRemainingMintableAmount()` → 910.5M
- `getMintsInRange()`, `getMintDetails()`, `mints()`
- `burn(uint256)` → not in source!
- `scheduleOperation()`, `executeOperation()` → TimelockController!
- `initializeV2()`, `initializeV3()` → multiple upgrade versions
- `ReentrancyGuardReentrantCall()` → reentrancy protection added
- `collate_propagate_storage(bytes16)` → storage migration

### Key indicators of divergence

1. `getRoleMemberCount`/`getRoleMember` revert → AccessControl is customized
2. `cap()` reverts → ERC20Capped not exposed
3. `version()` returns a version string → use this as fingerprint
4. `owner()` reverts → UUPS pattern, not Ownable

### Cross-chain verification (Ethereum as ground truth)

When the same proxy address exists on Ethereum:
```bash
# On Ethereum (original deployment)
cast implementation $PROXY --rpc-url $ETH_RPC  # → 0x9658... (different impl!)
cast call $PROXY "totalSupply()" --rpc-url $ETH_RPC  # → 4B (matches source!)
cast call $PROXY "version()" --rpc-url $ETH_RPC  # → reverts (no version)

# On BSC (upgraded)
cast implementation $PROXY --rpc-url $BSC_RPC  # → 0xc4e1... (different impl!)
cast call $PROXY "totalSupply()" --rpc-url $BSC_RPC  # → 89.5M (1B max)
cast call $PROXY "version()" --rpc-url $BSC_RPC  # → "3.0.0"
```

This pattern reveals: Ethereum = original deployment, BSC = heavily upgraded fork.

### Trust boundary impact

When implementation diverges from audited source:
- New roles (EMERGENCY_ROLE) = new trust assumptions
- TimelockController = upgrade delay added (1 day)
- Burn function = supply can be reduced
- Mint tracking = supply is phased, not all-at-once
- MAX_TOTAL_SUPPLY changed from 4B → 1B = fundamental economic change

Always flag divergence as CRITICAL finding — the audited source code is NOT what's deployed.