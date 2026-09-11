"""HUNT-OS conductor - protocol layer for the HuntAdapter boundary.

Slice A of blueprint C0+C1 (conductor.md sections 5, 6, 9): wire schemas,
session/attempt state machines, and the deterministic mock adapter. Slice C1
adds the orchestrator (sections 8, 9, 12): the managed-loop Conductor and the
control-room summary.
"""
from .adapter import HuntAdapter, MockAdapter, Scenario
from .schemas import (
    ADAPTER_PROTOCOL,
    ERROR_CLASSES,
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
    require_generic_four_lane_capabilities,
)
from .state import (
    ATTEMPT_TRANSITIONS,
    SESSION_TRANSITIONS,
    AttemptStatus,
    IllegalTransition,
    SessionStatus,
    assert_attempt_transition,
    assert_session_transition,
    is_research_result,
)
from .summary import compute_next_action, control_room_summary
from .conductor import Conductor, is_mutating_command
from .capsule import build_lane_capsule
from .jsonl_adapter import JsonlAdapter
from .registry import (
    DEFAULT_REGISTRY_PATH, add_adapter, build_registered_adapter, get_adapter,
    list_adapters, remove_adapter,
)

__all__ = [
    # schemas
    "ADAPTER_PROTOCOL",
    "ERROR_CLASSES",
    "FEATURE_KEYS",
    "Capabilities",
    "Event",
    "Heartbeat",
    "AssistantDelta",
    "ToolRequest",
    "ToolResult",
    "AssistantOutput",
    "Usage",
    "AttemptCompleted",
    "StructuredError",
    "SchemaError",
    "parse_event",
    "require_generic_four_lane_capabilities",
    # state
    "SessionStatus",
    "AttemptStatus",
    "SESSION_TRANSITIONS",
    "ATTEMPT_TRANSITIONS",
    "IllegalTransition",
    "assert_session_transition",
    "assert_attempt_transition",
    "is_research_result",
    # adapter
    "HuntAdapter",
    "MockAdapter",
    "Scenario",
    # orchestrator (C1)
    "Conductor",
    "is_mutating_command",
    "control_room_summary",
    "compute_next_action",
]
