# MATHEMATICAL BRUTE FORCE ANALYSIS — TEMPLATES

## Principle
**Math is the key.** Don't just scan — compute. Every consensus parameter has mathematical relationships. Find the contradictions.

---

## 1. THRESHOLD ALGEBRA

### Template: Check All Threshold Combinations
```python
def analyze_thresholds(thresholds: dict) -> list:
    """
    thresholds = {
        'safe_to_notar': 0.40,
        'notarize': 0.60,
        'finalize': 0.67,
        'genesis': 0.82,
        'notarize_fallback': 0.60
    }
    """
    issues = []
    names = list(thresholds.keys())
    
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            a, b = names[i], names[j]
            sum_ab = thresholds[a] + thresholds[b]
            
            if sum_ab > 1.0:
                issues.append({
                    'type': 'THRESHOLD_GAP',
                    'thresholds': (a, b),
                    'values': (thresholds[a], thresholds[b]),
                    'sum': sum_ab,
                    'impact': f'Attacker with {thresholds[a]*100:.0f}% can force {b} path'
                })
            
            # Check if honest stake < threshold but fallback triggers
            honest_stake = 1.0 - 0.20  # 20% malicious
            if honest_stake < thresholds[a] and thresholds[b] < 0.5:
                issues.append({
                    'type': 'FALLBACK_TRIGGER',
                    'thresholds': (a, b),
                    'impact': f'Honest({honest_stake*100:.0f}%) < {a}({thresholds[a]*100:.0f}%) but {b}({thresholds[b]*100:.0f}%) triggers'
                })
    
    return issues
```

### Solana/Alpenglow Specific
| Threshold | Value | Issues |
|-----------|-------|--------|
| SafeToNotar | 40% | — |
| Notarize | 60% | **20% gap** from SafeToNotar |
| Finalize | 67% | **27% gap** from SafeToSkip |
| Genesis | 82% | **> FastFinalize(80%)** — inconsistent! |
| NotarizeFallback | 60% | Same as Notarize |

**Key Finding:** 20% attacker + 20% coerced = 40% → triggers SafeToNotar → forces NotarizeFallback path

---

## 2. SATURATION ARITHMETIC

### u64::MAX Saturation Bypass
```python
U64_MAX = 18_446_744_073_709_551_615

def check_saturation_bypass(stake_per_validator: int, num_validators: int = 100) -> dict:
    total_stake = stake_per_validator * num_validators
    double_stake = total_stake * 2
    
    if double_stake > U64_MAX:
        return {
            'vulnerable': True,
            'stake_per_validator': stake_per_validator,
            'total_stake': total_stake,
            'double_stake': double_stake,
            'saturates_at': U64_MAX,
            'fraction': 1.0,  # Fraction(U64_MAX, total) = 1.0
            'impact': 'ALWAYS passes ANY threshold'
        }
    
    # Minimum to saturate
    min_stake = U64_MAX // (2 * num_validators)
    return {
        'vulnerable': False,
        'min_stake_to_saturate': min_stake
    }

# Result: min stake per validator = 184,467,440,737,095,516
```

### Saturating Add Double-Count
```python
# Base3: primary ranks = fallback ranks = {r1,r2,r3,r4}
# accumulate_stake called TWICE for same ranks
# 40% stake → 80% effective → passes 60% threshold
```

---

## 3. BITMAP ENCODING AMBIGUITY

### Base2 vs Base3 Decode
```python
# solana-signer-store decode() behavior:
# - Input: bitmap bytes
# - Output: Decoded::Base2(ranks) OR Decoded::Base3(ranks, fallback_ranks)
# - Format is SELF-DESCRIBING in bytes — NOT context-dependent

# VULNERABILITY: verify_base3() accepts Base2-decoded bitmap
# verify_base3() calls verify_single_vote_signature() for Base2
# Fallback payload verification SKIPPED entirely!

# Attack:
# 1. Craft NotarizeFallback cert (requires Base3)
# 2. Encode bitmap as Base2 (single payload)
# 3. verify_base3 decodes as Base2
# 4. Calls verify_single_vote_signature(primary_payload_only)
# 5. Fallback payload NEVER verified
# 6. Combined with double-count: 30% primary → 60% effective → PASSES
```

---

## 4. TOCTOU PROBABILITY

