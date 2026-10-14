# Bytecode-Only On-Chain Fuzzing (No Source Code)

Technique for probing smart contracts when source code is unavailable or unverified
on the explorer. Uses `cast` + `web3.py` to extract everything from on-chain bytecode.

## When to Use
- Contract NOT verified on explorer (BSCScan, Etherscan)
- API key unavailable or V1 deprecated
- Cloudflare blocks scraper
- Need fast, independent analysis without waiting for verification

## Tool Stack
```bash
cast --version  # >= 1.7.1
pip install web3
```

## Workflow: 4-Phase Iterative Probing

### Phase 1: Basic Recon (`fuzz_naoris.py`)
1. **EIP-1967 slot check** — confirm proxy pattern
   ```bash
   cast storage <PROXY> 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
   cast storage <PROXY> 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
   ```
2. **Call standard ERC20 functions** via `eth_call` (name, symbol, decimals, totalSupply, balanceOf)
3. **Probe extended function selectors** — build a list of 30+ known selectors (AccessControl, UUPS, Pausable, Governance, etc.) and try each via `eth_call`
4. **Storage slot scan** — read slots 0-50, classify as address-like or integer

### Phase 2: Deep Bytecode Analysis (`fuzz_deep.py`)
1. **Extract PUSH4 selectors** from implementation bytecode:
   ```python
   import re
   impl_code = w3.eth.get_code(IMPL).hex()
   push4_selectors = set(re.findall(r'63([0-9a-f]{8})', impl_code))
   ```
2. **Match against known selectors** — build a dictionary of known 4-byte selectors
3. **Call implementation directly** — check if storage is proxy-backed (impl returns 0)
4. **Count opcodes** — SELFDESTRUCT (`ff`), DELEGATECALL (`f4`), CREATE2 (`f5`)

### Phase 3: Edge Case Testing (`fuzz_edge.py`)
1. **Token edge cases** — simulate `transfer(0)`, `transfer(MAX)`, `transfer(to self)`, `approve(MAX)`, `transferFrom(0)` via `eth_call`
2. **Governance probing** — try all Governor/Delegation/Votes selectors
3. **UUPS edge cases** — `upgradeToAndCall(address(0))`, `proxiableUUID()` via impl
4. **Decode revert reasons** via `cast 4byte`:
   ```bash
   cast 4byte 0x96c6fd1e  # ERC20InvalidSender
   cast 4byte 0xe2517d3f  # AccessControlUnauthorizedAccount
   ```
5. **Storage collision check** — verify EIP-1967 slots don't overlap with implementation slots

### Phase 4: Final Verification (`fuzz_final.py`)
1. **ERC20Permit** — check `DOMAIN_SEPARATOR`, `nonces`, `permit`, `eip712Domain`
2. **ERC165** — test `supportsInterface` for IERC20, IERC721, IAccessControl, etc.
3. **Pausable/Burnable/Capped** — try `paused()`, `burn()`, `cap()`
4. **Initializer check** — test all `initialize()` variants for unprotected re-init
5. **Tax/Reflection scan** — check for known DeFi tax selectors in bytecode
6. **Kill/Destroy scan** — check for `kill()`, `destroy()`, `suicide()` selectors

### Phase 5: AccessControl & Role Scanning (`fuzz_roles.py`)
When the contract uses OpenZeppelin AccessControl, roles may be stored in ERC-7201
namespaced storage (OZ v5.0+) or sequential storage (OZ v4.x). Try both approaches.

1. **Detect OZ version** — call `UPGRADE_INTERFACE_VERSION()` (selector `0xad3cb1cc`).
   If it returns `"5.0.0"` → ERC-7201 namespaces. If it reverts → OZ v4 sequential.

2. **Compute OZ v5 ERC-7201 AccessControl namespace**:
   ```python
   from hashlib import new
   def keccak256(data): return new('sha3_256', data).digest()
   # OZ v5 AccessControl storage namespace
   AC_STORAGE = keccak256(b'openzeppelin.storage.AccessControl')
   # _roles[role] = keccak256(abi.encode(role, AC_STORAGE))
   role_slot = keccak256(role_hash + AC_STORAGE)
   ```

3. **Brute-force role discovery** — iterate base slots 0-100 for each role hash:
   ```python
   for base in range(100):
       encoded = role_hash + base.to_bytes(32, 'big')
       slot = '0x' + keccak256(encoded).hex()
       val = w3.eth.get_storage_at(PROXY, slot)
       if val != '0x' + '00'*32:
           print(f'FOUND role at base {base}: {val}')
   ```
   The adminRole for each role is stored at this slot. If non-zero, the role exists.

4. **Find role members** — members[address] = keccak256(abi.encode(address, role_slot + 1)):
   ```python
   members_slot = (int(role_slot, 16) + 1).to_bytes(32, 'big')
   for addr in candidate_addresses:
       encoded = bytes(12) + bytes.fromhex(addr[2:]) + members_slot
       member_slot = '0x' + keccak256(encoded).hex()
       val = w3.eth.get_storage_at(PROXY, member_slot)
       if val[-1] == '1':  # boolean true
           print(f'{addr} has role')
   ```

5. **Call `getRoleAdmin(bytes32)` for each role** — confirms the role hierarchy
   without needing to find the storage slot.

