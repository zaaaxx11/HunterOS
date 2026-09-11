"""HuntAdapter protocol boundary and the deterministic mock adapter.

Implements blueprint section 6 of ``conductor.md``: the transport-agnostic
protocol between the conductor and an external harness, plus
:class:`MockAdapter` for blueprint C0 - a fully deterministic adapter with
NO network, NO LLM, NO threads, NO sleep. Every failure shape of blueprint
section 9 exists as a named :class:`Scenario`.

``MockAdapter.run_turn`` validates its own emitted events through
``parse_event`` (self-consistency) - except :meth:`Scenario.protocol_error`,
whose entire purpose is to emit a deliberately malformed raw payload so
consumers can prove their strict-parsing / circuit-breaker path.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Optional, Union

from .schemas import (
    FEATURE_KEYS,
    AssistantDelta,
    AssistantOutput,
    AttemptCompleted,
    Capabilities,
    Event,
    Heartbeat,
    SchemaError,
    StructuredError,
    ToolRequest,
    ToolResult,
    Usage,
    parse_event,
)


class HuntAdapter(ABC):
    """Protocol boundary between the conductor and a harness.

    Blueprint section 6 command set. Implementations live behind this
    interface only; the conductor never talks to a harness directly.
    """

    @abstractmethod
    def doctor(self) -> "tuple[Capabilities, list[str]]":
        """Capability discovery plus human-readable diagnostic lines."""

    @abstractmethod
    def start_session(self, config: dict) -> dict:
        """Open a hunt session; returns a session receipt dict."""

    @abstractmethod
    def run_turn(self, attempt_config: dict) -> Iterator[Event]:
        """Run one attempt; returns an iterator of event message objects.

        ``attempt_config`` must carry at least: attempt_id, session_id,
        lane, round.
        """

    def submit_tool_result(self, attempt_id: str, result: ToolResult) -> None:
        """Deliver a mediated result to a duplex adapter.

        The compatibility default is a no-op for older in-process test adapters;
        production transports must override it.
        """
        return None

    @abstractmethod
    def cancel_turn(self, attempt_id: str) -> dict:
        """Request cancellation of a running turn; returns an ack dict."""

    @abstractmethod
    def get_attempt_status(self, attempt_id: str) -> dict:
        """Return the adapter's known state for an attempt."""

    @abstractmethod
    def stop_session(self, session_id: str) -> dict:
        """Tear down a session; returns an ack dict."""


class Scenario:
    """Declarative script deciding the event sequence of one ``run_turn``.

    Construct via the static factory methods only; each factory maps to
    one blueprint section 9 incident/response row.
    """

    KINDS = (
        "ok",
        "timeout_before_dispatch",
        "timeout_after_readonly",
        "timeout_after_mutation",
        "auth_failure",
        "rate_limit",
        "crash",
        "protocol_error",
        "claim_veto_output",
        "usage_spike",
    )

    # Default tool requests for OK-shaped turns. Each entry is emitted as
    # a request ONLY (the mock never fabricates a ToolResult for them).
    OK_DEFAULT_COMMANDS = ["hunt", "status"]
    # A read-only hunt command (blueprint section 9: observed output is
    # preserved, no final answer may be inferred).
    READONLY_COMMAND = ["hunt", "status"]
    # A mutating hunt command (state may have changed -> uncertain).
    MUTATING_COMMAND = ["hunt", "finding", "add", "--finding-id", "F-1"]

    def __init__(
        self,
        kind: str,
        *,
        tool_commands: Optional[list] = None,
        text: Optional[str] = None,
        tokens: Optional[int] = None,
    ):
        if kind not in self.KINDS:
            raise SchemaError(
                f"unknown scenario kind {kind!r}; expected one of {list(self.KINDS)}"
            )
        self.kind = kind
        self.tool_commands = (
            list(tool_commands) if tool_commands is not None else None
        )
        self.text = text
        self.tokens = tokens

    # -- factories (blueprint section 9 incident table, one per row) ------

    @staticmethod
    def ok(tool_commands: Optional[list] = None) -> "Scenario":
        """Clean turn: heartbeat, tool request(s), output, usage, completed."""
        return Scenario("ok", tool_commands=tool_commands)

    @staticmethod
    def timeout_before_dispatch() -> "Scenario":
        """Hung before any dispatch: no work was sent, retry is safe."""
        return Scenario("timeout_before_dispatch")

    @staticmethod
    def timeout_after_readonly() -> "Scenario":
        """Read-only tool observed, then hung: output preserved, no answer."""
        return Scenario("timeout_after_readonly")

    @staticmethod
    def timeout_after_mutation() -> "Scenario":
        """Possibly-mutating tool observed, then hung: needs reconciliation."""
        return Scenario("timeout_after_mutation")

    @staticmethod
    def auth_failure() -> "Scenario":
        """Invalid/expired credential: no dispatch, operator remediation."""
        return Scenario("auth_failure")

    @staticmethod
    def rate_limit() -> "Scenario":
        """Provider rate limit: no dispatch, bounded retry budget applies."""
        return Scenario("rate_limit")

    @staticmethod
    def crash() -> "Scenario":
        """Harness process died mid-turn after partial output."""
        return Scenario("crash")

    @staticmethod
    def protocol_error() -> "Scenario":
        """Deliberately malformed raw payload (invalid adapter protocol).

        Yields a raw dict with an unknown ``type``; parsing it MUST fail.
        """
        return Scenario("protocol_error")

    @staticmethod
    def claim_veto_output(
        text: str = "PROVEN[F-1] totally proven",
    ) -> "Scenario":
        """OK-shaped turn whose final output carries an unbacked claim."""
        return Scenario("claim_veto_output", text=text)

    @staticmethod
    def usage_spike(tokens: int) -> "Scenario":
        """Turn reporting the given token count (budget-cap testing)."""
        if isinstance(tokens, bool) or not isinstance(tokens, int):
            raise SchemaError(
                f"usage_spike tokens must be int, got {type(tokens).__name__}"
            )
        return Scenario("usage_spike", tokens=tokens)


