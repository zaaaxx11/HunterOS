# Mezo Trust Graph — Architect Session 2026-08-16

Source: Agent 1 — ARCHITECT: Map Mezo trust graph (mezo.org + mezo-org GitHub org).

## System Overview
- **Product:** Mezo — "Bitcoin Economic Layer". Tagline: "Everyday finance using Bitcoin", "Bitcoin's Economic Layer". Features: Borrow (BTC-collateral credit), Earn (Upshift vaults yield), MUSD stablecoin (100% BTC-backed 1:1 USD), Swap/Pools/Rewards/MEZO token. Qualities: Permissionless, Bank-free, Intuitive, Secure, Decentralized.
- **Frontend:** `https://mezo.org` SSR (modulepreload `_assets/*`, BaseWeb, Sanity CDN `cdn.sanity.io/images/9zunswfd/...`). Routes: `/feature/borrow`, `/feature/earn`, `/feature/musd`, `/explore`, `/for-institutions`, `/overview`. Docs: `https://info.mezo.org` (Astro 5 + Starlight 0.37.4) and `https://mezo.org/docs` mirror; repo `mezo-org/documentation`.
- **Org:** `mezo-org` (ID 175807022, created 2024-07-17, 90 followers, 24 public repos, description "Everything on Bitcoin." blog mezo.org).

## Org Inventory (24 repos, GET /orgs/mezo-org/repos sorted by updated)
| Repo | Lang | Stars | Desc | Updated |
|---|---|---|---|---|
| mezod | Go | 15 | Reference client for Mezo chain | 2026-08-12 |
| go-ethereum | Go fork | 5 | Go Ethereum fork | 2026-08-11 |
| documentation | MDX | 12 | Docs site Astro/Starlight | 2026-08-06 |
| validator-kit | Shell | 10 | Validator docker/native/helm/manual | 2026-08-04 |
| audits | — | 0 | 13 audit PDFs (Halborn/Thesis/Cantina/OtterSec/Quantstamp) | 2026-06-30 |
| musd | TS/Sol | 16 | MUSD contracts + dApp | 2026-05-19 |
| tigris | Sol | 0 | Gauge/DEX Solidly-inspired (ARCHIVED) | 2026-05-07 |
| keep-common | Go fork | 0 | Keep libs | 2026-04-24 |
| homebrew-tap | Ruby | 0 | mezo-cli packages | 2026-04-16 |
| AllocationsRaw | — | 0 |  | 2026-03-30 |
| ntt-bridge-musd-mainnet | TS | 0 | NTT MUSD mainnet | 2026-03-19 |
| ntt-bridge-musd-testnet | TS | 0 | NTT MUSD testnet | 2026-03-12 |
| safe-deployments | TS fork | 6 | Safe singletons | 2026-01-25 |
| ntt-bridge-mezo-mainnet | TS fork | 0 | Wormhole NTT framework | 2026-01-23 |
| ntt-bridge-mezo-testnet | TS | 0 |  | 2026-01-21 |
| ntt-bridge-musd | TS | 0 |  | 2025-12-18 |
| demo-ntt-ts-sdk | TS fork | 1 |  | 2025-10-17 |
| cosmos-sdk | Go fork | 1 | Cosmos SDK | 2025-10-17 |
| balance-exporter | Go fork | 1 | Prometheus balances | 2025-10-17 |
| evm-chain-list | Kotlin fork | 1 | chain metadata | 2025-09-03 |
| thUSD | fork | 1 | Threshold USD monorepo | 2025-09-03 |
| chains | TS | 0 | viem chain config @mezo/chains | 2025-08-27 |
| sourcify | fork | 0 | source verification | 2025-08-27 |
| pre-commit-hooks | fork | 0 |  | 2025-03-10 |

