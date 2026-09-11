"""Long-lived, strict JSON-lines transport for HUNT-ADAPTER/1."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from contextlib import suppress
from pathlib import Path
from typing import Iterator

from .adapter import HuntAdapter
from .schemas import (
    ADAPTER_PROTOCOL, AttemptCompleted, Capabilities, Event, SchemaError,
    StructuredError, ToolResult, parse_event,
)

MAX_LINE_BYTES = 1024 * 1024
STDERR_CAP = 16 * 1024
METHODS = {
    "doctor", "start_session", "run_turn", "tool_result", "cancel_turn",
    "get_attempt_status", "stop_session",
}


class JsonlAdapter(HuntAdapter):
    """A single-process adapter; provider credentials are inherited, never stored."""

    def __init__(self, executable: str, args: list[str] | None = None,
                 *, timeout: float = 30.0):
        path = Path(executable)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("BLOCKED: adapter executable must be an absolute existing file")
        if args is not None and (not isinstance(args, list) or
                                 not all(isinstance(arg, str) for arg in args)):
            raise ValueError("BLOCKED: adapter args must be a list of strings")
        if timeout <= 0:
            raise ValueError("BLOCKED: adapter timeout must be positive")
        self.argv = [str(path), *(args or [])]
        self.timeout = float(timeout)
        self._process: subprocess.Popen | None = None
        self._stdout_queue: queue.Queue = queue.Queue()
        self._stderr = bytearray()
        self._request_counter = 0
        self._seen_responses: set[str] = set()
        self._active_turn: tuple[str, str] | None = None
        self._write_lock = threading.Lock()

    def _ensure_process(self) -> subprocess.Popen:
        if self._process is not None:
            if self._process.poll() is not None:
                raise SchemaError(
                    f"adapter process exited {self._process.returncode}: {self.stderr_diagnostics}"
                )
            return self._process
        try:
            self._process = subprocess.Popen(
                self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, shell=False, bufsize=0,
            )
        except OSError as exc:
            raise SchemaError(f"adapter process failed to start: {exc}") from exc
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        return self._process

    def _read_stdout(self) -> None:
        process = self._process
        assert process is not None and process.stdout is not None
        try:
            while True:
                raw = process.stdout.readline(MAX_LINE_BYTES + 2)
                if not raw:
                    self._stdout_queue.put(("eof", None))
                    return
                if len(raw) > MAX_LINE_BYTES:
                    self._stdout_queue.put(("error", "adapter protocol line exceeds 1 MiB"))
                    return
                if not raw.endswith(b"\n"):
                    self._stdout_queue.put(("error", "adapter protocol line is not newline terminated"))
                    return
                try:
                    text = raw[:-1].decode("utf-8", errors="strict")
                    value = json.loads(text)
                except (UnicodeError, json.JSONDecodeError) as exc:
                    self._stdout_queue.put(("error", f"malformed UTF-8 JSON line: {exc}"))
                    return
                self._stdout_queue.put(("message", value))
        except Exception as exc:
            self._stdout_queue.put(("error", f"stdout reader failed: {exc}"))

    def _read_stderr(self) -> None:
        process = self._process
        assert process is not None and process.stderr is not None
        while len(self._stderr) < STDERR_CAP:
            chunk = process.stderr.read(min(4096, STDERR_CAP - len(self._stderr)))
            if not chunk:
                return
            self._stderr.extend(chunk)

    @property
    def stderr_diagnostics(self) -> str:
        return bytes(self._stderr).decode("utf-8", errors="replace")

    def _next_request_id(self) -> str:
        self._request_counter += 1
        return f"r-{self._request_counter}"

    def _send(self, method: str, payload: dict) -> str:
        if method not in METHODS or not isinstance(payload, dict):
            raise SchemaError("invalid adapter request method or payload")
        request_id = self._next_request_id()
        envelope = {
            "protocol": ADAPTER_PROTOCOL, "request_id": request_id,
            "type": "request", "method": method, "payload": payload,
        }
        data = (json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        if len(data) > MAX_LINE_BYTES:
            raise SchemaError("adapter request line exceeds 1 MiB")
        process = self._ensure_process()
        try:
            assert process.stdin is not None
            with self._write_lock:
                process.stdin.write(data)
                process.stdin.flush()
        except (OSError, BrokenPipeError) as exc:
            self.close()
            raise SchemaError(f"adapter request write failed: {exc}") from exc
        return request_id

    def _get_message(self) -> dict:
        try:
            kind, value = self._stdout_queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            self.close()
            raise SchemaError("adapter response timeout") from exc
        if kind == "error":
            self.close()
            raise SchemaError(str(value))
        if kind == "eof":
            process = self._process
            code = process.poll() if process is not None else None
            self.close()
            raise SchemaError(f"adapter process ended unexpectedly (exit {code})")
        return self._validate_envelope(value)

    @staticmethod
    def _validate_envelope(raw) -> dict:
        if not isinstance(raw, dict):
            raise SchemaError("adapter envelope must be an object")
        expected = {"protocol", "request_id", "type", "method", "payload"}
        if set(raw) != expected:
            raise SchemaError(f"adapter envelope fields must be exactly {sorted(expected)}")
        if raw["protocol"] != ADAPTER_PROTOCOL:
            raise SchemaError("adapter protocol mismatch")
        if not isinstance(raw["request_id"], str) or not raw["request_id"]:
            raise SchemaError("adapter request_id must be a non-empty string")
        if raw["type"] not in ("response", "event"):
            raise SchemaError("adapter output type must be response or event")
        if raw["method"] not in METHODS:
            raise SchemaError("adapter output method is unknown")
        if not isinstance(raw["payload"], dict):
            raise SchemaError("adapter output payload must be an object")
        return raw

    def _response(self, request_id: str, method: str) -> dict:
        message = self._get_message()
        if message["type"] != "response" or message["request_id"] != request_id or message["method"] != method:
            self.close()
            raise SchemaError("adapter response identity mismatch")
        if request_id in self._seen_responses:
            self.close()
            raise SchemaError("duplicate adapter response")
        self._seen_responses.add(request_id)
        return message["payload"]

    def _call(self, method: str, payload: dict) -> dict:
        request_id = self._send(method, payload)
        return self._response(request_id, method)

    def doctor(self) -> tuple[Capabilities, list[str]]:
        payload = self._call("doctor", {})
        if set(payload) != {"capabilities", "diagnostics"} or not isinstance(payload["diagnostics"], list) or not all(isinstance(x, str) for x in payload["diagnostics"]):
            raise SchemaError("doctor response must contain capabilities and diagnostics")
        return Capabilities.from_dict(payload["capabilities"]), list(payload["diagnostics"])

    def start_session(self, config: dict) -> dict:
        return self._call("start_session", config)

    def run_turn(self, attempt_config: dict) -> Iterator[Event]:
        attempt_id = attempt_config.get("attempt_id")
        session_id = attempt_config.get("session_id")
        if not isinstance(attempt_id, str) or not isinstance(session_id, str):
            raise SchemaError("run_turn requires string attempt_id and session_id")
        if self._active_turn is not None:
            raise SchemaError("only one serial turn may be active")
        request_id = self._send("run_turn", attempt_config)
        self._active_turn = (request_id, attempt_id)
        try:
            terminal = False
            while True:
                message = self._get_message()
                if message["request_id"] != request_id or message["method"] != "run_turn":
                    raise SchemaError("turn event identity mismatch")
                if message["type"] == "response":
                    if request_id in self._seen_responses:
                        raise SchemaError("duplicate adapter response")
                    self._seen_responses.add(request_id)
                    if not terminal:
                        raise SchemaError("run_turn response arrived before terminal event")
                    return
                event = parse_event(message["payload"])
                event_attempt = getattr(event, "attempt_id", None)
                if event_attempt is not None and event_attempt != attempt_id:
                    raise SchemaError("turn event attempt identity mismatch")
                if isinstance(event, (AttemptCompleted, StructuredError)):
                    terminal = True
                yield event
                if terminal:
                    continue
        finally:
            self._active_turn = None

    def submit_tool_result(self, attempt_id: str, result: ToolResult) -> None:
        if self._active_turn is None or self._active_turn[1] != attempt_id:
            raise SchemaError("tool_result does not match the active attempt")
        payload = {"attempt_id": attempt_id, "result": result.to_dict()}
        response = self._call("tool_result", payload)
        if response.get("accepted") is not True:
            raise SchemaError("adapter refused mediated tool result")

    def cancel_turn(self, attempt_id: str) -> dict:
        return self._call("cancel_turn", {"attempt_id": attempt_id})

    def get_attempt_status(self, attempt_id: str) -> dict:
        return self._call("get_attempt_status", {"attempt_id": attempt_id})

    def stop_session(self, session_id: str) -> dict:
        return self._call("stop_session", {"session_id": session_id})

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        with suppress(Exception):
            if process.stdin is not None:
                process.stdin.close()
        if process.poll() is None:
            with suppress(Exception):
                process.terminate()
            try:
                process.wait(timeout=1)
            except Exception:
                with suppress(Exception):
                    process.kill()
        for stream in (process.stdout, process.stderr):
            with suppress(Exception):
                if stream is not None:
                    stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def __del__(self):
        with suppress(Exception):
            self.close()
