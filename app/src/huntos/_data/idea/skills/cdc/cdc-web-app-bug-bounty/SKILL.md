---
name: cdc-web-app-bug-bounty
description: "CDC web app bug bounty hunting with 4-agent orchestration (Arkose/Chia/Wyze/EDBank case refs)"
trigger: Use when hunting for pre-auth RCE chains in web apps, APIs, or auth systems using CDC thinking and multi-agent orchestration.
---

# CDC Web App Bug Bounty Hunting Skill

## Overview
This skill codifies the Cycle Double Cover (CDC) methodology for web application bug bounty hunting, combining first-principles deconstruction, divergent exploration, chain building, and adversarial validation with a 4-agent orchestration model.

## When to Use
- Hunting for pre-auth RCE chains in web apps, APIs, auth systems
- Bug bounty programs requiring deep analysis over surface-level scanning
- Targets with complex auth flows, GraphQL, or multi-service architectures
- When standard scanning fails to find critical vulnerabilities

## CDC Thinking Protocol (Hard Rules)

### 1. DIVERGENT FIRST
- Start with 3+ genuinely different theories before any code
- Group by research IDEA, not wording (3 agents chasing "SQLi" differently = ONE family)
- Premature convergence = death — redirect overlapping agents immediately

### 2. CHAIN EVERYTHING
- Single bug is noise. Map: `[Trigger] → [Effect] → [Trust Boundary Crossed]`
- Hunt handoff points where Bug A's output becomes Bug B's input
- No finding reported without chain context

### 3. STALL = BLOCK
- 2 rounds no evidence → mark BLOCKED
- Do NOT force. Reopen only with materially new mechanism
- Prevents sunk-cost traps and token waste

### 4. ADVERSARIAL VALIDATION
- Every finding gets adversary: "Prove this ISN'T exploitable"
- Survives? Keep. Fails? Discard instantly. Zero ego.

### 5. KEEP INCOMPATIBLE ROUTES
- Winning chain often combines contradictory ideas
- Cross-pollinate ONLY after each route has independent depth
- Early sharing = groupthink

### 6. PERSISTENCE
- Minimum 10 rounds / 30 min before "nothing found" valid
- Most quit at round 2. Chain lives in round 7.

## 4-Agent Orchestration Model

| Agent | Role | Output |
|-------|------|--------|
| **Architect** | Maps trust graph, traces data/control flow, finds trust boundaries | Trust graph, input sinks, handoff points |
| **Red-Teamer** | Attacks specific functions, violates invariants, auth bypass | Broken assumptions, specific vulns |
| **Fuzz-Engineer** | Edge cases on high-risk sinks: 0/max, null, overflow, race | Crash vectors, parser differentials |
| **Chainer** | Builds exploit chain from Agent 2&3 findings | `[Trigger→Effect→Boundary]` full chain |

## Blind Spot Scanner (After Every Round)
1. What did I NOT look at? (parts skipped as "safe")
2. What would developers expect me to miss? (planted blind spots)
3. If I'm wrong, where am I wrong? (disprove own conclusion)

## Output Format (Exact)
```
VULNERABILITY: [Class/Type]
ENTRY: [Pre-auth / Post-auth / Unauth]
CHAIN: [Step 1 → Step 2 → ... → RCE]
IMPACT: [RCE / Theft / Escalation / Bypass]
POC: [Working exploit / Script / Proof — ≤50 lines]
EVIDENCE: [Line numbers or code snippets proving the chain]
CONFIDENCE: [PROVEN / HIGH / THEORETICAL]
MITIGATION: [Root cause + Fix]
VERIFICATION: Clean install → reproduce → tx hash / screenshot → minimal PoC
```

## Constraints
- NO changelogs, git history, internet searches
- NO known CVEs or public exploit-db
- NO "theoretical" — PoC required or you don't have it
- NO "potential" — only report "EXPLOITABLE"

## Pitfalls

### CSRF Classification: POST-AUTH, NOT Pre-Auth
**CRITICAL**: CSRF is a **post-auth** attack vector, NOT pre-auth.
- **Requirement**: User must be logged in (active session with cookies)
- **Attack**: User visits malicious site while session is active
- **Impact**: Request execution on behalf of authenticated user

**Do NOT classify CSRF as "PRE-AUTH"** — it requires an authenticated session.
Correct classifications:
- **PRE-AUTH**: No login required (unauthenticated queries, open endpoints)
- **POST-AUTH**: Requires login (CSRF, session hijack, privilege escalation)

