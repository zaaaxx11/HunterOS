"""Follow-up visibility (R2-09): the follow-up table must be READ.

The follow-up feature works (see test_followups.py) but nothing surfaced it,
so a finding's untested implications stayed invisible and rotted. These tests
pin the four surfaces that make the work visible: the brief, the contradiction
engine, the disclosure report, and the atlas-derived suggestion printed after
a promotion.
"""
import os
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "app" / "src"))

from huntos.core import atlas, db as kernel  # noqa: E402
from huntos.core.target_source import classify_target_source  # noqa: E402


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


def _finding(c, tid, title="parent bug", klass="Unknown"):
    return kernel.add_finding(c, tid, title, klass)


def _poc(tmp_path, name="p.py"):
    poc = tmp_path / name
    poc.write_text(f"print('{name}')\n", encoding="utf-8")
    return str(poc)


# --- (a) brief: the section exists and shows the live work -------------------


def test_brief_lists_open_followup_with_hypothesis(conn):
    c, tid = conn
    fid = _finding(c, tid)
    kernel.add_followup(c, fid, "same drain via the second operator key",
                        kind="escalation",
                        hypothesis="the guard checks only the first key")
    brief = kernel.export_brief(c, tid)
    assert "## Follow-ups" in brief
    assert "same drain via the second operator key" in brief
    assert "hypothesis: the guard checks only the first key" in brief
    assert f"parent=F-{fid}" in brief


def test_brief_shows_settled_outcomes(conn):
    """Dropped keeps its reason, promoted keeps the child finding id."""
    c, tid = conn
    fid = _finding(c, tid)
    u1 = kernel.add_followup(c, fid, "second operator key", kind="escalation")
    kernel.drop_followup(c, u1, "tried key[1]; the guard covers both keys")
    u2 = kernel.add_followup(c, fid, "proxy path skips the guard",
                             kind="chain-step")
    child = kernel.promote_followup(c, u2, "Unknown", "high")
    brief = kernel.export_brief(c, tid)
    assert "dropped" in brief
    assert "the guard covers both keys" in brief
    assert f"promoted to finding #{child}" in brief


def test_brief_guidance_line_when_empty(conn):
    c, tid = conn
    brief = kernel.export_brief(c, tid)
    assert "## Follow-ups" in brief
    assert "(none recorded" in brief
    assert "hunt followup add" in brief


# --- (b) contradictions: terminal findings cannot settle their follow-ups ----


def test_contradiction_flags_proven_live_with_open_followup(conn, tmp_path):
    """The rot case: the finding reached proven-live, THEN an implication was
    registered. The close gate never fires again, so the follow-up can only
    be settled directly — which is exactly what the flag says."""
    c, tid = conn
    fid = _finding(c, tid)
    poc = _poc(tmp_path)
    kernel.record_poc_run(c, fid, poc, 0, "ok")
    kernel.promote_finding(c, fid, "ref-1", poc)
    poc2 = _poc(tmp_path, "p2.py")
    kernel.record_poc_run(c, fid, poc2, 0, "ok")
    kernel.record_verification(c, fid, "http_transcript", "body", "verifier")
    kernel.record_adversary(c, fid, "attacked the guard; it held", "adversary")
    kernel.promote_finding(c, fid, "ref-2", poc2)
    assert c.execute("SELECT ladder_status FROM findings WHERE id=?",
                     (fid,)).fetchone()[0] == "proven-live"
    kernel.add_followup(c, fid, "second operator key", kind="escalation")
    flags = kernel.find_contradictions(c, tid)
    joined = "\n".join(flags)
    assert f"!! finding #{fid} is proven-live but still has 1 open follow-up(s)" in joined
    assert "hunt followup verify|drop|promote" in joined


def test_contradiction_ignores_theoretical_finding_with_open_followup(conn):
    """A finding that can still climb is normal — its gate will settle them."""
    c, tid = conn
    fid = _finding(c, tid)
    kernel.add_followup(c, fid, "second operator key", kind="escalation")
    flags = kernel.find_contradictions(c, tid)
    assert not any(f"finding #{fid}" in f for f in flags)


