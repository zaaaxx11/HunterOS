# Gimo Finance 0G — Trust Graph Session 2026-08-12

Proxy 0xAc06d1Df23a4Fa00981aFAC0f33A5936Bd2135aF / Impl 0x7A5e1b999a665f2b89e5f6eAE32dF9471De193C7 / st0G 0x7bBC63D01CA42491c3E084C941c3E86e55951404 / RPC https://evmrpc.0g.ai chainId 16661

## Storage Dump (verified eth_getStorageAt)
|slot|raw|dec|
|---|---|---|
|0|...3007306646ac90a647bebc9acc029c941db5b0Fb0001|owner<<8|0x01 -> owner 0x3007306646AC90a647BebC9Acc029c941dB5B0Fb|
|2|...015180|86400 eraSeconds|
|3|...4f7b|20347 era|
|4|...0149|329 validators|
|5|...12668ba79fc56de3|1.325900692e18 rate|
|8|...2386f26fc10000|1e16 fee 1%|
|9|...01|1 paused|
|12|...03|3 epoch|
|13|...1ba8|7080 commission|
|16|...7bBC...|st0G token|
|17|...016345785d8a0000|1e17 minStake|
|18|...1e6ec8e78362ea07a25b|1.437e23 totalPooled|
EIP1967 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc = 0x7A5e...
SLOAD set: [0,1,2,3,4,5,6,8,12,13,16,17,18]

## Selector Extraction (57)
Regex `8063([0-9a-fA-F]{8})14(61)([0-9a-fA-F]{4})57` on /tmp/impl_full.hex.
Dispatch table (selector -> jumpdest): 88611f35:0x756 … fd852c1b:0xa78 etc (57 entries, see /tmp/GIMO_TRUST_GRAPH.md).
Body slicing: `hexdata[dest*2:nextDest*2]` capped 600-2500 hex chars.

Keccak-verified: 8da5cb5b owner(), 679aefce getRate(), 2c4e722e rate(), 46f45b8d stake(string)=payable referral, 2e17de78 unstake, f2fde38b transferOwnership, 79ba5097 acceptOwnership, 3659cfe6 upgradeTo, 4f1ef286 upgradeToAndCall, 52d1902d proxiableUUID.
View probes: 88611f35->slot18 pooled, c8c20263->4f7b era, f1887684->1e16 fee, etc.

## Privileged Sinks
- fd852c1b @0xa78 dual owner guard: `SLOAD 0 + 0x010000 mask + CALLER EQ -> revert 0x015783e9` x2. Body uses mapping slot 0x77/0x78, internal 0x2a6c/0x2ac6/0x2af5, ends with CALLs to st0G mint (0x40c10f19) via 0xccd885bb/0x64af066b. eth_call anon vs owner diff.
- 3ccfd60b diff 0xd6d9e665 onlyOwner.
- 3659cfe6/4f1ef286 UUPS (delegatecall guard string).
- 7b207727 relay-only rate push (see below).

## Relay & Rate
Relay 0x3241549486acc64999e6b3c02c794bd7bbc71d54 calls 7b207727 (0 value) -> logs 0x02105621 ExchangeRateUpdate 0x1265089e73f3cc3b (~1.32e18). Tx 0x32b0d482a0657106f166a5426b3ed8645810d2e41e8d2dd25804c163a2079386 block 0x274b0a0; stake tx 0x7d4b738e7913d1007456b2d433203997f7a1e8375df613e0df99e4a63a1b86bc input 0x46f45b8d+galxe value 50 A0GI (0x2b5e3af16b1880000). eth_getLogs 100k chunks, curl 403 -> urllib.request 0.6s.

## Trust Boundary & Rate Math
stake(string) mints st0G = msg.value * 1e18 / rate(slot5). Token slot5=proxy sole minter. No TWAP/timelock; relay inflation = dilution. UpgradeTo drains slot18.

## Verification Cmds
```
python3 -c "import urllib.request,json; RPC='https://evmrpc.0g.ai'; d=lambda m,p: json.dumps({'jsonrpc':'2.0','id':1,'method':m,'params':p}).encode(); r=lambda m,p: __import__('urllib.request').request.urlopen(__import__('urllib.request').Request(RPC,data=d(m,p),headers={'Content-Type':'application/json'})).read(); print(r('eth_getStorageAt',['0xAc06d1Df23a4Fa00981aFAC0f33A5936Bd2135aF','0x0','latest']))"
```

Artifacts: /tmp/impl_full.hex (33492), /tmp/GIMO_TRUST_GRAPH.md full report.
