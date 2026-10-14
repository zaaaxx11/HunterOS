#!/usr/bin/env python3
"""SessionStart hook: inject the HUNT-OS always-on rules into the session.

Reads always-on-rules.md from the plugin root (this file's parent directory's
parent), independent of the current working directory. Emits the ZCode/Claude
Code hook envelope on stdout (`hookSpecificOutput` with `additionalContext`),
because the runner parses stdout as strict JSON.

Never crashes the session: any failure prints a one-line notice inside a valid
envelope and exits 0.
Stdlib only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RULES_NAME = "always-on-rules.md"
MAX_CHARS = 60_000  # keep the injected context bounded


def rules_path() -> Path:
    return Path(__file__).resolve().parent.parent / RULES_NAME


def envelope(text: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            }
        },
        ensure_ascii=False,
    )


def build_context() -> str:
    path = rules_path()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return (
            f"HUNT-OS notice: always-on rules unavailable ({type(exc).__name__}). "
            "Treat all active testing as default-deny until an owner-approved RoE is confirmed."
        )
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[truncated: always-on rules exceed the injection limit]\n"
    return text


def main() -> int:
    try:
        sys.stdout.write(envelope(build_context()) + "\n")
    except Exception as exc:  # noqa: BLE001 - a hook must never crash the session
        try:
            sys.stdout.write(envelope(f"HUNT-OS notice: session_start failed ({type(exc).__name__})") + "\n")
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
