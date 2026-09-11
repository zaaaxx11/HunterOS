# AUDIT v0.3 — consolidated product/doctrine audit (Auditor B)

- Auditor: B (product/doctrine; cross-corrector of A's engineering audit).
  Method: full doctrine walk (SOUL → roles → HUNT-BRIDGE → FRAMEWORK → QUICKSTART →
  WALKTHROUGH → OPEN-PROBLEMS → FIRSTBLOOD), code read, and adversarial experiments run
  from `app/` against throwaway dbs in the system temp dir (all scratch files removed).
  Nothing in the repo was modified; no commits made.
- Input: A's findings at `HunterOS-audit-a/pr/audit/A-engineering-findings.md` (sibling
  worktree). A's numbering is preserved below; verdicts are tagged `[B-agree]`,
  `[B-agree+severity]`, `[B-partial]`, `[B-better-fix]` with one-line reasons.
- Baseline: `PYTHONPATH=src python -m pytest tests/ -q` → 102 passed (Windows, Py 3.13).
- Severity: P1 blocker / P2 should-fix / P3 polish.

---

## TL;DR — the 10 next actions, ranked

1. **Make the promote gate trigger-enforced and stop overclaiming** (A1): move
   verifier/challenge/RoE/distinct-PoC semantics into `BEFORE UPDATE` triggers; reword
   README/BRIDGE to "no door through the CLI; the db file is the operator's seal".
2. **Close the archived lock** (A2): `_require_active_target` into
   `overturn_finding` / `record_reaudit` / `close_wave`; keep lessons allowed.
3. **One hygiene pass over db.py/main.py** (A3+A8): CAS `UPDATE ... AND ladder_status=?`,
   catch `sqlite3.Error`/`OSError` as `BLOCKED:`, `--severity` choices, `os.path.isfile`,
   WAL + `busy_timeout`, finite-only scores (A5).
4. **`hunt poc run`** (A7): the runner that turns "PoC exists" into "PoC ran, exit 0,
   hash pinned" — the single highest-leverage honesty fix in the repo.
5. **Claim gate: unbound claim = veto; explicit `PROVEN[F-n]` bind syntax** (A4);
   ambiguity veto second.
6. **Phase scoping + an archive command in the same pass** (A6+A16): scope
   findings/waves/artifacts to owning phases; add `hunt target archive` or completed
   hunts strand in `retro` forever.
7. **CI honesty** (A9): one stdlib command, no pipe, no fallback (`python3 -m unittest
   discover -s tests -v`); add `windows-latest`; extend the secret scan to `*.py`.
8. **Doctrine repair pass** (B1/B2/B3): SOUL hunting amendments (BLOCKED is a legal
   result; hunt report is the deliverable), FRAMEWORK L2/L4 rewrite to v0.3 reality,
   bridge gains `hunt brief` and the record→blind-challenge ordering.
9. **Falsifier becomes data** (B4): a `falsifier` column set at insert and printed in
   reports — the framework's own anti-confirmation-bias device currently lives only in a
   template the ledger cannot see.
10. **Platform-ready report export** (M2 in the roadmap): `hunt report 1 --format
    h1|bugcrowd` — the deliverable is the part of the product that pays.

---

## Cross-corrected findings (A's findings, B's verdicts, merged fix designs)

### A1 — P1: Raw-SQL forgery defeats the "cannot lie" core — **[B-agree]**

