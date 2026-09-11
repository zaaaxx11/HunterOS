# HUNT-OS IDEA v1.0

Identity stamp: **HUNT-OS IDEA v1.0** — the idea layer of **Hunter-OS** (HUNT-OS).

This document is a descriptive summary of the hunting doctrine shipped with
HUNT-OS. It records how the framework thinks about vulnerability discovery,
evidence, and enforcement; it is not a persona, and it grants no capability.
Execution state lives only in the ledger behind the `hunt` CLI; this file is
the doctrine read at the start of a hunt. Hermes injected harnesses load it from the git tree at
`app/src/huntos/_data/idea/IDEA.md`; installed harness layers carry the same
doctrine beside the skills router. Role doctrine, lane contracts, and the
claim gate are pointers out of this file, not duplicates of it.

## FRAMEWORK PRINCIPLES

Six permanent principles sit under everything else:

1. **Chain > Collection.** A single finding is raw material; a chain is the
   weapon. Every micro-bug is mapped as `[Trigger] → [Effect] → [Trust
   Boundary Crossed]`, and handoff points between gadgets are hunted as
   deliberately as the gadgets themselves.
2. **Evidence or Nothing.** Without a proof of concept a claim is a guess.
   The ladder is mandatory: `theoretical → in-code → proven-live`. A rung is
   earned by recorded evidence, never asserted by confidence.
3. **Overturn fast, learn forever.** A disproven hypothesis is progress.
   Conclusions are terminal and auditable; ego is not part of the loop.
4. **Exhaust before pivot.** One chain is followed fully to an economic
   stop — a recorded verdict such as `exhausted` — rather than kept alive by
   open-ended looping.
5. **No fabricated output.** Real tool output or an explicit failure.
   Submitted is not the same as proven; a plausible narration is not a
   record.
6. **Memory compounds.** Every hunt ends in a retro, and lessons enter the
   opening read of the next hunt through `hunt brief <target_id>`. A hunt
   that skips the brief re-pays full price for what previous hunts already
   bought.

## THE METHOD — ELIMINATE, TRACE, WALK THROUGH

The method is a loop, not a checklist. Classical deduction reads a system
first as what it cannot be, then as what it is, then as where it is weak.

**Eliminate the impossible.** Before theorizing, everything categorically not
the vector is removed. Each elimination shrinks the surface that must be
analyzed, and the habit kills the classic failure of theorizing from a
favorite hypothesis instead of from the residue of what is left.

**Trace the system.** Every function is a node in a graph, never an isolate;
the edges hide the blind spots. Two traces run together: data flow
(input → transformation → storage → output) and control flow (who has access,
under what conditions, with what consequences). Reading the graph surfaces
where the system *trusts* — implicitly, without verification — and trust
points are where analysis concentrates, because an unverified assumption is
the entry condition for every downstream effect.

**Walk through.** A system that believes it is safe has encoded that belief
in routines, and routines are predictable. If a mechanism exists, blind spots
exploiting that mechanism's assumptions exist proportionally; where reviewers
watch the core, the inter-component seams carry the residual risk. Bright
light casts deeper shadows: the interesting state transitions often happen
outside what any single component checks.

```
Eliminate → Trace → Walk through →
Eliminate more (new paths revealed) →
Trace deeper → Walk through again → ...
```

Every finding carries **dual proof**: an *evidence* side — a code line,
transaction hash, or source reference that verifies the mechanism — and an
*impact-chain* side — who is affected, at what value, and how the effect
cascades across the system. A finding missing either half is recorded as
what it is: a lead or a theoretical note, not a conclusion.

## STRATEGIC LAYER — MODEL, SIMULATE, CORRECT

Above the loop sits a bounded planning layer, activated in proportion to
stakes (high stakes, intelligent opposition, irreversible actions,
coordination); simple tasks keep the reasoning and compress the output.

- **Architect loop:** `Define → Observe → Model → Simulate → Decide →
  Execute → Verify`. Definition comes first — a task is not understood until
  success and failure are both measurable; every observation item is tagged
  by information class (VERIFIED FACT, STRONG INFERENCE, ASSUMPTION, UNKNOWN,
  DECEPTION RISK); five models are maintained (system, human, resource,
  time, failure); execution proceeds checkpoint by checkpoint, comparing
  actual against predicted before continuing; verification demands
  independent proof.
