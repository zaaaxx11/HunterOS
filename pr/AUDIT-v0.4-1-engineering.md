# AUDIT v0.4 — Engineering audit #1 (bug laten / SQLite & CLI efficiency / test gaps / upgrade path)

- Auditor: Engineering (Auditor 1, post-v0.4 re-audit). Scope: **landed code only** —
  `app/src/huntos/core/db.py` (2070 L), `app/src/huntos/cli/main.py` (836 L),
  `app/src/huntos/core/models.py`, `bridge/claim_gate.py` (290 L), `app/tests/`
  (3 files), `.github/workflows/ci.yml`, `app/conftest.py`.
- Round-1 boundaries respected: B-L6 (oracle shopping), B-L7 (promote override),
  B-L10 (secrets in retrigger), B-L11 (state-blind flag) are **Auditor 2's** — not re-audited here.
- **Mid-audit note (transparency)**: the mirror updated under this audit (13:21–13:26):
  round-2 items R2-02 (`lead promote --action`) and R2-05 (manual overwrite of
  oracle-`refuted` halves) landed mid-flight. Every repro below was **re-run and
  re-verified against the final head**; the R2-02 change itself introduced a new P1
  (E22) — found, pinned, and reported here. E7 (oracle-refuted laundering) is now
  **verified fixed** by R2-05 (see the fixed-during-audit section).
- Baseline: `cd /root/Hunter && python3 -m pytest app/tests/ -q` → **165 passed in 7.8s**
  (162 at audit start, +3 from the mid-audit landing; working tree = mirror + this report only).
- Method: full code read of all five units + adversarial experiments from `/tmp/audit-v04a/`
  against throwaway dbs. Findings tagged `[repro]` (real output above) or `[code-read]`
  (with the reason it was not run). No repo files modified except this report; no commits;
  no deps installed; scratch in `/tmp/audit-v04a/`.
- Severity: P1 blocker / P2 should-fix / P3 polish. Eff = efficiency finding.

---

## TL;DR — ranked next actions

1. **E22 (P1, new)**: `hunt lead promote` is a **silent no-op** — the new required
   `--action` (R2-02) reuses argparse `dest="action"`, clobbers the subcommand name,
   and `cmd_lead`'s `elif args.action == "promote"` never fires. rc 0, no output,
   lead stays open, no finding. The flagship lifecycle command is dead.
2. **E1 (P1)**: parked leads have **no exit** — every writer refuses `parked`; the
   docstring diagram promises `parked -> open`. Deadlocked state machine.
3. **E3 (P1)**: corrupt/garbage HUNT_DB **file** → raw `ValueError` traceback on every
   command. A8's contract comment (main.py:793) is violated by its own catch tuple.
4. **E2 (P1)**: `hunt target add --tvl nan` permanently poisons the row; every later
   `hunt target list` / `hunt report` crashes with a TypeError. A5's fix covered `score`
   only — `--tvl` re-opens the same class.
5. **E12 (P2)**: `promote_lead` spans **two commits** (trace-verified: 2× COMMIT/call).
   A crash between them strands an orphan finding with `lead_id IS NULL` and the lead
   stays promotable → duplicate findings on re-run.

Fastest efficiency wins (all ≤ 10 lines): **E14** (5-line `CREATE INDEX IF NOT EXISTS`
batch), **E5** (one-pass id positions in the claim gate — 105 s → ms), **E6** (kind
filter + index for the provenance scan), **E20** (connect fast-path: skip SCHEMA when
`meta.db_id` exists), **E18** (delete dead `_t()`/`nearest_finding`).

---

## P1 — blockers

### E22 — P1: `hunt lead promote` is a silent no-op — `--action` clobbers the argparse subcommand dest `[repro]` *(new; introduced by R2-02 mid-audit)*

R2-02 made `--action` a **required** argument on the lead-promote subparser with
`dest` unset (main.py:770): `plp2.add_argument("--action", required=True, choices=["read","mutate","auth-test"])`.
Argparse writes option values into the shared namespace under `dest="action"` — the
same attribute the subcommand dispatch reads (`cmd`, then `action` per group,
main.py:534/581/642/706). The repo **documented this exact trap** for the finding
parser: *"dest is `finding_action` because `action` is taken by the subcommand choice"*
(main.py:590-594) — the R2-02 change violated its own convention.

Repro (final head, real output; lead L-1 with both halves proven):

```
$ hunt lead promote --lead 1 --klass Access --action read --severity high
rc=0 stdout='' lead_state=open findings_bound=0     → SILENT NO-OP
```

`cmd_lead` (main.py:373-442) dispatches on `args.action`; the namespace holds
`"read"`, not `"promote"`, so every `elif` falls through and the handler returns 0.
Db-level `promote_lead(conn, lid, klass, severity, action)` works fine (verified) —
only the CLI door is broken, and it fails **quietly**: the operator believes the lead
promoted, the brief keeps listing it as open, no finding exists. Omitting `--action`
fails loudly (parse error, exit 2) — so the only parseable invocation shape is the
broken one. A mutation-flavored lead (R2-02's actual concern: RoE default-deny for
mutate) can never reach promote through the CLI at all.

