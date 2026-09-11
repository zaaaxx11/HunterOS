# IMPL-NOTES-batch3 — SPEC-batch3 (C1-C10), Subagent A'

- Implementer: Subagent A'. Spec: `pr/SPEC-batch3.md` (FINAL, arbiter).
- Baseline at start: `cd app && python3 -m pytest tests/ -q` → **168 passed in 8.03s**.
- Final: `cd app && python3 -m pytest tests/ -q` → **190 passed in 9.7s** (168 + 22 new, all in `app/tests/test_batch3.py`).
- Order: C1 → C10 sequentially, each fix green before the next (RED first — the C-tests were written against the un-patched code and failed, then landed).
- No commits, no pushed branches, no deps installed, SOUL.md untouched. CI touched only for the C9 grep step.

---

## C1 — E3 corrupt db file (DONE)

**Fix**: `app/src/huntos/cli/main.py` main() catch tuple `(sqlite3.Error, OSError)` →
`(sqlite3.Error, OSError, ValueError)` + comment. `db.connect()` wraps corrupt/foreign
db files as ValueError; only the directory case raised sqlite3.Error.

**Run proof** (real CLI, garbage file):

```
$ printf 'garbage' > /tmp/garbage_c1.db
$ HUNT_DB=/tmp/garbage_c1.db python3 -m huntos.cli.main target list
BLOCKED: cannot open the hunt db (/tmp/garbage_c1.db): BLOCKED: cannot open hunt db (/tmp/garbage_c1.db): file is not a database
rc=2
```

No traceback, rc=2. Test: `test_c1_corrupt_db_file_blocked_no_traceback`.

**Deviation (documented per spec rule)**: the audit's fuller contract also listed the
**empty file** as BLOCKED. Reality: sqlite's documented semantics initialize a 0-byte
file as a NEW database — `hunt target list` on an empty file returns rc=0 with
"(no targets)" and has never printed a traceback. Spec C1's contract is the garbage
file (which is what was broken); the empty-file behavior is pinned as-is in
`test_c1_empty_db_file_is_a_fresh_sqlite_db` (rc 0, no traceback) instead of forcing a
non-sqlite BLOCKED.

## C2 — E12 promote_lead single commit (DONE)

**Fix** (`app/src/huntos/core/db.py`):
- `add_finding(..., commit: bool = True)` — promote passes `commit=False`; also the
  `finding_added` event now carries `finding_id` (audit E12 note).
- `promote_lead` body: `BEGIN IMMEDIATE` → all writes (finding INSERT, wave-gap belt,
  provenance UPDATE, lead UPDATE, lead_promoted event) → single `conn.commit()`;
  `except BaseException: conn.rollback(); raise`.
- No other API behavior changed: standalone `add_finding` still commits (default True).

**Run proof — BEFORE** (pre-fix shape rebuilt in a scratch package, real run `/tmp/e12_before.py`):

```
[BEFORE] COMMITs per promote_lead: 2  (findings now: 1)
[BEFORE] crash-injected promote: crashed=1 -> orphan findings (lead_id IS NULL): 1, total findings: 2, lead2 state: 'open'
```

**Run proof — AFTER** (landed code, real run `/tmp/e12_after.py`):

```
[AFTER] COMMITs per promote_lead: 1
[AFTER] crash-injected promote: crashed=1 -> orphan findings: 0, total findings: 1, lead2 state: 'open'
[AFTER] retry promoted cleanly -> finding #2, total findings now: 2
```

Tests: `test_c2_promote_lead_single_commit` (trace callback counts exactly 1 COMMIT),
`test_c2_promote_lead_crash_injection_no_orphan` (proxy-connection crash injection at
the lead UPDATE → rollback leaves zero findings, lead still promotable, retry yields
exactly one linked finding). Note: the audit's monkeypatch shape
(`monkeypatch.setattr(conn, "execute", ...)`) is impossible on CPython —
`sqlite3.Connection.execute` is a read-only attribute; the test uses a proxy object
with the same semantics.

## C3 — E14 indexes (DONE)

