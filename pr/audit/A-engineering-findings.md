# Engineering audit A — HUNT-OS v0.3 (worktree `audit-a`)

- Auditor: A (engineering). Method: code read + adversarial experiments run from `app/`
  against throwaway dbs in the system temp dir (all scratch files removed afterwards).
  Nothing in the repo was modified; no commits made.
- Baseline: `PYTHONPATH=src python -m pytest tests/ -q` → **102 passed** (4.96s, Python 3.13.7, Windows).
- Severity: P1 blocker / P2 should-fix / P3 polish. Every claim below was executed or read
  at the cited location; experiment transcripts are quoted verbatim where load-bearing.

## TL;DR — top 5

1. **The tamper story is overclaimed and the enforcement surface is asymmetric (A1).**
   `HUNT-BRIDGE.md` says raw-sqlite bypass is "trigger-blocked … There is no door" and
   `db.py:248-256` claims a raw session's tamper is "blocked either way". Both are false:
   a 3-line script that registers `huntos_session_guard_ok` flips a finding straight to
   `proven-live` (demonstrated), and the `events` / `taxonomies` / `rules_of_engagement`
   tables have no triggers at all — forged `verifier_pass` + `adversary_pass` events make
   the honest CLI promote a garbage PoC (demonstrated end to end).
2. **The archived-target lock is Swiss cheese (A2).** `overturn`, `wave reaudit`,
   `wave close`, and `lesson add` all succeed on archived targets (demonstrated), directly
   contradicting db.py's own docstring ("archived targets are locked").
3. **Overturn terminality dies under concurrency (A3).** `promote_finding`'s UPDATE has no
   `AND ladder_status = ?` guard; interleaving it with a concurrent overturn converts an
   overturned finding to `proven-live` (demonstrated with two sessions).
4. **The claim gate launders unbound claims (A4).** Once *any* finding anywhere is
   proven-live, `EXPLOITABLE: <anything about anything>` passes (demonstrated); the
   nearest-id binding can also pin a claim to an innocent neighbor id (demonstrated).
5. **One `hunt score 1 nan` bricks `hunt status` for the whole db and bypasses the score
   gate (A5).** Python's sqlite3 binds NaN as NULL; `ev_score <= 0` is False for NaN; the
   first later `phase`/`status`/`target list` dies with a TypeError traceback (demonstrated).

---

## Findings

### A1 — P1: Raw-SQL forgery defeats the "cannot lie" core; the session guard is a naming convention, not a boundary

**Evidence.**
- `app/src/huntos/core/db.py:248-256`: "a raw sqlite3.connect() session has no such
  function, so its UPDATE on protected columns aborts … the tamper is blocked either way."
- Schema: `events` (db.py:120-127) has **no triggers and no FKs** on `target_id` /
  `finding_id`; `taxonomies` (112-118) and `rules_of_engagement` (96-103) are also
  unprotected. Triggers exist only for findings evidence columns, klass, and phase.
