# Qtum Smart Contract Hunt 2026-08 — Bridge + Offline Staking

## Scope
- `qtumproject/bridge-evm-contracts` (UUPS upgradeable multi-sig bridge: Bridge.sol, Signers.sol, PauseManager.sol, ERC20/721/1155/Native handlers)
- `qtumproject/offline-staking-contract` (offline-staking.sol, live at `0x86`, 5,113 tx, consensus-critical)

## Reality check — bridge = GHOST (do this FIRST)
USDC token on Qtum mainnet (`dc62350ddd32adb6e2f000fc80185eadf169e134`):
- `totalSupply = 18446744073709551615` = `2**64-1` sentinel, not real
- 6 holders, 7 total transactions
- 1 address holds ~all of the sentinel supply
- Bridge repo has `deploy/` migrations but no deployed proxy address anywhere
**Verdict:** pre-launch / ghost. Economic exploit work skipped. Only consensus/admin logic worth reviewing.

## Offline staking `0x86` — PoD signature: FALSE POSITIVE (adversarially disproven)
`verifyPoD(_PoD, _staker, _delegate)`:
```solidity
bytes memory message = toASCIIString(_staker);   // _staker param in message
bytes32 hash = sha256(abi.encodePacked(sha256(abi.encodePacked(prefix,message))));
return btc_ecrecover(hash,v,r,s) == _delegate;   // recover must equal _delegate
```
First-pass read looked like an unbound-signature hijack: `addDelegation(_staker, _fee, _PoD)` has no `_staker == msg.sender` check, and `fee`/`nonce`/`chainId` aren't in the signed payload.

**Killed by client-side evidence.** The actual signer is the electrum wallet:
`main_window.py: call_add_delegation() → pod = self.wallet.sign_message(addr, staker, password)`
where `addr` = the STAKER's own key (the wallet signing), `staker` arg = the delegate's address (the message). So in the real flow:
- signer (recovered) = staker = `msg.sender` on-chain ✓ (matches `_delegate` param being `msg.sender`)
- message = delegate address ✓ — the staker explicitly names WHICH delegate they accept

Direction is correct by design; a staker's signature is NOT reusable by an arbitrary delegate because the message IS the delegate's address. Remaining residue: `fee` and `nonce` are unbound, so a delegate could front-run a staker's pending `addDelegation` tx with a different fee — but the staker is the one broadcasting and can simply re-submit, so it's informational at best. **Verdict: NO exploitable bug. Do not re-report the "unbound PoD" theory.**

## Lesson: verify signature semantics against the PRODUCING client, not just the contract
Contract-only reasoning inverted the roles (`_staker`/`_delegate` naming is confusing in this repo). Two minutes reading the electrum caller killed a false MEDIUM/HIGH. When a signature-verify contract looks off, find the wallet/relayer/CLI that generates the signature and trace the actual `sign_message(signer, message)` arguments before writing the finding.

## Secondary: gas-burn anti-spam loop
`addDelegation` ends with `while(true){ dummy=0x0; if(gas-gasleft()>=0x1E8480) break; }` — burns ~2M gas deliberately. UX/griefing hazard (every delegation costs 2M gas to miner), not a sybil fix. Informational only.

## Bridge architecture notes (all solid, BLOCKED theories)
- `Signers._checkSignatures`: nonce + threshold + bloom-filter dedup on signer addresses — correct.
- `Hashes._checkAndUpdateHashes`: replay protection on `keccak256(txHash, txNonce)` — correct.
- `Bridge.withdrawERC20/721/1155/Native`: all gated by signature check + hash replay + `onlyNotStopped` — clean.
- `UUPSSignableUpgradeable.upgradeToWithSig[AndCall]`: `_authorizeUpgrade` requires owner-or-signer sig — clean.
- `_checkOwnerOrSignatures`: when `isSignersMode==false` falls back to `require(msg.sender==owner())` — owner key compromise = full takeover, but that's expected trust model, not a bug.
- DGP governance (qtum-dgp): multisig admin/gov voting with thresholds + proposal expiry — no single-key takeover path.

## Lesson
Ghost-token check saved ~1h of fake economic-exploit work. Verify holders/txs/totalSupply BEFORE writing PoC. And adversarially check signature-direction claims against the real client before reporting — a wrong-role finding is worse than no finding.
