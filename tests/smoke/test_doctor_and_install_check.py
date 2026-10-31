"""`install --check` on a bare tree, and doctor's runtime-readiness block.

Two contracts live here:

A. `hunt install --check` treats a MISSING manifest as an informational
   success (exit 0) — "not installed" is a legitimate preflight answer, not
   an error. `--uninstall` on the same state still exits non-zero: removing
   something that was never installed is a genuine operator mistake, and the
   fix must not over-correct into making that a no-op.

B. `hunt doctor` appends three runtime-readiness checks after the workspace
   preflight: the MCP server imports and its tool table is well-formed, the
   generated plugin tree is not drifted, and every installed hooks.json
   parses. They print through the same `report()` helper, so the output
   shape and the exit-2-on-failure contract are unchanged.

Hermetic: no network, stdlib + pytest only. The doctor cases call
`cmd_doctor` directly with an argparse.Namespace (the same shape
`cmd_harness` builds for a skills adapter) and capture stdout with capsys;
the install cases drive `huntos.installer.main` in-process.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
APP_SRC = REPO / "app" / "src"


def _doctor(monkeypatch, tmp_path, adapter=None, scope="project", dir_=None):
    """Run cmd_doctor in-process and return (exit_code, stdout_text).

    The hunt db is pointed at a throwaway path so the db-open check never
    touches the operator's ledger, and cwd is a fresh tmp dir so
    project-lock reports "unbound" deterministically.
    """
    from huntos.cli.main import cmd_doctor

    monkeypatch.setenv("HUNT_DB", str(tmp_path / "doctor.db"))
    monkeypatch.chdir(tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_doctor(
            argparse.Namespace(adapter=adapter, scope=scope, dir=dir_), None)
    return rc, buf.getvalue()


def _main_module():
    """The huntos.cli.main MODULE (not the `main` function it re-exports).

    `huntos/cli/__init__.py` does `from .main import main`, so the attribute
    `huntos.cli.main` is the function; the module itself only comes back from
    importlib (or sys.modules). Monkeypatching needs the module.
    """
    import importlib
    return importlib.import_module("huntos.cli.main")


# --------------------------------------------------------------------------
# A. install --check on a tree with no manifest
# --------------------------------------------------------------------------

def test_check_without_manifest_is_informational_success(tmp_path, monkeypatch, capsys):
    """A bare directory is a SUCCESSFUL preflight answer, not an error.

    Before the fix this printed `error: no .hunt-os-manifest.json in ... -
    nothing to check` to stderr and exited 1, so any CI probe that ran
    `install --check` before installing failed on a clean machine.
    """
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    dest = tmp_path / installer.ADAPTER_BASE["hermes"]
    dest.mkdir(parents=True)

    rc = installer.main(["--adapter", "hermes", "--check"])
    out = capsys.readouterr()

    assert rc == 0, f"--check on a bare tree must exit 0, got {rc}"
    assert out.err == "", f"nothing may go to stderr: {out.err!r}"
    assert "not installed" in out.out
    # the resolved skills dir is named ...
    assert str(dest) in out.out
    # ... and the exact command that fixes it
    assert "hunt install --adapter hermes --scope project" in out.out


def test_check_without_manifest_through_the_cli_door(tmp_path, monkeypatch, capsys):
    """The same contract through `hunt install --check` (main() delegation)."""
    from huntos.cli.main import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUNT_DB", str(tmp_path / "cli.db"))
    rc = main(["install", "--adapter", "hermes", "--scope", "project", "--check"])
    out = capsys.readouterr()

    assert rc == 0
    assert "not installed" in out.out
    assert "hunt install --adapter hermes --scope project" in out.out


def test_uninstall_without_manifest_still_fails(tmp_path, monkeypatch, capsys):
    """Pinned: the fix must NOT make uninstall-on-nothing a silent success.

    `--check` asks a question ("is anything installed?"); `--uninstall`
    performs an action ("remove what is installed"). Only the question has a
    benign empty answer.
    """
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    dest = tmp_path / installer.ADAPTER_BASE["hermes"]
    dest.mkdir(parents=True)

    with pytest.raises(SystemExit) as exc:
        installer.main(["--adapter", "hermes", "--uninstall"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no .hunt-os-manifest.json" in err
    assert "refusing to uninstall" in err


def test_check_after_uninstall_reports_not_installed(tmp_path, monkeypatch, capsys):
    """The reproduced bug: install -> uninstall -> check must be exit 0."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    argv = ["--adapter", "hermes"]
    capsys.readouterr()
    assert installer.main(argv) == 0
    capsys.readouterr()
    assert installer.main(argv + ["--uninstall"]) == 0
    capsys.readouterr()

    rc = installer.main(argv + ["--check"])
    out = capsys.readouterr()
    assert rc == 0
    assert "not installed" in out.out


