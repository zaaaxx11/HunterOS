# AUDIT-CHECKLIST-leads.md — adversarial audit of SPEC-leads-oracle v0.4 (Auditor B)

- Auditor: B (adversarial; audit-before-code). Method: spec-faithful prototype of §1/§2/§3
  built in `/tmp/audit-b/proto_leads.py` (uses the baseline `app/src` v0.3 as its substrate,
  imported read-only), then 30+ attack experiments (`/tmp/audit-b/attack*.py`,
  `final_sweep*.py`) run against throwaway sqlite dbs in `/tmp/audit-b/`. Nothing in
  `app/src`, `app/tests`, `bridge/` or the repo was modified; no commits.
- Baseline at audit time: `PYTHONPATH=src python3 -m pytest tests/ -q` → **126 passed**.
- Mid-audit note: Subagent A landed `bridge/claim_gate.py` v0.4 (I13) and the leads
  schema/`db.py` sections while this audit ran (mtime 11:39). Findings that attack A's
  landed code directly are marked **[vs landed code]**; the rest attack the SPEC via the
  prototype. Repro commands are given per finding; all scratch is reproducible from
  `/tmp/audit-b/` (kept intact for cross-correction).
- Severity: P1 blocker / P2 should-fix / P3 polish. "PASS" = the SPEC/prototype shielded
  the attack (with the test that must keep it shielded); "FINDING" = a real hole.

---

## 0. TL;DR — the 8 next actions, ranked

1. **[B-L1, P1] Ambiguous→proven manual overwrite launders an oracle-refuted half into
   promote fuel.** I2 blocks manual `ambiguous` but nothing forbids `set-half proven`
   on a half the oracle just marked ambiguous/refuted. One-line fix + one test.
2. **[B-L3, P1] Promote snapshot (I9) records the wrong things** — the SPEC's snapshot
   fields (`mutations`, `preconditions_present/refuted`, `parked_days`) are neither
   defined as of WHEN nor protected against the mutation count changing after promote.
   Either freeze real counts at promote time in one transaction or cut them from the spec.
3. **[B-L5, P1] I8 duplicate `--plan` crashes with a raw `IntegrityError`** (traceback
   class, not `BLOCKED:`). The SPEC mandates the INSERT but never handles
   `UNIQUE(lead_id,variable,value)` collision with an existing precondition.
4. **[B-L6, P2] I12 has no oracle-shopping cap** — unlimited re-runs per (lead, half)
   plus manual overwrite = verdict shopping. Cap re-runs or make later verdicts
   immutable-by-manual-path.