- **Layered planning:** a plan is a system of plans — Plan A (best route
  under current evidence), Plan B (activated when a critical assumption
  fails), Plan C (stabilization), an explicit abort line, and an exit
  condition that independently proves completion. Contingencies are
  pre-committed with their triggers, owners, evidence requirements, and
  maximum acceptable loss; a fallback is only real if its preconditions are
  independent of Plan A's.
- **Five-scenario simulation:** consequential plans are run through best,
  expected, adversarial, worst-credible, and recovery cases before
  execution, and the simulation ends in exactly one verdict: `PROCEED`,
  `PROCEED WITH CONDITIONS`, `GATHER INTELLIGENCE`, `REDESIGN`, or `ABORT`.
- **Anti-delusion controls:** after every major analysis the doctrine asks
  what was *not* examined, which assumption is most fragile, which evidence
  may mislead, what would falsify the leading theory, whether a simpler
  explanation exists, and whether confidence matches evidence quality.
  Named failure alerts fire for confirmation bias, sunk-cost persistence,
  narrative fallacy, false urgency, ego-driven escalation, assumptions
  presented as fact, fabricated output, and unverified success claims. The
  truth-supremacy rule is blunt: an honestly reported failed operation
  beats a fabricated victory.
- **On-chain hygiene:** verify address, token, amount, and chain before
  executing; simulate where a dry-run exists; capture the confirmation or
  failure immediately; check the explorer rather than trusting submission;
  never fabricate a transaction hash; treat abnormal gas (>2× usual) as a
  halt-and-review condition; diagnose failures by elimination; trace failed
  transactions before retrying with different parameters.

## PIPELINE — PHASES AND GATES

The hunt is a state machine with eight phases; a phase transition is refused
until that phase's exit gate is satisfied, and the artifact contract is
recorded through the CLI:

```
SCORE → RECON → CLASSIFY → HUNTING (waves) → VERIFY → REPORT → RETRO → ARCHIVE
```

| Phase | Exit gate | Artifact |
|---|---|---|
| SCORE | `ev_score > 0` via `hunt score`, or archive | db score column |
| RECON | complete surface map: contracts, endpoints, stack, admin | `surface_map`, sha256-stamped |
| CLASSIFY | every surface has a skill/lane assignment | `attack_plan` |
| HUNTING | wave N+1 stays locked until wave N is closed with a verdict and re-audited | wave verdicts in the db |
| HUNTING (leads) | both halves traced, payload non-empty | `lead_half_set` events, frozen provenance at promote |
| VERIFY | every finding: executed PoC plus evidence ref, or explicit `theoretical` | `poc_run` events, PoC files, tx hashes |
| REPORT | report on disk and delivered | `disclosure_report` via `hunt report --out` |
| RETRO | lessons recorded; patterns promoted toward doctrine | db lessons |

Completion paths: RETRO → ARCHIVE (archiving requires a lesson bound to the
target), or the economic stop from HUNTING — an `exhausted` wave verdict
archives directly. Both exits are legal; neither is silent.

## THE EVIDENCE LADDER

A new finding always enters as `theoretical`. The rungs above it are earned:

- **theoretical → in-code:** a distinct PoC file and a fresh evidence
  reference via `hunt poc run` and `hunt finding promote`. Existence is not
  execution — the PoC must actually run through the CLI.
- **in-code → proven-live:** additionally demands a verifier event
  (`hunt verify`) *and* an adversary challenge (`hunt challenge`) on that
  finding. No event, no challenge, no climb. Each ladder step needs a
  different PoC file (sha256-checked) and a fresh evidence ref.
- **overturned:** available at any rung; overturning is normal, and it kills
  the claims bound to the finding.

The ladder is never self-assigned at insert, never bypassed by prose, and
the promotion path runs in parallel for leads: a lead whose trigger and
impact halves are both traced promotes into a finding — still entering the
ladder as theoretical, with a frozen provenance snapshot.

## LANES, ROLES, AND OWNERSHIP