def test_check_on_a_fresh_install_is_still_clean(tmp_path, monkeypatch, capsys):
    """The manifest-present path is byte-identical to before the fix."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    dest = tmp_path / installer.ADAPTER_BASE["hermes"]
    capsys.readouterr()
    assert installer.main(["--adapter", "hermes"]) == 0
    capsys.readouterr()

    rc = installer.main(["--adapter", "hermes", "--check"])
    out = capsys.readouterr()
    assert rc == 0
    assert "check OK" in out.out
    assert str(dest) in out.out
    for token in ("MISSING", "MODIFIED", "FAILED", "DRIFT", "not installed"):
        assert token not in out.out, f"clean --check reported {token}: {out.out!r}"


def test_check_still_fails_on_real_drift(tmp_path, monkeypatch, capsys):
    """Exit 1 survives for a genuinely modified installed file."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    assert installer.main(["--adapter", "hermes"]) == 0
    capsys.readouterr()

    skill = tmp_path / installer.ADAPTER_BASE["hermes"] / installer.ROUTER_NAME / "SKILL.md"
    skill.write_text("tampered\n", encoding="utf-8")

    rc = installer.main(["--adapter", "hermes", "--check"])
    out = capsys.readouterr()
    assert rc == 1
    assert "MODIFIED:" in out.out
    assert "check FAILED" in out.out


def test_check_still_reports_source_drift_warning(tmp_path, monkeypatch, capsys):
    """The informational source-drift WARNING path is untouched."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    assert installer.main(["--adapter", "hermes"]) == 0
    capsys.readouterr()

    manifest_path = (tmp_path / installer.ADAPTER_BASE["hermes"]
                     / installer.MANIFEST_NAME)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_tree_hash"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    rc = installer.main(["--adapter", "hermes", "--check"])
    out = capsys.readouterr()
    assert rc == 0, "source drift is informational only"
    assert "WARNING: source changed since install" in out.out
    assert "check OK" in out.out


# --------------------------------------------------------------------------
# B. doctor's runtime-readiness block
# --------------------------------------------------------------------------

def test_doctor_mcp_server_check_passes(monkeypatch, tmp_path):
    """The hand-written MCP server imports and every tool schema is valid."""
    rc, out = _doctor(monkeypatch, tmp_path)
    assert "mcp-server: ok" in out
    assert "FAIL" not in out
    assert rc == 0


def test_doctor_plugin_tree_check_passes(monkeypatch, tmp_path):
    """The generated plugin tree matches the committed checkout."""
    rc, out = _doctor(monkeypatch, tmp_path)
    assert "plugin-tree: ok" in out
    assert rc == 0


def test_doctor_hooks_json_reports_none_installed(monkeypatch, tmp_path):
    """No adapter and no installed dest -> an OK line, not a failure."""
    rc, out = _doctor(monkeypatch, tmp_path)
    assert "hooks-json: ok" in out
    assert "no installed hooks to validate" in out
    assert rc == 0


def test_doctor_runtime_checks_are_appended_after_the_preflight(monkeypatch, tmp_path):
    """Ordering contract: the new block comes after the existing checks."""
    rc, out = _doctor(monkeypatch, tmp_path)
    names = [line.split(":")[0] for line in out.splitlines() if line.strip()]
    for existing in ("cli-import", "db-open", "project-lock", "claim-gate",
                     "hook-wrapper"):
        assert existing in names, f"preflight lost {existing}: {names}"
    assert names.index("mcp-server") > names.index("hook-wrapper")
    assert names.index("plugin-tree") > names.index("mcp-server")
    assert names.index("hooks-json") > names.index("plugin-tree")
    assert rc == 0


def test_doctor_validates_an_installed_hooks_json(tmp_path, monkeypatch):
    """An installed hooks.json in the Claude-Code shape validates OK."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    dest = tmp_path / "dest"
    capsys_buf = io.StringIO()
    with redirect_stdout(capsys_buf):
        assert installer.main(["--adapter", "hermes", "--dir", str(dest)]) == 0
    hooks = dest / installer.ROUTER_NAME / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text(json.dumps({
        "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": "true"}]}]},
    }), encoding="utf-8")

    rc, out = _doctor(monkeypatch, tmp_path, adapter="hermes", dir_=str(dest))
    assert "hooks-json: ok" in out
    assert "1 document(s) validated" in out
    assert rc == 0