6. **[B-L27, P2] Wave-economics regression (A's suite RED at audit time):** a lead
   promoted *between waves* inserts its finding with `wave_id=None`; `close_wave` counts
   only linked findings, so the wave that should have shown the promoted finding reads 0
   and the consecutive-zero economic stop fires. A's own
   `test_m24_old_laws_still_hold_end_to_end` fails (`assert 0 == 1`).
7. **[B-L7, P2] Promote-time title/payload override launders the lead record** — the
   SPEC's CLI has no `--title`/`--payload` on promote; if the db function accepts them
   (as any natural implementation will, to reuse `add_finding`), the finding can be
   born with a title/payload the lead never had. Pin both to the lead row.
8. **[B-L9, P2] I13 divergence: `PROVEN[L-1]` passes while `PROVEN[F-1]` (the very
   finding the lead minted) vetoes** — the L-bar is strictly weaker than the F-bar.
   Also `Lead #1 confirmed. PROVEN.` still launders through `#1` nearest-id. **[vs
   landed code]** Document/weaken deliberately or align the bars.
9. **[B-L10, P2] A11-class secret leak in lead free-text**: title/payload/evidence/
   precondition/retrigger bypass `assert_no_secrets`/`redact` (SPEC never wires the
   existing gates into lead fields). Brief echoes retrigger verbatim.
10. **[B-L11, P3] I15 flag is defeatable by any non-`open` state**: set-half on a
   payload-less lead moves it to `mutating` (state promotion, no payload), which hides
   it from the 7-day flag while remaining mutation-less forever.

Verified-clean (must stay clean; test contracts in §2): park gate blocks post-park
mutate/set-half/re-park (X1/X4/X4b); kill-refusal stalls after 1 dismissal (X1c);
oracle cannot mint `proven` and its events cannot be applied cross-lead/cross-half
(X7/X14a/X14d); `UNIQUE(target,number)` holds under the WAL race (X6); archived-target
gate covers all six lead ops (X36); legacy-DB migration keeps add_finding green (X33).

---

## 1. Findings per invariant (ID, severity, evidence, contract)

Format: **ID** — sev — invariant(s) attacked — evidence (experiment id + one-line result;
repro file in `/tmp/audit-b/`) — contract test for A's suite.

### I1 (two-half independence)

**B-L12 — P3 — I1** — CHECK-contract only.
- Experiment: prototype declares the two CHECKs separately; a copy-paste bug
  (`impact_verdict CHECK` referencing trigger states) would still pass every happy-path
  test in §4 (matrix rows never set a state outside the list).
- Contract test `test_i1_impact_check_independent`: raw-sqlite
  `UPDATE leads SET impact_verdict='bogus'` must fail with
  `CHECK constraint failed: impact_verdict` — and, if the schema uses named CHECKs, the
  test asserts `sqlite_master.sql` contains two *distinct* CHECK bodies
  (`trigger_verdict IN` and `impact_verdict IN`). Expected BLOCKED: n/a (schema refuses).

### I2 (oracle-exclusive ambiguity)

**B-L1 — P1 — I2/I10** — manual `proven` over oracle `ambiguous`/`refuted`.
- Experiments (final_sweep5.py): `X7b` oracle-unknown → apply-ambiguous → `set-half
  proven` → **promote succeeded** (`F-1 promoted`, zero mutations). `X5` (attack1.py):
  oracle-refuted → manual `proven` accepted outright (oracle event left dangling).
  `X14b` (final_sweep.py): stale oracle event re-applied over a later manual `proven`
  silently rewound the half to `refuted`.
- Root cause: I2 forbids manual `ambiguous` but is silent on (a) manual `proven/refuted`
  onto a half that already carries an oracle verdict, and (b) re-applying a consumed
  event. The promote gate (I10) then reads the laundered half as earned.
- Fix: a half that carries `ambiguous` or any oracle_event_id is frozen against manual
  set-half (BLOCKED: "L-n trigger was set by oracle event #k — use the oracle"); one
  oracle event applies at most once (consumption flag in detail or a
  `lead_oracle_applied` marker).
- Contract tests:
  - `test_set_half_proven_over_ambiguous_blocked` — lead with oracle-ambiguous trigger;
    `set-half --half trigger --verdict proven` → BLOCKED
    `BLOCKED: lead L-1 trigger verdict was set by oracle — manual overwrite refused (I2)`.
  - `test_set_half_proven_over_oracle_refuted_blocked` — same with oracle-refuted.
  - `test_oracle_event_single_use` — applying event #k, flipping manually (where legal),
    then re-applying #k → BLOCKED `BLOCKED: lead L-1 oracle event #k already consumed`.

**B-L2 — P2 — I2** — SPEC text gap: I12's mapping table never says what `confirmed`
maps to on the lead. Prototype maps confirmed→(nothing applicable). A's implementer
must state it in the docstring: `confirmed`/`refuted` oracle events feed
`set-half --verdict proven|refuted` as *advice only*, with the same single-use rule.
- Contract test `test_oracle_confirmed_cannot_apply_direct`: apply-oracle with
  `--verdict proven` backed by a `confirmed` event → BLOCKED
  `BLOCKED: lead L-1 oracle event #k says confirmed — set-half --verdict proven is the human step (I12)`.

### I3 (payload gate)

**B-L8 — P2 — I3** — set-half promotes a payload-less lead `open → mutating` with no
payload (X16b): I3's "wajib sebelum mutate pertama" is honored by `mutate` (BLOCKED,
verified) but the *state* promotion lets the lead drift out of I15's `open`-only flag
(see B-L11) while staying mutation-less. Also kill-refusal on a payload-less lead is
possible (auto-park path never needed payload).
- Fix: set-half on payload-less lead either BLOCKED (`payload required before verdicts`)
  or allowed with an explicit docstring note; pick one and test it.
- Contract test `test_set_half_payloadless_open_lead_documented`: whichever way A
  chooses, the test pins it — if BLOCKED:
  `BLOCKED: lead L-1 payload required before verdicts (I3)`; if allowed, assert
  `state='mutating'` AND `payload IS NULL` AND the I15 flag still counts it
  (see B-L11 contract).

### I4 (state gate / archived lock)

**B-L13 — PASS — I4** — archived gate verified across all six lead ops (attack7.py
X36): after `close_wave exhausted` archived the target, set-half/mutate/park/kill/
promote/oracle all BLOCKED, lead state unchanged. 
- Contract test `test_lead_ops_blocked_on_archived_target` (matrix row 17 extension):
  parametrize all six ops; each → BLOCKED
  `BLOCKED: lead L-1 — target #1 is archived — the hunt is closed`.

**B-L14 — PASS — I4** — park gate: post-park mutate (X4), set-half (X1), park again
(X4b) all BLOCKED. This makes kill-refusal a *terminal* state after one dismissal —
see B-L4 (design trap, P3).
- Contract tests: `test_parked_lead_refuses_mutate`, `test_parked_lead_refuses_set_half`,
  `test_parked_lead_refuses_repark`, each expecting
  `BLOCKED: lead L-1 is parked — <op> requires open|mutating`.

### I5 (kill guard)