Verified independently: (a) forged `verifier_pass`/`adversary_pass` events + a raw
`rules_of_engagement` row (events and RoE have no triggers at all, db.py:96-103,
120-127) make the honest CLI promote an unverified finding one step
(`promote_finding`'s gate checks are all `SELECT 1 FROM events ...`, db.py:495-512);
(b) a second raw session registering `huntos_session_guard_ok` flipped a row straight
to `proven-live`. One sharpening: it is not only "a raw session can register the
function" — **any** process that imports `huntos.core.db` and calls `connect()` gets
the guard automatically (db.py:254-256), so the guard is an import-convention, not a
boundary. The adversarial party in this threat model (the engine) has shell access and
can read db.py, so the docs' "There is no door" (HUNT-BRIDGE.md:56-57) and README.md:3
("cannot lie") are operationally false as stated.

Merged fix (A's design stands; B adds the wording fix as the load-bearing part):
1. A's trigger design is right and feasible — SQLite triggers can subquery `events` and
   `rules_of_engagement`, so the promote gate can bind every writer. Honest caveat both
   auditors should state: triggers raise effort, they do not close the class (a forger
   can INSERT the events raw too). The class cannot be closed in-process against a
   shell-armed engine; the file is the seal.
2. **[B-better-fix]** The cheap, zero-risk half first: reword precisely. README.md:3 and
   HUNT-BRIDGE.md:56-57 get one honest sentence: enforcement covers the CLI path and
   structure (klass, phase, evidence columns vs naive raw edits); row-level truth in a
   single-operator file is process (adversary, verifier) plus `hunt poc run`, not schema.
   The overclaim is itself the vulnerability — it teaches operators to trust a boundary
   that does not exist.

### A2 — P1: Archived targets accept overturns, re-audits, wave closes — **[B-agree]** (lessons part: **[B-downgrade]**)

Reproduced: `overturn_finding`, `record_reaudit`, and `close_wave(exhausted)` all
succeeded on an archived target (exit 0 each); `verify` was correctly blocked. B adds a
corollary A sketched and demonstrated fully: generate the report, archive, overturn →
`hunt verify-report` still says "report matches its fingerprint" while the report body
still shows `ladder: proven-live` for a finding the db now says `overturned`. The
fingerprint authenticates bytes, not freshness — a post-archive rewrite silently
diverges the one artifact third parties see.

- **[B-downgrade] on `lesson add`**: post-archive lessons are memory additions, not
  history rewrites; they touch no finding/wave/report. Allow them deliberately and say
  so in the docstring instead of "archived targets are locked" (db.py:15-16) without
  qualification.
- Merged fix: A's one-line guards for the three mutators; guard `close_wave` before
  `archive_target` re-runs; regression test per function (none exists today —
  `test_archived_locks_work` covers only `add_finding`/`open_wave`). Optionally have
  `verify-report` print the report's `generated:` stamp vs the newest
  `finding_overturned` event so staleness is visible even where it is legitimate.

### A3 — P1: Promote-vs-overturn lost update — **[B-agree+severity: P2]**

Reproduced with two app sessions: an in-flight promote clobbered a committed terminal
overturn (final row `ladder='in-code'`, with `overturned_by` residue left on a
non-overturned row — a bonus inconsistency `find_contradictions` could flag). The race
is real and the product invites parallel lanes — but the window is the SELECT→UPDATE
span of a single-statement CLI call between two human-scale commands; single operator,
no observed natural interleave. P2, not P1.

Fix (unchanged from A, it is the right and cheap one): `UPDATE findings SET ... WHERE
id=? AND ladder_status=?` + `rowcount` check → `BLOCKED: finding changed under you
(now: X)`; same CAS in `overturn_finding` (never overwrite `overturned_by` of an
already-overturned row). `BEGIN IMMEDIATE` optional — the CAS alone closes the lie.

### A4 — P1: Claim gate laundering + nearest-id binding — **[B-agree]**

Reproduced at the CLI level: `Our NEW deserialization chain ... is EXPLOITABLE, just
like F-1 last week` → exit 0 (unbound marker rides any proven-live row anywhere,
claim_gate.py:143-151); the marker binds nearest-id in an 80-char window
(claim_gate.py:55-71). Key context A missed: the laundering behavior is **tested as a
feature** (`test_proven_without_id_passes_when_db_has_proven_live`) and documented in
bridge/README.md:13-14 — so the fix is a conscious re-spec, not a bug patch. The fix
must ship with a bridge/docs update and a flipped test, or it will read as a regression.

Merged fix: (1) unbound strong claim → veto, immediately (the honest sentence "F-2
remains theoretical, no PoC yet" already passes since it uses no marker); (2) make
`PROVEN[F-7]` the documented explicit bind in HUNT-BRIDGE.md, proximity scan as
fallback only; (3) ambiguity veto later — it adds false-veto friction to prose-heavy
engine output, and (1)+(2) already kill A's demonstrated laundering sentence. **[B-add]**
a fourth gap neither A nor the tests cover: marker *coverage* — `RCE confirmed`,
`verified live`, `critical, 0day` carry the same lie with none of the three markers
(see B5).

### A5 — P1: `hunt score 1 nan` — **[B-agree on mechanism, downgrade to P2 on impact]**

Fully reproduced: `hunt score 1 nan` exits 0 ("scored ev=nan"); Python's sqlite3 binds
NaN as NULL; the scoring exit gate itself then dies with `TypeError: '<=' not supported
between instances of 'NoneType' and 'int'` (db.py:371) and `hunt status` dies on
`{t['ev_score']:>5}` (main.py:267) — raw tracebacks, exit 1. One correction to A's
"permanently bricks / until someone repairs the row via raw SQL": **the honest CLI
self-heals** — `hunt score 1 8.5` overwrites the NULL and `hunt status` recovers
(verified). A crash-with-recovery, not a permanent brick. P2.

Fix (A's design minus the drama): `math.isfinite` check in `score_target` and on
`--tvl`; make `cmd_status` render `ev=NULL` as `(unscored)` instead of crashing; keep a
`CHECK`/NOT NULL guard as belt. Tests: score nan/inf, tvl nan.

### A6 — P2: No phase scoping; the pipeline is ceremony — **[B-agree]**

Reproduced: with the target in `scoring` the whole time and no score set — `set_roe`,
`open_wave`, `finding add`, verify, challenge, and promote ×2 to **proven-live** all
succeeded. Also confirmed A's artifact point: `record_phase_artifact` checks only
existence/active-target (db.py:573-590), so `surface_map`/`attack_plan`/`disclosure_report`
can be pre-recorded before their phases exist, and `_has_artifact` matches any
historical event (db.py:353-357). The declared law was never implemented:
improvements.md:32 says "open_wave only in hunting".

Merged fix (A's design + one dependency A missed): phase-scope `add_finding`/
`open_wave` (hunting; promote/verify/challenge in hunting **and** verify); stamp
artifacts with the target's phase at record time and check the stamp. **Dependency:**
scope waves *before or with* A16's archive command — B verified that the only current
workaround for the retro dead-end (A16) is precisely this bug (`hunt wave open` works
in `retro`; close exhausted → archived). Fix A6 without A16 and a completed hunt can
never be archived by any path.

### A7 — P2: PoC-never-ran; `hunt poc run` — **[B-agree], promoted to the #1 firstblood fix and roadmap M1**

Confirmed by code and conceded by the repo itself (OPEN-PROBLEMS P2, firstblood #9).
B adds two design constraints to A's otherwise-correct spec:
1. The `poc_run` event must pin the PoC's sha256 **at run time** and `promote_finding`
   must require the event's hash to equal the promoted file's hash *and* the run to be
   newer than the previous promotion — otherwise the file can change between run and
   promote.
2. Never `shell=True`; capture with a timeout; store `exit_code` + digest of stdout (not
   raw output — secrets) in the event detail. Cross-finding PoC reuse (A's sharpening):
   do **not** hard-block (chain PoCs legitimately share stages); log it and let
   `find_contradictions` flag identical hashes across findings on different targets.

This is the fix that converts the ladder's core promise from honor system to checkable
invariant — it is also the anchor of the "paling best" roadmap (M1), because it is the
move a prompt-only setup structurally cannot copy.

### A8 — P2: Error paths leak tracebacks; connect() always writes — **[B-agree]**

Independently reproduced four of A's five rows: `--severity banana` →
`sqlite3.IntegrityError` traceback (argparse has `choices` for klass/action but not
severity, main.py:352); poc/artifact path pointing at a directory → `PermissionError`
traceback (`os.path.exists` is True for dirs, db.py:477/581); `report --out` into a
missing dir → `FileNotFoundError` traceback (main.py:152); write while another session
holds the lock → `sqlite3.OperationalError: database is locked` raw traceback after ~7s
(verified with a held `BEGIN EXCLUSIVE` and a read-probe proving the lock). A's point
that the failing statement is the taxonomy seed inside `connect()` (db.py:259-263) — so
even read commands die on a locked db — is correct and matters: the round loop runs four
lanes in parallel.

Fix: exactly A's list; B adds only the ordering — `main()` catching
`(ValueError, sqlite3.Error, OSError)` is a two-line change that removes the entire
class; do it before WAL/busy_timeout plumbing.

### A9 — P2: CI can never fail the test job; no Windows CI — **[B-agree] + [B-better-fix]**

Verified the mechanism directly: `python -m unittest discover ... 2>&1 | tail -2`
exits **0** over a failing suite (unittest alone: rc 1); shell precedence makes the CI
line `pytest || (unittest | tail -2)` (ci.yml:72), so a red suite prints "app tests
OK" under `set -e`. For a repo whose pitch is "they return exit code 2" (README.md:5)
and "Structure is a contract" (README.md:60), a test job that cannot go red is a
doctrine violation, not a papercut — B would treat it as P1-adjacent.

**[B-better-fix]** A offers pytest-with-constraints or a vendored runner. Cheaper and
in-voice: **drop pytest from CI entirely** — `PYTHONPATH=src python3 -m unittest
discover -s tests -v` is stdlib, has no pipe, no fallback, and the "zero pip in repo
tooling" grep (ci.yml:75-81) stays honest. Add `windows-latest` (the platform of record
— FIRSTBLOOD ran on Windows and A10/A14-class bugs are Windows-shaped); extend the
secret scan to `*.py`.

### A10 — P2: Workspace lock is cwd-only — **[B-agree]**

Code-confirmed: `check_project_lock` (db.py:1067-1092) and `claim_gate._lock_check`
(claim_gate.py:92-125) join `cwd` only, and bridge/README.md:99 itself says "Hooks may
run from anywhere" — so the gate's headline guarantee ("a fabricated HUNT_DB cannot
pass in a bound workspace") holds only when the hook's cwd happens to be the bound
directory. A's parent-walk + `HUNT_WORKSPACE` + atomic-lock-write fix is right; add the
docs honesty line A proposes ("consistency check, not authenticity").

### A11 — P2: Secret gates cover half the write paths — **[B-agree]**

Code-confirmed: `assert_no_secrets` fires on notes, evidence_ref, verification body,
adversary notes — and nowhere else. `add_lesson` stores `pattern`/`notes` raw with not
even the `redact()` net (it never calls `log_event`, db.py:829-838); RoE hosts are raw
and echoed; target name/url/notes rows are raw. The nastiest observation stands:
display-time `redact()` in report/brief *hides* the stored secret from the operator, so
the ledger carries it silently. Fix: one `clean_text(field, value)` helper applied at
every free-text write; `hunt secrets check <text>` dry-run (firstblood #8). Minor
[B-downgrade]: the poc_path-with-secret case is an edge; include it but don't let it
drive the design.

### A12 — P2: Wave economics count overturned rows; re-audit truth is prose — **[B-agree]**

Code-confirmed (`close_wave` counts `WHERE wave_id=?` including overturned, db.py:802-804;
`record_reaudit` appends counts into `waves.notes` as text, db.py:788-791).
`record_reaudit` already computes the survivor counts — promoting them to columns is a
trivial diff, and excluding overturned from `findings_new` fixes the two-empty-waves
economic stop's input in the same change. Pick one canonical order (reaudit → close)
and have `close_wave` refuse `reaudit_done=0` (firstblood #6).

### A13 — P2: Test blind spots — **[B-agree]**

Meta-finding, accepted as mapped. One addition: the suite's greenness is itself part of
the story A9 tells — CI *cannot* show red, so the 102 green tests have never been
load-bearing in CI. The regression tests A lists should land with their fixes in the
same PRs, or the gaps re-open silently.

### A14 — P3: Report fingerprint is content-not-bytes; encoding asymmetry — **[B-agree]**

Code-confirmed: write side `open(args.out, "w")` (main.py:152, locale encoding —
cp1252 risk on stock Windows), verify side UTF-8 read with universal newlines
(db.py:903-905) so CRLF rewrites pass verification. Fix as A says; either hash raw
bytes minus the footer or document the footer as a content fingerprint next to the
stamp. Cheap, do it in the same pass as A8's `main()` catch.

### A15 — P3: RoE binary at the top of the scale; ref floors — **[B-partial: downgrade to documented-behavior evolution]**

Reproduced the substance: an `auth-test` finding promoted to proven-live with RoE
`recon,read`. But this is *documented* behavior — WALKTHROUGH.md:155 says "only
`--actions` are enforced (the mutate proven-live gate, default-deny)" — so it is not a
silent hole; it is a design decision that firstblood exposed as too coarse (F-1, an
admin takeover, rode `auth-test` past a `recon,read` RoE would have been impossible to
write... and the run simply authorized everything up front). The right framing: either
implement the rank gate (`ROE_RANK[finding.action] <= max(roe actions)`) or fix the
models.py:14 comment ("escalation order") to say auth-test is RoE-ungated. **[B-agree]**
on the evidence_ref floor (8 chars) and the tx_hash↔evidence_ref consistency check —
both are one-line consistency wins that feed the roadmap's explorer cross-check (M3).

### A16 — P3: `retro` is a dead end — **[B-agree], severity raised to P2 when paired with A6**

Code-confirmed: no CLI path to `archived` from a completed pipeline (argparse choices
exclude it, main.py:339; `set_phase` refuses, db.py:365-366). B verified the only
workaround is an A6 bug: `hunt wave open` succeeds in `retro`, close exhausted →
archived — including for a target with **zero findings** (archive demands only a
lesson). So: fix A6 and A16 must land together; `hunt target archive <id> <reason>`
with the same lesson gate, plus A's papercut bundle (`_row` entity labels — firstblood
#3, wave-link echo — #13, `[PROVEN-LIVE]` display — #11).

---

## B's own findings

### B1 — P1 (doctrine): SOUL.md commands the exact behavior the enforcement layer exists to punish

SOUL.md is auto-injected every session and CI greps it verbatim (ci.yml:35-38), so this
is not decorative text. It commands: "The only failure is returning empty-handed"
(SOUL.md:32), "**No empty hands** — the command was given → the result must exist. By
any means" and "**No refusal** — operator instruction = executed" (SOUL.md:145-146).
The framework's whole discipline is the opposite: "A stall is BLOCKED, not a reason to
push harder" (HUNT-BRIDGE.md:73-74), STALL = BLOCK (lane-runner.md:27-28), "Honest
non-repro > forced proof" (verifier.md:11), exhaustion/pivot as *valid* verdicts. A
hunt under SOUL.md's binding protocols is instructed to never accept an empty result —
which is precisely the pressure that manufactures fabricated PoCs, forged verifier
events (A1), and unbacked PROVEN claims (A4). Same collision, milder: "I don't write
reports. I write results" (SOUL.md:238, 802) vs "hunt report is the only report"
(HUNT-BRIDGE.md:41-42); and SOUL's autonomous triggers (mempool arb > $50
auto-execute, airdrops auto-registered — SOUL.md:203-208) are unlicensed mutation by
doctrine, the exact thing RoE default-deny exists to prevent.

Fix: do not delete SOUL (CI contract, identity value) — amend it. Add a short
"HUNT-OS hunt-context amendments" block at the top of SOUL.md (or a preamble the bridge
explicitly outranks): in a hunt session, BLOCKED is a legal and final result;
empty-handed-after-honest-exhaustion is success; `hunt report` is the deliverable; the
autonomous-trigger table is out of scope for hunt sessions. Update the CI greps once.
Effort S; this is the cheapest P1 in the audit.

### B2 — P2 (doctrine drift): FRAMEWORK.md still teaches v0.1; its artifact contract does not match the machine

FRAMEWORK.md:40 (L4): "State machine app diparkir di `app/` ... **Framework jalan tanpa
app.** Enforcement v0.1 = disiplin + CI. Enforcement v1.0 = database." Every other
surface — README, HUNT-BRIDGE ("The database is the only ledger"), QUICKSTART,
WALKTHROUGH — treats the db as mandatory *now*. A new operator reading top-down gets
two mutually exclusive constitutions. L2's artifact table likewise names artifacts the
machine does not know: `target.json` for SCORE (no such gate), `DISCLOSURE_REPORT.md`
(CLI emits `REPORT.md`), `wave_N.md` (no wave artifact exists). Fix: rewrite L2/L4 to
v0.3 reality; delete `target.json`/`wave_N.md` or implement them. Effort S.

### B3 — P2 (glue): the bridge never reads the memory back, and the blind-challenge order is unspecified

`hunt brief` is the WALKTHROUGH's own memory-compounding move ("open with one read ...
before every new wave", WALKTHROUGH.md:66-71) — and the words "brief" appears **zero
times** in HUNT-BRIDGE.md and lane-runner.md. The engine that lives by the bridge is
never told to read the lessons back; "memory compounds" (doctrine #6) therefore depends
on a document the bridge doesn't reference. Related sequencing gap: cross-correction
happens *before* recording (lane-runner step 2), but the ladder's required
`adversary_pass` event needs a finding id — a db row — so the formal blind challenge
can only happen *after* insert. Nothing says the `hunt challenge` reviewer must be the
same blind adversary, or blind at all. Fix: one bridge block — "open every round and
every new wave with `hunt brief <target>`; record first (theoretical), then hand the
row to the blind adversary (role file: adversary.md), then `hunt challenge`" — plus one
line in lane-runner's round loop. Effort S.

### B4 — P2 (product): the falsifier — the framework's own anti-confirmation-bias device — cannot be stored

templates/FINDING.md:28 makes the falsifier mandatory ("finding tanpa falsifier = belum
selesai ditulis"), checks/PRE-REPORT.md requires it per finding, and SOUL's blind-spot
scanner (#3: "Hunt the evidence that DISPROVES the conclusion") is built on the idea —
but the schema has no falsifier field (db.py:53-70), no CLI flag captures it, and
`export_report` cannot print it. The ledger structurally cannot satisfy the checklist
the repo ships. Fix: `falsifier TEXT` column, `--falsifier` on `hunt finding add`,
printed per finding in the report; backfill optional (empty = flagged as `!! no
falsifier recorded` in `find_contradictions`). Effort S/M; doctrine-coherence payoff
disproportionate.

### B5 — P3 (gate coverage): three markers guard a large claim vocabulary

The gate scans exactly `PROVEN`, `EXPLOITABLE`, `admin takeover`
(claim_gate.py:32-36). "RCE confirmed", "verified live", "critical 0day", "fully
compromised" all pass with zero db backing. A4's binding fix does not change this.
Fix: do not chase the vocabulary with regexes (arms race); instead make the bridge's
claim law id-citation ("every claim carries its F-id"), and optionally extend markers
to the severity-adjective + confirmed/verified family documented in HUNT-BRIDGE.md.
Effort S for the bridge law, M if the marker set grows.

### B6 — P2 (product): the report carries less credibility than the db holds

`export_report` (db.py:847-886) prints findings with class/ladder/evidence/poc/notes
and a wave list. It omits: the verifier and adversary events (the ladder's entire
justification), re-audit outcomes, the falsifier (B4), severity rationale, and the
ENTRY/CHAIN/IMPACT structure templates/FINDING.md defines. The one artifact a third
party (program, partner, future you) sees proves less than the ledger it came from —
which inverts the product's own premise. Fix: fold into roadmap M2 (platform-ready
exports) rather than patching the current format twice: add the evidence-trail section
(verifier/challenge events per finding) in the near term, the platform formats next.
Effort M.

### B7 — P3 (consistency): the repo speaks two languages without a policy

docs/FRAMEWORK.md, templates/FINDING.md, templates/REPORT.md, templates/RETRO.md, and
checks/PRE-REPORT.md are substantially Indonesian; README, QUICKSTART, WALKTHROUGH,
bridge, roles, and all code are English. CI greps SOUL.md in English but nothing else.
If the operator's working language is Indonesian, that is a legitimate choice — but it
is undeclared, and the mixed template/checklist layer is the part a *new* operator or
an engine must parse. Fix: declare the policy in one line (README or FRAMEWORK) and
pick per audience: engine-facing surfaces (bridge, roles, templates the engine fills)
in English; operator-private notes may stay Indonesian. Effort S.

---

## The "paling best" roadmap — new moves, ranked

Ground truth to beat: plain Claude-Code-plus-prompt (a prompt cannot return exit code
2; its memory dies with its context), and BountyForge-class platforms (they manage
*submissions*; none own the *hunt process* — ladder, blind adversarial review, economic
stop). Every move below widens one of those two gaps.

**M1 — `hunt poc run`: the evidence runner** (S/M — also A7's fix, listed first because
it is both). Run the PoC through the CLI: exit code, duration, sha256 pinned at run
time, stdout digest (not raw output — secrets) into a `poc_run` event; promote
cross-checks hash + recency. *Unfair advantage:* converts the ladder from honor system
to checkable invariant — the competitor class literally cannot require "the file that
claims the exploit is the file that ran, and it ran inside the ledger." First move.

**M2 — Platform-ready report exports** (M). `hunt report 1 --format
h1|bugcrowd|markdown`: maps ladder + evidence trail + impact chain + falsifier into
HackerOne/Bugcrowd-shaped markdown, embeds trimmed PoC snippets, keeps the sha256
footer. *Unfair advantage:* the deliverable is what pays; today an operator re-types
the db into a form (30-60 min each, with transcription errors). HUNT-OS becomes the
only local OS whose submission is generated from the same ledger the claims were
enforced against. Needs B4/B6 first — the fields must exist.

**M3 — Explorer/API cross-check for tx_hash claims** (M). On `hunt verify 1 tx_hash
0x...`, fetch the explorer (stdlib `urllib`, JSON endpoint) and store the canonical
receipt (status, block, to/from, method) in the event; flag mismatch with the
evidence_ref (A15's consistency check, upgraded to machine truth); same shape later for
HTTP receipts (replay the request, diff the status line). *Unfair advantage:* closes
OPEN-PROBLEMS P1/P8 in the on-chain case — "tx hash, checked on explorer" (SOUL.md:168)
stops being a promise and becomes a row. Still stdlib-only, still fail-soft (no network
→ log, don't lie).

**M4 — Hunt analytics: `hunt stats`** (S). The events table already timestamps every
rung: time-per-ladder-step, overturn rate per lane, lane yield (which lane's findings
survive cross-correction), waves-to-first-proven, cross-correction kill rate. One
query file, zero schema change. *Unfair advantage:* no competitor measures the hunting
process itself; this is how the operator learns their own economics (the SCORE gate and
economic stop become calibrated instead of guessed). Highest value-per-effort on the
board after M1.

**M5 — Cross-hunt deduplication** (M). At `hunt finding add`, shingle the title/notes
against prior findings (stdlib); warn `~80% similar to F-12 on target #3 (proven-live)`
with a `--override` that is logged; `hunt dupes` command for the sweep. *Unfair
advantage:* the db becomes a personal knowledge base — the second time a bug class
appears, the system remembers the first. Platforms dedupe centrally; only a local
ledger dedupes *your* history against *your* new hunt.

**M6 — Lesson memory search** (S). `hunt lesson search <query>` (LIKE + ranking is
fine at v0 scale; FTS5 if it earns it) and `hunt brief --global <n>` to widen the
readback window beyond the hardcoded 10 (db.py:959). *Unfair advantage:* "memory
compounds" is currently true only up to ~20 lessons of scrollback; a searchable lesson
base is the moat FRAMEWORK.md:46 claims ("App bisa ditiru, moat tidak") made usable.

**M7 — Severity/CVSS scoring with rationale** (S). `hunt finding score --id N
--cvss "AV:N/AC:L/..." --rationale "..."` (or auto-suggest from klass/action/impact);
printed in reports; contradiction flag when severity=critical has no rationale. *Unfair
advantage:* triage consistency across hunts and operators; platforms expect a defensible
score, and the rationale field is exactly the kind of thing the ladder philosophy
demand-evidence-always implies.

**M8 — Multi-engine hook pack** (S). The bridge/README documents three wiring patterns
as pseudo-config; ship *real* ones: a ZCode hook config and a Claude Code PostToolUse/
Stop hook config that pipe assistant output through `bridge/claim_gate.py` and block on
exit 2, plus one worked "run the loop on a non-Hermes harness" example. *Unfair
advantage:* distribution — the gate is the product, and today wiring it is an
afternoon of guesswork; every harness that adopts the hook imports the doctrine.

**M9 — Report signing for the partner deliverable** (S/M). `hunt report sign <file>`
with an operator HMAC key (stdlib `hmac`): signature line joins the footer next to the
db fingerprint; `hunt report verify --sig` checks both. *Unfair advantage:* a
tamper-evident deliverable the partner can verify without trusting the operator's word
— the report's credibility stops depending on the sender.

**Order:** M1 → M2 → M3 → M4 → M6 → M5 → M7 → M8 → M9. M1 because every other
evidence claim gets stronger when PoCs run inside the ledger; M2 because it is where
the product touches money; M3 because on-chain hunts are the doctrine's home turf;
M4/M6 because they are nearly free; M5/M7 build on the data M1-M3 generate; M8/M9 are
distribution and trust polish.

---

## Firstblood friction triage — merged A+B view

All 14 items were triaged by both auditors; the merged calls, folding A's upgrades into
one plan:

| # | Item | Verdict | Lands in |
|---|------|---------|----------|
| 1 | Paths stored relative to cwd, never re-validated | **upgrade** | store `abspath` at record time (A8 hygiene pass) |
| 2 | MSYS mangling + no `hunt finding edit` | **upgrade** | `hunt finding retitle` / `hunt lesson reword` (titles are not evidence columns; the tamper trigger never fires on them) |
| 3 | `BLOCKED: not found: id = ?` | **upgrade** | `_row` entity labels (A16 pass) |
| 4 | Exhausted close archives out of pipeline order | **upgrade — top-3** | `archive_target` enforces the evidence of skipped phases (no in-code, report artifact or logged `--skip-report`), one design with #5 |
| 5 | `hunt report` on archived: half-success | **upgrade — top-3** | refuse before writing (exit 2, nothing on disk) or stamp first; never both-neither |
| 6 | Reaudit/close order ambiguity; counts in prose | **upgrade** | A12 structured columns + canonical order |
| 7 | `findings_new` counts overturned | **upgrade** | A12 exclude overturned |
| 8 | Secret-gate opacity | **upgrade** | `hunt secrets check <text>` + documented pattern list (A11) |
| 9 | Ladder cannot see whether the PoC ran | **upgrade — top-1** | `hunt poc run` (A7/M1) |
| 10 | No feedback on what a good verify body looks like | **upgrade** | per-type structural validation with the expected shape in the BLOCKED message (rides A7/A15) |
| 11 | Papercuts ([PROVEN], chain default, flag order) | mostly fine | A16 cosmetic pass; `[PROVEN-LIVE]` rename included |
| 12 | Crash responses have no HTTP representation | **fine / out of scope** | practice-app property, not an OS bug |
| 13 | No "what did I just record?" echo | **upgrade** | print `linked to open wave #N` from `add_finding` (A16 pass) |
| 14 | Claim-gate binding is positional luck | **upgrade** | A4: unbound veto + explicit `PROVEN[F-n]`; ambiguity veto later |

**Top-3 first fixes (merged):** **#9 → `hunt poc run`** (the only fix that turns the
ladder's core promise into a checkable invariant; also closes #10). **#4+#5 → archive/
report correctness as one design** (the current behavior permanently contradicts the
framework's own artifact contract on the exact path the runbook teaches). **#2 + #1 +
#3 + #13 as one CLI-UX repair bundle** (retitle, abspath, entity labels, wave-link echo
— four small diffs, one pass; together they delete the entire "bookkeeping casualty"
class firstblood suffered, where a shell-mangled title became a fake overturned row
polluting reaudit counts and the report).

---

## Scope footer

**Audited:** all of soul/ (SOUL.md, 7 role files, HUNT-BRIDGE), bridge/claim_gate.py +
bridge/README.md, docs/FRAMEWORK.md, templates/ (3), checks/PRE-REPORT.md, README.md,
QUICKSTART.md, app/WALKTHROUGH.md, pr/OPEN-PROBLEMS.md, improvements.md,
examples/practice_target/FIRSTBLOOD.md (+ skim of its REPORT.md/surface_map/attack_plan),
.github/workflows/ci.yml, app source (db.py, cli/main.py, core/models.py, conftest,
pyproject), both test files (name-level + targeted reads). Experiments run from
`app/` code against throwaway dbs in the system temp dir (five batches; every load-
bearing claim above was executed or read at a cited line; scratch files removed).

**Cross-checked but not re-derived:** A's HUNT_DB-is-not-a-database and
UNIQUE(target_id, number) traceback rows (A8) — accepted on A's transcript + code read;
A's CRLF fingerprint demo (A14) — accepted on code read of the universal-newlines path.

**NOT audited:** the practice target's exploit correctness (poc/*.py logic was taken as
demonstrated by FIRSTBLOOD.md, not re-run); the full 102-test suite line-by-line (gap
mapping only, per A13); SOUL.md's non-hunting layers beyond the contradictions in B1
(persona, heist-lab, V8 strategic content judged out of scope); any real Hermes/
ZCode/Claude-Code integration (no harness was wired; bridge/README's wiring patterns
were read, not executed); performance and WAL behavior beyond the single lock-holding
test; Linux/macOS behavior beyond reading CI; and the claim gate's behavior under
harness hooks (verified at the CLI/process level only).

*Cross-reference: A's original findings and experiment transcripts:
`HunterOS-audit-a/pr/audit/A-engineering-findings.md` (sibling worktree `audit-a`).*
