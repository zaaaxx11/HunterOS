---
description: Record an independent HUNT-OS verifier event or adversary challenge on a finding
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target. Verification re-runs or re-observes behavior, so it must stay inside the RoE.

Use the `hunt-os` skill router for the workflow.

1. Record an independent verifier event: `hunt verify <finding_id> <fork_receipt|tx_hash|http_transcript> "<body>" [--role <role>]`. The body must be the actual captured output, not a summary.
2. Record an adversary review: `hunt challenge <finding_id> "<notes>" [--role <role>]`. Try to disprove the mechanism and test simpler explanations.
3. Run or re-run the PoC inside the ledger when needed: `hunt poc run --id <finding_id> --poc-path <path> [--timeout <seconds>]`.

Claim constraints: a finding cannot become `proven-live` without a verifier event and an adversary challenge recorded in the ledger. Do not record a verification you did not perform. Never fabricate a transcript, receipt, or hash.

Stop when: the verifier cannot reproduce the behavior (record it as refuted or blocked), the challenge refutes the mechanism, or verification would require an action outside the RoE.