## mezod Architecture (Go 1.24, CometBFT 0.38.21, Cosmos SDK 0.50.15)
- **Origin:** Fork of Evmos LGPL heavily modified. `module github.com/mezo-org/mezod`.
- **Deps:** `btcd/btcutil`, `cosmos/btcutil`, `keep-network/keep-common v1.8.0`, `ethereum/go-ethereum v1.16.9`, `skip-mev/connect v2.1.2` (oracle/marketmap), `cometbft 0.38.21`, `cosmos-sdk 0.50.15`, `gogoproto`, `ibc?` indirect via simapp.
- **app/app.go wires:** `auth/authz/bank/consensus/crisis/params/upgrade` + `app/abci` + `app/ante/evm` (EIP712) + `x/bridge` + `x/poa` + `x/evm` + `x/feemarket` + `marketmap`+`oracle` (Skip) + `precompile/*` + `indexer/rpc/server`.
- **Top dirs:** `app/`, `x/bridge|poa|evm|feemarket`, `precompile/assetsbridge|btctoken|mezotoken|priceoracle|validatorpool|maintenance|upgrade|erc20`, `bridge-worker/`, `ethereum/`, `crypto/`, `proto/`, `solidity/`, `chain/mainnet|testnet/`, `indexer/`, `infrastructure/`.
- **Precompiles:** `btctoken` (IBTC.sol, btctoken.go), `assetsbridge`, `priceoracle` (Skip), `validatorpool`, `mezotoken`, `maintenance`, `upgrade`, `erc20`, `testbed`. Mapped via `precompile/version_map.go`.
- **x/bridge:** `keeper/{abci,assets_locked,assets_unlocked,btc,erc20,genesis,keeper,outflow_limit,params,pause,query_server,triparty}` + `types/{genesis,params,assets_locked,assets_unlocked,triparty,erc20}` + `abci/`, `client/`. `x/poa` (PoA validator): `keeper/`, `types/`, `client/`, `spec/`. `x/evm`, `x/feemarket`.
- **bridge-worker:** `bridge_worker.go`, `btc_withdrawal.go`, `assets_unlocked_endpoint.go`, `config.go`, `start.go`, `bitcoin/`, `ethereum/` — off-chain relayer watching BTC L1 + EVM.
- **chain/**: `mainnet/mezo_31612-1/seeds.txt`, `testnet/mezo_31611-1/seeds.txt`. Sync: block sync from genesis (version ordering chain documented in validator-kit README, e.g. mainnet v1* genesis->706500, v12* 10885900->tip) or state sync snapshot (team only for Matsnet testnet).
- **validator-kit:** `docker/`, `native/`, `helm-chart/`, `manual/`, `docker-monitoring/`. Artifacts: `mezo/mezod:VERSION` (DockerHub) + `github.com/mezo-org/mezod/releases/download/VERSION/linux-amd64.tar.gz`. Seed nodes public. PoA: `mezod poa submit-application <key_name> --rpc-url`.

## MUSD CDP (musd/solidity/contracts/ — Threshold USD → Liquity fork)
- **Contracts:** `ActivePool.sol`, `BorrowerOperations.sol` (+Signatures), `CollSurplusPool.sol`, `DefaultPool.sol`, `GasPool.sol`, `HintHelpers.sol`, `InterestRateManager.sol`, `PCV.sol`, `PriceFeed.sol`, `SortedTroves.sol`, `StabilityPool.sol`, `TroveManager.sol`, `token/{MUSD,IMUSD,TokenDeployer}` + `dependencies/`, `interfaces/`.
- **Data flow:** `User BTC -> BorrowerOperations.openTrove(BTC,MUSD) -> ActivePool (custody) -> TroveManager ICR check via PriceFeed.fetchPrice() [ChainlinkAggregatorV3Interface, MAX_PRICE_DELAY=60s, TARGET_DIGITS=18] -> storage ActivePool/DefaultPool/StabilityPool/CollSurplusPool/SortedTroves/GasPool -> output MUSD token mint`. Withdraw: `withdrawColl/closeTrove/redeemCollateral/liquidate` -> StabilityPool (funded) or DefaultPool (redistribute).
- **Peg:** Floor $1 via redeem arb (buy $0.80 MUSD -> redeem $1 BTC -> sell). Ceiling $1.10 via 110% min CR (mint 90,909 MUSD on 1 BTC $100k -> sell $109k). Oracle + redemption.
- **Fees:** 0.1% borrow (governable) minted to gov, 0.75% redemption taken as BTC, refinancing rate, simple fixed interest per-trove (global rate at open + refinance). Flow: tx triggers fee -> mint MUSD to PCV -> gov `distributeMUSD` with `feeSplitPercentage` (0-100) -> `MUSD Savings Rate vault receiveProtocolYield` vs bootstrap loan burn vs StabilityPool deposit. Bootstrap loan: deployment mints to PCV -> deposit to StabilityPool; repayment via feeSplit.
- **Key params:** `feeRecipient`, `feeSplitPercentage`, `PriceFeed.oracle` (`Ownable2StepUpgradeable setOracle`), interest manager global rate.

## Bridging (Wormhole NTT)
- **Repos:** `ntt-bridge-musd-mainnet/testnet`, `ntt-bridge-musd` (generic), `ntt-bridge-mezo-mainnet` (fork of wormhole NTT), `ntt-bridge-mezo-testnet`, `demo-ntt-ts-sdk`. Structure `ntt-bridge/<token>/<network>`.
- **Mechanism:** Mezo `Locking`, Ethereum `Burning` for MUSD mainnet. `deployment.json` is source of truth (contracts, access control, chain relationships). NTT CLI manages. Git subtree tracks `wormhole-foundation/native-token-transfers`.
- **Flow:** BTC L1 / Ethereum lock/burn -> `bridge-worker` observes (btcd chainhash + electrum `go-electrum` + eth RPC) -> `x/bridge` ABCI (assets_locked) -> mint/unlock on Mezo EVM via `btctoken/assetsbridge` precompile -> assets_unlocked/burn -> opposite chain withdrawal. `outflow_limit`, `pause`, `triparty` controls.

## Supporting Components
- **chains (TS):** `createMezoChain({network, rpcUrls})` exports `mezoMainnet/mezoTestnet` for viem `createPublicClient`. Private RPC injection surface.
- **solidity/ in mezod:** Hardhat precompile contracts `contracts/` + `deploy/` + `deployments/` + `external/` — precompile EVM deploy scripts.
- **audits repo:** 13 reports 2024-2026: native bridge (Halborn 2026-04-08, Thesis 2025-09-10, Halborn 2025-09-08, Ottersec 2025-03-18), Earn (Thesis 2026-01-30, Halborn 2026-01-08), mUSD Cantina 2025-04-15, mezod Halborn 2025-01-31/2024-10-18, stBTC/Portal Thesis 2024-08-08, Passport Quantstamp 2024-05-03 / Thesis 2024-04-19, Portal Thesis 2024-03-14.
- **sourcify/balance-exporter/evm-chain-list/keep-common/homebrew-tap:** verification, monitoring, chain list, shared libs, CLI distribution.

## Control Flow
`Wallet (viem @mezo/chains) -> RPC http 8545 / ws + CometBFT 26657 -> ante (feemarket + eth ante + EIP712) -> CheckTx/DeliverTx -> x/bridge|poa|evm keeper -> precompile.Run (version_map dispatch via validatorpool/btctoken etc.) -> keeper state (bank/cosmos-db) -> ABCI commit (CometBFT) -> bridge-worker async (bitcoin/ethereum poll) -> L1 finalization`. Governance: `PriceFeed.setOracle onlyOwner`, `PCV feeRecipient/feeSplit`, `InterestRateManager` global rate, `TroveManager` params, bridge `pause/outflow_limit/triparty` params, `poa submit-application` team approval.

## Trust Boundaries (attack surface map)
1. Bitcoin L1 <-> bridge-worker <-> x/bridge — btcd/electrum SPV trust, reorg handling, triparty attestations, outflow limits; pause is admin-gated.
2. Wormhole NTT <-> Mezo locking — deployment.json authority, wormhole guardian set, burn/mint sync, NTT manager ownership.
3. PriceFeed Oracle — Chainlink `latestRoundData()`, 60s staleness, `onlyOwner` setOracle, `decimals()>0` + `price!=0` checks; Skip Connect marketmap/oracle as second oracle layer.
4. MUSD CDP core — BorrowerOperations entry, SortedTroves ICR linked-list (hint manipulation), StabilityPool bootstrap loan (PCV owns funds, gov can redirect), OZ upgradeable proxies, sourcing via sourcify needed for verification.
5. EVM precompiles — `btctoken/assetsbridge/priceoracle` callable from any EVM contract; `x/evm` <-> `bank` keeper bridge (ERC20 mapping).
6. PoA validator set — `poa submit-application` requires team verification + central monitoring; CometBFT 2/3 honest majority, seed nodes as bootstrap trust.
7. Frontend/supply chain — mezo.org SSR + Sanity CDN, musd/dapp vite, @mezo/chains viem config (RPC URL injection), homebrew-tap binary + DockerHub `mezo/mezod`.
8. Governance/Admin — Ownable2Step on PriceFeed/PCV/MUSD + fee params + bridge params; Safe deployments dependency; no timelock visible at this layer.

## Recon Recipe (for next agent)
```bash
# org enumerate
curl -sL "https://api.github.com/orgs/mezo-org/repos?per_page=100&sort=updated" | jq
# file map
curl -sL "https://api.github.com/repos/mezo-org/mezod/contents/x?per_page=100" | jq
curl -sL "https://api.github.com/repos/mezo-org/mezod/contents/precompile?per_page=100" | jq
curl -sL "https://api.github.com/repos/mezo-org/musd/contents/solidity/contracts?per_page=100" | jq
# key files raw
curl -sL "https://raw.githubusercontent.com/mezo-org/mezod/main/x/bridge/keeper/keeper.go" | head
curl -sL "https://raw.githubusercontent.com/mezo-org/mezod/main/bridge-worker/btc_withdrawal.go" | head
curl -sL "https://raw.githubusercontent.com/mezo-org/musd/main/solidity/contracts/PriceFeed.sol"
# docs
curl -sL https://info.mezo.org | head
```

## Next Steps for Red/Fuzz/Chainer
- Deep read `x/bridge/keeper/{assets_locked,btc,triparty,pause,outflow_limit}.go` + `precompile/btctoken/btctoken.go` + `PriceFeed.sol` (stale price, decimals=0 edge).
- Verify `musd` bootstrap loan cannot be withdrawn before repayment completes (`PCV.distributeMUSD` feeSplit logic).
- Test wormhole `deployment.json` vs on-chain state drift.
