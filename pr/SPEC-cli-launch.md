# SPEC — CLI Launch: HUNT-OS as the operator for every harness

Status: FINAL for builder handoff (operator 2026-09-07).
Implementer: the builder this document is given to.
Reviewer: adversarial auditor against THIS spec, not against conversation memory.

This file is the oral-free contract. If chat and this file disagree, this file wins.

---

## 0. What "launch" means

HUNT-OS in this repo is an **interactive hunt CLI**. It occupies the **operator position** for every agent harness (Hermes, Claude Code, ZCode, generic): the human or the engine records only through `hunt`, the ledger is the only memory, the claim gate is the mouth.

A native HUNT harness (agent runtime: context, model calls, tools, sandbox, subagents) is **not this launch**. It is the next product, in a **sibling repo** (plans.md P10). Do not put a runner in this tree.

The accurate sentence after this spec ships:

> HUNT-OS is a stdlib hunt CLI. Any operator, and any harness that loads the hunt layer, records only through `hunt`. The claim gate is wired, not DIY. `hunt next` recommends the next command and exposes judgment branches honestly. `hunt doctor` tells the truth. Conductor `hunt run` stays experimental (mock).

The forbidden sentence (still forbidden after launch):

> `hunt run` orchestrates Claude / ZCode / Hermes. Native HUNT harness lives in this repo.

---

## 1. Maturity at handoff (do not redo)

Kernel enforcement is ahead of the operator shell. FIRSTBLOOD (`examples/practice_target/FIRSTBLOOD.md`: ZCode + HUNT-BRIDGE + CLI, no conductor) already completed a full pipeline against the practice target. That is the proof the **door exists**. It is not the proof the door is launchable as "operator for all harnesses."

### Already shipped — do not rebuild

- Evidence ladder `theoretical → in-code → proven-live` with executed `hunt poc run` (exit 0, sha pinned). Promote without a matching `poc_run` is BLOCKED (`db.promote_finding` in `app/src/huntos/core/db.py`).
- Pipeline gates, wave economics, RoE default-deny mutate, secrets refuse-at-gate, project lock, claim gate exit 2, taxonomy, leads + oracle, surfaces, chains, fuzz, report fingerprint, dual-OS CI, stdlib-only.
- Skills installer `python install/skills.py` (claude-code / zcode / hermes / generic; additive; `--check` / `--uninstall`).
- Conductor C0+C1 with **MockAdapter only** (`CONDUCTOR_ADAPTERS = {"mock": MockAdapter}` in `app/src/huntos/cli/main.py`). Leave it experimental.

### Not launch-ready

