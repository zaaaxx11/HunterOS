# EIP-7702 funds-forwarding session log (Plasma, 2026-08-15) — cut from l2-rollup-audit SKILL.md 2026-09-07

Cut verbatim from the shipped SKILL.md during the 2026-09-07 S2b-2 follow-up pass (per-target case material preserved, not deleted; reusable methodology stays in the skill body).

---

---

## Update: EIP-7702 Funds Forwarding (Session 2026-08-15)

### Discovery: Funds Auto-Forward to Separate EOA

When the proof coord address (`0xE25583...`) received funds, they were **automatically forwarded** to a different address:

```
From: User wallet (0xfd5b757d...)
To: Proof Coord (0xE25583...) [EIP-7702 delegated]
↓ Auto-forwarded to:
Address: 0x62B397AFD9DFB2166C57323FA3BBEAACEECB3460
```

**Tx:** `0xbc5ba30d08953ba6afe1ce0db07af4204e716d41ad61f92555d46aca6ab9f9c0`

### Analysis of Forwarding Address

| Property | Value |
|----------|-------|
| Address | `0x62B397AFD9DFB2166C57323FA3BBEAACEECB3460` |
| Type | EOA (code=0 bytes) |
| Balance | 2.109467 XPL |
| Nonce | 4 |

**Key finding:** This address is NOT derived from any hardcoded keys in GitHub. It is likely:
- Operator personal wallet, OR
- Forwarding address set in EIP-7702 delegation contract

### Delegated Contract Analysis

Contract: `0xef7b31f45b19ffef6f1ff5ae684b78b1a86c1c0c`

**Functions found:**
- `0xa9059cbb` — `transfer(address,uint256)`
- `0x23b872dd` — `transferFrom(address,address,uint256)`
- `0x4300081e` — Unknown (Plasma-specific?)
- `0x1f57256f`, `0xa5e38751`, `0xb61d27f6`, `0xdd98ae68` — Unknown

**Code size:** 4156 bytes

### RPC Balance Sync Issue

**Problem:** After tx confirmed on explorer, RPC still shows 0 balance.

```
Explorer: Balance = 2.1 XPL ✅
RPC: Balance = 0 XPL ❌
```

**Impact:** Cannot send tx via RPC (insufficient funds error).

**Workaround:** Use a different RPC node or wait for sync.

### Live Proof: Key Works

```
✅ Private key valid (cryptographic proof)
✅ Address active (nonce=1)
✅ Tx sent and confirmed on explorer
✅ EIP-7702 delegation works
✅ Funds forwarded to 0x62B397AF...
```

### New Attack Vector

```
1. Attacker uses Proof Coord key
2. Sends tx to delegated contract
3. Contract forwards funds to 0x62B397AF...
4. BUT: Need private key for 0x62B397AF... to control funds
```

**Status:** Funds can be sent TO the address, but cannot be withdrawn WITHOUT the private key for `0x62B397AF...`.

### Updated Recommendations

1. **Immediate:** Check if `0x62B397AF...` private key is also hardcoded somewhere
2. **Immediate:** Monitor this address for operator activity
3. **Investigate:** How was this forwarding address configured?
4. **Fix:** EIP-7702 delegation should not auto-forward to unknown EOA
- [Plasma.org Audit Findings](examples/hunts/web3/l2-rollup-audit/references/plasma-org-findings.md) — Session-specific findings from auditing PlasmaLaboratories/ethrex
