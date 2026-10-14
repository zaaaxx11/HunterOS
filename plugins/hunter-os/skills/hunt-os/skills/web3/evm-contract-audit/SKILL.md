---
name: evm-contract-audit
description: "EVM contract audit against 875 hack patterns"
trigger_keywords: [audit, smart-contract, evm, solidity, diamond, proxy, defi, vulnerability, exploit, keccak, selector, eth_call, eth_getStorageAt]
tags: [smart-contract, audit, evm, diamond, proxy, defi, vulnerability, exploit, keccak, foundry, reentrancy, oracle, access-control, signature-bypass, flash-loan]
---

# EVM Smart Contract Audit Framework

Adapted from SlowMist Security Team roadmap + 875 real DeFi hack PoCs (DeFiHackLabs).

## CRITICAL: keccak256 ≠ sha3_256

Python `hashlib.sha3_256` = NIST SHA-3 (WRONG for Ethereum).
Ethereum uses **Keccak-256** (pre-NIST padding).

```python
from web3 import Web3
w3 = Web3()
selector = '0x' + w3.keccak(text="owner()").hex()[:8]
# VERIFY: owner() must = 0x8da5cb5b
assert selector == "0x8da5cb5b"
```

WRONG selectors → "Diamond: Function does not exist" = MISLEADING. Always verify `owner()` first.

## Phase 1: Contract Recon

### Get bytecode + check if contract exists
```python
code = eth_getCode(address)
# "0x" = EOA (not a contract)
# length > 2 = contract
```

### Check Diamond pattern (EIP-2535)
```
eth_call facets() selector 0x7a0ed627 → facet addresses + selectors
eth_call owner() selector 0x8da5cb5b → owner address
eth_call diamondCut(...) selector 0x1f931c1c → upgrade function
eth_call transferOwnership(address) selector 0xf2fde38b
```

### Check owner
```
eth_getCode(owner) → EOA = single key (no multisig), contract = multisig/wallet
eth_getTransactionCount(owner) → nonce (>0 = active)
eth_getBalance(owner) → balance
eth_getBalance(treasury) → funds at risk
```

### Read storage
```
eth_getStorageAt(contract, slot 0-50, "latest")
Diamond namespace: keccak256("diamond.standard.facet.storage") - 1
Look for: admin addresses, owner keys, whitelist arrays, fee configs
```

### Get verified ABI
```
Blockscout API: GET /api/v2/smart-contracts/{address}
Legacy: GET /api?module=contract&action=getabi&address={addr}
If CF blocked: use browser_exec to fetch
If unverified: decompile bytecode (Dedaub, Heimdall, ethervm.io)
```

### Extract ABI from frontend JS bundle
```python
import re, json
for m in re.finditer(r"JSON\.parse\('\{\"abi\":(\[.*?\])\}'", bundle):
    abi = json.loads(m.group(1))
```

### Compute correct selectors for all functions
```python
from web3 import Web3
w3 = Web3()
for item in abi:
    if item['type'] == 'function':
        sig = f"{item['name']}({','.join(i['type'] for i in item['inputs'])})"
        sel = '0x' + w3.keccak(text=sig).hex()[:8]
```

### Read all state via eth_call
```python
ZERO_ADDR = "0x0000000000000000000000000000000000000000"
ZERO_UINT = "0" * 64
data = selector + ZERO_ADDR[2:] + ZERO_UINT
result = eth_call(contract, data)
# Decode: result[26:66] = address, int(result,16) = uint
```

## Phase 2: Vulnerability Classes (by frequency from 875 hacks)

### Access Control / Missing Permission (MOST COMMON 2024-2026)
**Pattern:** Missing `onlyOwner` / `onlyAdmin` / `msg.sender` check.
**Examples:** CompoundProvider ($774K), PolterFinance, MEVBot
**Test:**
```python
gas = eth_estimateGas(contract, sel + params, from="0xATTACKER")
# If gas succeeds → missing access control
# If revert with "owner"/"unauthorized" → properly gated
```

