#!/usr/bin/env python3
"""HUNT-ADAPTER/1 executable that drives a real Hermes agent session.

Unlike examples/adapters/reference_jsonl.py (a deterministic simulator), this
adapter shells out to the actual `hermes` CLI in headless mode, so a managed
`hunt run` executes a real lane turn on a real model.

Contract (docs/HUNT-ADAPTER-1.md):
  - one UTF-8 JSON object per stdout line; stdout is protocol-only
  - every envelope is exactly {protocol, request_id, type, method, payload}
  - a tool_request PAUSES the turn; HunterOS mediates the command through its
    own CLI and immediately sends tool_result back
  - the adapter never writes the ledger itself

The lane capsule (role doctrine, brief, RoE) arrives in the run_turn payload
and becomes the prompt. Provider credentials are inherited from the
environment and never appear on stdout/stderr or in protocol payloads.

Env:
  HUNT_ADAPTER_HERMES_BIN   path to the hermes executable (default: hermes)
  HUNT_ADAPTER_TIMEOUT      seconds per headless turn (default: 600)
  HUNT_ADAPTER_MODEL        optional model override passed through to hermes

Stdlib only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import NoReturn

PROTOCOL = "HUNT-ADAPTER/1"
ADAPTER_ID = "hermes-cli"
ADAPTER_VERSION = "1.0.0"

BIN = os.environ.get("HUNT_ADAPTER_HERMES_BIN", "hermes")
TIMEOUT = float(os.environ.get("HUNT_ADAPTER_TIMEOUT", "600"))
MODEL = os.environ.get("HUNT_ADAPTER_MODEL", "")

CAPABILITIES = {
    "type": "capabilities",
    "protocol": PROTOCOL,
    "adapter_id": ADAPTER_ID,
    "version": ADAPTER_VERSION,
    "features": {
        "skill_injection": True,
        "hunt_tool": True,
        "post_output_hook": True,
        "headless_turn": True,
        "subagents": False,
        "cancel": True,
        "heartbeats": False,
        "model_routing": bool(MODEL),
    },
}

# attempt_id -> the request_id of the run_turn that opened it, so a
# tool_result can be correlated back to the right turn.
_pending: dict[str, str] = {}


def send(request_id: str, kind: str, method: str, payload: dict) -> None:
    sys.stdout.write(json.dumps(
        {"protocol": PROTOCOL, "request_id": request_id, "type": kind,
         "method": method, "payload": payload},
        sort_keys=True, separators=(",", ":"),
    ) + "\n")
    sys.stdout.flush()


def event(request_id: str, payload: dict) -> None:
    send(request_id, "event", "run_turn", payload)


def _fail(message: str) -> "NoReturn":
    sys.stderr.write(f"{ADAPTER_ID} adapter error: {message}\n")
    sys.stderr.flush()
    raise SystemExit(2)


def _hermes_argv() -> list[str]:
    path = shutil.which(BIN) if os.sep not in BIN else BIN
    if not path or not os.path.isfile(path):
        _fail(f"hermes executable not found: {BIN!r} "
              f"(set HUNT_ADAPTER_HERMES_BIN)")
    return [path]


def _capsule_prompt(payload: dict) -> str:
    """Render the lane capsule as the headless-turn prompt.

    The capsule is the canonical bounded per-attempt input HunterOS built
    (identifiers, target, source, RoE, role text, brief). It is passed
    through as structured context; the adapter adds no doctrine of its own.
    """
    capsule = payload.get("capsule") or {}
    lines: list[str] = []
    role = capsule.get("role") or capsule.get("lane") or "hunter"
    lines.append(f"You are running one HUNT-OS lane turn as the {role} role.")
    lines.append("")
    contract = capsule.get("contract")
    if contract:
        lines.append("## CONTRACT")
        lines.append(str(contract))
        lines.append("")
    brief = capsule.get("brief")
    if brief:
        lines.append("## BRIEF")
        lines.append(str(brief))
        lines.append("")
    roe = capsule.get("roe")
    if roe:
        lines.append("## RULES OF ENGAGEMENT")
        lines.append(json.dumps(roe, sort_keys=True) if not isinstance(roe, str) else roe)
        lines.append("")
    lines.append("## LEDGER")
    lines.append(
        "Every observation, finding, lead and verification goes through the "
        "`hunt` CLI. Never claim PROVEN, EXPLOITABLE or admin takeover without "
        "a ledger row backing it. If you did not run a command, say so."
    )
    lines.append("")
    lines.append("## OUTPUT")
    lines.append(
        "Report what you actually did and observed. If you want to run a "
        "ledger command, emit exactly one line: "
        'TOOL_REQUEST {"command": ["hunt", "status"]} '
        "and stop; the result comes back to you."
    )
    return "\n".join(lines)


def _extract_tool_request(text: str) -> "list[str] | None":
    """Pull a TOOL_REQUEST line out of the model's output, if any.

    Deliberately narrow: the only accepted form is a single line beginning
    with TOOL_REQUEST followed by a JSON object carrying a string-list
    "command". Anything else is treated as prose, so a model that merely
    talks about tool requests never hijacks the turn.
    """
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("TOOL_REQUEST"):
            continue
        blob = line[len("TOOL_REQUEST"):].strip()
        try:
            obj = json.loads(blob)
        except ValueError:
            continue
        command = obj.get("command") if isinstance(obj, dict) else None
        if (isinstance(command, list) and command
                and all(isinstance(c, str) for c in command)):
            return list(command)
    return None


def _run_headless(prompt: str) -> str:
    argv = _hermes_argv() + ["--headless", "--print", prompt]
    if MODEL:
        argv += ["--model", MODEL]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        _fail(f"headless turn exceeded {TIMEOUT}s")
    except OSError as exc:
        _fail(f"could not run hermes: {exc}")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        _fail(f"hermes exited {proc.returncode}: {tail}")
    return proc.stdout or ""


def handle(message: dict) -> None:
    request_id = message["request_id"]
    method = message["method"]
    payload = message["payload"]
    if set(message) != {"protocol", "request_id", "type", "method", "payload"}:
        raise ValueError("closed envelope violation")
    if message["protocol"] != PROTOCOL or message["type"] != "request":
        raise ValueError("bad request envelope")

    if method == "doctor":
        # Resolve the executable HERE, not only on the first turn: a doctor
        # that reports healthy capabilities for a binary that does not exist
        # would let `hunt run start` preflight pass and then die on turn one.
        _hermes_argv()
        send(request_id, "response", method, {
            "capabilities": CAPABILITIES,
            "diagnostics": [
                f"{ADAPTER_ID} v{ADAPTER_VERSION} (real hermes CLI, headless)",
                f"executable: {BIN}",
                f"timeout: {TIMEOUT}s" + (f" model: {MODEL}" if MODEL else ""),
            ],
        })
        return

    if method == "start_session":
        send(request_id, "response", method, {
            "session_id": payload["session_id"], "started": True,
            "adapter_id": ADAPTER_ID, "adapter_version": ADAPTER_VERSION,
        })
        return

    if method == "run_turn":
        attempt_id = payload["attempt_id"]
        _pending[attempt_id] = request_id
        text = _run_headless(_capsule_prompt(payload))
        command = _extract_tool_request(text)
        if command is None:
            # No tool request: the turn is prose. It still goes through the
            # claim gate on HunterOS's side, so an unbacked claim dies there.
            event(request_id, {"type": "assistant_output", "text": text})
            event(request_id, {"type": "usage", "attempt_id": attempt_id,
                               "tokens": max(1, len(text) // 4)})
            event(request_id, {"type": "attempt_completed",
                               "attempt_id": attempt_id,
                               "status_hint": "completed"})
            send(request_id, "response", method, {"completed": True})
            _pending.pop(attempt_id, None)
            return
        event(request_id, {
            "type": "tool_request",
            "operation_id": f"op-{attempt_id}",
            "idempotency_key": f"idem-{attempt_id}",
            "command": command,
        })
        return

    if method == "tool_result":
        attempt_id = payload["attempt_id"]
        turn_id = _pending.pop(attempt_id, None)
        if turn_id is None:
            raise ValueError(f"tool_result for unknown attempt {attempt_id!r}")
        send(request_id, "response", method, {"accepted": True})
        result = payload.get("result") or {}
        observed = result.get("output", "") if isinstance(result, dict) else ""
        follow_up = (
            "The ledger answered:\n\n"
            f"{observed}\n\n"
            "Continue the lane turn. Report what you observed. Emit another "
            "TOOL_REQUEST line if you need one more command, otherwise give "
            "your final answer."
        )
        text = _run_headless(follow_up)
        event(turn_id, {"type": "assistant_output", "text": text})
        event(turn_id, {"type": "usage", "attempt_id": attempt_id,
                        "tokens": max(1, len(text) // 4)})
        event(turn_id, {"type": "attempt_completed", "attempt_id": attempt_id,
                        "status_hint": "completed"})
        send(turn_id, "response", "run_turn", {"completed": True})
        return

    if method == "get_attempt_status":
        aid = payload["attempt_id"]
        send(request_id, "response", method, {
            "attempt_id": aid,
            "status": "completed" if aid not in _pending else "running",
        })
        return

    if method == "cancel_turn":
        aid = payload["attempt_id"]
        _pending.pop(aid, None)
        send(request_id, "response", method, {"attempt_id": aid,
                                              "cancelled": True})
        return

    if method == "stop_session":
        _pending.clear()
        send(request_id, "response", method, {"session_id": payload["session_id"],
                                              "stopped": True})
        return

    raise ValueError(f"unknown method {method!r}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("envelope must be an object")
            handle(message)
        except Exception as exc:  # noqa: BLE001 — protocol failure is fatal
            _fail(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
