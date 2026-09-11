# Gimo Finance 0G LSaaS Misconfig — 2026-08-12

## Targets
- Web2: `gimofinance.xyz` / `app.gimofinance.xyz` / `docs.gimofinance.xyz` → `178.105.11.156` nginx/1.24 (Ubuntu), Next.js static export `etag 6a58f7c9`
- Web3: 0G mainnet chainId 16661 `https://evmrpc.0g.ai` (alt testnet 16602 `https://evmrpc-testnet.0g.ai`)
- Contracts: `st0G` `0x7bBC63D01CA42491c3E084C941c3E86e55951404` (LsdToken), proxy `0xAc06d1Df23a4Fa00981aFAC0f33A5936Bd2135aF` → impl `0x7A5e1b999a665f2b89e5f6eAE32dF9471De193C7` (16745B, 57 selectors), bonded pool `0x136b56554671976ef8366b01b31185f91ae696af` → impl `0x377db28b688e7fd84bb99a6a8f8f1084a33bb512`, Staking `evm-staking-contracts` fork

## Live snapshot (proven via eth_call/eth_getStorageAt)
- `rate 0x12668ba79fc56de3 = 1.325900692363505e18`, `minStake 0x2386f26fc10000 = 1e16 (0.01 0G)`, `totalSupply 0xbd3758aa1ba54db1061cb = 14,296,771 st0G`
- `eraSeconds 0x15180=86400`, `eraOffset 0x4f7b=20347`, `currentEra 329`, `latestEra 329`, `unbondingDuration 3`
- `owner 0x3007306646AC90a647BebC9Acc029c941dB5B0Fb` (EOA, single), `protocolFeeCommission 1e17 (10%)`, `totalProtocolFee 0x1e6ec8e78362ea07a25b ~143k st0G`
- `newEra() 0x7b207727` → `0xfd8f8078 EraNotMatch()` until `currentEra >= latestEra+1` (86400s window)

## Source: evm-lsd-contracts fork
Upstream: `stafiprotocol/evm-lsd-contracts` (branch main, 2025-12-15) — `staking/StakeManager.sol` is exact Gimo model:
- `initialize(_lsdToken,_poolAddress,_owner,_factory)-> _initManagerParams(..., unbondingDuration, rateChangeLimit)` — Gimo passes `rateChangeLimit=0`
- `Rate.sol: _setEraRate()` → `if(rateChangeLimit>0){ rateChange*1e18/rate > rateChangeLimit => revert } rate=_rate` → when 0, NO check (bypasses `MAX_RATE_CHANGE_LIMIT 5e15 = 0.5%`)
- `StakeManager: stakeWithPool(_stakeAmount*1e18/rate)`, `unstakeWithPool(_lsd*rate/1e18)`, `newEra() permissionless { currentEra < latestEra+1 revert EraNotMatch; claim+withdraw+stake/unstake pending; _distributeReward(totalNewReward,rate) → ILsdToken.mint; newRate=_calRate(newTotalActive, totalSupply); _setEraRate }`
- `LsdToken.sol: getRate() → IRateProvider(minter).getRate()` delegates to StakeManager
- `Staking.sol` (evm-staking-contracts): `getTotalStaked() = getUserInfo(poolId,pool).amount + pendingBond` — accounting, not `address.balance`

## Proxy storage map (EIP-1967)
- `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc -> 0x7A5e1b...193C7` (impl), `0xb531...06103 -> 0x0` (admin via proxy owner)
- Proxy slots (Manager layout): `0: packed owner 0x3007...0Fb + init 0x01`, `2: 0x15180`, `3: 0x4f7b`, `4: 0x149 (latestEra)`, `5: rate`, `7: rateChangeLimit 0x0`, `8: 0x2386... (minStake)`, `16: lsdToken 0x7bBC...`, `17: 0x16345... (protocol fee)`, `18: rate dup`
- Pool `0x136b...` impl slot same EIP-1967 → `0x377db28b688e7fd84bb99a6a8f8f1084a33bb512`; pool code 14864B; slots 0-11 mostly 0 (UUPS proxy, storage in impl)
- Token slots: `3: name 0x47696d6f...1c`, `4: symbol 0x73743047...08`, `5: minter 0xAc06...`

