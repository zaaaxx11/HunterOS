"""Control-room summary (blueprint section 8 of ``conductor.md``).

The terminal surface of the conductor is a bounded operational view, not an
unbounded transcript: one line per attempt, grouped by round, with a single
NEXT line that names the operator's next action. Raw assistant text and
verbose tool output are never part of it — the ledger decides what is shown.

Stdlib only. This module reads the kernel's conductor API and never writes.
"""
from __future__ import annotations

import re
import sys

from huntos.cli.terminal import pad_visible, style, supports_color, terminal_width, truncate_visible
from huntos.core import db

# Lane -> display label (the four blueprint section 5 roles).
LANE_LABELS = {
    "architect": "Architect",
    "red_teamer": "RedTeam",
    "fuzz_engineer": "Fuzz",
    "chainer": "Chainer",
}

# Attempt statuses that still need work (the orchestrator's pending set).
PENDING_STATUSES = ("ready", "running", "interrupted", "cancelled")


def compute_next_action(session: dict, attempts: list, incidents: list) -> str:
    """One deterministic sentence: what should happen to this session next.

    Priority order mirrors the orchestrator laws: a frozen session outranks a
    paused one, an uncertain lane outranks pending dispatches, pending work
    outranks a clean finish.
    """
    status = session["status"]
    if status == "recovery_required":
        return "dispatch frozen — doctor() the adapter, then recover or abort"
    if status == "paused":
        return "provider failure — remediate, then resume"
    if status == "aborted":
        return "none — session aborted"
    if status == "completed":
        return "none — session completed"
    uncertain = [a for a in attempts if a["status"] == "uncertain"]
    if uncertain:
        return f"reconcile {uncertain[0]['id']}, then retry"
    pending = [a for a in attempts if a["status"] in PENDING_STATUSES]
    if pending:
        return f"resume to re-dispatch pending attempts (first: {pending[0]['id']})"
    if attempts:
        return "all lanes complete for the recorded rounds"
    return "resume to open the first round"


def control_room_summary(conn, session_id: str) -> str:
    """Render the section-8 control-room view of one session as text.

    Raises ``ValueError("BLOCKED: ...")`` when the session does not exist.
    """
    session = db.get_conductor_session(conn, session_id)
    if session is None:
        raise ValueError(f"BLOCKED: conductor session '{session_id}' does not exist")
    attempts = db.list_conductor_attempts(conn, session["id"])
    incidents = db.list_conductor_incidents(conn, session["id"])

    rounds = session["rounds"] if session["rounds"] is not None else "?"
    lines = [
        f"SESSION {session['id']} / {session['status']} / target #{session['target_id']} / "
        f"rounds {rounds} / adapter {session['adapter_id'] or '?'} "
        f"v{session['adapter_version'] or '?'}"
    ]
    unresolved = sum(1 for i in incidents if i["resolved_at"] is None)
    lines.append(f"  incidents: {len(incidents)} total, {unresolved} unresolved")

    by_round: dict = {}
    for attempt in attempts:
        by_round.setdefault(attempt["round"], []).append(attempt)
    for round_no in sorted(by_round):
        lines.append(f"ROUND {round_no}")
        for attempt in by_round[round_no]:
            label = LANE_LABELS.get(attempt["lane"], attempt["lane"])
            # display label + the raw lane key the ledger stores, so the view
            # is auditable against conductor_attempt rows and greppable by id
            line = (f"  {attempt['status'].upper():<12} {label:<14} "
                    f"attempt {attempt['id']} [{attempt['lane']}]")
            if attempt["error_class"]:
                line += f" ({attempt['error_class']})"
            lines.append(line)
    if not attempts:
        lines.append("  (no attempts yet)")
    lines.append(f"NEXT         {compute_next_action(session, attempts, incidents)}")
    return "\n".join(lines)


def _mapping_get(row, key: str, default=""):
    if row is None:
        return default
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = getattr(row, key, default)
    return default if value is None else value


def _event_line(event) -> str:
    kind = str(_mapping_get(event, "event_type", "event")).upper()
    detail = re.sub(r"\s+", " ", str(_mapping_get(event, "detail", ""))).strip()
    return f"{kind}: {detail}" if detail else kind


