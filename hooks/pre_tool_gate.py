#!/usr/bin/env python3
"""PreToolUse gate for HUNT-OS MCP tools (matcher: mcp__hunter-os__.*).

Policy:
  - READ_ONLY tools always pass (exit 0).
  - Every other HUNT-OS tool is treated as a WRITE and needs a bound workspace:
    the HUNT_DB file must exist AND a `.huntos-project` lock must be present in
    the working directory. Otherwise exit 2 with stderr "BLOCKED: ...".
  - HUNT_PLUGIN_GATE=warn downgrades a block to exit 0 with a stderr warning.
  - Unknown tools are gated (fail closed) rather than assumed read-only.

Input: the PreToolUse JSON payload on stdin (tool_name, tool_input, cwd, ...).
Exit 0 allow, exit 2 block (the stderr text is shown to the model).
Stdlib only. The pure function decide() is the testable core.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PREFIX = "mcp__hunter-os__"
LOCK_FILENAME = ".huntos-project"
DEFAULT_DB = "~/.huntos/hunt.db"

# Read-only MCP tool names (suffix after the server prefix). These never gate.
# Must match the tool names registered by mcp/server.py.
READ_ONLY = frozenset({
    "hunt_status",
    "hunt_brief",
    "hunt_next",
    "hunt_target_list",
    "hunt_lead_list",
    "hunt_verify_report",
})


def _tool_suffix(tool_name: str) -> str | None:
    if not isinstance(tool_name, str) or not tool_name.startswith(PREFIX):
        return None
    return tool_name[len(PREFIX):]


def _db_path(env: dict) -> Path:
    raw = env.get("HUNT_DB") or os.path.expanduser(DEFAULT_DB)
    return Path(raw)


def decide(payload: dict, env: dict, cwd: str | None = None) -> tuple[int, str]:
    """Return (exit_code, stderr_message). Empty message means silent pass."""
    tool = payload.get("tool_name") if isinstance(payload, dict) else None
    suffix = _tool_suffix(tool)
    if suffix is None:
        return 0, ""  # not a HUNT-OS tool; out of scope for this matcher
    if suffix in READ_ONLY:
        return 0, ""

    problems: list[str] = []
    db = _db_path(env)
    if not db.is_file():
        problems.append(f"HUNT_DB not found at {db}")
    base = Path(cwd or payload.get("cwd") or os.getcwd())
    if not (base / LOCK_FILENAME).is_file():
        problems.append(f"no {LOCK_FILENAME} lock bound in {base} (run `hunt project bind`)")
    if not problems:
        return 0, ""

    msg = (
        f"BLOCKED: write tool '{suffix}' needs a bound HUNT-OS workspace: "
        + "; ".join(problems)
        + ". Confirm an owner-approved RoE and bind the workspace first."
    )
    if env.get("HUNT_PLUGIN_GATE") == "warn":
        return 0, "WARNING (HUNT_PLUGIN_GATE=warn): " + msg
    return 2, msg


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        # Unparseable input for a write-capable matcher: fail closed.
        sys.stderr.write("BLOCKED: pre_tool_gate could not parse hook input\n")
        return 2
    code, msg = decide(payload, dict(os.environ))
    if msg:
        sys.stderr.write(msg + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
