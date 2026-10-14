---
description: Print the opening brief for a HUNT-OS target before the next hunt round (read-only)
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target. This command is read-only, but the brief guides the next active step, so it must match the RoE.

Use the `hunt-os` skill router for the workflow.

1. Run: `hunt brief <target_id>`. The target id is an integer.
2. Summarize the brief's open leads, findings, and blocked items. Do not add new actions the brief does not list.

Claim constraints: do not describe any finding as PROVEN or EXPLOITABLE unless the claim gate binds it to a `proven-live` finding by id, for example `PROVEN[F-3]`.

Stop when: the brief reports the target archived, or it lists no permitted next action within the RoE.
