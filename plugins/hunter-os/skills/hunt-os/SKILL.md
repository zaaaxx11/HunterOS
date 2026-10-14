---
name: hunt-os
description: HUNT-OS hunting skills router - load during security, bug-bounty, web2/web3 audit, and offensive-recon work; routes into the HUNT-OS hunting skills corpus (50 skills across the catalog) one skill at a time, on demand.
---

# HUNT-OS - hunting skills router

Installed by HUNT-OS v1.3.0 (router mode).

## THE ONE RULE

The database is the only ledger. Everything you find, claim, climb, or report MUST go through the hunt CLI.

## WHO OWNS THE LOOP

Before running any hunt loop yourself (spawning lanes, opening a wave, re-auditing), ask the ledger: `hunt status`. If there is a conductor session with status RUNNING, HUNT-OS is the orchestrator — you are a judgment service. Execute ONLY the attempt you were given, never spawn lanes or open waves. If no such session exists, this layer runs solo and you follow the bridge and lane-runner doctrine yourself. One owner per session: the answer always comes from the ledger, never from guessing which doctrine was loaded.

## SKILLS INDEX (read first, load on demand)

# skills/INDEX.md — the skills router

The engine reads this file FIRST. It never bulk-loads the skills tree: it
picks the category that matches the target, then loads specific skills on
demand — one skill at a time, only what the lane needs. `<name>` resolves to
`app/src/huntos/_data/idea/skills/<category>/<name>/SKILL.md` in the git tree
(`hunt-os/skills/<category>/<name>/SKILL.md` in an installed layer); how a
load resolves per harness is in the LOADING DOCTRINE at the bottom.

Five categories: `recon/`, `web2/`, `web3/`, `cdc/`, `verification/`.

## recon/ — targeting and attack-surface discovery

- predator-recon — industrial-scale recon arsenal (wadgamer10 pipeline x yaklang)
- web2-spa-recon — SPA-decoy Next/Nuxt/Vite: catch-all traps, real-API extraction from JS chunks, Firebase triage (Colb/Nuxaris/BC Swap/Alltoscan/Bityuan/VersatizeCoin cases)
- web2-admin-takeover — automated admin takeover via JS bundle analysis
- cloudflare-waf-graphql-recon — bypass Cf-Mitigated challenge + GraphQL single-endpoint

## web2/ — web application and API attack

- web2-attack-surface-audit — full web2 attack-surface audit
- adversarial-exploit-chains — adversarial exploit chain construction
- bug-bounty-agent — bug bounty agent workflow
- disk-space-session-safety — disk-space and session safety for long runs
- web2-api-security-patterns — HMAC/OAuth/CORS/Shopify API security patterns
- nextjs-authn-authz-probing — Next.js authn/authz probing
- nextauth5-detection — detect NextAuth v5 deployments and version-specific weaknesses
- spa-live-backend-discovery — CDP-driven discovery of the real API base behind an SPA
- frontend-security-audit — client-side security audit (XSS and friends)
- js-secret-scanner — hunt secrets in shipped JavaScript bundles
- github-secret-hunt — hunt leaked secrets across GitHub
- saas-supply-chain-exploitation — exploit SaaS integrations and third-party trust
- wallet-auth-bypass-audit — audit wallet-based auth flows for bypass
- business-logic-invariant-hunt — payment/refund/IDOR/race invariant attacks
- adversarial-bug-bounty-hunting — adversarial posture for bounty programs
- mcp-security-audit — MCP server audit (path traversal %2e, ReDoS)
- web-blocked-page-recovery — 403/429/paywall/bot-wall recovery playbook

## web3/ — blockchain and protocol audit

- black-swan-engine — 19 universal laws of EVM vulnerability (CDC backbone)
- evm-contract-audit — EVM contract audit against 875 hack patterns
- smart-contract-exploit-pocs — exploit PoC library and construction
- token-transfer-audit — audit token transfer paths and hooks
- defi-protocol-analysis — DeFi protocol economic/mechanism analysis
- defi-audit-verification — verify DeFi audit claims vs source
- lending-protocol-fork-audit — lending-fork-specific audit playbook
- on-chain-exploit-workflow — end-to-end on-chain exploit workflow
- on-chain-forensics — post-incident on-chain forensics
- cross-contract-chain-builder — build cross-contract exploit chains
- custom-chain-rpc-exploit — RPC attack surface of custom chains
- blockchain-node-audit — node implementation audit
- blockchain-rpc-attack-surface-audit — RPC attack-surface audit
- rust-p2p-edge-case-audit — Rust P2P edge-case audit
- l2-rollup-audit — L2 rollup audit
- erc4337-bundler-audit — ERC-4337 bundler audit
- cdc-blockchain-audit — CDC blockchain audit loop
- rate-limited-chain-recon — rate-limited chain reconnaissance

