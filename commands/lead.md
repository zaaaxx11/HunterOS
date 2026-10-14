---
description: Manage a HUNT-OS lead (bounded hypothesis) through the hunt lead lifecycle
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target. Each mutation step is an active action and must be inside the RoE.

Use the `hunt-os` skill router for the workflow.

1. Register the hypothesis: `hunt lead add --target <target_id> --title "<hypothesis>"`. Optional: `--payload`, `--precondition 'variable|value|description'` (repeatable), `--surface <row>`.
2. Get the deterministic next precondition: `hunt lead next --lead <lead_id>`.
3. Record one authorized step: `hunt lead mutate --lead <lead_id> --variable <v> --new <value> --result <advanced|unchanged|refuted|unknown> --evidence "<observation>"`.
4. Set a half by evidence only: `hunt lead set-half --lead <lead_id> --half <trigger|impact> --verdict <proven|refuted> --evidence "<observation>"`.
5. Park an unresolved lead with a testable retrigger: `hunt lead park --lead <lead_id> --retrigger "<observable> :: <check>"`. Reopen with `hunt lead reopen --lead <lead_id> --evidence "<observation>"` when the tripwire fires.
6. Promote only when both halves are proven: `hunt lead promote --lead <lead_id> --klass <klass> --roe-action <read|mutate|auth-test> --severity <level>`.

Claim constraints: a lead is a hypothesis, not a finding. Use `PROVEN[L-<n>]` only after the lead is promoted; the claim gate passes it only in that state. Never turn a lead into a claim by narration.

Stop when: a step falls outside the RoE, a half is refuted (kill or park, do not broaden scope), or the lead is parked with no tripwire.