**Fix**: 7 `CREATE INDEX IF NOT EXISTS` executed in `connect()` (idempotent every
open, same pattern as the tables) — NOT inline in SCHEMA, because a legacy db whose
`findings` table predates `wave_id` (test m22 builds exactly that) would fail SCHEMA
with "no such column". Column-guarded: `idx_findings_wave` is created only when
`wave_id` exists in findings; the other six are unconditional. One-line deviation from
the spec's literal "SCHEMA tambah" — reason: the legacy-db requirement (also in the
spec) conflicts with putting indexes in SCHEMA for a partial legacy table; reality won,
documented here.

**Run proof**: `test_c3_indexes_exist_after_connect` (all 7 present after connect on a
fresh db) and `test_c3_indexes_added_to_legacy_db` (a hand-built legacy db with zero
indexes gains `idx_findings_target` + `idx_events_finding` on connect) — both green.

## C4 — E5 claim gate O(M×N) (DONE)

**Fix** (`bridge/claim_gate.py`):
- `claims()` precomputes ALL finding-id and lead-id positions in ONE regex pass each,
  plus newline positions; per bare marker, the nearest id is found by `bisect` over
  the sorted position lists (window semantics identical: a match counts only when it
  lies fully inside the window; the line+80 neighborhood rule unchanged).
- `_explicit_bind_id`/`_explicit_lead_bind` slice `text[m.end():m.end()+16]` instead of
  the unbounded tail (the bracket, if any, is adjacent).
- Return shape unchanged: list of `(marker, fid|None, lid|None)`.

**Benchmark** (`/tmp/e5_bench.py`, this machine, old algorithm reconstructed verbatim
vs landed code, outputs byte-identical on all shapes):

```
shape                                           OLD        NEW  speedup  identical
A: 5MB/900 markers, 5.6KB lines              0.964s     0.304s      3.2x  True
B: 1.1MB/2000 markers, dense short lines     0.239s     0.076s      3.2x  True
C: 5MB single line, 900 markers (worst)    126.914s     0.841s    150.8x  True
```

The audit's ~100s number corresponds to shape C (single-line dumps); measured here at
126.9s pre-fix → 0.841s post-fix. **Before/after for the contract test's shape: 126.9s
→ 0.84s (< 2s ceiling).** Correctness: a 3000-case randomized differential test against
the old algorithm found 0 mismatches; all 23 pre-existing claim-gate tests pass
unchanged.

Tests: `test_c4_claims_perf_5mb` (5MB single-line / 900 markers < 2s), 
`test_c4_claims_binding_behavior_unchanged` (golden fixtures: explicit lead > explicit
finding > nearest, tie → finding, unbound veto).

## C5 — R2-06 secrets gate (DONE)

**Fix** (`app/src/huntos/core/db.py`): `assert_no_secrets(...)` (the STORAGE gate —
refuses; `redact()` is display-only and was never the storage defense) wired at:

