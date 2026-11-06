# HunterOS Plugins — Universal Security Skills & Tools

A portable, harness-agnostic security framework. **No daemon, no app — just
skills, tools, hooks, and agents** that plug into any LLM agent framework.

**Compatible with:** Claude Code · Hermes Agent · OpenCode · Codex · any JSON-Schema tool consumer

---

## What's in the box

### 🔧 Skills (portable, load one at a time)

| Skill | Description |
|-------|------------|
| `hunt-os` | Router: 51 hunt skills across 5 categories (recon, web2, web3, cdc, verification) |
| `hunter-harness-core` | Full engine: state loop, goals vocabulary, 43 universal tools |
| `hunter-loop` | Daemon-free loop: `hunter loop <target> --time 6h --goals rce-min:1` |
| `hunter-tools` | 43 JSON-Schema tools (local files, network recon, web3, static analysis) |
| `hunter-agent-lanes` | Multi-agent dispatcher: architect, red-teamer, fuzz-engineer, chainer, verifier |

### 🤖 Agents (pre-built lane prompts)

| Agent | Role |
|-------|------|
| `architect` | Attack-surface mapping |
| `red-teamer` | Auth/authz testing, injection |
| `fuzz-engineer` | Edge cases, constraints |
| `chainer` | Exploit construction |
| `verifier` | Evidence checking |
| `adversary` | Adversarial review |

### 🪝 Hooks (lifecycle gates)

| Hook | When |
|------|------|
| `SessionStart` | Injects RoE-first doctrine |
| `PreToolUse` | Blocks unauthorized tools |
| `PostToolUse` | Validates outputs |

### 🔌 MCP Server

Standard Model Context Protocol server exposing `hunt_*` tools.

---

## Quick Start

### Native Claude Code (Recommended — 51 skills + 7 agents)

```bash
git clone https://github.com/zaaaxx11/hunteros-plugins.git ~/.hunteros-plugins

# One-time install to user-level Claude Code
mkdir -p ~/.claude/skills ~/.claude/agents
cp -r ~/.hunteros-plugins/.claude/skills/* ~/.claude/skills/
cp -r ~/.hunteros-plugins/.claude/agents/* ~/.claude/agents/
```

Restart Claude Code. Skills are auto-discovered. Load any skill:
```
load hunt-os                 # Router (51-skill index)
load hunt-web2-attack-surface-audit  # Web2 audit
load hunt-web3-black-swan-engine     # EVM vulnerability laws
load hunt-recon-predator-recon       # Recon pipeline
```

7 agents available: `hunt-architect`, `hunt-red-teamer`, `hunt-fuzz-engineer`, `hunt-chainer`, `hunt-verifier`, `hunt-adversary`, `hunt-lane-runner`.

### Plugin Install (Legacy)

```
/plugin marketplace add zaaaxx11/hunteros-plugins
/plugin install hunt-os@hunter-os
```

### Hermes Agent
```bash
ln -s ~/.hunteros-plugins/skills ~/.hermes/profiles/default/skills/hunter
```

### OpenCode/Codex
```bash
cp -r ~/.hunteros-plugins/skills ~/your-project/ai_skills/
```

### Install the harness (optional — for `hunter loop` and full engine)

```bash
pip install git+https://github.com/zaaaxx11/HunterOsHarness.git
hunter loop /path/to/target --time 6h --goals rce-min:1,findings-min:500 --yes
```

---

## Goal Vocabulary

| Kind | Matches | Example |
|------|---------|---------|
| `rce-min` | Pure RCE (code-exec, command-injection) | `rce-min:1` |
| `exploitable-min` | RCE + reentrancy + access-control | `exploitable-min:1` |
| `findings-min` | All findings | `findings-min:500` |
| `verified-min` | VERIFIED+ only | `verified-min:100` |

**Time > goals** — wall clock always wins. Read `state.json` for summary.

---

## Tool Categories (43 tools total)

| Category | Tools |
|----------|-------|
| **Local** | `search_files`, `read_file`, `patch_write` |
| **Network** | `dns_resolve`, `crt_sh`, `headers_audit`, `recon_subdomains` |
| **Web3** | `contract_read`, `contract_source_fetch`, `abi_decode_hint` |
| **Heavy** | `slither_audit`, `cast_call` |
| **Verify** | `verify_finding`, `derive_targets` |

All tools follow JSON-Schema — plug into any function-calling agent.

---

## Repo Structure

```
hunteros-plugins/
├── skills/          # Markdown skill files (load one at a time)
│   ├── hunt-os/     # Router + 51 sub-skills
│   ├── hunter-*/    # Harness engine, loop, tools, agent lanes
├── agents/          # Pre-built lane prompt templates
├── hooks/           # Lifecycle gate scripts (PreToolUse, SessionStart)
├── mcp/             # MCP server (hunt_* tools)
├── scripts/         # Utility scripts
├── .claude-plugin/  # Claude Code plugin manifest
├── marketplace.json # Plugin catalog (v0.7.0)
└── always-on-rules.md # RoE-first doctrine (injected at SessionStart)
```

## Claim Discipline

- Strong claims (PROVEN, EXPLOITABLE) must name their ledger record
- PoC must be EXECUTED, not just theorized
- Findings require ≥1 bound evidence artifact

---

Built from [HunterOsHarness v0.7](https://github.com/zaaaxx11/HunterOsHarness) — daemon purged, loop-driven, goals-aware.
