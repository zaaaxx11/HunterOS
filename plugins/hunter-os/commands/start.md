---
description: Begin a HUNT-OS assessment by registering an authorized target and its Rules of Engagement
---

FIRST: Confirm an owner-approved Rules of Engagement (RoE) exists for this target: in-scope assets, dates, permitted actions, data handling, rate limits, contacts, and stop conditions. If it does not, stop and ask. Do not take any active action without it.

Use the `hunt-os` skill router for the workflow.

1. Register the target: `hunt target add <name> <url>`. Optional flags: `--chain`, `--age-days`, `--tvl`, `--notes`.
2. Record the RoE: `hunt target roe <target_id> --hosts "<hosts>" --actions <recon,read,auth-test,mutate>`. Actions not listed are default-denied, and `mutate` is denied unless explicitly listed.
3. Read the opening brief: `hunt brief <target_id>`.

Claim constraints: do not describe any result as PROVEN or EXPLOITABLE unless the claim gate can bind it to a `proven-live` finding. Unbound claims are vetoed.

Stop when: the RoE is missing or ambiguous, the target is out of scope, or the brief shows the target is already archived.
