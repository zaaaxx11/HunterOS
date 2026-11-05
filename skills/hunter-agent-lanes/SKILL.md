---
name: hunter-agent-lanes
description: HunterOs multi-agent lane system — architect, red-teamer, fuzz-engineer, chainer, verifier. Use when dispatching multi-agent hunts across different specialties.
allowed-tools: Bash, Read, Grep
---
# HUNTEROS AGENT LANES — Multi-Agent Orchestrator

## LANE SYSTEM

Six lanes dispatched by the orchestrator. Each lane has its own role, tools,
and prompts. The orchestrator assigns work based on the hunt phase and the
lane's specialty.

| Lane | Role | Triggers | Default Tools |
|------|------|----------|---------------|
| **Architect** | Attack-surface mapping | New target | read_file, search_files, derive_targets |
| **Red-Teamer** | Auth/authz, injection | Login pages, API endpoints | dns_resolve, headers_audit, contract_read |
| **Fuzz-Engineer** | Edge cases, constraints | Validation, parsing logic | search_files, patch_write |
| **Chainer** | Exploit construction | Verified findings | slither_audit, contract_read, derive_targets |
| **Verifier** | Evidence checking | Every lane output | verify_finding, read_file, search_files |

## LANE LOADOUTS (one line per dispatched lane)

```
Architect     ← web2-attack-surface-audit, derive_targets
Red-Teamer    ← web2-admin-takeover, nextjs-authn-authz-probing, business-logic-invariant-hunt
Fuzz-Engineer ← dynamic-fuzz-testing, systematic-debugging, search_files
Chainer       ← adversarial-exploit-chains, cross-contract-chain-builder
Verifier      ← audit-verification-methodology, poc-reverification
```

## SESSION LOOP

```
Authorize → Observe → Model → Minimal reversible test → Verify → Report
```

Every finding must carry:
1. **Evidence** (code line, tx hash, source reference)
2. **Impact chain** (who is affected, at what value, how it cascades)

## CLAIM DISCIPLINE

Strong claims (PROVEN, EXPLOITABLE, "admin takeover") must name their ledger
record (e.g. PROVEN[F-3]) or the claim gate vetoes the turn. A PoC must be
EXECUTED, not just theorized.

## ADAPTING TO YOUR HARNESS

### Claude Code
```
# .claude-plugin/plugin.json
{"agents": ["architect", "red-teamer", "fuzz-engineer", "chainer", "verifier"]}
```

### Hermes Agent
```bash
# Spawn subagents for each lane
hunter agent dispatch architect --target URL
hunter agent dispatch red-teamer --target URL
```

### Custom Harness
Use the agent specs at `agents/*.md` — each contains the role description,
tool allowlist, prompt template, and budget constraints for one lane.