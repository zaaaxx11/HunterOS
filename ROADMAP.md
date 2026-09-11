# HUNT-OS ROADMAP — v0.4 → v1.0
# The Operating System for Hunts That Cannot Lie

Version: 1.1 (this document) · Repo state: v0.4+batch3 + conductor C0+C1 (branch) · 467 tests · CI dual-OS green
Basis: AUDIT-v0.3 (A/B), AUDIT-v0.4-1 (engineering), AUDIT-v0.4-2 (product),
REVIEW-CHECKLIST-batch3, three arbitration rounds (B-L*, R2-*, E*), IMPL-NOTES v0.4/b3,
external product review 2026-09-07 (Grok K1-K10 + Kimi K3) — merged, verified, prioritized.

---

## 0. MISSION

A hunting framework where **every claim is enforced by code, not prompt**:

- The engine's mouth is gated (claims die without ledger rows).
- The evidence ladder is mechanical (PoC must RUN inside the ledger to climb).
- Leads are research objects with a lifecycle (uncertainty is managed, not lost).
- Observations are judged deterministically (the oracle owns verdicts, not feelings).
- Reports are fingerprints (tampering is detectable, exports come from the db).

**Ground truth to beat.** Two competitor classes, both beatable:
1. *Prompt-only setups* (any agent + a good prompt): cannot return exit code 2, memory dies with context, zero enforcement. Everything we gate, they suggest.
2. *Submission managers* (BountyForge-class): manage leads and reports well, own no hunt process — no ladder, no blind adversarial review, no economic stop, no claim gate. They organize; we enforce.

**The moat thesis: ONE LEDGER.** Findings, leads, oracle events, waves, lessons,
RoE, PoC runs — all in one SQLite spine, all cross-checkable, all CI-pinned.
A prompt cannot do that; a submission manager would have to rebuild their
architecture to do it. Every milestone below widens one of those two gaps.

---

## 1. WHERE WE ARE — v0.4+batch3 inventory (enforced, tested, live)

| Surface | What is mechanically enforced | Test coverage |
|---|---|---|
| Claim gate | `PROVEN[F-n]` needs proven-live row; `PROVEN[L-n]` needs lead promoted AND its finding proven-live ("a lead claim dies with its finding"); unbound strong claims = veto; project lock binds HUNT_DB; fail-closed on any unreadable state | 27+ tests, golden corpus, 5MB worst-case <1s (was 127s) |
| Evidence ladder | theoretical → in-code → proven-live; each step needs a fresh evidence_ref; in-code needs a PoC that RAN (sha pinned at run time, different file per step); proven-live needs verifier event + adversary pass + RoE (mutate default-deny) | full matrix |
| Lead lifecycle | add (payload optional) → set payload → mutate (1 variable, anti-repeat UNIQUE, unknown births a planned precondition) → park (testable retrigger `obs :: check`) → reopen (evidence required) → kill (BOTH halves refuted or refused→park+dismissal counter) → promote (--roe-action required, provenance snapshot FROZEN) | 24-matrix + round-2/3 pins |
| Oracle | deterministic verdict (status/body/timing/size vs baseline); NaN/inf/range-refused; `ambiguous` and oracle-verdicts are oracle-owned (manual overwrite = BLOCKED); events store both feature JSONs | boundary tests |
| Wave economics | wave N+1 locked behind re-audit; findings_new computed (never typed); two-empty-waves economic stop; gap-promotions retro-linked on next open_wave | regression-pinned |
| Taxonomy | klass allow-list as data + triggers; growth only at retro | trigger tests |
| Reports | generated with sha256 footer; `verify-report` refuses tampered/no-footer files; UTF-8 deterministic (cp1252-mangled writes refused with named cause) | incl. Windows CI |
| Secrets | payload/notes/falsifier/title/evidence/precondition/mutation/retrigger/reopen — token-shapes BLOCKED at storage; display redact on old rows | field matrix |
| Integrity | single-commit promote (crash→0 orphans); CAS on finding transitions; archived lock on 6 mutator paths; corrupt DB = BLOCKED rc2 no traceback; 7 hot-path indexes; tvl/NaN refused at source | crash-injection tested |

**Process engine (proven 3×)**: spec → implementer ∥ blind adversarial auditor →
independent arbitration (every P1 reproduced by hand before it counts) →
regression pins → push → dual-OS CI. Round 1 caught the implementer's hole (B-L1),
round 2 caught the product holes (R2-01/02) AND a bug in MY OWN patch (E22),
round 3 caught a perf-test shaped wrong (B3-C4) and a spec location error (E18).

