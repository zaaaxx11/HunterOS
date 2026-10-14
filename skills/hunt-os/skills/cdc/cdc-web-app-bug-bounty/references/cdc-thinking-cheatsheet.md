# CDC Thinking Cheatsheet

## The 6 Hard Rules (Memorize)

| # | Rule | Action |
|---|------|--------|
| 1 | **DIVERGENT FIRST** | 3+ theories before code. Group by IDEA not wording. Redirect overlap. |
| 2 | **CHAIN EVERYTHING** | Map `[Trigger→Effect→Boundary]`. Hunt handoff points. No solo bugs. |
| 3 | **STALL = BLOCK** | 2 rounds no evidence → BLOCKED. Don't force. New mechanism only. |
| 4 | **ADVERSARIAL VALIDATION** | Every finding: "Prove this ISN'T exploitable." Survives? Keep. Fails? Discard. |
| 5 | **KEEP INCOMPATIBLE ROUTES** | Winning chain = contradictory ideas. Cross-pollinate AFTER independent depth. |
| 6 | **PERSISTENCE** | 10 rounds / 30 min minimum. Chain lives in round 7. |

## Blind Spot Scanner (After EVERY Round)

1. **What did I NOT look at?** — Parts skipped as "safe"
2. **What would developers expect me to miss?** — Planted blind spots
3. **If I'm wrong, where am I wrong?** — Disprove own conclusion

## 4-Agent Quick Reference

| Agent | Trigger | Output |
|-------|---------|--------|
| **Architect** | "Map trust graph for X" | Trust graph, sinks, boundaries |
| **Red-Teamer** | "Attack auth bypass on X" | Broken assumptions, vulns |
| **Fuzz-Engineer** | "Edge cases on X sinks" | Crash vectors, parser diffs |
| **Chainer** | "Build chain from findings" | `Trigger→Effect→Boundary` |

## Output Format (Exact)

```
VULNERABILITY: [Class/Type]
ENTRY: [Pre-auth / Post-auth / Unauth]
CHAIN: [Step 1 → Step 2 → ... → RCE]
IMPACT: [RCE / Theft / Escalation / Bypass]
POC: [Working exploit ≤50 lines]
EVIDENCE: [Line numbers / code snippets]
CONFIDENCE: [PROVEN / HIGH / THEORETICAL]
MITIGATION: [Root cause + Fix]
VERIFICATION: Clean install → reproduce → hash/screenshot → minimal PoC
```

## Constraints (Non-Negotiable)

- NO changelogs, git history, internet searches
- NO known CVEs or public exploit-db
- NO "theoretical" — PoC required or you don't have it
- NO "potential" — only report "EXPLOITABLE"

## Multi-Agent Spawn Pattern

```python
delegate_task(tasks=[
  {"goal": "Architect: map trust graph for target X", "context": "..."},
  {"goal": "Red-Teamer: attack auth bypass on target X", "context": "..."},
  {"goal": "Fuzz-Engineer: edge cases on target X sinks", "context": "..."},
  {"goal": "Chainer: build chain from findings", "context": "..."}
])
```

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Premature convergence | Force 3 divergent theories first |
| Reporting solo bugs | Always chain: Trigger→Effect→Boundary |
| Forcing stalled paths | Mark BLOCKED after 2 rounds |
| Ego attachment to findings | Adversarial validation every time |
| Early cross-pollination | Independent depth first |

## Quick Commands

```bash
# Spawn 4 agents in parallel
delegate_task(tasks=[...])

# Check agent status
delegate_task(action="list")

# Steer stuck agent
delegate_task(action="steer", subagent_id="sa-xxx", message="...")
```