#!/usr/bin/env python3
"""Universal HUNT-OS hook pack: one contract, every harness.

Four lifecycle points are enough to enforce the doctrine in any agent
harness. Each is a plain function returning (exit_code, stderr_message), so
every harness-specific translator below is a thin adapter over the SAME
decisions — there is no second implementation to drift.

    doctor        -> is this workspace wired for HUNT-OS? (never blocks)
    pre_write     -> may this write run?            (exit 2 blocks)
    post_output   -> does this output's claim hold? (exit 2 vetoes)
    stop          -> does the final turn's claim hold? (exit 2 vetoes)

Exit codes are the whole contract: 0 pass, 2 block/veto. Harnesses that
cannot run a hook at all simply lose that gate, which is why the CLI and the
claim gate remain the real enforcement and this pack is the wiring.

Stdlib only. No network, no writes outside the ledger.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# The claim markers. Exact, case-sensitive tokens for PROVEN/EXPLOITABLE
# (word-bounded so "unproven" and lowercase "proven" stay clean) plus the
# case-insensitive takeover phrase — identical to the packaged gate.
MARKER = re.compile(r"\bPROVEN\b|\bEXPLOITABLE\b|\badmin takeover\b", re.IGNORECASE)

PREFIX = "mcp__hunter-os__"
LOCK_FILENAME = ".huntos-project"
DEFAULT_DB = "~/.huntos/hunt.db"

# Read-only tool names (suffix after the server prefix). Mirrors
# mcp/server.py's readOnlyHint tools; every other tool is a write.
READ_ONLY = frozenset({
    "hunt_status",
    "hunt_brief",
    "hunt_next",
    "hunt_target_list",
    "hunt_lead_list",
    "hunt_verify_report",
    "hunt_followup_list",
})


# ---------------------------------------------------------------------------
# the four contract points
# ---------------------------------------------------------------------------

def doctor(env: dict, cwd: str | None = None) -> tuple[int, list[str]]:
    """Report wiring state. Never blocks: returns (exit_code, lines)."""
    lines: list[str] = []
    base = Path(cwd or os.getcwd())
    db = Path(env.get("HUNT_DB") or os.path.expanduser(DEFAULT_DB))
    lines.append(f"db: {'ok' if db.is_file() else 'MISSING'} ({db})")
    lock = base / LOCK_FILENAME
    lines.append(f"lock: {'ok' if lock.is_file() else 'MISSING'} ({lock})")
    gate = gate_path()
    lines.append(f"claim gate: {'ok' if gate.is_file() else 'MISSING'} ({gate})")
    ok = db.is_file() and lock.is_file() and gate.is_file()
    return (0 if ok else 1), lines


def pre_write(tool_name: str, env: dict, cwd: str | None = None) -> tuple[int, str]:
    """May this write run? Exit 2 blocks. Read-only tools always pass."""
    suffix = _tool_suffix(tool_name)
    if suffix is None or suffix in READ_ONLY:
        return 0, ""
    problems: list[str] = []
    db = Path(env.get("HUNT_DB") or os.path.expanduser(DEFAULT_DB))
    if not db.is_file():
        problems.append(f"HUNT_DB not found at {db}")
    base = Path(cwd or os.getcwd())
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


def post_output(text: str, env: dict, cwd: str | None = None) -> tuple[int, str]:
    """Does this output's claim hold? Exit 2 vetoes. Fail-closed."""
    if not text or not MARKER.search(text):
        return 0, ""
    return _run_gate(text, env, cwd)


def stop(text: str, env: dict, cwd: str | None = None) -> tuple[int, str]:
    """Same judge as post_output, for the final turn. Exit 2 vetoes."""
    if not text or not MARKER.search(text):
        return 0, ""
    code, msg = _run_gate(text, env, cwd)
    if code == 0:
        return 0, ""
    # The gate could not verify (missing/unreachable db) — an unverifiable
    # claim cannot pass, unless the operator opted out explicitly.
    if _no_db(env) and env.get("HUNT_STOP_GATE_ALLOW_NO_DB") == "1":
        return 0, ("hunt-os claim gate: no ledger db resolvable, claims "
                   "unverified (HUNT_STOP_GATE_ALLOW_NO_DB=1)")
    return 2, msg


# ---------------------------------------------------------------------------
# shared internals
# ---------------------------------------------------------------------------

def gate_path() -> Path:
    """The claim gate that ships beside this file (byte-identical copy).

    Installed layout: the gate is copied into the same hooks/ dir. In the
    source tree it lives at _data/bin/claim_gate.py, so fall back to it.
    """
    beside = Path(__file__).resolve().parent / "claim_gate.py"
    if beside.is_file():
        return beside
    return Path(__file__).resolve().parent.parent / "bin" / "claim_gate.py"


