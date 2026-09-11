# HUNT-BRIDGE — Public Assessment Session Contract

This contract is injected into authorized assessment sessions by the installer.
The source path is `app/src/huntos/_data/idea/`; installed layers use the same
files beside the `hunt-os` skill. Pair with the claim gate hook at
`app/src/huntos/_data/bin/claim_gate.py` (installed as
`hunt-os/hooks/claim_gate.py`). This document grants no authorization.

## AUTHORIZATION FIRST

Before any observation or test, confirm an owner-approved Rules of Engagement
(RoE): in-scope assets and accounts, dates, permitted methods, data handling,
limits, contacts, and stop conditions. If any part is missing or ambiguous,
default-deny and ask the authorized contact. The RoE is the maximum permitted
activity. Do not broaden scope, access unrelated data, use credentials found
incidentally, or perform disruptive, deceptive, evasive, persistent, or
irreversible actions.

## THE SESSION LOOP

Follow this bounded sequence:

```text
Authorize → Observe → Model → Minimal reversible test → Verify → Report
```

Observe before acting. Record facts, assumptions, unknowns, expected impact,
and an abort condition. Use the least invasive test, preferably read-only,
dry-run, synthetic, local, and reversible. Verify independently against a
baseline; a request submitted or a tool invoked is not proof. Stop and escalate
if a test may affect availability, confidentiality, real users or data, or if
scope, identity, safety, or evidence integrity becomes uncertain.

## THE CLI IS THE WRITE DOOR

The `hunt` CLI is the sole persistence path. Every finding, observation,
evidence item, verification, review, phase transition, artifact, and report
must be recorded as soon as it exists. If it is not in the ledger, it is not a
record. Do not edit the database directly, reconstruct state from chat, or
write a report from memory. Use the installed CLI help for the current command
syntax; never invent a command result.

The public compatibility surface includes these command families where enabled:
`hunt status`, `hunt brief`, `hunt finding`, `hunt lead`, `hunt verify`,
`hunt poc`, `hunt challenge`, `hunt phase`, `hunt artifact`, `hunt report`,
`hunt score`, and `hunt target roe`. Availability and permissions are determined
by the installed CLI and the RoE. A blocked command is a stop condition, not an
invitation to bypass the gate or use raw SQLite.

## RECORDS AND EVIDENCE

- Add a finding or hypothesis with an honest initial status: **theoretical**.
- Attach the source, scope, assumptions, test conditions, and artifact through
  the CLI. Do not treat a hypothesis as evidence.
- Run only authorized, minimal tests. Record actual output or an explicit
  failure; never fabricate a transcript, hash, screenshot, or result.
- Independent verification and adversarial review are required before calling a
  material result verified. Refuted, inconclusive, and blocked are valid
  outcomes.
- Promote claims only when the ledger's evidence requirements are satisfied.
  Use precise status labels and bind claims to their ledger record when the
  claim gate requires an identifier.
- Generate reports with `hunt report` so they are derived from the ledger and
  retain the available integrity checks.

The evidence ladder is: **theoretical → in-code/reproducible → verified**;
**overturned** may occur at any stage. Confidence never exceeds evidence
quality. A new test must be materially different and authorized; do not repeat
stalled attempts merely to obtain a preferred result.

## LEAD LANE

A lead is a bounded hypothesis, not a finding or proof. Keep its trigger,
impact, scope, assumptions, and falsifier explicit, then record it through the
ledger before taking a next step.

- Register the hypothesis with `hunt lead add --target <id> --title "<hypothesis>"`.
- Ask for the deterministic next precondition with `hunt lead next --lead <id>`.
- Record an authorized observation with `hunt lead mutate --lead <id> ...` and its evidence.
- Set each trigger or impact half with `hunt lead set-half --lead <id> ...` only when evidence supports it.
- Park an unresolved lead with `hunt lead park --lead <id> --retrigger "<observable> :: <check>"`.
- Reopen a parked lead with `hunt lead reopen --lead <id> --evidence "<observation>"` when its tripwire fires.
- Promote only when both halves are supported: `hunt lead promote --lead <id> ...`.

A blocked, refuted, ambiguous, or parked lead is a valid outcome. Never turn a
lead into a claim by narration, and never broaden its scope without a new RoE
decision.

## ADVERSARIAL REVIEW

Before finalizing a conclusion, challenge the mechanism and impact: what would
refute it, what simpler explanation fits, what was not examined, and which
assumption is weakest? Record the challenge and outcome through the CLI. Keep
observation, inference, and conclusion distinct. An honest failure or
uncertainty is preferable to an unsupported positive claim.

## PRIVACY AND HANDLING

Collect and retain the minimum necessary evidence. Use fixtures, synthetic
values, masking, and redaction. Remove secrets, tokens, credentials, personal
data, and unrelated identifiers from reports and diagnostics. Follow approved
storage, access, retention, and disclosure rules. If sensitive data or an
active incident appears, stop, preserve only the minimum relevant context, and
escalate through the RoE contact.

## STOP AND ESCALATE

Stop immediately when authorization or scope is unclear; a planned action may
be harmful, disruptive, irreversible, or outside the RoE; a safety or privacy
boundary is approached; a control behaves unexpectedly; evidence is
contaminated or missing; or an incident is suspected. State the reason,
record the stop, preserve minimal authorized evidence, and await direction.
Never bypass a gate, conceal a test, evade monitoring, or continue because a
hypothesis appears promising.

**HUNT-BRIDGE — public/free, role-neutral contract. The ledger and CLI enforce
state; this text does not grant capability or permission.**
