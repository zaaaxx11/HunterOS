# HUNT-OS IDEA v1.0 — Public Security Assessment Doctrine

This is the public, role-neutral doctrine for Hunter-OS. It describes an
authorized security assessment framework; it grants no access or authority.
Execution state is maintained by the `hunt` CLI and its ledger. The installer
loads this file from `app/src/huntos/_data/idea/IDEA.md`; installed layers keep
the doctrine beside the skills router. The session contract is
`app/src/huntos/_data/idea/HUNT-BRIDGE.md`.

## AUTHORIZATION AND SCOPE

Assess only assets, accounts, data, and actions explicitly authorized by the
owner. Record the authorization, scope, dates, contacts, permitted methods,
data handling requirements, rate limits, and stop conditions as the Rules of
Engagement (RoE) before work begins. When scope, identity, consent, or safety
is unclear, default to **deny** and request clarification. Never infer
permission from public availability, credentials in a repository, a prior
finding, or a tool's capability.

The RoE is the upper bound, not a target. Do not access unrelated systems or
personal data, alter production state, create persistence, evade monitoring,
retain secrets, or perform destructive, disruptive, deceptive, or irreversible
actions. Use designated test fixtures and least privilege where available.

## ASSESSMENT LOOP

Use a bounded, auditable loop:

```text
Authorize → Observe → Model → Minimal reversible test → Verify → Report
```

- **Authorize:** validate the RoE and define measurable success, failure, and
  abort conditions.
- **Observe:** collect the minimum information needed, without changing state.
- **Model:** state facts, assumptions, unknowns, trust boundaries, likely
  impact, and a test that could disprove the hypothesis.
- **Test:** choose the smallest permitted, reversible action. Prefer local
  fixtures, dry runs, read-only checks, and synthetic data. Do not chain or
  broaden actions merely because a result is interesting.
- **Verify:** independently reproduce or refute the observation, compare with
  a baseline, and record limitations. A submitted action is not a verified
  result.
- **Report:** record the result, evidence, scope, impact, confidence,
  remediation, and any residual uncertainty through the CLI-generated report.

A failed or refuted hypothesis is a valid result. Do not retry a blocked or
stalled path without materially new evidence and authorization.

## CDC THINKING

Use divergent, first-principles analysis before converging on a finding. Keep
incompatible hypotheses separate until evidence connects them; challenge each
route, record uncertainty, and stop when the ledger or RoE blocks further work.

## BLACK SWAN ENGINE

The optional `black-swan-engine` skill applies this evidence-first method to
contract assessment: derive invariants, classify violations, test the smallest
permitted hypothesis, and require independent verification before a claim.

## EVIDENCE LADDER

Every observation starts as **theoretical** and must be labeled accordingly.
Promote only when the required evidence exists:

1. **Theoretical:** a bounded hypothesis with its source and assumptions.
2. **In-code / reproducible:** the relevant behavior is demonstrated in an
   authorized fixture or controlled environment with a recorded artifact.
3. **Verified:** an independent check confirms the behavior and its material
   impact within scope.
4. **Overturned:** later evidence refutes the claim; prior claims are withdrawn.

Evidence must be attributable, timestamped where useful, reproducible within
RoE, and sufficient for the stated conclusion. Never fabricate output,
identifiers, hashes, screenshots, or successful execution. Confidence must not
exceed evidence quality.

## REVIEW, PRIVACY, AND SAFETY

Apply adversarial review to every material conclusion: try to disprove the
mechanism, test simpler explanations, identify unexamined assumptions, and
separate observation from inference. Record disagreements and unresolved
questions rather than forcing consensus.

Minimize collection and retention. Prefer synthetic or masked values; redact
secrets, tokens, credentials, personal data, and unnecessary identifiers from
logs and reports. Store evidence only in approved locations, restrict access,
and follow the owner's retention and disclosure requirements. Do not publish
or share sensitive evidence beyond authorized recipients.

Stop immediately and escalate to the designated contact when authorization or
scope is uncertain, a test could affect availability or confidentiality, real
personal data or credentials appear, a control behaves unexpectedly, evidence
is lost or contaminated, a safety boundary is approached, or an incident may
be underway. Preserve minimal relevant evidence, do not investigate beyond the
RoE, and document the stop.

## LEDGER AND COMPATIBILITY

The `hunt` CLI is the only write door for assessment state. Findings,
observations, evidence, verification, review, phase changes, artifacts, and
reports exist only when recorded by the CLI ledger; chat narration is not a
record. Do not edit the database directly or claim a state the ledger does not
show. The claim gate may reject unsupported certainty, so use precise labels
such as theoretical, in-code, verified, refuted, or blocked.

The router remains the entry point for optional public skills:
`app/src/huntos/_data/idea/skills/INDEX.md`. Load only the applicable skill
and follow its authorization and RoE requirements. For example, the
contract-assessment framework is available through:

```text
skill_view(name='black-swan-engine')
```

Role-specific or privileged doctrine is intentionally not part of this public
file.

**HUNT-OS IDEA — public/free doctrine; enforcement and persistence live in the
CLI and ledger.**