def _tool_suffix(tool_name) -> str | None:
    if not isinstance(tool_name, str) or not tool_name.startswith(PREFIX):
        return None
    return tool_name[len(PREFIX):]


def _no_db(env: dict) -> bool:
    if env.get("HUNT_DB"):
        return not Path(env["HUNT_DB"]).is_file()
    return not Path(os.path.expanduser(DEFAULT_DB)).is_file()


def _run_gate(text: str, env: dict, cwd: str | None) -> tuple[int, str]:
    gate = gate_path()
    if not gate.is_file():
        return 2, "BLOCKED: claim gate missing from the hook pack; strong claim cannot be verified"
    try:
        proc = subprocess.run(
            [sys.executable, str(gate)],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60,
            env=dict(env),
            cwd=cwd or env.get("HUNT_PROJECT_DIR") or None,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 2, f"BLOCKED: claim gate could not run ({type(exc).__name__}); claim not verified"
    if proc.returncode == 0:
        return 0, ""
    if proc.returncode == 2:
        err = proc.stderr.decode("utf-8", "replace").strip() or "BLOCKED: unbacked claim"
        return 2, err
    return 2, f"BLOCKED: claim gate exited {proc.returncode}; claim not verified"


def response_text(payload: dict) -> str:
    """Extract the assistant-visible text from a tool-response payload."""
    if not isinstance(payload, dict):
        return ""
    resp = payload.get("tool_response")
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        parts = []
        content = resp.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        if isinstance(resp.get("text"), str):
            parts.append(resp["text"])
        if parts:
            return "\n".join(parts)
    return json.dumps(resp, ensure_ascii=False)


# ---------------------------------------------------------------------------
# harness translators (thin: each only reshapes I/O, never the decision)
# ---------------------------------------------------------------------------

def cli_pre_write(argv: list[str] | None = None) -> int:
    """Claude Code / ZCode PreToolUse: JSON on stdin, exit code on stdout."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        sys.stderr.write("BLOCKED: hook could not parse PreToolUse input\n")
        return 2
    code, msg = pre_write(payload.get("tool_name"), dict(os.environ),
                          payload.get("cwd"))
    if msg:
        sys.stderr.write(msg + "\n")
    return code


def cli_post_output(argv: list[str] | None = None) -> int:
    """Claude Code / ZCode PostToolUse: JSON on stdin, exit code on stdout."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return 0  # PostToolUse cannot undo the call; nothing to check
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool.startswith(PREFIX):
        return 0
    code, msg = post_output(response_text(payload), dict(os.environ),
                            payload.get("cwd"))
    if msg:
        sys.stderr.write(msg + "\n")
    return code


def cli_stop(argv: list[str] | None = None) -> int:
    """Claude Code / ZCode Stop: JSON on stdin, exit code on stdout."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        sys.stderr.write("BLOCKED: hook could not parse Stop input\n")
        return 2
    if not isinstance(payload, dict):
        sys.stderr.write("BLOCKED: Stop payload is not an object\n")
        return 2
    if payload.get("stop_hook_active") is True:
        return 0  # already continuing because of a stop hook
    msg_in = payload.get("last_assistant_message", "")
    if not isinstance(msg_in, str):
        msg_in = str(msg_in)
    code, msg = stop(msg_in, dict(os.environ), payload.get("cwd"))
    if msg:
        sys.stderr.write(msg + "\n")
    return code


def cli_doctor(argv: list[str] | None = None) -> int:
    """`hunt-os-hook doctor`: print the wiring report."""
    code, lines = doctor(dict(os.environ))
    for line in lines:
        print(line)
    return code


def cli_check(argv: list[str] | None = None) -> int:
    """Generic/Codex/OpenCode text mode: read text from stdin or argv[1],
    vet it, exit 0/2. This is the harness-agnostic entry point."""
    if argv:
        try:
            text = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            sys.stderr.write(f"BLOCKED: cannot read input file '{argv[0]}' ({exc})\n")
            return 2
    else:
        text = sys.stdin.read()
    code, msg = post_output(text, dict(os.environ))
    if msg:
        sys.stderr.write(msg + "\n")
    return code


ENTRY_POINTS = {
    "pre-write": cli_pre_write,
    "post-output": cli_post_output,
    "stop": cli_stop,
    "doctor": cli_doctor,
    "check": cli_check,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.stderr.write(
            "usage: hunt-os-hook <pre-write|post-output|stop|doctor|check> [file]\n"
        )
        return 2
    entry = ENTRY_POINTS.get(argv[0])
    if entry is None:
        sys.stderr.write(f"BLOCKED: unknown hook entry point {argv[0]!r}\n")
        return 2
    return entry(argv[1:])


if __name__ == "__main__":
    sys.exit(main())