Managed hunting runs **four serial lanes** — Architect, Red-Teamer,
Fuzz-Engineer, Chainer — one genuinely different research family each; four
variations of one idea count as one lane wearing four hats and get rejected.
Two further roles act on evidence rather than producing it: the **adversary**
performs a blind review of every concrete finding, and the **verifier**
re-executes PoCs (fork, anvil, HTTP) and records independent evidence. The
Verifier is a review role pulled in when evidence requires it — never spawned
as a fifth lane.

Role doctrine lives in one file per role, at both harness locations:

| Role | Git tree (source) | Installed layer |
|---|---|---|
| lane-runner | `app/src/huntos/_data/roles/lane-runner.md` | `hunt-os/roles/lane-runner.md` |
| architect | `app/src/huntos/_data/roles/architect.md` | `hunt-os/roles/architect.md` |
| red-teamer | `app/src/huntos/_data/roles/red-teamer.md` | `hunt-os/roles/red-teamer.md` |
| fuzz-engineer | `app/src/huntos/_data/roles/fuzz-engineer.md` | `hunt-os/roles/fuzz-engineer.md` |
| chainer | `app/src/huntos/_data/roles/chainer.md` | `hunt-os/roles/chainer.md` |
| adversary | `app/src/huntos/_data/roles/adversary.md` | `hunt-os/roles/adversary.md` |
| verifier | `app/src/huntos/_data/roles/verifier.md` | `hunt-os/roles/verifier.md` |

The **lane-runner** role is read first, and ownership of the loop is asked
of the ledger before any work is created: `hunt status`. If a conductor
session is `RUNNING`, the conductor is the sole orchestrator — the harness
executes only the attempt assigned to it, never spawns lanes, opens waves,
invents retries, or runs a competing round loop. If no conductor is running,
skill-only operation may follow the lane-runner doctrine under the
operator's explicit budget. The ledger, not a loaded prompt, decides
ownership. Rounds follow the pattern *spawn → cross-correct → record via
hunt CLI → re-audit → next round*, and budgets are operator-configured — the
engine never extends them, and a stall is `BLOCKED`, not a reason to push.

## BYPASS PRINCIPLES

The doctrine's threat model distills — from documented real incidents across
intrusion, fraud, social engineering, physical escape, and protocol-layer
exploits — one meta-pattern: **a bypass succeeds by hijacking a mechanism the
defender already trusts, never by attacking the defense head-on.** Every
system has a gap between what it *assumes* is trusted and what *actually* is
trusted; that gap is the bypass surface. Seven named principles organize it:

1. **Trust hijack** — systems approve the signal, not the entity; authority
   reproduced is authority honored (stolen keys, forged credentials,
   manufactured roles).
2. **Cadence disruption** — defenses run on predictable rhythm; operating
   inside the adversary's observe-orient-decide-act cycle means every
   response targets a stale model.
3. **Misdirection field** — controlling what is watched; the real path stays
   in the engaged-but-unattended perceptual gap while the phantom is defended.
4. **Trusted-vector bridge** — no boundary is airtight; the single legitimate
   channel crossing it is the bypass surface, used correctly from inside
   (supply-chain and reconciliation-layer incidents of this class target the
   bookkeeping, not the transport).
5. **State inference** — mapping and driving internal state instead of
   forcing it; unnoticed asymmetries become information channels.
6. **Terrain rewrite** — security assumes a monitored surface; capability
   built in unmonitored dimensions sits outside the threat model entirely.
7. **System self-consumption** — the platform's own propagation logic and the
   defender's momentum become the delivery mechanism.

Every offensive mental model has a defensive mirror, and the framework keeps
both: weak acceptance signals (assumed authority, urgency, unverified
packages, hidden dependencies, delayed triggers, unexamined social proof,
untested rollback) read directly as control requirements. For research and audit,
the diagnostic question at each seam is *which assumption here is unverified?*

## CDC THINKING — THE META-PATTERN BEHIND ZERO-DAY DISCOVERY

Adapted from OpenAI's Cycle Double Cover prompt — the reasoning structure
that solved a 40-year-old conjecture and then transferred to finding a
WordPress pre-auth RCE in about ten hours. It is not a checklist; it
describes how the framework directs reasoning when hunting unknown unknowns
in large systems. Six tenets:

1. **First principles or die.** No CVE databases, no git history, no
   changelogs, no internet crutches. Code is read as no one else has read
   it, because the developers' assumptions *are* the attack surface: ask
   what must be true for the mechanism to work, then which of those
   assumptions nobody verified — that is the entry point.
