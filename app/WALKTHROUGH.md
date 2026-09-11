# Example: one target, end to end

Walkthrough of the full pipeline against a fictional target (TestVault). Install
the CLI with the bootstrap instructions in `README.md` or `QUICKSTART.md`, then
run these commands from an authorized workspace. Every phase move is gated: you
cannot leave a phase without producing its evidence.

## Target-source safety

The universal entry accepts an authorized URL, public GitHub repository, or
existing local folder through one ledger transaction:

```bash
hunt target prepare SOURCE --name TestVault --chain evm \
  --hosts "testvault.xyz" --actions "recon,read" \
  --authorization-note "owner-approved assessment"
```

A URL is recorded, not crawled. A GitHub source is shallow-cloned into an
isolated workspace. A local folder is referenced and never modified by
preparation. Credentials, controls, unsupported schemes, malformed GitHub
paths, and missing authorization fail closed. Treat every prepared tree as
untrusted: adapters are registered separately by absolute executable path and
are never loaded from the target.

The explicit `target add` command below is a compact way to walk the full
ledger manually; `target prepare` above is the universal source path:

```bash
# 0 SCORE - add + score; a target cannot leave scoring with ev_score <= 0
hunt target add TestVault https://testvault.xyz --chain evm --age-days 12 --tvl 250000
hunt score 1 8.5

# 0b RULES OF ENGAGEMENT - default-deny: a finding with --action mutate cannot
# reach proven-live unless the target's RoE allows the mutate action.
# NOTE: --hosts is INFORMATIONAL ONLY (the DB cannot verify what host a PoC
# touched) - only --actions are enforced.
hunt target roe 1 --hosts "testvault.xyz" --actions "recon,read"

# 1 RECON - record the surface map artifact, then move
hunt phase 1 recon
hunt artifact 1 surface_map surface_map.md
hunt phase 1 classify

# 2 CLASSIFY - record the attack plan artifact, then move
hunt artifact 1 attack_plan attack_plan.md
hunt phase 1 hunting

# 3 HUNT - wave 1
hunt wave open 1 "parser,auth,state,econ"
hunt finding add 1 "Unprotected drain() via generate-1 operator key" Access --severity critical --action mutate --notes "0x0b01... style deployer backdoor"
hunt finding add 1 "Oracle staleness on redeem path" Oracle --severity high
# a finding the taxonomy can't classify yet goes in as Unknown (quarantine class)
hunt finding add 1 "Storage slot drift after proxy upgrade" Unknown --severity medium
# wave closes with verdict; findings_new is computed from wave-linked findings
hunt wave close --wave-id 1 --verdict continue
hunt wave reaudit --wave-id 1 --summary "2 confirmed, 0 overturned"

# wave 2 now unlocks
hunt wave open 1 "sig,UUPS"

# 4 VERIFY - the engine produces PoC files on a fork; the CLI records the ladder climb.
# Each ladder step demands a DIFFERENT PoC file, EXECUTED through
# `hunt poc run --id <n> --poc-path <file>` before any promote (existence is
# not execution; poc run pins the file's sha256 at run time). Proven-live also
# requires a verifier event (hunt verify <id> <fork_receipt|tx_hash|http_transcript> <body>)
# AND an adversary review (hunt challenge <id> "<what you attacked and what held>").
# You cannot leave verify with in-code findings: promote, overturn, or leave theoretical.
# Claim syntax: when the engine speaks, claims bind to a finding id — PROVEN[F-1],
# EXPLOITABLE[F-1]. An unbound PROVEN/EXPLOITABLE fails the turn at the claim gate.
hunt phase 1 verify
printf '%s\n' 'print("drain()")' > poc_drain_in_code.py
hunt poc run --id 1 --poc-path ./poc_drain_in_code.py
hunt finding promote --id 1 --evidence-ref "anvil fork receipt, block 21000000" --poc-path ./poc_drain_in_code.py
hunt verify 1 tx_hash 0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef
hunt challenge 1 "attacked reentrancy paths and the guard bypass angles - no counterexample found"
printf '%s\n' 'print("drain() LIVE at block 21000000")' > poc_drain_live.py
hunt poc run --id 1 --poc-path ./poc_drain_live.py
hunt finding promote --id 1 --evidence-ref "tx 0xdeadbeef on fork" --poc-path ./poc_drain_live.py

# 5 REPORT - generated from the database, not memory.
# --out also logs the disclosure_report artifact (the phase exit gate for report).
hunt phase 1 report
hunt report 1 --out REPORT.md

# 6 RETRO - a lesson bound to the target is required before archive
# (memory compounds or it never happened)
hunt phase 1 retro
hunt lesson add TestVault "operator-key backdoors recur on generative NFT contracts - check gen-N deployer == operator" --scope skill --target-id 1
# taxonomy growth is retro-gated: promote the quarantined Unknown finding into
# a real class (re-tags the finding and records a law_candidate lesson)
hunt klass add Upgradeable --from-finding 3
hunt status

# 7 ARCHIVE - the completion path: retro -> archive. Archiving requires a
# lesson bound to the target (recorded above). The economic stop from HUNTING
# (hunt wave close --verdict exhausted) is the other legal exit - and the
# memory gate still applies: the target must already have a bound lesson
# BEFORE the exhausted close, or the close stays BLOCKED and the wave open.
hunt target archive 1 "pipeline complete: findings reported, lessons recorded"
```

