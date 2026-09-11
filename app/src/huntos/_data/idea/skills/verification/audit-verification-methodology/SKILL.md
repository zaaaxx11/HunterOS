---
name: audit-verification-methodology
description: "verify audit claims against actual source code before repeating them"
metadata:
  version: 1.0.0
  hermes:
    tags: [audit, verification, truth-enforcement, anti-hyperbole, bug-bounty]
    category: security
---

# Audit Verification Methodology — Truth Enforcement Protocol

## Purpose

This skill captures the methodology for **verifying every security claim against actual source code** before reporting. Born from a session where an external audit report was audited — 2/4 claims false, 1 partial, 1 overrated — while 5 verified findings were discovered independently.

**Core Principle:** Trust nothing. Verify everything against actual source code. Hyperbolic claims destroy credibility.

---

## TRUTH ENFORCEMENT PROTOCOL (Non-Negotiable)

### NEVER (Auto-Reject Output if Violated)

| Violation | Correct Behavior |
|-----------|------------------|
| Inflate time spent ("21 jam" when 12 menit) | STATE ACTUAL ELAPSED or "unknown" |
| Claim file exists when not verified | "File not found" or "Not in codebase" |
| Multiply findings ("3 instances" when 1) | COUNT EXACT, cite line numbers |
| Claim exploit works without PoC | "Theoretical" or "PoC pending" |
| Use "confirmed" without source code line | "Unverified" |
| Say "audit complete" when files unread | List unread files |

### ALWAYS (Mandatory Before Delivery)

- Cite exact `file:line` for every claim
- Distinguish: **VERIFIED** (code seen) vs **THEORETICAL** (logic only) vs **FALSE** (disproven)
- Report failed vectors honestly: "Checked X, not vulnerable because Y"
- Time claims: "Started at HH:MM, now HH:MM" or "Duration unknown"
- PoC status: "Compiles/runs" or "Logic only, not tested"

### SELF-CHECK BEFORE OUTPUT (5-Point)

1. Did I read the actual file? → If no, don't claim content
2. Is the line number exact? → If no, say "approx line X"
3. Did PoC actually run? → If no, "PoC logic only"
4. Am I exaggerating severity? → Map to actual impact chain
5. Can I falsify my own claim? → Try to break it first

**VIOLATION = IMMEDIATE CORRECTION** — No excuses, no "I meant", just fix and acknowledge.

---

## EXTERNAL REPORT AUDIT WORKFLOW

When operator provides an external report (PDF, MD, URL, GitHub advisory):

### Phase 1: Inventory Claims (5 min)
- Extract every specific technical claim
- Note file paths, line numbers, function names mentioned
- Flag claims without source references

### Phase 2: Verify Against Source (30-60 min)
- For each claim: `search_files` for file, read exact lines
- Check: file exists? function exists? line numbers accurate?
- Classify each claim:

| Classification | Criteria |
|----------------|----------|
| **VERIFIED** | Code matches claim exactly, line numbers correct |
| **PARTIAL** | Core mechanism exists but details wrong (count, lines, scenario) |
| **OVERRATED** | Mechanism exists but attack scenario flawed/impractical |
| **FALSE** | File doesn't exist, function doesn't exist, or claim contradicts code |

### Phase 3: Report Only Verified Findings
- Discard FALSE claims entirely
- Note PARTIAL/OVERRATED with exact discrepancies
- Only actionable findings = VERIFIED + your own independent discoveries

---

## CLAIM CLASSIFICATION STANDARDS

### VERIFIED
- Read actual source code
- Exact line numbers cited
- Logic traceable end-to-end
- PoC compiles/runs or logic demonstrably sound

### THEORETICAL
- Logical deduction only, no code verification
- "If X then Y" without confirming X exists
- Label explicitly: "THEORETICAL — not verified against source"

### FALSE
- File not in codebase
- Function doesn't exist
- Line numbers don't match
- Claim contradicts actual code behavior

### OVERRATED
- Mechanism exists but impact exaggerated
- Attack scenario requires unrealistic conditions
- Impact chain has broken link

### BLOCKED (New — Cross-Audit Filter)
- Code exists but execution blocked by `checked` math / `Assert` / `throw` / dedup / dead code
- Example: `IsValidAmount` bolong but caller is dead (`grep -rn ValidateSwapTokenInput` = 1 hit), real path `decimal.ToInt64` throws on overflow