---

## 2. ROADMAP — four phases, value-ordered

Effort key: S < half-day · M < 2 days · L = a focused week (single operator).
Each milestone: goal · why now · spec sketch · acceptance (tests ARE the contract) ·
unfair advantage. NOTHING lands without tests; nothing closes without the audit round.

---

### PHASE A — THE DELIVERABLE (money edge)

> **PHASE A STATUS: DEFERRED (operator decision, 2026-09-07).** The two external
> audits disagreed on what ships next; the operator chose the proof path — a
> harder practice target + bench calibration BEFORE report engineering. The
> standing refusal (plans.md P8) holds: the partner owns the report standard,
> and report-format work stays out until one real bounty cycle proves which
> formats matter. The specs below are kept intact for when Phase A reopens.

#### A1 = M2. Platform-ready report export  [M] — DEFERRED (until one real bounty cycle)
**Goal:** `hunt report 1 --format h1|bugcrowd|immunefi|markdown` — submission
drafts generated from the same ledger that enforced the claims.
**Why now:** everything else feeds this. The report is the part programs pay for;
today an operator re-types the db into a form (30-60 min, transcription errors).
**Spec sketch:**
- `export_report(conn, tid, fmt)` gains per-format templates (title/impact/reproduction/ severity rationale/falsifier+evidence trail per finding).
- Findings section renders: ladder status, poc_run digests (sha + exit code), verifier + adversary events, **lead provenance** (promoted-from-L-2, mutations N, parked days, trigger/impact evidence — closes R2-09).
- Keep the sha256 footer; `verify-report` works on every format.
- `--format` list pinned in `hunt report --help`; unknown format = BLOCKED.
**Acceptance:**
- `test_report_h1_shape` (required sections present, no engine claims beyond ladder rows), `test_report_includes_lead_provenance`, `test_report_includes_evidence_trail`, `test_verify_report_all_formats`, `test_report_redacts_secrets` (display redact pipeline reused).
- Golden-file fixtures per format (byte-stable given same db).
**Unfair advantage:** the only local OS whose submission is generated from the
ledger its claims were enforced against — the report CANNOT be more optimistic
than the db without tripping the gate.

#### A2 = M7. Severity/CVSS rationale as data  [S] — rides with A1 (deferred)
**Goal:** `hunt finding score --id N --cvss "AV:N/AC:L/..." --rationale "..."`;
`find_contradictions` flags critical/high without rationale.
**Why:** platforms reject unscored findings; severity-from-memory is the last
honesty hole at report time; schema is one column pair.
**Acceptance:** `test_cvss_requires_rationale`, `test_unscored_critical_flagged`, report renders vector+rationale in A1 templates.

#### A3 = M9. Report signing  [S/M] — deferred with Phase A
**Goal:** `hunt report sign <file>` — HMAC (operator key, stdlib) joins the footer; `hunt report verify --sig` checks fingerprint AND signature.
**Why:** A1 outputs leave the machine; partners need tamper-evidence that does not trust the sender's word.
**Acceptance:** `test_sign_tamper_detected`, `test_verify_sig_ok`, key from env/file (never stored in db), documented in bridge README.

---

### PHASE B — MACHINE TRUTH (kills self-attestation where possible)

#### B1 = M3. Explorer/API cross-check for tx_hash artifacts  [M]
**Goal:** on `hunt verify <id> tx_hash 0x...`, fetch the explorer JSON (stdlib
urllib, config for endpoint per chain), store canonical receipt (status, block,
to/from, method) in the event detail; mismatch with evidence_ref = BLOCKED;
no network = fail-soft log (never lie).
**Why:** on-chain is the doctrine's home turf; "tx hash, checked on explorer"
stops being a promise and becomes a row. Closes the on-chain half of P1/P8.
Bonus: the same capture design solves B3's baseline freeze.
**Spec sketch:** `explorer_providers.md` (endpoint map), `capture_tx_receipt()`
with timeout + fail-soft, event kind `tx_receipt_checked`, `record_verification`
extended for artifact_type=tx_hash.
**Acceptance:** `test_tx_receipt_stored`, `test_tx_mismatch_blocked`, `test_no_network_fail_soft` (offline run stays green, logs the miss), `test_receipt_in_report` (A1 renders it).

