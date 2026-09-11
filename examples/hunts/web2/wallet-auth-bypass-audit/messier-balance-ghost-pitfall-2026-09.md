# RPC load-balancer ghost-balances — false-positive autopsy (messier dump, 2026-09-02)

A wallet balance sweep for impact-sizing produced THREE fake aggregate figures before the honest
fix. This is the single most important reporting discipline for "dump all users + balance" tasks:
**verify per-wallet on a single RPC before claiming any aggregate USD value.**

## What went wrong
A Python sweep of 3,278 wallet addresses via a list of public ETH RPC endpoints (with a fallback /
load-balancer list) returned:
- "13,632 ETH" — one address (`0x0000...dEaD`, the burn address) returned 12,640 ETH; when the RPC
  that should answer a given wallet's `eth_getBalance` timed out/errored, the load-balancer served the
  result from a *different* heavily-cached address (the burn). The aggregate then amplified it.
- "4,002 ETH" — same artifact class after the first fix attempt (still using a failover list).
- "16,595,846 BNB ($9.6B)" on BSC — also fake: Binance seed-node RPCs (`bsc-dataseed*) answer
  `eth_blockNumber`/`eth_call` from the datacenter-IP host with garbage/stale data or block entirely,
  and the fallback chain again bled a pool/burn balance into the aggregate.

None of the three figures was a real user holding. Only after a **per-wallet loop pinned to ONE
stable RPC** (`eth.rpc.blxrbdn.com` for ETH, verified honest via a known-funded control) did the true
number come out: **~21.6 ETH total**, top-1 wallet 15.15 ETH (70% — a real whale, but the "70% of the
aggregate" signal is exactly the red flag that something big bled in, worth checking either way).

## The honest ruleset that fixed it
1. **One stable RPC per sweep** — a *failover list* is what bleeds wrong balances in across requests.
   Prefer a single verified endpoint; it is consistent per-address even if not the fastest.
2. **Sanity the RPC before any sweep**: `eth_blockNumber` + `eth_getBalance` of a KNOWN-funded wallet
   (e.g. vitalik.eth) returning a plausible number. If a seed node answers zero to a known-funded
   wallet, it is NOT honest — do not trust its zeros (produces false "empty" conclusions) or its
   outliers.
3. **Exclude burn / pool addresses explicitly** and report them as their own line, not as holdings.
   `0x0000...dEaD` and LP/pool 0x...000 addresses are the classic bleed sources.
4. **Pull the top-1 wallet individually and check dominance.** >50-70% of an aggregate = a single
   address is swinging it; verify it is a real user, not a burn/pool artifact.
5. **Never report "N users dumped, total $X" from a threaded aggregate alone.** The deliverable is a
   per-wallet list with whales flagged; the aggregate is a derived summary, not ground truth.

## Why it mattered here (operator preference)
The operator ("the operator") explicitly distrusts fabricated numbers and asked for honest verification
("bisa lo test dulu? biar ga fabricated"). Reporting $9.6B BSC or 13K ETH would have been a
fabricated-looking claim. The trusted per-wallet truth (21.6 ETH, ~33K M87-valued, ~2,523 AVAX from a
reliable Avalanche endpoint) plus "BSC/Polygon/Arbitrum RPC-blocked from this datacenter IP, amount
unknown" was the honest close. Note also: many public RPCs (binance `bsc-dataseed*`, `eth.llamarpc.com`,
`1rpc.io`, `eth.drpc.org`, `cloudflare-eth.com`) block datacenter IPs or demand an API key — probe a
known-funded wallet first before a thousands-address sweep, and say "blocked" when it is, not zero.