**Fix** (one line, mirroring main.py:593): `plp2.add_argument("--action",
dest="lead_action", required=True, choices=[...])`, pass
`action=args.lead_action` at main.py:430. Add a parse-time assertion to CI or a test
that walks every subparser for `dest="action"` collisions.

**Test contract**: full CLI lifecycle via `main([...])` — add → set-half ×2 →
`lead promote --lead N --klass Access --action read --severity high` → prints
`lead L-N promoted -> finding #M`, lead `state == 'promoted'`, `promoted_finding_id`
set, finding's `action == 'read'`; `--action mutate` on a RoE-less target → promote
BLOCKED by the RoE default-deny gate (the R2-02 behavior, currently unreachable);
grep-guard test: no `add_argument("--action")` without an explicit non-`action` dest
anywhere in main.py.

### E1 — P1: Parked is a one-way door; the lead state machine dead-locks `[repro]`

`db.py:812-815` documents `parked -> open` as a legal transition ("parked (… always with a
testable retrigger condition) -> open"). No code path performs it: there is no
`reopen/unpark/wake` function in the module, and **every** lead writer gates on
`state in ("open", "mutating")`:

- `_set_lead_half` (db.py:872-876) — BLOCKED on parked
- `add_lead_precondition` (db.py:988-992) — BLOCKED
- `mutate_lead` (db.py:1016-1022) — BLOCKED
- `set_lead_payload` (db.py:1344-1349) — BLOCKED
- `kill_lead` (db.py:1174-1178) — BLOCKED ("only open or mutating leads can be killed")
- `promote_lead` (db.py:1291-1295) — BLOCKED

Repro (real output, throwaway db): a parked lead, then all seven exit attempts:

```
state: parked
set-half trigger proven: BLOCKED (lead L-1 is parked — half verdicts are only admissi...)
set-half refuted:        BLOCKED
mutate:                  BLOCKED
add precondition:        BLOCKED
payload set:             BLOCKED
kill (both refutations): BLOCKED
promote:                 BLOCKED
has reopen/unpark/wake fn: False
```

Consequences that compound: (a) the kill-refusal flow (I5) parks leads **by design** and
increments `dismissal_count` "so a half-refuted lead doesn't die quietly" — but the lead
can now never be killed, promoted, or resumed: refusal is a tombstone, not a pause;
(b) parked leads render forever in the brief's tripwire table (db.py:~1978-1982) with a
tripwire that can never re-open anything; (c) I15's "wake the lead" story
(db.py:1132) is unimplementable. Not a deadlock *error* — a deadlock *by omission*.

**Fix**: one writer, `reopen_lead(conn, lead_id)`: state gate `parked` only, sets
`state='open'` (keep `retrigger_condition` for history), logs `lead_state_reset` —
which is already an event kind `_build_provenance` listens for (db.py:1237, currently
written by nobody, see E6). CLI: `hunt lead reopen --lead N`. Optional stricter variant:
require the tripwire to be "checked" via `--note` evidence, but the state fix must not
wait on that design debate.

**Test contract**: park → reopen → `state == 'open'` and `hunt lead mutate` succeeds;
reopen on open/mutating/killed/promoted → BLOCKED; reopen logs `lead_state_reset` and
`_build_provenance`'s parked-day window closes at the reopen event (parked_days stops
growing); refusal-parked lead → reopen → kill (both refutations) → `killed`.

### E2 — P1: `--tvl nan` permanently poisons the targets row; list/report crash forever `[repro]`

A5/A8 fixed the `score` gate (main.py:145-146 rejects non-finite **before** argparse's
float() binds NaN) but `target add` got no such gate:

- `main.py:541`: `pta.add_argument("--tvl", type=float, default=0)` — argparse's float
  happily accepts `nan`/`inf`/`1e999`.
- `db.add_target` (db.py:418-426) has no finiteness check (contrast `score_target`
  db.py:~442-445). SQLite binds NaN as **NULL**.

Repro (real output):

```
$ HUNT_DB=... hunt target add T https://x.xyz --tvl nan   → rc 0
tvl bound as: None
$ hunt target list
TARGET LIST CRASH: TypeError unsupported format string passed to NoneType.__format__
$ hunt report 1
REPORT CRASH: TypeError unsupported format string passed to NoneType.__format__
```

The poisoned row is **permanent**: no CLI command edits tvl, so from then on *every*
`hunt target list` (main.py:121-122, `${r['tvl_usd']:,.0f}`) and every
`hunt report <id>` (db.py:1781, `${t['tvl_usd']:,.0f}`) for that db crashes — one bad
flag bricks the overview for all targets. `--age-days` has the same argparse-accepts-
anything shape (int is safer, but absurd values also flow in unvalidated).

**Fix**: (1) gate at the CLI: in `cmd_target` `add`, `math.isfinite(args.tvl)` and
`args.tvl >= 0`, `args.age_days >= 0` (mirroring cmd_score); (2) belt in
`db.add_target`: `if not math.isfinite(tvl_usd) or tvl_usd < 0: raise ValueError("BLOCKED: ...")`;
(3) display-side COALESCE in the two format strings so a legacy poisoned row renders
instead of crashing (`f"${(r['tvl_usd'] or 0):,.0f}"`, main.py:122 and db.py:1781).