### HYGIENE
- Real but not fund-theft: info leak, privacy enumeration, rate-limit, DOS, spam
- Example: anon `GET /api/app/cross-chain-transfers` leaks amounts/chains — recon amplifier only if contract missing dedup (it doesn't)

## CROSS-AUDIT FILTER — BRUTAL NO-OVERSELL

When cross-auditing findings from agents A/B/C, classify each alleged weakness into exactly one:

| # | Class | Meaning | Evidence required |
|---|-------|---------|-------------------|
| 1 | **PROVEN fund theft** | Pre-auth mint/drain — attacker mints without auth and `Transfer` succeeds | `file:line` of missing check + live Tx hash showing the mint/drain |
| 2 | **PROVEN admin takeover** | Any addr can become admin/controller/pause-controller | `file:line` of missing sender assert + live Tx where anon privileged call succeeds |
| 3 | **HYGIENE / info leak** | Real but not theft — enumeration, privacy, rate-limit, DOS | `file:line` of anon route + proof it does NOT reach the mint/withdrawal gate |
| 4 | **False positive** | Dead code, blocked by checked math / assert / throw, dedup, frozen-at-zero, unreachable branch | `grep` caller count + the blocking check's `file:line` |

**Required output table (no oversell):**
```
weakness | file:line | claimed impact | real impact | verdict (OPEN/BLOCKED/HYGIENE)
```
- `OPEN` = proven theft/takeover. `BLOCKED` = the vulnerable-looking string exists but a `checked`/`Assert`/`throw`/dedup/dead-code gate blocks it — do NOT report as theft. `HYGIENE` = real but not theft — report as LOW, defense-in-depth, don't inflate to CRITICAL.

Generic demotion traps to re-check before any theft claim: (1) an anon read endpoint is an oracle-gated recon leak, not a mint — trace who can actually reach the state-changing entry; (2) a missing input check that is never called, or whose downstream conversion throws instead of wrapping, is dead, not exploitable; (3) an unset limit usually means frozen-at-zero (DoS), not unlimited; (4) unchecked-looking arithmetic is often wrapped by `checked` math or a bytecode validator — verify the real path throws. (The eBridge 2026-08-15 worked example with the four canonical traps and verification commands is preserved at examples/hunts/verification/audit-verification-methodology/ebridge-auditor1-sections.md, with the full case at examples/hunts/verification/audit-verification-methodology/references/aelf-ebridge-cross-audit-filter-2026-08-15.md.)

---

## RE-AUDIT (ADVERSARIAL) — RPC AUTH PATTERN

When re-auditing a prior RPC auth bypass claim (CORS + loopback + BasicAuth + whitelist), classify every claim as **VERIFIED FACT** (`file:line` proven) vs **ASSUMPTION** (to disprove), and prove the trust primitive itself: read the CORS library defaults and the handler-ordering chain (whitelist → BasicAuth → loopback shortcuts), confirm `RemoteAddr` is kernel TCP and not spoofable via `X-Forwarded-For`, and establish what the default bind + config actually gate. Then run the PoC matrix — browser `fetch` with `Origin: evil.com` + `Content-Type: application/json` for CSRF, `curl -H Origin` for CORS `*`, `curl -H X-Forwarded-For` for no-spoof, plus `Authorization` variants — always stating prerequisites (same-host browser vs `0.0.0.0` rebind).
(The AUDITOR-1 bityuan worked example with the 7-step workflow and file:line anchors is preserved at examples/hunts/verification/audit-verification-methodology/ebridge-auditor1-sections.md; the underlying case at examples/hunts/web3/blockchain-rpc-attack-surface-audit/references/bityuan-rpc-auth-re-audit-2026-08.md.)

## AUDIT WORKFLOW INTEGRATION

### Pre-Audit (Before Spawning Agents)
```bash
# 1. Inventory target files
find <target> -name "*.rs" -o -name "*.sol" -o -name "*.py" | head -50

# 2. Quick existence check for claimed files
ls <claimed_file_path> 2>/dev/null || echo "NOT FOUND: <claimed_file_path>"

# 3. Read 5-10 critical files to establish baseline
read_file <critical_file>
```

### During Audit (Per Finding)
```python
# For each claim:
claim = "bls_vote_sigverify.rs:110 has .unwrap() panic"
file_exists = search_files("bls_vote_sigverify.rs", target="files")
if not file_exists:
    classification = "FALSE"
else:
    content = read_file("bls-sigverify/src/bls_vote_sigverify.rs")
    if "unwrap()" in content at line 110:
        classification = "VERIFIED"
    else:
        classification = "OVERRATED" if ".unwrap()" elsewhere else "FALSE"
```

### Post-Audit (Before Report)
- [ ] Every claim has `file:line` citation
- [ ] No claim labeled "confirmed" without source verification
- [ ] Time spent stated accurately or "unknown"
- [ ] PoC status explicit for each exploit
- [ ] Failed vectors documented with reason

---

## REAL-WORLD EXAMPLE

(The Alpenglow session's claims-vs-reality table and independent VERIFIED findings table — the worked case behind this protocol — are preserved at examples/hunts/verification/audit-verification-methodology/alpenglow-example.md, with the session log at examples/hunts/verification/audit-verification-methodology/references/alpenglow-audit-verification-log.md.)

## ANTI-HYPERBOLE CHECKLIST (Per Output)

Before every response containing findings:

- [ ] No time inflation (actual elapsed or "unknown")
- [ ] No file claims without `read_file`/`search_files` verification
- [ ] No multiplied findings (exact count + line numbers)
- [ ] No "exploit works" without PoC status
- [ ] No "confirmed" without `file:line`
- [ ] No "audit complete" with unread files listed
- [ ] VERIFIED/THEORETICAL/FALSE labels on all claims
- [ ] Failed vectors documented with reason

---

## INTEGRATION WITH OTHER SKILLS

| Skill | Integration Point |
|-------|-------------------|
| `bug-bounty-agent` | Apply Truth Enforcement before every report delivery |
| `adversarial-exploit-chains` | Verify each chain link against source before chaining |
| `predator-recon` | Verify recon claims (endpoints, params) against actual responses |
| `on-chain-exploit-workflow` | Verify contract state/bytecode before exploit dev |
| `smart-contract-exploit-pocs` | PoC must compile/run — "logic only" labeled explicitly |

---

## TEMPLATES

### Claim Verification Log Template
```markdown
## Claim Verification Log — <Target> — <Date>

| # | Claim | File | Line | Status | Evidence |
|---|-------|------|------|--------|----------|
| 1 | ... | ... | ... | VERIFIED/PARTIAL/OVERRATED/FALSE | ... |
| 2 | ... | ... | ... | ... | ... |

### Failed Vectors
| # | Vector Tested | File | Result | Reason Not Vulnerable |
|---|---------------|------|--------|----------------------|
| 1 | ... | ... | Not vuln | ... |
| 2 | ... | ... | Not vuln | ... |

### Time Tracking
- Started: HH:MM
- Current: HH:MM
- Duration: XX min / unknown
```

### PoC Status Template
```markdown
## PoC Status

| Finding | PoC File | Compiles | Runs | Status |
|---------|----------|----------|------|--------|
| Stake double-count | /tmp/alpenglow_poc.rs | ✅ | ✅ | Compiles/runs |
| Migration race | (logic only) | N/A | N/A | Logic only, not tested |
```

---

## VERSION HISTORY

- **1.0.0** (2026-08-01): Initial creation from Alpenglow audit session. External report audit revealed 2/4 FALSE, 1 PARTIAL, 1 OVERRATED. 5 independent VERIFIED findings discovered. Anti-hyperbole protocol added to the doctrine file (now IDEA.md).
+++
- **1.1.0** (2026-08-01): **Alpenglow Consensus zero-day audit** — 41 verified vulns, 8 critical chains, 34,491 lines audited in ~6 hours via 4-agent cross-audit swarm.
  - **NEW**: 4-agent cross-audit swarm pattern (Architect/Red-Teamer/Fuzz-Engineer/Chainer)
  - **NEW**: CHAINING RULE — small findings chained into ONE exploit (file:line + connected)
  - **NEW**: Anti-hyperbole protocol integrated into the doctrine file (now IDEA.md)
  - **NEW**: 4-agent delegation pattern for parallel deep audit
  - **NEW**: 10 Alpenglow-specific patterns documented (stake double-count, migration race, UpdateParent TOCTOU, BLS rogue key, bitmap ambiguity, stake saturation, parallel exhaustion, stale epoch stakes, overlap check, unverified local certs)
  - 8 critical chains constructed from 41 verified findings
  - Anti-hyperbole protocol enforced in the doctrine file (now IDEA.md)
  - 4-agent delegation pattern for parallel deep audit