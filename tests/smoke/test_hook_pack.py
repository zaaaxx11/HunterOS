"""Hook pack contract: the universal 4-point hook and the Stop adaptor.

Hermetic: the hook module is imported as a plain file, no install and no
network. The Stop adaptor is exercised as a real subprocess because its
contract IS the exit code.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
HOOK = REPO / "app" / "src" / "huntos" / "_data" / "hooks" / "hunt_os_hook.py"
STOP = REPO / "scripts" / "claim-gate-stop.sh"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook():
    return _load("huntos_universal_hook", HOOK)


# ----------------------------------------------------------- the four points

def test_doctor_reports_missing_wiring(hook, tmp_path):
    code, lines = hook.doctor({"HUNT_DB": str(tmp_path / "nope.db")},
                              str(tmp_path))
    assert code == 1
    assert any("MISSING" in line for line in lines)


def test_doctor_ok_when_wired(hook, tmp_path):
    (tmp_path / "hunt.db").write_bytes(b"")
    (tmp_path / ".huntos-project").write_text("{}", encoding="utf-8")
    code, lines = hook.doctor({"HUNT_DB": str(tmp_path / "hunt.db")},
                              str(tmp_path))
    assert code == 0
    assert all("ok" in line for line in lines)


def test_pre_write_allows_read_only(hook):
    code, msg = hook.pre_write("mcp__hunter-os__hunt_status", {})
    assert code == 0


def test_pre_write_blocks_write_without_workspace(hook, tmp_path):
    code, msg = hook.pre_write(
        "mcp__hunter-os__hunt_finding_promote",
        {"HUNT_DB": str(tmp_path / "nope.db")}, str(tmp_path))
    assert code == 2
    assert "BLOCKED" in msg


def test_pre_write_warn_downgrade(hook, tmp_path):
    code, msg = hook.pre_write(
        "mcp__hunter-os__hunt_finding_promote",
        {"HUNT_DB": str(tmp_path / "nope.db"), "HUNT_PLUGIN_GATE": "warn"},
        str(tmp_path))
    assert code == 0
    assert msg.startswith("WARNING")


def test_pre_write_allows_write_when_bound(hook, tmp_path):
    (tmp_path / "hunt.db").write_bytes(b"")
    (tmp_path / ".huntos-project").write_text("{}", encoding="utf-8")
    code, _ = hook.pre_write(
        "mcp__hunter-os__hunt_finding_promote",
        {"HUNT_DB": str(tmp_path / "hunt.db")}, str(tmp_path))
    assert code == 0


def test_pre_write_ignores_foreign_tools(hook):
    code, _ = hook.pre_write("some_other_tool", {})
    assert code == 0


def test_post_output_passes_claim_free_text(hook):
    code, msg = hook.post_output("nothing strong here", {})
    assert code == 0


def test_post_output_vetoes_unbacked_claim(hook, tmp_path):
    """A PROVEN with no ledger db is fail-closed, not a warning."""
    code, msg = hook.post_output(
        "This is PROVEN[F-9] exploitable.", {"HUNT_DB": str(tmp_path / "nope.db")})
    assert code == 2
    assert "BLOCKED" in msg


def test_stop_vetoes_unbacked_claim(hook, tmp_path):
    code, msg = hook.stop("admin takeover achieved",
                          {"HUNT_DB": str(tmp_path / "nope.db")})
    assert code == 2


def test_stop_opt_out_is_explicit(hook, tmp_path):
    """The only downgrade is the operator setting the flag themselves."""
    code, msg = hook.stop(
        "admin takeover achieved",
        {"HUNT_DB": str(tmp_path / "nope.db"),
         "HUNT_STOP_GATE_ALLOW_NO_DB": "1"})
    assert code == 0
    assert "unverified" in msg


def test_stop_passes_claim_free_turn(hook):
    code, _ = hook.stop("all done, nothing to claim", {})
    assert code == 0


def test_read_only_set_matches_mcp_server(hook):
    """The hook's read set must equal the MCP server's readOnlyHint tools."""
    server = _load("hunter_os_mcp_server_for_hook_test",
                   REPO / "mcp" / "server.py")
    read_tools = {
        name for name, tool in server.TOOLS.items()
        if tool["annotations"].get("readOnlyHint")
    }
    assert read_tools == set(hook.READ_ONLY)


def test_response_text_shapes(hook):
    assert hook.response_text({"tool_response": "plain"}) == "plain"
    assert hook.response_text(
        {"tool_response": {"content": [{"text": "a"}, {"text": "b"}]}}) == "a\nb"
    assert hook.response_text({"tool_response": None}) == ""


def test_entry_points_dispatch(hook):
    assert set(hook.ENTRY_POINTS) == {
        "pre-write", "post-output", "stop", "doctor", "check"}


# ------------------------------------------------- the shipped Stop adaptor

def _stop(payload: dict, env: dict | None = None,
          home: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    child = dict(os.environ)
    child.pop("HUNT_DB", None)
    child.pop("HUNT_STOP_GATE_ALLOW_NO_DB", None)
    # Isolate HOME so the operator's real ~/.huntos/hunt.db cannot satisfy
    # the "no db resolvable" branch — the test must own that precondition.
    child["HOME"] = str(home or "/nonexistent-huntos-home")
    if env:
        child.update(env)
    return subprocess.run(
        ["sh", str(STOP)], input=json.dumps(payload), capture_output=True,
        text=True, env=child, timeout=60,
    )


def test_stop_adaptor_passes_claim_free_turn():
    proc = _stop({"last_assistant_message": "nothing to claim"})
    assert proc.returncode == 0, proc.stderr


def test_stop_adaptor_vetoes_unbacked_claim():
    """The documented exit-0 downgrade is gone: an unverifiable claim vetoes."""
    proc = _stop({"last_assistant_message": "the bug is PROVEN[F-1]"})
    assert proc.returncode == 2
    assert "BLOCKED" in proc.stderr


def test_stop_adaptor_opt_out_flag_restores_downgrade():
    proc = _stop({"last_assistant_message": "the bug is PROVEN[F-1]"},
                 {"HUNT_STOP_GATE_ALLOW_NO_DB": "1"})
    assert proc.returncode == 0
    assert "unverified" in proc.stderr


def test_stop_adaptor_fails_closed_on_malformed_stdin():
    proc = subprocess.run(
        ["sh", str(STOP)], input="not json", capture_output=True, text=True,
        timeout=60,
    )
    assert proc.returncode == 2


def test_stop_adaptor_respects_stop_hook_active():
    proc = _stop({"last_assistant_message": "PROVEN[F-1]",
                  "stop_hook_active": True})
    assert proc.returncode == 0


def test_stop_adaptor_vets_against_a_real_ledger(tmp_path):
    """With a bound db the gate judges the claim against the ledger."""
    db = tmp_path / "hunt.db"
    env = {"HUNT_DB": str(db)}
    sys.path.insert(0, str(REPO / "app" / "src"))
    try:
        from huntos.core import db as kernel
        from huntos.core.target_source import classify_target_source
        conn = kernel.connect()
        # `target prepare` is the honest intake path: it records the source,
        # the RoE and the workspace in one savepoint, which is what the
        # phase gates expect. Findings are refused outside hunting/verify.
        source = classify_target_source(str(tmp_path))
        tid = kernel.prepare_target(
            conn, "t", source, "evm",
            hosts="*", actions="read", authorization_note="unit test")
        kernel.score_target(conn, tid, 5.0)
        kernel.set_phase(conn, tid, "recon")
        surface_map = tmp_path / "surface_map.md"
        surface_map.write_text("surface map", encoding="utf-8")
        kernel.record_phase_artifact(conn, tid, "surface_map",
                                     str(surface_map))
        kernel.set_phase(conn, tid, "classify")
        attack_plan = tmp_path / "attack_plan.md"
        attack_plan.write_text("attack plan", encoding="utf-8")
        kernel.record_phase_artifact(conn, tid, "attack_plan",
                                     str(attack_plan))
        kernel.set_phase(conn, tid, "hunting")
        fid = kernel.add_finding(conn, tid, "f", "Unknown")
        conn.close()
        # unbacked claim -> veto
        proc = _stop({"last_assistant_message": f"PROVEN[F-{fid}]"}, env)
        assert proc.returncode == 2
        # claim-free turn -> pass
        proc = _stop({"last_assistant_message": "no claims"}, env)
        assert proc.returncode == 0
    finally:
        sys.path.pop(0)