### better-auth: Cookie auth, NOT Authorization header
Many GraphQL APIs use `Authorization: Bearer <token>` headers. **better-auth does NOT.** Auth is via `__Secure-better_auth_session` cookie only. If you send the token as an Authorization header, `viewer` returns `null` and all protected queries return UNAUTHENTICATED. Use `http.cookiejar.CookieJar()` + `urllib.request.build_opener(HTTPCookieProcessor(cj))` for all requests.

### WebAuthn CDP: enableUI must be false
`WebAuthn.enable({enableUI: true})` hangs forever in headless Chrome. Always use `enableUI: false`. The virtual authenticator still creates credentials without UI.

### Session expiry: better-auth sessions can rotate
Session cookies from `verifyPasskeyAssign` may expire or rotate after ~5 minutes or after certain mutations. Always run exploitation chain in the SAME Python process (same `opener` jar) immediately after obtaining the cookie. Do not save cookies to files and reuse across processes.

### Strapi V5 + Vite Dev-Server: the `?raw??` bypass family
**When a Strapi v5 admin serves `/admin/@vite/client` with 200, it runs the Vite dev server in production and leaks by default**: `GET /admin/.env?raw??` (the double `??` bypasses fs.deny) exposes `ADMIN_JWT_SECRET`/`APP_KEYS`, `/admin/.tmp/data.db` drops the SQLite DB, and `/admin/@fs/<abs>?raw??` is arbitrary file read — forge an admin JWT from the leaked secret for instant takeover. If one client on a vendor template is patched, the vendor's other clients usually are not — pivot via crt.sh to the vendor domain and its other vhosts.
(Original worked example with full exploit order and the patch-verification trap: preserved at examples/hunts/cdc/cdc-web-app-bug-bounty/case-derived-pitfall-originals.md.)

### Django DEBUG=True in production = settings-table disclosure on ANY 500
Django with `DEBUG=True` in production dumps stack traces AND the settings table (DB engine/name/user/host in cleartext, SECRET_KEY-class values masked) on any 500; `DisallowedHost` responses on sibling hostnames prove one debug-mode instance serves many client vhosts — enumerate the client list via crt.sh on the platform domain. Locate the real API base by grepping a built JS bundle for ALL URL literals (`REACT_APP_*` strings do not survive builds — download the full bundle).
(Original gorealtime/PlayMPOS worked example: preserved at examples/hunts/cdc/cdc-web-app-bug-bounty/case-derived-pitfall-originals.md.)

### On-chain user-supplied URLs consumed server-side = SSRF to cloud metadata
Where a chain stores user-supplied mirror/store URLs on-chain and a node or service later fetches them server-side without validation, an attacker-controlled mirror pointed at cloud metadata endpoints (169.254.169.254, metadata.google.internal) turns every syncing node into a credential-theft SSRF. Test with the platform's own download/sync API against an IMDS URL and enumerate what the fetcher runs as.
(Original Chia Data Layer worked example: preserved at examples/hunts/cdc/cdc-web-app-bug-bounty/case-derived-pitfall-originals.md; case refs at examples/hunts/cdc/cdc-web-app-bug-bounty/references/.)

## Multi-Agent Delegation Pattern
```python
# Spawn agents in parallel for divergent exploration
delegate_task(tasks=[
  {"goal": "Architect: map trust graph for target X", "context": "..."},
  {"goal": "Red-Teamer: attack auth bypass on target X", "context": "..."},
  {"goal": "Fuzz-Engineer: edge cases on target X sinks", "context": "..."},
  {"goal": "Chainer: build chain from findings", "context": "..."}
])
```

## References
- `references/cdc-thinking-cheatsheet.md` — Quick reference for CDC protocol
- `references/user-workflow-preferences.md` — Operator workflow preferences (sequential phases, probe-then-report)
- Case evidence from the arkose, chia, wyze, colb, ed3, edbank, grafana, nestjs, nextauth-enum, and nextjs-persisted-GraphQL hunts (19 files) is preserved at `examples/hunts/cdc/cdc-web-app-bug-bounty/references/` — moved out of the product layer 2026-09-07.

## Templates
- `templates/architect_prompt.md` — Prompt template for Architect agent
- `templates/redteamer_prompt.md` — Prompt template for Red-Teamer agent
- `templates/fuzzer_prompt.md` — Prompt template for Fuzz-Engineer agent
- `templates/chainer_prompt.md` — Prompt template for Chainer agent

## Scripts
- `scripts/verify_poc.py` — Minimal PoC verification script template