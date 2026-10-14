---
description: Record a theoretical HUNT-OS finding and climb its evidence ladder with the hunt CLI
---

FIRST: Confirm an owner-approved Rules of Engagement exists for the target. Do not record or test a finding outside it.

Use the `hunt-os` skill router for the workflow.

1. Record a theoretical finding: `hunt finding add <target_id> "<title>" <klass> --severity <critical|high|medium|low|info> --action <recon|read|auth-test|mutate> --falsifier "<observation that would disprove it>"`. The class must be an existing taxonomy class (check with `hunt klass list`) or `Unknown`. Add `--surface <row>` when it was found on a mapped surface.
2. Climb the ladder only with evidence: `hunt poc run --id <finding_id> --poc-path <path>` records the exit code and output, then `hunt finding promote --id <finding_id> --evidence-ref <ref> --poc-path <path>`.
3. Record a verifier event: `hunt verify <finding_id> <fork_receipt|tx_hash|http_transcript> "<body>"`. Record an adversary review: `hunt challenge <finding_id> "<notes>"`.

Claim constraints: a finding is theoretical until the ledger shows it promoted. Any PROVEN or EXPLOITABLE statement must be bound to its id, for example `PROVEN[F-3]`, and the claim gate passes it only if the finding is `proven-live`. Never fabricate PoC output or hashes.

Stop when: the RoE does not cover the action, the PoC fails to run, or the adversary review refutes the finding. A refuted finding is a valid result; record it with `hunt finding overturn --id <finding_id> --by "<adversary evidence>"`.
