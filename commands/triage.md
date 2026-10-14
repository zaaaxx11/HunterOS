---
description: Triage a HUNT-OS target's leads and findings to choose the next authorized step
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target. Triage only ranks next steps; it must not start an action the RoE does not permit.

Use the `hunt-os` skill router for the workflow.

1. Review the target's open leads: `hunt lead list --target <target_id>`.
2. Ask the ledger for the single recommended next command: `hunt next --target <target_id>`. This is read-only; it never executes the command.
3. For a lead you select, get its next deterministic precondition: `hunt lead next --lead <lead_id>`.
4. Rank by RoE fit and evidence strength. Park any lead that needs an action the RoE does not allow, with `hunt lead park --lead <lead_id> --retrigger "<observable> :: <check>"`.

Claim constraints: triage produces a ranking, not a claim. Do not describe any lead or finding as PROVEN or EXPLOITABLE unless the claim gate binds it to its id in the promoted or proven-live state.

Stop when: no remaining lead is permitted by the RoE, the ledger recommends an action outside it, or the target is archived.
