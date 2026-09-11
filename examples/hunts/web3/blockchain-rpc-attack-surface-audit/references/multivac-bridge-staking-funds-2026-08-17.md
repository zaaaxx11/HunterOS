# MultiVAC Bridge/Staking Fund Exposure — 2026-08-17

## Context
After CDC 4-agent audit of mtv.ac ecosystem, bridge/staking addresses were extracted from explorer JS and verified live via `eth_getBalance` + `eth_getCode`. All addresses are EOAs (no smart contract code) — private key holders control funds directly.

## Addresses and Balances (verified via rpc.mtv.ac)

| Address | Role | Code | Balance (wei hex) | Balance (MTV) | USD (~$0.0001) |
|---------|------|------|-------------------|---------------|-----------------|
| `0xAAAA3eE85d58fb0b8A38b57Ce97B11321152c5b3` | MTV Bridge | 0x (EOA) | 0x3485a3cffd6ffe74841b | 248,028 | ~$25 |
| `0xBE20Fb1bcAD2F3dAbA3339CC631e91b17519720a` | BEP20 Bridge (BSC) | 0x (EOA) | 0xa9fc24b21a6e81b8f9e69d | 205,499,177 | ~$20,550 |
| `0xEC20d16450081d544A8002eD7fBf08BcF718E3E0` | ERC20 Bridge (ETH) | 0x (EOA) | 0x10dee7d05367070806cf430 | 326,327,275 | ~$32,633 |
| `0x000000007b46d81c9c1d6993aa5ff8233ceb16ee` | Staking Pool | 0x (EOA) | 0xac9222774a1bd1863444a3d | 3,338,005,476 | ~$333,801 |
| `0x6226e00bCAc68b0Fe55583B90A1d727C14fAB77f` | ERC20 Token Contract ref | 0x (EOA) | 0x170db1775df847e5d566 | 108,867 | ~$11 |
| `0x8aa688ab789d1848d131c65d98ceaa8875d97ef1` | BEP20 Token Contract ref | 0x (EOA) | 0x28d3cc4a3fab101d4360e | 184,093 | ~$18 |

**TOTAL EXPOSURE: ~3,873,080,000 MTV (~$387K USD)**

## Fund Flow (verified via explorer /transaction/list)
Bridge address `0xAAAA3eE...` has 3 transactions:
1. `0xd36d9c4d...` → `0xAAAA3eE...` | 10,340 MTV (user deposit)
2. `0xd36d9c4d...` → `0xAAAA3eE...` | 9,000 MTV (user deposit)
3. `0xd36d9c4d...` → `0xAAAA3eE...` | 2,148 MTV (user deposit)
4. `0xAAAA3eE...` → `0x0000007b46...` | 1,064,906,141 MTV (bridge→staking transfer)
5. `0xae10f0d2...` → `0xAAAA3eE...` | 1,064,906,141 MTV (bridge incoming)

Flow: `User → 0xAAAA3eE (Bridge) → 0x0000007b46 (Staking pool)`

## Staking API Endpoints (from staking.js)
- `POST /stake/withdraw` — accepts `address`, `timestamp`, `msg`, `sign` (form-encoded)
- `POST /stake/cancelWithdraw` — accepts same params
- `POST /stake/count` — returns total staked amount (3,014,325,205 MTV)
- `POST /stake/tops` — returns top stakers
- `POST /stake/updateStaker` — returns staker status for an address

## Unlocked Account Staker Status
- Address: `0x2781bcbdad5c702eb9258d82ac32a94f3db95e69`
- `stakerStatus: 1` (registered staker)
- `stake.balance: 0`, `stake.mainnet: 0`, `stake.erc20: 0`, `stake.bep20: 0`
- `withdrawPending: 0`, `withdrawSuccess: 0`
- **Armed but not immediately exploitable** — 0 stake balance means nothing to withdraw.

## Signing Oracle → Staking Withdraw Chain
```
eth_sign(account, message) → forged signature
→ POST /stake/withdraw { address, timestamp, msg, sign }
→ Backend verifies signature matches account owner
→ If account has stake balance → withdraw processes
→ Funds move to attacker address
```
**Blocked by:** 0 stake balance on the unlocked account. If the account ever receives stake (faucet, mining reward deposit, manual stake), the signing oracle enables forged withdrawal.

## hex → decimal conversion
```python
balances = {
    'Bridge 0xAAAA3eE...': '0x3485a3cffd6ffe74841b',
    'Staking 0x0000007b46...': '0xac9222774a1bd1863444a3d',
    'BEP20 Bridge 0xBE20Fb...': '0xa9fc24b21a6e81b8f9e69d',
    'ERC20 Bridge 0xEC20d1...': '0x10dee7d05367070806cf430',
}
for name, hex_val in balances.items():
    wei = int(hex_val, 16)
    mtv = wei / 10**18
    print(f'{name}: {wei:,} wei = {mtv:,.2f} MTV')
```
