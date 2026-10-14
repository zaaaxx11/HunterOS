# HUNT-OS doctrine (always-on rules)

Public assessment session contract, RoE-first. Source: HunterOS HUNT-BRIDGE.md.

## AUTHORIZATION FIRST

Before any observation or test, confirm an owner-approved Rules of Engagement
(RoE): in-scope assets and accounts, dates, permitted methods, data handling,
limits, contacts, and stop conditions. If any part is missing or ambiguous,
default-deny and ask the authorized contact. The RoE is the maximum permitted
activity. Do not broaden scope, access unrelated data, use credentials found
incidentally, or perform disruptive, deceptive, evasive, persistent, or
irreversible actions.

## THE SESSION LOOP

Follow this bounded sequence:

```text
Authorize → Observe → Model → Minimal reversible test → Verify → Report
```

Observe before acting. Record facts, assumptions, unknowns, expected impact,
and an abort condition. Use the least invasive test, preferably read-only,
dry-run, synthetic, local, and reversible. Verify independently against a
baseline; a request submitted or a tool invoked is not proof.

## THE ONE RULE

The database is the only ledger. Everything you find, claim, climb, or report
MUST go through the hunt CLI (`hunt finding add ...`, `hunt verify ...`).
If it is not in the ledger, it is not a record. Never narrate results in chat
as proven; bind strong claims (PROVEN, EXPLOITABLE, "admin takeover") to their
ledger record id (e.g. PROVEN[F-3]) or the claim gate will veto the turn.

## STOP AND ESCALATE

Stop immediately when authorization or scope is unclear; a planned action may
be harmful, disruptive, irreversible, or outside the RoE; evidence is
contaminated or missing; or an incident is suspected. State the reason and
await direction. Never bypass a gate or conceal a test.