- `soul/bridge/HUNT-BRIDGE.md` ("Attempting to bypass via raw sqlite is trigger-blocked
  … There is no door") and `README.md` ("a state machine that cannot lie") make the
  overclaim operational: the adversarial party in this threat model is the engine, which
  has shell access and can read `db.py`.

**Demonstrated (one db, plain `sqlite3` — no app code involved):**
```
forged: 2 events, 1 klass, 1 roe row        # INSERT INTO events (verifier_pass/adversary_pass),
                                            # INSERT INTO taxonomies ('MASSIVE'), INSERT roe (mutate)
finding #2 promoted -> proven-live          # via the honest CLI afterwards
    F-2 [PROVEN]     info     MASSIVE finding
...
finding 1 flipped to proven-live via raw SQL with self-registered guard
    F-1 [PROVEN]     info     honest row      # create_function("huntos_session_guard_ok", 0, lambda: 1)
```
Note the irony: the *gate-level* checks (verifier event, adversary review, RoE, taxonomy)
were all satisfied by forged rows, so the CLI itself did the climbing — every one of the
promote gate's checks trusts `events`, and `events` is writable by anyone who can open the file.

**Fix design (staged, stdlib-only).**
1. Move the promote-gate semantics **into triggers** so they bind every writer, app or not:
   a `BEFORE UPDATE OF ladder_status` trigger that, when `NEW.ladder_status='proven-live'`,
   requires `EXISTS(SELECT 1 FROM events WHERE finding_id=NEW.id AND kind='verifier_pass')`,
   the same for `adversary_pass`, `NEW.poc_sha256 != OLD.poc_sha256`, non-empty
   `evidence_ref`, and (subquery) `mutate` ∈ the target's RoE actions. SQLite triggers can
   query other tables; the app's own promote path already satisfies all of these, so it
   keeps working — and the guard function becomes unnecessary for enforcement, which
   removes the "register the function" bypass class outright.
2. Add FKs (and a minimal insert trigger) on `events.finding_id/target_id` so audit rows
   cannot dangle; add a trigger refusing `verifier_pass`/`adversary_pass` for findings on
   archived targets.
3. Say precisely in README/BRIDGE what is enforced (structure/consistency) and what is
   not (row-level truth in a single-operator file). "There is no door" should read
   "there is no door through the CLI; the db file itself is the operator's seal."

### A2 — P1: Archived targets accept overturns, re-audits, wave closes, and lessons

**Evidence.** `_require_active_target` (db.py:300-304) is called in `add_finding`,
`open_wave`, `record_verification`, `record_adversary`, `record_phase_artifact`, `set_roe`
— but **not** in `overturn_finding` (593-598), `record_reaudit` (772-794), `close_wave`
(797-820), or `add_lesson` (829-838). Docstring (db.py:15-16): "archived targets are
locked: no findings, waves, promotions, or verifications".

**Demonstrated** (target archived via exhausted close; then, exit codes all 0):
```
=== overturn on archived:          finding #1 OVERTURNED by post-archive rewrite
=== reaudit on archived:           wave #1 re-audit recorded: ...
=== close_wave(exhausted) again:   wave #1 closed findings_new=1 verdict=exhausted
                                   (second 'archived' event logged)
=== lesson add on archived:        lesson #2 recorded (skill): post-archive lesson
=== verify on archived:            BLOCKED: target #1 is archived — the hunt is closed
```
The only one of the five that blocked is `verify`. A post-archive overturn rewrites the
ladder the report was generated from, and the report already on disk (fingerprint valid)
no longer matches the db it claims to summarize.

**Fix design.** One line each: call `_require_active_target` in the four functions.
For `close_wave`, the archived case must be refused *before* `archive_target` re-runs
(guard at the top of the function). Add a regression test per function — none exists
today (the suite only tests `add_finding`/`open_wave` on archived, see A13).

### A3 — P1: Promote-vs-overturn lost update: an overturned finding becomes proven-live

**Evidence.** `promote_finding` (db.py:464-532) reads the row (466), then writes with an
unconditional `UPDATE … WHERE id=?` (525-528) — no `AND ladder_status = ?`, no
`BEGIN IMMEDIATE`. The overturn check is TOCTOU: any interleaving between the SELECT and
the UPDATE loses it. Same-shape races exist for `close_wave`'s read-then-write of
`findings_new`/`ev_verdict` (801-815).

**Demonstrated** (two independent `db.connect` sessions on one db):
```
row (session 1): ladder_status='in-code'
db.overturn_finding(session 2, 1, "adversary-wins-the-race")   # commits 'overturned'
session 1 resumes the verbatim promote UPDATE ... WHERE id=1   # overwrites it
$ hunt status → F-1 [PROVEN]     info     race target
```
Single-process behavior is correct (`overturned findings cannot be promoted`); the hole
is scheduler-shaped, and the product explicitly encourages parallel lanes
(`soul/roles/lane-runner.md`, four lanes per round).

**Fix design.** Compare-and-swap: `UPDATE findings SET ladder_status=?, … WHERE id=? AND
ladder_status=?`; if `rowcount == 0`, re-read and fail with `BLOCKED: finding changed
under you (now: X)`. Wrap promote in `BEGIN IMMEDIATE` (or `conn.execute("BEGIN
IMMEDIATE")` via isolation_level=None) so the read-evaluate-write is atomic. Add the same
CAS to `overturn_finding` (don't overwrite `overturned_by` of an already-overturned row).

### A4 — P1: Claim gate: unbound claims ride on unrelated proof; nearest-id binding launders neighbors

**Evidence.** `bridge/claim_gate.py:143-151`: an unbound marker passes if the db has *any*
proven-live row anywhere. `nearest_finding` (55-71) binds the **nearest** id in an
80-char window; a sentence mentioning two ids resolves to whichever is closer.

**Demonstrated:**
```
$ printf 'EXPLOITABLE: the admin panel of target-9 in the other engagement is fully
  compromised\n' | python bridge/claim_gate.py      # db: one proven-live row on target 1
claim gate: no unbacked claims                      exit=0

$ printf 'F-1 is PROVEN, and by the same token F-99 is confirmed live too\n' | ...
claim gate: no unbacked claims                      exit=0   # binds F-1, sentence claims F-99
```
The gate's promise ("claims must be backed by proven-live rows") is kept only for the
narrow case the engine conveniently uses anyway (id adjacent to marker).

**Fix design.** (1) Drop the any-row fallback for unbound markers: an unbound strong
claim should be a veto by default (the honest phrasing "theoretical, no PoC yet" already
passes because it uses no marker). If a soft mode is wanted, gate it behind an env flag.
(2) Veto on ambiguous binding: if two ids in the window are within a few chars of
equidistant, refuse ("ambiguous finding reference — bind the claim explicitly").
(3) Prefer an explicit bind syntax (`PROVEN[F-7]`) documented in HUNT-BRIDGE.md, with the
proximity scan as fallback only.

### A5 — P1: `hunt score 1 nan` bypasses the score gate and permanently bricks `hunt status`

**Evidence.** `score_target` (db.py:328-336) checks `ev_score <= 0` — False for NaN;
argparse `type=float` accepts `nan`/`inf` (main.py:333-335). Python's sqlite3 binds NaN
as **NULL**. Then `set_phase` (db.py:371) raises `TypeError: '<=' not supported between
instances of 'NoneType' and 'int'`, and `cmd_status` (main.py:267) dies on
`{t['ev_score']:>5}` with `TypeError: unsupported format string passed to NoneType` —
`status` iterates all targets, so **every** target becomes unprintable until someone
repairs the row via raw SQL.

**Demonstrated:**
```
$ hunt score 2 nan      → target #2 scored ev=nan        (exit 0)
$ hunt phase 1 recon    → TypeError traceback, exit 1
$ hunt status           → TypeError traceback, exit 1    (whole db bricked)
```
Same family: `hunt target add X url --tvl nan` poisons `tvl_usd` → `target list` /
`status` crash on `${t['tvl_usd']:,.0f}` (main.py:80). `inf` passes the gate too and
prints as `ev=  inf`.

**Fix design.** In `score_target`: `if not math.isfinite(ev_score) or ev_score <= 0:
raise ValueError(...)`. Add a `CHECK (ev_score > -1e18)`-style guard or NOT NULL +
app-side isfinite for `tvl_usd`/`ev_score`. Add a db self-check to `hunt status`
(`SELECT id FROM targets WHERE ev_score IS NULL`) that reports instead of crashing.
Regression tests: score nan/inf/tvl nan.

### A6 — P2: No phase scoping: the whole hunt can be executed inside the `scoring` phase

**Evidence.** `add_finding` (db.py:419-461), `open_wave` (744-769), `promote_finding`
(464-532), `record_verification`, `record_adversary`, and `record_phase_artifact`
(573-590) never check `targets.phase` (only `_require_active_target`, i.e. not archived).
`improvements.md` line 32 declared the law "open_wave only in hunting" — never
implemented, and no test covers it. `_has_artifact` (353-357) matches *any* historical
event, so artifacts can be pre-recorded before their phase begins.

**Demonstrated (target in `scoring` the whole time):** opened wave 1, added findings,
recorded `surface_map` + `attack_plan` **and `disclosure_report`**, promoted one finding
to `in-code` and another to **`proven-live`** (`action=read`; the `mutate` one was
correctly RoE-blocked — see attacks-that-fail), then scored and walked
recon→classify→hunting→verify→report→retro with zero hunting-phase work. The verify
exit gate caught only the leftover in-code row (overturned it and sailed through).
The pipeline is currently ceremony on top of an unscoped ledger.

**Fix design.** Add `_require_phase(conn, tid, "hunting")` to `add_finding`/`open_wave`
(allow `promote`/`verify`/`challenge` in hunting *and* verify). Scope
`record_phase_artifact` to the phase that owns the artifact type (surface_map while in
recon, attack_plan in classify, disclosure_report in report) — the artifact is stamped
with the target's phase at record time, and `_has_artifact` checks that stamp. Decide
explicitly whether `promote` in scoring should be refused (I'd refuse; the walkthrough
narrative already treats verify as the ladder phase).

### A7 — P2: The PoC-never-ran hole, made concrete: promote validates existence, not execution (and one file can serve many findings)

**Evidence.** `promote_finding` checks `os.path.exists`, non-empty, and (step 2 only)
sha256 distinctness from *that finding's* previous step (db.py:476-494). Nothing ties the
file to any execution, to the verifier event, or across findings: `poc1` of finding B can
be `poc2` of finding A; a PoC that has never exited 0 promotes fine. This is documented
Class B (`pr/OPEN-PROBLEMS.md` P2) and firstblood friction #9 — but it remains the single
biggest honesty gap, and the audit adds two sharpenings: (a) cross-finding PoC reuse is
untracked; (b) the content could be `README.md` — no extension, structure, or parse
check at all.

**Fix design (`hunt poc run` — turns "exists" into "ran, exit 0, hash pinned").**
`hunt poc run --finding N --step in-code|live -- <cmd...>`: run via `subprocess.run`,
record a `poc_run` event with `{exit_code, poc_sha256, stdout_digest, duration}`; the
PoC file's sha256 is pinned at run time. `promote_finding` then requires a `poc_run`
event whose `poc_sha256` matches the promoted file, `exit_code=0`, and which is newer
than the previous promotion. Additionally require the `hunt verify` body to reference the
same `poc_sha256` (or the poc_run event id) — this closes the hand-trimming gap too
(transcript ↔ binary ↔ ledger cross-linked). Still self-attested, but now internally
consistent: a hand-trimmed transcript or a never-run PoC leaves a detectable
inconsistency instead of none.

### A8 — P2: Error paths leak tracebacks and exit 1 — the "everything returns exit code 2" contract breaks exactly under bad input

**Evidence.** `main` (main.py:472-478) catches only `ValueError`. Demonstrated:

| Input | Result |
|---|---|
| `--severity banana` | `sqlite3.IntegrityError: CHECK constraint failed: severity IN (...)` traceback, exit 1 (db.py:447-451; `--severity` has no `choices`, main.py:352) |
| `--poc-path <a directory>` | `PermissionError: [Errno 13] …` traceback, exit 1 (db.py:479 `open()`; `os.path.exists` is True for dirs) |
| `HUNT_DB=<a text file>` | `sqlite3.DatabaseError: file is not a database` traceback, exit 1 |
| write while another session holds the write lock | `sqlite3.OperationalError: database is locked` after Python's default 5s — and the failing statement is the **taxonomy seed INSERT inside `connect()`** (db.py:259-263), so even `status`/`brief` can die on a locked db |
| two sessions `wave open` simultaneously | second gets `IntegrityError: UNIQUE(target_id, number)` traceback |

Also: `connect()` **always writes** (seeds + meta, db.py:254-274), so read-only commands
are not read-only at the db level (and would fail on a read-only db file). No WAL, no
explicit `busy_timeout` (db.py:244) — with four lanes running in parallel per the round
loop, intermittent 5s-hang-then-traceback is a real operational mode, not a corner.

**Fix design.** (1) `main()` catches `(ValueError, sqlite3.Error, OSError)` → `BLOCKED: …`
/ exit 2. (2) `--severity` gets argparse `choices`. (3) poc/artifact paths validated with
`os.path.isfile`. (4) `connect(timeout=N)` + `PRAGMA journal_mode=WAL` +
`PRAGMA busy_timeout=N`; skip seed/meta writes when `PRAGMA user_version` shows the db is
initialized, making read commands genuinely read-only. (5) Tests: one per row above
(none exist; see A13).

### A9 — P2: CI can never fail the test job, and Windows (the platform of record) is untested in CI

**Evidence.** `.github/workflows/ci.yml:68-73`:
```yaml
PYTHONPATH=src python3 -m pytest tests/ -q 2>/dev/null || PYTHONPATH=src python3 -m unittest discover -s tests 2>&1 | tail -2
```
Shell precedence makes this `pytest || (unittest | tail -2)`; the pipeline's exit status
is `tail`'s (0), so a **red suite still prints "app tests OK"** under `set -e`.
Demonstrated: `bash -c 'set -e; false || echo "1 failed, 101 passed" | tail -2; …' → exit 0`.
Additionally: all jobs run `ubuntu-latest`, but the first real hunt (FIRSTBLOOD.md) ran on
Windows and the platform-specific bugs below (A10, A5-adjacent encoding) are
Windows-shaped; the secret scan (ci.yml:60-66) covers only `*.md`/`*.yml`.

**Fix design.** Make the test step a single command with no fallback and no redirect:
`PYTHONPATH=src python3 -m pytest tests/ -q` (declare pytest via a pinned constraints
file, or vendor a tiny runner; the "no pip in repo tooling" grep at ci.yml:75-81 greps
only yml/toml so a GH Action-level install is compatible). Add a `windows-latest` job.
Extend the secret scan to `*.py`.

### A10 — P2: The workspace lock is cwd-only — no parent search, trivially escaped by running elsewhere (CLI and gate both)

**Evidence.** `check_project_lock` (db.py:1067-1092) reads `os.path.join(cwd,
LOCK_FILENAME)`; `claim_gate._lock_check` (claim_gate.py:92-125) does the same and is
documented as cwd-based ("Hooks may run from anywhere"). No upward search, no env
override. Consequences (fabricated-db-with-planted-proven-live demonstrated passing):
```
cd $TMP/gatecwd            # unbound dir, no .huntos-project anywhere above
HUNT_DB=$TMP/fake.db python bridge/claim_gate.py <<< "PROVEN F-1: the drain executes on the live fork"
claim gate: no unbacked claims          exit=0
```
The CLI is symmetric: `hunt` run from any unbound directory binds to nothing. And the
lock verifies db↔directory *consistency*, not directory authenticity: an engine that can
write files can `hunt project bind` inside its own fresh directory (the rebind event goes
into the db being bound — no cross-check) and then pass the gate there. `bind_project`
(db.py:1052-1064) also writes the lock non-atomically — a crash mid-write leaves a
malformed lock that blocks every write command until manually deleted.

**Fix design.** Walk parents (git-style) to find `.huntos-project`; accept
`HUNT_WORKSPACE` as an explicit root for harnesses that run hooks elsewhere; write the
lock atomically (temp file + `os.replace`); for the gate, treat "lock file found but
belonging to an unknown directory" as exactly what it is — a consistency check, and say
so in bridge/README.md instead of "a fabricated HUNT_DB cannot pass in a bound workspace".

### A11 — P2: Secret-hygiene gates cover half the write paths — `poc_path`, lessons, RoE hosts, target name/notes are ungated

**Evidence.** `assert_no_secrets` is called on `notes` (add_finding), `evidence_ref`
(promote), verification body, adversary notes — and **nowhere else**. `poc_path`
(db.py:476-494), `add_lesson` (829-838 — no gate and *not even the redact safety net*,
since it never calls `log_event`), `set_roe` hosts/notes (702-733), `add_target`
name/url/notes (309-317), `overturn_finding`'s `overturned_by` (593-598) all store raw.

**Demonstrated:**
```
promote --poc-path "$TMP/password=SuperSecretValue123/poc.py"  → promoted; DB stores path raw
lesson add A12 "admin password=CorrectHorse12 found in config" → recorded; DB stores raw
target roe 1 --hosts "password=CorrectHorse12" --actions read  → accepted, echoed to stdout raw
```
Display-time `redact()` in report/brief hides most of this from output, which makes it
worse: the operator sees `[REDACTED]` and never learns the ledger itself is carrying the
secret. The README claim "raw secrets are refused at the gates" is ~half true.

**Fix design.** Route every free-text write through one helper:
`clean_text(field, value, refuse=True)` (refuse at the gate, redact what must be stored).
Apply to lesson pattern/notes, RoE hosts/notes, overturned_by, target name/url/notes,
poc_path (refuse; a path component with `password=` is never legit). Add
`hunt secrets check <text>` (friction #8) so operators can pre-flight.

### A12 — P2: Wave economics count overturned rows as "new findings"; re-audit truth lives in free text

**Evidence.** `close_wave` computes `findings_new = COUNT(*) … WHERE wave_id=?`
(db.py:802-804) — overturned rows included; the two-empty-waves economic stop
(805-814) consumes the same inflated number. `record_reaudit` appends
`" reaudit: … | confirmed=N overturned=M"` into `waves.notes` (788-791) as prose — no
columns, nothing downstream can verify it (firstblood #6/#7 felt exactly this).

**Fix design.** `findings_new` = `COUNT(*) … AND ladder_status != 'overturned'`; add
`confirmed INTEGER`, `overturned INTEGER` columns written by `record_reaudit` (computed,
not claimed); keep the prose in notes as color. The economic stop then uses survivor
counts.

### A13 — P2: Test blind spots (the suite proves the happy path, not the boundaries)

**Evidence.** 102 tests, all green. Gaps, each mapped to a finding above:
- **No concurrency tests at all** (no two-session interleaving, no locked-db case) — A3, A8.
- **Archived lock tested only for `add_finding`/`open_wave`** (`test_archived_locks_work`,
  test_enforcement.py:504-511) — overturn/reaudit/close/lesson untested, which is why A2 exists.
- **No phase-scoping tests** — nothing asserts that `open_wave`/`promote` outside
  hunting/verify is refused (A6).
- **No boundary-value tests on numeric inputs** — NaN/inf score, negative tvl (A5).
- **No raw-SQL forgery tests for `events`/`taxonomies`/`rules_of_engagement`** — the suite
  checks tamper only on findings columns, targets.phase, and klass (A1).
- **Gate tests stop at the documented behavior** — no test for unbound-claim cross-target
  laundering, no ambiguity test for `nearest_finding` (A4).
- **No format/encoding tests** — non-ASCII titles through `report --out`/`verify-report`,
  CRLF-only "tampering" (A10-adjacent, A14).
- **No test that a read-only command stays read-only** (A8: `connect()` always writes).
- **No Windows CI** (A9) — the suite passes on Windows today, but nothing guards it.

### A14 — P3: Report fingerprint is newline-normalizing and encoding-asymmetric — it verifies content, not bytes

**Evidence.** `verify_report_file` opens with `encoding="utf-8"` (db.py:903-905) —
universal newlines translate CRLF→LF before hashing; `cmd_report` writes with
`open(args.out, "w")` (main.py:152) — locale/preferred encoding (UTF-8 on this machine;
**cp1252 on stock Windows installs**, where a non-ASCII title would encode at write and
fail decode at verify with a misleading `BLOCKED: 'charmap'/'utf-8' codec…` line; a
UnicodeEncodeError mid-write also leaves a truncated file). Demonstrated: rewriting every
newline LF→CRLF still yields `report matches its fingerprint` — so the footer digest does
not match the file's actual bytes (`sha256sum` fails), and byte-level changes confined to
line endings pass verification.

**Fix design.** Write with `encoding="utf-8", newline="\n"`; read with
`open(..., encoding="utf-8", newline="")` and hash raw bytes minus the footer (or hash
the normalized text but document that the fingerprint is a *content* fingerprint, and say
so next to the footer). Catch `UnicodeDecodeError` explicitly with a "file is not valid
UTF-8" message.

### A15 — P3: RoE enforcement is binary at the top of the scale; evidence refs have no floor

**Evidence.** The RoE gate checks only `action == "mutate"` (db.py:516-524): an
`auth-test` finding promotes to proven-live even when the target's RoE is `recon,read`,
although `ROE_ACTIONS` (models.py:15) declares the escalation order
recon<read<auth-test<mutate. `evidence_ref` accepts `" "` (whitespace-only truthy) and
any ≤1-char string; the same ref can be reused across different findings; refs are never
cross-checked with `tx_hash`-typed verifier events even when both exist (the tx-hash
regex is enforced only inside `record_verification`, db.py:542-543). Also `add_klass`
allows near-duplicates (`unknown` vs `Unknown` — case-sensitive table, db.py:607-633).

**Fix design.** Rank check: allowed iff `SEVERITY_RANK-style ROE_RANK[finding.action] <=
max(ROE_RANK[a] for a in roe.actions)`. Floor evidence_ref at, say, 8 chars; when the
finding has a `tx_hash` verifier event, require the ref to contain that hash (cheap
consistency, OPEN-PROBLEMS P2 candidate). Reject case-insensitive klass duplicates at
`add_klass`.

### A16 — P3: `retro` is a dead end — no CLI command can archive a target that completed the pipeline

**Evidence.** `set_phase` refuses `'archived'` (db.py:365-366, and argparse choices
exclude it, main.py:339); `archive_target` is reachable **only** from
`close_wave(verdict="exhausted")` (db.py:816-817). A target that walks
score→…→report→retro honestly (as WALKTHROUGH.md teaches) can never be archived; it
sits in `retro` forever, and the "archiving requires a retro lesson" law (docstring 16)
is only ever exercised through the economic-stop side door. Related papercuts from the
same maintainership pass: `_row`'s error is the opaque `BLOCKED: not found: id = ?`
(db.py:293-297 — firstblood #3), `finding add` doesn't echo the auto-linked wave
(firstblood #13), and `status` prints `[PROVEN]` for `proven-live` (firstblood #11).

**Fix design.** `hunt target archive <id> <reason>` (thin wrapper over `archive_target`,
same lesson gate); give `_row` an entity label (`_row(..., what=f"target {tid}")`); echo
`linked to open wave #N` from `finding add`; print `[PROVEN-LIVE]`.

---

## Attacks that fail (verified — the enforcement holds)

These were tried and are correctly blocked; listed so the cross-correction pass doesn't
re-report them, and because each fix design above must not break them.

1. **Mutate proven-live outside RoE.** The scoring-phase speedrun's `mutate` finding was
   refused: `BLOCKED: mutate finding cannot reach proven-live outside the rules of
   engagement` (db.py:516-524; also suite-tested). Default-deny works.
2. **Direct raw UPDATE of findings evidence columns without registering the guard.**
   Aborts (`no such function: huntos_session_guard_ok`) — true for the naive case only
   (A1 shows the 3-line escape); phase backward via raw SQL is genuinely trigger-blocked
   (targets_phase_guard, suite-tested).
3. **Raw-SQL klass cheats on findings.** `INSERT/UPDATE … klass='MASSIVE'` on the
   findings table aborts via the klass triggers — but note the asymmetry: injecting the
   class into `taxonomies` first *is* possible (A1).
4. **Empty PoC / same-PoC-hash / reused evidence_ref between ladder steps** — all
   blocked (db.py:481-494; suite-tested). Verify/challenge on overturned findings —
   blocked (547, 564). Promote of overturned (single-process) — blocked (469).
5. **Report tampering.** Body edits and content appended after the footer are refused
   (`test_verify_report_tampered`, `test_verify_report_content_after_footer_blocked`);
   stripping the footer is refused as "not generated by hunt report". A11/A14 show what
   still slips *into* reports, not around the fingerprint.
6. **Fabricated db in a bound workspace.** Gate lock check fires before claims are
   evaluated and refuses foreign dbs without a `meta` table
   (`test_gate_lock_mismatch_blocks`, `test_gate_lock_foreign_db_blocks`). A10 shows the
   escape is spatial (run unbound), not cryptographic.
7. **Missing/unreadable db at the gate.** Fail-closed exit 2, db never created
   (`test_missing_db_fail_closed`).
8. **Two consecutive empty `continue` waves** — economic stop enforced
   (`test_two_empty_waves_force_economic_stop`).
9. **`hunt verify` on an archived target** — blocked (demonstrated in A2's transcript).
10. **Lowercase "proven" / "unproven" / "nonexploitable" prose** — no false vetoes
    (case-sensitive word-boundary markers, suite-tested).

---

## First-blood friction triage (14 items)

Legend: **upgrade** = the log described symptoms; here is the root cause + fix design.
**fine** = current behavior is correct or the item is out of OS scope. Bold = top-3 pick.

1. **Paths stored relative to cwd** — **upgrade (fold into A6/A8).** Root cause:
   `promote_finding`/`record_phase_artifact` store the operator's string verbatim
   (db.py:527, 589) and nothing re-validates. Fix: store `os.path.abspath(expanduser(p))`
   (plus the raw input in the event detail), so evidence survives any later cwd. Cheap,
   removes the entire `../` fragility class firstblood hit on every command.
2. **MSYS mangling + no `hunt finding edit`** — **upgrade (top-3).** Root cause is the
   shell, but the *amplifier* is that titles/lesson text are immutable, forcing an
   overturn + re-add that pollutes the ledger with a fake casualty (F-3 showed up in
   reaudit counts and the report next to real kills). Titles are **not** evidence columns
   — the tamper trigger never fires on them — so a logged, title-only
   `hunt finding retitle --id N --title …` (and `hunt lesson reword`) violates no law and
   deletes the casualty class. Also print a one-line hint when a title starts with
   `/` and looks MSYS-converted? No — keep scope: retitle is the fix.
3. **`BLOCKED: not found: id = ?`** — **upgrade (A16).** Root cause: `_row` splices the
   SQL WHERE clause into the message. Give it an entity label; one-line fix, kills the
   "wave id vs target id" detour firstblood walked into.
4. **Exhausted close archives out of pipeline order** — **upgrade (top-3, with #5).**
   Root cause: `archive_target` enforces only the retro lesson; the verify/report exit
   gates apply to `set_phase` only, and the trigger whitelists archived from any phase
   (db.py:153). Fix design: keep the economic-stop single command, but make
   `archive_target` enforce the *evidence* of the phases it skips: no in-code findings,
   disclosure_report artifact present (or an explicit `--skip-report` that is logged as
   an event and surfaced by `find_contradictions`), plus the lesson. The phase ladder
   stays forward-only; the archive path just stops pretending the skipped gates never
   existed.
5. **`hunt report` on archived: half-success** — **upgrade (top-3, same root as #4).**
   `cmd_report` writes the file first, then the artifact stamp fails as an advisory
   stderr line, exit 0 (main.py:148-163) — the report exists, verifies, and its own
   artifact gate is permanently unsatisfiable. Fix: check `phase == 'archived'` (or the
   A2 guard result) **before** opening the output file; refuse cleanly with exit 2 and
   write nothing. Half-success is the worst of both, exactly as the log says.
6. **Reaudit/close order ambiguity; counts in free text** — **upgrade (A12).** Structured
   `confirmed`/`overturned` columns computed by `record_reaudit`; pick one canonical
   order (reaudit, then close) and have `close_wave` refuse `reaudit_done=0` instead of
   silently accepting both orders.
7. **`findings_new` counts overturned** — **upgrade (A12).** Exclude overturned from the
   count; the economic stop inherits the honest number.
8. **Secret-gate opacity** — **upgrade (A11).** Add `hunt secrets check <text>` (prints
   which pattern would fire / that it's clean) and document the pattern list; unify the
   refuse-vs-redact coverage so the asymmetry the log had to reverse-engineer disappears.
9. **The ladder cannot see whether the PoC ran** — **upgrade (top-3, A7).** This is the
   documented Class B limit, but the log's own run proved the temptation is real (the
   broken poc2 that was fixed *before* promoting, by luck not by enforcement). Fix:
   `hunt poc run` design in A7 — existence → execution → hash pinned → cross-linked to
   the verify event. Highest-leverage honesty fix in the list.
10. **No feedback on what a good verify body looks like** — **upgrade (A7/A15).**
    Per-type structural validation for `http_transcript` (request line + status line
    regex) and `fork_receipt` (min length + structure), with the expected shape inside
    the BLOCKED message; merge with #8's dry-run.
11. **Papercuts ([PROVEN], chain default, promote flag order)** — **mostly fine.**
    `[PROVEN]` vs `proven-live` is a deliberate display shorthand; rename for consistency
    in the A16 pass if desired. `--chain evm` default is documented free text; the
    add/promote positional asymmetry is a consequence of correct per-action subparsers
    (PR-5a) — not worth re-breaking. No action beyond A16 cosmetics.
12. **Crash responses have no HTTP representation** — **fine / out of scope.** This is a
    property of the practice app (stdlib http.server closes the connection), not of
    HUNT-OS; on real targets the operator captures what the wire gives. The OS-side
    lesson (record the app-log corroboration as an artifact) already worked in the run.
13. **No "what did I just record?" echo** — **upgrade (A16).** `add_finding` already
    finds the open wave (db.py:453-459); return it and print
    `linked to open wave #N` / `(no open wave — unlinked)`. One line, saves a dozen
    `status` calls per hunt.
14. **Claim-gate binding is positional luck** — **upgrade (A4).** Two concrete upgrades:
    veto on ambiguous nearest-id ties, and require the id on the same line as the marker
    (drop the 80-char cross-line reach); document `PROVEN[F-7]` as the explicit bind. The
    demonstrated laundering sentence ("F-1 is PROVEN, and by the same token F-99 …")
    fails under either change.

**The 3 to fix first:** **#9 (poc run)** — it is the only fix that turns the ladder's core
promise ("each step demands fresh, distinct work") from an honor system into a checkable
invariant, and it also closes #10; **#2 (retitle)** — smallest change that stops
manufacturing fake overturned rows that distort reaudit counts, reports, and the economic
stop; **#4+#5 (archive/report correctness, one design)** — the current behavior
permanently contradicts the framework's own artifact contract on the exact path the
runbook tells operators to walk.

---

## Recommended order

1. **A1** (triggers-as-enforcement; kill the guard-function trust) + **A2** (archived
   guards) — the honesty core; both are small diffs with big claim-correction value.
2. **A3** (CAS update) and **A8** (error-path hygiene, WAL/busy_timeout, isfile checks) —
   same files, one pass; add the A13 regression tests as you go.
3. **A7** (`hunt poc run`) — the top firstblood upgrade; design first, then implement.
4. **A4 + A10** (claim gate: unbound-claim veto, ambiguous-binding veto, lock parent
   walk / `HUNT_WORKSPACE`).
5. **A5, A6, A9, A11, A12** — input validation, phase scoping, CI, hygiene coverage,
   wave economics.
6. **A14–A16** — polish pass (report bytes/encoding, RoE ranks, archive command, echoes).
