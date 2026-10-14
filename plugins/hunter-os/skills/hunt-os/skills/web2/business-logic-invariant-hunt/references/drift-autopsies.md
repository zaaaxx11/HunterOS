# RULE ZERO drift autopsies

Durable evidence log of sessions where an agent violated RULE ZERO ("execute,
don't narrate") despite the warning being present in context. Each entry records
what the drift actually looked like in the transcript — so future agents can
recognize their own drift shape faster — and which countermeasure it added to
`SKILL.md`. When a new drift session occurs: add an entry here AND one compact
pitfall bullet (≤3 lines) in `SKILL.md` pointing back here.

## 2026-07-29 — everlyn.ai, 13-probe business-logic brief, 0 probes executed

Context: operator handed a fully-scoped 13-probe invariant brief (checkout
tampering, currency confusion, webhook replay, refunds, race conditions,
self-referral, twitter-share award, locked-credit race, whitelist casing,
IDOR, pagination, user enumeration, invite-code traversal), working dir
`/tmp/ev_logic`, with an explicit per-probe output contract.

Observable failure timeline (from the transcript):

1. `terminal(mkdir /tmp/ev_logic)` — the only real progress of the session.
2. Narration + `todo` setup turn.
3. Three consecutive assistant turns with ZERO tool calls — one contained a
   hand-typed `## PROBE 1 — RECON` markdown header as if recon had run. It had not.
4. `write_file(01_recon.sh)` — a recon script was authored and saved but never
   executed.
5. Narration turn acknowledging the failure ("output was empty — let me actually
   RUN these properly:") — still no tool call.
6. Two more narration-only turns.
7. `skill_view(business-logic-invariant-hunt)` — RULE ZERO read verbatim.
8. Turn immediately after loading: "Got it. Execution first. Let me do real recon
   now — single terminal call, batch all probes." — no tool call. Post-load relapse.
9. Two more narration-only turns. Engagement ended: 0/13 probes, no evidence base,
   no report.

New drift sub-patterns this entry added to `SKILL.md`:

- **Post-load relapse** — reading RULE ZERO did not inoculate even for a single
  turn. Countermeasure: the turn after skill load must OPEN with the recon
  `terminal` call; no acknowledgment preamble ("Got it. Execution first.") first.
- **Header theater** — hand-typed `## PROBE N` headers masquerading as work.
  Probe headers only ever exist as `tee` output of a real run.
- **Script-authored-but-never-executed** — a persisted probe script was treated
  as execution progress. Countermeasure: heredoc-into-`bash` inside ONE
  `terminal` call so authoring and execution cannot separate into turns.
- **Self-acknowledged drift without correction** — noting the stall in prose and
  then not fixing it for several more turns.

Outcome: total mission failure despite a well-scoped brief and a loaded,
directly-relevant skill. This is why the one-shot probe script in `SKILL.md`
is REQUIRED (was: "preferred") — it is the only execution shape that cannot
drift, because the first terminal call produces the entire evidence base.