## Managed control room: serial lanes and evidence boundaries

A managed round always attempts four distinct lanes **serially**:
`architect`, `red_teamer`, `fuzz_engineer`, then `chainer`. The static page may
show four panels at once, but that layout is not a claim of parallel execution.
The conductor owns order, budgets, retries, mediated tools, and claim-gate
checks. While its session is RUNNING, a connected harness is only the judgment
service for the assigned attempt; it must not start another lane loop.

Adapter messages and assistant output are bounded operational logs. They help
diagnose execution, but they are not evidence and cannot promote a finding.
Evidence is only what the CLI records through the defined gates: artifacts,
executed PoCs, verifier events, adversary review, and ledger-backed finding
state. Infrastructure errors are never converted into research findings.

The built-in `mock` is deterministic and always labelled
`SIMULATED — no external agents invoked`. It demonstrates control flow only.
A real harness requires explicit `hunt adapter add NAME --exec ABSOLUTE_PATH
[--arg ARG ...]` registration and a passing `hunt adapter doctor NAME` under
`HUNT-ADAPTER/1`. Installing a skill directory does not create managed support.
A conforming adapter is a protocol executable; a reference adapter proves that
protocol but is not an LLM, external subagent, or evidence source.

## Open the next hunt with a brief

Memory compounds only if you read it back. Before round 1 of a new session —
and before every new wave — open with one read:

```bash
hunt brief 1
```

One markdown page, generated from the database: lessons (target-bound first,
then global), current contradictions (`!!` lines), wave history with verdicts
and re-audit state, findings by ladder, and the klass taxonomy. Everything the
last round learned is what this round starts from.

## SEE, COMBINE, PROVE — the 0-day tools

Three tools mechanize the doctrine's manual steps: surfaces organize the
looking, chains organize the combining, fuzz mechanizes the flinch-probing.

```bash
# SEE - record what exists, then let coverage name what you have not probed:
hunt surface add 1 trust_boundary "client-asserted role cookie"
hunt surface add 1 endpoint "/transfer (POST from,to,amount)"
hunt coverage 1        # [no-lead] [no-finding] rows, then !! blind spots

# COMBINE - a 0-day claim is a chain: entry -> linked steps -> impact.
hunt chain add 1 "cookie to admin" --entry "role cookie is client-asserted" --impact "full admin takeover"
hunt chain link 1 1 lead 1
hunt chain show 1      # and: hunt chain novelty 1 -> "novel: yes — never appeared in your ledger"
                       #                    or "novel: NO — seen in: <where you claimed it before>"

# PROVE the cheap way first - the standard edge-case battery, automated:
hunt fuzz --url http://127.0.0.1:8765/transfer --method POST --param amount --target-id 1
# every probe lands as a redacted fuzz_probe event; flinches print:
#   !! anomaly: amount=negative status=500 (baseline 200)
#   consider: hunt lead add --target <id> --title "fuzz flinch: amount=negative" (leads stay manual — engine judgment)
```

Fuzz flinches become leads (never auto-findings); leads promoted become
findings; findings chained and checked for novelty become the 0-day claim.
Pin each with `--surface <id>` on `finding add` / `lead add` so `hunt
coverage` can tell you which trust boundaries never grew anything. The tools
organize the evidence — you still have to be right.

Try to cheat the app - it refuses:

```bash
hunt phase 1 recon                                               # BLOCKED before scoring: cannot leave scoring without a positive ev_score
hunt finding promote --id 2 --evidence-ref "" --poc-path ""      # BLOCKED: no evidence
hunt phase 1 hunting                                             # BLOCKED: phase skip (already past)
hunt wave open 1 "more"                                          # BLOCKED if previous wave lacks re-audit/verdict
hunt finding promote --id 1 --evidence-ref "..." --poc-path ...  # BLOCKED: proven-live without verifier event or challenge
hunt finding add 1 "MASSIVE FIND" MASSIVE                        # BLOCKED: unknown klass — label inflation has no door
hunt finding promote --id 1 --evidence-ref "tx ..." --poc-path ...  # BLOCKED: --action mutate outside the rules of engagement (default-deny)
hunt verify 1 fork_receipt "password=hunter2"                    # BLOCKED: raw secrets are refused at the gates - store the fact, not the secret
```

## Phase exit gates

The phase you are LEAVING must have produced its evidence. All failures are `BLOCKED:` errors.

| Leaving phase | Gate |
|---|---|
| scoring | `ev_score > 0` (`hunt score <id> <n>`, must be positive) |
| recon | a `surface_map` artifact: `hunt artifact <id> surface_map <file>` |
| classify | an `attack_plan` artifact: `hunt artifact <id> attack_plan <file>` |
| hunting | at least one closed wave (last wave has an `ev_verdict`) |
| verify | zero `in-code` findings (promote, overturn, or leave theoretical) |
| report | a `disclosure_report` artifact (`hunt report --out` logs it automatically) |
| retro | archiving requires a lesson bound to the target: `hunt lesson add <source> "pattern" --target-id <id>` |

