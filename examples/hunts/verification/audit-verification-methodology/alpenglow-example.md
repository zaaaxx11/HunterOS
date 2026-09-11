# Alpenglow worked example (cut from audit-verification-methodology SKILL.md 2026-09-07)

Cut verbatim from the shipped SKILL.md during the 2026-09-07 S2b-2 follow-up pass (per-target case material preserved, not deleted; reusable methodology stays in the skill body).

---

## REAL-WORLD EXAMPLE (This Session)

### External Report Claims vs Reality

| Claim | Reported Location | Actual Code | Classification |
|-------|-------------------|-------------|----------------|
| Cache miss panic | `bls_vote_sigverify.rs:110` | File doesn't exist | **FALSE** |
| 3x unsafe PopVerified | `bls_vote_sigverify.rs:365`, `bls_cert_sigverify.rs:365` | Files don't exist / wrong line count | **FALSE** (2/3), **PARTIAL** (1/3) |
| Base2/Base3 ambiguity | `cert_verify.rs:182-185` | Format is self-describing | **FALSE** |
| Epoch transition replay | `consensus_pool.rs:357-381` | Rejected as OldMessage | **OVERRATED** |

### Independent Findings (All VERIFIED)

| Finding | File:Line | Classification |
|---------|-----------|----------------|
| Stake double-count Base3 | `cert_verify.rs:86,124-134` | **VERIFIED** |
| NotarizeFallback limit=3 | `vote_pool.rs:13,141` | **VERIFIED** |
| Thread exhaustion rayon | `bls_sigverifier.rs:222-227` | **VERIFIED** |
| Banlist saturation DoS | `bls_cert_sigverify.rs:169-176` | **VERIFIED** |
| Migration race condition | `migration.rs:562,616` | **VERIFIED** |

---
