---
description: Generate a HUNT-OS disclosure report from the ledger and verify its integrity footer
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target and that the disclosure recipients are authorized. Reports contain evidence, so redact secrets, tokens, and personal data before sharing.

Use the `hunt-os` skill router for the workflow.

1. Generate the report from the ledger: `hunt report <target_id> [--out <path>]`. `--out` also stamps the disclosure_report artifact. Do not write a report from memory.
2. Check the report's sha256 footer: `hunt verify-report <path>`. A BLOCKED result means the file was tampered with; do not send it.

Claim constraints: the report may state only what the ledger records. Findings must appear with their ledger status. Do not describe any result as PROVEN or EXPLOITABLE unless the claim gate binds it to a `proven-live` finding.

Stop when: `verify-report` reports tampering, the target has no promoted findings to report, or the disclosure recipient is not authorized by the RoE.