def test_contradiction_flags_overturned_finding(conn):
    c, tid = conn
    fid = _finding(c, tid)
    kernel.overturn_finding(c, fid, "blind adversary")
    # overturn is blocked while a follow-up is open, so this row can only
    # exist via a direct write — which is exactly the rot case.
    c.execute("INSERT INTO followups (parent_finding_id, target_id, title, "
              "hypothesis, kind, state) VALUES (?,?,?,?,?,'open')",
              (fid, tid, "leftover implication", "", "variant"))
    c.commit()
    flags = kernel.find_contradictions(c, tid)
    assert any(f"finding #{fid} is overturned but still has 1 open follow-up(s)"
               in f for f in flags)


# --- (c) report: the section rides inside the hashed body --------------------


def test_report_has_followups_and_a_valid_footer(conn, tmp_path):
    c, tid = conn
    fid = _finding(c, tid)
    kernel.add_followup(c, fid, "proxy path skips the guard", kind="chain-step")
    report = kernel.export_report(c, tid)
    assert "## Follow-ups" in report
    assert "proxy path skips the guard" in report
    assert f"parent=F-{fid}" in report
    out = tmp_path / "report.md"
    out.write_text(report, encoding="utf-8")
    assert kernel.verify_report_file(str(out)) == "report matches its fingerprint"
    # the footer is the last thing in the file, and the follow-up section is
    # INSIDE the hashed body (before it), not appended after.
    assert "<!-- hunt-report sha256:" in report.splitlines()[-1]
    assert report.index("## Follow-ups") < report.index("<!-- hunt-report sha256:")


def test_report_empty_followups_placeholder(conn, tmp_path):
    c, tid = conn
    _finding(c, tid)
    report = kernel.export_report(c, tid)
    assert "## Follow-ups" in report
    assert "(none recorded)" in report
    out = tmp_path / "report.md"
    out.write_text(report, encoding="utf-8")
    assert kernel.verify_report_file(str(out)) == "report matches its fingerprint"


# --- (d) the atlas suggestion after a promotion ------------------------------


def _promote_via_cli(capsys, tmp_path, klass):
    """Drive `hunt finding promote` through the real CLI and return stdout.

    The fixture's connection is the same one the CLI opens (HUNT_DB points at
    the fixture's db), so the finding added here is the one promoted there.
    """
    from huntos.cli.main import main
    fid = kernel.add_finding(_conn(), 1, "bug", klass)
    poc = tmp_path / "poc.py"
    poc.write_text("print('poc')\n", encoding="utf-8")
    kernel.record_poc_run(_conn(), fid, str(poc), 0, "ok")
    capsys.readouterr()
    assert main(["finding", "promote", "--id", str(fid),
                 "--evidence-ref", "ev1", "--poc-path", str(poc)]) == 0
    return capsys.readouterr().out


def _conn():
    """A second handle on the fixture's db (WAL allows concurrent readers)."""
    return kernel.connect()


def test_promote_suggests_followups_for_a_known_klass(conn, capsys, tmp_path):
    out = _promote_via_cli(capsys, tmp_path, "Reentrancy")
    assert "consider follow-up: hunt followup add" in out
    assert "--kind" in out
    # the suggestion is a command, not a claim: it names the finding id
    assert "hunt followup add 1 " in out


def test_promote_silent_for_an_unknown_klass(conn, capsys, tmp_path):
    """The db refuses an unknown klass at insert, so the 'no atlas family'
    path is exercised directly: the finding's klass simply has no family."""
    from huntos.cli.main import _suggest_followups
    c, tid = conn
    fid = _finding(c, tid, klass="Unknown")
    # Unknown is a real taxonomy value but has no atlas family.
    assert atlas.by_klass("Unknown") == []
    capsys.readouterr()
    _suggest_followups(c, fid)
    assert capsys.readouterr().out == ""


def test_suggestion_kind_is_deterministic(conn, capsys, tmp_path):
    """The documented kind rule: escalation only for escalation-ish variants."""
    # Access control names a takeover variant -> escalation
    out = _promote_via_cli(capsys, tmp_path, "Access")
    assert "--kind escalation" in out
    # Reentrancy's variants are plain sibling shapes -> variant
    out = _promote_via_cli(capsys, tmp_path, "Reentrancy")
    assert "--kind variant" in out


def test_atlas_klasses_are_known(conn):
    """Guard the suggestion test's assumption about the atlas data."""
    assert "Reentrancy" in atlas.klasses()
    assert "Access" in atlas.klasses()
    assert atlas.by_klass("NoSuchKlass") == []
