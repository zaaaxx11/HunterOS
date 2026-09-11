"""Small tracked contracts for the public test boundary and CLI surface."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
SRC = APP / "src"


def _env(**extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(extra)
    return env


def test_import_and_module_entrypoint():
    import huntos

    assert huntos.__file__
    result = subprocess.run(
        [sys.executable, "-m", "huntos", "--help"],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_harness_list_and_mock_doctor(capsys, monkeypatch):
    monkeypatch.setenv("PATH", "")
    from huntos.cli.main import main

    assert main(["harness", "list"]) == 0
    listed = capsys.readouterr().out
    assert {"mock", "claude-code", "zcode", "hermes"} <= set(listed.split())
    assert main(["harness", "doctor", "mock"]) == 0
    diagnosed = capsys.readouterr().out
    assert "adapter: mock-harness" in diagnosed
    assert "duplex smoke: ok" in diagnosed


def test_non_tty_bare_entrypoint_does_not_prompt(capsys, monkeypatch):
    from huntos.cli.main import main

    class NonTTY:
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdin", NonTTY())
    assert main([]) == 2
    output = capsys.readouterr()
    assert "input(" not in (output.out + output.err).lower()
    assert "usage:" in (output.out + output.err).lower()


def test_target_prepare_requires_explicit_authorization():
    from huntos.cli.main import main

    with pytest.raises(SystemExit) as exc:
        main(["target", "prepare", str(ROOT)])
    assert exc.value.code == 2


def test_package_boundary_and_resources():
    import huntos

    package = Path(huntos.__file__).resolve().parent
    assert (package / "_data" / "bin" / "claim_gate.py").is_file()
    assert (package / "_data" / "hooks" / "claim_gate_wrapper.py").is_file()
    assert (package / "_data" / "idea" / "IDEA.md").is_file()
    assert not (package / "_data" / "attic").exists() or not any(
        (package / "_data" / "attic").rglob("*")
    )
