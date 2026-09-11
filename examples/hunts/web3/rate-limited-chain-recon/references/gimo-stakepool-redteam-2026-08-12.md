# Gimo StakePool Red-Team 0G 2026-08-12 — Session Detail

Source: conversation `StakePool 0x7A5e… via proxy 0xAc06…` — cast disassemble + live `evmrpc.0g.ai` (16661).

## Live Snapshot
- Proxy 0xAc06d1Df23a4Fa00981aFAC0f33A5936Bd2135aF 178B `DELEGATECALL` to `SLOAD(0x360894a13…bc)` → impl 0x7A5e1b999a665f2b89e5f6eAE32dF9471De193C7 16745B
- st0G 0x7bBC63D01CA42491c3E084C941c3E86e55951404 totalSupply 14296771602173362179170763
- Owner slot0 `0x3007306646AC90a647BebC9Acc029c941dB5B0Fb` (bytes10-29, byte31 0x01 initialized)
- Views: rate 1.3259e18 (slot5), era 329, unbond 3 (0xccf6802a), totalProtocolFee 143714e18, rateChangeLimit 0
- Upgraded events: 5065775→0xd0c85d62…, 25708823→0x7A5e… (owner 0x3007… nonce 73), no timelock

## Selector→JUMPDEST Map (cast disassemble)
- `46f45b8d stake(string)` → 0x0599 → 0x0f9c → 0x1360 (CALLVALUE non-zero, 0x39c3 validator decode, minStake 0x2386f26fc10000)
- `2e17de78 unstake(uint256)` → 0x04cb → 0x0e35 → 0x0e4a → 0x1146 (keccak 0x77 mapping)
- `3ccfd60b withdraw()` → 0x054e → SELFBALANCE @0x363f LT→0x369c CALL @0x36c5
- `3659cfe6 upgradeTo` → 0x0518 → 0x0e74 (SLOAD 0>>160 == CALLER) → 0x2b1f → 0x322d5 (EXTCODESIZE + STATICCALL proxiableUUID 0x52d1902d)
- `7b207727` relay → 0x0741 → 0x16fb + 0x1d47 owner checks → 0x1eba/0x1eec isRelay mapping 0x0b/0x77

## Rate Formula
`Cr=(Qstk-Qred+Qrew*(1-Rcom))/(M-N)`; `M-N = st0G.totalSupply`; `Qstk` is `SLOAD` not `SELFBALANCE` (SELFBALANCE only at 0x363f withdraw). Python:
```py
def calc_cr(Qstk,Qred,Qrew,Rcom_bps,M,N):
    num=Qstk-Qred+Qrew*(10000-Rcom_bps)//10000
    den=M-N
    return 10**18 if den==0 else num*10**18//den
```
Donation spike sim (10 A0G on 800-share pool): stored model Cr 1.25→1.25 safe; balance model 1.25→1e19 dusts victim 100A0G→9 wei.

## Disasm Signatures to Grep
- `SLOAD 0x00 >>160 == CALLER` = onlyOwner
- `keccak(CALLER.0x03)` = hasRole / isRelay
- `SLOAD 0x4910fdfa… & 0xff ISZERO` = reentrancy guard (present on withdraw/upgrade, missing on stake prefix)
- `CALLVALUE`@0x21e4 vs `5000…` LT, `SLOAD 0x05`@0x2007 rate, `PUSH8 0x0de0b6b3a7640000` scaling
- `SELFBALANCE LT 0x369c` then `GAS CALL` = withdraw payout (reentrancy lead)

## Leads to Fuzz
1. withdraw reentrancy `receive(){ withdraw(); }` after unstake 3 eras
2. relay arbitrary Cr when limit 0 → stake cheap then inflate
3. hidden selectors 0x62b8e169/0xfd852c1b/0xaf737e60 as attacker
4. upgradeTo vs upgradeToAndCall auth delta
5. `cast storage` map slots 0b/77/0f for relay enumeration
