"""Conductor protocol schemas - wire messages on the HuntAdapter boundary.

Implements the event and capability contracts of blueprint sections 6 and 9
of ``conductor.md``: canonical message dataclasses for everything that
crosses the adapter boundary, strict closed-schema parsing, and the
capability discovery record.

Law of this module:

- Schemas are CLOSED. ``from_dict``/``parse_event`` reject unknown event
  types, missing required fields, unexpected fields, and wrongly typed
  values with :class:`SchemaError`.
- Every event class roundtrips exactly: ``X.from_dict(x.to_dict()) == x``.
- ``StructuredError.error_class`` is a closed vocabulary; infrastructure
  failure is never research evidence, so the classes are fixed here.

Stdlib only (repo law). No network, no threads, no clock dependence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Optional


class SchemaError(ValueError):
    """A payload violates the conductor wire schema (closed + strict).

    It remains a distinct protocol exception while crossing the CLI's normal
    ``ValueError`` boundary as a fail-closed ``BLOCKED:`` exit 2.
    """


# Closed vocabulary for StructuredError.error_class (blueprint section 9:
# infrastructure failure is never research evidence).
ERROR_CLASSES = (
    "auth",
    "rate_limit",
    "crash",
    "protocol",
    "disk_full",
    "timeout",
    "cancelled",
)

# The exactly-8 capability keys of the blueprint section 6 discovery record.
ADAPTER_PROTOCOL = "HUNT-ADAPTER/1"

FEATURE_KEYS = (
    "skill_injection",
    "hunt_tool",
    "post_output_hook",
    "headless_turn",
    "subagents",
    "cancel",
    "heartbeats",
    "model_routing",
)


# --- validation helpers (raise SchemaError, so from_dict stays strict too) ---

def _check_str(value, name: str) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"{name} must be str, got {type(value).__name__}")
    return value


def _check_bool(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaError(f"{name} must be bool, got {type(value).__name__}")
    return value


def _check_int(value, name: str) -> int:
    # bool is a subclass of int; a boolean token count is a protocol bug.
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{name} must be int, got {type(value).__name__}")
    return value


# --- capabilities (blueprint section 6: capability discovery) ---

@dataclass
class Capabilities:
    """Adapter capability discovery record.

    ``features`` is normalized to EXACTLY the 8 blueprint keys: missing
    keys default to False, non-bool values and unknown keys are schema
    errors. An adapter may only claim what it can prove; managed mode
    requires ``meets_managed_requirements()``.
    """

    adapter_id: str
    version: str
    features: dict = field(default_factory=dict)
    protocol: str = ADAPTER_PROTOCOL

    def __post_init__(self):
        if not isinstance(self.adapter_id, str) or not self.adapter_id:
            raise SchemaError("adapter_id must be a non-empty str")
        if not isinstance(self.version, str) or not self.version:
            raise SchemaError("version must be a non-empty str")
        if self.protocol != ADAPTER_PROTOCOL:
            raise SchemaError(
                f"unsupported adapter protocol {self.protocol!r}; expected {ADAPTER_PROTOCOL!r}"
            )
        if not isinstance(self.features, dict):
            raise SchemaError(
                f"features must be a dict, got {type(self.features).__name__}"
            )
        unknown = sorted(set(self.features) - set(FEATURE_KEYS))
        if unknown:
            raise SchemaError(f"unknown feature keys: {unknown}")
        normalized = {}
        for key in FEATURE_KEYS:
            value = self.features.get(key, False)
            if not isinstance(value, bool):
                raise SchemaError(
                    f"feature {key!r} must be bool, got {type(value).__name__}"
                )
            normalized[key] = value
        self.features = normalized

    def meets_managed_requirements(self) -> bool:
        """Managed run (blueprint section 3) needs exactly these three."""
        return bool(
            self.features["hunt_tool"]
            and self.features["post_output_hook"]
            and self.features["headless_turn"]
        )

    def to_dict(self) -> dict:
        return {
            "type": "capabilities",
            "protocol": self.protocol,
            "adapter_id": self.adapter_id,
            "version": self.version,
            "features": dict(self.features),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Capabilities":
        if not isinstance(raw, dict):
            raise SchemaError(
                f"capabilities payload must be a dict, got {type(raw).__name__}"
            )
        if "adapter_id" not in raw:
            raise SchemaError("capabilities: missing adapter_id")
        if "version" not in raw:
            raise SchemaError("capabilities: missing version")
        raw_type = raw.get("type")
        if raw_type is not None and raw_type != "capabilities":
            raise SchemaError(
                f"capabilities: expected type 'capabilities', got {raw_type!r}"
            )
        allowed = {"type", "protocol", "adapter_id", "version", "features"}
        extra = sorted(set(raw) - allowed)
        if extra:
            raise SchemaError(f"capabilities: unexpected fields {extra}")
        return cls(
            adapter_id=raw["adapter_id"],
            version=raw["version"],
            features=raw.get("features", {}),
            protocol=raw.get("protocol", ADAPTER_PROTOCOL),
        )


def require_generic_four_lane_capabilities(capabilities: Capabilities) -> None:
    """Fail closed unless an adapter can run the generic four-lane contract."""
    if not capabilities.meets_managed_requirements() or not capabilities.features["subagents"]:
        raise SchemaError(
            "generic four-lane managed mode requires hunt_tool, post_output_hook, "
            "headless_turn, and subagents"
        )


# --- events (blueprint section 6: events from adapter) ---

class Event:
    """Base for adapter event messages.

    Subclasses declare ``type`` (the wire discriminator), ``_REQUIRED``
    and ``_OPTIONAL`` field-name tuples; ``to_dict``/``from_dict`` are
    generic and strict over those declarations.
    """

    type: ClassVar[str]
    _REQUIRED: ClassVar[tuple[str, ...]] = ()
    _OPTIONAL: ClassVar[tuple[str, ...]] = ()

    def to_dict(self) -> dict:
        out = {"type": self.type}
        for name in self._REQUIRED + self._OPTIONAL:
            out[name] = getattr(self, name)
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> "Event":
        if not isinstance(raw, dict):
            raise SchemaError(
                f"{cls.type}: payload must be a dict, got {type(raw).__name__}"
            )
        if raw.get("type") != cls.type:
            raise SchemaError(
                f"expected type {cls.type!r}, got {raw.get('type')!r}"
            )
        allowed = {"type", *cls._REQUIRED, *cls._OPTIONAL}
        missing = [name for name in cls._REQUIRED if name not in raw]
        if missing:
            raise SchemaError(f"{cls.type}: missing required fields {missing}")
        extra = sorted(set(raw) - allowed)
        if extra:
            raise SchemaError(f"{cls.type}: unexpected fields {extra}")
        kwargs = {name: raw[name] for name in cls._REQUIRED}
        kwargs.update({name: raw[name] for name in cls._OPTIONAL if name in raw})
        return cls(**kwargs)


@dataclass
class Heartbeat(Event):
    """Adapter liveness marker (managed runs rely on heartbeats)."""

    type: ClassVar[str] = "heartbeat"


@dataclass
class AssistantDelta(Event):
    """Streaming partial assistant text; never evidence on its own."""

    type: ClassVar[str] = "assistant_delta"
    _REQUIRED: ClassVar[tuple[str, ...]] = ("text",)

    text: str

    def __post_init__(self):
        _check_str(self.text, "text")


@dataclass
class ToolRequest(Event):
    """Adapter asks to run a command (e.g. the ``hunt`` tool) locally.

    ``operation_id`` + ``idempotency_key`` exist so a timeout never
    repeats an action that may already have run (blueprint section 9).
    """

    type: ClassVar[str] = "tool_request"
    _REQUIRED: ClassVar[tuple[str, ...]] = (
        "operation_id",
        "idempotency_key",
        "command",
    )

    operation_id: str
    idempotency_key: str
    command: list

    def __post_init__(self):
        _check_str(self.operation_id, "operation_id")
        _check_str(self.idempotency_key, "idempotency_key")
        if (
            not isinstance(self.command, list)
            or not self.command
            or not all(isinstance(c, str) for c in self.command)
        ):
            raise SchemaError("command must be a non-empty list of str")


@dataclass
class ToolResult(Event):
    """Observed local output of a dispatched tool request."""

    type: ClassVar[str] = "tool_result"
    _REQUIRED: ClassVar[tuple[str, ...]] = ("operation_id", "output", "ok")

    operation_id: str
    output: str
    ok: bool

    def __post_init__(self):
        _check_str(self.operation_id, "operation_id")
        _check_str(self.output, "output")
        _check_bool(self.ok, "ok")


@dataclass
class AssistantOutput(Event):
    """Final assistant output of a turn; still subject to the claim gate."""

    type: ClassVar[str] = "assistant_output"
    _REQUIRED: ClassVar[tuple[str, ...]] = ("text",)

    text: str

    def __post_init__(self):
        _check_str(self.text, "text")


@dataclass
class Usage(Event):
    """Token accounting for one attempt (budget caps read this)."""

    type: ClassVar[str] = "usage"
    _REQUIRED: ClassVar[tuple[str, ...]] = ("attempt_id", "tokens")

    attempt_id: str
    tokens: int

    def __post_init__(self):
        _check_str(self.attempt_id, "attempt_id")
        _check_int(self.tokens, "tokens")


@dataclass
class AttemptCompleted(Event):
    """Adapter's hint that a turn ended; the conductor owns real status."""

    type: ClassVar[str] = "attempt_completed"
    _REQUIRED: ClassVar[tuple[str, ...]] = ("attempt_id", "status_hint")

    attempt_id: str
    status_hint: str

    def __post_init__(self):
        _check_str(self.attempt_id, "attempt_id")
        _check_str(self.status_hint, "status_hint")


