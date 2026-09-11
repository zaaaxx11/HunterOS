"""Conductor state machines - session and attempt lifecycles.

Implements blueprint section 5 of ``conductor.md``: the session status
graph, the lane/attempt status graph, and the law that separates research
results from infrastructure failures.

Law of this module:

- Only edges present in the graphs are legal; anything else raises
  :class:`IllegalTransition`.
- A same-value transition is a no-op, not an error.
- ``interrupted`` / ``uncertain`` / ``cancelled`` are NEVER research
  results (blueprint section 5: "interrupted dan uncertain bukan hasil
  riset dan tidak boleh dihitung sebagai lane kosong atau wave kosong").
  They may never count as an empty lane or an empty wave.

Statuses accept both the enum members and their plain string values.
"""
from __future__ import annotations

from enum import Enum


class IllegalTransition(Exception):
    """A state change not permitted by the lifecycle graph."""


class SessionStatus(str, Enum):
    """Session lifecycle (blueprint section 5 graph)."""

    PREFLIGHT = "preflight"
    RUNNING = "running"
    DEGRADED = "degraded"
    PAUSED = "paused"
    COMPLETED = "completed"
    RECOVERY_REQUIRED = "recovery_required"
    ABORTED = "aborted"


class AttemptStatus(str, Enum):
    """Lane/attempt lifecycle (blueprint section 5 graph)."""

    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    RESEARCH_BLOCKED = "research_blocked"
    INTERRUPTED = "interrupted"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"


# EXACT blueprint section 5 session graph. Terminal states carry no edges;
# recovery from recovery_required is only via an explicit path (aborted or
# an operator-driven fresh session), never automatic.
SESSION_TRANSITIONS: dict = {
    "preflight": frozenset({"running"}),
    "running": frozenset(
        {"degraded", "paused", "completed", "recovery_required", "aborted"}
    ),
    "degraded": frozenset({"running", "recovery_required", "aborted", "paused"}),
    "paused": frozenset({"running", "aborted"}),
    "recovery_required": frozenset({"aborted"}),
    "completed": frozenset(),
    "aborted": frozenset(),
}

# EXACT blueprint section 5 attempt graph. The interrupted->running and
# uncertain->running edges model a NEW bounded attempt taking over (retry /
# post-reconcile); the orchestrator enforces the reconcile precondition,
# the state layer only permits the edge.
ATTEMPT_TRANSITIONS: dict = {
    "ready": frozenset({"running", "cancelled"}),
    "running": frozenset(
        {"completed", "research_blocked", "interrupted", "uncertain", "cancelled"}
    ),
    "completed": frozenset(),
    "research_blocked": frozenset(),
    "interrupted": frozenset({"running"}),
    "uncertain": frozenset({"running"}),
    "cancelled": frozenset(),
}

# The only attempt statuses that count as research outcomes.
_RESEARCH_RESULTS = frozenset({"completed", "research_blocked"})

# Attempt statuses that END an attempt (the blueprint §5 graph gives them no
# outgoing edges). interrupted/uncertain are deliberately absent: they are
# pauses with an error_class, not results.
TERMINAL_ATTEMPT_STATUSES = ("completed", "research_blocked", "cancelled")

# Attempt statuses on which an error_class may be recorded (blueprint §12.8:
# provider failures stay distinguishable from research outcomes). cancelled
# is both terminal and a failure — it ends the attempt AND carries a class.
FAILURE_ATTEMPT_STATUSES = ("interrupted", "uncertain", "cancelled")


def _session_key(status) -> str:
    """Coerce SessionStatus member or string to its canonical value."""
    if isinstance(status, SessionStatus):
        return status.value
    if isinstance(status, str) and status in SESSION_TRANSITIONS:
        return status
    raise IllegalTransition(f"unknown session status: {status!r}")


def _attempt_key(status) -> str:
    """Coerce AttemptStatus member or string to its canonical value."""
    if isinstance(status, AttemptStatus):
        return status.value
    if isinstance(status, str) and status in ATTEMPT_TRANSITIONS:
        return status
    raise IllegalTransition(f"unknown attempt status: {status!r}")


def assert_session_transition(old, new) -> None:
    """Raise :class:`IllegalTransition` unless old->new is a legal edge.

    Same-value transitions are a no-op (idempotent re-assert).
    """
    old_key = _session_key(old)
    new_key = _session_key(new)
    if old_key == new_key:
        return
    if new_key not in SESSION_TRANSITIONS[old_key]:
        raise IllegalTransition(
            f"illegal session transition {old_key!r} -> {new_key!r}"
        )


def assert_attempt_transition(old, new) -> None:
    """Raise :class:`IllegalTransition` unless old->new is a legal edge.

    Same-value transitions are a no-op (idempotent re-assert).
    """
    old_key = _attempt_key(old)
    new_key = _attempt_key(new)
    if old_key == new_key:
        return
    if new_key not in ATTEMPT_TRANSITIONS[old_key]:
        raise IllegalTransition(
            f"illegal attempt transition {old_key!r} -> {new_key!r}"
        )


def is_research_result(status: AttemptStatus) -> bool:
    """True only for completed | research_blocked.

    This encodes the law: interrupted/uncertain/cancelled (and unknown
    values, fail-closed) are never research results and never count as
    empty lanes/waves.
    """
    try:
        key = _attempt_key(status)
    except IllegalTransition:
        return False
    return key in _RESEARCH_RESULTS


def is_terminal_attempt(status: AttemptStatus) -> bool:
    """True only for completed | research_blocked | cancelled.

    The statuses that END an attempt (no outgoing edges in the blueprint §5
    graph) — the ones on which ended_at is stamped. interrupted/uncertain
    are pauses with an error_class, not results. Unknown values fail
    closed (False).
    """
    try:
        key = _attempt_key(status)
    except IllegalTransition:
        return False
    return key in TERMINAL_ATTEMPT_STATUSES


def is_failure_attempt(status: AttemptStatus) -> bool:
    """True only for interrupted | uncertain | cancelled.

    The statuses on which an error_class may be recorded (blueprint §12.8:
    provider failures stay distinguishable from research outcomes — a clean
    path can never carry a failure label). cancelled is both a failure and
    terminal. Unknown values fail closed (False).
    """
    try:
        key = _attempt_key(status)
    except IllegalTransition:
        return False
    return key in FAILURE_ATTEMPT_STATUSES
