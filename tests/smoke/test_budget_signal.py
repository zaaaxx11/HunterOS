"""The iteration budget as a SIGNAL, not only a brake.

A spent wave used to leave `hunt next` recommending work the gate already
refused, and the conductor loop kept dispatching attempts into that refusal.
Both now read the budget as a direction: an open follow-up outranks the
generic status read while budget remains, a spent wave makes NEXT the close
command, and the managed loop stops with a recorded incident instead of
burning turns on refusals.
"""
import os
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "app" / "src"))

from huntos.core import db as kernel  # noqa: E402
from huntos.core.target_source import classify_target_source  # noqa: E402
from huntos.conductor.adapter import MockAdapter  # noqa: E402
from huntos.conductor.conductor import Conductor  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    os.environ["HUNT_DB"] = str(tmp_path / "hunt.db")
    c = kernel.connect()
    tid = kernel.prepare_target(
        c, "t", classify_target_source(str(tmp_path)), "evm",
        hosts="*", actions="read", authorization_note="unit test")
    kernel.score_target(c, tid, 5.0)
    kernel.set_phase(c, tid, "recon")
    sm = tmp_path / "surface_map.md"
    sm.write_text("sm", encoding="utf-8")
    kernel.record_phase_artifact(c, tid, "surface_map", str(sm))
    kernel.set_phase(c, tid, "classify")
    ap = tmp_path / "attack_plan.md"
    ap.write_text("ap", encoding="utf-8")
    kernel.record_phase_artifact(c, tid, "attack_plan", str(ap))
    kernel.set_phase(c, tid, "hunting")
    yield c, tid
    c.close()


def _open(c, tid, budget=None):
    return kernel.open_wave(c, tid, "architect,red", iteration_budget=budget)


# --- next_command: the budget as a signal ---------------------------------

def test_next_names_the_close_command_when_the_budget_is_spent(conn):
    """Row 9.5: a spent wave cannot fund the work row 9 used to advertise."""
    c, tid = conn
    wid = _open(c, tid, 2)
    kernel.spend_iteration(c, wid, 2)
    nxt, why = kernel.next_command(c, tid)
    assert nxt == f"hunt wave close --wave-id {wid} --verdict exhausted"
    assert "spent all 2 of its iteration budget" in why
    assert "refused until it is closed" in why
    # The read is gone: NEXT is no longer the generic status read.
    assert nxt != "hunt status"


def test_next_is_unchanged_when_the_budget_remains(conn):
    """Row 9 byte-identical: an open wave with budget left still reads."""
    c, tid = conn
    wid = _open(c, tid, 3)
    kernel.spend_iteration(c, wid, 1)
    nxt, why = kernel.next_command(c, tid)
    assert nxt == "hunt status"
    assert why == (
        f"wave #{wid} (number 1) is open — record findings and leads through the "
        "CLI; close it when the wave is done: "
        f"hunt wave close --wave-id {wid} --verdict continue|exhausted|pivot"
    )


def test_next_is_unchanged_for_an_unbudgeted_wave(conn):
    """No declared budget is a decision, not a default: the read survives."""
    c, tid = conn
    _open(c, tid, None)
    wid = _wave_id(c, tid)
    for _ in range(6):  # spend past any number a budget would have set
        kernel.spend_iteration(c, wid, 1)
    nxt, why = kernel.next_command(c, tid)
    assert nxt == "hunt status"
    assert "is open — record findings and leads" in why


def test_next_prefers_the_open_followup_while_budget_remains(conn):
    """Row 8.5: the untested implication is the next unit of work."""
    c, tid = conn
    wid = _open(c, tid, 5)
    first = kernel.add_finding(c, tid, "first bug", "Unknown")
    second = kernel.add_finding(c, tid, "second bug", "Unknown")
    kernel.add_followup(c, second, "same drain via the second operator key",
                        kind="escalation")
    nxt, why = kernel.next_command(c, tid)
    assert nxt == f"hunt followup list --finding {second}"
    assert f"finding #{second} has 1 open follow-up(s)" in why
    assert "escalation" in why
    # Both findings spent the budget: 5 declared, 2 gone, 3 left.
    assert "3 iteration(s) left" in why
    # The lowest parent finding id wins when more than one has follow-ups.
    kernel.add_followup(c, first, "check the sibling pool", kind="adjacent-surface")
    nxt, why = kernel.next_command(c, tid)
    assert nxt == f"hunt followup list --finding {first}"


