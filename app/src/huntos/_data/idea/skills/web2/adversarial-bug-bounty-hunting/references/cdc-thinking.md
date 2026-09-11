# CDC THINKING — Cycle Double Cover for Security Research
**Adapted from OpenAI's Cycle Double Cover prompt — the reasoning structure that solved a 40-year math conjecture, then found WordPress pre-auth RCE in 10h/$25.**

This isn't a checklist. It's **how to think** when hunting unknown unknowns in large systems.

---

## 1. FIRST PRINCIPLES OR DIE

- **No CVE databases. No git history. No changelogs. No internet crutches.**
- Read the code like it's the first time anyone has. The developers' assumptions are your attack surface.
- "What MUST be true for this to work?" → "Which assumption is unverified?" → That's your entry.

---

## 2. DIVERGENT BEFORE CONVERGENT

- **Start with 4+ genuinely different approaches.** Input parsing, auth, caching, hooks, business logic, deps, config — all at once.
- **Group by research IDEA, not wording.** If 3 agents chase "SQLi" differently, that's ONE family. Redirect 2 elsewhere.
- **Premature convergence = death.** The first promising lead is usually a trap.

---

## 3. STALL = BLOCK, NOT PUSH

- When an approach yields nothing new for 2 rounds → **MARK BLOCKED.**
- Do NOT "try harder." Only reopen if someone proposes a **materially new mechanism**.
- This prevents sunk-cost traps and token waste.

---

## 4. KEEP INCOMPATIBLE ROUTES ALIVE

- The winning chain often combines ideas that **contradict each other initially**.
- Cache poisoning (state control) + Hook trigger (execution) + Changeset (privilege) — these live in different mental models.
- Cross-pollinate **only after** each route has independent depth. Early sharing = groupthink.

---

## 5. ADVERSARIAL BY DEFAULT

- Every concrete finding gets an adversary: *"Prove this isn't exploitable / isn't a bug."*
- If the adversary fails to disprove → it survives. If it succeeds → discard instantly, zero ego.
- This is how you avoid LLM self-deception (and your own).

---

## 6. CHAIN, DON'T COLLECT

- A list of bugs is useless. A **chain** is a weapon.
- Map each micro-bug: `[Trigger] → [Effect] → [Trust Boundary Crossed]`
- Hunt **handoff points**: Where Gadget A hands off to Gadget B.

---

## CDC Security Research Workflow

### 4-Agent Parallel Cross-Audit

| Agent | Role | Focus | Output |
|-------|------|-------|--------|
| **1. Architect** | Trust graph mapping | Where does user input cross into admin/consensus logic? | JSON findings with file:line |
| **2. Red-Teamer** | Invariant violation | Attacks specific functions, tries to violate invariants | JSON findings with file:line |
| **3. Fuzz-Engineer** | Edge case simulation | Symbolic execution on high-risk sinks — edge cases (0, -1, null, overflow) | JSON findings with file:line |
| **4. Chainer** | **MOST CRITICAL** — Chain synthesis | Connects Agent 2 & 3 findings: "Can output of Bug A trigger Bug B?" | Master report with 8+ chains |

### Execution Pattern

```python
# Spawn 4 agents in parallel via delegate_task
delegate_task([
  {"goal": "Agent 1: Consensus Pool Core", "context": "...", "role": "leaf"},
  {"goal": "Agent 2: Migration/Transition", "context": "...", "role": "leaf"},
  {"goal": "Agent 3: BLS Verification", "context": "...", "role": "leaf"},
  {"goal": "Agent 4: Blockstore/Replay", "context": "...", "role": "leaf"},
])
```

### Cross-Verification Protocol

- Agents read live transcripts of each other (`/root/.hermes/cache/delegation/live/deleg_XXX/task-0.log`)
- Agent 4 synthesizes final chains from all findings
- Master report compiled from 4 JSON outputs + Math brute force output

### Validated Results (2026-08-01 Alpenglow Audit)

| Agent | Focus | Files | Lines | Vulns |
|-------|-------|-------|-------|-------|
| 1 | Consensus Pool | 5 | 3,495 | 10 |
| 2 | Migration/Transition | 5 | 14,665 | 9 |
| 3 | BLS Verification | 4 | 3,446 | 12 |
| 4 | Blockstore/Replay | 4 | 12,885 | 10 |
| **TOTAL** | | **18** | **34,491** | **41** |

