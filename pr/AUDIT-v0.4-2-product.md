# AUDIT-v0.4-2-product.md — Round-2 product/adversarial audit of HUNT-OS v0.4 LANDED

- Auditor: Auditor 2 (product/adversarial lens; Auditor 1 runs engineering/efficiency in
  parallel — index/WAL/commit-granularity/CLI-arg-internals/test-line-coverage are NOT
  attacked here and were not touched).
- Target: **landed state**, mirror head `168d83b3` line, suite baseline re-run at audit
  start: `pytest -q` → **162 passed** (enforcement 109 + leads 29 + claim_gate 22 ≙;
  suite untouched, still 162 after every experiment).
- Method: fresh reproduction only. Every claim below was executed against the LANDED
  code in `/tmp/audit-v04b/` (`attacks1.py` … `attacks4.py`, `friction.py`,
  throwaway sqlite DBs in the same dir). Nothing in `app/`, `bridge/`, `soul/`, CI, or
  the repo was modified; scratch + this report are the only writes.
- Round-1 findings re-verified against code, NOT against their old status. Statuses:
  FIXED / STILL-OPEN / MOOT, each with the fresh repro that decides it.
- Severity: P1 blocker / P2 should-fix / P3 polish. "PASS" rows = shields that held and
  must keep holding.

---

## 0. TL;DR

Round-1 backlog re-verified (15 distinct IDs): **5 FIXED** — every P1/P2 blocker the
round-1 arbitration tracked (B-L1-ambiguous, B-L3, B-L5, B-L7, B-L27) holds on landed
code — **8 STILL-OPEN** (B-L1's refuted half, B-L2, B-L6, B-L9 core, B-L10, B-L11,
B-L18, B-L21/B-L24 P3 residuals), **2 sub-claims MOOT** (B-L9's laundering paths do
not reproduce; controls prove the space-form and `#n` forms bind honestly).
New on landed code: **2× P1** (claim-gate L-bar/F-bar divergence after an overturn;
RoE default-deny bypass through the lead lane), **4× P2** (oracle baseline trust,
parked dead-end, B-L1 refuted-half hole, doctrine surfaces silent on v0.4),
**2× P3**. Doctrine: SOUL B1 repair is real; FRAMEWORK.md B2 repair is real but the
doc lags v0.3→v0.4; README's RoE promise is now factually false (R2-02).

| ID | Sev | One line |
|---|---|---|
| R2-01 | P1 | `PROVEN[L-n]` passes while the lead's finding is OVERTURNED — the L-bar is permanently weaker exactly where it matters most |
| R2-02 | P1 | Lead lane hardcodes `action="read"` → a mutate attack promoted via a lead bypasses the RoE default-deny gate (direct contrast proven) |
| R2-03 | P2 | Oracle baseline is an unbound operator-supplied JSON file: no capture step, no binding to lead/target, unlimited re-runs (B-L6) → verdict engineering is trivial |
| R2-04 | P2 | Parked is a polite graveyard: no unpark/reopen exists; the tripwire promise ("wakes the lead") is unenforceable in-process |
| R2-05 | P2 | B-L1 patch is half-done: manual `proven` over an oracle-**refuted** half is still accepted (docstring promises the opposite) |
| R2-06 | P2 | B-L10: secrets gate unwired on lead evidence/precondition-description/mutation-evidence/retrigger; brief echoes non-token-shape secrets verbatim |
| R2-07 | P2 | v0.4 is invisible in README, QUICKSTART, FRAMEWORK.md, and HUNT-BRIDGE — the engine has no contract for the lead/oracle pipeline |
| R2-08 | P3 | B-L11 confirmed with sharper repro: park silences the 7-day payload-less flag forever |
| R2-09 | P3 | Report submittability (M2 gap): promoted findings render no trigger/impact evidence; no platform format exists |

---

## 1. Re-verification of round-1 findings (against LANDED code)

Repro: `cd /root/Hunter/app && PYTHONPATH=src python3 /tmp/audit-v04b/attacks1.py`
(+ `attacks2.py` for spot-checks). Fresh DBs per finding; raw output cited verbatim.