**Test contract**: `main(["target","add","T","u","--tvl","nan"])` → rc 2, BLOCKED line,
row NOT inserted; same for `inf`, `1e999`, negative; regression: a hand-poisoned row
(raw `UPDATE targets SET tvl_usd=NULL`) renders as `$0` in list and report instead of
TypeError.

### E3 — P1: `connect()` ValueError escapes as a traceback on a corrupt db file `[repro]`

A8's contract is written verbatim in the code: *"a bad HUNT_DB (a text file, an
unreadable path) must speak the same BLOCKED contract, not leak a traceback from
connect()"* (main.py:793-794). The catch tuple is `except (sqlite3.Error, OSError)`
(main.py:798) — but `db.connect` wraps its failures as **`ValueError`**
(db.py:380: `raise ValueError(f"BLOCKED: cannot open hunt db ...")`).

Repro (real output, `printf 'not a database' > /tmp/garbage.db`):

```
File "/root/Hunter/app/src/huntos/cli/main.py", line 791, in main
    conn = db.connect()
  File ".../db.py", line 380, in connect
    raise ValueError(f"BLOCKED: cannot open hunt db ({db_path}): {e}")
ValueError: BLOCKED: cannot open hunt db (/tmp/garbage.db): file is not a database
```

(Contrast: HUNT_DB pointing at a *directory* correctly prints
`BLOCKED: cannot open the hunt db (/root): unable to open database file; rc 2` —
that path raises `sqlite3.Error`, which the tuple catches.) Any corrupted/foreign **file**
— the more plausible operator error — leaks a traceback and exits 1, on every command.

**Fix**: one-token class: `except (sqlite3.Error, OSError, ValueError)` at main.py:798
(the ValueError already carries the BLOCKED wording), or have `connect()` raise
`sqlite3.Error`-shaped failures.

**Test contract**: HUNT_DB → text file: rc 2, stderr starts `BLOCKED: cannot open`,
stderr contains no `Traceback`; HUNT_DB → empty file; HUNT_DB → db from a *newer schema*
(CHECK failure) — same contract.

---

## P2 — should fix

### E4 — P2: claim gate crashes (exit 1, traceback) on non-UTF-8 stdin `[repro]`

`claim_gate.read_input` decodes the **file** path leniently (`errors="replace"`,
claim_gate.py:55) but reads **stdin** with a bare `sys.stdin.read()` (claim_gate.py:63).
One invalid byte and the whole hook dies:

```
Traceback (most recent call last):
  File ".../claim_gate.py", line 254, in main
    text = read_input(sys.argv)
  ...
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 17
exit=1
```

The contract (claim_gate.py:21) says the gate speaks {0 = pass, 2 = veto}; exit 1 with a
traceback is outside the contract. Most harnesses treat any non-zero as block, so this is
accidentally fail-closed — hence P2, not P1 — but it's an unspecified third behavior and
it leaks a traceback into hook logs. A7's lesson ("a PoC may print non-UTF-8 bytes",
main.py:204-205) applies verbatim to engine output.

**Fix**: read stdin as bytes and decode with `errors="replace"`
(`sys.stdin.buffer.read().decode("utf-8", errors="replace")`), matching the file path.

**Test contract**: pipe `b"PROVEN \xff\xfe"` into the gate → exit ∈ {0, 2} with a
properly-formatted line, never a traceback; the replaced-decode text still binds markers
(`PROVEN[F-1]` with binary padding still vetoes/passes per db state).

### E5 — P2 (Eff): claim gate `claims()` is O(markers × text) — 100 s on 5 MB `[repro]`

`claims()` (claim_gate.py:145-158) scans the full text once per marker pattern, then for
**every bare marker** runs `nearest_binding`, which slices a ~200-char window — cheap per
call, but multiplied by M markers over an N-char text with `rfind`/`find` scans inside,
cost is O(M×N). Measured (real timing, this machine; re-verified on final head: 100.1 s):

```
input 5,120,400 chars, 900 markers  → claims(): 105.1 s (first run) / 100.1 s (final head)
dense-line input 1,578 KB, 2,000 markers → 629.2 ms
adversarial no-boundary 195 KB → 6.5 ms (regexes themselves are safe — no backtracking blowup)
```

The gate sits in every engine turn's veto path; a verbose engine output (big diffs,
pasted logs with many id-bearing lines) hangs the harness for minutes. No
catastrophic backtracking found (the marker/id patterns are linear — probed
deliberately). P2 because input size is attacker-adjacent (engine output) but bounded in
practice.

