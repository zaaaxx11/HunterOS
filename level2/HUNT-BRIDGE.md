# HUNT-BRIDGE — the engine's contract with the hunt state machine

Injected into the host harness every hunt session — Hermes via idea-injection
of `huntos/_data/idea/`, every other harness (Claude Code / ZCode / generic)
via the installed `hunt-os` skill (`python -m huntos.installer`, run as
`hunt install`). Pair with the claim gate hook
(`app/src/huntos/_data/bin/claim_gate.py`, installed as
`hunt-os/hooks/claim_gate.py`) — it scans your output after this file loads.

## THE ONE RULE

The database is the only ledger. Everything you find, claim, climb, or report
MUST go through the hunt CLI. If it is not in hunt.db, it does not exist.

- You are not the state machine. The CLI is. Narration is not a record.
- A finding that lives only in your context dies with your context.
- Before you say anything about a hunt, ask: which row does this come from?
  No row → run the command first, speak after.
- Chat is not persistence. Context is not evidence. Disk and DB or nothing.

## OPEN EVERY ROUND WITH A BRIEF

`hunt brief <target_id>` before round 1 and before each new wave. It returns
the lessons, the open contradictions, the wave history with verdicts, and the
taxonomy — everything the previous hunts paid for. Memory compounds only if
you read it back; a hunt that skips the brief re-pays full price.

## EVERY RECORD GOES THROUGH THE GATE

One command per event. Run it the moment the event exists — not at the end of
the turn, not "after I finish the chain".

- Finding discovered  → hunt finding add <target_id> <title> <klass> [--action ...]
  (label it honestly: it enters as theoretical — the ladder is earned, not claimed)
- Observation (lead)  → hunt lead add --target <id> --title "<hypothesis>" --payload "<the concrete attack>"
  (payload optional at add, required before the mutation loop; the payload is
  the hypothesis, not evidence — evidence lands in the halves)
- Next step (lead)    → hunt lead next --lead <n>
  (the deterministic first missing, never-tried precondition — run it, then
  execute it)
- Mutation (lead)     → hunt lead mutate --lead <n> --variable v --old o --new n --result advanced|unchanged|refuted|unknown --evidence "..."
  (anti-repeat: the same (variable, new_value) pair is refused; result=unknown
  requires --plan 'variable|value|description' — the loop never dead-ends)
- Half verdict (lead) → hunt lead set-half --lead <n> --half trigger|impact --verdict proven|refuted --evidence "..."
  (manual path; 'ambiguous' is oracle-exclusive)
- Oracle observation  → hunt oracle --lead <n> --half trigger|impact --baseline f.json --candidate f.json
  (deterministic rule on two feature JSONs: confirmed → proven, refuted,
  unknown → ambiguous. Inputs are operator-supplied — the VERDICT RULE is
  deterministic, the features are self-attested)
- Park with tripwire  → hunt lead park --lead <n> --retrigger "observable :: check"
  (a park without a testable retrigger is a lazy kill — refused; the tripwire
  wakes the lead: hunt lead reopen --lead <n> --evidence "what fired")
- Kill (lead)         → hunt lead kill --lead <n> --trigger-refutation "..." --impact-refutation "..."
  (both halves refuted; a one-sided kill is refused → auto-parked)
- Lead promoted       → hunt lead promote --lead <n> --klass <klass> --roe-action read|mutate|auth-test --severity ...
  (both halves proven; mints the finding with a frozen provenance snapshot —
  the RoE default-deny gate fires here exactly as it does for direct findings)
- Evidence produced   → hunt verify <finding_id> <fork_receipt|tx_hash|http_transcript> <body>
- PoC executed        → hunt poc run --id <n> --poc-path <file>
  (a finding's PoC must be EXECUTED through poc run before any promote —
  existence is not execution)
- Blind review passed → hunt challenge <finding_id> "<what you attacked and what held>"
- Ladder climb        → hunt finding promote --id <n> --evidence-ref ... --poc-path ...
- Waves & rounds      → hunt wave open / hunt wave close / hunt wave reaudit
- Phases & artifacts  → hunt phase / hunt artifact / hunt score / hunt target roe
- Report              → hunt report <target_id> --out REPORT.md

Command discipline:

- `klass` is a closed vocabulary. Nothing fits → `Unknown`, never free text.
- A new finding enters as theoretical. In-code and proven-live are never
  self-assigned at insert.
- Each ladder step needs a DIFFERENT PoC file and a fresh evidence ref.
- in-code → proven-live additionally demands a verifier event AND an adversary
  challenge on the finding. No event, no challenge, no climb.
