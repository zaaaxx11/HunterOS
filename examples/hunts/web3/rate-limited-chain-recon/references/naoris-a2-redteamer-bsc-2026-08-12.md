# Agent 2 RED-TEAMER BSC — Naoris Proxy 0x1b37...80cc (2026-08-12)

## Target
- Proxy `0x1b379a79c91a540b2bcd612b4d713f31de1b80cc` → Impl `0xc4e16e56ea3660110924cc06850120672b7e11ef` (UUPS, `Naoris.sol:16-23`).
- ERC20 `Naoris Protocol (NAORIS)` 18 dec, `TOTAL_SUPPLY 4B` (`Naoris.sol:29`), live `88,731,471` (`88731471e18`), `paused=false` (`0x5c975abb` @350).
- Proxy 342b minimal delegate (`7f360894a13ba1...` in prefix), impl 38298b (126 PUSH4 sels).

## Task Shape (required methodology)
- Deployer & creation block via `eth_getLogs` pagination 100k (Transfer `0xddf252ad`, Upgraded `0xbc7cd75a`, AdminChanged `0x7e644d79`) + `Etherscan V2 tokentx chainid=56`.
- Holders via `Transfer 0xddf252ad` in 100k chunks → `balanceOf (0x70a08231)` per holder → top % concentration.
- Proxy upgradeability & `hasRole` correct hashes on proxy (DEFAULT_ADMIN `0x00...`, PAUSER `keccak("PAUSER_ROLE")=0x65d7a28e...862a`), pause risk, holder centralization.
- Save `/tmp/naoris-a2-findings.json` + `/tmp/naoris-a2-report.md` with file:line/bytecode offsets.

## What actually happened (honest)
- **100k requested → 5000 real.** Tested 8 RPCs sequentially with 0.6-1.2s throttle:
  - `1rpc.io/bnb`: `eth_getLogs is limited to 0-50` (-32602) even at 50.
  - `bsc-dataseed*`: `limit exceeded` (-32005) even at 50.
  - `bsc.meowrpc.com`: `method not supported`.
  - `bsc-rpc.publicnode.com`: `Please specify an address`.
  - `bsc.drpc.org`: free 10000 → 5000, `You reached Public endpoint rate limit`, archive pruned before ~114688716 (`no upstreams`).
  - `rpc-bsc.48.club`: **5000 max** (`exceed maximum block range: 5000`), early blocks `header not found` (archive pruned). **Chosen.**
  - `api.bscscan.com` V1: `deprecated, switch to V2`. `api.etherscan.io/v2?chainid=56`: `Free API access not supported for this chain` — tokentx path blocked free tier. `bscscan.com` scrape: 403.
  - `eth_getStorageAt` both EIP1967 slots (`0x360894...b`, `0xb53127...03`) → `0x000...` on ALL public RPCs despite proxy delegating (`totalSupply` `eth_call` succeeds, 342b code contains `7f360894`). Don't trust zero — verify via `eth_call`.
  - `eth_getCode` historical → `0x` + `header not found`; binary search for creation block fails. Need paid archive (Alchemy/QuickNode).
- Full 115M chain / 5000 = 23000 chunks (~6h) + throttling → impossible on free tier within task window. Adapted: **recent 200k window** (40×5k) + **50k window** (10×5k) with 0.6-1.2s, checkpointing.
- Holder window: 86 unique (filtered zero), 129 logs per 5k recent, `balanceOf` 0.7s each, checkpoint `holders_200k.json`. Sum window 14.9M vs total 88.7M → under-sample. Top1 `0x73d8bd54...` 15.97%, Top10 16.82% sample (true unknown).
- `hasRole` on proxy (`0x91d14854` @515) for top15 all false → pauser/admin is separate EOA/multisig not in window.
- Offsets (impl 38298b): `hasRole 515`, `paused 350`, `balanceOf 416`, `totalSupply 97`, `upgradeToAndCall 4f1ef286 295`, `pause 482`, `unpause 240`, `transfer 570`. Proxy code prefix docs EIP1967 slot.

## Repro (throttled)
```bash
RPC=https://rpc-bsc.48.club; TOPIC=0xddf252ad...; PROXY=0x1b37...
# 5k chunks, 0.6-1.2s
for fr in $(seq $((LATEST-50000)) 5000 $LATEST); do
  curl -s -X POST $RPC -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_getLogs","params":[{"address":"'$PROXY'","fromBlock":"'$(printf "0x%x" $fr)'","toBlock":"'$(printf "0x%x" $((fr+4999)))'","topics":["'$TOPIC'"]}],"id":1}'
  sleep $(python -c "import random;print(random.uniform(0.6,1.2))")
done
# balanceOf per holder
for h in $(jq -r .[] holders_200k.json); do
  data="0x70a08231$(printf "%064x" $((16#${h:2})))" # padded
  curl -s -X POST $RPC -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"'$PROXY'","data":"'$data'"},"latest"],"id":1}'
  sleep 0.7
done
```

## Artifacts
- `/tmp/naoris-a2-findings.json` (17K, latest 115357212, live `totalSupply`/`paused`/`decimals`, slots, offsets, sample logs)
- `/tmp/naoris-a2-report.md` (6.6K)
- `/tmp/naoris-a2/holders_200k.json` (86), `balances_200k.json`, `logs_200k.json`

## Lesson for future BSC recon
Document **requested vs real chunk size**, never silently downgrade 100k→5k. When archive is pruned, report `UNKNOWN` for deployer/creation with root cause (limit + height + Etherscan free block), keep window sample honest.