def test_doctor_rejects_a_hooks_json_whose_values_are_not_lists(tmp_path, monkeypatch):
    """A malformed installed hooks document FAILs the check."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    dest = tmp_path / "dest"
    with redirect_stdout(io.StringIO()):
        assert installer.main(["--adapter", "hermes", "--dir", str(dest)]) == 0
    hooks = dest / installer.ROUTER_NAME / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text(json.dumps({"SessionStart": "not-a-list"}), encoding="utf-8")

    rc, out = _doctor(monkeypatch, tmp_path, adapter="hermes", dir_=str(dest))
    assert "hooks-json: FAIL" in out
    assert "must be a list" in out
    assert rc == 2


def test_doctor_rejects_unparseable_hooks_json(tmp_path, monkeypatch):
    """A hooks.json that is not JSON at all FAILs the check."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    dest = tmp_path / "dest"
    with redirect_stdout(io.StringIO()):
        assert installer.main(["--adapter", "hermes", "--dir", str(dest)]) == 0
    hooks = dest / installer.ROUTER_NAME / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text("this is not json", encoding="utf-8")

    rc, out = _doctor(monkeypatch, tmp_path, adapter="hermes", dir_=str(dest))
    assert "hooks-json: FAIL" in out
    assert rc == 2


def test_doctor_exits_2_when_a_runtime_check_fails(monkeypatch, tmp_path):
    """A failing runtime check still drives the exit-2 contract.

    The plugin-tree check is the one forced to fail here: its subprocess is
    patched to return a non-zero CompletedProcess carrying a DRIFT payload,
    which is exactly what `build_plugin.py --check` does on real drift.
    """
    main_mod = _main_module()

    drift = subprocess.CompletedProcess(
        args=["build_plugin.py", "--check"], returncode=1,
        stdout="DRIFT:\n  skills/hunt-os/SKILL.md\nrun: python scripts/build_plugin.py\n",
        stderr="")
    monkeypatch.setattr(main_mod.subprocess, "run", lambda *a, **kw: drift)

    rc, out = _doctor(monkeypatch, tmp_path)
    assert rc == 2, f"a FAIL must exit 2, got {rc}"
    assert "plugin-tree: FAIL" in out
    assert "DRIFT" in out
    # the other checks still ran and reported
    assert "mcp-server: ok" in out


def test_doctor_mcp_server_check_fails_when_the_server_is_broken(monkeypatch, tmp_path):
    """A missing or raising MCP server is a FAIL, never a traceback."""
    main_mod = _main_module()

    monkeypatch.setattr(main_mod, "_mcp_server_path",
                        lambda: tmp_path / "gone" / "server.py")
    # the resolved path is missing AND a candidate root does carry the file:
    # that is a broken checkout, not a packaging gap
    real_root = tmp_path / "real"
    (real_root / "mcp").mkdir(parents=True)
    (real_root / "mcp" / "server.py").write_text("# real\n", encoding="utf-8")
    monkeypatch.setattr(main_mod, "_repo_root_candidates", lambda: [real_root])

    rc, out = _doctor(monkeypatch, tmp_path)
    assert "mcp-server: FAIL" in out
    assert "not found" in out
    assert rc == 2


def test_doctor_mcp_server_check_fails_on_a_bad_tool_schema(monkeypatch, tmp_path):
    """A tool whose inputSchema is not an object FAILs the import check."""
    main_mod = _main_module()

    broken = tmp_path / "server.py"
    broken.write_text(
        "TOOLS = {'hunt_x': {'inputSchema': {'type': 'string'}}}\n",
        encoding="utf-8")
    monkeypatch.setattr(main_mod, "_mcp_server_path", lambda: broken)

    rc, out = _doctor(monkeypatch, tmp_path)
    assert "mcp-server: FAIL" in out
    assert "expected 'object'" in out
    assert rc == 2