### Race Window Calculation
```python
def toctou_probability(window_us: float, interval_us: float, attempts: int) -> float:
    """
    window_us: TOCTOU race window in microseconds
    interval_us: Operation interval in microseconds  
    attempts: Number of attack attempts
    """
    p_single = window_us / interval_us
    if p_single >= 1.0:
        return 1.0
    return 1.0 - (1.0 - p_single) ** attempts

# Example:
# Slot: 400ms, Shred: 20ms (20 shreds/slot)
# TOCTOU window: ~100μs
# Shred interval: 20,000μs
# P(success) = 100/20000 = 0.5%
# With 1000 attempts: 1 - (0.995)^1000 = 99.33%
```

---

## 5. BLS ROGUE KEY MATHEMATICS

### Rogue Key Construction
```python
# Attacker wants agg_pk = pk_attacker
# Honest validators have pk_honest_1 ... pk_honest_n
# Attacker registers: pk_rogue = pk_attacker - Σ pk_honest_i

# During aggregation:
# agg_pk = pk_rogue + Σ pk_honest_i = pk_attacker

# Attacker signs with sk_attacker
# verify(agg_pk, signature) → VALID!

# REQUIREMENTS:
# 1. Attacker can register rogue key with valid PoP
# 2. Aggregate function doesn't check subgroup membership on result
# 3. new_unchecked() bypasses validation on aggregate
```

### PoP Verification Bypass
```python
# cert_verify.rs:209 - unsafe PopVerified::new_unchecked()
# Assumes: "Because every constituent key has already proven possession,
# the resulting aggregated key inherits this property and is mathematically protected against rogue-key attacks"

# THIS ASSUMPTION BREAKS WHEN:
# 1. Rank map is stale (epoch transition)
# 2. Rank map is poisoned (rogue key inserted)
# 3. Bitmap encoding ambiguity (Base2 vs Base3)
```

---

## 6. MIGRATION GENESIS SPLIT

### State Machine Analysis
```python
# migration.rs: Two independent transitions to ReadyToEnable

# Path A: set_genesis_block(G1)
#   if genesis_cert == G1: phase = ReadyToEnable

# Path B: set_genesis_certificate(G2)  
#   if genesis_block == G2: phase = ReadyToEnable

# ATTACK: G1 ≠ G2
# Attacker equivocates: G1 to 50%, G2 to 50%
# Each half: 62% honest + 20% attacker = 82% → BOTH certify!
# Genesis threshold: 82% = 100% - 18% (assumes 20% malicious)
# CONTRADICTION: Honest(80%) < Genesis(82%) BUT 40% triggers fallback
```

---

## 7. CONSENSUS STALL PROBABILITY

### UpdateParent TOCTOU Cascade
```python
# 3 independent TOCTOU points in update_parent.rs
# update_parent.rs:151 (check) → 169 (clear) → gap
# update_parent.rs:200 (promote to hard-dead) → concurrent UpdateParent
# update_parent.rs:325 (check) → 358 (clear_slots) → gap

# Each: P(race) = 0.5% per try
# Combined: 1 - (0.995)^3 = 1.49% per slot
# With 1000 slots: ~99.99% guaranteed success
```

---

## QUICK REFERENCE: ALL MATH FINDINGS

| # | Finding | Math Proof | Severity |
|---|---------|------------|----------|
| 1 | Threshold Inconsistency | 40% ≠ 60% ≠ 67% ≠ 82% | CRITICAL |
| 2 | Stake Saturation | U64_MAX cap → Fraction(1.0) | CRITICAL |
| 3 | Double-Count + Base3 | 40% → 80% effective | CRITICAL |
| 4 | Bitmap Ambiguity | Base3→Base2: fallback skipped | HIGH |
| 5 | Rogue Key | pk_rogue = pk_a - Σpk_h → agg_pk = pk_a | HIGH |
| 6 | Migration Race | 2 transitions → ReadyToEnable with G1≠G2 | CRITICAL |
| 7 | TOCTOU Probability | 99.33% @ 1000 attempts | HIGH |
| 8 | Unbounded Loops | O(n²) no limit | HIGH |
| 9 | Stale Cache | 1 epoch window = 2-3 days | HIGH |
| 10 | Missing Subgroup | new_unchecked bypasses validation | MEDIUM |