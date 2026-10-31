---
description: Set, inspect, or raise a HUNT-OS wave's iteration budget
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target. A budget bounds effort; it never widens scope.

Use the `hunt-os` skill router for the workflow.

1. Open a wave with a budget: `hunt wave open <target_id> "<lanes>" --budget <N>`. Omit `--budget` for unbounded — a recorded decision, not a default.
2. Inspect spend: `hunt wave budget --wave-id <id>` prints used/limit/remaining, or `EXHAUSTED`.
3. Raise it when the work genuinely needs more: `hunt wave budget --wave-id <id> --set <M> --reason "<why the limit moves>"`. The reason is required and is logged beside the old and new values.
4. When the budget is spent, close the wave: `hunt wave close --wave-id <id> --verdict <continue|exhausted|pivot>`, then `hunt wave reaudit --wave-id <id> --summary "<confirmed/overturned and why>"`.

Claim constraints: the counter is computed by the CLI, never typed — the same law that makes `findings_new` computed. Lowering a budget below spend already recorded is refused, because that would hide work that happened. A spent wave refuses new findings, lead mutations, and fuzz probes until it is closed or explicitly raised.

Stop when: a raise would need a reason you cannot state honestly, or the wave's remaining budget cannot cover the next authorized step.