6. **Check `DEFAULT_ADMIN_ROLE()` constant** (selector `0xa217fddf`) — if it returns
   `0x00...00`, DEFAULT_ADMIN is the root of all roles.

7. **Role-to-role mapping**:
   ```bash
   # Check role admin for each role
   cast call $PROXY "getRoleAdmin(bytes32)(bytes32)" $ROLE_HASH --rpc-url $RPC
   # Returns 0x00...00 = DEFAULT_ADMIN_ROLE
   ```

### Phase 6: UUPS Upgrade Authorization Analysis
1. **Check if UPGRADER_ROLE exists** — call `getRoleAdmin(UPGRADER_ROLE_HASH)`.
   If it reverts, UPGRADER_ROLE is not defined → upgrade auth falls back to
   DEFAULT_ADMIN_ROLE or a custom override.

2. **Check `proxiableUUID()`** — if it reverts when called on the proxy, the
   implementation uses ERC-7201 UUPS storage (OZ v5). Call it on the
   implementation directly to verify.

3. **Check `UPGRADE_INTERFACE_VERSION()`** — returns the OZ version string
   (e.g., `"5.0.0"`). This confirms the UUPS implementation variant.

4. **Analyze the upgrade authorization path**:
   - If no UPGRADER_ROLE + DEFAULT_ADMIN_ROLE is `0x0` → admin may be renounced
   - If admin is renounced → contract is frozen (can't upgrade)
   - If admin is active → single-key compromise = full takeover
   - Check for timelock or multisig by looking at role holder address type

5. **Governance detection** — systematically check for ERC20Votes and Governor
   selectors in the bytecode:
   ```python
   governance_selectors = {
       '7b3c71d3': 'delegate(address)',
       '5c19a95c': 'delegateBySig(...)',
       '3e4eea9d': 'delegates(address)',
       '382d5ab1': 'getVotes(address)',
       'b58131b0': 'propose(...)',
       '7d5e81e2': 'castVote(uint256,uint8)',
       '3bccf4fd': 'execute(...)',
   }
   ```
   If NONE of these exist in the bytecode → token has no on-chain governance.
   Governance would be off-chain (Snapshot) or in a separate contract.

## Common Pitfalls

### P1: BSCScan API V1 Deprecated
V1 returns `"You are using a deprecated V1 endpoint"`. Use V2 with `chainid=56` or skip the API entirely — `cast` + `web3.py` is sufficient for all analysis.

### P2: Checksum Addresses
`web3.py` requires checksum addresses. Always use `Web3.to_checksum_address()`:
```python
PROXY = Web3.to_checksum_address("0x1b379a79c91a540b2bcd612b4d713f31de1b80cc")
```

### P3: web3.py ABI Format
Must use JSON ABI (list of dicts), NOT human-readable signatures:
```python
# WRONG:
ERC20_ABI = ["function name() view returns (string)", ...]
# CORRECT:
ERC20_ABI = [{"constant": True, "inputs": [], "name": "name", ...}, ...]
```

### P4: Selector Encoding
When building raw calldata for `eth_call`, encode arguments correctly:
- `address`: 32 bytes, left-padded with zeros
- `uint256`: 32 bytes, left-padded with zeros
- `bytes32`: 32 bytes as-is
- Dynamic types (`bytes`, `string`): offset + length + data

### P5: False Positive SELFDESTRUCT
UUPS contracts contain 100+ SELFDESTRUCT opcodes in the upgrade path. This is NORMAL — the old implementation selfdestructs after upgrade. It's only exploitable if there's a direct `kill()`/`destroy()` function or if the upgrade path is unauthenticated.

### P7: OZ v5 ERC-7201 Storage Namespace Blindness
When scanning storage for AccessControl roles, OZ v5 uses ERC-7201 namespaced storage
(`keccak256("openzeppelin.storage.AccessControl")`) instead of sequential slots.
If you only scan sequential slots 0-50, you'll miss ALL role assignments. Always:
1. Call `UPGRADE_INTERFACE_VERSION()` to detect OZ version
2. If v5+, compute the namespace hash and use it as the base for `_roles[role]`
3. The namespace hash is NOT the slot number — it's a 32-byte key for the
   `keccak256(abi.encode(role, namespace))` computation
4. If all slots return 0, try both v4 sequential AND v5 namespace approaches

### P8: Explorer API Deprecation Loop
BSCScan v1 API returns `"You are using a deprecated V1 endpoint"` for ALL endpoints.
V2 API (`/v2/api?chainid=56`) returns 404 on many endpoints. Workarounds:
- Use `cast` + `web3.py` for all analysis (no API dependency)
- Use `eth_getLogs` on RPC directly (beware rate limits on public nodes)
- Try Blockscout explorer instances as alternative (`blockscout.com`)

## Output Format
Generate a markdown report with:
1. Contract summary table (name, symbol, type, features detected)
2. Per-category edge case tables with simulation results
3. Revert reason decoding
4. Storage layout map
5. Final summary table with severity ratings

## Indonesian Communication Style
- Tone: Casual technical ("lo/elu", "bro", "gak", "aman", "bahaya")
- Format: Tables, bullets, code blocks
- Emojis: ✅ ❌ ⚠️ 💀 🔒 🚫
- Direct, no fluff, straight to findings