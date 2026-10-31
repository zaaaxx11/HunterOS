"""Claim gate: a chained finding's claim rides its ancestors too.

The gate is exercised as a real subprocess against a real ledger, because its
contract IS the exit code.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
GATE = REPO / "app" / "src" / "huntos" / "_data" / "bin" / "claim_gate.py"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load("claim_gate_under_test", GATE)


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    """A real ledger with a target in hunting phase and a finding."""
    monkeypatch.setenv("HUNT_DB", str(tmp_path / "hunt.db"))
    sys.path.insert(0, str(REPO / "app" / "src"))
    try:
        from huntos.core import db as kernel
        from huntos.core.target_source import classify_target_source
        conn = kernel.connect()
        tid = kernel.prepare_target(
            conn, "t", classify_target_source(str(tmp_path)), "evm",
            hosts="*", actions="read", authorization_note="unit test")
        kernel.score_target(conn, tid, 5.0)
        kernel.set_phase(conn, tid, "recon")
        sm = tmp_path / "sm.md"
        sm.write_text("sm", encoding="utf-8")
        kernel.record_phase_artifact(conn, tid, "surface_map", str(sm))
        kernel.set_phase(conn, tid, "classify")
        ap = tmp_path / "ap.md"
        ap.write_text("ap", encoding="utf-8")
        kernel.record_phase_artifact(conn, tid, "attack_plan", str(ap))
        kernel.set_phase(conn, tid, "hunting")
        yield conn, tid, tmp_path
        conn.close()
    finally:
        sys.path.pop(0)


def _run_gate(text: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE)], input=text, capture_output=True,
        text=True, timeout=60,
    )


def _promote_to_proven_live(conn, fid, tmp_path):
    """Walk a finding all the way up the ladder, honestly."""
    poc = tmp_path / f"poc_{fid}.py"
    poc.write_text(f"print('poc for {fid}')\n", encoding="utf-8")
    kernel = sys.modules["huntos.core.db"]
    kernel.record_poc_run(conn, fid, str(poc), 0, "ok")
    kernel.promote_finding(conn, fid, f"ref-{fid}", str(poc))
    kernel.record_verification(conn, fid, "fork_receipt", f"receipt {fid}")
    kernel.record_adversary(conn, fid, f"challenged {fid}")
    poc2 = tmp_path / f"poc_live_{fid}.py"
    poc2.write_text(f"print('live {fid}')\n", encoding="utf-8")
    kernel.record_poc_run(conn, fid, str(poc2), 0, "ok")
    kernel.promote_finding(conn, fid, f"live-ref-{fid}", str(poc2))


def _force_status(db_path, fid, status):
    """Set a finding's ladder status on a RAW connection.

    The app connection registers huntos_session_guard_ok(), so its tamper
    triggers refuse a direct UPDATE. These tests isolate the CHAIN rule from
    the ordinary finding rule, which needs a row whose own status is already
    proven-live while its parent is not — a state the honest ladder cannot
    produce. A raw connection without the guard can, and the gate under test
    opens the db read-only anyway, so what it sees is identical.
    """
    import sqlite3
    raw = sqlite3.connect(str(db_path))
    try:
        # The tamper triggers call huntos_session_guard_ok(); a raw connection
        # has not registered it, so provide the permissive stub the app session
        # registers for its own guarded writes.
        raw.create_function("huntos_session_guard_ok", 0, lambda: 1)
        # findings_proven_requires_evidence does NOT consult the guard (it is a
        # hard law, not a session one), so it is dropped for the duration of
        # this forced write and restored immediately after.
        raw.execute("DROP TRIGGER IF EXISTS findings_proven_requires_evidence")
        raw.execute("UPDATE findings SET ladder_status=? WHERE id=?", (status, fid))
        raw.commit()
    finally:
        raw.execute(
            "CREATE TRIGGER IF NOT EXISTS findings_proven_requires_evidence "
            "BEFORE UPDATE OF ladder_status ON findings "
            "WHEN NEW.ladder_status='proven-live' "
            "AND NOT EXISTS (SELECT 1 FROM events e WHERE e.finding_id=NEW.id "
            "AND e.kind='verifier_pass') "
            "BEGIN SELECT RAISE(ABORT, "
            "'BLOCKED: proven-live requires verifier, adversary, and poc-run events'); END"
        )
        raw.close()


def test_unproven_ancestor_helper_direct(ledger):
    conn, tid, tmp_path = ledger
    from huntos.core import db as kernel
    parent = kernel.add_finding(conn, tid, "parent", "Unknown")
    child = kernel.add_finding(conn, tid, "child", "Unknown")
    conn.execute("UPDATE findings SET parent_finding_id=? WHERE id=?",
                 (parent, child))
    conn.commit()
    # parent is theoretical -> the child's claim cannot pass
    msg = gate._unproven_ancestor(conn, child)
    assert msg is not None
    assert "parent" in msg and "theoretical" in msg
    # a root finding has no ancestor to check
    assert gate._unproven_ancestor(conn, parent) is None


def test_gate_vetoes_chain_claim_with_theoretical_parent(ledger):
    conn, tid, tmp_path = ledger
    from huntos.core import db as kernel
    parent = kernel.add_finding(conn, tid, "parent", "Unknown")
    child = kernel.add_finding(conn, tid, "child", "Unknown")
    conn.execute("UPDATE findings SET parent_finding_id=? WHERE id=?",
                 (parent, child))
    conn.commit()
    # Force the child's own row to proven-live so ONLY the ancestor is weak:
    # this isolates the chain rule from the ordinary finding rule.
    _force_status(tmp_path / "hunt.db", child, "proven-live")
    proc = _run_gate(f"the drain is PROVEN[F-{child}]")
    assert proc.returncode == 2
    assert "parent" in proc.stderr


def test_gate_passes_chain_claim_when_all_links_proven(ledger):
    conn, tid, tmp_path = ledger
    from huntos.core import db as kernel
    parent = kernel.add_finding(conn, tid, "parent", "Unknown")
    _promote_to_proven_live(conn, parent, tmp_path)
    child = kernel.add_finding(conn, tid, "child", "Unknown")
    conn.execute("UPDATE findings SET parent_finding_id=? WHERE id=?",
                 (parent, child))
    conn.commit()
    _force_status(tmp_path / "hunt.db", child, "proven-live")
    proc = _run_gate(f"the drain is PROVEN[F-{child}]")
    assert proc.returncode == 0, proc.stderr


def test_gate_vetoes_chain_claim_with_overturned_parent(ledger):
    conn, tid, tmp_path = ledger
    from huntos.core import db as kernel
    parent = kernel.add_finding(conn, tid, "parent", "Unknown")
    _promote_to_proven_live(conn, parent, tmp_path)
    kernel.overturn_finding(conn, parent, "blind adversary")
    child = kernel.add_finding(conn, tid, "child", "Unknown")
    conn.execute("UPDATE findings SET parent_finding_id=? WHERE id=?",
                 (parent, child))
    conn.commit()
    _force_status(tmp_path / "hunt.db", child, "proven-live")
    proc = _run_gate(f"the drain is PROVEN[F-{child}]")
    assert proc.returncode == 2
    assert "overturned" in proc.stderr


def test_gate_vetoes_missing_ancestor(ledger):
    conn, tid, tmp_path = ledger
    from huntos.core import db as kernel
    child = kernel.add_finding(conn, tid, "child", "Unknown")
    # Point the child at a parent id that does not exist. The app connection
    # enforces the FK, so the dangling link is written on a raw connection —
    # the gate must treat a missing ancestor as weak, not as absent.
    import sqlite3
    raw = sqlite3.connect(str(tmp_path / "hunt.db"))
    try:
        raw.create_function("huntos_session_guard_ok", 0, lambda: 1)
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("UPDATE findings SET parent_finding_id=? WHERE id=?",
                    (9999, child))
        raw.commit()
    finally:
        raw.close()
    _force_status(tmp_path / "hunt.db", child, "proven-live")
    proc = _run_gate(f"the drain is PROVEN[F-{child}]")
    assert proc.returncode == 2
    # The dangling parent reads as a weak link either way — the gate names it
    # and refuses the claim.
    assert "parent #9999" in proc.stderr
    assert "chained claim rides its ancestors" in proc.stderr


def test_gate_detects_cyclic_lineage(ledger):
    conn, tid, tmp_path = ledger
    from huntos.core import db as kernel
    a = kernel.add_finding(conn, tid, "a", "Unknown")
    b = kernel.add_finding(conn, tid, "b", "Unknown")
    conn.execute("UPDATE findings SET parent_finding_id=? WHERE id=?", (b, a))
    conn.execute("UPDATE findings SET parent_finding_id=? WHERE id=?", (a, b))
    conn.commit()
    _force_status(tmp_path / "hunt.db", a, "proven-live")
    _force_status(tmp_path / "hunt.db", b, "proven-live")
    proc = _run_gate(f"the drain is PROVEN[F-{a}]")
    assert proc.returncode == 2
    assert "cyclic" in proc.stderr


def test_gate_unchanged_for_unchained_findings(ledger):
    """The chain rule must not disturb the ordinary finding rule."""
    conn, tid, tmp_path = ledger
    from huntos.core import db as kernel
    fid = kernel.add_finding(conn, tid, "solo", "Unknown")
    proc = _run_gate(f"the drain is PROVEN[F-{fid}]")
    assert proc.returncode == 2
    assert "theoretical" in proc.stderr
    _promote_to_proven_live(conn, fid, tmp_path)
    proc = _run_gate(f"the drain is PROVEN[F-{fid}]")
    assert proc.returncode == 0, proc.stderr


def test_gate_still_passes_claim_free_text(ledger):
    proc = _run_gate("nothing strong in here")
    assert proc.returncode == 0