| Round-1 ID | Sev (r1) | Status | Fresh evidence (this audit) |
|---|---|---|---|
| B-L1 (manual proven over oracle-ambiguous) | P1 | **FIXED (half)** | `_set_lead_half` blocks it: `BLOCKED: lead L-1 impact verdict was set by the oracle (ambiguous) — manual overwrite to 'proven' refused (I2/B-L1)`. **BUT** the guard only fires for `current == "ambiguous"` → the refuted branch is open → see R2-05. |
| B-L1b (manual proven over oracle-refuted) | — | **STILL-OPEN → R2-05 (P2)** | `set_lead_half(trigger,'proven')` on an oracle-refuted half ACCEPTED, oracle event left dangling. Docstring says "the manual path must start from 'untraced'" — code disagrees with its own doc. |
| B-L3 (promote snapshot) | P1 | **FIXED (adequate)** | Snapshot frozen at promote in one transaction (`mutations=1, preconditions_present=0, parked_days=0` recorded); post-promote mutate BLOCKED (`lead L-1 is promoted — the mutation loop runs on open or mutating leads`); snapshot can't drift. Contract test from round-1 satisfied in spirit. |
| B-L5 (raw IntegrityError on dup `--plan`) | P1 | **FIXED** | `BLOCKED: lead L-1 duplicate precondition 'role|user'` on both the add path and the `--plan` birth path (`plan precondition 'role|admin' already exists — an unknown must give birth to a NEW pair`). Named handler, no traceback. |
| B-L6 (oracle shopping, no cap) | P2 | **STILL-OPEN → folded into R2-03** | 5 consecutive `record_oracle_verdict` runs on ONE (lead, half), verdict flipping run-to-run, all 5 events retained, zero resistance. |
| B-L7 (promote title/payload override) | P2 | **FIXED** | `promote_lead(conn, lead_id, klass, severity)` — no title/payload params; `promote_lead(..., title="EVIL")` → TypeError. Finding born with the lead's own content: `finding #1 title='LeadBornTitle' notes='promoted from lead L-1 (payload: orig payload)'`. Content pinned to the lead row. |
| B-L9 (L-bar vs F-bar divergence; laundering) | P2 | **SPLIT: sub-claims MOOT, core STILL-OPEN → R2-01 (P1)** | MOOT: `PROVEN L-1` space form IS lead-bound (control: unpromoted lead → rc=2 — no bypass); `Lead #1 confirmed. PROVEN.` binds the finding and is VETOED (rc=2, theoretical). Core divergence lives and is worse than round-1 stated: see R2-01. |
| B-L10 (secrets in lead free-text) | P2 | **STILL-OPEN → R2-06 (P2)** | `add_lead` payload gate holds (`BLOCKED: payload contains what looks like a raw secret`), but set-half evidence, precondition description, mutation evidence, and park retrigger all store token-shaped secrets VERBATIM. Brief echo: token-shapes get display-redacted, non-token-shapes echo verbatim (R2-06 for the sharp version). |
| B-L11 (state-blind 7-day flag) | P3 | **STILL-OPEN → R2-08 (P3, sharper)** | set-half does NOT move a payload-less lead out of `open` (state stays `open` — round-1's `mutating` path is actually closed); but **park** does: 8-day-old payload-less lead flagged while open, `flags=[]` the moment it parks, permanently (parked has no exit → R2-04 compounds it). |
| B-L27 (gap promote → wave economics) | P2 | **FIXED (both directions verified)** | Gap promote → `wave_id=None`; next `open_wave` retro-links it (`finding wave_id=2 == new wave 2`). New twist this audit: an **overturned** gap finding is correctly NOT re-linked to wave 3 (stays in the wave that counted it) — economic-stop misfire does not occur (wave-3 `continue` accepted because wave 2 counted the promoted finding). Belt + suspenders hold. |
| B-L2 (oracle `confirmed` maps to what?) | P2 | **STILL-OPEN (behavior decided, contract not)** | Oracle `confirmed` sets the half `proven` DIRECTLY (no human step): `verdict=confirmed, half now=proven`. That is a defensible reading of I12, but it means the oracle alone can mint promote-fuel — combined with R2-03 this is the laundering core. Round-1's "advice only" contract was not adopted; decide and pin it. |
| B-L18 (anti-repeat is per-lead) | P2 | **STILL-OPEN (likely by design — needs a decision)** | Same `(role → admin)` accepted on lead B after lead A. Cross-lead dedup absent; fine within one target, wasteful across 30 leads on it. P3-grade; pin the decision either way. |
| B-L21 (`lead next` on promoted lead) | P2 | **STILL-OPEN (P3-grade)** | `next_mutation` on a PROMOTED lead returns an actionable step: `{'precondition_id': 1, 'variable': 'role', 'value': 'user', ...}`. The brief correctly hides promoted leads; the command does not refuse. Cosmetic + honesty-of-output issue. |
| B-L24 (absurd feature values) | P2 | **STILL-OPEN (P3-grade)** | `status=-5, size=-1, timing_ms=10**12` accepted → `unknown`. Harmless alone; feeds the anomaly path of R2-03. Bound the ranges at `_read_oracle_feature`. |
| B-L4/B-L8 (park/kill design traps) | P3 | superseded by R2-04 | The one-dismissal stall and payload-less kill-refusal behave as round-1 described; the real product hole is that parked has no exit at all. |

**Round-1 doctrine items:**

| ID | Status | Evidence |
|---|---|---|
| B1 (SOUL commands what enforcement punishes) | **FIXED** | `soul/SOUL.md:151` — `## HUNTING AMENDMENTS (these override the protocols above, inside a hunt)` exists, 4 amendments: no-fabrication carve-out, "BLOCKED is the sovereign's voice", reports-from-ledger-only, claims-carry-ids. Exactly the round-1 fix shape. |
| B2 (FRAMEWORK.md teaches v0.1) | **FIXED, then reopened one version behind** | FRAMEWORK.md now teaches v0.3 truthfully (poc-run ladder, artifact table matches CLI, db-as-spine). But it is silent on leads/oracle/L-binding — L4 says "v0.3: the db IS the spine" on a v0.4 repo. New drift is R2-07, one minor version instead of two majors. |
| B7 (ID/EN language mix, no policy) | **STILL-OPEN (P3)** | FRAMEWORK.md still mixes (`prinsip permanen`, `bahan. Rantai = senjata`) against all-EN README/QUICKSTART. No policy statement anywhere. Cheap fix: one line in README ("docs: EN norm, FRAMEWORK may gloss in ID"). |

---

## 2. New findings on LANDED v0.4 (nobody audited these yet)

### R2-01 — P1 — The L-bar is permanently weaker than the F-bar exactly after an overturn

**Attack.** Lead L-1 promoted → finding #1 (theoretical). Adversary overturns the
finding (`hunt finding overturn`-equivalent: `db.overturn_finding`). The lead's state
is still `promoted` — promote is a one-way terminal state with no demotion path.

**Repro (landed code, real gate subprocess, `/tmp/audit-v04b/attacks4.py`):**
```
setup: lead state=promoted, promoted_finding_id=1, finding ladder=theoretical

-- pre-overturn --
PROVEN[L-1] -> rc=0
PROVEN[F-1] -> rc=2

-- post-overturn: finding ladder=overturned (overturned_by='adversary disproved
   the trigger end-to-end'), lead state=promoted --
PROVEN[L-1] -> rc=0  'claim gate: no unbacked claims'
PROVEN[F-1] -> rc=2  "BLOCKED: engine claimed PROVEN for finding #1 but the database
                      says 'overturned' — claims must be backed by proven-live rows"
```
The gate (`bridge/claim_gate.py::vet`) judges lead-bound claims by **`leads.state ==
'promoted'`** and nothing else: no check of `promoted_finding_id`'s `ladder_status`,
no check that the finding still exists. Meanwhile the F-bar on the same evidence
correctly refuses with the exact ladder value (`'overturned'`). Two instances of the
divergence, ordered by severity:
1. **Finding theoretical (round-1's original claim):** `PROVEN[L-1]` passes while
   `PROVEN[F-1]` vetoes — arguably the intended design (promote IS the lead's bar;
   the finding may still be climbing), grade: document deliberately.
2. **Finding OVERTURNED (this audit):** `PROVEN[L-1]` STILL passes while `PROVEN[F-1]`
   vetoes saying `'overturned'`. The system's own disprove-procedure — doctrine law #3,
   "overturn fast" — does not propagate to the lead's claim surface. **Laundering
   through the precise case the evidence ladder exists for. P1.**

**Why the controls matter (no overclaim).** Three controls ran clean: `PROVEN L-1`
(space form, unpromoted lead) → rc=2; `PROVEN[L-1]` unpromoted → rc=2; both-halves-
proven-but-not-promoted → rc=2. The promote bar is real. The hole is only the
*post-promote* half of the bar.

**Fix design (in-process, small).**
1. `vet()`: a lead-bound claim checks `leads.state='promoted'` AND
   `(SELECT ladder_status FROM findings WHERE id = leads.promoted_finding_id)
   IN ('in-code','proven-live')` — an overturned finding must veto its lead's claims
   (message: `BLOCKED: ... the finding L-n promoted into is 'overturned'`).
2. When `promote_finding`/overturn flips a finding that has `lead_id NOT NULL`,
   the lead's claim surface changes — that is fine as long as the gate reads it
   live (it does, read-only, per turn).
**Test contract:** `test_l_claim_vetoed_when_promoted_finding_overturned` — promote
lead L-1 → overturn its finding → `PROVEN[L-1] x` → exit 2 with the message above
pinned verbatim; `test_l_claim_passes_when_promoted_finding_proven_live` — climb the
finding to proven-live → same claim → exit 0.

### R2-02 — P1 — RoE default-deny bypassed through the lead lane

**Attack.** `promote_lead` inserts the finding via `add_finding(..., action="read")`
— hardcoded (`db.py:1301-1305`). The RoE gate in `promote_finding` fires only for
`action == 'mutate'` (`db.py:695-703`). So a lead whose payload describes a pure
state-changing attack (the leads feature's whole point — concrete hypothesis)
promotes into a `read` finding and sails through proven-live with **no RoE row at
all**, on the default-deny principle the README advertises.

**Repro (landed code, same attack, two lanes):**
```
[N7a] mutate-attack lead ("POST /api/admin/users/1337 {role: admin} — full account
      takeover") promoted -> finding #1 action='read'
[N7b] that finding climbed to ladder=proven-live with NO RoE row (default-deny)
[N7c] the SAME attack via finding add --action mutate is BLOCKED at proven-live:
      "BLOCKED: mutate finding cannot reach proven-live outside the rules of
      engagement — hunt target roe 2 --actions ..."
```
HUNT-BRIDGE even teaches the correct behavior (`Mutate outside RoE → stop ...
default-deny`) — the lead lane silently teaches the opposite.

**Impact.** The authorization gate is lane-dependent. An operator (or a sloppy
engine) that records mutations through leads — the encouraged workflow post-v0.4 —
never hits the gate. README's claim "a mutate finding cannot reach proven-live
outside the authorized scope" is now **factually false** on landed code.

**Fix design.** `promote_lead` must not guess: derive `action` from the lead's own
content or make it explicit. Cheapest honest fix: add `--action read|mutate` to
`hunt lead promote` (default `read` for back-compat is WRONG here — default should
follow the payload, or better: BLOCKED without an explicit choice when the RoE
question is live, i.e. whenever the target has no RoE row or the payload mentions
write verbs is undecidable — so: explicit flag, logged in `lead_promoted` event,
carried into `add_finding`). Then the existing RoE gate does its job unchanged.
**Test contract:** `test_promote_lead_mutate_action_requires_roe` — lead promoted
with `--action mutate` on a target with no RoE → `promote_finding` to proven-live →
BLOCKED message identical to the direct-lane one; `test_promote_lead_read_action_unaffected`
— `--action read` path green; `test_promote_logs_action` — `lead_promoted` event
detail contains `action=mutate`.

### R2-03 — P2 — Oracle baseline trust: the verdict is only as honest as an unbound JSON file (design split: in-process vs OPEN-PROBLEM)

**Attack surface (all verified on landed code):**
1. **No capture step.** `baseline`/`candidate` are hand-carried JSON files; the CLI
   has no command that observes a live target (grep: no capture/observe anywhere in
   `cli/main.py`). Whoever writes `baseline.json` decides the verdict.
2. **No binding.** `record_oracle_verdict(conn, lead_id, half, baseline, candidate)`
   accepts any dicts. A baseline claiming `status=200` minted `verdict=confirmed →
   half=proven` with zero contact with any live system; the only receipt is event
   `#9` whose "baseline" is the operator's own fiction.
3. **Shopping composes (B-L6).** Unlimited re-runs per (lead, half); verdicts flip
   run-to-run; all events retained, none authoritative; the last writer wins the
   half. Pick-file + re-run = verdict engineering.
4. **Oracle `confirmed` mints `proven` directly** (B-L2 status above) — no human
   step between "operator-supplied features" and promote-fuel.

**What can be fixed in-process (cheap, deterministic):**
- **Cap runs per (lead, half)** (e.g. 3): 4th run → `BLOCKED: L-n trigger already has
  3 oracle observations — park with a new retrigger or refute manually from untraced`.
  Test: `test_oracle_run_cap`.
- **Baseline immutability across re-runs**: store the first baseline's canonical JSON
  digest on the (lead, half) (one column or derived from the first oracle event);
  a later run with a different baseline → `BLOCKED: baseline changed since observation
  #k — a new hypothesis needs a new lead` (this kills pick-the-file: the FIRST
  baseline pins the comparison). Test: `test_baseline_frozen_after_first_run`.
- **Verdict monotonicity for manual overwrite**: manual `refuted` may always
  overwrite; manual `proven` over `refuted` is R2-05's hole — closing R2-05 also
  closes the last shopping lane.
- **Feature sanity**: `status` ∈ [100,599], `size ≥ 0`, `timing_ms` ≤ 60_000 (B-L24).
  Test: `test_oracle_feature_ranges`.

**What must become a NEW OPEN-PROBLEM (P10): "the oracle's baseline is
self-attested."** Binding a baseline to reality requires *observing the target*,
which the stdlib app deliberately does not do (that is M1's poc-run shape applied to
the oracle: `hunt oracle capture --lead N --half trigger --url ...` recording
status/timing/sha as a db-stamped event). Design it as M1-adjacent roadmap work, not
as a v0.4 patch. Until then, say so in docs — the honest label is "deterministic
*verdict rule*, self-attested *inputs*", not "observation oracle" unqualified.

### R2-04 — P2 — Parked is a one-way door: the tripwire can never wake anything

**Verified.** State writers on `leads` across the whole codebase:
`{killed, mutating, parked, promoted}` — **no writer ever returns a parked lead to
open/mutating**; the CLI has no `unpark`/`reopen`/`wake`; `_set_lead_half`,
`mutate_lead`, `promote_lead`, `park_lead`, `kill_lead` all BLOCKED on `parked`.
Post-park freeze integrity itself is good (PASS: set-half/re-park/promote all
refused). But the docstring and the brief promise a wake: "Parked leads stay in the
brief as tripwires — the observable, when checked, **wakes the lead**"
(`park_lead` docstring) and the brief prints `tripwire: ...` rows. Nothing can wake
them: BF's chain-pool rescan has no equivalent here; the human reading the brief
must re-add the lead from scratch (losing number, history, preconditions, dismissal
count) or raw-SQL the state (forging the ledger, which the project's own doctrine
forbids).

**Impact (product).** The 7-day flag escape (R2-08) + no exit = the system quietly
trains operators to *kill* leads they should keep: parking is terminal, so the
rational move under deadline pressure is a lazy kill or a payload-less park that
vanishes from all honesty flags. The Lead Ledger's core value (BF's crown — cheap
resumable observations) is structurally absent on the resume side.

**Fix design (S).** `hunt lead reopen --lead N --note "retrigger observed: ..."`:
state `parked|killed` → `open`, requires non-empty note, logs
`lead_reopened` (kind already anticipated by `_build_provenance`'s
`lead_state_reset` handler — the snapshot math even has a dead branch waiting for
this event kind; today nothing emits it). Killed-with-retrigger may reopen the same
way (the brief already shows those tripwires). **Test contract:**
`test_reopen_parked_lead_returns_to_open` (state, event kind `lead_reopened`,
`dismissal_count` preserved, `next_mutation` alive again);
`test_reopen_requires_note`; `test_reopen_promoted_blocked` (promoted stays
terminal); `test_provenance_parked_days_counts_reopen_pair` (reopen event resets the
parked-days accumulation exactly as the dead branch expects).

### R2-05 — P2 — B-L1 is half-landed: manual `proven` over an oracle-REFUTED half is accepted

**Repro (landed code):**
```
oracle run (identical features) -> verdict=refuted, half=trigger, event #k stored
set_lead_half(trigger, 'proven', 'my own manual evidence') -> ACCEPTED
```
The B-L1 patch guards `current == "ambiguous"` only
(`db.py:882-889`), while the docstring written with the same patch promises: "The
manual path must start from 'untraced'" (db.py:877-881) and the arbiter's fix note
says "or refute it with the oracle first". Result: an oracle refutation can be
overwritten by hand into promote-fuel — the exact laundering shape B-L1 described,
one verdict-value over. (The ambiguous case — the one the arbiter reproduced — is
genuinely closed; severity drops P1→P2 accordingly, and round-1's `X5` experiment is
reproduced verbatim on landed code.)

**Fix design.** In `_set_lead_half`'s manual branch, also refuse `proven` when
`current == "refuted"` AND the half's latest verdict was oracle-installed. The
round-1 design already said it precisely: check the half carries an oracle event
(the `lead_mutations.oracle_event_id` receipt or the last `oracle_verdict` event for
that half) — if yes and verdict-incoming is `proven` by hand → `BLOCKED: ... verdict
was set by the oracle (refuted) — manual overwrite to 'proven' refused (I2/B-L1):
rerun the oracle, or refute it with the oracle first`. Keep manual `refuted` legal
over anything (humans may always disprove). **Test contract:**
`test_set_half_proven_over_oracle_refuted_blocked` (round-1's own contract text,
still unwritten in the suite) + `test_manual_refuted_over_oracle_proven_allowed`.

### R2-06 — P2 — B-L10: the secrets gate covers `payload` only; the other four lead free-text fields store raw, and the brief leaks the exotic shapes

**Verified (landed code):**
| Field | Storage gate? | Evidence |
|---|---|---|
| `payload` (add/set) | YES | `BLOCKED: payload contains what looks like a raw secret` |
| `set-half` evidence | **NO** | stored verbatim: `...evidence leaked ghp_A1…l2` |
| precondition `description` | **NO** | stored verbatim |
| mutation `evidence` | **NO** | stored verbatim |
| park/kill `retrigger` | **NO** | stored verbatim: `deploy log :: ghp_A1…l2 in env` |
| brief echo | **display-only redact** | token-shaped secrets are redacted on display (`redact()` catches `ghp_…`), but a non-token-shape secret is stored AND echoed verbatim: park retrigger `rotated key lands :: api key 9f8e7d6c5b4a3210fedcba9876543210` → brief prints it character-for-character (repro `bl10g.db`, `B-L10g-brief-echo-hex`).

So round-1's "brief echoes retrigger verbatim" is **conditionally true**: known
shapes are display-redacted (good), everything else is not — and the storage layer
never had a gate at all. The brief is the one artifact that leaves the machine
(pasted to the operator/partner), so the display-layer-only defense is the weak one.

**Fix design.** One helper, five call sites: `assert_no_secrets` +
`redact()` on `set_lead_half` evidence, `add_lead_precondition` value/description,
`mutate_lead` evidence, `_validate_retrigger` (both park and kill-refusal paths) —
the exact A11 `clean_text` shape round-1 proposed. The payload gate is the template;
copy it, don't invent. **Test contract:** `test_lead_free_text_secret_gates` —
parametrized over the five fields, each raw-secret input → `BLOCKED: <field>
contains what looks like a raw secret` (message pinned), plus
`test_brief_never_echoes_secrets` with a non-token-shape secret through park →
brief.

### R2-07 — P2 — v0.4 is invisible in every doctrine surface (README, QUICKSTART, FRAMEWORK.md, HUNT-BRIDGE)

**Verified.** Grep across the four surfaces: `lead` appears in HUNT-BRIDGE only as
the English word ("a lead looks promising"), never as `hunt lead ...`; `oracle`
appears zero times. Concretely:
- **README** ("What this is"): six bullets, none is the leads/oracle pipeline; the
  closest claim ("Honest labels", "Guarded mouth") predates it. The repo's headline
  feature of the release is absent from its front page.
- **QUICKSTART** ("a hunt in 10 minutes"): walks target→finding→ladder→report with
  zero lead/oracle steps. A new operator completes the quickstart having never met
  the feature.
- **FRAMEWORK.md**: L2 pipeline table has no lead lane; L4 still says "v0.3".
- **HUNT-BRIDGE** (injected EVERY session — this is the engine's constitution): the
  "EVERY RECORD GOES THROUGH THE GATE" list has no `hunt lead add|mutate|promote`,
  no `hunt oracle`, and the CLAIMS section teaches only `PROVEN[F-<n>]` — the engine
  is structurally steered to the v0.3 finding lane and is never told the L-binding
  exists. Combined with R2-02, the engine's default path is the un-gated one.

**Fix design (docs-only, S).** README: add the leads/oracle bullet + one line on the
L-binding. QUICKSTART: §4.5 "the observation lane" (5 commands: add → next → mutate
→ set-half → promote + one oracle call). FRAMEWORK.md: L2 row for leads, L4 "v0.4".
HUNT-BRIDGE: add the six lead commands to the gate list and one CLAIMS line
("`PROVEN[L-<n>]` binds the lead; the gate judges it by the lead's state"). **Test
contract:** CI structure gate can pin `grep -c 'hunt lead' soul/bridge/HUNT-BRIDGE.md`
≥ 5 (the CI already validates framework contract lines — same mechanism).

### R2-08 — P3 — B-L11 sharpened: park is what silences the 7-day payload-less flag

Round-1's mechanism (set-half → `mutating`) did not reproduce on landed code — a
payload-less lead stays `open` through set-half (state promotion happens only via
`mutate_lead`, which requires a payload). The live escape is **park**:
```
payload-less lead aged 8d: flag while open=['!! lead L-1 still payload-less after 8 days']
after park (still payload-less, 0 mutations): flags=[]
```
Permanent, because parked has no exit (R2-04). Fix rides along: `lead_contradictions`
should flag `state='parked' AND payload IS NULL` leads too (the tripwire row already
prints in the brief; the honesty flag should not be state-blind), or R2-04's reopen
makes the flag escapable-but-honest. **Test contract:**
`test_payloadless_parked_lead_still_flagged`.

### R2-09 — P3 — Report submittability of promoted findings (the M2 gap, now concrete)

`export_report` renders a promoted finding as:
```
### F-1 [CRITICAL] Privilege escalation via role write
- class: Access | ladder: proven-live
- evidence: ev-live: admin panel reachable
- poc: /tmp/audit-v04b/n7_poc2.py
- notes: promoted from lead L-1 (payload: POST /api/admin/users/1337 {role: admin} — ...)
```
The lead's actual trigger/impact evidence — the two sentences that *justify* the
finding — are in `lead_{trigger,impact}_evidence` and render nowhere; the payload is
buried inside `notes` prose; there is no H1/Bugcrowd shape (M2 unstarted). For
Phase-A revenue the report IS the product; today a promoted finding submits worse
than a hand-written one. Fix belongs to M2 (roadmap §5), not a v0.4 patch: render a
`lead provenance` block (payload + both half-evidences + snapshot counts) and target
the M2 format mapping at it.

---

## 3. Doctrine & claims coherence (verdict per surface)

| Surface | Verdict | Detail |
|---|---|---|
| `soul/SOUL.md` | **CLEAN (B1 repair real)** | HUNTING AMENDMENTS block present, 4 amendments, exactly the round-1 shape; CI gates identity. No overclaim found. |
| `docs/FRAMEWORK.md` | **LAGS (P3)** | Truthful for v0.3; silent on v0.4 (R2-07). B2's v0.1 drift is genuinely repaired — artifact table now matches the CLI. |
| `README.md` | **ONE FALSE CLAIM (via R2-02)** | "a mutate finding cannot reach proven-live outside the authorized scope" — false through the lead lane (repro R2-02). Everything else checked: no overclaim; the layout/CI descriptions match reality (162 tests, dual-OS, stdlib-only). |
| `QUICKSTART.md` | **INCOMPLETE, not false** | Every command shown runs (verified in the friction walkthrough); the feature is just missing (R2-07). |
| `soul/bridge/HUNT-BRIDGE.md` | **INCOMPLETE (P2, part of R2-07)** | Engine constitution has no lead/oracle contract and teaches only F-binding claims. |
| Language policy (B7) | **STILL-OPEN (P3)** | Unchanged; one-line fix proposed in §1. |
| `pr/OPEN-PROBLEMS.md` | **STALE (P3)** | P1–P9 do not include the v0.4 self-attestation class; R2-03's OPEN-PROBLEM (oracle baseline trust) belongs there — the repo's own rule is "keep this pattern in every release". |

---

## 4. Friction of the hunt process (product lens)

Measured: fresh DB, CLI only, lead from `add` to `promoted`
(`/tmp/audit-v04b/friction.py`, transcript preserved):

**6 CLI calls** for the happy path (add → next → mutate --resolve → set-half ×2 →
promote), **+2 per loop iteration** (next + mutate), plus one-shot setup (target/score/
roe/2×artifact/2×phase ≈ 8 calls, once per target). The loop shape is honest work,
not bureaucracy — the per-step discipline is the product. The skip-magnets are
elsewhere:

1. **`--lead N` retyped on every call** (and `--target T` again inside add/list). In
   a bound workspace the target is known; in a session the lead is the working
   object. Cheap win: `hunt lead` (no args) = "list my open leads + each one's next
   mutation" (the brief already computes this — `export_brief` calls
   `next_mutation` per live lead).
2. **Promote-readiness is invisible.** The brief shows open leads with `next: ...`
   but never says "both halves proven — promote-ready" (verified: the friction run's
   promoted lead vanished from the brief the moment it promoted, and nothing
   surfaced readiness before). `hunt lead list` shows verdicts but buries readiness
   in a wide table. One `ready:` annotation in the brief/list = the operator never
   re-derives state.
3. **Kill-refusal retype**: refusal demands `--retrigger` inline (good gate), but the
   operator learns it only by failing (rc=2 with a long message). Fine.
4. **Parked has no next action** (R2-04): the brief prints a tripwire the system
   itself cannot act on. After R2-04's `reopen`, the tripwire row should end with
   `— wake: hunt lead reopen --lead N`.
5. **Brief round-readiness is otherwise good**: lessons, contradictions, wave
   history, ladder, taxonomy, leads — one call opens a round honestly. Keep it the
   single entry point.

**One-command opportunities (ranked):** `hunt lead` (working-set view); `lead ready`
annotation; `hunt lead reopen` (R2-04). Do NOT collapse the loop itself — next/
mutate per step is the discipline the framework sells.

---

## 5. Roadmap leverage after v0.4 (economic ranking, M2–M9 from pr/AUDIT-v0.3.md)

Context: M1 (`hunt poc run`) landed; leads+oracle landed; the ledger now generates
evidence-dense events that nothing aggregates and nothing formats for submission.

1. **M2 — platform-ready report export** (M). The deliverable is what pays; Phase A
   revenue is the whole point of the staging. v0.4 made the ledger *richer* (lead
   provenance, half-evidences, oracle events) and the report *relatively poorer*
   (R2-09: none of it renders). Every hunt from here on re-pays the re-typing tax M2
   deletes. Highest value-per-effort because the hard part (the enforced ledger) is
   already built — M2 is formatting over truth.
2. **M3 — explorer/API cross-check** (M). Post-v0.4 the repo's largest honesty gap
   is self-attested inputs (OPEN-PROBLEMS P1/P8 AND the new oracle-baseline class,
   R2-03). M3's shape — fetch a canonical receipt, store it, diff against the claim —
   is the same shape an `oracle capture` needs. Building M3 buys the oracle-trust
   fix design for free. Second only to M2 because M2 is revenue and M3 is trust, and
   Phase A runs on revenue.
3. **M4 — `hunt stats`** (S). The events table now timestamps leads (add →
   mutations → verdicts → promote) — time-to-promote, lane yield, overturn rate are
   one query file away. Cheapest calibration of the economic stop on the board.
4. Non-roadmap S-items that outrank M5–M9 on leverage: **`hunt lead reopen`**
   (R2-04 — unblocks the Lead Ledger's core promise), **oracle cap + baseline
   freeze** (R2-03 in-process half), **doctrine pass** (R2-07 — the feature nobody
   reads about cannot compound).
5. M6 (lesson search), M8 (hook pack), M5 (dedup), M7 (CVSS), M9 (signing) keep
   their v0.3 relative order; M8 rises if/when the platform pitch starts (the gate
   as distribution), M9 is polish until a partner deliverable is due.

---

## 6. Verified-clean shields (must keep holding; test contracts already pinned)

- B-L1 ambiguous-overwrite BLOCKED (regression pin `test_bl1_*` holds).
- B-L27 retro-link both directions; overturned gap findings correctly stay in their
  counting wave; no economic-stop misfire (twist test this audit).
- B-L5 named BLOCKED on both duplicate paths.
- B-L7 promote content pinned to the lead row (no override surface).
- Claim-gate controls: unpromoted lead claims vetoed in bracket AND space form;
  both-halves-proven-but-not-promoted vetoed; `PROVEN L-n` never launders into
  finding n (rc=2); `Lead #n ... PROVEN.` binds the finding honestly.
- Promoted findings are born `theoretical` and the full ladder (poc-run, distinct
  PoC sha, verifier, adversary) applies unchanged — m24 independently re-verified
  (N5a/N5b: `BLOCKED: this PoC has never been executed`).
- Kill-refusal demands a retrigger through the park gate (auto-park not lazier than
  park).
- Anti-starvation: `unknown` requires `--plan`, plan must birth a NEW
  (variable,value) pair, redeclare BLOCKED; exhausted loop returns `None` +
  "consider park" suggestion (information, not error). next_mutation determinism:
  first-missing-by-id, never-tried filter — deterministic as specified.
- `_build_provenance` parked-days math already anticipates a `lead_state_reset` /
  reopen event kind — R2-04's fix completes a half-built seam, it does not fight one.

---

## 7. Repro index

```
cd /root/Hunter/app
PYTHONPATH=src python3 /tmp/audit-v04b/attacks1.py   # re-verification + N1/N3/N4/N5/N6 + gate subprocess
PYTHONPATH=src python3 /tmp/audit-v04b/attacks2.py   # controls + B-L2/3/18/21/24 spot-checks
PYTHONPATH=src python3 /tmp/audit-v04b/attacks3.py   # R2-02 (RoE bypass, contrast lanes) + R2-09 report render
PYTHONPATH=src python3 /tmp/audit-v04b/attacks4.py   # R2-01 definitive: promote -> overturn -> gate L vs F
python3 /tmp/audit-v04b/friction.py                  # §4 friction transcript (fresh DB)
python3 -m pytest -q                                 # 162 passed — unchanged before/after audit
```
Suite before audit: 162 passed. Suite after all experiments: 162 passed.
Repo files modified by this audit: **none** (report + scratch only).