- Wave N+1 stays locked until wave N is closed with a verdict and re-audited.
- NEVER narrate results as if they were recorded. NEVER write a report from
  memory. hunt report is the only report — generated from hunt.db, stamped,
  verifiable with hunt verify-report.

## WHEN THE GATE SAYS BLOCKED

BLOCKED is the framework working, not a bug. Read the message: it tells you
which law you hit and what paying it looks like (evidence, artifact, review,
RoE). Fix the evidence, never the gate.

- No PoC → write a real PoC file, promote again.
- No verifier event → run the fork/anvil/HTTP check, then hunt verify.
- No challenge → hand the finding to the adversary role, then hunt challenge.
- Phase move refused → produce that phase's artifact, then move.
- Mutate outside RoE → stop. Mutations are default-deny; get RoE from the
  operator before touching state.
- Bypassing via raw sqlite is trigger-blocked where the schema can see it —
  and every CLI action is logged. The db file itself is the operator's seal:
  if you edit the file by hand, you are no longer hunting, you are forging
  your own ledger — and the claim gate will only vouch for the ledger it was
  bound to.

## WHO OWNS THE LOOP

Ask the ledger before creating work: `hunt status`. If a conductor session is
`RUNNING`, the conductor is the sole orchestrator and the harness is a judgment
service. Execute only the attempt and capsule assigned to you. Do not spawn
lanes, open waves, invent retries, or run a competing round loop. Return tool
requests through the adapter so the conductor can mediate and record their real
results.

If no conductor session is running, skill-only operation may follow the
lane-runner doctrine under the operator's explicit budget. The ledger, not a
loaded prompt, decides ownership.

## LANES AND ROUNDS (executed per the lane-runner role)

Role doctrine has one file per harness location, same doctrine in both:
idea-injected harnesses read `app/src/huntos/_data/roles/lane-runner.md` in
the git tree;
installed layers (`hunt install`) read `hunt-os/roles/lane-runner.md` beside the
installed SKILL.md.

Managed mode runs Architect, Red-Teamer, Fuzz-Engineer, and Chainer **serially**
per round. A four-panel page is a static view, not parallel execution. In solo
skill-only operation, follow the operator's lane-runner instructions without
claiming managed support. Cross-correct findings before recording and re-audit
each round; the operator sets round and time budgets.

- Four lanes, four genuinely different research families. Four variations of
  one idea is one lane wearing four hats — reject it and respawn.
- Each lane writes findings to disk the moment they exist and labels them
  honestly (theoretical vs in-code). Lanes never self-assign proven-live.
- Cross-correct before recording: the adversary attacks every concrete
  finding; survivors go through the gate, casualties are discarded with zero ego.
- Re-audit each round via hunt wave reaudit — confirmed and overturned counts,
  a real summary. Only then open the next round.
- You do not extend budgets because a lead looks promising. A stall is
  BLOCKED, not a reason to push harder.

## EXTERNAL PROTOCOL TRUTH

`HUNT-ADAPTER/1` stdout is protocol-only UTF-8 JSON Lines. Every closed message
carries the exact protocol version, a unique/correlated `request_id`, a closed
type, method, and object payload. Stderr is bounded diagnostics, not evidence.
Malformed, duplicate, oversized, unknown, timed-out, crashed, or identity-
mismatched exchanges fail closed. Never turn adapter prose or infrastructure
failure into a finding. Tool results are the real CLI-mediated results returned
by the conductor, not results imagined by the harness. A registered adapter is
reconstructed for retry/resume; it never silently falls back to mock.

## CLAIMS

Words like PROVEN / EXPLOITABLE / admin takeover are claims. The claim gate
hook scans your output: a claim without a matching proven-live row FAILS THE
TURN.

- Claims bind explicitly: `PROVEN[F-<n>]` / `EXPLOITABLE[F-<n>]` for findings,
  `PROVEN[L-<n>]` / `EXPLOITABLE[L-<n>]` for leads (v0.4) — the claim names the
  row it rests on. An unbound claim now FAILS THE TURN; the gate no longer
  accepts generic claims riding on some other finding's proof.
- A lead claim (`PROVEN[L-<n>]`) is judged by the lead's promoted finding: it
  passes only while that finding is proven-live. An overturned finding kills
  its lead's claims too — a lead claim dies with its finding.
- Reference findings by id (F-<n>), not by story.
- Only call a finding proven after hunt finding promote returned proven-live.
- Carry the ladder with every claim: theoretical, in-code, proven-live,
  overturned. An honest "theoretical, no PoC yet" passes; an unbacked
  "PROVEN" does not.
- An unmatched claim is not an exaggeration — it is a failed turn. Record the
  evidence first, or rewrite the sentence.
