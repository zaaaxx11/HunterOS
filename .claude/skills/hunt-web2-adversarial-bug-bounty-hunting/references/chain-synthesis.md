# CHAIN SYNTHESIS — DOOMSDAY PATTERNS

## Core Principle
**Single bug = noise. Chain = exploit.**

Every critical exploit is a chain of small verified findings. The art is finding how they connect.

---

## CHAIN ANATOMY

```
CHAIN = [Link1: file:line] → [Link2: file:line] → [Link3: file:line] → IMPACT
```

### Link Requirements (ALL MANDATORY)
| Field | Description |
|-------|-------------|
| **Trigger** | Specific condition that activates this link |
| **File:Line** | Exact source code location (verified) |
| **Effect** | What state change occurs |
| **Trust Boundary** | What trusted assumption is violated |
| **Connects To** | How output enables next link |

---

## PATTERN 1: THE DOOMSDAY (9-PHASE)

### Phase 0: Preparation
```
[R1] Rogue key registration → epoch_stakes.rs:84
     pk_rogue = pk_a - Σpk_h → wrapped PopVerified
     
[R2] Stake accumulation → U64_MAX/2 via delegation
     Target: stake ≥ U64_MAX/2 for saturation
```

### Phase 1: Epoch Boundary Exploitation
```
[E1] Epoch transition (natural, ~2-3 days)
     bls_sigverifier.rs:252 → rank_map_cache retains old epoch
     
[E2] Submit votes for PREVIOUS epoch slots
     Cache hit returns STALE stake weights
     Stake changes IGNORED
```

### Phase 2: Migration Genesis Split
```
[G1] Feature flag activation → migration.rs:465
     MIGRATION_SLOT_OFFSET = 5000 slots
     
[G2] EQUIVOCATION — TWO GENESIS BLOCKS
     migration.rs:562 & 616 — TWO independent transitions:
     Path A: set_genesis_block(G1) → ReadyToEnable
     Path B: set_genesis_cert(G2) → ReadyToEnable
     G1 ≠ G2 → BOTH transition with DIFFERENT genesis
     
     Split: 50% get G1, 50% get G2
     Each: 62% honest + 20% attacker = 82% → BOTH certify!
     Genesis threshold: 82% (assumes 20% malicious)
     CONTRADICTION: Honest(80%) < Genesis(82%) BUT 40% triggers fallback
```

### Phase 3: Consensus Hijack
```
[H1] Chained Block ID Bypass → blockstore_processor.rs:2104
     Parent missing → Pass unconditionally
     Attacker: chained_block_id = H(attacker_parent)
     
[H2] Optimistic Parent Race → block_creation_loop.rs:482
     select_freshest_window prefers higher start_slot
     Attacker injects forged OptimisticParent with higher slot
     
[H3] RESULT: Attacker decides parent block
```

### Phase 4: Full Compromise
```
[C1] Rogue Key in Aggregation → epoch_stakes.rs:84 + cert_verify.rs:209
     new_unchecked on aggregate → attacker forges signatures ALONE
     
[C2] Bitmap Ambiguity (Base3→Base2) → cert_verify.rs:149
     verify_base3 accepts Base2-decoded bitmap
     Fallback payload SKIPPED entirely
     
[C3] Double-Count + Base3 Overlap → cert_verify.rs:86 + aggregate_accumulator.rs:134
     Primary ranks = Fallback ranks = {r1,r2,r3,r4}
     aggregate_stake = 2×actual = 40% → 80% effective
     Threshold 60% → 80% PASSES!
     
[C4] Parallel Verification DoS → cert_verify.rs:223 + bls_vote_sigverify.rs:347
     Base3 certs = 2× CPU, no rate limit
     Thread pool exhausted
     
[C5] Missing Subgroup Check → cert_verify.rs:238
     new_unchecked bypasses validation on aggregate
```

### Phase 5: Consensus Stall
```
[S1] UpdateParent TOCTOU Cascade → update_parent.rs:151, 200, 325
     3 independent TOCTOU points
     P(race) = 99.33% @ 1000 attempts
     
[S2] Soft-Dead Promotion Race → update_parent.rs:200
     Valid fork PERMANENTLY MARKED DEAD
     Requires manual intervention
```

### Phase 6: Leader Denial
```
[L1] Stake Saturation → aggregate_accumulator.rs:65,119
     stake ≥ U64_MAX/2 → Fraction(1.0) always passes
     
[L2] Base3 Overlap + Stale ParentReady → parent_ready_tracker.rs:282
     set_root() doesn't update highest
     highest_parent_ready()=1000 > 600 → MissedWindow → SKIPS BLOCK!
     
[L3] Unbounded CPU Loops → parent_ready_tracker.rs:149,187
     O(n²) unbounded → leader thread STARVED
```