**Fix** (two cheap moves): (1) precompute all finding/lead id positions in **one pass**
(`[(m.start(), m.end(), int(g)) for m in _FINDING_ID.finditer(text)]`, same for leads)
and binary-search the window per marker — O(N + M log K); (2) hard cap: if
`len(text) > 2_000_000`, evaluate only the first 2 MB for bare-marker fallback and add a
note, or require explicit binds beyond the cap (explicit binds are O(1) after the marker
pass). **Test contract**: 5 MB / 10k-marker input vetoes in < 1 s (regression ceiling);
result equality old-vs-new on a golden corpus of binding fixtures (`PROVEN[F-1] L-2`,
tie cases, nearest races).

### E6 — P2: `_build_provenance` scans the **global** events table; `lead_state_reset` is a dead event kind `[repro + code-read]`

`_build_provenance` (db.py:1232-1239) reconstructs parked-days via
`SELECT kind, created_at FROM events WHERE detail LIKE 'lead L-<n> %' ORDER BY id` —
no `target_id` clause, no `kind` filter, no index. Two defects in one query:

1. **Global scan** `[repro for the scan shape]`: `EXPLAIN QUERY PLAN` → `SCAN events`
   (real output). The LIKE key is the lead's **row id**, globally unique, so the
   *matched rows* are the right lead's — but every event row in every target's history
   is string-compared to get there. At 10k events × every promote, that's O(E) per
   promote with zero selectivity. `parked_days` itself verified correct in isolation
   (repro: backdated `lead_parked` event → `parked_days computed: 5`).
2. **`lead_state_reset` closes the parked window (db.py:1237) but no code writes that
   kind** (grep: exactly one occurrence — the listener; zero writers in db.py/main.py/
   tests). It's the intended reopen signal for a function that doesn't exist yet (E1).
   Dead branch today; load-bearing the day E1 lands — land them together or drop the kind.

**Fix**: add `kind` to the WHERE (`AND kind IN ('lead_parked','lead_state_reset','lead_killed')`)
plus an index (see E14), or better: write `parked_since`/`parked_until` onto the leads
row at park/reopen time and stop reconstructing history at promote (I9's snapshot is
frozen anyway — a column is cheaper and cannot drift).

**Test contract**: two targets each owning a lead whose row ids interleave in `events`:
promote target A's lead → provenance counts reflect only A's events (pin with distinct
parked-day backdates per target); an `lead_state_reset` event between park and promote
resets the parked window (write it via the E1 reopen function once it exists).

### E8 — P2: `hunt oracle --finding N` is dead on arrival for its only real use case `[repro]`

The CLI help (main.py:456-458 area) sells the finding-anchored oracle: *"The
finding-anchored oracle reuses the finding's lead"* — i.e., trace further observations on
an **already-promoted** lead. But every lead oracle call funnels into
`record_oracle_verdict`, whose state gate (db.py:1466-1471) requires
`state in ("open","mutating")` — and a promoted lead is terminal. Repro (final head,
db-level, real output):

```
oracle on promoted lead: BLOCKED -> BLOCKED: lead L-1 is promoted — the oracle runs on open or mutating le...
```

So `--finding` can only ever target the lead of a finding that is **not yet promoted**
— which is the one case where you'd use `--lead` instead. The flag's only reachable
success path is redundant; its advertised path always fails. (Re-verified post-R2-02:
unchanged by the mid-audit landing.)

**Fix**: either (a) document `--finding` as a pre-promote alias and add a test pinning
that, or (b) make it meaningful: allow `record_oracle_verdict` on a promoted lead to
append the oracle event + update the *finding*'s evidence trail without touching the
frozen verdicts (I9-safe), explicitly for post-promote re-observation. (a) is one test;
(b) is the product the help text promises.

**Test contract**: (a) finding of an open lead: `oracle --finding` == `oracle --lead`
same verdict/event; promoted lead: documented behavior pinned (BLOCKED today, or the
(b) event-append path); finding without lead: existing BLOCKED message (already tested).

### E9 — P2: `mutate --resolve` resurrects a **refuted** precondition without an evidence gate `[repro]`

`mutate_lead`'s `resolve` path (db.py:1049-1060; the bare UPDATE at 1059) validates only
*ownership* (the precondition belongs to this lead) and then unconditionally sets
`status='present'`. A precondition an oracle or refutation flipped to `refuted` is
silently resurrected:

```
refuted precondition after --resolve: present   (resurrection without evidence gate)
```

Downstream: `_build_provenance` counts it as `preconditions_present` in the frozen
snapshot (db.py:1252-1259) — the promoted finding's provenance then records a disproven
precondition as present. The `missing → present` transition is the intended one;
`refuted` should require its own refutation-reversal evidence or be refused.

**Fix**: read the row's status before the UPDATE: `refuted` → BLOCKED
("refuted by <evidence> — reverse it with a dedicated command or a new precondition");
`missing` → set present (unchanged); `present` → idempotent no-op or BLOCKED on
re-resolve. **Test contract**: refuted + `--resolve` → BLOCKED, status stays refuted;
missing + `--resolve` → present (existing behavior preserved); provenance snapshot after
a refused resolve shows `preconditions_refuted` unchanged.

### E10 — P2: `open_wave` retro-link claims every `wave_id IS NULL` finding — including deliberately unlinked ones `[code-read]`

