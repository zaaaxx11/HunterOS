---
name: headless-shell-access
description: "headless access to shells and admin planes"
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [headless, container, shell, diagnostics, computer-use, tool-access]
    category: development
    related_skills: [computer-use, hermes-agent-skill-authoring]
---

# Headless Shell Access Diagnostics

## Overview

In containerized, CI, or SSH environments with no graphical display, the `computer_use` tool will return 0x0 captures, zero windows, and zero elements. Combined with a missing `terminal` tool in the agent's tool set, this creates a situation where the agent cannot execute shell commands, extract files, or manage processes — and may waste turns trying.

This skill captures the diagnostic pattern and escape strategy so the agent recognizes the condition quickly and reports it cleanly.

## When to Use

- `computer_use` captures consistently return 0x0 / empty results
- `focus_app` / `list_windows` return empty or "No on-screen window found"
- `process list` returns empty and `process write` requires a session_id
- The `terminal` tool is not available in the agent's tool set
- Any task requires file extraction, shell execution, or command-line access

## Diagnostic Checklist

Run these checks in order. If ALL conditions below are true, you're in a headless blocker:

1. `computer_use(action='capture', app='screen')` → returns 0x0, 0 elements
2. `computer_use(action='list_windows')` → returns 0 windows
3. `computer_use(action='list_apps')` → returns processes but NO windows
4. `computer_use(action='focus_app', app='bash')` → "No on-screen window found"
5. `process(action='list')` → returns 0 background processes
6. `process(action='write' | 'submit' | 'log', session_id='anything')` → "session_id is required" or "not found" — no managed sessions exist to write to
7. No `terminal` tool available in your tool set
8. `execute_code` fails with: `RuntimeError: Neither 'apptainer' nor 'singularity' was found in PATH`
9. The task requires shell commands, file operations, or ZIP extraction

**Key signal:** If `process list` succeeds (returns empty) but `process write/submit/log` immediately fails with "session_id is required" or "not found", there are no background sessions for the `process` tool to manage. The `process` tool cannot create sessions on its own — it only manages sessions started via `terminal(background=true)`. Without a `terminal` tool, this is a hard blocker.

**Critical addition (2026-07-18):** The `execute_code` tool ALSO requires singularity/apptainer on PATH. Even if you could write a Python script, `execute_code` will fail with "Neither 'apptainer' nor 'singularity' was found in PATH" — it's not a Python problem, it's the same container backend dependency. This means **three tools** that could execute code are all blocked: `terminal`, `execute_code`, AND `computer_use` (no display).

## Escape Strategy

When you hit this blocker:

1. **Report it immediately.** Do not try more workarounds. The environment simply lacks the tools needed.
2. **Explain what's missing:** "I have `computer_use` but no display server (no X11/Wayland). I have a `process` tool but no `terminal` tool to start background sessions. `execute_code` also requires singularity which is not installed. The combination means I cannot execute shell commands or Python code."
**Suggested alternatives:**
- Provide a `terminal` tool or shell access to the agent
- Provide the file contents directly (paste, URL, or base64)
- Run the extraction commands locally and share the results
- Deploy to an environment with proper GUI or terminal access

**Critical note about delegating:** `delegate_task` and `process` tools
also fail in this scenario — subagents inherit the same broken Singularity
backend. Do NOT retry with delegation as a workaround. It wastes turns.

For the cross-tool diagnosis pattern (process list succeeds but write fails,
list_apps returns processes with zero windows), see
`references/cross-tool-diagnosis.md`. For the specific case where the system
prompt declares a `terminal` tool but it's missing from the actual tool set,
see `references/missing-terminal-tool.md`. For user frustration patterns
when asked to install skills from ZIP files, see
`references/headless-user-frustration-pattern.md`.

## Common Pitfalls

- **Wasting turns on workarounds** — `focus_app`, `type`, `key` all require an active window. They will fail on headless systems. Don't retry.
- **Confusing missing tools with broken tools** — If `computer_use` returns 0x0, it's not broken; it's just unable to operate without a display. This is expected, not a bug.
- **Assuming `process` can start sessions** — The `process` tool only manages sessions started by `terminal(background=true)`. It cannot create sessions on its own.
- **Calling `list_apps` and thinking you found a target** — `list_apps` returns OS processes (like `bash`, `hermes`, `sshd`) but on headless they have zero windows. No `focus_app` or `click` will work.
- **Trying `computer_use(action='key')` as a workaround** — `type` and `key` actions require an active window to receive input. On headless they fail with "No active window — call capture() first."
- **Using `execute_code` as a workaround** — `execute_code` also depends on the singularity/apptainer backend. It fails with "Neither 'apptainer' nor 'singularity' was found in PATH" regardless of whether your Python code is correct. The root cause is the same container environment, not the script itself.
- **Calling `delegate_task` as a workaround** — subagents inherit the same tool limitations. A delegated task that needs shell execution or Python code will fail with the same singularity error. This wastes turns and context.

- **Asking the user to extract/install themselves** — when a skill or config comes in a ZIP file and the environment can't read it, asking the user to paste content triggers frustration (especially for this user who prefers immediate action over back-and-forth). Report the blocker ONCE, then stop.

## Quick Reference

### Tools that work in headless mode

| Tool | Status | What it does |
|------|--------|-------------|
| `computer_use` | ❌ No display | GUI automation — requires X11/Wayland |
| `process` | ❌ No sessions | Background process mgmt — needs `terminal` to create sessions first |
| `execute_code` | ❌ No singularity | Python sandbox — needs singularity/apptainer on PATH |
| `terminal` | ❌ Not available | Shell execution — missing from tool set |
| `session_search` | ✅ Works | Search conversation history |
| `skill_manage` | ✅ Works | Skill CRUD operations |
| `skill_view` | ✅ Works | Read skill content |
| `skills_list` | ✅ Works | List available skills |
| `text_to_speech` | ✅ Works | Text → audio output |
| `todo` | ✅ Works | Task list management |
| `vision_analyze` | ✅ Works | Image analysis (not for ZIP/binary files) |

### Tools that don't work (and why)

| Tool | Failure | Why |
|------|---------|-----|
| `computer_use(capture)` | 0x0 / empty | No display server |
| `computer_use(focus_app)` | "No on-screen window" | No windows to focus |
| `computer_use(type/key)` | "No active window" | No active window to receive input |
| `process(poll/write/submit)` | "session_id required" | No sessions to manage |
| `computer_use(list_apps)` | ⚠️ No windows | Lists processes but all have 0 windows on headless |

### Pitfall: System Prompt Claims `terminal` Tool But It's Not Available

The system prompt may state `Terminal backend: singularity` and even list `terminal` as an available tool. However, the **actual tool registry** at runtime may not include it. The `terminal` tool requires the `terminal` toolset to be enabled and the Singularity binary to be on PATH. If it's missing, you'll get "Tool 'terminal' does not exist. Available tools: ..." when you try to use it.

When this happens, treat it as confirmation of the headless blocker (see `references/missing-terminal-tool.md`). Do not retry the `terminal` call — the tool is genuinely not registered.