## Selectors (57 PUSH4)
Key: `679aefce getRate()`, `2c4e722e rate()`, `f1887684 minStakeAmount()`, `8da5cb5b owner()`, `a694fc3a stake(uint256)`, `2e17de78 unstake(uint256)`, `3ccfd60b withdraw()`, `1525be32 stakeWithPool(address,uint256)`, `b608b458 unstakeWithPool`, `f737abac withdrawWithPool`, `7b207727 newEra()`, `3659cfe6 upgradeTo(address)`, `4f1ef286 upgradeToAndCall`, `54fd4d50 version()=1`, `e81f1553 eraSeconds`, `c8c20263 eraOffset`, `ccf6802a unbondingDuration`, `973628f6 currentEra`, `3f6f5f32 latestEra`, `a6645fdd lsdToken()`, `88611f35 totalProtocolFee()`, `19301c26 protocolFeeCommission()`
- Pool impl selectors: `91... getTotalStaked()` fail on pool proxy (needs Staking context) — matches pendingBond logic

## Trust graph
```
User --stake/unstake/withdraw--> StakeManager UUPS Proxy (onlyOwner=0x3007...)
 |  rate slot5, minStake slot8, lsdToken slot16
 |  ILsdToken.mint/burn via minter
 +-- newEra() ANYONE (era-gated) --> Staking.claim/withdraw + _distributeReward (mint) + _calRate(totalActive*1e18/totalSupply) + _setEraRate (NO CAP when limit=0)
 +-- upgradeTo(address) onlyOwner EOA
Pool 0x136b... --IStaking--> Staking.sol (amount+pendingBond) -- accounting, not balance
Relay (docs: decentralized, permissionless) = same newEra race as attacker
```

## Chainer: why HIGH not CRITICAL, why no web2 RCE
- **Chain:** Era flip → anyone `newEra()` → `_calRate` arbitrary (limit 0) → `getRate` inflated → `unstake` extra `0G` → `withdraw` after 3 eras. Needs era window + pre-inflation via `pendingBond` grief (stake just-before to bloat `totalActive`). Donation via `selfdestruct` does NOT inflate (accounting defense → Stall=Block on Theory B). Theft per st0G = `(newRate-oldRate)/1e18` 0G; at 1.32->2.0 = 51% extra. `totalProtocolFee` already shows mint path works.
- **Web2:** `app` is `next export` (no SSR): `/_next/static/chunks/pages/index-bf4950ab66bef452.js` `fetch((0,f.j9)())` → coingecko `binancecoin` price only; `curl -I` + `/_next` probe → 404 on `/api`, `/.env`, `/.next`, `/graphql`; `x-middleware-subrequest` not applicable (static). Correctly marked BLOCKED per CDC Stall=Block (no 2nd round evidence), not forced.
- **Upgrade centralization:** `upgradeTo` is `onlyOwner` single EOA → instant takeover if key leaked; no `TimelockController`. Separate HIGH finding, not chained to rate theft unless key compromise.

## Mitigation
- `initialize(..., 5e15)` not `0`; enforce cap even when `0` (`require(newRate <= old*1005/1000)`)
- Gate `newEra` to `onlyDelegationBalancer` or `onlyOwner` + timelock, or add `rateChangeLimit` invariant
- Cap `pendingBond` contribution in `_calRate` or snapshot `totalActive` pre-pendingBond
- Replace EOA `0x3007...` with `Timelock 48h + multisig 3/5` for all `onlyOwner` (upgrade/addPool/setRate)

## Recon recipe (0G)
- RPC `https://evmrpc.0g.ai` requires `Content-Type: application/json` + `User-Agent: Mozilla/5.0`, `timeout 12-15s`, throttle `0.6-0.7s` between `eth_call/getCode/getStorageAt`, `1.0-1.2s` between `eth_getLogs` 100k windows; `curl` 403 → `python urllib.request` fallback
- EIP-1967 impl: `eth_getStorageAt(proxy, 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc)` → last 20 bytes = impl
- `git clone https://` fails `remote-https` missing → `curl -L https://github.com/<org>/<repo>/archive/refs/heads/main.zip -o /tmp/x.zip && unzip -q`
- Static export detection: `etag 6a58f7c9`, `buildId sPTMvTljk... nextExport:true`, `/_next/static/chunks` only price fetch → no SSR RCE
- Error selectors: `0xfd8f8078 EraNotMatch()`, `0x2af07d20 CallerNotAllowed()`, `0x6098ba0a RateChangeExceedLimit`

## POC (live eth_call)
See SKILL.md POC block — `sel()` via `Crypto.Hash.keccak`, verify `rateChangeLimit 0x0`, `newEra 0xfd8f8078`, `owner 0x3007...`, `token getRate`.

## References
- `/tmp/impl_full.hex` (33492), `/tmp/pool_impl.hex` (14864), `/tmp/token.hex`
- `evm-lsd-contracts/contracts/base/Rate.sol:25-41`, `staking/StakeManager.sol`, `LsdToken.sol`, `Staking.sol` (evm-staking-contracts)
- Live RPC snapshot 2026-08-12 block `41370xxx`, era 329