| Gap | Why it blocks "operator for all harnesses" |
|---|---|
| No hook pack | Mouth-guard is a script the operator must wire. Guarded mode is fiction. `bridge/README.md` is illustrative. |
| No `hunt install` | Second CLI (`python install/skills.py`). Docs still pretend a hunt subcommand. |
| `hunt doctor` is mock-only | Does not check PATH, db, lock, gate, or skills. Lies by omission. |
| Roles not installed | HUNT-BRIDGE tells engines to read `soul/roles/lane-runner.md`; the installed tree does not contain it. |
| No `hunt next` | 15+ command tax. Engine must memorize the pipeline. |
| Thin `--help` | `hunt -h` is a name list. Real manual is the module docstring in `main.py`. |
| FIRSTBLOOD friction still live | MSYS mangling + no retitle (#2), `wave open` error `id = ?` (#3), `report --out` exit 0 on archived (#5), `brief` lock-blocked. |
| QUICKSTART omits `poc run` | An agent following QUICKSTART §4 is BLOCKED on promote. WALKTHROUGH is correct. |
| Ladder CLI untested as CLI | `poc` / `wave` / `verify` / `challenge` / `brief` / `oracle` / `klass` are kernel-tested, not `main([...])`-tested. |
| P5 says session-scoped; installer is permanent | Doctrine vs machine. |

Honest pre-launch score: **ledger door 8/10, operator shell 4/10, all-harness occupancy 4/10.** Launch is the work that raises the last two without touching C2/C4/bench.

---

## 2. Out of scope (hard)

Builder MUST NOT implement, scaffold, or "just add":

- C2 real-harness adapter / headless `HuntAdapter` for Hermes, Claude, ZCode
- C4 native harness, provider SDKs, sandbox, subagents, anything under `app/src/huntos/harness/`
- `hunt bench`, practice-target v2, N-run harness eval
- `hunt stats`, `hunt snapshot`, `hunt dupes`, `hunt lesson search`, `hunt skill promote`
- Phase A report export / CVSS / signing (A1–A3)
- `hunt migrate`, WAL audit, multi-user API, web dashboard
- Session-scoped skill injection (P5 remainder) — **document honesty**, do not build a session injector
- Changing claim-gate bind algorithm (nearest-id within 80 chars) — FIRSTBLOOD #14 stays open
- Changing economic-stop law (`exhausted` still archives immediately) — only messaging + docs
- Changing `findings_new` to exclude overturned — kernel economics, not this launch
- verify-eats-poc (free-text `hunt verify` body) — proof-path kernel work, scheduled after bench in ROADMAP; not this launch
- New pip dependencies. stdlib-only holds.
- Expanding conductor beyond mock. `CONDUCTOR_ADAPTERS` stays `{"mock": MockAdapter}`.

If a task is not in §4–§9, it is out of scope even if ROADMAP §7 lists it as NOW.

---

## 3. Product laws (invariants)

Numbered. Tests pin them.

1. **CLI is the only write door.** No new raw-SQL helpers for launch features. New commands call existing `db.*` or a new `db.*` that is trigger-guarded like the rest.
2. **Fail-closed.** User-input failure = `BLOCKED:` on stderr + exit 2. No traceback. argparse usage errors may stay `SystemExit(2)` with usage text (do not rewrite argparse).
3. **Stdlib-only.**
4. **Additive install.** Never overwrite a harness soul/identity. Refuse non-manifest overwrite unless `--force` (already shipped; keep it).
5. **Roles travel with the hunt layer.** After install, an engine that only has the installed skills tree can read lane-runner + the four lanes + adversary + verifier without the git checkout.
6. **`hunt next` never hunts.** It names one recommended next **command**. It does not add findings, pick lanes, or judge evidence. When the next act is judgment, next is a read (`hunt brief` / `hunt status`) and the WHY line names the human branch.
7. **`hunt doctor` never flatters.** Missing hook / missing `hunt` / unreadable db / missing gate = non-zero + named cause. Mock capabilities are printed only for `--adapter mock`.
8. **Conductor is not the launch surface.** Docs, `--help`, and doctor must not imply managed run on a real harness.
9. **Docs are runnable.** Every command in QUICKSTART and WALKTHROUGH must succeed on a fresh db in the order written, including `hunt poc run` before each promote.
10. **Dual-OS.** Every new test green on Linux and Windows CI.
11. **Installer compatibility is explicit.** `hunt install` delegates to `install/skills.py` and preserves its documented exit contract (including exit 1 for an install conflict or a failed `--check`). The normal hunt commands keep the fail-closed `BLOCKED:` + exit 2 contract.
12. **Hook lock context is explicit.** A copied hook runs the claim gate from its installed directory and evaluates the project lock from the operator's project root (`HUNT_PROJECT_DIR` when the harness does not preserve cwd). A hook must not silently fall back to the git checkout.

---

## 4. Work packages (build in this order)

Do not start L5 until L1–L4 tests exist. L0 may share a PR with L1. One package per PR otherwise: L0 → L1 → L2 → L3 → L4 → L5.

### L0 — Honest docs

**Goal:** the public sentence matches the machine.

- QUICKSTART §4: insert `hunt poc run --id N --poc-path <file>` **before each** `finding promote`. Mirror `app/WALKTHROUGH.md` lines 48–53. The current promote-without-poc-run path is a lie.
- QUICKSTART §1: keep the `PYTHONPATH=src python -m huntos` recipe. Add one line: this is how every harness must expose `hunt` (shell function, alias, or PATH wrapper). After L3, point at `hunt install` / `hunt doctor`.
- QUICKSTART §1: pin the supported bootstrap in both a POSIX shell and PowerShell. The repository does not promise a global packaged `hunt` executable in this launch; the documented `PYTHONPATH=src python -m huntos` shim (or an equivalent PATH wrapper) is the command every harness must expose.
- QUICKSTART §9 (conductor): one paragraph, experimental, mock adapter, **not required to hunt**. Do not cite `conductor.md` as if it were committed doctrine. If a sentence still says `from conductor.md`, delete the filename citation.
- README "How it runs with an engine": HUNT-OS is the CLI operator layer; the engine is the harness; native harness is later / sibling. Pair with claim gate **and** the shipped hook pack (after L3).
- `bridge/README.md`: replace "illustrative only" as the primary story. After L3, the primary story is the shipped hook pack paths. Keep manual/audit mode.
- P5 honesty in README or WALKTHROUGH (one sentence): skills install is **permanent and namespaced** until uninstalled. Not session-scoped. Operator identity between hunts is the operator's job, not an installer feature we pretend to have.
- HUNT-BRIDGE: if roles are copied into the installed tree (L3), update the path engines should read (`hunt-os/roles/lane-runner.md` or whatever L3 chooses). Do not leave a path that only exists in the git checkout.
- FIRSTBLOOD / WALKTHROUGH: `wave close --verdict exhausted` archives only after the existing target-lesson gate succeeds (`db.close_wave` -> `archive_target`). Do not instruct `exhausted` then `hunt report`. Report before economic stop, or use `continue` until report/retro/archive.

Acceptance: a reviewer can run every QUICKSTART command in order against a temp db and get exit 0 through proven-live (tiny PoC files). L5 scripts this.

The economic-stop sentence above is shorthand for the existing kernel behavior:
the required target lesson must be present before `exhausted` can archive.
Docs must not imply that an exhausted close bypasses the lesson memory gate.

### L1 — Operator shell: `hunt next` + help + lock-exempt reads

**Goal:** the CLI occupies the operator. The engine asks `hunt next` instead of memorizing 15 commands.

#### L1.1 `hunt next [--target ID]`

- New subcommand. Read-only. Lock-exempt (L1.2).
- Resolves target: `--target` wins; else the single non-archived target; else BLOCKED listing ids (`hunt target list`).
- Prints **exactly two lines** to stdout on success (plus optional stderr warnings):

  ```
  NEXT: <one copy-pasteable command>
  WHY: <one sentence, ledger-grounded>
  ```

- Exit 0 if a next command exists. Exit 2 only on BLOCKED (no target, unknown id, corrupt db). An archived target prints `NEXT: hunt target list` / WHY archived — still exit 0.
- Does **not** execute the named command.
- `NEXT` is one deterministic recommendation, not a claim that no other legal
  command exists. In judgment states, `WHY` must name the available human
  branch(es); `hunt next` never records that the operator has read a brief.
- Total order (first match wins). Implement as a pure function `db.next_command(conn, target_id) -> tuple[str, str]` so tests do not go through argparse only.

| # | Ledger condition | NEXT | WHY (sense, not exact string) |
|---|---|---|---|
| 1 | target in `scoring` and `ev_score <= 0` | `hunt score <id> <ev>` | cannot leave scoring without a score |
| 2 | `scoring` and scored | `hunt phase <id> recon` | next phase |
| 3 | `recon` and no `surface_map` artifact | `hunt artifact <id> surface_map <path>` | phase exit artifact |
| 4 | `recon` and artifact present | `hunt phase <id> classify` | |
| 5 | `classify` and no `attack_plan` | `hunt artifact <id> attack_plan <path>` | |
| 6 | `classify` and artifact present | `hunt phase <id> hunting` | |
| 7 | `hunting` or `verify`, previous wave closed but `reaudit_done=0` | `hunt wave reaudit --wave-id <wid> --summary "..."` | wave N+1 locked |
| 8 | `hunting`, no open wave (none, or last closed+reaudited) | `hunt brief <id>` | opening read before a wave |
| 9 | `hunting`, a wave is already open | see hunting fork below | |
| 10 | `verify`, some finding `in-code` without verifier event | `hunt verify <fid> <type> <body>` | proven-live gate |
| 11 | `verify`, `in-code` with verifier, no adversary event | `hunt challenge <fid> "<notes>"` | |
| 12 | `verify`, `theoretical` or `in-code` whose next promote lacks matching `poc_run` | `hunt poc run --id <fid> --poc-path <file>` | existence is not execution |
| 13 | `verify`, a finding's next ladder promotion is admissible and has a matching `poc_run` | `hunt finding promote --id <fid> --evidence-ref "<evidence>" --poc-path <file>` | climb the ladder; the db remains the final gate |
| 14 | `verify`, zero `in-code` findings and no row 13 candidate | `hunt phase <id> report` | leave-verify gate |
| 15 | `report` and no `disclosure_report` artifact | `hunt report <id> --out REPORT.md` | |
| 16 | `report` and artifact present | `hunt phase <id> retro` | |
| 17 | `retro` and no lesson bound to target | `hunt lesson add <name> "<pattern>" --target-id <id>` | archive gate |
| 18 | `retro` and lesson present | `hunt target archive <id> "<reason>"` | completion |
| 19 | `archived` | `hunt target list` | hunt is closed |

For rows 10–13, choose the lowest finding id among the findings matching the
first applicable row. Row 13 uses the path of the matching `poc_run` as
`<file>` and leaves `<evidence>` as an operator placeholder; it must exist for
both theoretical → in-code and in-code → proven-live. For the latter, the
verifier and adversary events must already exist. A command can still be
blocked by a deeper kernel gate (for example RoE); `next` reports ledger state,
it does not pre-judge free-text evidence.
For an in-code → proven-live promotion, the matching PoC must also have a
different sha256 from the PoC recorded on the in-code step; the old run cannot
be reused as the second proof.

**Hunting fork (row 9) — judgment, so next is a read, never a finding:**

- If a wave is **open**: `NEXT: hunt status` — WHY: wave #n is open; record findings/leads through the CLI; close when the wave is done (`hunt wave close --wave-id n --verdict continue|exhausted|pivot`). The close command is in WHY, not in NEXT.
- If hunting, no open wave, last wave absent or closed+reaudited → always `hunt brief <id>` (row 8). **Do not invent a "briefed" session table.** Operators re-read. Cheap. After reading, the operator may open a wave (`hunt wave open <id> "<lanes>"`) or, when the hunt is complete, enter verify (`hunt phase <id> verify`). Repeating `hunt next` repeats the read recommendation by design; the ledger does not pretend that a read was a decision.
- `hunt next` **never** prints `hunt wave open` as NEXT (lanes are judgment). Put the wave-open example in WHY of the brief row: `when done reading: hunt wave open <id> "<lanes>"`.

**Placeholders** in NEXT (`<path>`, `<ev>`, `"..."`) stay as literals the operator fills. Do not invent scores, titles, or file paths.

**RoE:** not a phase gate today. Do not insert `hunt target roe` into the total order. Mention RoE in `hunt target add` echo and `--help` only.

Tests (`app/tests/test_next.py` + CLI `main(["next", ...])`):

- Empty db → BLOCKED, names the missing target.
- Each row 1–19 on a fixture db (throwaway). One test per row **or** one walk that asserts the NEXT at each step.
- The walk includes the row-13 promotion recommendation after each successful
  `poc run`; it must not dead-end before report.
- Open wave → NEXT is `hunt status`, not `finding add`.
- Archived → exit 0, NEXT is `target list`.
- Two active targets without `--target` → BLOCKED, lists both.
- `next` does not write (compare events count before/after).

The row fixture covers rows 1 through 19, including both promotion states; the
numbering is intentionally not frozen if a later row is added, but every
state that can be returned by `next` must have a regression pin.

#### L1.2 Lock-exempt reads

`READ_ONLY_COMMANDS` today (`main.py`): `verify-report`, `status`.

Add at least: `brief`, `next`, `doctor`, `klass` (list only), `lesson` (list only), `lead` (list only), `target` (list only), `surface` (list only), `coverage`, `chain` (show / novelty), `run` (status only).

Write actions under those groups (`klass add`, `lesson add`, `run start`, …) stay lock-blocked.

The allowlist today is command-name-only. If a group mixes read and write (`target list` vs `target add`), the lock check must look at `args.action` (or equivalent), not only `args.cmd`. Do not make `target add` lock-exempt by accident.

Test: bind to db A, `HUNT_DB=dbB`, `hunt brief 1` and `hunt next` print WARNING + still run (exit 0). `hunt finding add` on the same mismatch is exit 2. `hunt target add` on mismatch is exit 2. `hunt target list` on mismatch is WARNING + exit 0.

#### L1.3 `--help` density

Every `add_parser(...)` for a user-facing command gets a one-line `help=`. `hunt -h` / `hunt --help` must list every top-level command with that line. Fill missing top-level helps (`score`, `phase`, `poc`, `verify`, `challenge`, `wave`, `report`, `status`, `brief`, `oracle`, `next`, `install`, …).

Do not dump the module docstring into argparse. Docstring can stay as the long manual.

Test: `main(["-h"])` capturing stdout includes `next`, `install`, `doctor`, `brief`, `poc`.

#### L1.4 Echo what was recorded

- `finding add` stdout must say whether it linked to an open wave (`linked to open wave #N` or `no open wave`). FIRSTBLOOD #13. Today `db.add_finding` silent-links; the echo must read the finding's `wave_id` after insert.
- `wave open` error path: never `not found: id = ?`. See L2.3.

### L2 — FIRSTBLOOD friction that is CLI (not kernel economics)

Source: `examples/practice_target/FIRSTBLOOD.md` items 2, 3, 5, 11, 13. Items 4, 6, 7, 8, 10, 12, 14 stay open. Item 9 is already closed in kernel (`poc_run` required); do not rebuild.

#### L2.1 `hunt finding retitle` and `hunt lesson reword`

- `hunt finding retitle --id N --title "..."`
  - Allowed when the target is not archived and the finding is not `overturned`.
  - Proven-live **may** retitle (bookkeeping, not evidence). Ladder status unchanged. Logs `finding_retitled` event with old title.
  - Secrets gate on the new title (`assert_no_secrets`).
- `hunt lesson reword --id N --pattern "..."`
  - Rewrites `pattern` (and optionally `--notes`). Logs event. Archive gate unchanged (lessons already allowed on archived targets for memory; retitle/reword of findings is not).
- These exist so MSYS mangling is not an overturn. They are not a general edit API (no klass/severity/ladder edits).

Tests: retitle theoretical; retitle proven-live; BLOCKED on overturned; BLOCKED on archived target; secret-shaped title BLOCKED; event logged.

#### L2.2 MSYS leading-slash guard (Windows / Git Bash)

If a positional **free-text** string matches a mangled Git path (`[A-Za-z]:/Program Files/Git/` or `[A-Za-z]:\\Program Files\\Git\\`), **BLOCKED** with:

`BLOCKED: argument looks MSYS-mangled (leading '/' became a Git path). Prefix the command with MSYS_NO_PATHCONV=1, or do not start the argument with /.`

Apply to `finding add` title, `finding retitle` title, `lesson add` pattern/source, `lesson reword` pattern. Do not apply to real Windows paths that are **files** (`poc-path`, artifact path) — those should still be files that exist.

Test: feed a title `C:/Program Files/Git/api/users dumps...` → exit 2, no row. A normal title still works. A real existing `C:\Users\...` poc path is not blocked by this detector.

#### L2.3 Named not-found errors

`db._row` currently raises `not found: {sql.split('WHERE')[-1].strip()}` → `not found: id = ?`.

For CLI-facing lookups at least:

- unknown target → `BLOCKED: target #<n> not found`
- unknown finding → `BLOCKED: finding #<n> not found`
- unknown wave → `BLOCKED: wave #<n> not found`
- unknown lead → `BLOCKED: lead L-<n> not found`

Prefer `_row` growing an optional `label=` so kernel tests that match the old string are updated in the same PR. `main()` already prefixes `BLOCKED:` if missing. Do not leave `id = ?` on `hunt wave open 2` when target 2 does not exist.

Test: `main(["wave", "open", "2", "parser"])` on a db with only target 1 → stderr contains `target` and `2`, not `id = ?`.

#### L2.4 `hunt report --out` fail-closed

Today (`cmd_report`): writes the file, then artifact stamp may print BLOCKED, **exit 0**.

Law for launch:

1. If the target is archived (or otherwise cannot stamp `disclosure_report`): **do not write** `--out`. stderr BLOCKED, exit 2.
2. If write succeeds and stamp succeeds: exit 0, file on disk, artifact event present.
3. If write succeeds and stamp fails for any other reason: exit 2, stderr BLOCKED. File may remain (do not delete user data). Do not claim success.

Test: archived target + `--out` → rc 2, file absent. Happy path still stamps and exit 0.

#### L2.5 Exhausted messaging (law unchanged)

`exhausted` still archives immediately (`db.close_wave` → `archive_target`). Change the close echo to say so:

`wave #N closed findings_new=… verdict=exhausted — target archived (economic stop; report/retro skipped)`

WALKTHROUGH / QUICKSTART must not close exhausted then report (L0). For an economic stop, record the required lesson before the close.

Clarification: the existing `archive_target` memory gate still applies. The
target must already have at least one bound lesson; without one, close remains
BLOCKED and the wave stays open. This is an existing kernel precondition, not a
new launch rule.

Tests: an exhausted close with no target lesson is BLOCKED and leaves the target
active; the same close after `hunt lesson add ... --target-id <id>` archives
and prints the exact economic-stop meaning. No schema or economic-law change.

#### L2.6 `[PROVEN]` vs `proven-live`

`hunt status` must print the ledger name `proven-live` (or print both once: `proven-live`). Do not invent a second status. Claim-gate markers stay `PROVEN[F-n]`.

### L3 — Occupy every harness (install, roles, hooks, doctor)

This package makes "all harnesses" true for **skill-only + guarded**. Managed `hunt run` stays mock.

#### L3.1 `hunt install` wraps `install/skills.py`

```
hunt install --adapter claude-code|zcode|hermes|generic
             [--scope project|user] [--mode router|native]
             [--dir PATH] [--force] [--check] [--uninstall]
```

- Same flags, same exit codes as `python install/skills.py`.
- Implementation: import the installer module (do not fork the logic). Keep `python install/skills.py` working for people who have not put `hunt` on PATH.
- `hunt install --help` is the operator-facing doc. QUICKSTART points here.
- Do not normalize installer exit 1 into the normal hunt-command exit 2:
  conflict/refusal and failed `--check` remain exit 1, while successful
  install/check/uninstall remains exit 0. argparse misuse may still be
  `SystemExit(2)`.

Note: `hunt install` does not need a hunt db. If `main()` currently opens `HUNT_DB` before dispatch, `install` (and possibly `doctor` preflight) must skip the db-open / lock path the way a missing-db command should not traceback. Empty default db that `connect()` creates is acceptable if doctor/install do not require a hunt; do not fail install because `~/.huntos/hunt.db` does not exist yet — but also do not silently create a db as a side effect of `install` if you can skip `connect()`. Prefer skip.

Tests: `main(["install", "--adapter", "generic", "--dir", tmp])` then
`--check` round-trip; conflict and failed-check exit contracts match the
standalone installer; an install invocation does not open or create
`HUNT_DB`.

#### L3.2 Roles travel with the layer

Installer (router and native) also copies `soul/roles/*.md` into the installed hunt layer, e.g. `hunt-os/roles/`. Additive, manifest-tracked, `--uninstall` removes them.

Required files: `lane-runner.md`, `architect.md`, `red-teamer.md`, `fuzz-engineer.md`, `chainer.md`, `adversary.md`, `verifier.md`.

HUNT-BRIDGE and the generated router SKILL.md must point at **that** path, not `soul/roles/lane-runner.md` in the git tree.

Test: after generic install, all seven exist under dest and are in the manifest. `--uninstall` removes them. Additive law still refuses clobbering a pre-existing non-manifest file.

#### L3.3 Hook pack (ROADMAP B3, this launch)

Ship **real** wiring under `install/hooks/`:

| File | What |
|---|---|
| `install/hooks/generic.sh` | stdin → the gate copied beside the wrapper; propagate the gate exit code. `HUNT_DB` passthrough. If the harness does not preserve project cwd, `HUNT_PROJECT_DIR` is required and the wrapper `cd`s there before invoking the gate. |
| `install/hooks/README.md` | How to attach generic.sh. Claude Code Stop / PostToolUse recipe **only if the JSON schema is the real current Claude settings schema** (not the old illustrative blob in `bridge/README.md`). |
| Claude snippet | If and only if the format is known and tested. e.g. `install/hooks/claude-code-settings.fragment.json`. |
| ZCode | Do **not** invent a ZCode hook schema. If no documented in-tree format exists, README says: wrap the generic script as the post-output command. FIRSTBLOOD used ZCode as a manual engine; guarded ZCode is "run this wrapper." |

The installed layout is fixed for this launch: `hunt-os/hooks/claim_gate_wrapper.sh` and
`hunt-os/hooks/claim_gate.py`, both manifest-tracked. The wrapper resolves the gate
relative to its own directory and invokes it with `${HUNT_PYTHON:-python}`; it never
falls back to `bridge/claim_gate.py` in the git checkout. `HUNT_PROJECT_DIR`, when
set, is the directory whose `.huntos-project` lock the gate must evaluate. A
project without a lock remains valid (the gate's existing unbound behavior stays).
The copied gate must keep the existing fail-closed behavior byte-for-byte in
behavior, including read-only db access and exit 2 on an unreadable db.

Tests (`app/tests/test_hook_pack.py`):

- Wrapper + fixture db **without** proven-live + stdin `F-1 is PROVEN` → exit 2, stderr `BLOCKED:`.
- Same db after a real proven-live row + `PROVEN[F-1]` → exit 0.
- Empty stdin → exit 0.
- Unreadable `HUNT_DB` → exit 2 (fail-closed).
- Installed wrapper invoked from a foreign cwd with `HUNT_PROJECT_DIR` pointing
  at a bound project and a mismatched `HUNT_DB` → exit 2; the wrapper must not
  bypass the project lock.
- Installed wrapper works after the source checkout is absent from its cwd; the
  test must exercise the copied `hunt-os/hooks/claim_gate.py`, not the source
  file by accident.
- On Windows, where the shell wrapper is not executed, invoke that copied gate
  with the wrapper-equivalent project cwd and environment; do not silently
  replace the lock-context assertion with a source-tree-only smoke test.

No network. No real harness process required. Windows CI: if `.sh` cannot run, test the same contract by invoking `python bridge/claim_gate.py` the wrapper would have called (and still ship the `.sh` for Unix). Do not skip the veto/pass assertions on Windows.

#### L3.4 `hunt doctor` tells the truth

Replace the current "ask MockAdapter for eight flags" as the **default** meaning of `hunt doctor`.

```
hunt doctor [--adapter claude-code|zcode|hermes|generic|mock]
             [--scope project|user] [--dir PATH]
```

Default: workspace preflight, not conductor, with no adapter-specific skill
check and no mock capability dump. `--adapter mock` opts into the existing
conductor capability dump. For `claude-code` and `zcode`, `--scope` and
`--dir` resolve exactly as they do for `hunt install`; for `generic`, `--dir`
is required. The same resolved directory is used for the manifest, installed
gate, and installed hook checks. Hermes remains the explicit no-op adapter.
With no adapter, doctor checks the source workspace's `bridge/claim_gate.py`
and `install/hooks/` pack; it must not infer an arbitrary adapter destination.

Checks (each prints `ok` or `FAIL: ...`; process exit 2 if any FAIL):

1. **CLI import:** current entry can run. `hunt status` against current `HUNT_DB` does not traceback (empty db is ok).
2. **DB open:** `HUNT_DB` or default opens; corrupt file is FAIL with the existing BLOCKED message.
3. **Project lock:** unbound = `ok (unbound)`; match = `ok`; mismatch = FAIL (doctor reports FAIL; it may still complete the rest of the checklist).
4. **Claim gate:** the resolved source or installed `claim_gate.py` runs on empty stdin, exit 0. Missing file = FAIL. When an adapter destination is supplied, prefer and verify the installed copy there.
5. **Skills layer (if `--adapter` is claude-code/zcode/generic):** manifest present at the adapter dest. Hermes: print the soul-injection reminder, do not FAIL for missing copy (Hermes is no-op by design). Missing manifest on claude-code/zcode = FAIL (`hunt install --adapter …` first).
6. **Hook wrapper:** the resolved installed wrapper exists and is runnable. Missing = FAIL with `guarded mode unwired; see install/hooks/README.md`.
7. **`--adapter mock` extra:** existing conductor capability dump. Only then. Unknown conductor adapter still BLOCKED.

Do not check provider keys, disk reserve, headless heartbeat, or "agent can spawn subagents." Those are C2/C3.

Tests: each FAIL mode independently; all-ok on a temp install + temp db;
`--adapter generic --dir <tmp>` resolves the same destination as install;
default doctor does not print mock capability flags; `--adapter mock` still
shows mock flags without implying Claude is managed. Doctor must remain
diagnostic: no provider calls, no network, and no writes to the installed
manifest or hook files.

#### L3.5 Installer tests for claude-code / zcode paths

`app/tests/test_install.py` today uses `generic --dir` only.

Add: monkeypatch home/cwd, `--adapter claude-code --scope project` writes under `<cwd>/.claude/skills/hunt-os/`, `--adapter zcode` under `.zcode/skills/hunt-os/`, `--scope user` under patched `Path.home()`. Do not touch the real user profile.

Hermes remains no-op + exit 0 + instruction text.

### L4 — CLI wiring tests for the real hunt loop

New tests that call `huntos.cli.main.main([...])` (same door as the operator), not only `db.*`:

- `poc run` success (tiny python file exit 0) + failed poc (exit 1) → BLOCKED, no `poc_run` event
- `wave open/close/reaudit` happy path
- `verify` + `challenge` + second `poc run` + `finding promote` to proven-live
- `brief` stdout contains whatever `export_brief` already guarantees (phase / findings section)
- `oracle` with two tiny feature JSON files
- `klass list` / `klass add` at retro
- `next` as in L1, including the row-13 promotion recommendation after a
  successful `poc run`

Reuse existing kernel fixtures where possible. No LLM. No network.

This closes the audit gap named in plans.md (poc/wave/verify/challenge/brief/oracle/klass).

### L5 — Launch gate (definition of done)

Launch is not a version bump. It is this checklist, all true:

1. Dual-OS CI green (existing workflow). New tests included.
2. QUICKSTART commands, in order, on a throwaway db, including `poc run` before promote, reach proven-live + report + archive. Script this as `app/tests/test_quickstart_path.py` (or a documented `checks/` script run in CI) — **runnable**, not a screenshot.
3. `hunt doctor` FAIL modes covered; happy path covered after `hunt install --adapter generic --dir <tmp>`.
4. Hook wrapper smoke (L3.3) in CI, using the installed copy from a foreign
   cwd and checking project-lock veto.
5. `hunt next` walks a fixture from scoring → archive without ever suggesting `finding add`.
6. README one-paragraph "How it runs with an engine" matches §0.
7. No new dependency. No conductor adapter besides mock.
8. FIRSTBLOOD items 2, 3, 5, 11 (status wording), 13 addressed. Items 4 (exhausted law), 6 (reaudit order), 7 (`findings_new`), 8 (secret regex UX), 9 (already kernel-closed), 10 (verify body style), 12 (practice app HTTP), 14 (claim bind) **not required** for this launch.
9. At least one launch-path test runs the documented POSIX and PowerShell
   bootstrap from a fresh working directory; it must not rely on an implicit
   global `hunt` binary or a source-tree fallback for the installed hook.
   The same walk must exercise both ladder-promotion recommendations and must
   not dead-end before report.

---

## 5. Files the builder is expected to touch

Expected (not a quota — do not touch others without cause):

- `app/src/huntos/cli/main.py` — next, install, doctor, retitle, reword, help, lock-exempt, report fail-closed, finding-add echo, MSYS guard, exhausted echo
- `app/src/huntos/core/db.py` — `next_command()`, `_row` labels, retitle/reword + events; **no** exhausted-law change
- `install/skills.py` — copy roles and the fixed manifest-tracked hook wrapper + gate into the installed destination
- `install/hooks/` — new
- `bridge/README.md`, `soul/bridge/HUNT-BRIDGE.md`, `QUICKSTART.md`, `README.md`, `app/WALKTHROUGH.md`
- `app/tests/test_next.py`, `test_hook_pack.py`, `test_cli_ladder.py`, `test_quickstart_path.py`, extend `test_install.py`, existing CLI tests as needed

The installer changes must include the fixed manifest-tracked
`hunt-os/hooks/claim_gate_wrapper.sh` and `hunt-os/hooks/claim_gate.py`
layout; the installed wrapper must not fall back to the source checkout.

Do not edit `conductor.md` / `plans.md` unless the operator asks (those are local scratch). Do not merge conductor into main as part of this launch.

---

## 6. Test contract (minimum names)

| Test | Pins |
|---|---|
| `test_next_empty_db_blocked` | L1.1 |
| `test_next_scoring_to_archive_order` | table rows 1–19, including promotion rows |
| `test_next_open_wave_is_status` | no `finding add` |
| `test_next_promote_after_poc_run` | row-13 promotion recommendation; no dead end |
| `test_next_finding_selection_is_stable` | lowest matching finding id for rows 10–13 |
| `test_next_does_not_write` | events count |
| `test_brief_and_next_lock_mismatch_warning` | L1.2 |
| `test_help_lists_next_install_doctor` | L1.3 |
| `test_finding_add_echoes_wave` | L1.4 |
| `test_finding_retitle_*` | L2.1 |
| `test_msys_mangled_title_blocked` | L2.2 |
| `test_wave_open_unknown_target_names_target` | L2.3 |
| `test_report_out_archived_no_write` | L2.4 |
| `test_install_via_hunt_cli` | L3.1 |
| `test_install_copies_roles` | L3.2 |
| `test_hook_wrapper_veto_and_pass` | L3.3 |
| `test_hook_wrapper_respects_project_root` | L3.3 |
| `test_doctor_fail_missing_gate` / `_ok_workspace` | L3.4 |
| `test_install_claude_code_scope_project` | L3.5 |
| `test_cli_poc_run_and_promote` | L4 |
| `test_cli_wave_verify_challenge` | L4 |
| `test_quickstart_path` | L5 |

Every test: throwaway db, no network, no real home-dir writes.

---

## 7. Process (how this lands)

Follow ROADMAP §4:

1. Spec is this file. No orals.
2. Implementer + blind auditor. Auditor attacks the spec and the landing.
3. Arbitration by reproduction on P1/P2 claims.
4. Regression pins land with the fix.
5. Dual-OS CI green before "done."
6. Do not commit secrets. Hook fixtures use `PROVEN[F-1]` not live tokens.

Builder may land **one work package per PR** (L0 → L1 → L2 → L3 → L4 → L5).

---

## 8. What "done" is not

Shipping this launch does **not**:

- start the sibling harness repo
- decide C2's first adapter
- calibrate engines (`hunt bench`)
- make `hunt run` production

Those stay on the proof path: harder practice target + bench + then C2, with C4 in another repo.

---

## 9. Operator decisions already locked (do not reopen)

- Native harness = sibling repo (P10).
- This launch = CLI as operator for all harnesses.
- `hunt next` is a deterministic recommendation. Judgment branches remain
  human decisions; no `briefed` session table is added.
- Install is permanent + namespaced (honest P5). Session-scoped activation is not in this launch.
- `hunt install` preserves the standalone installer exit contract; normal hunt
  command failures remain `BLOCKED:` + exit 2.
- The supported bootstrap is the documented POSIX/PowerShell
  `PYTHONPATH=src python -m huntos` shim or an equivalent PATH wrapper; no
  implicit global executable is promised in this launch.
- Installed hooks use the fixed `hunt-os/hooks/` layout and
  `HUNT_PROJECT_DIR` for project-lock context when cwd is not reliable.
- `exhausted` law stays. Messaging + docs only.
- Claim-gate nearest-id algorithm stays.
- stdlib-only stays.
- Conductor stays mock.

End of spec.