@dataclass
class StructuredError(Event):
    """Classified infrastructure failure; never a research result."""

    type: ClassVar[str] = "structured_error"
    _REQUIRED: ClassVar[tuple[str, ...]] = ("error_class", "detail")
    _OPTIONAL: ClassVar[tuple[str, ...]] = ("attempt_id",)

    error_class: str
    detail: str
    attempt_id: Optional[str] = None

    def __post_init__(self):
        _check_str(self.error_class, "error_class")
        if self.error_class not in ERROR_CLASSES:
            raise SchemaError(
                f"error_class {self.error_class!r} is outside the closed "
                f"vocabulary {list(ERROR_CLASSES)}"
            )
        _check_str(self.detail, "detail")
        if self.attempt_id is not None:
            _check_str(self.attempt_id, "attempt_id")


# Strict dispatch table: wire type string -> event class.
EVENT_TYPES: dict = {
    Heartbeat.type: Heartbeat,
    AssistantDelta.type: AssistantDelta,
    ToolRequest.type: ToolRequest,
    ToolResult.type: ToolResult,
    AssistantOutput.type: AssistantOutput,
    Usage.type: Usage,
    AttemptCompleted.type: AttemptCompleted,
    StructuredError.type: StructuredError,
}


def parse_event(raw: dict) -> Event:
    """Strictly parse one raw event payload into its message dataclass.

    Raises :class:`SchemaError` on non-dict payloads, unknown/missing
    ``type``, missing required fields, unexpected fields, or wrongly
    typed values.
    """
    if not isinstance(raw, dict):
        raise SchemaError(
            f"event payload must be a dict, got {type(raw).__name__}"
        )
    kind = raw.get("type")
    if not isinstance(kind, str) or kind not in EVENT_TYPES:
        raise SchemaError(f"unknown event type: {kind!r}")
    return EVENT_TYPES[kind].from_dict(raw)