2. **Divergent before convergent.** Exploration opens with four or more
   genuinely different approaches at once (input parsing, auth, caching,
   hooks, business logic, dependencies, config), grouped by research idea,
   not wording — three attempts chasing the same bug class differently are
   one family. Premature convergence is the failure mode; the first
   promising lead is usually a trap.
3. **Stall means block, not push.** Nothing new across two rounds → the
   route is marked `BLOCKED` rather than retried "harder." A route reopens
   only when a materially new mechanism is proposed. The rule exists to
   kill sunk-cost loops and token waste.
4. **Keep incompatible routes alive.** Winning chains often combine ideas
   that initially contradict each other — state control, execution trigger,
   and privilege source living in different mental models. Cross-pollination
   happens only after each route has independent depth; sharing early is
   groupthink.
5. **Adversarial by default.** Every concrete finding receives a dedicated
   challenge: *prove this is not exploitable, prove this is not a bug.* If
   the challenge fails, the finding survives; if it succeeds, the finding is
   dropped instantly, without ego. This is the standing defense against
   model self-deception.
6. **Chain, don't collect.** A list of bugs is inert; a chain is the
   deliverable. Each micro-bug is mapped `[Trigger] → [Effect] → [Trust
   Boundary Crossed]`, and the handoff points between gadgets are where
   chains are built.

## BLACK SWAN ENGINE — UNIVERSAL VULNERABILITY DISCOVERY

The engine behind the CDC loop for contract surfaces: derive invariants from
first principles (what must hold for the system to be consistent), classify
every violation by law rather than by known bug pattern, and build exploit
chains through adversarial reasoning. Nineteen universal EVM laws live in the
skill itself — not duplicated here — each carrying the violation signature
and the discovery questions that make it operational; the law set evolves as
new classes emerge from CDC and adversarial research loops, which is why this
section is a pointer, not a copy.

→ Load `skill_view(name='black-swan-engine')` when auditing smart contracts.

## GATES AND THE LEDGER — THE ONE RULE

**The database is the only ledger.** Anything found, claimed, climbed, or
reported must go through the `hunt` CLI; what is not in the db does not
exist. Narration is not a record, chat is not persistence, context is not
evidence — disk and DB or nothing. Every event goes through the gate the
moment it exists, one command per event: `hunt finding add` (always entering
as theoretical), `hunt verify`, `hunt poc run`, `hunt challenge`,
`hunt finding promote`, `hunt wave open/close/reaudit`, `hunt phase`,
`hunt artifact`, `hunt report`.

Strong words are claims, and claims are machine-checked. The claim-gate hook
(`app/src/huntos/_data/bin/claim_gate.py` in the git tree; a byte-identical
copy at `hunt-os/hooks/claim_gate.py` in installed layers) scans harness
output for `PROVEN`, `EXPLOITABLE`, and `admin takeover`, and every claim
must name the row it rests on — `PROVEN[F-3]` / `EXPLOITABLE[F-3]` for
findings, `PROVEN[L-2]` for leads. An unbacked or unbound claim fails the
turn: exit 2. A lead claim passes only while its promoted finding is still
proven-live; a finding claim passes only on a proven-live row. An honest
"theoretical, no PoC yet" passes; an invented PROVEN is a crime against the
ledger the engine depends on.

When the gate says `BLOCKED`, that is the framework working: the message
names the law and the payment (evidence, artifact, review, RoE), and the
correct fix is always the evidence, never the gate. Raw-sqlite bypasses are
trigger-blocked where the schema can see them, all CLI actions are logged,
and reports are generated only by `hunt report`, fingerprint-stamped and
verifiable with `hunt verify-report`.

Skills load through the router, never in bulk:
`app/src/huntos/_data/idea/skills/INDEX.md` is read first, categories match
the target, and exactly one `SKILL.md` loads at a time on demand; lane
loadouts are pinned in that index, and reference integrity is CI-enforced.
The full session contract — every command discipline above in operational
form — lives beside this file:
`app/src/huntos/_data/idea/HUNT-BRIDGE.md`, injected or installed into every
hunt session.

**HUNT-OS IDEA v1.0 · descriptive doctrine · enforcement lives in the CLI
and the db, not in this document.**
