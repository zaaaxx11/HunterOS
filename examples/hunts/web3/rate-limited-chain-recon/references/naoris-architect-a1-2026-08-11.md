# Naoris Architect A1 — BSC Throttled Recon 2026-08-11

## Target
- Proxy `0x1b379a79c91a540b2bcd612b4d713f31de1b80cc` → Impl `0xc4e16e56ea3660110924cc06850120672b7e11ef` (BSC 0x38)
- Sources: `Governance.sol` 675 LOC + `Naoris.sol` 166 LOC, solidity 0.8.22, OZ upgradeable

## Live RPC (bsc-dataseed.binance.org)

### eth_getCode
- proxy: 342 hex chars (171 bytes) — minimal EIP-1967 proxy, `SLOAD 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bb` + `DELEGATECALL 0x845af43d`
- impl: 38298 hex chars (19149 bytes) — NaorisToken logic, slots 0..5 zero (uninitialized logic contract)

### PUSH4 extraction (scan 0x63)
```python
b = bytes.fromhex(hexcode[2:])
selectors = [b[i+1:i+5].hex() for i in range(len(b)-4) if b[i]==0x63]
```
- proxy: 1 total, 1 uniq `4300081d` (solc metadata, not selector) → 0 user selectors, correct for proxy
- impl: 143 total, 126 uniq — key: `06fdde03 name`, `95d89b41 symbol`, `313ce567 decimals`, `18160ddd totalSupply`, `5c975abb paused`, `91d14854 hasRole`, `e63ab1e9 PAUSER_ROLE()`, `52d1902d proxiableUUID`, `a217fddf DEFAULT_ADMIN_ROLE`, `248a9ca3 getRoleAdmin`
- comparison: common 0, only_proxy 1, only_impl 126 → thin dispatcher confirmed

### eth_getStorageAt
- proxy slot0 `0x...033b2e3c9fd0803ce8000000` = 1e27 (cap/packed)
- proxy slot1 `0x...49490a9d97c0bb7db0a62b` = 88596513408315047887808043 = 88.59M (live totalSupply, not 4B)
- erc1967 impl slot `0x3608...2bb` → `0x00..00` on public RPC (pruned); `latest-1000` → `-32000 missing trie node`
- impl slots 0..5 all zero

### eth_call (correct keccak)
Hashes verified via `Crypto.Hash.keccak`:
- PAUSER `0x65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a`
- DEFAULT `0x00..00`, MINTER `0x9f2df0fe...`, UPGRADER `0x189ab7a9...` (last two unused)
- hasRole encoding: `0x91d14854` + 32B role + 32B padded addr
- Results via proxy: `name Naoris Protocol`, `symbol NAORIS`, `decimals 18`, `totalSupply 88.59M`, `paused false`, `PAUSER_ROLE() 0x65d7..`, `hasRole(PAUSER,0x00) false`, `hasRole(DEFAULT,0x00) false`, `getRoleMemberCount` reverts (no Enumerable), `cap()` reverts (no getter), `owner()` reverts (AccessControl not Ownable)
- Via impl directly: totalSupply 0, paused 0 — storage isolation confirmed

## Throttle Reality (stricter than Sonic)
| RPC | Window | Result |
|-----|--------|--------|
| eth_getLogs no filter 5k/10k/20k/100k/200k | all | `limit exceeded` (-32005) even 5k |
| eth_getLogs with address+topic 10k/50k/100k | all | `limit exceeded` |
| eth_getLogs with chunk 50k-100k sequential 0.7-0.9s | all | still limit exceeded |
| eth_getProof | any | `limit exceeded` |
| eth_getStorageAt historical | latest-1000 | `missing trie node` (-32000) |
| eth_call 0.6s sequential | 1 | OK |

Conclusion: BSC public dataseed is **hard-capped** — no log enumeration without archive node / Etherscan V2. Mark BLOCKED honestly, don't fabricate. Throttle 0.6-1.2s sequential still fails → pivot required.

## Governance Invariant Checklist (second-pass)
1. `_delegate` off-by-one: `> max` should be `>=` → allows limit+1
2. Shared `totalDelegators[delegatee]` conflates global+per-proposal → double-count; `getDelegatedVoteCount` sums both
3. `castVote` only iterates `proposalDelegators`, ignores `globalDelegators` → global weight burnt
4. Lifecycle stall: Pending → Active only on first vote; zero-turnout cannot `executeProposal` (needs Active) → stuck unless cancelled
5. One-shot cleanup: `cancelledProposalDataRemoved[proposalId] bool` per-proposal not per-voter → first clean blocks others, leaves ghost `optionWeights`
6. `userConsecutiveVotes` checks `hasVoted[proposalId-1]` — id=1 checks 0 (always false)
7. External weight oracle `stakingContract.getUserTotalGovernanceWeight` — single trust boundary, CALL in loop (reentrancy if staking proxy upgrades)
8. `owner` can rotate `multiSig` instantly; `renounceOwnership` disabled; `extendVoting` arbitrary `uint32` max 3×

All gated `onlyMultisig`/`onlyOwner` → BLOCKED pre-auth, but checklist catches design bugs.

## Verdict
BLOCKED — no pre-auth chain. Firebase takeover (contact@... / <redacted>) has 0 edge to on-chain keys (grep 0x/mnemonic 0 hits). Next pivot: archive node or BscScan V2 for Upgrade/RoleGranted logs.

## Artifacts
`/tmp/naoris-a1/proxy_code.hex`, `impl_code.hex`, `proxy_push4.json`, `impl_push4.json`, `storage_*.txt`, `/tmp/naoris-a1-findings.json`, `/tmp/naoris-a1-report.md`
