# TARGET PRIORITY MATRIX — BUG BOUNTY

## Target Priority by Type

| Priority | Target Type | Chains | Min TVL | Why |
|----------|-------------|--------|---------|-----|
| **P0** | Bridge (custom, unaudited, new) | ETH/Arb/Base/Sol/Robinhood | $10M+ | Trust assumption = single point of failure |
| **P1** | Lending (custom oracle, new market) | ETH/Arb/Base | $20M+ | Oracle manip + liquidation cascade |
| **P2** | Perps (custom pricing, new market) | Arb/Base | $15M+ | Funding rate / mark price manip |
| **P3** | DEX/AMM (custom AMM math, hooks) | ETH/Arb/Base/Sol | $30M+ | Reentrancy / precision loss / sandwich |
| **P4** | Governance (token voting, timelock) | ETH/Arb/Base | $50M+ | Flash loan + proposal injection |
| **P5** | Staking/LRT (liquid staking, restaking) | ETH/Arb/Base | $100M+ | Slashing oracle, withdrawal queue |

---

## Chain Priority by Ecosystem

| Chain | Bridge | Lending | Perps | DEX | Why |
|-------|--------|---------|-------|-----|-----|
| **Ethereum** | P0 | P1 | P2 | P3 | Highest TVL, most complex |
| **Arbitrum** | P0 | P1 | P2 | P3 | High TVL, custom contracts |
| **Base** | P0 | P1 | P2 | P3 | Growing, new deployments |
| **Solana** | P0 | P1 | P2 | P3 | High throughput, unique consensus |
| **Robinhood** | P0 | — | — | — | New, untested |

---

## Signal Indicators (Drop Everything and Investigate)

| Indicator | Why |
|-----------|-----|
| "Emergency" functions (pause, shutdown, upgrade, migrate) | Admin key = god mode |
| "Bridge" or "cross-chain" in name | Trust assumption across networks |
| "Oracle" or "price" in any function | Manipulable input |
| "Governance" with token voting | Flash loan surface |
| "Reward" or "claim" with time-based calc | Precision loss, timing attack |
| Custom math library | Unaudited, likely buggy |
| Assembly blocks | Harder to audit, more edge cases |
| Upgradeable proxy / Diamond / Beacon | Storage collision, init bypass |
| New protocol, small team, high TVL | Oversight gaps |
| "Audited by X 6 months ago, no changes" | Read audit — find what they missed |

---

## Noise Indicators (Skip Unless Calculus Says Otherwise)

| Indicator | Why |
|-----------|-----|
| Standard ERC-20/721 without modifications | No custom logic |
| Simple getter/setter functions | No state change |
| UI-only parameters | Not on-chain |
| Cosmetic issues (naming, comments) | No impact |

---

## CALCULUS (Every Move)

`Value > Cost + Risk + Irreversibility? → GO | Else → PIVOT or ABORT`

| Factor | Question |
|--------|----------|
| **Value** | Maximum extractable value? |
| **Window** | How long is it open? (blocks, epochs, days) |
| **Cost** | Gas, time, capital, opportunity cost |
| **Risk** | Detection probability? |
| **Clean** | Exit without footprint? |
| **Fallback** | If primary fails, what's Plan B? |

**No sentiment. Worth it → execute. Not → move on.**

---

## BOUNTY THRESHOLDS

| Program | Critical | High | Medium | Low |
|---------|----------|------|--------|-----|
| **Ethereum Foundation** | $250k+ | $50k+ | $10k+ | $2k+ |
| **Arbitrum** | $100k+ | $25k+ | $5k+ | $1k+ |
| **Optimism** | $100k+ | $25k+ | $5k+ | $1k+ |
| **Base** | $50k+ | $15k+ | $3k+ | $500+ |
| **Solana Foundation** | $50k+ | $15k+ | $3k+ | $500+ |
| **Immunefi (avg)** | $100k+ | $25k+ | $5k+ | $1k+ |

**Target: $50K+/quarter** → Need 2-3 Critical OR 10+ High OR mix

---

## QUICK FILTER: IS THIS WORTH HUNTING?

```
IF target_type in [Bridge, Lending, Perps] 
   AND chain in [ETH, Arb, Base, Sol]
   AND TVL > threshold
   AND (unaudited OR custom_logic OR recent_deployment)
THEN → INVESTIGATE IMMEDIATELY

ELSE IF target_type in [DEX, Governance]
   AND custom_math_or_logic
   THEN → INVESTIGATE

ELSE → SKIP (unless Calculus says otherwise)
```

---

## ALPENGLOW SPECIFIC (CURRENT TARGET)

| Property | Value |
|----------|-------|
| **Program** | Alpenglow Bug Bounty Competition |
| **Prize Pool** | 50,000 SOL |
| **Window** | 2026-08-05 to 2026-08-19 |
| **Target Code** | `anza-xyz/agave` (master) |
| **Core Crates** | `votor`, `votor-messages`, `bls-sigverify`, `bls-cert-verify` |
| **Integration Points** | 15+ files |
| **Required** | Working PoC, local fork/simulation |

### Alpenglow Priority Targets

| Priority | Crate | Focus |
|----------|-------|-------|
| **P0** | `bls-cert-verify` | Cert verification, stake thresholds, migration |
| **P0** | `bls-sigverify` | Vote/cert sig verification, vote pool, rogue key |
| **P0** | `votor` | Consensus pool, parent ready, stake counters |
| **P1** | `votor-messages` | Migration logic, certificate encoding |
| **P2** | `core/replay_stage` | Replay, update_parent, blockstore integration |
| **P2** | `ledger/blockstore_processor` | Chained block ID, genesis cert, VoM |
| **P2** | `turbine/retransmit_stage` | Shred dedup, first shred → Votor bridge |

---

## EXECUTION ORDER FOR ALPENGLOW

1. **Cert verification** (`bls-cert-verify`) — stake thresholds, double-count, bitmap
2. **Vote/cert sig verification** (`bls-sigverify`) — vote pool, rogue key, parallel DoS
3. **Consensus pool** (`votor`) — parent ready, stake counters, safe-to-notar
4. **Migration** (`votor-messages`) — genesis split, state machine
5. **Replay/Blockstore** — TOCTOU, chained block ID, VoM
6. **Turbine** — shred dedup, FirstShred→Votor bridge

---

## POST-FINDING: SUBMISSION CHECKLIST

- [ ] Working PoC compiles and runs
- [ ] Chain links all have file:line evidence
- [ ] Impact mapped to Consensus Safety / Liveness / Funds
- [ ] Pre-auth confirmed
- [ ] Calculus: Value > Cost + Risk
- [ ] Clean exit path identified
- [ ] Report format: VULN/ENTRY/CHAIN/IMPACT/POC/EVIDENCE/CONFIDENCE/MITIGATION