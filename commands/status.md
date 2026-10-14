---
description: Show the HUNT-OS ledger status and the single recommended next step (read-only)
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target you are reporting on. This command is read-only, but do not act on its output without a valid RoE.

Use the `hunt-os` skill router for the workflow.

1. Show ledger status: `hunt status`
2. Show the recommended next command for a target: `hunt next --target <target_id>`. This prints the recommendation only; it never executes it. Run it only after reviewing it against the RoE.

Claim constraints: report what the ledger shows, not what you expect. Do not describe any result as PROVEN or EXPLOITABLE unless the claim gate binds it to a `proven-live` finding.

Stop when: the ledger reports a blocked state, or the RoE no longer covers the next recommended action.
