# pr/ — Open problems & parked work

Parking lot for problems the schema **cannot solve today**, plus deferred work.
Every item here states: what the hole is, why the DB can't close it, what
currently mitigates it, and which future PR (if any) carries the real fix.

| File | Status |
|---|---|
| [OPEN-PROBLEMS.md](OPEN-PROBLEMS.md) | Active — read before designing any new enforcement |
| [audit/A-engineering-findings.md](audit/A-engineering-findings.md) | Round-1 engineering audit findings (the A-series) |
| [skills-landing/landing-a.md](skills-landing/landing-a.md) | Skills corpus landing log — batch A |
| [skills-landing/landing-b.md](skills-landing/landing-b.md) | Skills corpus landing log — batch B |
| [skills-landing/](skills-landing/) `*-hygiene.md` (4) | Secret-hygiene passes per landing batch — the real leaks caught before land (provider keys, PAT, private keys, keyed RPC) |
| [AUDIT-v0.3.md](AUDIT-v0.3.md) | Historical — v0.3 audit (A/B findings) |
| [AUDIT-v0.4-1-engineering.md](AUDIT-v0.4-1-engineering.md) | Historical — v0.4 engineering audit round |
| [AUDIT-v0.4-2-product.md](AUDIT-v0.4-2-product.md) | Historical — v0.4 product audit round |
| [AUDIT-CHECKLIST-leads.md](AUDIT-CHECKLIST-leads.md) | Historical — leads-lane audit checklist |
| [REVIEW-CHECKLIST-batch3.md](REVIEW-CHECKLIST-batch3.md) | Historical — batch-3 review checklist |
| [SPEC-cli-launch.md](SPEC-cli-launch.md) | **Active handoff** — CLI launch: HUNT-OS as operator for every harness (L0–L5). Builder implements from this file. Native harness / C2 / bench are out of scope. |
| [SPEC-batch3.md](SPEC-batch3.md) / [SPEC-leads-oracle.md](SPEC-leads-oracle.md) | Historical — the specs the audit rounds attacked |
| [IMPL-NOTES-batch3.md](IMPL-NOTES-batch3.md) / [IMPL-NOTES-leads.md](IMPL-NOTES-leads.md) | Historical — implementation notes + known-trap log |

Related reading: `app/WALKTHROUGH.md` § Known limits (Class B) — the operator-facing
summary. This folder is the engineering-facing version.

Rule of the house: a problem moves **out** of this folder only when something in
the repo returns exit code 2 for it — not when a document says it should.