def test_doctor_plugin_tree_ok_when_the_build_script_is_absent(monkeypatch, tmp_path):
    """An installed wheel has no scripts/ dir: that is OK, not a failure."""
    main_mod = _main_module()

    monkeypatch.setattr(main_mod, "_build_plugin_script",
                        lambda: tmp_path / "no-such-scripts" / "build_plugin.py")
    rc, out = _doctor(monkeypatch, tmp_path)
    assert "plugin-tree: ok" in out
    assert "build script not packaged" in out
    assert rc == 0


def test_doctor_mcp_server_ok_when_not_packaged(monkeypatch, tmp_path):
    """A wheel install ships no mcp/server.py: that is OK, not a failure.

    The wheel's package-data allowlist (app/pyproject.toml) covers only
    `huntos/_data/**`; `mcp/server.py` lives at the repo root and is not
    packaged. Before this was pinned, a wheel install reported
    `mcp-server: FAIL: mcp server not found at ...` and exited 2, so
    `hunt doctor` failed on every legitimate wheel install.
    """
    main_mod = _main_module()

    # a checkout root that exists but carries no mcp/ dir ...
    empty_root = tmp_path / "checkout"
    (empty_root / "scripts").mkdir(parents=True)
    monkeypatch.setattr(main_mod, "_repo_root", lambda: empty_root)
    # ... and no candidate root carrying the server either
    monkeypatch.setattr(main_mod, "_repo_root_candidates", lambda: [empty_root])

    rc, out = _doctor(monkeypatch, tmp_path)
    assert "mcp-server: ok" in out
    assert "mcp server not packaged" in out
    assert rc == 0


def test_doctor_mcp_server_fails_when_a_checkout_has_it_but_the_path_is_wrong(
        monkeypatch, tmp_path):
    """The FAIL path survives: a checkout that HAS the server still fails.

    "Not packaged" must not become a blanket excuse. When some candidate
    root does carry mcp/server.py but the resolved path does not, the check
    FAILs — that is a real broken install, not a packaging gap.
    """
    main_mod = _main_module()

    real_root = tmp_path / "real"
    (real_root / "mcp").mkdir(parents=True)
    (real_root / "mcp" / "server.py").write_text("# real server\n", encoding="utf-8")
    wrong_root = tmp_path / "wrong"
    wrong_root.mkdir()

    monkeypatch.setattr(main_mod, "_repo_root", lambda: wrong_root)
    monkeypatch.setattr(main_mod, "_repo_root_candidates", lambda: [real_root])

    rc, out = _doctor(monkeypatch, tmp_path)
    assert "mcp-server: FAIL" in out
    assert "not found" in out
    assert rc == 2


def test_doctor_through_the_cli_door(tmp_path, monkeypatch, capsys):
    """`hunt doctor` end-to-end carries the new checks in its output."""
    from huntos.cli.main import main

    monkeypatch.setenv("HUNT_DB", str(tmp_path / "door.db"))
    monkeypatch.chdir(tmp_path)
    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    for name in ("cli-import", "db-open", "project-lock", "claim-gate",
                 "hook-wrapper", "mcp-server", "plugin-tree", "hooks-json"):
        assert f"{name}: ok" in out, f"{name} missing from `hunt doctor` output"


def test_doctor_harness_door_carries_the_new_checks(tmp_path, monkeypatch, capsys):
    """`hunt harness doctor <skills adapter>` delegates to the same checklist.

    The harness door resolves the destination exactly like `hunt install`
    with no --dir (project scope under cwd), so the install in this test
    targets that same location.
    """
    from huntos import installer
    from huntos.cli.main import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUNT_DB", str(tmp_path / "harness.db"))
    capsys.readouterr()
    assert installer.main(["--adapter", "hermes"]) == 0
    capsys.readouterr()

    rc = main(["harness", "doctor", "hermes"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "mcp-server: ok" in out
    assert "plugin-tree: ok" in out


# --------------------------------------------------------------------------
# C. the checks agree with the real artifacts
# --------------------------------------------------------------------------

def test_mcp_server_tool_table_is_really_wellformed():
    """Independent proof of what the doctor check asserts (no doctor code)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "huntos_test_mcp_server", REPO / "mcp" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert isinstance(module.TOOLS, dict) and module.TOOLS
    for name, tool in module.TOOLS.items():
        schema = tool["inputSchema"]
        assert isinstance(schema, dict), name
        assert schema["type"] == "object", name
        assert "additionalProperties" in schema, name


def test_build_plugin_check_really_is_clean():
    """The plugin-tree check's subprocess passes on this checkout."""
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_plugin.py"), "--check"],
        cwd=REPO, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(APP_SRC)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