The B-L27 suspenders (db.py:1686-1689):
`UPDATE findings SET wave_id=? WHERE target_id=? AND wave_id IS NULL AND ladder_status != 'overturned'`.
Cross-target safety verified: the `target_id` clause correctly scopes the claim
(repro: T1's NULL finding kept `wave_id IS NULL` after T2's `open_wave` — no theft across
targets). What remains:

- **No provenance marker**: a raw-SQL-inserted or pre-v0.3 legacy finding with a NULL
  wave_id (e.g. a row the operator deliberately left unlinked — the schema allows NULL
  and `promote_lead`'s own belt at db.py:1318-1325 *sets* NULL in the gap) is
  indistinguishable from a gap-born promote. After the next `open_wave`, it is silently
  conscripted into wave economics: `close_wave` counts it in `findings_new`
  (db.py:1730) and the economic-stop gate (db.py:1732-1741) judges waves the
  operator never intended it to belong to.
- **Double-claim ordering**: promote-in-gap (belt sets NULL) followed by open_wave
  (retro-link) is the intended flow and works; but a promote *during* an open wave is
  linked by `add_finding` (db.py:584-589) — so the retro-link's only legitimate
  population is "gap-born promotes". Restricting to them is free: those rows carry
  `lead_provenance IS NOT NULL` (promoted leads) or can be marked at promote time.

**Fix**: narrow the clause to `AND lead_provenance IS NOT NULL` (gap-born lead promotes)
**plus** keep the belt; or add `findings.wave_link_origin TEXT` set to `'auto'` by
add_finding/retro-link and never touched for operator rows. **Test
contract** `[code-read-based]`: raw-inserted NULL-wave finding with
`lead_provenance IS NULL` survives open_wave unlinked (pin the deliberately-unlinked
case); gap-promoted lead finding IS claimed; overturned stays untouched (existing).

### E11 — P2: `close_wave` rewrites a closed wave's verdict; history economics are mutable `[repro]`

`close_wave` (db.py:1721-1748) has no "already closed" gate. Real repro:

```
close1: continue 0
close2 (rewrite): pivot 0     # wave's ev_verdict silently replaced
close3 'exhausted'            # would fire archive_target (blocked only by the lesson gate here)
```

Consequences: (a) the two-consecutive-zero-findings economic-stop gate
(db.py:1732-1741) reads the *stored* verdict of the previous wave — rewriting wave N's
verdict after wave N+1 closed retroactively changes whether N+1's close should have been
blocked; (b) an `exhausted` re-close re-fires `archive_target` (db.py:1744; the A2
comment at db.py:1726-1728 says the archived lock fires *before* a second exhausted
close could re-run it — the lock holds for the *target*, but the close itself still logs
another `wave_closed` event and recomputes `findings_new`, now against post-wave
findings); (c) `findings_new` is recomputed on every re-close (db.py:1742), so a verdict
rewritten weeks later reports today's count, not the wave's own.

**Fix**: `if wave["ev_verdict"]: raise ValueError("BLOCKED: wave N already closed
(<verdict>) — waves are append-only; record a re-audit instead")` as the first gate after
fetching the row. **Test contract**: second `close_wave` on a closed wave → BLOCKED,
stored verdict unchanged, no second `wave_closed` event; the consecutive-zero gate still
fires on genuinely consecutive closes (existing m24 coverage stays green).

### E12 — P2: promote_lead spans two commits; the crash window strands an orphan finding and the re-run duplicates it `[repro (commit count) + code-read (window)]`

Verified with a trace callback (real output): **one `promote_lead` call emits 2 COMMITs**
— the first inside `add_finding` (db.py:590), the second at promote's own end
(db.py:~1338). Between them sit the `wave_id=NULL` belt (1318-1325), the provenance
UPDATE (1327-1329) and the lead-state UPDATE — none committed. Kill the process there
(OOM, Ctrl-C, CI timeout) and the db is left with:

- a finding whose `lead_id IS NULL` and `lead_provenance IS NULL` (the crash injected at
  that boundary left `findings born=1 (lead_id NULL), lead state=open` in the blocked
  monkeypatch run; the two-commit trace proves the boundary exists),
- the lead still `open` with both halves proven → the operator (or a retry loop) re-runs
  promote → **a second, correctly-linked finding for the same lead**. Two findings, one
  observation; the orphan has no provenance and no lead binding, so briefs and reports
  count it as an unlinked finding forever.

The whole point of the I9/I10 snapshot ("the finding is born through the existing
add_finding… the lead adds its gates on top") is one atomic birth. Today it's two.

**Fix**: one transaction: wrap promote_lead's body in an explicit transaction
(`conn.execute("BEGIN IMMEDIATE")` … single `commit` at the end) and give `add_finding`
a `commit: bool = True` parameter (internal callers pass False), or inline the INSERT.
Single-commit invariant is testable and cheap. **Test contract** `[code-read-based]`:
trace callback asserts exactly **1** COMMIT per promote_lead; a forced failure between
the finding INSERT and the lead UPDATE (monkeypatch `conn.execute` to raise on the
`UPDATE leads SET state='promoted'` call) leaves **no** finding row after rollback and
the lead promotable with re-run producing exactly one linked finding. Note:
`add_finding`'s `finding_added` event currently omits `finding_id` (db.py:582) — pass
`finding_id=` there so the audit trail binds the row id.

### E13 — P2: the test suite has an assert-nothing test, duplicated fixtures, and CLI-surface holes `[repro (grep)]`

- **Assert-nothing test**: `test_m19_claim_gate_l_binding_delegated`
  (test_leads.py:478-484) only does `import test_claim_gate` — its "assertion" is that
  the import succeeds. Side effect: the entire claim-gate suite effectively **runs
  twice** in the collection, inflating the count and hiding a coverage hole: if the
  L-binding tests were ever removed from test_claim_gate.py, M19 stays green.
- **Fixture duplication**: `conn` defined three times (test_enforcement.py:13,
  test_leads.py:18, test_claim_gate.py:32); `hunting_target` (7 setup calls per use)
  exists only in test_leads — enforcement tests re-walk phases by hand. Zero
  module-scope fixtures (deliberate isolation is defensible; the cost is ~8s and growing).
- **CLI surface never exercised through `main()`** (grep across all three test files,
  real counts): `challenge` 0×, `roe` 0×, `artifact` 0× as a CLI word, `archive` 0× via
  main(), `reaudit` 0×, `wave` 0× via main(), `brief` 0× via main(), `score`/`phase`
  only at db level. The A8 BLOCKED-contract paths for these commands (argparse
  per-action subparsers, the `--summary` gate at main.py:~240-244, the archive reason
  gate) are untested end-to-end. E22 is exactly the kind of bug this hole hides — a
  one-line CLI smoke test on the promote path would have caught the R2-02 regression
  before it landed.
- Function-level: `_validate_retrigger`, `_parse_retrigger`, `_build_provenance`,
  `list_targets`, `list_leads`, `list_lessons`, `read_project_lock`,
  `add_lead_precondition` are never named in any test (indirect coverage exists for
  some via public callers; `_build_provenance`'s parked-day math and
  `read_project_lock`'s malformed-JSON branch are genuinely uncovered — E6/E17).

**Fix**: delete M19's body and renumber the matrix mapping (or make it a real
cross-module contract test: `assert "test_lead_bound_claim_passes_after_promote" in
dir(test_claim_gate)`); promote `conn`/`hunting_target` into `app/conftest.py`; add one
CLI-level smoke test per untested command group (wave open/close/reaudit, archive,
roe, challenge, artifact, brief) asserting rc + BLOCKED contract on the empty-arg path.

**Test contract**: `pytest --collect-only` shows each command's smoke test; deleting
test_claim_gate.py's L-binding tests turns a named M19-replacement test RED.

---

## P3 — polish / efficiency

### E14 — P3 (Eff): zero indexes on any hot query path `[repro: grep + EXPLAIN]`

`grep "CREATE INDEX" db.py` → **0 hits**. Every `target_id`/`wave_id`/`lead_id`/`state`
query is a table scan. Measured at v0 scale it does not bite (repro: `export_brief` with
400 open leads = 10.4 ms; `find_contradictions` ×50 at 407 events = 4.3 ms) — but the
scan shape is confirmed (`SCAN events` for the provenance LIKE, E6) and `events` is the
fastest-growing table (3 rows per lead action, ~10 per finding lifecycle). The on-chain
mismatch check (db.py:~1592-1597) is a correlated EXISTS over `events.finding_id` per
finding row — O(N×E) at 100+ findings.

**Fix** (5 lines in SCHEMA, all `CREATE INDEX IF NOT EXISTS`):
`events(finding_id)`, `events(target_id, kind)`, `findings(target_id)`,
`findings(wave_id)`, `leads(target_id, state)`, `lead_mutations(lead_id)`,
`lead_preconditions(lead_id, status)`. Zero behavior change, zero migration risk
(idempotent), makes E6's query and M4 stats viable. **Test contract**: `EXPLAIN QUERY
PLAN` for the provenance query and the mismatch query shows `USING INDEX` (pin in a test
that fails on `SCAN events` for the lead-scoped subset once the kind-filter lands).

### E15 — P3: oracle accepts negative timing and ignores `size` entirely `[repro]`

`_read_oracle_feature` checks `math.isfinite` only (db.py:~1414) —
`{"timing_ms": -5.0}` validates clean (repro: "negative timing_ms: ACCEPTED at
validation"). The rule then computes `3*max(baseline,1.0)` and `c - b >= 500`, so a
negative baseline (200→-600 ms) can never anomaly-fire and inverted timings produce
verdicts with no physical meaning (repro: both-negative → `refuted`; candidate −9000 ms
vs baseline 5000 ms → `refuted`). Separately, `size` is required, validated, stored…
and never read by `oracle_verdict` (repro: size 10 → 999999 with identical
status/sha/timing → `refuted`, i.e. a 100 kB response-body inflation is invisible). The
spec (SPEC §I12) defines exactly these keys and the exact rule, so this is
spec-compliant — the finding is that **the validation contract advertises four signals
and the rule uses two and a half**. Either validate `timing_ms >= 0` (and document
size as context-only) or make size delta a third delta term.

**Fix**: `if timing < 0: BLOCKED` (one line, matches A5's "refuse at the source"
philosophy); document `size` as recorded-context in `_read_oracle_feature`'s docstring,
or add `delta_size = abs(c.size - b.size) >= threshold` to the rule with a spec
amendment. **Test contract**: negative timing → BLOCKED at `_read_oracle_feature`;
size-only delta → pinned verdict (whichever the spec lands on).

### E16 — P3: concurrency race is fail-closed but ugly; two CLI processes can spuriously BLOCK `[code-read + repro]`

`add_lead` computes `MAX(number)+1` in autocommit, INSERTs in a separate write tx
(db.py:955-962). Two concurrent CLI processes can both see the same max; the loser hits
`UNIQUE(target_id, number)` and surfaces `BLOCKED: database error: UNIQUE constraint
failed: leads.target_id, leads.number` — correct, not corrupted, but a raw sqlite message
where every other gate speaks a named BLOCKED. Empirical: 2 processes × 15 concurrent
add_lead on WAL → 30/30 succeeded, **no duplicate numbers** (the UNIQUE constraint did
its job; WAL+timeout=10s absorbed the interleavings). Same shape for `open_wave`
(MAX+INSERT, protected by `UNIQUE(target_id, number)`). WAL is confirmed on
(db.py:333), `timeout=10.0` confirmed (db.py:330) — A8's busy-wait item landed.

**Fix**: catch `sqlite3.IntegrityError` around the leads INSERT and re-raise as
`BLOCKED: lead numbering raced with a concurrent add — retry` (or retry once in-process
with a recomputed number). **Test contract**: two threads sharing one db, barrier before
add → both terminate in {success, named BLOCKED}, never a raw UNIQUE message, numbers
never duplicated.

### E17 — P3: `hunt project status` leaks the raw JSONDecodeError text `[repro]`

With a malformed `.huntos-project`, `cmd_project` status prints
`BLOCKED: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)` —
Python's internal parser message as a user-facing BLOCKED line (main.py:282-301; the
named-message variant lives in `db.check_project_lock` db.py:2045-2054 but the CLI
`project status` path re-reads the file itself and prints `e` raw). Also inconsistent
with the mismatch path, which prints a named message.

**Fix**: reuse `db.check_project_lock(conn, cwd)` in `cmd_project` status and print its
named message (one branch deleted, two code paths become one). **Test contract**:
malformed lock → `hunt project status` prints the named "malformed — fix or delete it,
or rebind" line, rc 2; no parse-error text.

### E18 — P3: dead code and docstring lies `[code-read]`

- `main.py:100-101`: `_t()` — zero callers (grep).
- `claim_gate.py:103-108`: `nearest_finding()` — kept "for the finding part of the
  race" but `claims()` calls `nearest_binding` directly; zero callers in prod or tests.
- `db.py:865`: `_set_lead_half` docstring says "Returns the event id" — returns
  literal `0` (the `log_event` id is discarded).
- `db.py:1237`: `lead_state_reset` listened for, never written (see E6/E1).

**Fix**: delete the two dead helpers, fix the docstring or return the real id
(`_set_lead_half` returning the event id would also let the oracle event be correlated
later). **Test contract**: n/a (grep-based: zero references after removal; suite green).

### E19 — P3: `admin takeover` can never be explicitly bound; tie-break precedence is doc-only `[code-read]`

`_explicit_lead_bind`/`_explicit_bind_id` accept only `PROVEN`/`EXPLOITABLE`
(claim_gate.py:119,132) — the takeover phrase (the *most* overclaim-prone marker, per
the gate's own docstring) has no bracket form, so `admin takeover[L-1]` binds only via
the nearest-id fallback. And the L-vs-F distance tie → finding (claim_gate.py:95) is
implemented but documented only in `nearest_binding`'s docstring; v0.4's `claims()`
docstring lists a different precedence order (explicit lead > explicit finding > nearest)
without mentioning the bare-marker tie. Confirmed working as intended
(`PROVEN[F-1] L-2` → binds F-1; tested), but the takeover-phrase asymmetry is an
operator surprise waiting in a bridge doc.

**Fix**: either support `admin takeover[L-n]/[F-n]` in the two bind helpers (drop the
`m.group(0) in (...)` restriction for the phrase, match `\[([FL])-(\d+)\]`) or document
the asymmetry in bridge/README.md's binding table. One test per decision.

### E20 — P3 (Eff): one lead lifecycle costs 7–9 CLI invocations; connect() re-runs SCHEMA+guards each time `[repro: timing]`

add → set payload → next → mutate → next → set-half ×2 (or oracle ×2) → promote = 7–9
process spawns, each paying interpreter start + `db.connect()` (measured: **1.2 ms**
existing db, **30.6 ms** fresh db — SCHEMA executescript + guard setup + migrations on
every call). Fine for humans, slow for the automation HUNT-OS addresses. No correctness
issue.

**Fix**: (a) `hunt lead flow --lead N --mutate v=o->n --result r ...` multi-verb
compound command, or (b) keep JSON-lines stdin mode for scripted loops. Also cache the
connect-time work: skip `executescript(SCHEMA)` when `meta.db_id` already exists
(one SELECT, saves most of the fresh-db path on steady-state calls).

### E21 — P3 (Eff): brief/status N+1 patterns are fine at v0 scale — keep, but pin the ceiling `[repro: timing]`

`export_brief` calls `next_mutation` per open lead (db.py:~1971) and
`find_contradictions` re-runs per target per status/brief (measured: 400 leads → 10.4 ms
brief; 50× contradictions at 407 events → 4.3 ms). No action needed now; the E13 indexes
plus a `LIMIT` on the leads-rendered list keep v1.0 dashboards honest. **Test
contract**: perf smoke (pytest marker): brief with 500 leads + 5k events completes
< 500 ms — fails loudly when someone makes next_mutation quadratic.

---

## Fixed during this audit (verified, keep the regression tests)

### E7 — oracle-refuted laundering — **VERIFIED FIXED by R2-05** `[repro]`

At audit start, manual `proven` over an oracle-**refuted** half was allowed (repro:
`manual proven over oracle-refuted: ALLOWED -> half now: proven`) — narrower than the
landed B-L1 comment's own contract. The mid-audit landing of R2-05 (db.py:882-892,
guard `if current in ("ambiguous", "refuted")`) closed it. Re-verified on final head:
both `manual proven` and `manual refuted` over an oracle-refuted half → BLOCKED with
"was set by the oracle (refuted)". **Test contract to keep**: the landed
`test_r205_manual_proven_over_oracle_refuted_blocked` plus one for the manual-`refuted`
arm; the oracle-rerun-then-confirm path must stay legal (verified: oracle re-run on an
oracle-refuted half still sets `proven` — the only legal path, per the error message).

---

## Upgrade-path notes (v1.0 / multi-target dashboard / M4 stats)

1. **events.detail is a schema-less blob** — phase artifacts live as
   `detail LIKE 'surface_map:%'` (db.py:~475-477), oracle verdicts as JSON strings,
   poc digests as 16-hex prefixes. Every dashboard query over artifacts/verdicts is a
   LIKE scan. Before M4: split `events` into `kind` + structured columns (or a
   `kind, artifact_type` pair) — the single highest-leverage schema change; doing it
   post-1.0 means rewriting every LIKE.
2. **Provenance is a frozen JSON string** (`findings.lead_provenance`) — cannot be
   SQL-aggregated (`parked_days`, `mutations` per klass). If M4 wants "parked days by
   severity", it needs either JSON1 (stdlib sqlite has it, but the query surface gets
   ugly) or the `leads.parked_since` column from E6's fix. Land the column, keep the
   snapshot for the audit trail.
3. **No FK indexes** (E14) — multi-target joins (`findings ⋈ waves ⋈ leads`) are the
   dashboard's bread and butter; add the indexes now (idempotent) so v1.0 doesn't ship
   with a profiling surprise.
4. **CHECK-constrained enums** on `leads.state/verdicts`/`findings.ladder_status`
   mean any new state (e.g. a reopen design for E1, or a `deferred` rung) is a table
   rebuild. The klass pattern (allow-list as DATA, db.py:130-138) is the house style —
   leads missed it. Migrating leads' state to a DATA table before v1.0 is cheap; after
   v1.0 it's a migration with a rewritten CHECK.
5. **Dual identity for leads**: `L-<row id>` (claim gate binding) vs
   `number` (per-target, brief display). v1.0's UI must pick one; today the brief says
   `L-{id}` (db.py:~1977) while `hunt lead list` shows `#number` too — harmless now,
   a support ticket later. Document or unify.
6. **`targets` has no `updated_at`/phase timestamp** beyond `created_at` — M4
   time-series (phase durations, hunt velocity) reconstructs history from
   `events.created_at` only, with no index on it (E14). Add `events(created_at)` when
   the stats work starts.

---

## Verified-clean (checked, no finding)

- WAL + `timeout=10.0` present (db.py:330-333) — A8's item landed.
- `_parse_retrigger` edge cases: `'obs :: check :: extra'`, whitespace-only sides,
  `'obs ::\tcheck'` all BLOCKED correctly (repro, 4/4).
- `promote_lead` over ambiguous/refuted/unproven halves: BLOCKED with both halves
  named (repro, re-verified on final head).
- `open_wave` retro-link is target-scoped — no cross-target theft (repro).
- Claim-gate marker regexes: no catastrophic backtracking (probed, 6.5 ms worst case).
- `verify_report_file` fail-closed paths (missing footer, appended content) intact.
- CAS promote (`WHERE id=? AND ladder_status=?`) intact; stale-promotion test present.
- Workspace lock BLOCKED path for mismatched writes intact.
- Suite isolation: no module-scope state, tmp_path dbs per test — no fixture leakage found.
- Concurrent `add_lead` (2 processes × 15, WAL): 30/30 ok, zero duplicate numbers —
  UNIQUE + WAL hold (E16 notes the message-quality nit only).