## cdc/ — CDC multi-agent hunt methodology

- multi-target-cdc-audit — batched sequential CDC audit for multi-target ecosystems (GitHub orgs + live endpoints), per-target scan reports
- cdc-web-app-bug-bounty — CDC web app bug bounty hunting with 4-agent orchestration (Arkose/Chia/Wyze/EDBank case refs)
- cdc-lending-audit-foundry-poc — CDC 4-agent lending-fork audit with Foundry PoC testing
- cdc-device-audit — CDC audit for device/IoT local web interfaces and firmware
- sovereign-ops-protocol — persistence contract for long hunts (10-round floor, cross-steering) plus reporting style protocol

## verification/ — evidence discipline and engineering rigor

- audit-verification-methodology — verify audit claims against actual source code before repeating them
- poc-reverification — re-verify saved PoCs against the live target before building on them (stale indicators, old cookies, patched chains)
- dynamic-fuzz-testing — dynamic fuzz and property-based testing for Python/ML codebases
- systematic-debugging — 4-phase root-cause debugging: understand bugs before fixing
- test-driven-development — TDD discipline: RED-GREEN-REFACTOR, tests before code
- requesting-code-review — pre-commit review: security scan, quality gates, auto-fix

## LOADING DOCTRINE

1. The engine reads THIS file first. It never bulk-loads the skills tree.
2. On demand it loads ONE skill at a time — the name must appear in this index
   or the reference is broken (CI enforces this for every `skill_view` in
   `IDEA.md`). How a single-skill load resolves is harness-dependent:
   - Hermes: `skill_view(name='<name>')` resolves to
     `app/src/huntos/_data/idea/skills/<category>/<name>/SKILL.md`
   - Claude Code / ZCode: native skill discovery via frontmatter (`name:` +
     `description:`). Router mode: the entry skill is `hunt-os` and skills are
     read from its nested `skills/` tree on demand. Native mode: they appear
     as `hunt-<category>-<name>`.
   - generic harness: read the SKILL.md file directly by path
     (`app/src/huntos/_data/idea/skills/<category>/<name>/SKILL.md` in the
     git tree, `hunt-os/skills/<category>/<name>/SKILL.md` when installed).
3. Lane loadouts — one line per DISPATCHED lane; these are exactly the four
   lanes the conductor machine dispatches (`db.CONDUCTOR_LANES`):
   - Architect (`architect`) ← surface/web2-attack-surface-audit
   - Red-Teamer (`red_teamer`) ← web2-admin-takeover, nextjs-authn-authz-probing, business-logic-invariant-hunt
   - Fuzz-Engineer (`fuzz_engineer`) ← dynamic-fuzz-testing, systematic-debugging
   - Chainer (`chainer`) ← adversarial-exploit-chains, cross-contract-chain-builder
   NOT a dispatched lane: Verifier ← audit-verification-methodology,
   poc-reverification. The Verifier is a review role, invoked on evidence
   when a claim must be verified — it is pulled in when the evidence
   requires it, never spawned as a fifth lane.
4. A skill never bypasses the gate: see `skills/README.md` (this directory)
   for the contract every landed skill is held to.

## HUNT-BRIDGE - the hunt-ledger contract

(source: `huntos/_data/idea/HUNT-BRIDGE.md`)

# HUNT-BRIDGE — Public Assessment Session Contract

This contract is injected into authorized assessment sessions by the installer.
The source path is `app/src/huntos/_data/idea/`; installed layers use the same
files beside the `hunt-os` skill. Pair with the claim gate hook at
`app/src/huntos/_data/bin/claim_gate.py` (installed as
`hunt-os/hooks/claim_gate.py`). This document grants no authorization.

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
baseline; a request submitted or a tool invoked is not proof. Stop and escalate
if a test may affect availability, confidentiality, real users or data, or if
scope, identity, safety, or evidence integrity becomes uncertain.

## THE CLI IS THE WRITE DOOR

The `hunt` CLI is the sole persistence path. Every finding, observation,
evidence item, verification, review, phase transition, artifact, and report
must be recorded as soon as it exists. If it is not in the ledger, it is not a
record. Do not edit the database directly, reconstruct state from chat, or
write a report from memory. Use the installed CLI help for the current command
syntax; never invent a command result.

