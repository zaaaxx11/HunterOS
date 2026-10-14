# Unverified Contract Audit Methodology

**Context:** When smart contract source code is NOT verified on Etherscan, auditors must rely on bytecode analysis, RPC calls, and decompilation to understand contract logic and find vulnerabilities.

**⚠️ BEFORE STARTING:** Run the Reality Check from `references/pre-launch-detection.md`. If the protocol is pre-launch (0 TVL, empty implementation, 0 supply), skip the deep audit and report pre-launch issues only.

---

## Why This Matters

Many DeFi protocols deploy proxy patterns where:
- Implementation contracts are not verified
- Proxy admin is unknown or unset
- Factory-deployed vaults have no public source

**Example:** t3tris.finance ($6.4M TVL) — Silo & VaultImpl unverified, UUPS proxy with empty admin slot, implementation has no code.

---

## Step-by-Step Methodology

### 1. Contract Discovery

**Find all related contracts:**
```bash
# Search Etherscan by name
curl "https://api.arbiscan.io/api?module=contract&action=getContractCreationCode&address=0x..."

# Or search via explorer web UI for "protocol name"

# Check app frontend for contract addresses (often in JS bundles)
curl -s https://app.protocol.com | grep -oE '0x[a-fA-F0-9]{40}'

# Check GitHub repos for deployment scripts
```

### 2. Proxy Pattern Identification

**Read EIP-1967 storage slots:**
```bash
# Implementation slot
curl -X POST https://arb1.arbitrum.io/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getStorageAt","params":["<proxy>","0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc","latest"],"id":1}'

# Admin slot
curl -X POST https://arb1.arbitrum.io/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getStorageAt","params":["<proxy>","0xb53127684a568b3173ae13b9f8a6016e24aa342e","latest"],"id":1}'

# Beacon slot (for beacon proxy)
curl -X POST https://arb1.arbitrum.io/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getStorageAt","params":["<proxy>","0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50","latest"],"id":1}'
```

**CRITICAL: Trace the FULL delegation path.** The implementation slot may point to an address with code, but the proxy's bytecode might DELEGATECALL to a DIFFERENT address. Always:
1. Check proxy bytecode for DELEGATECALL instructions
2. Extract the actual delegation target from bytecode
3. Verify THAT address has code
4. Don't trust the storage slot alone — custom proxies may ignore it

### 3. Implementation Code Check

**Verify implementation exists:**
```bash
curl -X POST https://arb1.arbitrum.io/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["<implementation>","latest"],"id":1}'
```

**Critical finding:** If code length is 0 or 2 bytes, implementation doesn't exist → ALL CALLS REVERT.

### 4. Bytecode Analysis

**Decompile bytecode:**
```bash
# Using ethers-decompile (if available)
npx ethers-decompile <bytecode>

# Using Panoramix (online)
# https://panoramix.ethereum.org

# Using Foundry (if source available)
forge inspect <contract> bytecode
```

**Extract function selectors:**
```bash
# Get all 4-byte selectors from bytecode
python3 -c "
import sys
bytecode = sys.argv[1]
selectors = set()
i = 0
while i < len(bytecode):
    if bytecode[i:i+8] in ['60', '61', '62', '63', '64', '65', '66', '67', '68', '69', '6a', '6b', '6c', '6d', '6e', '6f', '70', '71', '72', '73', '74', '75', '76', '77', '78', '79', '7a', '7b', '7c', '7d', '7e', '7f']:
        push_size = int(bytecode[i:i+2], 16) - 0x5f
        i += 2 + push_size * 2
    elif bytecode[i:i+2] in ['80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '8a', '8b', '8c', '8d', '8e', '8f']:
        i += 2
    elif bytecode[i:i+4] not in ['0000', ''] and len(bytecode[i:i+4]) == 4:
        selectors.add(bytecode[i:i+4])
        i += 4
    else:
        i += 2
for s in sorted(selectors):
    print(s)
" "<bytecode>"

# Then lookup on 4byte.directory
for sel in $(cat selectors.txt); do
  curl -s "https://www.4byte.directory/api/v1/signatures/?hex_signature=$sel" | jq '.results[].text_signature'
done
```

### 5. Storage Slot Analysis

