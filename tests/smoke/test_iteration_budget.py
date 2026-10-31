"""Iteration budget: the per-wave spend counter and its gate.

The budget is a ledger object, not a prompt: it is declared at wave open,
decremented by the CLI (never typed), and a spent wave refuses new work.
"""
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "app" / "src"))

from huntos.core import db as kernel  # noqa: E402
from huntos.core.target_source import classify_target_source  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    import os
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


def test_unbounded_wave_never_blocks(conn):
    c, tid = conn
    wid = _open(c, tid, None)
    for _ in range(50):
        kernel.spend_iteration(c, wid, 1)
    state = kernel.wave_budget(c, wid)
    assert state["budget"] is None
    assert state["exhausted"] is False
    assert state["remaining"] is None
    kernel.require_wave_budget(c, wid)  # no raise


def test_spend_decrements_and_blocks_at_zero(conn):
    c, tid = conn
    wid = _open(c, tid, 3)
    kernel.spend_iteration(c, wid, 1)
    assert kernel.wave_budget(c, wid)["used"] == 1
    kernel.spend_iteration(c, wid, 2)
    state = kernel.wave_budget(c, wid)
    assert state["used"] == 3
    assert state["remaining"] == 0
    assert state["exhausted"] is True
    assert state["exhausted_at"] is not None
    with pytest.raises(ValueError, match="iteration budget exhausted"):
        kernel.require_wave_budget(c, wid)


def test_finding_add_spends_and_gates(conn):
    c, tid = conn
    wid = _open(c, tid, 2)
    kernel.add_finding(c, tid, "first", "Unknown")
    kernel.add_finding(c, tid, "second", "Unknown")
    assert kernel.wave_budget(c, wid)["used"] == 2
    with pytest.raises(ValueError, match="iteration budget exhausted"):
        kernel.add_finding(c, tid, "third", "Unknown")


def test_lead_mutate_spends_and_gates(conn):
    c, tid = conn
    wid = _open(c, tid, 1)
    lid = kernel.add_lead(c, tid, "lead one", payload="p")
    kernel.mutate_lead(c, lid, "v", "a", "b", "advanced", "evidence")
    assert kernel.wave_budget(c, wid)["used"] == 1
    lid2 = kernel.add_lead(c, tid, "lead two", payload="p")
    with pytest.raises(ValueError, match="iteration budget exhausted"):
        kernel.mutate_lead(c, lid2, "v", "a", "c", "advanced", "evidence")


def test_raising_budget_requires_a_reason(conn):
    c, tid = conn
    wid = _open(c, tid, 1)
    kernel.spend_iteration(c, wid, 1)
    with pytest.raises(ValueError, match="requires a reason"):
        kernel.set_wave_budget(c, wid, 5, "")
    kernel.set_wave_budget(c, wid, 5, "second lane needed a real attempt")
    assert kernel.wave_budget(c, wid)["exhausted"] is False


def test_cannot_lower_budget_below_spend(conn):
    c, tid = conn
    wid = _open(c, tid, 10)
    kernel.spend_iteration(c, wid, 4)
    with pytest.raises(ValueError, match="already spent"):
        kernel.set_wave_budget(c, wid, 2, "trying to hide the spend")


def test_budget_change_is_logged(conn):
    c, tid = conn
    wid = _open(c, tid, 2)
    kernel.set_wave_budget(c, wid, 6, "operator widened the scope")
    row = c.execute(
        "SELECT detail FROM events WHERE kind='wave_budget_set' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert "budget 2 -> 6" in row["detail"]
    assert "operator widened the scope" in row["detail"]


def test_spend_is_logged_per_iteration(conn):
    c, tid = conn
    wid = _open(c, tid, 5)
    kernel.spend_iteration(c, wid, 1, what="probe: x=0")
    rows = c.execute(
        "SELECT detail FROM events WHERE kind='wave_iteration_spent'"
    ).fetchall()
    assert len(rows) == 1
    assert "wave" in rows[0]["detail"] and "probe: x=0" in rows[0]["detail"]


def test_negative_spend_refused(conn):
    c, tid = conn
    wid = _open(c, tid, 5)
    with pytest.raises(ValueError, match="positive integer"):
        kernel.spend_iteration(c, wid, 0)
    with pytest.raises(ValueError, match="positive integer"):
        kernel.spend_iteration(c, wid, True)


def test_status_flags_an_exhausted_open_wave(conn):
    c, tid = conn
    wid = _open(c, tid, 1)
    kernel.spend_iteration(c, wid, 1)
    flags = kernel.find_contradictions(c, tid)
    assert any("iteration budget exhausted" in f for f in flags)


def test_legacy_db_migrates_to_unbounded(tmp_path):
    """A db created before the budget columns opens and reads NULL (unbounded)."""
    import os
    import sqlite3
    os.environ["HUNT_DB"] = str(tmp_path / "legacy.db")
    # Build a minimal waves table without the budget columns, then open it
    # through the kernel so the guarded migration runs.
    raw = sqlite3.connect(str(tmp_path / "legacy.db"))
    raw.execute(
        "CREATE TABLE waves (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "target_id INTEGER, number INTEGER, lanes TEXT DEFAULT '', "
        "findings_new INTEGER DEFAULT 0, reaudit_done INTEGER DEFAULT 0, "
        "ev_verdict TEXT DEFAULT '', notes TEXT DEFAULT '', "
        "created_at TEXT DEFAULT (datetime('now')), "
        "UNIQUE(target_id, number))"
    )
    raw.commit()
    raw.close()
    c = kernel.connect()
    cols = {r[1] for r in c.execute("PRAGMA table_info(waves)").fetchall()}
    assert {"iteration_budget", "iterations_used", "budget_exhausted_at"} <= cols
    c.close()