#### B2 = P10. Oracle baseline capture (from R2-03)  [M] — design with B1
**Goal:** kill verdict-shopping at the root: baselines are CAPTURED, not typed.
`hunt oracle capture --lead N --half trigger --from <request-spec>` runs the
request through the same stdlib http path, hashes the response into the event,
and PINS baseline + candidate to the (lead, half). Re-running an oracle on a
half whose verdict came from a captured run = BLOCKED unless features changed.
**Why:** R2-03 says in-process trust cannot be minted; this narrows it to the
wire only. Cross-process attestation stays OPEN-PROBLEMS P1/P10 territory.
**Acceptance:** `test_captured_baseline_pinned`, `test_oracle_rerun_after_capture_blocked_without_delta`, `test_capture_fail_soft_offline`.

#### B3 = M8. Multi-engine hook pack  [S]
**Goal:** ship real wiring — Claude Code PostToolUse/Stop hook config, a generic
shell wrapper, one worked non-Hermes example — all piping engine output through
`bridge/claim_gate.py` and blocking on exit 2.
**Why:** the gate is the product's most un-copyable surface; today wiring is
guesswork. Distribution beats depth here.
**Acceptance:** each shipped config has a smoke script (`tests/test_hook_pack.py`
runs the wrapper against a fixture db and asserts veto propagation).

---

### PHASE C — THE FEEDBACK LOOPS (compounding)

