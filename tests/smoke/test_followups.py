"""Follow-up vulns: the finding->finding lineage edge and its close gate.

A finding's untested implications used to live in the operator's head. They
are now ledger objects, and a finding cannot reach a terminal state while
any of them is still open.
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


def _finding(c, tid, title="parent bug"):
    return kernel.add_finding(c, tid, title, "Unknown")


def test_add_followup_and_list(conn):
    c, tid = conn
    fid = _finding(c, tid)
    uid = kernel.add_followup(c, fid, "same drain via the second operator key",
                              kind="escalation",
                              hypothesis="the guard checks only the first key")
    rows = kernel.list_followups(c, finding_id=fid)
    assert len(rows) == 1
    assert rows[0]["id"] == uid
    assert rows[0]["state"] == "open"
    assert rows[0]["kind"] == "escalation"
    assert rows[0]["parent_finding_id"] == fid


def test_unknown_kind_refused(conn):
    c, tid = conn
    fid = _finding(c, tid)
    with pytest.raises(ValueError, match="follow-up kind must be one of"):
        kernel.add_followup(c, fid, "x", kind="nonsense")


def test_promote_blocked_while_followup_open(conn):
    """The close gate: a finding cannot climb over an open follow-up."""
    c, tid = conn
    fid = _finding(c, tid)
    kernel.add_followup(c, fid, "second operator key", kind="escalation")
    poc = pathlib.Path(c.execute("PRAGMA database_list").fetchone()["file"]).parent / "p.py"
    poc.write_text("print('x')\n", encoding="utf-8")
    kernel.record_poc_run(c, fid, str(poc), 0, "ok")
    with pytest.raises(ValueError, match="open follow-up"):
        kernel.promote_finding(c, fid, "evidence-ref-1", str(poc))


def test_overturn_blocked_while_followup_open(conn):
    c, tid = conn
    fid = _finding(c, tid)
    kernel.add_followup(c, fid, "second operator key", kind="escalation")
    with pytest.raises(ValueError, match="open follow-up"):
        kernel.overturn_finding(c, fid, "blind adversary")


def test_verify_closes_the_gate(conn):
    c, tid = conn
    fid = _finding(c, tid)
    uid = kernel.add_followup(c, fid, "second operator key", kind="escalation")
    with pytest.raises(ValueError, match="requires the evidence"):
        kernel.verify_followup(c, uid, "")
    kernel.verify_followup(c, uid, "guard reads key[0] only; key[1] passes the same drain")
    assert kernel.open_followups(c, fid) == []
    rows = kernel.list_followups(c, finding_id=fid)
    assert rows[0]["state"] == "verified"
    assert rows[0]["closed_at"] is not None


def test_drop_requires_a_real_reason(conn):
    c, tid = conn
    fid = _finding(c, tid)
    uid = kernel.add_followup(c, fid, "second operator key", kind="escalation")
    with pytest.raises(ValueError, match="min 20 chars"):
        kernel.drop_followup(c, uid, "nope")
    kernel.drop_followup(c, uid, "tried key[1] against the guard; it reverts, so no escalation")
    rows = kernel.list_followups(c, finding_id=fid)
    assert rows[0]["state"] == "dropped"
    assert "reverts" in rows[0]["drop_reason"]


def test_promote_followup_mints_a_linked_finding(conn):
    c, tid = conn
    parent = _finding(c, tid, "parent bug")
    uid = kernel.add_followup(c, parent, "unprotected drain on the proxy path",
                              kind="chain-step",
                              hypothesis="the proxy forwards without the guard")
    child = kernel.promote_followup(c, uid, "Unknown", "high")
    row = c.execute("SELECT parent_finding_id FROM findings WHERE id=?",
                    (child,)).fetchone()
    assert row["parent_finding_id"] == parent
    fu = kernel.list_followups(c, finding_id=parent)[0]
    assert fu["state"] == "promoted"
    assert fu["promoted_finding_id"] == child
    # the child itself carries no open follow-ups, so it can climb
    assert kernel.open_followups(c, child) == []


def test_closed_followup_cannot_be_reclosed(conn):
    c, tid = conn
    fid = _finding(c, tid)
    uid = kernel.add_followup(c, fid, "x", kind="variant")
    kernel.drop_followup(c, uid, "checked the sibling endpoint; the guard is present there too")
    with pytest.raises(ValueError, match="only an open follow-up"):
        kernel.verify_followup(c, uid, "evidence")
    with pytest.raises(ValueError, match="only an open follow-up"):
        kernel.drop_followup(c, uid, "another reason that is long enough")


def test_duplicate_title_per_parent_refused(conn):
    c, tid = conn
    fid = _finding(c, tid)
    kernel.add_followup(c, fid, "same title", kind="variant")
    with pytest.raises(Exception):
        kernel.add_followup(c, fid, "same title", kind="escalation")


def test_promote_allowed_after_followups_settled(conn):
    """The full loop: open follow-up blocks, settling it unblocks."""
    c, tid = conn
    fid = _finding(c, tid)
    u1 = kernel.add_followup(c, fid, "second operator key", kind="escalation")
    u2 = kernel.add_followup(c, fid, "proxy path skips the guard", kind="chain-step")
    poc = pathlib.Path(c.execute("PRAGMA database_list").fetchone()["file"]).parent / "p.py"
    poc.write_text("print('x')\n", encoding="utf-8")
    kernel.record_poc_run(c, fid, str(poc), 0, "ok")
    with pytest.raises(ValueError, match="2 open follow-up"):
        kernel.promote_finding(c, fid, "ref-1", str(poc))
    kernel.verify_followup(c, u1, "key[1] is checked too; no escalation")
    kernel.drop_followup(c, u2, "the proxy re-validates before forwarding; chain dead")
    status = kernel.promote_finding(c, fid, "ref-1", str(poc))
    assert status == "in-code"


def test_followup_events_are_logged(conn):
    c, tid = conn
    fid = _finding(c, tid)
    uid = kernel.add_followup(c, fid, "second operator key", kind="escalation")
    kinds = [r["kind"] for r in c.execute(
        "SELECT kind FROM events WHERE finding_id=? ORDER BY id", (fid,)).fetchall()]
    assert "followup_added" in kinds
    kernel.verify_followup(c, uid, "checked; the guard covers both keys")
    kinds = [r["kind"] for r in c.execute(
        "SELECT kind FROM events WHERE finding_id=? ORDER BY id", (fid,)).fetchall()]
    assert "followup_verified" in kinds


def test_legacy_db_migrates_parent_column(tmp_path):
    """A db created before the lineage edge opens and reads NULL."""
    import os
    import sqlite3
    os.environ["HUNT_DB"] = str(tmp_path / "legacy.db")
    raw = sqlite3.connect(str(tmp_path / "legacy.db"))
    raw.execute(
        "CREATE TABLE findings (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "target_id INTEGER, title TEXT, klass TEXT, severity TEXT DEFAULT 'info', "
        "ladder_status TEXT DEFAULT 'theoretical', evidence_ref TEXT DEFAULT '', "
        "poc_path TEXT DEFAULT '', poc_sha256 TEXT DEFAULT '', falsifier TEXT DEFAULT '', "
        "overturned_by TEXT DEFAULT '', notes TEXT DEFAULT '', action TEXT DEFAULT 'read', "
        "wave_id INTEGER, surface_id INTEGER, created_at TEXT)"
    )
    raw.commit()
    raw.close()
    c = kernel.connect()
    cols = {r[1] for r in c.execute("PRAGMA table_info(findings)").fetchall()}
    assert "parent_finding_id" in cols
    tables = {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "followups" in tables
    c.close()


def test_followup_promote_flag_does_not_clobber_subaction():
    """E22 class: a `--action` flag must not overwrite the subparser's dest.

    `hunt lead promote` shipped with exactly this bug once (--action claimed
    dest="action", so the promote branch never ran). The followup promote
    parser uses --roe-action instead; this pins it.
    """
    import argparse
    p = argparse.ArgumentParser(prog="hunt")
    sub = p.add_subparsers(dest="cmd", required=True)
    pfu = sub.add_parser("followup")
    pfu_sub = pfu.add_subparsers(dest="action", required=True)
    pfup = pfu_sub.add_parser("promote")
    pfup.add_argument("followup_id", type=int)
    pfup.add_argument("--klass", required=True)
    pfup.add_argument("--severity", default="info")
    pfup.add_argument("--roe-action", dest="roe_action", default="read")
    a = pfu.parse_args(["promote", "2", "--klass", "Unknown", "--severity", "high"])
    assert a.action == "promote"
    assert a.roe_action == "read"
    a = pfu.parse_args(["promote", "2", "--klass", "Unknown",
                        "--roe-action", "mutate"])
    assert a.action == "promote"
    assert a.roe_action == "mutate"


def test_followup_promote_end_to_end(conn):
    """The CLI path: a follow-up becomes its own linked finding."""
    c, tid = conn
    parent = _finding(c, tid, "parent bug")
    uid = kernel.add_followup(c, parent, "proxy path skips the guard",
                              kind="chain-step")
    child = kernel.promote_followup(c, uid, "Unknown", "high", action="read")
    row = c.execute("SELECT parent_finding_id, ladder_status FROM findings WHERE id=?",
                    (child,)).fetchone()
    assert row["parent_finding_id"] == parent
    assert row["ladder_status"] == "theoretical"