**Read key storage slots (0-20):**
```bash
for i in $(seq 0 20); do
  slot=$(printf "0x%064x" $i)
  echo -n "Slot $i: "
  curl -s -X POST https://arb1.arbitrum.io/rpc \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getStorageAt\",\"params\":[\"<contract>\",\"$slot\",\"latest\"],\"id\":1}" | jq -r '.result'
done
```

**Look for:**
- Owner/admin addresses (non-zero values)
- Token addresses
- Oracle addresses
- Boolean flags (0x01, 0x00)

### 6. Function Signature Matching

**Common dangerous selectors to look for:**

| Selector | Function | Risk |
|----------|----------|------|
| `0x38a6c2a9` | `getPrice()` | Oracle manipulation |
| `0x1f00ca74` | `setPrice(uint256)` | Owner-controlled price |
| `0x4825cf63` | `updatePrice(uint256)` | Price manipulation |
| `0x3659cfe6` | `upgradeTo(address)` | Upgrade risk |
| `0x4f1ef286` | `upgradeToAndCall(address,bytes)` | Upgrade + init |
| `0x715018a6` | `renounceOwnership()` | Ownership change |
| `0xf2fde38b` | `transferOwnership(address)` | Ownership transfer |
| `0x8da5cb5b` | `owner()` | Read admin |
| `0x3f4ba83a` | `pause()` | Emergency pause |
| `0x3f4ba83b` | `unpause()` | Emergency unpause |
| `0x3912f93c` | `withdraw(uint256)` | Fund withdrawal |
| `0xd0e30db0` | `deposit()` | Deposit |
| `0x2e1a7d4d` | `withdraw(uint256)` | Withdraw |

### 7. Critical Findings Checklist

**When auditing unverified contracts, always check:**

- [ ] **Implementation exists?** If no → all calls revert
- [ ] **Admin slot set?** If zero → initialization attack possible
- [ ] **Timelock present?** If no → immediate upgrade possible
- [ ] **Multi-sig admin?** If EOA → single key compromise = total loss
- [ ] **Pause mechanism?** If no → no emergency response
- [ ] **Owner-only withdraw?** If yes → admin can drain funds
- [ ] **Upgradeable?** If UUPS → admin can change logic
- [ ] **Reentrancy guards?** Check for OpenZeppelin ReentrancyGuard
- [ ] **Oracle addresses?** Check if Chainlink or custom
- [ ] **Cross-chain relayers?** Check message verification

---

## Common Findings

### 🔴 CRITICAL: Empty Admin + No Implementation

```
Proxy: 0x... (EIP-1967)
Implementation: 0x... (NO CODE)
Admin: 0x0000000000000000000000000000000000000000

Impact: 
- All calls to proxy revert (no implementation)
- If implementation deployed later, admin can upgrade to malicious code
- Empty admin slot allows initialization attack
```

### 🔴 CRITICAL: EOA Admin, No Timelock

```
Admin: 0x<EOA address>
Timelock: None

Impact:
- Single private key compromise = total fund loss
- Immediate upgrade to malicious implementation
- No grace period for user response
```

### 🟠 HIGH: Custom Oracle, Owner-Controlled

```
Oracle: Custom contract at 0x...
setPrice(): Owner-only, no timelock

Impact:
- Owner can manipulate price instantly
- Can trigger unfair liquidations
- Can inflate collateral value
```

---

## Tools

| Tool | Purpose |
|------|---------|
| `eth_getStorageAt` | Read storage slots |
| `eth_getCode` | Check bytecode |
| `eth_call` | Execute read-only functions |
| `4byte.directory` | Function signature lookup |
| `panoramix.ethereum.org` | Bytecode decompiler |
| `ethers-decompile` | NPM decompiler |
| `foundry` | Local fork testing |

---

## Reporting Template

```markdown
## Unverified Contract: [Name]

**Address:** 0x...
**Chain:** [Arbitrum/Ethereum/etc.]
**Type:** [Proxy/Implementation/Factory/Vault]

### Bytecode Analysis

**Function Selectors Found:**
- 0x... → `functionName()` 
- 0x... → `functionName(uint256)`

**Storage Slots:**
- Slot 0: 0x... (owner/admin)
- Slot 1: 0x... (token address)
- Slot 2: 0x... (oracle address)

### Findings

**[Severity]: [Title]**
- Evidence: [selector/storage/bytecode finding]
- Impact: [what attacker can do]
- PoC: [steps to verify]
```

---

*Methodology developed from t3tris.finance audit session, July 2026*
