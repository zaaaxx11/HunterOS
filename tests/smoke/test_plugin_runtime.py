"""Plugin surface: generator determinism, hook decisions, and the MCP server.

Hermetic: the server and hooks are imported as plain modules from the plugin
tree; nothing is installed and no network is used. The MCP tests exercise the
pure protocol functions (handle / build_argv / parse_refusal) so they do not
depend on spawning a real CLI.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "hunter-os"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def server():
    return _load("hunter_os_mcp_server", PLUGIN / "mcp" / "server.py")


@pytest.fixture(scope="module")
def pre_gate():
    return _load("hunter_os_pre_gate", PLUGIN / "hooks" / "pre_tool_gate.py")


@pytest.fixture(scope="module")
def post_check():
    return _load("hunter_os_post_check", PLUGIN / "hooks" / "post_tool_check.py")


# ---------------------------------------------------------------- generator

def test_generator_check_is_clean():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_plugin.py"), "--check"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_manifest_version_matches_package_and_paths_exist():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = (REPO / "app" / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{manifest["version"]}"' in pyproject
    assert manifest["name"] == "hunter-os"
    for key in ("skills", "commands"):
        assert (PLUGIN / manifest[key].removeprefix("./")).is_dir(), key
    assert (PLUGIN / "hooks" / "hooks.json").is_file()


def test_marketplace_points_at_plugin_root():
    market = json.loads((REPO / "marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p["name"] == "hunter-os")
    assert (REPO / entry["source"]).resolve() == PLUGIN.resolve()


# ---------------------------------------------------------------- MCP server

def test_initialize_and_tools_list(server):
    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["protocolVersion"] == "2024-11-05"
    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in listed["result"]["tools"]}
    assert {"hunt_status", "hunt_finding_add", "hunt_target_add"} <= names


def test_notification_gets_no_response(server):
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_method_is_method_not_found(server):
    reply = server.handle({"jsonrpc": "2.0", "id": 9, "method": "nope"})
    assert reply["error"]["code"] == -32601


def test_unknown_tool_is_invalid_params_not_crash(server):
    reply = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                           "params": {"name": "hunt_rm", "arguments": {}}})
    assert reply["error"]["code"] == -32602


def test_flag_injection_is_rejected(server):
    reply = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "hunt_target_add",
                                      "arguments": {"name": "-rf", "url": "https://x.test"}}})
    assert reply["error"]["code"] == -32602


def test_integer_type_is_enforced(server):
    reply = server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                           "params": {"name": "hunt_finding_add",
                                      "arguments": {"target_id": "1", "title": "t", "klass": "Unknown"}}})
    assert reply["error"]["code"] == -32602


def test_build_argv_uses_json_flag_before_verb(server):
    argv = server.build_argv("hunt_status", {})
    assert argv == ["--json", "status"]


def test_build_argv_is_a_list_never_a_shell_string(server):
    argv = server.build_argv("hunt_target_add",
                             {"name": "Acme", "url": "https://acme.test"})
    assert isinstance(argv, list)
    assert all(isinstance(a, str) for a in argv)
    assert "Acme" in argv and "https://acme.test" in argv


def test_parse_refusal_reads_envelope(server):
    env = server.parse_refusal('{"ok": false, "code": 2, "error": "no target", "next": null}')
    assert env == {"ok": False, "code": 2, "error": "no target", "next": None}


def test_parse_refusal_ignores_human_text(server):
    assert server.parse_refusal("target #1 added") is None


def test_tools_call_status_on_empty_ledger(server, tmp_path, monkeypatch):
    monkeypatch.setenv("HUNT_DB", str(tmp_path / "hunt.db"))
    monkeypatch.setenv("PYTHONPATH", str(REPO / "app" / "src"))
    reply = server.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                           "params": {"name": "hunt_status", "arguments": {}}})
    assert reply["result"]["isError"] is False
    assert reply["result"]["content"][0]["type"] == "text"


# ---------------------------------------------------------------- pre-tool gate

def test_read_only_tool_always_passes(pre_gate, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_status", "cwd": str(tmp_path)}
    code, _ = pre_gate.decide(payload, {"HUNT_DB": str(tmp_path / "missing.db")}, str(tmp_path))
    assert code == 0


def test_write_tool_blocked_without_ledger(pre_gate, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_finding_add", "cwd": str(tmp_path)}
    code, message = pre_gate.decide(payload, {"HUNT_DB": str(tmp_path / "missing.db")}, str(tmp_path))
    assert code == 2
    assert message.startswith("BLOCKED:")


def test_write_tool_warn_mode_downgrades_to_pass(pre_gate, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_finding_add", "cwd": str(tmp_path)}
    env = {"HUNT_DB": str(tmp_path / "missing.db"), "HUNT_PLUGIN_GATE": "warn"}
    code, _ = pre_gate.decide(payload, env, str(tmp_path))
    assert code == 0


def test_unknown_hunter_tool_is_gated_fail_closed(pre_gate, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_mystery", "cwd": str(tmp_path)}
    code, _ = pre_gate.decide(payload, {"HUNT_DB": str(tmp_path / "missing.db")}, str(tmp_path))
    assert code == 2


def test_non_hunter_tool_is_ignored(pre_gate, tmp_path):
    payload = {"tool_name": "Bash", "cwd": str(tmp_path)}
    code, _ = pre_gate.decide(payload, {}, str(tmp_path))
    assert code == 0


# ---------------------------------------------------------------- post-tool check

def test_post_check_clean_output_passes(post_check, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_status",
               "tool_response": {"content": [{"type": "text", "text": "no claims here"}]}}
    code, _ = post_check.decide(payload, {"HUNT_DB": str(tmp_path / "missing.db")})
    assert code == 0


def test_post_check_unbacked_claim_is_vetoed(post_check, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_report",
               "tool_response": {"content": [{"type": "text", "text": "This is PROVEN."}]}}
    code, _ = post_check.decide(payload, {"HUNT_DB": str(tmp_path / "missing.db")})
    assert code == 2