### Price Oracle Manipulation (MOST COMMON historically)
**Pattern:** Spot price from DEX reserves, manipulable via flash loan.
**Examples:** MoonwellMAMO, Atomic, edel-xstock, BonqDAO
**Attack:**
1. Flash loan large amount
2. Swap to manipulate DEX reserves (x*y=k)
3. Target reads manipulated price
4. Borrow/liquidate/mint at inflated value
5. Repay flash loan, keep profit
**Test:** Check if contract uses reserve0/reserve1 directly, TWAP window, Chainlink staleness.

### Reentrancy (CEI violation)
**Types:** Single, cross-function, cross-contract, read-only reentrancy
**Examples:** DFX Finance ($4M), Curve (Vyper bug), StarsArena
**Test:** Check external calls in write functions, state update order, nonReentrant modifier.

### Signature Verification Bypass
**Pattern:** `ecrecover` returns `address(0)` for malformed sig, unchecked.
**Examples:**
- LegendaryMoneyMonNft: ecrecover(0,0,27)=address(0)=admin → drain ($85K)
- LixirPermitDrain: dummy sig if ecrecover≠0 → drain vault
- MureDistribution, AROS, GiddyVaultV3, AzukiDAO

**Test:**
- Check ecrecover return != address(0)
- Check if signature can be null/empty
- Check EIP-712 domain includes chainId
- Check nonce used and incremented
- Check deadline/expiry enforced

### Logic Error / Business Flaw
**Examples:** Vault4626, AIDC, FractalProtocol
**Test:** Manual review, edge case testing (0, max, precision loss).

### Integer Overflow/Underflow
**Examples:** TRU, Poolz
**Test:** Check compiler version, `unchecked` blocks, require bounds.

### Flash Loan Attack
**Examples:** TermFinance, LULA, ProToken
**Test:** Can protocol logic be manipulated within single tx using borrowed funds?

## Phase 3: Diamond Pattern (EIP-2535) Specific

### Storage Layout
- Facets share Diamond's storage
- Namespaced: `keccak256("contract.name.storage") - 1`
- **Storage collision** = critical

### DiamondCut Audit
```
diamondCut(FacetCut[], address, bytes) — selector 0x1f931c1c
```
- Who can call? Test eth_estimateGas from arbitrary address
- Can non-owner replace facet with malicious implementation?

### Facet Exposure
- Map all facets + selectors via `facets()`
- Check if withdraw/admin functions exposed as facets
- Are withdraw functions deployed or omitted?

### Cross-Facet Consistency
- Can calling functions in unexpected order bypass checks?
- Are preconditions consistent across facets?

## Phase 4: Tools

### Contract Analysis
- eth_call: Read state | eth_estimateGas: Test writes
- eth_getStorageAt: Raw storage | eth_getCode: EOA vs contract
- Blockscout API: Verified ABIs + tx history
- Dedaub/Heimdall-rs/ethervm.io: Decompile bytecode
- 4byte.directory/sig.eth.samczsun.com: Selector lookup

### Transaction Analysis
- Phalcon: Call trace + balance changes
- Tenderly: Simulate/replay
- samczsun tx viewer: Storage + gas per call
- Eigenphi: DeFi tx decoding

### Testing
- Foundry: Fork mainnet + write PoC
- Hardhat: Test + debug
- Tenderly DevNet: Simulate forked network

## Phase 5: Audit Methodology

### Recon → Map → Attack → Verify
1. Recon: bytecode, ABI, owner, storage, balances
2. Map: all functions + selectors, facets, access control matrix
3. Attack: test each vulnerability class
4. Verify: Foundry PoC on forked mainnet

### Access Control Matrix
For each function: Who can call? What changes? Modifier present? Test with eth_estimateGas.

### State Machine Analysis
- Map transitions (INIT → LISTED → LOANED → EXPIRED)
- Can we skip states? Re-enter states?

### Economic Model Analysis
- What invariants hold? (supply = balances, collateral >= debt)
- Can flash loan/oracle/governance break invariant?