### Phase 7: State Corruption
```
[C1] Genesis Cert Replay → blockstore_processor.rs:1869
     Cert accepted without re-verification
     
[C2] VoM Bypass → blockstore_processor.rs:1705
     vote_only_bank set at creation only
     
[C3] TowerBFT Purge → replay_stage.rs:1713
     use-after-free during purge
```

### Phase 8: Crypto Break
```
[B1] Rogue Key Registration → epoch_stakes.rs:84
     rogue key enters rank_map as PopVerified
     
[B2] Bitmap Ambiguity + Parallel Exhaustion
     
[B3] Vote Pool Cross-Type Conflict → vote_pool.rs:53
     Notarize A + Finalize B in SAME SLOT allowed!
     
[B4] RESULT: Forged certs with ARBITRARY stake weights
```

### Phase 9: DOOMSDAY
```
CHAIN A (Genesis G1)     CHAIN B (Genesis G2)
├─ 50% validators        ├─ 50% validators  
├─ Attacker produces all ├─ Attacker produces all
├─ Drains 100% value     ├─ Drains 100% value
└─ "Valid" chain         └─ "Valid" chain

RESULT: 2 chains, G1≠G2, attacker controls both
       200% value extraction, network DEAD
```

---

## PATTERN 2: MINIMAL DESTROY BUTTON (VOTE POOL)

### 2-Link Chain
```
LINK 1: vote_pool.rs:114-133 (Notarize check)
        MISSING: || self.finalize[rank]
        
LINK 2: vote_pool.rs:77-90 (Finalize check)  
        MISSING: || self.notar[rank].is_some()

CHAIN: Notarize(Block_A) + Finalize(Block_B) same slot
       BOTH accepted → CONFLICTING FINALITIES
       
IMPACT: Consensus Safety = DESTROYED
REQUIREMENT: 1 validator key (0% stake)
```

---

## PATTERN 3: BLS CRYPTO BREAK (6-VECTOR)

```
LINK 1: Rogue key registration → epoch_stakes.rs:84
LINK 2: Base3→Base2 bitmap bypass → cert_verify.rs:149
LINK 3: Stale epoch stakes cache → bls_sigverifier.rs:252
LINK 4: Parallel verification DoS → cert_verify.rs:223
LINK 5: Vote pool cross-type conflict → vote_pool.rs:53
LINK 6: Missing subgroup check → cert_verify.rs:238

CHAIN: Forged certificates with ARBITRARY stake weights
IMPACT: Full consensus compromise
```

---

## PATTERN 4: BLOCKSTORE TOCTOU CASCADE

```
LINK 1: Chained Block ID Bypass → blockstore_processor.rs:2104
LINK 2: Optimistic Parent Race → block_creation_loop.rs:482
LINK 3: Soft-Dead Promotion Race → update_parent.rs:200
LINK 4: Child Bank Deferral → update_parent.rs:80

CHAIN: Valid fork marked DEAD permanently
IMPACT: Consensus stall, manual intervention required
```

---

## PATTERN 5: MIGRATION REPLAY ATTACK

```
LINK 1: Genesis Cert Replay → blockstore_processor.rs:1869
LINK 2: VoM Bypass → blockstore_processor.rs:1705
LINK 3: TowerBFT Purge UAF → replay_stage.rs:1713
LINK 4: Super-OC Fork → migration.rs (20% stake)

CHAIN: Invalid blocks in ledger, state diverged
IMPACT: State corruption, network split
```

---

## CHAIN VALIDATION CHECKLIST

Before declaring a chain proven:

- [ ] Every link has exact file:line (verified by reading code)
- [ ] Links are CONNECTED (output of A = input of B)
- [ ] Each link has clear trigger condition
- [ ] Each link crosses a trust boundary
- [ ] Combined impact = CONSENSUS SAFETY / LIVENESS / FUNDS
- [ ] Working PoC demonstrates the chain end-to-end
- [ ] Tried to break it yourself (adversarial validation)
- [ ] No link is speculative or theoretical

---

## CHAIN REPORT FORMAT

```
VULNERABILITY: [Class]
ENTRY: [Pre-auth/Post-auth/Unauth]
CHAIN: [Link1: file:line] → [Link2: file:line] → ... → IMPACT
IMPACT: [Consensus Safety / Liveness / Funds]
POC: [Working Exploit]
EVIDENCE: [Line numbers proving each link]
CONFIDENCE: PROVEN
MITIGATION: [Root cause + Fix per link]
```