#!/usr/bin/env python3
"""Deterministic reference HUNT-ADAPTER/1 executable; no LLM is invoked."""
from __future__ import annotations

import json
import sys

PROTOCOL = "HUNT-ADAPTER/1"
active = {}


def send(request_id, kind, method, payload):
    print(json.dumps({
        "protocol": PROTOCOL, "request_id": request_id, "type": kind,
        "method": method, "payload": payload,
    }, sort_keys=True, separators=(",", ":")), flush=True)


def event(request_id, payload):
    send(request_id, "event", "run_turn", payload)


for line in sys.stdin:
    try:
        message = json.loads(line)
        request_id = message["request_id"]
        method = message["method"]
        payload = message["payload"]
        if message != {
            "protocol": PROTOCOL, "request_id": request_id, "type": "request",
            "method": method, "payload": payload,
        }:
            raise ValueError("closed envelope violation")
        if method == "doctor":
            capabilities = {
                "type": "capabilities", "protocol": PROTOCOL,
                "adapter_id": "reference-jsonl", "version": "1.0.0",
                "features": {
                    "skill_injection": True, "hunt_tool": True,
                    "post_output_hook": True, "headless_turn": True,
                    "subagents": True, "cancel": True, "heartbeats": True,
                    "model_routing": True,
                },
            }
            send(request_id, "response", method, {
                "capabilities": capabilities,
                "diagnostics": [
                    "reference-jsonl v1.0.0 (deterministic protocol simulator)",
                    "SIMULATED — no external agents invoked",
                ],
            })
        elif method == "start_session":
            send(request_id, "response", method, {
                "session_id": payload["session_id"], "started": True,
                "adapter_id": "reference-jsonl", "adapter_version": "1.0.0",
            })
        elif method == "run_turn":
            attempt_id = payload["attempt_id"]
            active[attempt_id] = request_id
            event(request_id, {"type": "heartbeat"})
            event(request_id, {
                "type": "tool_request", "operation_id": "op-" + attempt_id,
                "idempotency_key": "idem-" + attempt_id,
                "command": ["hunt", "status"],
            })
        elif method == "tool_result":
            attempt_id = payload["attempt_id"]
            turn_id = active.pop(attempt_id)
            send(request_id, "response", method, {"accepted": True})
            event(turn_id, {"type": "assistant_output", "text": "reference turn complete"})
            event(turn_id, {"type": "usage", "attempt_id": attempt_id, "tokens": 1})
            event(turn_id, {"type": "attempt_completed", "attempt_id": attempt_id,
                            "status_hint": "completed"})
            send(turn_id, "response", "run_turn", {"completed": True})
        elif method == "get_attempt_status":
            send(request_id, "response", method, {
                "attempt_id": payload["attempt_id"], "status": "completed",
            })
        elif method == "cancel_turn":
            active.pop(payload["attempt_id"], None)
            send(request_id, "response", method, {
                "attempt_id": payload["attempt_id"], "cancelled": True,
            })
        elif method == "stop_session":
            send(request_id, "response", method, {
                "session_id": payload["session_id"], "stopped": True,
            })
        else:
            raise ValueError("unknown method")
    except Exception as exc:
        print(f"reference adapter protocol error: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2)
