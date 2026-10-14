#!/usr/bin/env python3
"""PostToolUse check: run tool output through the claim gate.

If a HUNT-OS tool's response text contains a strong-claim marker (PROVEN,
EXPLOITABLE, or "admin takeover"), the text is piped to the adjacent
scripts/claim_gate.py (the packaged gate, byte-identical to app/src/huntos/_data/bin/claim_gate.py). Exit 2
with the gate's stderr on veto; exit 0 otherwise.

Fail-closed on a claim: if the gate cannot run, the claim is vetoed.
Stdlib only. decide() is the testable core.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PREFIX = "mcp__hunter-os__"
MARKER = re.compile(r"\bPROVEN\b|\bEXPLOITABLE\b|\badmin takeover\b", re.IGNORECASE)
GATE = Path(__file__).resolve().parent.parent / "scripts" / "claim_gate.py"


def _response_text(payload: dict) -> str:
    resp = payload.get("tool_response")
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        parts = []
        for item in resp.get("content", []) if isinstance(resp.get("content"), list) else []:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if isinstance(resp.get("text"), str):
            parts.append(resp["text"])
        if parts:
            return "\n".join(parts)
    return json.dumps(resp, ensure_ascii=False)


def decide(payload: dict, env: dict) -> tuple[int, str]:
    """Return (exit_code, stderr_message) for a PostToolUse payload."""
    tool = payload.get("tool_name") if isinstance(payload, dict) else None
    if not isinstance(tool, str) or not tool.startswith(PREFIX):
        return 0, ""
    text = _response_text(payload)
    if not MARKER.search(text):
        return 0, ""
    if not GATE.is_file():
        return 2, "BLOCKED: claim gate missing from plugin hooks; strong claim cannot be verified"
    child_env = dict(env)
    try:
        proc = subprocess.run(
            [sys.executable, str(GATE)],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60,
            env=child_env,
            cwd=env.get("CLAUDE_PROJECT_DIR") or None,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 2, f"BLOCKED: claim gate could not run ({type(exc).__name__}); claim not verified"
    if proc.returncode == 0:
        return 0, ""
    if proc.returncode == 2:
        err = proc.stderr.decode("utf-8", "replace").strip() or "BLOCKED: unbacked claim"
        return 2, err
    return 2, f"BLOCKED: claim gate exited {proc.returncode}; claim not verified"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return 0  # nothing to check; PostToolUse cannot undo the call anyway
    code, msg = decide(payload, dict(os.environ))
    if msg:
        sys.stderr.write(msg + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
