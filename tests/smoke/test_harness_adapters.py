"""HUNT-ADAPTER/1 conformance for the real-harness adapters.

Both hermes_cli.py and codex_cli.py drive an external CLI in headless mode.
These tests point them at a FAKE executable (a shell script that prints a
canned answer), so the protocol is exercised for real — envelopes, duplex
tool mediation, fail-closed errors — without invoking a model or the network.
"""
import importlib.util
import json
import os
import pathlib
import stat
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
ADAPTERS = {
    "hermes": REPO / "examples" / "adapters" / "hermes_cli.py",
    "codex": REPO / "examples" / "adapters" / "codex_cli.py",
}

# A fake headless CLI: echoes a scripted answer, and on the second call
# (the follow-up after a tool result) reports what it observed.
FAKE_CLI = """#!/bin/sh
# args after the prompt are ignored; we answer from the call counter.
N=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
N=$((N + 1))
echo "$N" > "$COUNT_FILE"
if [ "$N" -eq 1 ]; then
  printf '%s\\n' 'TOOL_REQUEST {"command": ["hunt", "status"]}'
else
  printf '%s\\n' 'observed the ledger; nothing further to probe'
fi
exit 0
"""


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def fake_cli(tmp_path):
    counter = tmp_path / "count"
    script = tmp_path / "fake-agent"
    script.write_text(FAKE_CLI, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    env = dict(os.environ)
    env["COUNT_FILE"] = str(counter)
    env["HUNT_ADAPTER_TIMEOUT"] = "30"
    return script, env


def _spawn(adapter_path: pathlib.Path, bin_path: pathlib.Path, env: dict):
    child = dict(env)
    child["HUNT_ADAPTER_HERMES_BIN"] = str(bin_path)
    child["HUNT_ADAPTER_CODEX_BIN"] = str(bin_path)
    return subprocess.Popen(
        [sys.executable, str(adapter_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, env=child,
    )


def _send(proc, method: str, payload: dict, request_id: str = "r-1"):
    proc.stdin.write(json.dumps({
        "protocol": "HUNT-ADAPTER/1", "request_id": request_id,
        "type": "request", "method": method, "payload": payload,
    }) + "\n")
    proc.stdin.flush()


def _read(proc) -> dict:
    line = proc.stdout.readline()
    assert line, "adapter closed stdout without a response"
    return json.loads(line)


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_doctor_reports_capabilities(name, fake_cli):
    script, env = fake_cli
    proc = _spawn(ADAPTERS[name], script, env)
    try:
        _send(proc, "doctor", {})
        reply = _read(proc)
        assert reply["type"] == "response"
        assert reply["method"] == "doctor"
        caps = reply["payload"]["capabilities"]
        assert caps["protocol"] == "HUNT-ADAPTER/1"
        # the four the conductor requires for a managed run
        for feature in ("hunt_tool", "post_output_hook", "headless_turn"):
            assert caps["features"][feature] is True, feature
        assert isinstance(reply["payload"]["diagnostics"], list)
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_full_duplex_turn(name, fake_cli):
    """run_turn -> tool_request -> tool_result -> output -> completed."""
    script, env = fake_cli
    proc = _spawn(ADAPTERS[name], script, env)
    try:
        _send(proc, "start_session", {"session_id": "S-1"}, "r-0")
        assert _read(proc)["payload"]["started"] is True

        _send(proc, "run_turn", {
            "attempt_id": "A-1", "session_id": "S-1", "lane": "architect",
            "round": 1, "capsule": {"role": "architect", "brief": "brief text"},
        }, "r-1")
        first = _read(proc)
        assert first["type"] == "event"
        assert first["payload"]["type"] == "tool_request"
        command = first["payload"]["command"]
        assert command[0] == "hunt"

        _send(proc, "tool_result", {
            "attempt_id": "A-1",
            "result": {"operation_id": first["payload"]["operation_id"],
                       "output": "hunt status ok", "ok": True},
        }, "r-2")
        assert _read(proc)["payload"]["accepted"] is True

        kinds = []
        while True:
            msg = _read(proc)
            if msg["type"] == "response":
                assert msg["payload"]["completed"] is True
                break
            kinds.append(msg["payload"]["type"])
        assert "assistant_output" in kinds
        assert "usage" in kinds
        assert "attempt_completed" in kinds
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_prose_only_turn_completes_without_tool_request(name, tmp_path):
    """A turn whose answer carries no TOOL_REQUEST still terminates."""
    script = tmp_path / "prose-only"
    script.write_text("#!/bin/sh\nprintf '%s\\n' 'nothing to probe here'\nexit 0\n",
                      encoding="utf-8")
    script.chmod(0o755)
    env = dict(os.environ)
    env["HUNT_ADAPTER_TIMEOUT"] = "30"
    proc = _spawn(ADAPTERS[name], script, env)
    try:
        _send(proc, "run_turn", {"attempt_id": "A-9", "session_id": "S-1",
                                 "lane": "chainer", "round": 1}, "r-1")
        kinds = []
        while True:
            msg = _read(proc)
            if msg["type"] == "response":
                break
            kinds.append(msg["payload"]["type"])
        assert "assistant_output" in kinds
        assert "attempt_completed" in kinds
        assert "tool_request" not in kinds
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_missing_executable_fails_closed(name, tmp_path):
    env = dict(os.environ)
    env["HUNT_ADAPTER_HERMES_BIN"] = str(tmp_path / "nope")
    env["HUNT_ADAPTER_CODEX_BIN"] = str(tmp_path / "nope")
    proc = _spawn(ADAPTERS[name], tmp_path / "nope", env)
    try:
        _send(proc, "doctor", {})
        # doctor resolves the binary and exits non-zero when it is absent
        proc.wait(timeout=30)
        assert proc.returncode != 0
        assert "not found" in proc.stderr.read()
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_cli_failure_fails_closed(name, tmp_path):
    script = tmp_path / "broken"
    script.write_text("#!/bin/sh\necho 'boom' >&2\nexit 3\n", encoding="utf-8")
    script.chmod(0o755)
    env = dict(os.environ)
    env["HUNT_ADAPTER_TIMEOUT"] = "30"
    proc = _spawn(ADAPTERS[name], script, env)
    try:
        _send(proc, "run_turn", {"attempt_id": "A-1", "session_id": "S-1",
                                 "lane": "architect", "round": 1}, "r-1")
        proc.wait(timeout=30)
        assert proc.returncode != 0
        assert "exited 3" in proc.stderr.read()
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_unknown_method_fails_closed(name, fake_cli):
    script, env = fake_cli
    proc = _spawn(ADAPTERS[name], script, env)
    try:
        _send(proc, "not_a_method", {})
        proc.wait(timeout=30)
        assert proc.returncode != 0
        assert "unknown method" in proc.stderr.read()
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_cancel_and_stop(name, fake_cli):
    script, env = fake_cli
    proc = _spawn(ADAPTERS[name], script, env)
    try:
        _send(proc, "cancel_turn", {"attempt_id": "A-1"}, "r-1")
        assert _read(proc)["payload"]["cancelled"] is True
        _send(proc, "stop_session", {"session_id": "S-1"}, "r-2")
        assert _read(proc)["payload"]["stopped"] is True
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_tool_result_for_unknown_attempt_fails_closed(name, fake_cli):
    script, env = fake_cli
    proc = _spawn(ADAPTERS[name], script, env)
    try:
        _send(proc, "tool_result", {"attempt_id": "GHOST",
                                    "result": {"output": "x", "ok": True}}, "r-1")
        proc.wait(timeout=30)
        assert proc.returncode != 0
        assert "unknown attempt" in proc.stderr.read()
    finally:
        if proc.poll() is None:
            proc.kill()


@pytest.mark.parametrize("name", ["hermes", "codex"])
def test_tool_request_extraction_is_narrow(name):
    """Only the exact TOOL_REQUEST {"command": [...]} line is honoured."""
    mod = _load(f"{name}_adapter_for_extract", ADAPTERS[name])
    assert mod._extract_tool_request(
        'TOOL_REQUEST {"command": ["hunt", "status"]}') == ["hunt", "status"]
    # prose that merely mentions the token is not a request
    assert mod._extract_tool_request(
        "I considered a TOOL_REQUEST but decided against it") is None
    # malformed JSON is not a request
    assert mod._extract_tool_request("TOOL_REQUEST {not json") is None
    # a non-list command is not a request
    assert mod._extract_tool_request('TOOL_REQUEST {"command": "hunt status"}') is None
    assert mod._extract_tool_request('TOOL_REQUEST {"command": []}') is None
    assert mod._extract_tool_request("") is None