## Phase 6: PoC Templates (Foundry)

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;
import "forge-std/Test.sol";

contract Exploit is Test {
    function setUp() public {
        vm.createSelectFork("rpc_url", block_number);
        vm.deal(address(this), 100 ether);
    }
    function testExploit() public {
        uint256 before = token.balanceOf(address(this));
        // exploit
        assertGt(token.balanceOf(address(this)), before, "profit");
    }
}
```

### Signature Bypass
```solidity
bytes memory fakeSig = abi.encodePacked(bytes32(0), bytes32(0), uint8(27));
target.claim(token, amount, fakeSig);
```

### Reentrancy
```solidity
receive() external payable {
    if (stillProfitable) { target.withdraw(); }
}
```

## Phase 7: Vulnerability Checklists

### ERC-20/721/1155 Token
- [ ] transfer zero address check
- [ ] approve zero amount reset
- [ ] transferFrom allowance precision
- [ ] mint/burn access control
- [ ] Reentrancy in transfer (ERC-777 hooks)
- [ ] Fee-on-transfer handling
- [ ] Deflationary token handling

### Lending/Borrowing
- [ ] Reentrancy in borrow/repay/liquidate
- [ ] Oracle manipulation (spot vs TWAP)
- [ ] Collateral ratio bypass
- [ ] Self-liquidation profit
- [ ] Flash loan collateral inflation
- [ ] expireLoan missing auth
- [ ] processLoan CEI violation

### NFT Marketplace/Launchpad
- [ ] Signature replay (nonce/chainId in EIP-712)
- [ ] ecrecover address(0) bypass
- [ ] Missing expiry on offers
- [ ] buyNFT missing payment validation
- [ ] acceptNFTOffer missing auth
- [ ] Whitelist bypass (empty, merkle proof)
- [ ] addTokenMetadata accepts null signature
- [ ] update-token-minted missing ownership proof

### Diamond/Proxy
- [ ] diamondCut access control
- [ ] Storage collision between facets
- [ ] Cross-facet state inconsistency
- [ ] Fallback doesn't revert on missing function
- [ ] transferOwnership accessible from non-owner
- [ ] forceDeleteAsset accessible from non-owner
- [ ] withdrawFee/withdrawTreasury exposed as facet

## References

### Source Repos (cloned to /tmp/)
- SlowMist Roadmap: `/tmp/slowmist-roadmap/` (curated resource links)
- DeFiHackLabs: `/tmp/defihacklabs/` (875 PoC hack files + academy lessons)
- Knowledge-Base: `/tmp/slowmist-kb/` (696 audit reports + security research)

### Vulnerability Databases
- DASP Top 10: https://www.dasp.co/
- SWC Registry: https://swcregistry.io/
- Kaden: https://github.com/kadenzipfel/smart-contract-vulnerabilities
- Quillhash: https://github.com/Quillhash/Solidity-Attack-Vectors

### Best Practices
- ConsenSys: https://github.com/Consensys/smart-contract-best-practices
- Solcurity: https://github.com/transmissions11/solcurity
- SCSVSv2: https://github.com/securing/SCSVS
- OpenZeppelin: https://github.com/OpenZeppelin/openzeppelin-contracts

### Audit Reports
- SlowMist: https://github.com/slowmist/Knowledge-Base
- Code4rena: https://code4rena.com/reports
- Sherlock: https://github.com/sherlock-protocol/sherlock-reports
- Cyfrin: https://github.com/Cyfrin/cyfrin-audit-reports
- Full list: https://github.com/0xNazgul/Blockchain-Security-Audit-List

### Decompilers
- Dedaub: https://app.dedaub.com/decompile
- Heimdall-rs: https://github.com/Jon-Becker/heimdall-rs
- ethervm.io: https://ethervm.io/decompile

### Bug Bounty
- Immunefi: https://immunefi.com
- Code4rena: https://code4rena.com
- Sherlock: https://github.com/sherlock-protocol/sherlock-reports
- HackenProof: https://hackenproof.com
