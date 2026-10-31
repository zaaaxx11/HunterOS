---
description: Track a HUNT-OS finding's untested implications as follow-up objects
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target. Chasing an implication is an active action and must be inside the RoE.

Use the `hunt-os` skill router for the workflow.

1. Register the implication: `hunt followup add <finding_id> "<title>" --kind <escalation|variant|adjacent-surface|chain-step>`. Optional: `--hypothesis "<what you expect, stated so it can fail>"`.
2. List what is still open: `hunt followup list --finding <finding_id>` (or `--target <id>`, or `--state open`).
3. Close one that held: `hunt followup verify <id> --evidence "<the observation that settled it>"`.
4. Close one that did not: `hunt followup drop <id> --reason "<what was tried and what ruled it out>"` (min 20 chars).
5. Turn one into its own finding: `hunt followup promote <id> --klass <klass> --severity <level> [--roe-action <read|mutate|auth-test>]`.

Claim constraints: a follow-up is untested work, not a result. It carries no claim of its own until it is promoted into a finding and that finding climbs the ladder. A finding cannot be promoted or overturned while it has open follow-ups, and `PROVEN[F-<n>]` on a chained finding requires every ancestor in its chain to be proven-live.

Stop when: a follow-up would take you outside the RoE, or the parent finding is overturned with every follow-up settled.