**B-L4 — P3 (design trap) — I5/I6** — kill-refusal dead end (attack7.py X1c/X34): one
refusal parks the lead; the park gate then refuses set-half/mutate, so a *later genuine*
refutation of the second half can never be recorded and kill can never succeed. The
lead is unparkable (no command exists). Not a bypass — a starvation trap the SPEC does
not acknowledge. §5's echo ("kill refused → parked (dismissal #2)") implies multiple
refusals are expected, but refusal #2 is unreachable (kill on parked = BLOCKED).
- Fix options (document the choice): (a) `hunt lead unpark --lead N` with a fresh
  precondition requirement; (b) allow `mutate` on parked leads (park = paused, not
  frozen) while keeping set-half gated; (c) state in SPEC that one refusal is final.
- Contract test `test_kill_refusal_terminal_or_resumable` pins the chosen semantics;
  if (b): `mutate` on parked succeeds and the park tripwire survives in the brief.

**B-L15 — PASS — I5** — refusal increments `dismissal_count` exactly once and writes
`lead_kill_refused` (X1c: `dismissal=1` after 3 attempts, loop stalls correctly).
- Contract test: matrix row 11 as written, plus assert `dismissal_count == 1` and the
  event `detail` contains `dismissal #1`.

### I6 (retrigger format)

**B-L16 — PASS — I6** — `kill --retrigger` refusal path and `park` both enforce
`observable :: check` (prototype `_check_retrigger`; matrix rows 13/14 pass).
- Contract test `test_kill_refusal_retrigger_gate`: kill refused without `--retrigger`
  → BLOCKED `BLOCKED: lead L-1 kill refused (both halves must be refuted with
  evidence) — kill refusal requires --retrigger ...`; with `"a :: "` / `"a::b"` →
  BLOCKED `BLOCKED: park/kill-refusal requires --retrigger "observable :: check" ...`.

### I7 / I8 (anti-repeat, unknown-consumption)

**B-L5 — P1 — I8** — duplicate `--plan` crashes (final_sweep.py `X13raw`):
`lead_mutate(..., plan="param|id=1|dup")` where `param|id=1` already exists →
`sqlite3.IntegrityError: UNIQUE constraint failed: lead_preconditions.lead_id, ...` —
a traceback class, violating the mandatory BLOCKED contract. Atomicity holds
(`X13partial`: mutations=0) but the CLI contract is broken.
- Fix: catch the collision, raise `ValueError("BLOCKED: lead L-n plan pair (var|value)
  already exists as precondition #k — pick a NEW pair")`. Also decide I8-vs-I11: a plan
  whose pair equals the mutation's own `new_value` is *born already tried* (attack3.py
  `X13b`: `next` immediately suggests park) — legal per I11's letter, starvation per its
  spirit; BLOCKED it or document it.
- Contract tests:
  - `test_unknown_plan_duplicate_blocked` → BLOCKED
    `BLOCKED: lead L-1 plan pair (param|id=1) already exists as precondition #1`.
  - `test_unknown_plan_self_colonizing_value_blocked` (or documented-allowed) — plan
    `--plan "param|<new_value>|..."` where `new_value` is the mutation just recorded →
    BLOCKED `BLOCKED: lead L-1 plan value equals the mutation's new_value — born tried (I8/I11)`.

**B-L17 — PASS — I7** — repeat `(lead_id, variable, new_value)` BLOCKED; same variable
different value OK (prototype X3-style rows; matrix row 5).
- Contract test: matrix row 5 as written, plus assert the BLOCKED message names the
  lead: `BLOCKED: lead L-1 repeat mutation (v -> b) — anti-repeat (I7)`.

**B-L18 — P2 — I7 (cross-lead)** — anti-repeat is per-lead only; the same
`(variable,new_value)` refuted on L-1 is freely replayed on L-2 (attack3.py X17: both
rows coexist, one `refuted` one `advanced`). SPEC's task-brief asks about
"anti-repeat cross-lead" — current answer: not covered. A *finding* is the natural
dedup unit, so hard-blocking would be wrong (leads on the same target legitimately
share recon state); instead: `lead mutate` on lead L-2 with a pair already
`refuted` on another lead of the SAME target must at least WARN (echo line) or record
the cross-reference; `export_brief` should list prior refutations.
- Contract test `test_cross_lead_refuted_pair_warned`: mutate L-2 with L-1's refuted
  pair → command succeeds (exit 0) AND stderr/echo contains
  `WARNING: (param=b) was refuted on L-1 — same target` (or the brief lists it); pin
  whichever behavior A chooses.

### I9 (provenance frozen)

