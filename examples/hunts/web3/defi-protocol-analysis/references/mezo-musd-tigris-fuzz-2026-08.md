# Mezo MUSD/Tigris/Mezod Fuzz — 2026-08-16 (Agent 3 FUZZ-ENGINEER)

**Targets:** `mezo-org/mezod` (Go precompiles), `mezo-org/musd` (Liquity fork 0.8.24 OwnedUpgradeable), `mezo-org/tigris` (Velodrome fork 0.8.24), `mezo-org/ntt-bridge-musd` (Wormhole NTT ERC1967 proxy), Web2 `musd/dapp` (stub) + `tigris/dapp` (Vite)
**Task:** Hunt sinks where input reaches privileged logic — 0 amount, max uint256, overflow, delegatecall, storage collision, SSRF/SSTI
**Report:** `/root/MEZO_FUZZ_REPORT.md` — full [Trigger→Effect→Boundary] matrices

## HIGH — PriceFeed.fetchPrice (MUSD)

`musd/solidity/contracts/PriceFeed.sol:46-76`
```solidity
function fetchPrice() public view virtual returns (uint256) {
    (, int256 price, , uint256 updatedAt, ) = oracle.latestRoundData();
    require(block.timestamp - updatedAt <= MAX_PRICE_DELAY, "Oracle is stale");
    return _scalePriceByDigits(uint256(price), oracle.decimals());
}
function _scalePriceByDigits(uint256 p, uint8 d) internal pure returns(uint256) {
    unchecked { if(d<TARGET_DIGITS) return p * (10**(TARGET_DIGITS-d)); ... }
}
```
- `setOracle:37` checks `price !=0` but `fetchPrice:48` does NOT → `int256 -1` → `uint256 2^256-1` → `unchecked *1e10` wraps → fake cheap BTC price → under-collateralized troves bypass MCR/CCR in `BorrowerOperations._openTrove:651/_adjustTrove:778`.
- `block.timestamp - updatedAt` underflows on future updatedAt (0.8 revert) → DoS every BorrowerOps path; `updatedAt==0` also stale. `MAX_PRICE_DELAY=60` << Chainlink heartbeat (~1h) → 61s liveness DoS.
- `setOracle:30` onlyOwner, no timelock.
- Fix: `require(price>0)` before cast, remove `unchecked` or guard, `updatedAt<=block.timestamp` check, raise delay to 3600, gate setOracle.

## MEDIUM — Pool.initialize front-run (Tigris)

`tigris/solidity/contracts/Pool.sol:78`
```solidity
function initialize(address _token0,address _token1,bool _stable) external {
    if(factory!=address(0)) revert FactoryAlreadySet();
    factory=_msgSender(); _voter=IPoolFactory(factory).voter();
```
Only `factory==0` guard, no `initializer` → front-run `PoolFactory.createPool` to poison voter or brick (FactoryAlreadySet DoS). Impl contract itself open even as clone impl → `constructor(){factory=address(1);}`.

## MEDIUM — Router UNSAFE no-slippage (Tigris)

`tigris/solidity/contracts/Router.sol:403`
```solidity
function UNSAFE_swapExactTokensForTokens(uint256[] memory amounts, Route[] calldata routes, address to, ...) external {
    _safeTransferFrom(routes[0].from, _msgSender(), poolFor(...), amounts[0]); _swap(amounts,routes,to);
}
```
No `amountOutMin` vs safe `swapExactTokensForTokens:388` which checks `amounts[last] < amountOutMin`. Caller `amounts[1]=1` accepted → MEV. Deliberate foot-gun, verify no dapp calls it (`grep -rn UNSAFE tigris/dapp` → 0).

## LOW (latent) — dangerouslySetInnerHTML XSS (Tigris dapp)

`tigris/dapp/components/labels.tsx:14` + `incentivize.tsx:65`:
`decodeURIComponent(token.logoURI.split(",")[1])` → `dangerouslySetInnerHTML`. Currently `logoURI` is hardcoded `data:image/svg+xml,` (`mocks.ts`) → not reachable. If registry becomes dynamic: `data:text/html,<svg onload=alert(1)>` → XSS. Fix: `<img src={logoURI}>` or DOMPurify.

## INFO — Mezod bridgeOut (CLEAN)

`mezod/precompile/assetsbridge/bridge_out.go:240-330`: `Sign()<=0` blocks 0/negative, `validateToken/validateRecipientForChain/TargetChain.Validate` block zero-address/invalid chain, `validateAmount` Bitcoin-specific→general fallback. `type(uint256).max` passes precompile but fails on `SendAuthorization.Accept` (balance) — not bypass. `btctoken` is thin ERC20, `upgrade` ScheduleUpgrade gated PoaKeeper, NTT RateLimiter unlimited `type(uint64).max` intentional.

## INFO — Web2 SSRF/SSTI (CLEAN)

- `musd/dapp` empty (`App.tsx:"App"`), no fetch/template.
- `tigris/dapp` no external fetch, `next.config.ts` default, no `getServerSideProps`.
- `mezod/bridge-worker/bitcoin/electrum/config.go:26` URL from local config, not user.
- No `delegatecall`/`selfdestruct` across all Solidity+Go (`grep delegatecall` 0 hits), storage uses OZ `__gap` / NTT ERC1967 slots `keccak-1`.

## Repro

```bash
# PriceFeed negative
cast call $PF "fetchPrice()"  # after mock aggregator price=-1, expect huge wrapped if unpatched
# stale DoS
cast rpc evm_increaseTime 61; cast rpc evm_mine; cast call $PF "fetchPrice()" # stale revert
# Pool front-run
cast send $POOL_IMPL "initialize(address,address,bool)" $A $B false
# XSS
# set token.logoURI="data:text/html,<svg onload=alert(1)>," render TokenIcon → fires if unsanitized
```
