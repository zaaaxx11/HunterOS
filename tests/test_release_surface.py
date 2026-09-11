import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "src"


def test_source_cli_exposes_update_without_opening_database(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["HUNT_DB"] = str(tmp_path / "must-not-exist.db")
    result = subprocess.run(
        [sys.executable, "-m", "huntos", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "    update " in result.stdout
    assert not (tmp_path / "must-not-exist.db").exists()