# AGENTS.md — HunterOS Plugins — portable security skills, tools, hooks, and agents

This is a **skills/tools/hooks repository** — it does NOT contain a runnable app.
It plugs into agent harnesses (Claude Code, Hermes, OpenCode, Codex).

## Layout

- `skills/` — Markdown skill files (load one at a time per lane)
- `agents/` — Pre-built lane prompt templates
- `hooks/` — Lifecycle gate scripts (SessionStart, PreToolUse, PostToolUse)
- `mcp/` — MCP server (hunt_* tools)
- `.claude-plugin/` — Claude Code plugin manifest
- `marketplace.json` — Plugin catalog for marketplace discovery
- `always-on-rules.md` — RoE-first doctrine injected at SessionStart

## Rules for agents

1. Do not run active testing against any target until the owner has approved
   rules of engagement (RoE) in writing.
2. Write findings, leads, and verification results only through `hunt` (or the
   `hunt_*` MCP tools that wrap it). Do not edit the ledger directly.
3. Do not claim `PROVEN`, `EXPLOITABLE`, or admin takeover without a bound
   finding or lead ID in the ledger.
4. Never fabricate command output. If a step did not run, say so.
5. Do not commit secrets.

## Skill loading convention

Load ONE skill at a time, only what the lane needs:

```
skill_view(name='hunt-os')       # router — pick your category
skill_view(name='hunter-tools')  # tool registry
skill_view(name='hunter-loop')   # loop CLI reference
skill_view(name='hunter-agent-lanes')  # dispatch map
```