#### C1 = M4. `hunt stats`  [S] — highest value-per-effort on the board
**Goal:** one query file, zero schema change: time-per-ladder-step, overturn rate
per lane, lane yield (which lane's findings survive cross-correction),
waves-to-first-proven, unknown-rate per lane, dismissal→reopen ratio,
oracle-unknown→confirmed conversion.
**Why:** the events table already timestamps every rung; no competitor measures
the hunting process itself. This is how the SCORE gate and economic stop get
calibrated with YOUR data instead of intuition (the home-grown answer to
BountyForge's 27k-finding corpus — smaller, but ours and per-lane).
**Acceptance:** `test_stats_shapes`, `test_stats_empty_db_clean`, rendered in `hunt brief --stats`.

#### C2 = M6. Lesson memory search  [S]
**Goal:** `hunt lesson search <query>` (LIKE + rank now, FTS5 if it earns it);
`hunt brief --global N` widens the readback beyond the per-target window.
**Why:** "memory compounds" is currently capped at ~20 lessons of scrollback;
this makes L5 real. Nearly free.
**Acceptance:** `test_lesson_search_rank`, `test_brief_global_window`.

#### C3 = M5. Cross-hunt deduplication  [M]
**Goal:** at `finding add`/`lead add`, shingle title+notes against prior rows
(stdlib); `~80% similar to F-12 on target #3 (proven-live)` warning with logged
`--override`; `hunt dupes` sweep.
**Why:** turns the db into a personal knowledge base — the second time a bug
class appears, the system remembers the first. Platforms dedupe centrally;
only a local ledger dedupes YOUR history against YOUR new hunt.
**Acceptance:** `test_dupe_warning_on_add`, `test_override_logged`, `test_dupes_sweep`.

---

### PHASE D — SCALE & POLISH (only after A-C prove out)

- **D1.** `hunt migrate` (P7): pre-v0.4 db rebuild; decide before first real hunt archives value. [S]
- **D2.** Taxonomy rename/merge tooling (P9): only once real hunts produce real taxonomies. [M]
- **D3.** Language policy pass (B7): engine-facing surfaces EN; operator notes may stay ID; one declared line. [S]
- **D4.** WAL + busy_timeout audit for parallel lanes (A8 residue) if 4-lane parallel CLI ever contends. [S, code-read first]
- **D5.** events.detail → structured columns where dashboards need it (E-upgrade note); only with C1 data in hand. [M]

---

## 3. OPEN-PROBLEMS REGISTER (the honest ledger)

| # | Problem | Class | Status / candidate fix |
|---|---|---|---|
| P1 | Verifier events self-attested (same operator, same terminal) | trust | Partially closed by claim gate + poc-run; cross-process attestation remains (B2 direction); R2-03 is its observation-oracle twin |
| P2 | PoC content authenticity (distinct hash ≠ truth) | truth | Mitigated: must RUN in-ledger (exit 0 pinned); real fix = A1 evidence trail + B1 receipts |
| P3 | Self-reported scoring inputs (ev/tvl/age) | truth | Ranges enforced; linked-evidence scoring parked (needs C1 calibration data) |
| P4 | Report edit-after-generate | integrity | CLOSED (fingerprint + UTF-8 law) |
| P5 | HUNT_DB swap mid-story | integrity | CLOSED (project lock, rebind events) |
| P6 | klass free text | integrity | CLOSED (taxonomy table + triggers) |
| P7 | Legacy DBs don't migrate | compat | hunt migrate in D1 — decide before first real hunt |
| P8 | evidence_ref no semantic binding | truth | Partially closed by B1 (tx case); oracle capture (B2) closes the observation case |
| P9 | Taxonomy cleanup tooling | ops | Deferred by choice |
| P10 | Oracle baseline self-attested (R2-03) | trust | NEW. B2 is the in-process narrowing; full closure needs capture-at-the-wire, documented as open |

**Doctrine:** problems move to CLOSED only with a regression pin. "Mitigated" is
a claim the next audit round is free to attack.

---

## 4. PROCESS DOCTRINE (how every change lands)

1. **Spec first** — one file, invariants numbered, test matrix enumerated, traps listed. No orals.
2. **Two builders, blind** — implementer + adversarial auditor in parallel; the auditor attacks the SPEC and (mid-flight) the landing, with real throwaway-db experiments, never speculation.
3. **Arbitration by reproduction** — every P1/P2 claim re-run by hand by the parent before it counts; auditor claims that fail reproduction are recorded as refuted (B-L9 precedent), not buried.
4. **Regression pins land with the fix** — a fix without a test is a rumor.
5. **Push partial, verify remote** — remote is truth; CI must be green on BOTH OS before anything is called done.
6. **Audit the patches too** — round 2 caught a bug my round-1 fix introduced (E22); the scheme audits itself, not just the code.
7. **Known trap:** tool output passes a redaction layer here — token-shaped strings in checklists LOOK alive/mutating in terminal views. Byte-level verify (python open()) is the only ground truth for secret-shape questions; escape example payloads in docs before push (CI secret-scan bites its own audit artifacts — twice now).

---

## 5. RISK REGISTER

| Risk | Likelihood | Impact | Counter |
|---|---|---|---|
| Feature creep dilutes enforcement spine | M | H | every milestone must widen the two gaps (§0) or it waits |
| Docs drift from machine again (R2-07 pattern) | M | M | CI structure gate pins bridge/docs lines; every docs claim must be a runnable command (B3-C9 contract) |
| Oracle trust hole shipped as closed | L | H | P10 stays OPEN until B2 lands; docs must say "narrowed", not "closed" |
| Test suite grows load-bearing-but-unread | M | M | golden fixtures + the 3-round audit cadence; prune dead tests at retro |
| Single-operator bus factor | H | M | ROADMAP + IMPL-NOTES + this process doctrine are the onboarding path |
| Scope creep into multi-user (v1.0 trap from improvements.md) | M | H | REFUSED until the bridge is wired and real hunts run — "an API on top of honor-system flags just scales the lie" — now it would scale enforcement, but M2/M4 first |

---

## 6. NON-GOALS (explicit)

- No web dashboard before C1 data justifies it.
- No multi-user API in this cycle (Park (v0.3) — revisit after A+B phases land and one real hunt completes end-to-end).
- No new soul adjectives. Enforcement is code.
- No dependencies. stdlib-only until the app layer EARNS one (M3 explorer map is data, not code).
- No chasing prompt-competitor feature lists; every item here maps to either "prompt cannot" or "submission-manager cannot".

---

## 7. THE ORDER (decision 2026-09-07: the proof path — calibrate the machine before polishing the deliverable)

```
NOW  → P1 hunt bench vs practice-target v2 (chained non-obvious flaws + trap + decoy)  ← calibrates everything
     → hunt next (one legal next command)      ← kills the 15+-command process tax
     → verify-eats-poc (no free-text evidence)  ← closes the last self-attestation hole BEFORE C2 automates it
     → C1 hunt stats                           ← nearly free, calibrates everything after
     → B3 hook pack                           ← distribution of the moat
THEN → C2 real-harness adapter decision (conductor) — gated on bench results
     → B1 explorer cross-check  ──┐
     → B2 oracle capture (P10)  ──┴─ same capture design, build once
     → C2 lesson search · C3 dedup
LATER→ A1 report export (Phase A reopens) · A3 signing · D1 migrate · D3 language pass · D4 WAL audit
      v1.0 conversation (multi-target, second engine) AFTER first real bounty cycle
```

**First-blood rule for every milestone:** it must pass the same bar First Blood
set — a full end-to-end run against the practice target (or a real target for
A1), artifacts on disk, claims through the CLI only, gate green both OS.

*The system believed it was safe. That belief was the first vulnerability —
ours is that it believes nothing without a row.*
