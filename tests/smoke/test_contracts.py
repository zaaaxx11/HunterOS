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


# --- Phase 3: unified BLOCKED|NEXT refusals + --json envelope -----------------
# Every refusal speaks one shape: `BLOCKED: <what> | NEXT: <exact command>`
# on stderr with exit 2; `--json` emits {ok, code, error, next} on stdout.


def _isolated_db(tmp_path, monkeypatch) -> str:
    """Throwaway ledger + unbound cwd (no .huntos-project lock)."""
    path = str(tmp_path / "phase3.db")
    monkeypatch.setenv("HUNT_DB", path)
    monkeypatch.chdir(tmp_path)
    return path


def _walk_to_hunting(tmp_path) -> None:
    """Drive target #1 scoring -> hunting through the phase exit gates."""
    from huntos.cli.main import main

    sm = tmp_path / "surface_map.md"
    sm.write_text("map")
    ap = tmp_path / "attack_plan.md"
    ap.write_text("plan")
    assert main(["target", "add", "Demo", "https://demo.xyz"]) == 0
    assert main(["score", "1", "8"]) == 0
    assert main(["phase", "1", "recon"]) == 0
    assert main(["artifact", "1", "surface_map", str(sm)]) == 0
    assert main(["phase", "1", "classify"]) == 0
    assert main(["artifact", "1", "attack_plan", str(ap)]) == 0
    assert main(["phase", "1", "hunting"]) == 0


def test_blocked_wrong_phase_score_carries_next(tmp_path, monkeypatch, capsys):
    from huntos.cli.main import main

    _isolated_db(tmp_path, monkeypatch)
    assert main(["target", "add", "Demo", "https://demo.xyz"]) == 0
    assert main(["score", "1", "8"]) == 0
    assert main(["phase", "1", "recon"]) == 0
    capsys.readouterr()
    assert main(["score", "1", "5"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("BLOCKED:")
    assert "| NEXT: hunt next --target 1" in err


def test_blocked_wave_collision_carries_next(tmp_path, monkeypatch, capsys):
    from huntos.cli.main import main

    _isolated_db(tmp_path, monkeypatch)
    _walk_to_hunting(tmp_path)
    assert main(["wave", "open", "1", "architect"]) == 0
    capsys.readouterr()
    assert main(["wave", "open", "1", "red"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("BLOCKED:")
    assert "| NEXT: hunt wave close --wave-id 1 --verdict exhausted" in err


def test_blocked_promote_without_run_carries_next(tmp_path, monkeypatch, capsys):
    from huntos.cli.main import main

    _isolated_db(tmp_path, monkeypatch)
    _walk_to_hunting(tmp_path)
    assert main(["finding", "add", "1", "Drain", "Access"]) == 0
    poc = tmp_path / "poc.py"
    poc.write_text("print('poc')")
    capsys.readouterr()
    assert main(["finding", "promote", "--id", "1",
                 "--evidence-ref", "ev1", "--poc-path", str(poc)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("BLOCKED:")
    assert "| NEXT: hunt poc run --id 1 --poc-path" in err


def test_blocked_bogus_session_carries_next(tmp_path, monkeypatch, capsys):
    from huntos.cli.main import main

    _isolated_db(tmp_path, monkeypatch)
    assert main(["run", "status", "--session", "bogus"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("BLOCKED:")
    assert "| NEXT: hunt run status" in err


def test_json_refusal_envelope(tmp_path, monkeypatch, capsys):
    import json

    from huntos.cli.main import main

    _isolated_db(tmp_path, monkeypatch)
    assert main(["--json", "run", "status", "--session", "bogus"]) == 2
    out = capsys.readouterr()
    assert out.err == ""
    assert json.loads(out.out) == {
        "ok": False,
        "code": 2,
        "error": "conductor session 'bogus' does not exist",
        "next": "hunt run status",
    }


def test_json_bare_refusal_has_null_next(tmp_path, monkeypatch, capsys):
    """Refusals with inline remediation (MSYS guard) emit next: null."""
    import json

    from huntos.cli.main import main

    _isolated_db(tmp_path, monkeypatch)
    assert main(["--json", "finding", "add", "1",
                 "C:/Program Files/Git/api", "Access"]) == 2
    out = capsys.readouterr()
    assert out.err == ""
    payload = json.loads(out.out)
    assert payload["ok"] is False and payload["code"] == 2
    assert payload["next"] is None
    assert "MSYS" in payload["error"]


def test_split_blocked_roundtrip():
    from huntos.cli.errors import blocked, split_blocked

    error, nxt = split_blocked(
        blocked("wave #3 still open",
                "hunt wave close --wave-id 3 --verdict exhausted"))
    assert (error, nxt) == (
        "wave #3 still open",
        "hunt wave close --wave-id 3 --verdict exhausted",
    )
    assert split_blocked("BLOCKED: bare refusal") == ("bare refusal", None)
