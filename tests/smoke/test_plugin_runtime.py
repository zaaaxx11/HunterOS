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
PLUGIN = REPO


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
    assert manifest["name"] == "hunt-os"
    for key in ("skills", "commands"):
        assert (PLUGIN / manifest[key].removeprefix("./")).is_dir(), key
    assert (PLUGIN / "hooks" / "hooks.json").is_file()


def test_marketplace_points_at_plugin_root():
    market = json.loads((REPO / "marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p["name"] == "hunt-os")
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


def test_ladder_verbs_are_exposed(server):
    """An MCP-only agent must be able to climb the evidence ladder.

    Before the ladder tools existed, an agent with MCP access alone could
    record a theoretical finding and nothing more — promote/verify/challenge/
    poc-run lived only in the slash commands and the shell.
    """
    names = set(server.TOOLS)
    for tool in ("hunt_poc_run", "hunt_finding_promote", "hunt_verify",
                 "hunt_challenge", "hunt_finding_overturn", "hunt_lead_mutate",
                 "hunt_wave_reaudit"):
        assert tool in names, f"missing ladder tool {tool}"


def test_ladder_argv_shapes(server):
    assert server.build_argv("hunt_poc_run", {
        "finding_id": 3, "poc_path": "/tmp/poc.py"}) == [
        "--json", "poc", "run", "--id=3", "--poc-path=/tmp/poc.py"]
    assert server.build_argv("hunt_finding_promote", {
        "finding_id": 3, "evidence_ref": "ref-1", "poc_path": "/tmp/p.py"}) == [
        "--json", "finding", "promote", "--id=3", "--evidence-ref=ref-1",
        "--poc-path=/tmp/p.py"]
    assert server.build_argv("hunt_verify", {
        "finding_id": 3, "artifact_type": "tx_hash", "body": "0xabc"}) == [
        "--json", "verify", "3", "tx_hash", "0xabc"]
    assert server.build_argv("hunt_wave_reaudit", {
        "wave_id": 2, "summary": "x" * 20}) == [
        "--json", "wave", "reaudit", "--wave-id=2", "--summary=" + "x" * 20]


def test_ladder_positional_rejects_flag_shaped_values(server):
    """A body/notes value starting with '-' must not become an argparse flag."""
    with pytest.raises(Exception):
        server.build_argv("hunt_verify", {
            "finding_id": 3, "artifact_type": "tx_hash", "body": "--evil"})


def test_pre_gate_read_only_set_matches_server(server, pre_gate):
    """The gate's read-only set must be exactly the server's read tools.

    Fail-closed means a NEW tool is gated automatically, but a read tool that
    is missing from the set would be wrongly gated — so the set is pinned.
    """
    read_tools = {
        name for name, tool in server.TOOLS.items()
        if tool["annotations"].get("readOnlyHint")
    }
    assert read_tools == set(pre_gate.READ_ONLY)


def test_pre_gate_gates_ladder_writes(pre_gate, tmp_path):
    """Every ladder tool needs a bound workspace (db + project lock)."""
    import os
    payload = {"tool_name": "mcp__hunter-os__hunt_finding_promote",
               "cwd": str(tmp_path)}
    code, msg = pre_gate.decide(payload, {"HUNT_DB": str(tmp_path / "nope.db")})
    assert code == 2
    assert "BLOCKED" in msg


def test_pre_gate_allows_ladder_write_when_bound(pre_gate, tmp_path):
    db = tmp_path / "hunt.db"
    db.write_bytes(b"")
    (tmp_path / ".huntos-project").write_text("{}", encoding="utf-8")
    payload = {"tool_name": "mcp__hunter-os__hunt_finding_promote",
               "cwd": str(tmp_path)}
    code, msg = pre_gate.decide(payload, {"HUNT_DB": str(db)})
    assert code == 0


def test_followup_and_budget_tools_are_exposed(server):
    """An MCP-only agent must be able to run the follow-up loop and the
    iteration budget: add / list / verify / drop / promote plus the budget
    verb. Without them both features are shell-only."""
    names = set(server.TOOLS)
    for tool in ("hunt_followup_add", "hunt_followup_list", "hunt_followup_verify",
                 "hunt_followup_drop", "hunt_followup_promote", "hunt_wave_budget"):
        assert tool in names, f"missing follow-up/budget tool {tool}"


def test_followup_argv_shapes(server):
    assert server.build_argv("hunt_followup_add", {
        "finding_id": 7, "title": "same class on the sibling pool"}) == [
        "--json", "followup", "add", "7", "same class on the sibling pool"]
    assert server.build_argv("hunt_followup_add", {
        "finding_id": 7, "title": "sibling pool", "kind": "variant",
        "hypothesis": "the sibling pool shares the same oracle"}) == [
        "--json", "followup", "add", "7", "sibling pool",
        "--kind=variant",
        "--hypothesis=the sibling pool shares the same oracle"]
    assert server.build_argv("hunt_followup_list", {"finding": 7, "target": 3,
                                                    "state": "open"}) == [
        "--json", "followup", "list", "--finding=7", "--target=3",
        "--state=open"]
    assert server.build_argv("hunt_followup_list", {}) == [
        "--json", "followup", "list"]
    assert server.build_argv("hunt_followup_verify", {
        "followup_id": 4, "evidence": "replayed on fork block 19000000"}) == [
        "--json", "followup", "verify", "4",
        "--evidence=replayed on fork block 19000000"]
    assert server.build_argv("hunt_followup_drop", {
        "followup_id": 4, "reason": "t" * 20}) == [
        "--json", "followup", "drop", "4", "--reason=" + "t" * 20]


def test_followup_promote_uses_roe_action_flag(server):
    """--roe-action, never --action: the `followup` subparser owns
    dest="action", and a flag claiming it would silently reroute the
    subcommand (E22 class)."""
    argv = server.build_argv("hunt_followup_promote", {
        "followup_id": 4, "klass": "oracle-manipulation",
        "severity": "high", "roe_action": "mutate"})
    assert argv == ["--json", "followup", "promote", "4",
                    "--klass=oracle-manipulation", "--severity=high",
                    "--roe-action=mutate"]
    assert "--action=mutate" not in argv
    assert not any(a.startswith("--action") for a in argv)


def test_followup_add_title_rejects_flag_shaped_values(server):
    """The title is a positional; a value argparse could read as a flag must
    not reach the CLI."""
    with pytest.raises(Exception):
        server.build_argv("hunt_followup_add",
                          {"finding_id": 7, "title": "--evil"})


def test_followup_drop_reason_minimum_is_enforced(server):
    """The CLI refuses a drop reason under 20 chars; the schema must catch it
    before the subprocess is spawned."""
    with pytest.raises(Exception):
        server.build_argv("hunt_followup_drop",
                          {"followup_id": 4, "reason": "too short"})


def test_wave_budget_argv_shapes(server):
    # No `set`: show only — --reason must be omitted entirely, because the CLI
    # treats a missing reason as "show only".
    assert server.build_argv("hunt_wave_budget", {"wave_id": 2}) == [
        "--json", "wave", "budget", "--wave-id=2"]
    assert server.build_argv("hunt_wave_budget", {"wave_id": 2, "set": 40,
                                                  "reason": "lead looked live"}) == [
        "--json", "wave", "budget", "--wave-id=2", "--set=40",
        "--reason=lead looked live"]
    # `set` without a reason still reaches the CLI, which refuses it.
    assert server.build_argv("hunt_wave_budget", {"wave_id": 2, "set": 0}) == [
        "--json", "wave", "budget", "--wave-id=2", "--set=0"]


def test_followup_list_is_the_only_new_read_tool(server):
    """The new read tool must be annotated read-only, and every other new tool
    must not be — the pre-tool gate pins its set against this."""
    new_tools = ("hunt_followup_add", "hunt_followup_list", "hunt_followup_verify",
                 "hunt_followup_drop", "hunt_followup_promote", "hunt_wave_budget")
    assert server.TOOLS["hunt_followup_list"]["annotations"].get("readOnlyHint") is True
    for name in new_tools:
        if name == "hunt_followup_list":
            continue
        assert not server.TOOLS[name]["annotations"].get("readOnlyHint"), name


def test_pre_gate_read_only_set_still_matches_server(server, pre_gate):
    """The parity test, re-asserted for the new surface: the gate's READ_ONLY
    set is exactly the server's read tools, so hunt_followup_list passes
    ungated and the other five new tools are gated."""
    read_tools = {
        name for name, tool in server.TOOLS.items()
        if tool["annotations"].get("readOnlyHint")
    }
    assert read_tools == set(pre_gate.READ_ONLY)
    assert "hunt_followup_list" in read_tools


def test_pre_gate_allows_followup_list_without_workspace(pre_gate, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_followup_list",
               "cwd": str(tmp_path)}
    code, _ = pre_gate.decide(payload, {"HUNT_DB": str(tmp_path / "nope.db")},
                              str(tmp_path))
    assert code == 0


def test_pre_gate_gates_followup_add_without_workspace(pre_gate, tmp_path):
    payload = {"tool_name": "mcp__hunter-os__hunt_followup_add",
               "cwd": str(tmp_path)}
    code, msg = pre_gate.decide(payload, {"HUNT_DB": str(tmp_path / "nope.db")})
    assert code == 2
    assert "BLOCKED" in msg


def test_pre_gate_allows_followup_add_when_bound(pre_gate, tmp_path):
    db = tmp_path / "hunt.db"
    db.write_bytes(b"")
    (tmp_path / ".huntos-project").write_text("{}", encoding="utf-8")
    payload = {"tool_name": "mcp__hunter-os__hunt_followup_add",
               "cwd": str(tmp_path)}
    code, _ = pre_gate.decide(payload, {"HUNT_DB": str(db)})
    assert code == 0


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