**B-L3 — P1 — I9** — the SPEC's snapshot `{mutations, preconditions_present,
preconditions_refuted, parked_days}` is under-specified and provably unstable:
1. When are they measured? `parked_days` at promote time for a lead that parked and
   resumed is ill-defined (prototype parked leads cannot resume at all — B-L4).
2. Mutation count is NOT frozen by the schema: `lead_mutations` rows reference the
   lead, and nothing blocks `mutate` after promote unless the state gate does
   (state='promoted' is outside open|mutating — verified X21 the *prototype* blocks
   it, but raw SQL doesn't, and the SPEC never asks for a trigger).
3. Landed-code check (X21): finding ladder can climb theoretical→proven-live after
   promote while `lead_provenance` keeps its birth snapshot — fine — but the SPEC's
   `promoted_at` is the only timestamp, so a reader cannot tell whether `mutations=5`
   means "5 before promote" or "5 total ever".
- Fix: snapshot real `COUNT(*)` values in the same transaction as the promote (SELECT
  counts → INSERT finding → UPDATE lead state), and state in the SPEC: "counts are
  as-of promote; post-promote mutation attempts are BLOCKED by the state gate; raw-SQL
  additions are detectable by `mutations_live > mutations_snapshot`" — and ship a
  `find_contradictions` flag for exactly that divergence.
- Contract tests:
  - `test_provenance_counts_frozen_at_promote` — lead with 3 mutations, 2 present / 1
    refuted preconditions → snapshot matches exactly; then raw-INSERT a 4th mutation →
    `find_contradictions` flags `!! lead L-1 mutation count diverges from promoted
    snapshot (4 vs 3)` (I15 extension; see B-L20).
  - `test_provenance_unchanged_after_edit` — matrix row 21 as written.

**B-L19 — P2 — I9/I10** — promote-time title/payload override launders the record
(attack8.py X39/X40): prototype `lead_promote(..., title="INJECTED TITLE")` produced a
finding titled `INJECTED TITLE` and a snapshot whose `payload` differs from the lead's
row. The SPEC's CLI (§3) has no `--title/--payload` flags on promote — but any
implementation reusing `add_finding(title, ...)` will invent one. Pin it: promote takes
NO content arguments; finding title = lead title (redacted), notes = lead payload.
- Contract test `test_promote_uses_lead_content`: promote with any db-function kwargs
  beyond `klass/severity` → TypeError or BLOCKED; the inserted finding's `title ==
  lead.title` and `notes == lead.payload` (both through `redact()`).

### I10 (promote gate)

**B-L20 — P2 — I10** — verified-clean paths: both-halves-proven gate (X8
ambiguous→BLOCKED `promote requires both halves proven`), payload gate, archived gate,
taxonomy/severity via `add_finding` (row 16). The zero-mutation promote (X26: verdicts
set manually, no mutations ever) is legal per the letter of the SPEC — both halves
proven is the only evidence bar — but it makes I10 strictly weaker than the findings
ladder it feeds (a lead promote inserts a theoretical finding needing the full ladder
anyway; the lead's own `proven` halves are self-attested set-half calls). Not a bypass;
a wording overclaim to fix: SPEC §2 I10 says "kedua half proven" — add "(set-half
attempts are logged with evidence; the finding ladder remains the real bar)".
- Contract test `test_promote_with_zero_mutations_allowed_but_audited`: promote
  succeeds; `find_contradictions` (or the echo) contains
  `!! lead L-1 promoted with 0 recorded mutations` — pin it so the honesty flag exists.

### I11 (deterministic next)

**B-L21 — P2 — I11** — `lead_next` on a **promoted** lead still returns an actionable
precondition (attack7.py X35: `{'variable': 'v', 'value': 'a', 'lead_state': 'promoted'}`).
Matrix row 18 only defines exhausted-open behavior. `next` on promoted/killed must be a
no-op suggestion, not work orders on a closed lead.
- Contract test `test_next_on_promoted_lead_is_noop`: →
  `{'suggest': None, 'message': 'lead L-1 is promoted — no next mutation'}` (or
  equivalent; no precondition_id).

**B-L22 — PASS — I11** — determinism + exhaustion suggestion verified (attack5.py X25:
first→`param`, after `unknown` with plan→`mode`; exhausted→suggest-park message).
- Contract test: matrix row 18 as written, plus the order assertion (`ORDER BY id`).

### I12 (oracle rules)

**B-L6 — P2 — I12** — verdict shopping (final_sweep5.py `X14c`): 5 oracle runs on one
half, verdicts `[refuted, unknown, refuted, unknown, refuted]` — no run cap, no
per-half monotonicity, every event retained. Combined with B-L1 (manual overwrite) the
operator picks whichever run they like. Fix: cap oracle runs per (lead, half) —
SPEC should pick N (2 or 3) and say "later events do not reopen the half; an
ambiguous half can only be escalated by a human set-half with fresh evidence".
- Contract test `test_oracle_run_cap`: 3rd oracle call on the same (lead, half) →
  BLOCKED `BLOCKED: lead L-1 trigger already has 2 oracle verdicts — shopping refused (I12)`.

**B-L23 — PASS — I12** — event-binding integrity verified (final_sweep5.py
`X14a` cross-half BLOCKED, final_sweep2.py `X14own` cross-lead BLOCKED, final_sweep3.py
mapping table: unknown→ambiguous only; refuted→refuted only; confirmed applies to
nothing). Feature validation: NaN timing BLOCKED (matrix row 10), missing keys BLOCKED,
boundary behavior exact (attack6.py X29b: 749.999ms→refuted, 750.0ms→unknown).
- Contract tests: rows 8/9/10 as written, plus
  `test_oracle_event_cannot_apply_cross_half` → BLOCKED
  `BLOCKED: lead L-1 oracle event #k says unknown for trigger — cannot apply ambiguous for impact`, and
  `test_oracle_event_cannot_apply_cross_lead`.

