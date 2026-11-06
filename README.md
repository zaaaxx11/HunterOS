# HunterOS Plugins

<div align="center">

**Portable security-assessment framework for LLM agent harnesses.**

[![Version](https://img.shields.io/badge/version-0.5.0-blue)](#)
[![Skills](https://img.shields.io/badge/skills-52-orange)](#skill-index)
[![Agents](https://img.shields.io/badge/agents-7-green)](#agents)
[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)

</div>

---

## Overview

HunterOS Plugins is a self-contained, harness-agnostic security testing framework. It ships as pure Markdown and Python — no daemon, no runtime, no vendor lock-in. Drop the files into your agent harness of choice and you have a production-grade security-assessment pipeline: recon, web application audit, smart-contract analysis, CDC multi-agent orchestration, and evidence-ladder verification.

**Works with:** Claude Code (native) · Hermes Agent · OpenCode · Codex · any function-calling agent that consumes JSON-Schema tools.

### What makes it different

- **RoE-first.** Every workflow starts with rules-of-engagement validation. Default-deny on scope ambiguity.
- **Evidence ladder.** Claims graduate through `theoretical → in-code → proven-live` with mandatory adversary challenge at each gate.
- **No duplication.** Each tool in the essential kit solves exactly one problem class. Overlapping tools are documented and replaced.
- **CDC backbone.** 6 hard rules: divergent-first, chain-everything, stall-means-blocked, adversarial-default, keep-incompatible-routes, minimum-10-rounds.
- **Self-contained.** No external database, no telemetry, no API keys. Skills read from disk, tools run from `$PATH`.

---

## Quick Start

### Claude Code (native — recommended)

```bash
git clone https://github.com/zaaaxx11/hunteros-plugins.git ~/.hunteros-plugins
mkdir -p ~/.claude/skills ~/.claude/agents
cp -r ~/.hunteros-plugins/.claude/skills/* ~/.claude/skills/
cp -r ~/.hunteros-plugins/.claude/agents/* ~/.claude/agents/
```

Restart Claude Code. Skills are auto-discovered. Then:

```
load hunt-recon-predator-recon        # Industrial recon pipeline
load hunt-web2-attack-surface-audit   # Full web2 audit
load hunt-web3-black-swan-engine      # EVM vulnerability laws
load hunt-os                          # Router (full 51-skill index)
```

### Install essential tools

```bash
# One-command installer (Windows/Unix)
bash ~/.hunteros-plugins/scripts/install-essential-tools.sh
```

Installs 5 non-overlapping tools: `go`, `jq`, `subfinder`, `nuclei`, `paramspider`. For the full tool matrix and overlap rationale, see [`TOOLS.md`](TOOLS.md).

### Other harnesses

```bash
# Hermes Agent
ln -s ~/.hunteros-plugins/skills ~/.hermes/profiles/default/skills/hunter

# OpenCode / Codex
cp -r ~/.hunteros-plugins/skills ~/your-project/ai_skills/
```

### Harness CLI (optional)

For the full daemon-free hunt loop with state tracking:

```bash
pip install git+https://github.com/zaaaxx11/HunterOsHarness.git
hunt loop /path/to/target --time 6h --goals rce-min:1,findings-min:500 --yes
```

---

## Architecture

```
hunteros-plugins/
│
├── .claude/                         # Native Claude Code integration
│   ├── skills/                      # 52 discoverable skills (auto-loaded)
│   │   ├── hunt-os/                 # Router (index of all 51 sub-skills)
│   │   ├── hunt-recon-*/           # 4 recon skills
│   │   ├── hunt-web2-*/            # 17 web2 audit skills
│   │   ├── hunt-web3-*/            # 19 blockchain audit skills
│   │   ├── hunt-cdc-*/             # 5 multi-agent CDC skills
│   │   └── hunt-verification-*/    # 6 verification skills
│   └── agents/                      # 7 lane agent definitions
│
├── skills/                          # Raw skill source (Hermes/OpenCode)
│   └── hunt-os/
│       ├── SKILL.md                 # Canonical router
│       └── skills/                  # 51 sub-skills in 5 categories
│
├── agents/                          # Agent lane prompt templates
│   ├── hunt-architect.md
│   ├── hunt-red-teamer.md
│   ├── hunt-fuzz-engineer.md
│   ├── hunt-chainer.md
│   ├── hunt-verifier.md
│   ├── hunt-adversary.md
│   └── hunt-lane-runner.md
│
├── hooks/                           # Lifecycle gate scripts
│   ├── hooks.json                   # Hook registry
│   ├── session_start.py             # RoE injection at session start
│   ├── pre_tool_gate.py             # Tool-use authorization gate
│   └── post_tool_check.py           # Output validation
│
├── mcp/                             # MCP server (Model Context Protocol)
│   └── server.py                    # stdio JSON-RPC 2.0 — 22 hunt_* tools
│
├── scripts/                         # Utility scripts
│   ├── install-essential-tools.sh   # One-command tool installer
│   └── claim-gate-stop.sh           # Session-stop claim gate
│
├── marketplace.json                 # Plugin catalog entry
├── .claude-plugin/plugin.json       # Claude Code plugin manifest
├── always-on-rules.md               # RoE-first doctrine (injected at SessionStart)
├── TOOLS.md                         # Tool matrix + overlap analysis
├── QUICKSTART.md                    # Quick-reference card
└── README.md
```

### Skill categories

| Category | Count | Domain |
|----------|-------|--------|
| **recon** | 4 | Subdomain enumeration, SPA decoding, admin takeover, WAF bypass |
| **web2** | 17 | Next.js/NestJS/Express/Django audit, auth bypass, exploit chains, GraphQL, CMS |
| **web3** | 19 | EVM audit, DeFi protocol, RPC attack surface, ERC-4337 bundler, L2 rollup |
| **cdc** | 5 | Multi-agent CDC orchestration, batch audit, sovereign ops protocol |
| **verification** | 6 | Evidence discipline, PoC re-verification, fuzz testing, debugging |

### Agents

| Agent | Lane | Primary Skill |
|-------|------|---------------|
| `hunt-architect` | Attack-surface mapping | `hunt-web2-web2-attack-surface-audit` |
| `hunt-red-teamer` | Auth/authz, injection, invariant violation | `hunt-web2-nextjs-authn-authz-probing` |
| `hunt-fuzz-engineer` | Edge cases, constraints, crash vectors | `hunt-verification-dynamic-fuzz-testing` |
| `hunt-chainer` | Exploit chain synthesis | `hunt-web2-adversarial-exploit-chains` |
| `hunt-verifier` | Evidence checking, claim validation | `hunt-verification-audit-verification-methodology` |
| `hunt-adversary` | Adversarial review, falsification | (review role — pulled in on demand) |
| `hunt-lane-runner` | Multi-lane dispatcher | (orchestration) |

### Essential tools

The framework ships with a curated, non-overlapping toolset. Every tool solves exactly one problem class.

| Tool | Category | Use |
|------|----------|-----|
| `subfinder` | Recon | Passive subdomain enumeration |
| `nuclei` | Vuln scan | Template-driven vulnerability scanning |
| `httpx` | HTTP | Live host probing |
| `paramspider` | Params | Parameter discovery and mining |
| `cast` | Web3 RPC | Ethereum RPC calls, storage-slot analysis |
| `forge` | Web3 test | Solidity testing, PoC verification |
| `anvil` | Web3 node | Local testnet for exploit simulation |
| `jq` | Parsing | JSON query and transformation |
| `curl` | HTTP | Raw HTTP request crafting |

See [`TOOLS.md`](TOOLS.md) for the full matrix, install instructions, and overlap analysis (13 tools skipped with documented replacements).

---

## Usage Patterns

### Single-target recon → audit → report

```bash
# 1. Load the recon skill
load hunt-recon-predator-recon

# 2. Feed target
"recon example.com — bug bounty scope, web2 + web3"

# 3. After recon, load the audit skill
load hunt-web2-web2-attack-surface-audit

# 4. Audit the discovered surface
"audit the 12 live hosts from recon phase"

# 5. Chain findings
load hunt-web2-adversarial-exploit-chains

# 6. Verify
load hunt-verification-audit-verification-methodology
```

### Multi-agent CDC hunt (4-lane parallel)

```
# Spawn lanes
Architect: "map trust graph for target X"
Red-Teamer: "violate auth invariants on target X"
Fuzz-Engineer: "edge cases on all input sinks"
Chainer: "synthesize exploit chains from Agent 2 & 3 findings"
```

### Smart contract audit

```bash
load hunt-web3-black-swan-engine
# Then: load hunt-web3-evm-contract-audit
# Then: load hunt-web3-smart-contract-exploit-pocs
```

---

## MCP Server

The plugin ships a standard Model Context Protocol server exposing 22 `hunt_*` tools for ledger-backed hunting. The server runs `hunt` CLI as a subprocess — tracking targets, findings, leads, follow-ups, and evidence ladder progression.

### Available tools

| Group | Tools |
|-------|-------|
| **Read** | `hunt_status`, `hunt_brief`, `hunt_next`, `hunt_target_list`, `hunt_lead_list`, `hunt_verify_report`, `hunt_followup_list` |
| **Write** | `hunt_target_add`, `hunt_finding_add`, `hunt_lead_add`, `hunt_report` |
| **Evidence ladder** | `hunt_poc_run`, `hunt_finding_promote`, `hunt_verify`, `hunt_challenge`, `hunt_finding_overturn`, `hunt_lead_mutate` |
| **Wave** | `hunt_wave_reaudit`, `hunt_wave_budget` |
| **Follow-up** | `hunt_followup_add`, `hunt_followup_verify`, `hunt_followup_drop`, `hunt_followup_promote` |

The MCP server is configured in `.mcp.json` and hooks gate MCP tool calls via `hooks/pre_tool_gate.py`. For direct testing:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python mcp/server.py
```

---

## Hooks (Lifecycle Gates)

Four lifecycle hooks enforce RoE-first discipline:

| Hook | Trigger | Script | Behavior |
|------|---------|--------|----------|
| `SessionStart` | `startup \| resume \| clear \| compact` | `hooks/session_start.py` | Injects `always-on-rules.md` into session context |
| `PreToolUse` | Any `mcp__hunter-os__*` tool call | `hooks/pre_tool_gate.py` | Validates authorization before execution |
| `PostToolUse` | Any `mcp__hunter-os__*` tool result | `hooks/post_tool_check.py` | Validates output integrity |
| `Stop` | Session termination | `scripts/claim-gate-stop.sh` | Enforces the claim gate (unverified claims vetoed) |

---

## Evidence Ladder

Every finding must climb the ladder. No shortcuts.

```
theoretical ──→ in-code ──→ proven-live
     │              │              │
     ▼              ▼              ▼
  hypothesis    PoC ran +      verifier event
  recorded      evidence ref   + adversary
                                challenge
```

Rules:
- Strong claims (PROVEN, EXPLOITABLE) require a ledger record ID.
- PoC must be **executed**, not theorized. Existence is not execution.
- A finding with open follow-ups cannot be promoted.
- Every chained finding requires every ancestor to be proven.

---

## Goal Vocabulary (Harness CLI)

For state-driven continuous hunting with the optional harness:

| Goal | Matches | Example |
|------|---------|---------|
| `rce-min` | Pure RCE (code-exec, command-injection) | `rce-min:1` |
| `exploitable-min` | RCE + reentrancy + access-control + proxy bypass | `exploitable-min:1` |
| `findings-min` | All findings regardless of severity | `findings-min:500` |
| `verified-min` | VERIFIED+ findings only | `verified-min:100` |

**Wall-clock time always wins over goal counters.** Read `state.json` for the live summary.

---

## Claim Discipline

- File:line for every claim. Never narrate unbound assertions.
- Distinguish: **VERIFIED** (code seen) vs **THEORETICAL** (logic only) vs **FALSE** (disproven).
- Report failed vectors honestly: "Checked X, not vulnerable because Y."
- No "potential", no "may expose", no "could leak."
- Anti-hyperbole: time claims cite actual elapsed, finding counts are exact, severity maps to actual impact chain.

---

## Compatibility Matrix

| Feature | Claude Code | Hermes Agent | OpenCode | Codex | Generic |
|---------|-------------|--------------|----------|-------|---------|
| Native skills (52) | ✅ `.claude/skills/` | ✅ symlink | ✅ copy | ✅ copy | ✅ read SKILL.md |
| Agents (7) | ✅ `.claude/agents/` | ✅ | — | — | ✅ read AGENT.md |
| MCP server (22 tools) | ✅ `.mcp.json` | ✅ | ✅ | ✅ | ✅ stdio JSON-RPC |
| Hooks | ✅ plugin system | ✅ | — | — | — |
| Auto-load triggers | ✅ AGENTS.md | ✅ trigger words | — | — | — |
| Essential tools | See [`TOOLS.md`](TOOLS.md) | same | same | same | same |

---

## FAQ

### Why 52 skills and not one monolithic skill?

Each skill is self-contained — a lane agent loads only what it needs. Loading all 51 skills at once would waste context. The `hunt-os` router gives you the index; pick the skill that matches your target category.

### Why is tool X missing from the essential kit?

See [`TOOLS.md`](TOOLS.md) — every skipped tool has a documented reason and a replacement. The principle: no two tools that solve the same problem class. `sort -u` replaces `anew` and `uro`. `sed` replaces `qsreplace`. `nuclei` templates replace `dalfox`, `kxss`, `gxss`. Curl one-liners replace `corscanner`.

### Do I need the harness CLI?

No. The 52 skills work entirely with native Claude Code tools (`Read`, `Grep`, `Glob`, `Bash`, `Agent`). The harness CLI (`hunt loop`) adds state-driven continuous hunting with goal tracking, but it's optional.

### Can I use this without Claude Code?

Yes. The `skills/` directory contains raw Markdown skill files that any LLM agent can read. The `mcp/server.py` is a standard stdio JSON-RPC 2.0 server — plug it into any MCP-compatible harness. Agent prompts in `agents/` work with any framework that supports templated sub-agent dispatch.

### How do I contribute a new skill?

1. Create `skills/hunt-os/skills/<category>/<new-skill>/SKILL.md`
2. Add frontmatter: `name`, `description`, `allowed-tools`
3. Add the skill to `skills/hunt-os/skills/INDEX.md`
4. Create the corresponding entry in `.claude/skills/hunt-<category>-<new-skill>/`
5. Rebuild: `cp -r .claude/skills/* ~/.claude/skills/`

---

## Acknowledgments

Built from [HunterOsHarness](https://github.com/zaaaxx11/HunterOsHarness) — daemon purged, loop-driven, goals-aware. CDC methodology adapted from graph-theoretic vulnerability discovery research.

---

## License

MIT — see [LICENSE](LICENSE).