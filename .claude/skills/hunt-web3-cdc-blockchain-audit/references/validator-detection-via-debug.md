# Validator Detection via Debug API (Goroutine Dump)

## Context
When a blockchain node exposes `debug_stacks` (goroutine dump), determine whether it's a validator/producer node or just a regular RPC/full node by analyzing goroutine patterns.

## Technique
1. Call `debug_stacks`
2. Search the dump for consensus-specific goroutines

## Signature Goroutines by Consensus Type

### BFT / Lachesis / aBFT (U2U, Fantom, etc.)
- **Validator signals**: `emitter`, `abft`, `consensus`, `seal`, `propose`, `vote`, `sfc`, `gasPower`
- **Non-validator only**: `gossip/service`, `p2p/dial`, `p2p/server`, `evmcore/TxPool`, `pebble/DB`, `rpc/handler`, `snap/handler`

### PoS (Ethereum, etc.)
- **Validator signals**: `beacon`, `validator`, `attest`, `propose`, `sync/committee`
- **Non-validator only**: `eth/handler`, `p2p/discover`, `rpc/handler`

## Quick Test
```bash
curl -s -X POST https://rpc.target.xyz \
  -d '{"method":"debug_stacks","params":[]}' \
  | grep -i "consensus\|emitter\|abft\|propose\|vote\|seal\|validator\|beacon\|attest"
```

## Interpretation
- **Results found** → likely validator. Impact of debug API abuse = consensus-level.
- **No results** → full/RPC node. Impact = DoS + info leak only.

## Related
- `eth_coinbase` — if `0x000...000`, likely non-validator
- `net_peerCount` — validators typically have more peers
- `eth_syncing` — syncing nodes are not validators