**B-L24 — P2 — I12** — negative/absurd features accepted (attack6.py X29):
`status=-1, timing_ms=-5.0, size=-3` → verdict `confirmed` (body delta). Negative timing
can never be `anomaly` (the `3*max(b,1)` guard saves it, but the SPEC's validator
("JSON parse gagal / key hilang / timing non-finite") omits sign/range checks, so
`size=-999999` and `status=-1` are legal inputs.
- Contract test `test_oracle_feature_ranges`: baseline/candidate with `status<0` or
  `size<0` or `timing_ms<0` → BLOCKED
  `BLOCKED: oracle feature file c.json: 'timing_ms' must be >= 0` (status/size same).

### I13 (claim gate L-binding) — **[vs landed code]**

**B-L9 — P2 — I13** — evidence-bar divergence + `#1` laundering survive (attack9b.py
X45/X44):
- `PROVEN[L-1]` passes (rc 0) while `PROVEN[F-1]` — the *same claim about the finding
  the lead minted* — vetoes (rc 2, `says 'theoretical'`). The L-bar (state=promoted) is
  strictly weaker than the F-bar (proven-live). An engine can launder a theoretical
  finding by binding it as a lead.
- `Lead #1 confirmed. PROVEN.` still rides an unrelated proven-live finding via `#1`
  nearest-id (rc 0) — the v0.3 laundering sentence survives the v0.4 gate when the
  subject is a lead.
- Fix (pick + document): either (a) L-claims pass only when the lead is promoted AND
  its `promoted_finding_id` is proven-live, or (b) keep (state=promoted) but say
  explicitly in bridge/README that an L-claim asserts *lead-level* truth (both halves
  proven), not exploitability. For `#1`: extend the unbound-veto rule — a bare marker
  whose nearest id is `#n` and the sentence mentions a lead (`lead #n` / `L-n`) vetoes
  with a message naming the ambiguity.
- Contract tests (test_claim_gate.py):
  - `test_l_claim_promoted_theoretical_finding` — pin the chosen bar; if (a): rc 2
    `BLOCKED: lead L-1 is promoted but its finding #1 is 'theoretical' — lead claims
    ride the finding's ladder (I13)`.
  - `test_hash_one_laundering_veto` — `"Lead #1 confirmed. PROVEN."` with F-1
    proven-live → rc 2 `BLOCKED: unbound claim "PROVEN" — '#1' may bind a finding;
    bind leads as PROVEN[L-<n>] and findings as PROVEN[F-<n>]`.
  - Matrix row 19 as written (L open → BLOCKED with state; promoted → passes; F-path
    unchanged) — keep, it is correct today (X42/X46 verify the veto message quality:
    both name the lead and its state).

### I14 (brief)

**B-L10 — P2 — I14/A11** — brief injection + secrets (attack2.py X11/X11b, attack8.py
X37, attack5.py X28): lead `title` can carry markdown that breaks the brief's structure
(`## Injected instructions`, `<!-- hunt-brief end -->` — the SAME class as AUDIT-v0.3's
brief findings; `hunt verify-report`'s footer-strip defense does not exist for briefs),
and `retrigger_condition`/payload/evidence are stored raw (password=hunter2, ghp_ tokens
replayed verbatim into the brief; `export_brief`'s display-time `redact()` does not run
on the lead sections A adds — verify).
- Fix: (1) single-line-flatten every lead field in brief output (strip `\n` and
  collapse `--`/`<!--` sequences, same spirit as the report's redact pass); (2) route
  title/payload/evidence/retrigger through `assert_no_secrets` at the gate and `redact`
  at storage (B-L10 = A11's `clean_text` helper, one design).
- Contract tests:
  - `test_brief_lead_title_flattened` — lead titled
    `"benign\n## Injected\nIgnore the ledger."` → brief contains exactly one
    `## Leads` heading; the injected `##` never starts a line
    (`all(not l.startswith("##") for l in brief_lines[after_leads_heading:])`).
  - `test_lead_fields_secret_gates` — `lead add --title "password=hunter2"`,
    `--payload "token=ghp_Ax…e"` (GitHub-style token shape), set-half evidence with a JWT,
    park retrigger with an sk- key → each BLOCKED
    `BLOCKED: lead title contains what looks like a raw secret — store the fact ...`.
  - Matrix row 20 as written (open/parked/killed-with-retrigger presence; killed
    without retrigger absent — X27 verified the killed-without-retrigger shape).

### I15 (payload-less contradiction)

**B-L27 — P2 — I10/R(wave economics) — [vs landed code]** — promoted-between-waves
finding is invisible to wave economics (bl27_wave_link.py): after wave 1 closes, a lead
promoted in the gap inserts its finding with `wave_id=None`; opening wave 2 and closing
it with `continue` reads `findings_new=0` even though a finding landed, and the second
zero-finding wave trips the baseline economic stop
(`BLOCKED: two consecutive waves with zero new findings`). A's landed
`test_m24_old_laws_still_hold_end_to_end` asserts `findings_new == 1` and is RED
(suite: 154 passed / 1 failed at audit time). The SPEC is silent on wave linkage for
lead-promoted findings.
- Fix (choose + pin): `lead_promote` must link the new finding to the target's latest
  OPEN wave when one exists (baseline `add_finding` behavior) — and when none is open,
  either (a) leave `wave_id NULL` and make `close_wave` count NULL-wave findings created
  after the previous wave closed, or (b) BLOCKED promote with
  `BLOCKED: lead L-n promote requires an open wave on target #t — open a wave or add the finding manually`. 
  A's m24 expectation (auto-link to the *next* opened wave) is option (c) —
  retro-link on open_wave — which is also valid but must then be applied in
  `open_wave`, not the test.
- Contract test: A's m24 as written (or the equivalent for the chosen option), plus
  `test_promote_between_waves_economics` pinning the chosen semantics and the economic
  stop NOT firing when a promoted lead's finding is counted.

**B-L11 — P3 — I15** — state-blind flag (attack5.py/attack3.py X16/X16b): the flag
fires on 8-day-old open payload-less leads (`!! lead L-1 still payload-less after 8
days`) but a single `set-half` moves the lead to `mutating` and out of scope forever,
still payload-less, still mutation-less. Also legacy `created_at` manipulation is
trivially possible raw (out of scope).
- Fix: flag `state IN ('open','mutating') AND payload empty` — a mutating lead without
  payload is *more* suspicious, not less.
- Contract test `test_payloadless_flag_covers_mutating`: payload-less lead, set-half
  once, age 8 days → flag present
  `!! lead L-1 still payload-less after 8 days`; fresh lead → absent.

**B-L25 — P2 — I15 (new contradiction for B-L3)** — promoted-lead divergence flag
(mutation count / verdict changes under a promoted snapshot via raw SQL). See B-L3's
contract. `find_contradictions` is display-only by design; this stays a flag, not a gate.

---

## 2. Contract tests grouped per invariant (acceptance checklist for cross-correction)

Every item = test name (A's suite) + key assertion + expected BLOCKED (or pass) line.
✓ = verified shielded in this audit's prototype; ⚠ = currently failing per finding.

| # | Invariant | Test | Key assertion / expected message | Status |
|---|-----------|------|----------------------------------|--------|
| 1 | I1 | `test_i1_impact_check_independent` | two distinct CHECK bodies in `sqlite_master`; raw bogus impact → CHECK failed | contract |
| 2 | I2 | `test_set_half_ambiguous_manual_blocked` | matrix row 7: `BLOCKED: --verdict ambiguous is set only by record_oracle_verdict (I2)` | ✓ |
| 3 | I2 | `test_set_half_proven_over_ambiguous_blocked` | `BLOCKED: lead L-1 trigger verdict was set by oracle — manual overwrite refused (I2)` | ⚠ B-L1 |
| 4 | I2 | `test_set_half_proven_over_oracle_refuted_blocked` | same shape, refuted case | ⚠ B-L1 |
| 5 | I2 | `test_oracle_event_single_use` | re-applying a consumed event → BLOCKED `already consumed` | ⚠ B-L1 |
| 6 | I2 | `test_oracle_confirmed_cannot_apply_direct` | `confirmed` event ≠ proven; `set-half --verdict proven` is the human step | ⚠ B-L2 |
| 7 | I3 | `test_add_without_payload_ok` | matrix row 1 | ✓ |
| 8 | I3 | `test_first_mutate_without_payload_blocked` | matrix row 3: `BLOCKED: lead L-1 payload required before the mutation loop` | ✓ |
| 9 | I3 | `test_set_half_payloadless_open_lead_documented` | pins BLOCKED-or-allowed for set-half on payload-less (with I15 consequence) | ⚠ B-L8 |
| 10 | I4 | `test_lead_ops_blocked_on_archived_target` | all six ops → `BLOCKED: lead L-1 — target #1 is archived — the hunt is closed` | ✓ |
| 11 | I4 | `test_parked_lead_refuses_mutate` / `_set_half` / `_repark` | `BLOCKED: lead L-1 is parked — <op> requires open\|mutating` | ✓ |
| 12 | I5 | `test_kill_one_refusal_autopark` | matrix row 11 + `dismissal_count==1` + `lead_kill_refused` detail `dismissal #1` | ✓ |
| 13 | I5 | `test_kill_two_refusals_ok` | matrix row 12 (clean kill, state killed) | ✓ |
| 14 | I5 | `test_kill_refusal_terminal_or_resumable` | pins the unpark semantics (B-L4) | ⚠ B-L4 |
| 15 | I6 | `test_park_retrigger_gate` | matrix row 14: missing / no ` :: ` / empty side → BLOCKED | ✓ |
| 16 | I6 | `test_kill_refusal_retrigger_gate` | refusal without `--retrigger` → BLOCKED (lazy kill refused) | ✓ |
| 17 | I7 | `test_mutate_repeat_blocked` | matrix row 5 + lead-named message | ✓ |
| 18 | I7 | `test_cross_lead_refuted_pair_warned` | same pair refuted on sibling lead → success + WARNING (or brief listing) | ⚠ B-L18 |
| 19 | I8 | `test_unknown_without_plan_blocked` | matrix row 6 | ✓ |
| 20 | I8 | `test_unknown_plan_creates_precondition` | matrix row 6b: precondition status=missing, `followup_precondition_id` set | ✓ |
| 21 | I8 | `test_unknown_plan_duplicate_blocked` | `BLOCKED: lead L-1 plan pair (param\|id=1) already exists as precondition #1` | ⚠ B-L5 (P1) |
| 22 | I8 | `test_unknown_plan_self_colonizing_value_blocked` | plan value == mutation new_value → BLOCKED `born tried` | ⚠ B-L5 |
| 23 | I9 | `test_provenance_counts_frozen_at_promote` | snapshot counts measured in the promote transaction; divergence flagged by contradictions | ⚠ B-L3 (P1) |
| 24 | I9 | `test_provenance_unchanged_after_edit` | matrix row 21 | ✓ |
| 25 | I9/I10 | `test_promote_uses_lead_content` | no title/payload kwargs on promote; finding title==lead.title, notes==lead.payload (redacted) | ⚠ B-L19 |
| 26 | I10 | `test_promote_requires_both_halves_proven` | ambiguous halves → `BLOCKED: lead L-1 promote requires both halves proven` | ✓ |
| 27 | I10 | `test_promote_klass_severity_gates` | matrix row 16 (via add_finding gates) | ✓ |
| 28 | I10 | `test_promote_with_zero_mutations_allowed_but_audited` | honesty flag `promoted with 0 recorded mutations` | ⚠ B-L20 |
| 29 | I11 | `test_next_deterministic_and_exhausted` | matrix row 18 + ORDER BY id | ✓ |
| 30 | I11 | `test_next_on_promoted_lead_is_noop` | `{'suggest': None, ...}` — no precondition id on a promoted lead | ⚠ B-L21 |
| 31 | I12 | `test_oracle_identical_refuted_event_saved` | matrix row 8 | ✓ |
| 32 | I12 | `test_oracle_timing_anomaly_unknown` / `_delta_body_confirmed` | matrix row 9 | ✓ |
| 33 | I12 | `test_oracle_bad_files_blocked` | matrix row 10 (corrupt JSON / missing key / NaN) | ✓ |
| 34 | I12 | `test_oracle_feature_ranges` | negative status/timing/size → BLOCKED | ⚠ B-L24 |
| 35 | I12 | `test_oracle_event_cannot_apply_cross_half` / `_cross_lead` | event binding to (lead, half) enforced | ✓ |
| 36 | I12 | `test_oracle_boundary_750ms` | 749.999→refuted, 750.0→unknown (pins `3*max` AND `>=500` semantics) | ✓ |
| 37 | I12 | `test_oracle_run_cap` | 3rd run same (lead,half) → BLOCKED `shopping refused (I12)` | ⚠ B-L6 |
| 38 | I13 | matrix row 19 (three-part) | L open → veto with state; promoted → pass; F-path unchanged | ✓ (landed code X42/X45/X46) |
| 39 | I13 | `test_l_claim_promoted_theoretical_finding` | pins L-bar vs F-bar (B-L9) | ⚠ B-L9 |
| 40 | I13 | `test_hash_one_laundering_veto` | `"Lead #1 confirmed. PROVEN."` → rc 2, ambiguity named | ⚠ B-L9 |
| 41 | I14 | `test_brief_lead_sections` | matrix row 20 (open+next / parked tripwire / killed-with-retrigger; promoted and killed-without absent) | ✓ |
| 42 | I14 | `test_brief_lead_title_flattened` | injected `##`/footer never break brief structure | ⚠ B-L10 |
| 43 | I14/A11 | `test_lead_fields_secret_gates` | secrets in title/payload/evidence/retrigger → BLOCKED at the gate | ⚠ B-L10 |
| 44 | I15 | `test_payloadless_flag_after_7_days` | 8-day open payload-less → flag; fresh → none | ✓ |
| 45 | I15 | `test_payloadless_flag_covers_mutating` | set-half does not hide the flag | ⚠ B-L11 |
| 46 | R | `test_promote_between_waves_economics` | promoted-in-gap finding counted (`findings_new==1`); economic stop not tripped | ⚠ B-L27 (A's m24 RED now) |
| 47 | legacy | matrix row 22 | ALTER guarded; add_finding green on migrated legacy db (X33 full CLI walk green) | ✓ |
| 48 | schema | matrix row 2 | `UNIQUE(target_id, number)` per target; cross-target same number OK | ✓ |
| 49 | schema | `test_lead_number_race_cas` | the WAL stale-snapshot race (X6) must stay held: second writer fails or retries; no duplicate (target,number) ever | ✓ (holds via UNIQUE; document the OperationalError path) |

---

## 3. Regression attacks on EXISTING behavior (§C)

**B-R1 — PASS (keep green)** — claim gate F-binding untouched (attack9b X45 F-path,
baseline `test_claim_gate.py` semantics): a proven-live finding still backs
`PROVEN[F-n]`; a theoretical one still vetoes. Contract: matrix row 19's third clause
plus the existing `test_proven_binds_nearest_id`-class tests must remain.

**B-R2 — PASS (keep green)** — `export_brief`/`export_report` (attack4.py X22):
unicode lead titles round-trip through both; the report does NOT mention leads/L-ids
(X31) — promoted leads surface as findings only, which is correct per §1's migration
design. Contract: `test_report_does_not_leak_lead_provenance` — report contains no
`lead_provenance`/`L-n` strings (pin, so A doesn't "helpfully" add them).

**B-R3 — PASS (keep green)** — `find_contradictions` existing flags unchanged with
leads present (prototype ran the full contradiction set against leads-bearing dbs; no
crashes). Contract: `test_contradictions_with_leads_present` — all v0.3 flags still
fire on a findings-heavy target that also has leads.

**B-R4 — PASS (keep green)** — phase gates + wave economics (attack4.py X20/X20b,
attack6.py X32): archived targets refuse lead ops (B-L13); `close_wave exhausted`
archive path still requires the lesson; a parked lead's tripwire is orphaned by the
economic stop (X32: `phase=archived; leads=[(1,'parked'),(2,'open')]`) — acceptable
(brief still shows the tripwire if the operator re-reads a dead target; document).
Contract: `test_parked_tripwire_survives_archive_in_brief` — brief on the archived
target still lists the parked lead's retrigger (I14 explicitly lists parked; archived
targets are not excluded by the SPEC).

**B-R5 — PASS (keep green)** — `hunt verify`/`challenge`/`poc run` on lead-minted
findings behave exactly as on hand-added findings (attack6.py X30: full ladder walk
green post-promote). Contract: matrix row 24 (full suite) covers.

**B-R6 — PASS (keep green)** — legacy DB without lead columns: guarded ALTER runs on
connect, `add_finding` green immediately after (attack6b.py X33: full CLI walk, exit 0
on every step). Contract: matrix row 22.

**B-R7 — P3 (watch)** — `export_brief` output is engine-consumed text; with leads the
brief gains *claimed-authority strings* (titles like "See PROVEN[F-1] below..."). The
baseline gate vetoes such a brief if pasted back (attack4.py X19: rc 2) — good, but it
means an operator echoing the brief into the engine can trip the gate on the *lead
author's* words. Mitigation is B-L10's flattening + bridge guidance ("do not paste
brief verbatim into engine output"). No code change required beyond B-L10.

**B-R8 — PASS (keep green)** — workspace lock/`hunt project` untouched by leads; CLI
smoke on a leads-migrated db ran green end-to-end (attack4.py X23).

**B-R9 — FINDING (see B-L27)** — wave economics + close_wave: the baseline
"two consecutive zero-finding waves → economic stop" now mis-fires when the only new
finding of a wave came from a lead promoted in the gap between waves
(wave_id=None at insert). Regression class: baseline gate made stricter-in-effect by
the new feature's missing linkage. Contract: row 46.

---

## 4. What was NOT audited

- The `hunt lead list`/CLI argparse surface (§3 echoes) — no CLI existed at audit time;
  echo-contract checks are named as contract tests only (`lead_list_echo`, X-note).
- `hunt oracle --finding N` (SPEC §3 offers the flag; §2 I12 defines only the lead path)
  — flag exists in the CLI surface but has no specified semantics: SPEC BUG (minor):
  either define it (oracle verdict on a finding? nonsense) or drop it. Noted as B-L26
  P3, HANYA-BACA-KODE/SPEC (reason: nothing to run against; the flag is underspecified
  on paper).
- Windows/CI behavior (per scope footer of AUDIT-v0.3; tests 23 apply).
- SOUL/bridge doctrine layers (covered by AUDIT-v0.3 B1/B3; not re-litigated).

---

## 5. Scratch & reproducibility

- `/tmp/audit-b/proto_leads.py` — the spec-faithful prototype (strawman; every finding
  cites the function it attacks).
- `/tmp/audit-b/attack1.py .. attack9b.py, final_sweep*.py` — experiments; each prints
  `[XN] PASS/FINDING` with the observed BLOCKED message or the bypass output.
- `/tmp/audit-b/harness.py` — fresh-db builder walking the real phase pipeline;
  `clean_scratch.py` — scratch cleaner.
- Repro one-liner: `cd /tmp/audit-b && python3 clean_scratch.py && python3 attack1.py`
  (then attack2..attack9b, final_sweep5.py).
- Repo untouched: only this file (`pr/AUDIT-CHECKLIST-leads.md`) was written; no
  commits/pushes; baseline suite re-verified green (126 passed) after all experiments.
