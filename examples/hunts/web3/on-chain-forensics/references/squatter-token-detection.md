# Squatter / Impersonator Token Detection

## Pattern: DexScreener Labeled Tokens with Zero Bytecode

When DexScreener lists multiple tokens with the same name (e.g., "Pops Finance" / "POPS") across different pairs, MOST will be **squatter/impersonator tokens**.

## Detection Flow

```bash
# 1. Get all token addresses from DexScreener
curl -s "https://api.dexscreener.com/latest/dex/search?q=<Protocol>" | \
  jq '[.pairs[] | .baseToken.address] | unique'

# 2. Check bytecode on EACH address
for addr in <addr1> <addr2> <addr3> ...; do
  code=$(cast code "$addr" --rpc-url "$RPC")
  if [ "$code" = "0x" ]; then
    echo "$addr = SQUATTER (no bytecode)"
  else
    symbol=$(cast call "$addr" "symbol()(string)" --rpc-url "$RPC")
    echo "$addr = REAL ($symbol) — $(echo $code | wc -c) bytes"
  fi
done
```

## Real World Example: Pops Finance
- **4 tokens labeled "POPS"** on DexScreener (Robinhood chain)
- **1 real**: `0x7E072b...` — 22,612 bytes of bytecode, name "Pops Finance", symbol "POPS"
- **3 squatters**: `0x059C...`, `0x6ecF...`, `0xDd1a...` — `cast code → 0x0` each
- Squatters had TVL of $2,545 to $8,517 — front-runners seeded fake liquidity

## Key Signs of a Squatter Token
1. **`cast code <addr>` returns `0x`** — the contract has ZERO bytecode deployed
2. **Multiple tokens with same name** on the same chain — improbable for a real protocol
3. **Small TVL** but active DexScreener pair — bots seed liquidity to appear real
4. **Pair created at similar time** to the real token — bots monitor new token launches
5. **Only appears on DexScreener** — no mention in docs, GitHub, Twitter, or block explorer

## Reporting Convention
Always separate real contracts from squatters in output:

```
✅ REAL: 0x7e0... "Pops Finance" / "POPS" — TVL $7,975
⚠️ IMPOSTER: 0x059c... — TVL $2,546 (zero bytecode)
⚠️ IMPOSTER: 0x6eCf... — TVL $2,551 (zero bytecode)
⚠️ IMPOSTER: 0xDd1a... — TVL $8,517 (zero bytecode)
```

The `⚠️ IMPOSTER` marker must be clear — do not silently merge squatter TVL into the real token's numbers.