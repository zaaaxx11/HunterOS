# HunterOS as a Claude Code / ZCode plugin

HunterOS ships as a plugin in the `hunter-os` marketplace. It bundles the
router skill and doctrine corpus, slash commands, lifecycle hooks, and an MCP
server that wraps the `hunt` CLI. The plugin follows the same layout as the
Claude Code plugin format, so it installs in Claude Code and in ZCode.

Claude Code stays in control. MCP tools are called like skills: the model
decides when to call one, Claude Code's permission prompt applies, and the
PreToolUse hook enforces the gates before a write runs.

## What is in the plugin

| Piece | Path | Role |
| --- | --- | --- |
| Manifest | `.claude-plugin/plugin.json` | Name and version (from `app/pyproject.toml`) |
| Router skill | `skills/hunt-os/` | Generated from `huntos.installer.build_plan("router")` |
| Commands | `commands/*.md` | `start`, `status`, `brief`, `finding`, `lead`, `verify`, `report`, `triage` |
| Hooks | `hooks/` | SessionStart doctrine, PreToolUse gate, PostToolUse claim check |
| MCP server | `mcp/server.py` | JSON-RPC over stdio, stdlib only, calls `hunt --json <verb>` |
| Doctrine card | `always-on-rules.md` | Generated from `IDEA.md` and `HUNT-BRIDGE.md` |

The MCP server never writes SQLite directly. Every tool runs
`hunt --json <verb>` as a subprocess with a list argv (no shell), so the CLI
stays the single write door. Refusals (`{"ok": false, "code": 2, ...}`) become
MCP tool errors with the refusal text.

## Install

Claude Code:

```text
/plugin marketplace add zaaaxx11/HunterOS
/plugin install hunt-os@hunter-os
```

ZCode: add the same marketplace source in the plugin settings and install
`hunter-os`.

Offline, from a release: download `hunter-os-plugin-<version>.zip` from the
GitHub Release, verify it against `SHA256SUMS`, and unpack it. Then add the
unpacked directory as a local plugin.

The MCP server needs a working `hunt` CLI. Set `HUNT_CLI` if the CLI is not on
the default path (for example `HUNT_CLI="python -m huntos"`, or a full path
with quotes if it contains spaces).

## Environment switches

| Variable | Effect |
| --- | --- |
| `HUNT_DB` | Ledger path. Default `~/.huntos/hunt.db`. |
| `HUNT_CLI` | Command used to run the CLI. Default is `python -m huntos` with `app/src` on `PYTHONPATH` when the source tree is present, else `hunt`. |
| `HUNT_MCP_TIMEOUT` | Seconds per CLI call. Default 60. |
| `HUNT_PLUGIN_GATE` | `warn` downgrades PreToolUse blocks to warnings for debugging. Default is fail-closed. |

## Gates

- Read-only tools (`hunt_status`, `hunt_brief`, `hunt_next`, `hunt_target_list`,
  `hunt_lead_list`, `hunt_verify_report`) always pass the PreToolUse hook.
- Write tools require an existing ledger file and a `.huntos-project` marker in
  the working directory. Without both, the write is blocked.
- Any `mcp__hunter-os__*` tool that is not on the known list is blocked
  (fail-closed).
- PostToolUse rejects output that claims `PROVEN`, `EXPLOITABLE`, or
  "admin takeover" when no ledger backs the claim.
- The doctrine loaded at SessionStart requires an owner-approved rules of
  engagement (RoE) before any active action.

## Verify locally

```sh
python scripts/build_plugin.py --check
PYTHONPATH=app/src python -m pytest tests/smoke/test_plugin_surface.py test/tests/test_plugin.py -q
```

Regenerate the committed tree after changing the installer's corpus:

```sh
python scripts/build_plugin.py
```

The hand-written files (`commands/`, `hooks/`, `mcp/`, `.mcp.json`) are source,
not generated. Edit them directly.

## Limits

- The plugin has been checked with the automated suites and the MCP stdio
  smoke. A live install in Claude Code or ZCode has not been run as part of CI;
  that step is manual and must be confirmed by the operator.
- Only the core verbs have MCP tools. The full CLI is still available through
  the shell.
- The hook gates are a guardrail, not a sandbox. They do not stop a determined
  operator from running `hunt` directly.
- Use only against systems you are authorized to test.