def _panel_events(events: list) -> list:
    """Select bounded activity instead of three trailing bookkeeping rows."""
    selected = []
    for kinds in (
        {"tool_request"},
        {"tool_result"},
        {"error", "completion", "claim_gate"},
    ):
        match = next(
            (
                event for event in reversed(events)
                if _mapping_get(event, "event_type") in kinds
            ),
            None,
        )
        if match is not None:
            selected.append(match)
    return selected


def control_room_page(conn, session_id: str, *, color=None, width=None, stream=None) -> str:
    """Render a bounded static four-lane control-room page.

    This remains an operational ledger view: event excerpts are typed and
    bounded, never presented as a raw transcript or as research evidence.
    """
    session = db.get_conductor_session(conn, session_id)
    if session is None:
        raise ValueError(f"BLOCKED: conductor session '{session_id}' does not exist")
    stream = sys.stdout if stream is None else stream
    use_color = supports_color(stream) if color is None else bool(color)
    columns = terminal_width(stream) if width is None else int(width)
    columns = max(60, min(120, columns))
    inner = columns - 4

    attempts = list(db.list_conductor_attempts(conn, session["id"]))
    incidents = list(db.list_conductor_incidents(conn, session["id"]))
    rounds = [int(_mapping_get(a, "round", 0)) for a in attempts]
    shown_round = max(rounds) if rounds else (session["rounds"] or 1)

    target = db.get_target(conn, session["target_id"])
    source = None
    get_source = getattr(db, "get_target_source", None)
    if get_source is not None:
        source = get_source(conn, session["target_id"])
    canonical = _mapping_get(source, "canonical", target["url"])
    source_kind = _mapping_get(source, "kind", "url")

    adapter_id = str(session["adapter_id"] or "?")
    adapter_version = str(session["adapter_version"] or "?")
    simulated = adapter_id in {"mock", "mock-harness"}
    mode = (
        "SIMULATED — no external agents invoked"
        if simulated
        else f"ADAPTER {adapter_id} v{adapter_version} — SERIAL 4-LANE"
    )

    border = "+" + "-" * (columns - 2) + "+"

    def frame(text: str, *, decorate: bool = False) -> str:
        content = pad_visible(truncate_visible(text, inner), inner)
        plain = f"| {content} |"
        return style(plain, green=True, bold=decorate, color=use_color) if decorate else plain

    lines = [style(border, green=True, color=use_color)]
    lines.append(frame(f"HUNT-OS CONTROL ROOM / SESSION {session['id']}", decorate=True))
    lines.append(frame(
        f"adapter {adapter_id} v{adapter_version} / status {session['status']} / round {shown_round}"
    ))
    lines.append(frame(f"target #{target['id']} {target['name']} / {source_kind}: {canonical}"))
    lines.append(frame(mode))
    lines.append(style(border, green=True, color=use_color))

    list_events = getattr(db, "list_conductor_events", None)
    for lane in db.CONDUCTOR_LANES:
        lane_attempts = [
            a for a in attempts
            if a["lane"] == lane and int(_mapping_get(a, "round", 0)) == int(shown_round)
        ]
        attempt = lane_attempts[-1] if lane_attempts else None
        label = f"{LANE_LABELS.get(lane, lane)} [{lane}]"
        lines.append(frame(label, decorate=True))
        if attempt is None:
            lines.append(frame("READY / no attempt yet"))
        else:
            status_line = f"{str(attempt['status']).upper()} / attempt {attempt['id']}"
            if attempt["error_class"]:
                status_line += f" / {attempt['error_class']}"
            lines.append(frame(status_line))
            events = []
            if list_events is not None:
                # Query the full per-attempt journal (bounded: one attempt
                # holds a handful of rows) so _panel_events can still find
                # the tool_request/tool_result pair. A narrow trailing
                # window (e.g. limit=3) only contains bookkeeping rows
                # (claim_gate/usage/completion) and starves the panel.
                try:
                    events = list(list_events(conn, session["id"], attempt["id"], limit=100))
                except TypeError:
                    events = list(list_events(
                        conn, session["id"], attempt_id=attempt["id"], limit=100
                    ))
            if events:
                for event in _panel_events(events):
                    lines.append(frame("  " + _event_line(event)))
            else:
                lines.append(frame("  no recorded operational events"))
        lines.append(style(border, green=True, color=use_color))

    next_line = "NEXT  " + compute_next_action(session, attempts, incidents)
    lines.append(frame(next_line, decorate=True))
    lines.append(style(border, green=True, color=use_color))
    return "\n".join(lines)
