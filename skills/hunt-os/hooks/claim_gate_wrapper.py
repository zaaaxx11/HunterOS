#!/usr/bin/env python3
"""Cross-platform launcher for the installed HUNT-OS claim gate.

The gate is resolved only from this file's directory. Engine output remains on
stdin, and the child inherits stdout/stderr so its verdict and exact exit code
reach the harness unchanged.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _blocked(message: str) -> int:
    print(f"BLOCKED: {message}", file=sys.stderr)
    return 2


def main() -> int:
    try:
        hook_dir = Path(__file__).resolve(strict=True).parent
    except OSError:
        return _blocked("claim gate wrapper cannot resolve its own directory")

    gate = hook_dir / "claim_gate.py"
    try:
        with gate.open("rb"):
            pass
    except OSError:
        return _blocked(
            f"claim gate missing or unreadable beside the wrapper ({gate}) - "
            "reinstall the hook pack (hunt install)"
        )

    project_dir = os.environ.get("HUNT_PROJECT_DIR")
    cwd: str | None = None
    if project_dir:
        project = Path(project_dir)
        try:
            if not project.is_dir():
                raise NotADirectoryError(project_dir)
            cwd = str(project.resolve(strict=True))
        except OSError:
            return _blocked(
                f"HUNT_PROJECT_DIR is not a usable directory: {project_dir}"
            )

    try:
        # Do not capture any stream: stdin reaches the gate unchanged, and its
        # stdout/stderr remain the harness-facing streams.
        return subprocess.call([sys.executable, str(gate)], cwd=cwd)
    except (OSError, ValueError) as exc:
        return _blocked(f"claim gate could not be started ({exc})")


if __name__ == "__main__":
    raise SystemExit(main())