The public compatibility surface includes these command families where enabled:
`hunt status`, `hunt brief`, `hunt finding`, `hunt lead`, `hunt verify`,
`hunt poc`, `hunt challenge`, `hunt phase`, `hunt artifact`, `hunt report`,
`hunt score`, and `hunt target roe`. Availability and permissions are determined
by the installed CLI and the RoE. A blocked command is a stop condition, not an
invitation to bypass the gate or use raw SQLite.

## RECORDS AND EVIDENCE

- Add a finding or hypothesis with an honest initial status: **theoretical**.
- Attach the source, scope, assumptions, test conditions, and artifact through
  the CLI. Do not treat a hypothesis as evidence.
- Run only authorized, minimal tests. Record actual output or an explicit
  failure; never fabricate a transcript, hash, screenshot, or result.
- Independent verification and adversarial review are required before calling a
  material result verified. Refuted, inconclusive, and blocked are valid
  outcomes.
- Promote claims only when the ledger's evidence requirements are satisfied.
  Use precise status labels and bind claims to their ledger record when the
  claim gate requires an identifier.
- Generate reports with `hunt report` so they are derived from the ledger and
  retain the available integrity checks.

The evidence ladder is: **theoretical → in-code/reproducible → verified**;
**overturned** may occur at any stage. Confidence never exceeds evidence
quality. A new test must be materially different and authorized; do not repeat
stalled attempts merely to obtain a preferred result.

## LEAD LANE

A lead is a bounded hypothesis, not a finding or proof. Keep its trigger,
impact, scope, assumptions, and falsifier explicit, then record it through the
ledger before taking a next step.

- Register the hypothesis with `hunt lead add --target <id> --title "<hypothesis>"`.
- Ask for the deterministic next precondition with `hunt lead next --lead <id>`.
- Record an authorized observation with `hunt lead mutate --lead <id> ...` and its evidence.
- Set each trigger or impact half with `hunt lead set-half --lead <id> ...` only when evidence supports it.
- Park an unresolved lead with `hunt lead park --lead <id> --retrigger "<observable> :: <check>"`.
- Reopen a parked lead with `hunt lead reopen --lead <id> --evidence "<observation>"` when its tripwire fires.
- Promote only when both halves are supported: `hunt lead promote --lead <id> ...`.

A blocked, refuted, ambiguous, or parked lead is a valid outcome. Never turn a
lead into a claim by narration, and never broaden its scope without a new RoE
decision.

## ADVERSARIAL REVIEW

Before finalizing a conclusion, challenge the mechanism and impact: what would
refute it, what simpler explanation fits, what was not examined, and which
assumption is weakest? Record the challenge and outcome through the CLI. Keep
observation, inference, and conclusion distinct. An honest failure or
uncertainty is preferable to an unsupported positive claim.

## PRIVACY AND HANDLING

Collect and retain the minimum necessary evidence. Use fixtures, synthetic
values, masking, and redaction. Remove secrets, tokens, credentials, personal
data, and unrelated identifiers from reports and diagnostics. Follow approved
storage, access, retention, and disclosure rules. If sensitive data or an
active incident appears, stop, preserve only the minimum relevant context, and
escalate through the RoE contact.

## STOP AND ESCALATE

Stop immediately when authorization or scope is unclear; a planned action may
be harmful, disruptive, irreversible, or outside the RoE; a safety or privacy
boundary is approached; a control behaves unexpectedly; evidence is
contaminated or missing; or an incident is suspected. State the reason,
record the stop, preserve minimal authorized evidence, and await direction.
Never bypass a gate, conceal a test, evade monitoring, or continue because a
hypothesis appears promising.

**HUNT-BRIDGE — public/free, role-neutral contract. The ledger and CLI enforce
state; this text does not grant capability or permission.**

## WHERE THE SKILL BODIES LIVE

Skill bodies live at `skills/<category>/<name>/SKILL.md`, relative to this SKILL.md file. Never bulk-load them: pick the category from the index above, then read the one skill the lane needs.

## ROLE DOCTRINE (installed paths - read roles from HERE)

The lane roles travel with this installed layer (law: roles travel with the hunt layer). lane-runner, architect, red-teamer, fuzz-engineer, chainer, adversary, and verifier live at `roles/<name>.md`, relative to this SKILL.md file. When HUNT-BRIDGE (embedded above) points at `huntos/_data/roles/...`, the packaged location for idea-injected harnesses -- in THIS installed layer read `roles/lane-runner.md` (and the other roles) from beside this file, without the package checkout.
