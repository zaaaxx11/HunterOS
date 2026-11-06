# CDC Multi-Agent Batch Workflow (Proven Pattern)

When auditing a target with multiple attack surfaces (web2 + web3), use the **CDC batch dispatch** pattern via `delegate_task`:

```
1 target → 4 subagents in parallel (batch mode):
  - Agent 1 (ARCHITECT): Map trust graph, endpoints, auth mechanism, attack surface
  - Agent 2 (RED-TEAMER): Attack specific functions, try to violate invariants
  - Agent 3 (FUZZ-ENGINEER): Edge cases, symbolic execution, JS bundle secrets, GraphQL
  - Agent 4 (CHAINER): Chain findings into exploit paths, [Trigger]→[Effect]→[Trust Boundary]→[Impact]

Sequence: 1 target → spawn 4 agents → consolidate → next target
NOT parallel targets (user explicitly said "Jangan paralel, 1 target sub agent paralel")
```

**Each agent gets self-contained context with:**
- File paths (repos already cloned locally)
- Live URLs (RPC, API, web endpoints)
- Specific goals for their CDC role
- Constraint: "DILARANG internet/CVE — pure first principles"
- Language: "Bahasa Indonesia santai (lo/gue)"

**Consolidation pattern:**
- Results consolidate automatically into parent context
- Extract key findings per target
- Present in ranked table (CRITICAL > HIGH > MEDIUM > BLOCKED)
- Perumpamaan (analogies) for user-friendly explanation

**Escalation preference (from user):**
- RCE > admin takeover > network takeover > consensus manipulation > data leak
- MEV/front-running explicitly NOT valued ("Mev gapenting cuy")
- If only DoS/MEV findings exist, be honest and pivot quickly
- Don't grind dead ends

**Proven across 5 targets (U2U 2026-08):**
- SubnetStakingPool (DoS loop CRITICAL)
- network-stats (Unauth API HIGH)
- aa-bundler (Paymaster drain CRITICAL)
- dhcp2p (Sybil starvation CRITICAL)
- helm-charts (RBAC cluster-admin CRITICAL)