Artifacts are sha256-stamped into the `events` table when recorded; the file must exist and be non-empty.

## Label discipline

`klass` is a closed vocabulary, not free text: the 9 researched classes (OWASP
SC Top 10:2025 + DASP + SWC) plus the `Unknown` quarantine class are seeded as
DATA into a `taxonomies` table on first connect. Two database triggers
(`findings_klass_guard_insert` / `findings_klass_guard_update`) abort any
finding whose klass is not in that table — including raw-SQL cheats.

Growth is retro-gated: new classes are born only at retro via
`hunt klass add <Name> --from-finding <id>`, which re-tags the quarantined
finding and records a `law_candidate` lesson. Because the allow-list is a
table, the taxonomy can grow without a schema migration. `hunt status` prints
a contradiction report (`!!` lines) from the DB-level honesty engine — loud
claims without evidence, hollow waves, reports without proof, and unclassified
findings.

## Project lock

The db is the project's single notebook. A `.huntos-project` file in the
working directory pins the workspace to one database: it stores the full
`db_id` the directory was bound to, and every `hunt` command re-checks it
against whatever `HUNT_DB` currently points at. A swapped or freshly recreated
db file is blocked before it can write a single row:

```bash
hunt target add Sneaky https://sneaky.xyz
# BLOCKED: this project is bound to db 3fa1c2e90b44 but HUNT_DB points to 9c04aa712df0 — deliberate switch? rebind first: hunt project bind
```

Read-only commands (`hunt status`, `hunt verify-report <file>`) are allowed
through with a hard warning, and the `hunt project` group itself always runs
(otherwise a mismatch could never be repaired):

```bash
hunt project status   # shows the bound db_id and whether it matches HUNT_DB
hunt project bind     # deliberate switch: rebind this directory to the current db
                      # (logs a project_rebound event in the db it binds to)
```

Reports carry a sha256 fingerprint footer. Verify a report before trusting or
publishing it: `hunt verify-report REPORT.md` prints
`report matches its fingerprint` or refuses with `BLOCKED:` (tampered content,
or a file that was never generated by `hunt report`).

## Known limits (Class B)

The database enforces internal consistency, not truth. A verifier event is self-attested by the operator; the DB can check that a PoC file's hash is distinct between ladder steps, but it cannot judge the CONTENT authenticity of that PoC file; and ev_score, tvl and age are self-reported by the operator. These gaps are closed by process (the adversary role attacking claims, the verifier role independently confirming them) and by the upcoming Hermes bridge (PR-6), not by the schema.

The rules of engagement (PR-4) live in the same honesty envelope. RoE `--hosts` is informational only - the DB cannot see the wire, so it cannot verify what host a PoC actually touched; only `--actions` is enforced (the mutate proven-live gate, default-deny). The `--action` on a finding is self-declared by the operator - the DB labels what it is told, it does not classify the exploit. And loosening the RoE after mutate findings already exist is not blocked: it is logged (`roe_updated` events) and flagged by `hunt status` as a retroactive-authorization contradiction. Enforcement covers the promote gate; truth remains the operator's problem.

## Run through a harness

The state machine above remains operator-driven in skill-only mode. Inject or
install `app/src/huntos/_data/idea/HUNT-BRIDGE.md`, load only the assigned lane role, send all
records through `hunt`, and guard output with the claim gate. This works with
any harness that can call a CLI; it does not mean HUNT-OS controls that harness.

Managed mode is separate. Register an executable implementing
`HUNT-ADAPTER/1`, run its protocol doctor, and let the conductor assign each
serial attempt. The harness must not create competing lanes while a conductor
session is running. Hook wiring and lane contracts are in
`app/src/huntos/_data/bin/README.md`,
`app/src/huntos/_data/hooks/README.md`, and
`app/src/huntos/_data/roles/lane-runner.md`.

## How the engine loads skills

The skills tree (`app/src/huntos/_data/idea/skills/`, six categories) is never bulk-loaded. The
engine reads `app/src/huntos/_data/idea/skills/INDEX.md` first — the router — and then loads
specific skills on demand, one `skill_view` call at a time:

```
skill_view(name='black-swan-engine')        # EVM laws before touching a contract
skill_view(name='multi-target-cdc-audit')   # multi-target CDC batch procedure
skill_view(name='poc-reverification')       # before building on a saved PoC
```

Each lane has a fixed loadout (see the LOADING DOCTRINE section of
`INDEX.md`): the Verifier, for example, loads
`skill_view(name='audit-verification-methodology')` and
`skill_view(name='poc-reverification')`. A `skill_view(name='X')` written in
`app/src/huntos/_data/idea/IDEA.md` must resolve to a landed
`app/src/huntos/_data/idea/skills/<category>/X/SKILL.md` —
CI's `Skills reference integrity` check enforces it.