| Field | Site | Gate |
|---|---|---|
| set-half evidence | `_set_lead_half` (covers manual AND oracle evidence; oracle evidence is machine-built so it never trips) | `assert_no_secrets(evidence, f"{half} evidence")` |
| precondition description | `add_lead_precondition` | `assert_no_secrets(description, "precondition description")` |
| mutation evidence | `mutate_lead` (after the non-empty gate) | `assert_no_secrets(evidence, "mutation evidence")` |
| park/kill retrigger | `_validate_retrigger` (one site covers park, kill-refusal auto-park, and kill's optional retrigger) | `assert_no_secrets(retrigger, "retrigger")` |
| reopen evidence | `reopen_lead` — **already landed** in the batch that introduced `reopen_lead` (E1/R2-04); re-tested here | `assert_no_secrets(evidence, "reopen evidence")` |

**Run proof**: `test_c5_secrets_blocked_in_all_five_fields` — `ghp_` and `sk-` shapes
through each of the five fields → `ValueError: BLOCKED: <field> contains what looks
like a raw secret...`, and the set-half case additionally asserts nothing was stored.
`test_c5_reopen_evidence_secret_blocked`, and the false-positive guard
`test_c5_clean_prose_still_accepted` ("reset token present in table users" passes) —
all green. The brief-echo exposure is closed transitively: non-token shapes are
refused at storage, so nothing leaky remains to echo.

## C6 — R2-08 parked payload-less flag (DONE)

**Fix**: `lead_contradictions` selects `state IN ('open','parked')` (was `'open'` only)
and appends `" (still parked)"` to the flag for parked rows.

**Run proof**: `test_c6_payloadless_parked_lead_still_flagged` — 8-day-old payload-less
lead flags while open, then after `park_lead` the flag STILL lists it (was `flags=[]`
before the fix) — green.

## C7 — B-L21 next_mutation state gate (DONE)

**Fix**: `next_mutation` raises `BLOCKED: lead L-<n> is <state> — the mutation loop
runs on open or mutating leads (...)` for any state outside open/mutating. `None`
remains the exhausted-loop answer for live leads (behavior unchanged there).

**Run proof**: `test_c7_next_mutation_promoted_lead_blocked` (promoted → ValueError
matching "promoted"), `test_c7_next_mutation_killed_lead_blocked` (killed → "killed"),
`test_c7_next_mutation_parked_lead_blocked` (parked → "parked"),
`test_c7_next_mutation_open_lead_still_works` (open lead still returns the step dict) —
all green. Existing suite unaffected (next_mutation is called by the brief only for
live leads).

## C8 — B-L24 oracle feature ranges (DONE)

**Fix**: `_read_oracle_feature` bounds — `status` in [100, 599], `size >= 0`,
`timing_ms` in [0, 3_600_000] (1 hour). Outside = `BLOCKED: ... status out of range
(100-599); got -5` etc.

**Run proof**: `test_c8_oracle_feature_ranges_blocked` pins status=-5, status=999,
size=-1, timing_ms=10**12, timing_ms=-5.0 → all BLOCKED;
`test_c8_oracle_feature_valid_ranges_accepted` pins the boundary values 100/599,
size 0, timing 0 and exactly 3600000 as accepted — green.

## C9 — R2-07 docs v0.4 (DONE)

Every command/claim in the docs was executed first (scratch db, real CLI runs via
`/tmp/c9_verify.py`, `/tmp/c9_gate.py`, `/tmp/c9_climb.py`):

```
rc=0  hunt lead add --target 1 ... (lead L-1 added)
rc=0  hunt lead set --lead 1 ... (payload set)
rc=0  hunt lead mutate --lead 1 --variable role ... (mutation #1 recorded, state=mutating)
rc=0  hunt lead set-half --lead 1 --half trigger ... (trigger -> proven)
rc=0  hunt lead set-half --lead 1 --half impact ... (impact -> proven)
rc=0  hunt lead promote --lead 1 --klass Access --roe-action read --severity high (finding #1, snapshot frozen)
rc=0  hunt oracle --lead 2 --half trigger --baseline ... --candidate ... (verdict: confirmed)
ALL-RC-0: True
PROVEN[L-1] after finding proven-live: rc = 0 (claim gate: no unbacked claims)
PROVEN[F-1] same state:              rc = 0
PROVEN[L-2] unpromoted:              rc = 2 (BLOCKED: ... the lead is 'open' ...)
```

Changes (no overclaim — the oracle line in HUNT-BRIDGE explicitly says the verdict
rule is deterministic while the features are self-attested, matching R2-03's honesty
label):

- `README.md`: one new bullet "Leads & the observation lane" (add → mutate loop →
  halves/oracle → promote → kill/park/reopen) + the Guarded-mouth bullet extended with
  the L-binding (verified: an overturned finding kills its lead's claims — that is the
  landed R2-01 behavior, verified in /tmp runs and pre-existing tests).
- `QUICKSTART.md`: new §4.5 "The observation lane: a lead from hypothesis to finding"
  with 5 real commands (add → mutate → set-half ×2 → promote) + 1 `hunt oracle` call +
  park/reopen/kill mentioned; every command verified rc=0 above.
- `docs/FRAMEWORK.md`: L2 new row "HUNTING (leads)" (exit gate: both halves traced,
  payload non-empty; artifact: lead_half_set events + frozen provenance snapshot at
  promote) + L4 says "v0.4" (was v0.3).
- `soul/bridge/HUNT-BRIDGE.md`: 8 new gate-list lines (hunt lead add / next / mutate /
  set-half / oracle / park / kill / promote — 8 ≥ 5) + CLAIMS section now teaches
  `PROVEN[L-<n>]` with the "a lead claim dies with its finding" rule.
- `.github/workflows/ci.yml`: ONE new step "Lead lane doctrine contract" —
  `grep -c 'hunt lead' soul/bridge/HUNT-BRIDGE.md` must be ≥ 5 (currently 8), same
  mechanism as the existing structure gates. No other CI change.

SOUL.md untouched. `test_c9_*` (3 tests) pin the docs structure.

## C10 — E18 dead code (DONE — both deleted, grep first)

**Grep before delete** (real output):

```
$ grep -rn "nearest_finding" --include="*.py" app/src bridge app/tests
bridge/claim_gate.py:104:def nearest_finding(...)          # own def — no callers
$ grep -rn '\b_t\b' app/src app/tests bridge
app/src/huntos/cli/main.py:100:def _t(v: str) -> str:      # own def — no callers
```

Zero callers in prod or tests (docs mention them only as the E18 finding itself).
**Deleted**: `nearest_finding()` from `bridge/claim_gate.py` (dead wrapper — `claims()`
called `nearest_binding` directly) and `_t()` from `app/src/huntos/cli/main.py`
(identity helper). `nearest_binding` survives (it is the real fallback engine).
Behavior change: none (claims() output byte-identical, see the C4 differential runs).

**Run proof**: `test_c10_dead_helpers_removed` + post-fix grep over
`app/src bridge app/tests` shows only the test's own negative assertions.

---

## Skips

None — all ten items DONE.

## Final numbers

```
$ cd app && python3 -m pytest tests/ -q
190 passed in 9.7s        # baseline 168 + 22 new (test_batch3.py: 22 passed)
```

Files modified:
- `app/src/huntos/cli/main.py` (C1 ValueError catch; C10 `_t` removed)
- `app/src/huntos/core/db.py` (C2 commit param + one-transaction promote; C3 indexes
  in connect(); C5 four gate sites; C6 flag query; C7 next_mutation gate; C8 ranges)
- `bridge/claim_gate.py` (C4 one-pass claims + bounded bind slices; C10
  `nearest_finding` removed)
- `app/tests/test_batch3.py` (NEW, 22 contract tests)
- `README.md`, `QUICKSTART.md`, `docs/FRAMEWORK.md`, `soul/bridge/HUNT-BRIDGE.md` (C9)
- `.github/workflows/ci.yml` (C9: one grep step)

Evidence scripts (scratch, not part of the repo): `/tmp/e12_before.py`,
`/tmp/e12_after.py`, `/tmp/e5_bench.py`, `/tmp/c9_verify.py`, `/tmp/c9_gate.py`,
`/tmp/c9_climb.py`.

---

## Ad-hoc verification (post-implementation, independent of the pytest suite)

`/tmp/hermes-verify-batch3.py` (tempfile `hermes-verify-` prefix, scratch dbs under
its own tempdir) probes the CHANGED behavior of each fix directly — real module/CLI
calls, no repo writes. Final run:

```
PASS  C1    # garbage db file via real CLI: rc=2, BLOCKED, no traceback
PASS  C2    # 1 COMMIT traced per promote_lead; crash injection -> 0 orphans, retry clean
PASS  C3    # all 7 indexes on fresh db; legacy schema gains idx_findings_target/_wave/events_finding
PASS  C4    # worst-case 5MB single-line/900 markers < 2s; binding precedence intact
PASS  C5    # secret shapes refused on all 5 fields; clean prose accepted; state order legal
PASS  C6    # payload-less aged lead flagged while open AND after park ("still parked")
PASS  C7    # next_mutation: open -> step dict; parked/promoted -> BLOCKED
PASS  C8    # status/-5,999 size/-1 timing/1e12,-5 all BLOCKED via CLI rc=2; boundaries 100/599/0/3.6M accepted
PASS  C9    # HUNT-BRIDGE >=5 lead lines + CI gate present; full §4.5 walkthrough rc=0 every step
PASS  C10   # nearest_finding/_t gone; nearest_binding still resolves F-3

VERDICT: 10/10 probes PASS — ad-hoc verification OK   (exit code 0)
```

Scope note: this is AD-HOC verification of the changed behavior, run in addition to
(and after) the full suite; the suite run remains the canonical 190-passed gate.

Fresh rerun after the final cleanup pass (script retained at
`/tmp/hermes-verify-batch3.py`, tempfile-based, scratch dbs only):

```
$ python3 /tmp/hermes-verify-batch3.py   -> 10/10 probes PASS, exit 0
$ cd app && python3 -m pytest tests/ -q  -> 190 passed in 9.78s
```