def test_next_falls_through_to_status_when_no_followups_are_open(conn):
    """Follow-ups that are resolved no longer steer NEXT."""
    c, tid = conn
    _open(c, tid, 5)
    fid = kernel.add_finding(c, tid, "first bug", "Unknown")
    uid = kernel.add_followup(c, fid, "same drain via the second operator key")
    kernel.verify_followup(c, uid, "evidence ref")
    nxt, why = kernel.next_command(c, tid)
    assert nxt == "hunt status"
    assert "record findings and leads" in why


def test_next_does_not_recommend_followups_on_a_spent_wave(conn):
    """A spent wave outranks the follow-up row: the verdict comes first."""
    c, tid = conn
    wid = _open(c, tid, 1)
    fid = kernel.add_finding(c, tid, "first bug", "Unknown")
    kernel.add_followup(c, fid, "same drain via the second operator key")
    assert kernel.wave_budget(c, wid)["exhausted"] is True
    nxt, why = kernel.next_command(c, tid)
    assert nxt == f"hunt wave close --wave-id {wid} --verdict exhausted"
    assert "followup" not in nxt


def test_next_still_opens_the_brief_with_no_wave_at_all(conn):
    """Row 8 is untouched: no open wave is still the opening read."""
    c, tid = conn
    nxt, why = kernel.next_command(c, tid)
    assert nxt == f"hunt brief {tid}"
    assert "no open wave" in why


# --- the conductor loop: the budget as a stop ----------------------------

def _hunting_target(tmp_path):
    os.environ["HUNT_DB"] = str(tmp_path / "hunt.db")
    c = kernel.connect()
    tid = kernel.prepare_target(
        c, "t", classify_target_source(str(tmp_path)), "evm",
        hosts="*", actions="read", authorization_note="unit test")
    kernel.score_target(c, tid, 5.0)
    kernel.set_phase(c, tid, "recon")
    sm = tmp_path / "surface_map.md"
    sm.write_text("sm", encoding="utf-8")
    kernel.record_phase_artifact(c, tid, "surface_map", str(sm))
    kernel.set_phase(c, tid, "classify")
    ap = tmp_path / "attack_plan.md"
    ap.write_text("ap", encoding="utf-8")
    kernel.record_phase_artifact(c, tid, "attack_plan", str(ap))
    kernel.set_phase(c, tid, "hunting")
    return c, tid


def test_conductor_stops_dispatching_when_the_wave_budget_is_spent(tmp_path):
    """A spent wave stops the loop cleanly and records why."""
    c, tid = _hunting_target(tmp_path)
    wid = kernel.open_wave(c, tid, "architect,red", iteration_budget=1)
    kernel.spend_iteration(c, wid, 1)
    conductor = Conductor(MockAdapter())
    session = conductor.start_run(c, tid, 2)
    # No raise, and the session row comes back.
    assert session["id"].startswith("S-")
    # Nothing was dispatched: the budget was already spent at the first cell.
    assert kernel.list_conductor_attempts(c, session["id"]) == []
    assert conductor.dispatch_log == []
    incidents = kernel.list_conductor_incidents(c, session["id"])
    assert len(incidents) == 1
    assert incidents[0]["class"] == "wave_budget_exhausted"
    assert f"wave #{wid} spent 1/1 iterations" in incidents[0]["detail"]
    c.close()


def test_conductor_runs_normally_while_the_wave_has_budget(tmp_path):
    """The stop is a signal, not a blanket brake: budget left, lanes run."""
    c, tid = _hunting_target(tmp_path)
    kernel.open_wave(c, tid, "architect,red", iteration_budget=50)
    conductor = Conductor(MockAdapter())
    session = conductor.start_run(c, tid, 1)
    assert session["status"] == "completed"
    assert len(kernel.list_conductor_attempts(c, session["id"])) == 4
    assert kernel.list_conductor_incidents(c, session["id"]) == []
    c.close()


def test_conductor_ignores_a_target_with_no_open_wave(tmp_path):
    """No open wave means no budget to read: the loop is unaffected."""
    c, tid = _hunting_target(tmp_path)
    conductor = Conductor(MockAdapter())
    session = conductor.start_run(c, tid, 1)
    assert session["status"] == "completed"
    assert len(kernel.list_conductor_attempts(c, session["id"])) == 4
    c.close()


def _wave_id(c, tid):
    row = c.execute(
        "SELECT id FROM waves WHERE target_id=? AND ev_verdict='' "
        "ORDER BY number DESC LIMIT 1", (tid,)
    ).fetchone()
    return row["id"]
