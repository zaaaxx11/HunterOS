# Cross-Tool Diagnosis: The Triple-Fail Headless Blocker

## Pattern

This is the canonical failure signature in headless/container environments
where the agent needs shell access but lacks it:

| Tool | First call | Result | Second call | Result |
|------|-----------|--------|------------|--------|
| `computer_use(list_apps)` | Returns processes (bash, sshd, hermes, cua-driver) | ✅ | `computer_use(focus_app, app=bash)` | ❌ "No on-screen window found" |
| `computer_use(capture, app=screen)` | Returns 0x0, 0 elements | ❌ | `computer_use(type/key)` | ❌ "No active window" |
| `process(list)` | Returns empty array | ✅ (but empty) | `process(write, session_id=x)` | ❌ "session_id is required" |
| `terminal` | N/A | ❌ Not in tool set | N/A | N/A |

## Why Agents Fail Here

1. **`list_apps` looks promising** — it returns real processes (bash, hermes, cua-driver)
2. **But they have zero windows** — headless systems run processes without GUI windows
3. **`process(list)` succeeds** — looks like the tool is working
4. **But `process(write)` fails** — the tool has no sessions to manage (no `terminal` tool created any)
5. **Agent thinks:** "The process tool works, let me write to it" → fails → tries more workarounds

## Quick Recognition Rule

> **`process list` returns empty AND `process write` requires a session_id** = no managed sessions exist = no `terminal` tool = headless blocker.

## What to Do Instead

1. Report the blocker immediately with the diagnostic table above
2. Suggest alternatives: provide contents directly, add `terminal` tool, deploy to GUI-enabled env
3. Load `headless-shell-access` skill for the full escape strategy

## Related Sessions

See `repro-headless-blocker.md` for the original reproduction case (ZIP extraction in Singularity container).