# FlyingTulip Sonic Deep-Dive — 2026-08-08/09 Session

Source: live RPC forensics on Sonic (chain 146, RPC https://rpc.soniclabs.com). FT 0x5DD1A7A369e8273371d2DBf9d83356057088082c.

## What looked like a vault but wasn't
- Top holder 0xccac8b32a958b4a59833351c430423600bae66bd holds 1,721,811 FT (87% of 1.98M supply) in last 800k blocks.
- Code 21,890 bytes, 28 selectors — all map via 4byte.directory to UniswapV3Pool: slot0(), liquidity(), mint(), burn(), ticks(), observations(), fee(), token0(), token1().
- token0 = 0x29219dd400f2bf60e5a23d13be72b486d4038894 → USDC 6dec (symbol raw 0x...45534443), token1 = FT 18dec.
- fee() = 0x4d58 = 19736 (not standard 500/3000/10000) → Shadow DEX (Sonic) custom fee.
- slot0: sqrtPrice 251514383695007236969249873464784175, tick 299428 → price_raw = (sqrt/2^96)^2 ≈ 1.007e13; FT per USDC human = raw *1e-12 ≈ 10.07; USDC per FT ≈ 0.099.
- Reserves: USDC 2477 (2477619572 raw 6dec) vs FT 1,721,811 → reserve ratio 693 FT/USDC vs price-implied 10 FT/USDC = 69x imbalance (pool 99.85% FT side). Indicates single-sided FT LP or drained USDC side.
- Liquidity raw 0x224c2f1539ed9821 = 2471402063732250657 — small for that TVL.

## True vault (ECR4626 clone)
- 0x7127bb9d9ad0f47b8da9087e634d67f3946f840e — 77-byte EIP-1167 minimal proxy (60806040527f360894a13ba...5ffd).
- Impl slot 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc → 0x051589975909644bee7c33c037a7d2009c8f1839 (20,007 bytes).
- Impl selectors include circuitBreaker(), yield(), isStrategy(address), numberOfStrategies(), totalAssets() — matches PutManager / ftDNMM CircuitBreaker private repo (KNOWN_ISSUES CB-01, PM-01, PM-03).
- Proxy totalSupply() == FT balance == 14,004.80 FT (1:1 share token), storage slot1 = 0x59222220759efe35b8e46f5563151827e4114628 (7,743 bytes, unknown vault/strategy), slot3 = Safe 0x1118...70Cb.
- Second clone 0x5e7a9eea6988063a4dbb9ccddb3e04c923e8e37f (1,202 bytes, impl 0xC1c7E1076Ca856e6D362a6e286861B3be5510193 5,939 bytes) — all calls revert (uninitialized).

## Throttled holder enumeration (Sonic RPC limits)
- eth_getLogs with Transfer topic 0xddf252ad... times out for >400k window. Must chunk 100k blocks.
- Working recipe: 8 chunks × 100k covering 800k tip, 1.0-1.2s delay between getLogs, 0.6-0.7s delay between balanceOf eth_call, progress checkpoint every 10 holders to /tmp/*.json.
- Result 800k: 111 holders, 39 with balance >0 in sampled pass; checkpoint file bal_checkpoint2.json holds sorted top with throttle. Holders file /tmp/holders_111.txt.
- Router 0x6131b5fae19ea4f9d964eac0408e4408b66337b5 (13,725 bytes, 7 selectors: e21fd0e9 swap(...Shadow), 78e3214f rescueFunds, 8af033fb swapSimpleMode, 715018a6 renounceOwnership). Owner 0x1874028262f1f4b2dd1f2700a72ee8b9b7c69090 (onlyOwner rescueFunds). Tx 0x34292f36... shows pool funding via this router.

## Tick math sanity check
- tick 299428 → 1.0001^tick ≈ 1.007e13 raw, matches (sqrt/2^96)^2. Human FT/USDC = raw *10^(6-18).
- If price and reserves diverge 69x, pool is not at equilibrium — watch for slippage-exploit (PM-03).

## Lessons
- Don't assume biggest holder = vault; verify selectors + token0/token1 + fee tier.
- For Sonic, always probe both master/main archive branches; default is master.
- EIP-1967 admin slot can be zero while proxy still delegates via bytecode PUSH20 — extract DELEGATECALL target from proxy bytecode, not storage.
