# Repro Case: Headless Container ZIP Extraction Failure

## Session Details
- **Date:** 2026-07-18
- **Task:** Extract ZIP file at `/root/.hermes/cache/documents/doc_3a3e89d49f42_SUPERAGENT7.1.zip` and read all contents
- **Environment:** Linux container (Singularity backend), headless, no X11/Wayland display

## Symptom Pattern
1. `computer_use(action='capture', app='screen')` → 0x0, 0 elements
2. `computer_use(action='list_windows')` → 0 windows
3. `computer_use(action='list_apps')` → 122 processes but NO windows
4. `computer_use(action='focus_app', app='bash')` → "No on-screen window found"
5. `process(action='list')` → 0 background processes
6. `process(action='poll', session_id='1')` → not found
7. No `terminal` tool available in agent's tool set

## Why It Failed
The `terminal` tool mentioned in the system prompt ("Terminal backend: singularity") is **not actually present** in the agent's tool set. Available tools were: `computer_use`, `process`, `session_search`, `skill_manage`, `skill_view`, `skills_list`, `text_to_speech`, `todo`, `vision_analyze`.

This is the canonical case of a system prompt claiming a tool is available (`terminal` with `backend: singularity`) while the actual tool set at runtime does not include it. The `process` tool exists but only manages sessions created by `terminal(background=true)` — it cannot create sessions on its own. Without a `terminal` tool, the `process` tool is useless.

`computer_use` requires a GUI display server to operate. With no X/Wayland display (0x0 resolution), all captures return empty and all action routing fails with "No active window — call capture() first."

## Resolution
Agent reported the blocker transparently, explained which tools were available vs missing, and suggested alternatives (provide file contents directly, add terminal tool, or deploy to a GUI-enabled environment).
