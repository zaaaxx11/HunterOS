# U2U Network Audit — Session Reference (2026-08-13)

## Target
U2U Network — Chain ID 39, 71 repos, mainnet live, Block 66M+

## Key Attack Surfaces Found
- **RPC Debug API**: debug_writeMemProfile, debug_setGCPercent, debug_stacks, txpool_content — ALL PUBLIC, no auth
- **aa-bundler v0.7.0**: DepositManager.ts:26 double-sub bug (getUserOpMaxCost(userOp) vs entry.userOp)
- **SubnetStakingPool**: rewardRateHistory unbounded loop → DoS permanent fund lock
- **helm-charts**: ClusterRole pods/exec + pods/create cluster-wide → K8s takeover
- **dhcp2p**: REST API (not DHCP!), /request-auth no auth, /lease/* public read, Sybil starvation, lease squatting
- **SubnetProvider**: claimWithdrawal sends to msg.sender, not provider owner
- **SubnetBidMarketplace**: claimPayment no access control

## Critical Live PoCs
- C1: debug_writeMemProfile → file write to /tmp/* (proven on mainnet)
- C2: txpool_content → full mempool dump (proven on mainnet)
- C3: Paymaster drain — EntryPoint deployed but 0 deposits, 0 UserOps (infra ready, no users)
- C4: K8s takeover — private cluster, no public access (need provider foothold)

## K8s Recon Results
- K3s confirmed (from subnet agent source code)
- Subnet agent on port 8585 (X-API-Key auth)
- Subnet node API on port 8080 (Bearer token auth)
- All behind Cloudflare, origin IPs not leaked
- No public K8s endpoints found

## Provider Registration Path
To get K8s access: register as subnet provider → deploy node → scan internal network → pivot

## Web2 CDC Agent 1 (ARCHITECT) Pass — 2026-08-14

Separate Agent 1-only pass on U2U Web2 surface (no source, remote-only). Full methodology: curl all targets → JS bundle analysis → API probe → auth identification → admin panel hunt → trust boundary map.

### Key Findings
- **CRITICAL: `/api/revalidate` unprotected** — `POST {"secret":"***","path":"/"}` → `{"revalidated":true}` for any secret. ISR cache poisoning vector.
- **No Server Actions** on u2u.xyz — pure content site (Prismic CMS), zero `$ACTION_ID` in bundles.
- **No auth** on u2u.xyz — no NextAuth, SIWE, JWT, or session cookies.
- **Wallet-based auth** on staking.u2u.xyz — wagmi + RainbowKit + Reown, WalletConnect project ID `807caabcacf68376094209c3e9d946e6` hardcoded in 4.2MB bundle.
- **ERC-4337 bundler** v0.7.0 functional on bundler.u2u.xyz/rpc — EntryPoint `0xdbd3939BeeC5DC02Df4820212820cB078d95DD32`, chainId 39.
- **GraphQL introspection** enabled on all subgraph endpoints (staking-graphql, graph, subgraph).
- **report.u2u.xyz** — Go API: `/api/circulating` (supply: 8.36B U2U), `/api/u2u_price`.
- **All CORS `*`** — u2u.xyz (with credentials:true), report, bundler, staking-graphql.
- **No admin panels** — all /admin, /dashboard, /console, /wp-admin, /cms, /login, /signin = 404.
- **RPC endpoints**: rpc-mainnet active (chainId 39), rpc-devnet timeout, rpc-nebulas-testnet CF error 1016.

### Full Endpoint Inventory
```
u2u.xyz/api/preview          → 307 (Prismic preview, sets __prerender_bypass)
u2u.xyz/api/exit-preview     → 200 {"success":true}
u2u.xyz/api/revalidate       → POST 200 {"revalidated":true} (NO SECRET!)
report.u2u.xyz/api/circulating → 200 {"supply":8356001269}
report.u2u.xyz/api/u2u_price → price endpoint
bundler.u2u.xyz/rpc          → ERC-4337 JSON-RPC (EntryPoint: 0xdbd3939...)
rpc-mainnet.u2u.xyz          → chainId 39, net_version 39
staking-graphql.u2u.xyz/graphql → calculateApr (introspection on)
graph.u2u.xyz/subgraphs/name/u2u/sfc-network-v3  → epochs, validators, pointers
graph.u2u.xyz/subgraphs/name/u2u/sfc-subgraph-v3  → same class
subgraph.u2u.xyz/subgraphs/name/u2u/sfc-network   → same class
testnet-staking-graphql.u2u.xyz/graphql          → testnet mirror
subgraph-testnet.u2u.xyz/subgraphs/name/u2u/sfc-subgraph-v2 → testnet subgraph
```

Full details in `web2-attack-surface-audit` references: `u2u-web2-remote-fuzzing-2026-08.md`.