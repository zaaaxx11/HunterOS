"""Contract tests for the crypto-attack atlas (`hunt atlas` + skill payload).

The atlas is DATA that the CLI and the skill corpus both rely on, so the cheap
checks here are the ones that would otherwise fail silently at runtime:
JSON parses, every family is well formed, every `klass` is a value the ledger
actually accepts (otherwise `hunt finding add` would refuse it), every
referenced skill exists in the corpus, and the routed CLI verb stays read-only.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "app" / "src"
SKILL = SRC / "huntos" / "_data" / "idea" / "skills" / "web3" / "crypto-attack-atlas"
ATLAS = SKILL / "data" / "atlas.json"

sys.path.insert(0, str(SRC))


def _atlas() -> dict:
    return json.loads(ATLAS.read_text(encoding="utf-8"))


def test_atlas_file_exists_and_parses():
    data = _atlas()
    assert data["schema"] == "huntos-atlas/1"
    assert len(data["families"]) == 18


def test_every_family_is_well_formed():
    for fam in _atlas()["families"]:
        assert fam["id"].startswith("A")
        for key in ("name", "klass", "summary", "signals", "detect", "mitigate", "skills"):
            assert fam.get(key), f"{fam['id']} missing {key}"
        assert isinstance(fam["detect"], list) and fam["detect"]
        assert fam["incidents_total"] >= 0
        assert fam["loss_usd_parsed"] >= 0


def test_family_ids_are_unique_and_contiguous():
    ids = [f["id"] for f in _atlas()["families"]]
    assert len(ids) == len(set(ids))
    assert ids == [f"A{i}" for i in range(1, len(ids) + 1)]


def test_every_klass_is_in_the_ledger_taxonomy():
    # label discipline: a klass the ledger would refuse must never ship here
    from huntos.core.models import KLASS

    for fam in _atlas()["families"]:
        assert fam["klass"] in KLASS, f"{fam['id']} files under unknown klass {fam['klass']}"


def test_every_referenced_skill_exists_in_the_corpus():
    skills_root = SRC / "huntos" / "_data" / "idea" / "skills"
    known = {p.parent.name for p in skills_root.glob("*/*/SKILL.md")}
    for fam in _atlas()["families"]:
        for name in fam["skills"]:
            assert name in known, f"{fam['id']} points at missing skill {name}"


def test_every_swc_reference_is_in_the_shipped_registry():
    # The atlas cites SWC ids; they must match what the reference file claims.
    refs = (SKILL / "references" / "attack-families.md").read_text(encoding="utf-8")
    for fam in _atlas()["families"]:
        for swc in fam.get("swc", []):
            assert swc["id"] in refs


def test_keywords_cover_every_family():
    data = _atlas()
    for fam in data["families"]:
        assert data["keywords"].get(fam["id"]), f"{fam['id']} has no match keywords"


def test_atlas_verb_is_declared_read_only():
    from huntos.cli.main import READ_ONLY_COMMANDS
    from huntos.cli.registry import COMMAND_REGISTRY

    assert "atlas" in READ_ONLY_COMMANDS
    assert COMMAND_REGISTRY["atlas"]["read_only"] is True


def _run(args, db):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["HUNT_DB"] = str(db)
    return subprocess.run([sys.executable, "-m", "huntos", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, check=False)


def test_cli_list_show_and_match(tmp_path):
    db = tmp_path / "hunt.db"
    r = _run(["atlas", "list"], db)
    assert r.returncode == 0, r.stderr
    assert "A1" in r.stdout and "A18" in r.stdout

    r = _run(["atlas", "show", "a7"], db)
    assert r.returncode == 0, r.stderr
    assert "Precision" in r.stdout and "DETECT" in r.stdout

    r = _run(["atlas", "match", "share price jumps after deposit"], db)
    assert r.returncode == 0, r.stderr
    assert "A6" in r.stdout


def test_cli_unknown_family_is_a_clean_refusal(tmp_path):
    db = tmp_path / "hunt.db"
    r = _run(["atlas", "show", "Z9"], db)
    assert r.returncode == 2
    assert "BLOCKED" in r.stderr and "NEXT" in r.stderr


def test_seed_prints_a_lead_command_without_writing(tmp_path):
    db = tmp_path / "hunt.db"
    r = _run(["atlas", "seed", "--family", "A6", "--target-id", "4"], db)
    assert r.returncode == 0, r.stderr
    assert "hunt lead add --target 4" in r.stdout
    # `seed` prints, it never records: whatever db the CLI opened stays empty of
    # leads/findings (the CLI opening/creating a db is the pre-existing lifecycle
    # for every db-backed verb, not an atlas write).
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0
    finally:
        conn.close()