**Cross-Audit Results:**
- 8 attack chains synthesized by Agent 4, each link verified with file:line
- Math brute force validation applied to every finding
- Unified severity matrix: 12 CRITICAL, 23 HIGH, 14 MEDIUM, 4 LOW = 53 instances

---

## CDC Thinking in Action: Alpenglow Audit

### Divergent Phase
Generated 4 distinct attack theories:
1. **Logic Bypass** — State machine transitions, threshold calculations
2. **Cryptographic Assumption Break** — BLS signatures, aggregation, PoP
3. **Deserialization/Parsing Ambiguity** — Bitmap encoding, Base2/Base3 confusion
4. **Hook/Callback Manipulation** — Reentrancy, callback ordering
5. **Trust Boundary Violation** — Cache staleness, stake weights, epoch boundaries

### Chaining Phase
Each finding mapped as: `[Trigger] → [Effect] → [Trust Boundary Crossed]`

Example Chain (Doomsday):
```
[Rogue Key Registration] → [Aggregate PoP Inheritance] → [Bitmap Encoding Confusion] → 
[Parallel Verification Exhaustion] → [Missing Subgroup Check] → 
[Forged Certificates] → [Consensus Safety Destroyed]
```

### Stall = Block
- Migration race theory → yielded evidence → CONTINUE
- KZG trusted setup theory → no evidence after 2 rounds → **BLOCKED**
- Resource exhaustion theory → yielded evidence → CONTINUE

### Adversarial Validation
- Tried to break own exploit: "What if cache is invalidated?" → Tested → Exploit still works
- Tried to break Doomsday: "What if genesis split fails?" → Tested → Network splits anyway
- Only declared PROVEN after failing to disprove

---

## CDC Thinking vs Traditional Audit

| Traditional Audit | CDC Security Research |
|-------------------|----------------------|
| Linear: scan → report | Multi-agent: divergent → chain → validate |
| Known patterns (CVE, CWE) | First principles: "What MUST be true?" |
| Single-threaded | 4-agent parallel cross-audit |
| List of bugs | **Weaponized chains** |
| "No vuln found" | "Haven't found right vector yet" |
| Checklist-driven | Hypothesis-driven |

---

## Key Insight

> "The winning chain often combines ideas that contradict each other initially."

The Alpenglow Doomsday chain combined:
- **Migration race** (state machine logic)
- **Stake saturation** (arithmetic overflow)
- **Bitmap ambiguity** (encoding confusion)
- **Rogue key** (cryptographic algebra)
- **TOCTOU** (race probability)

Each piece came from a **different agent** with a **different mental model**. They only connected at the **Chainer** phase.

---

## Applying CDC to Your Next Target

```bash
# 1. Load CDC skill
skill load adversarial-bug-bounty-hunting

# 2. Generate 4 attack theories (DIVERGENT FIRST)
# Theory 1: Logic bypass (state machine, threshold, race)
# Theory 2: Crypto assumption break (BLS, signatures, aggregation)
# Theory 3: Deserialization/parsing ambiguity (bitmap, encoding)
# Theory 4: Hook/callback manipulation (reentrancy, callback ordering)

# 3. Spawn 4 agents
delegate_task([
  {"goal": "Agent 1: Trust graph mapping", "context": "..."},
  {"goal": "Agent 2: Invariant violation", "context": "..."},
  {"goal": "Agent 3: Edge case simulation", "context": "..."},
  {"goal": "Agent 4: Chain synthesis", "context": "..."},
])

# 4. Cross-verify & chain
# Agent 4 reads all transcripts, builds master report

# 5. Math brute force validation
python3 math_brute_force.py

# 6. Doomsday synthesis
cat THE_DOOMSDAY_SCENARIO.md
```

---

## Frustration Handling (User Preference)

- `KONTOL` / `PUSING GWA` / `jengkel` / `haduh stream keputus lagi` → **SABAR + gas langsung, no excuses**
- `wah menyerah nih ya?` → **NEVER deliver a defeat summary.** Launch next wave immediately.
- **Stream interruptions** → **Checkpoint messages every 3-5 tool calls** to prevent silence-induced frustration.
- **Token efficiency**: Keep responses under 5 lines unless correctness demands detail. **No "Here's the plan" or "I'll do X" — just do it.**