class MockAdapter(HuntAdapter):
    """Deterministic in-process HuntAdapter.

    - Constructor takes optional :class:`Capabilities` (default: fully
      capable mock) and a ``scenarios`` mapping keyed by attempt sequence
      number (0, 1, 2, ... in ``run_turn`` call order); missing keys fall
      back to ``Scenario.ok()``.
    - ``run_turn`` builds the whole event list eagerly (deterministic,
      re-runnable, no state leak between calls) and returns an iterator
      over it; every event object is round-tripped through
      ``parse_event`` before being handed out.
    - Tool request ids derive from the attempt id, so identical inputs
      yield byte-identical event streams.
    - ``get_attempt_status`` returns the recorded attempt config plus a
      deterministic status per scenario kind; ``cancel_turn`` /
      ``stop_session`` return acknowledgement dicts.
    """

    ADAPTER_ID = "mock-harness"
    ADAPTER_VERSION = "1.0.0"

    # Deterministic attempt status per scenario kind (blueprint section 9
    # response column, as an attempt status).
    ATTEMPT_STATUS_BY_SCENARIO = {
        "ok": "completed",
        "claim_veto_output": "completed",
        "usage_spike": "completed",
        "timeout_before_dispatch": "interrupted",
        "timeout_after_readonly": "interrupted",
        "timeout_after_mutation": "uncertain",
        "auth_failure": "interrupted",
        "rate_limit": "interrupted",
        "crash": "interrupted",
        "protocol_error": "interrupted",
    }

    REQUIRED_ATTEMPT_KEYS = ("attempt_id", "session_id", "lane", "round")

    def __init__(
        self,
        capabilities: Optional[Capabilities] = None,
        scenarios: Optional[dict] = None,
    ):
        if capabilities is None:
            capabilities = Capabilities(
                adapter_id=self.ADAPTER_ID,
                version=self.ADAPTER_VERSION,
                features={key: True for key in FEATURE_KEYS},
            )
        self.capabilities = capabilities
        self.scenarios = dict(scenarios) if scenarios else {}
        self._turn_count = 0
        self._session_counter = 0
        self._attempts: dict = {}
        self.submitted_results: list[tuple[str, ToolResult]] = []

    # -- HuntAdapter contract ---------------------------------------------

    def doctor(self) -> "tuple[Capabilities, list[str]]":
        diagnostics = [
            f"adapter {self.ADAPTER_ID} v{self.ADAPTER_VERSION} "
            "(deterministic scenario replay)",
            "network: none; llm: none; threads: none; sleep: none",
            f"scenarios registered for sequences: {sorted(self.scenarios)}",
        ]
        return self.capabilities, diagnostics

    def start_session(self, config: dict) -> dict:
        session_id = config.get("session_id") or f"S-MOCK-{self._session_counter}"
        self._session_counter += 1
        return {
            "type": "session_started",
            "session_id": session_id,
            "adapter_id": self.capabilities.adapter_id,
            "adapter_version": self.capabilities.version,
        }

    def run_turn(self, attempt_config: dict) -> "Iterator[Union[Event, dict]]":
        """Build and return this turn's event iterator (eager, deterministic).

        The only item that is not an ``Event`` is the deliberate raw
        protocol violation produced by ``Scenario.protocol_error``.
        """
        for key in self.REQUIRED_ATTEMPT_KEYS:
            if key not in attempt_config:
                raise ValueError(
                    f"attempt_config missing required key {key!r}"
                )
        sequence = self._turn_count
        self._turn_count += 1
        scenario = self.scenarios.get(sequence, Scenario.ok())
        attempt_id = attempt_config["attempt_id"]

        # Record the attempt BEFORE handing out events so get_attempt_status
        # answers deterministically even if the stream is abandoned/cancelled.
        self._attempts[attempt_id] = {
            **dict(attempt_config),
            "status": self.ATTEMPT_STATUS_BY_SCENARIO[scenario.kind],
            "scenario": scenario.kind,
        }

        items = self._script(scenario, attempt_id)
        checked = []
        for item in items:
            if isinstance(item, Event):
                parse_event(item.to_dict())  # self-consistency gate
            checked.append(item)
        return iter(checked)

    def submit_tool_result(self, attempt_id: str, result: ToolResult) -> None:
        if not isinstance(result, ToolResult):
            raise SchemaError("submitted tool result must be ToolResult")
        self.submitted_results.append((attempt_id, result))

    def cancel_turn(self, attempt_id: str) -> dict:
        return {
            "type": "cancel_ack",
            "attempt_id": attempt_id,
            "cancelled": True,
        }

    def get_attempt_status(self, attempt_id: str) -> dict:
        recorded = self._attempts.get(attempt_id)
        if recorded is None:
            return {"attempt_id": attempt_id, "status": "unknown"}
        return dict(recorded)

    def stop_session(self, session_id: str) -> dict:
        return {
            "type": "stop_ack",
            "session_id": session_id,
            "stopped": True,
        }

    # -- scenario scripting ------------------------------------------------

    def _tool_request(self, attempt_id: str, index: int, entry) -> ToolRequest:
        command = self._normalize_command(entry)
        return ToolRequest(
            operation_id=f"op-{attempt_id}-{index}",
            idempotency_key=f"idem-{attempt_id}-{index}",
            command=command,
        )

    @staticmethod
    def _normalize_command(entry) -> list:
        """A command entry is a str (single word) or a non-empty list[str]."""
        if isinstance(entry, str) and entry:
            return [entry]
        if (
            isinstance(entry, list)
            and entry
            and all(isinstance(c, str) for c in entry)
        ):
            return list(entry)
        raise SchemaError(
            f"tool command entry must be str or non-empty list[str], got {entry!r}"
        )

    def _script(self, scenario: Scenario, attempt_id: str) -> list:
        kind = scenario.kind
        if kind == "ok":
            items = [Heartbeat()]
            commands = (
                scenario.tool_commands
                if scenario.tool_commands is not None
                else list(Scenario.OK_DEFAULT_COMMANDS)
            )
            for i, entry in enumerate(commands):
                items.append(self._tool_request(attempt_id, i, entry))
            items.append(AssistantOutput(text="attempt ok"))
            items.append(Usage(attempt_id=attempt_id, tokens=100))
            items.append(
                AttemptCompleted(attempt_id=attempt_id, status_hint="completed")
            )
            return items

        if kind == "claim_veto_output":
            items = [Heartbeat()]
            for i, entry in enumerate(Scenario.OK_DEFAULT_COMMANDS):
                items.append(self._tool_request(attempt_id, i, entry))
            items.append(AssistantOutput(text=scenario.text))
            items.append(Usage(attempt_id=attempt_id, tokens=100))
            items.append(
                AttemptCompleted(attempt_id=attempt_id, status_hint="completed")
            )
            return items

        if kind == "usage_spike":
            return [
                Heartbeat(),
                Usage(attempt_id=attempt_id, tokens=scenario.tokens),
                AttemptCompleted(attempt_id=attempt_id, status_hint="completed"),
            ]

        if kind == "timeout_before_dispatch":
            return [
                StructuredError(
                    error_class="timeout",
                    detail="hung before dispatch",
                    attempt_id=attempt_id,
                )
            ]

        if kind == "timeout_after_readonly":
            request = self._tool_request(attempt_id, 0, Scenario.READONLY_COMMAND)
            return [
                request,
                ToolResult(
                    operation_id=request.operation_id,
                    output="hunt status ok: ledger reachable (observed before hang)",
                    ok=True,
                ),
                StructuredError(
                    error_class="timeout",
                    detail="hung after read-only tool observation; "
                    "observed output preserved, no final answer inferred",
                    attempt_id=attempt_id,
                ),
            ]

        if kind == "timeout_after_mutation":
            request = self._tool_request(attempt_id, 0, Scenario.MUTATING_COMMAND)
            return [
                request,
                ToolResult(
                    operation_id=request.operation_id,
                    output="finding F-1 write accepted (may or may not have landed)",
                    ok=True,
                ),
                StructuredError(
                    error_class="timeout",
                    detail="hung after possibly-mutating tool; "
                    "target state requires reconciliation",
                    attempt_id=attempt_id,
                ),
            ]

        if kind == "auth_failure":
            return [
                StructuredError(
                    error_class="auth",
                    detail="invalid or expired API credential; "
                    "operator/provider remediation required",
                    attempt_id=attempt_id,
                )
            ]

        if kind == "rate_limit":
            return [
                StructuredError(
                    error_class="rate_limit",
                    detail="provider rate limit hit; bounded retry budget applies",
                    attempt_id=attempt_id,
                )
            ]

        if kind == "crash":
            return [
                AssistantDelta(text="partial analysis before the process died"),
                StructuredError(
                    error_class="crash",
                    detail="harness process died mid-turn",
                    attempt_id=attempt_id,
                ),
            ]

        if kind == "protocol_error":
            # Deliberate contract violation: raw dict, unknown type, NOT an
            # Event, NOT parseable. Consumers must treat this as an invalid
            # adapter protocol (circuit breaker path).
            return [{"type": "hyperturn_delta", "payload": "not a real event"}]

        raise SchemaError(f"unknown scenario kind: {kind!r}")
