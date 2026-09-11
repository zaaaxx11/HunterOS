import hashlib
from pathlib import Path

import pytest

from huntos import updater


def test_manifest_rejects_non_canonical_tags():
    digest = "a" * 64
    manifest = f"{digest}  huntos-0.4.0-py3-none-manylinux.whl\n"

    with pytest.raises(ValueError, match="valid canonical"):
        updater._manifest_entry(manifest, "0.4.0")


def test_installation_target_refuses_non_official_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("HUNTOS_HOME", str(tmp_path / "HunterOS"))
    monkeypatch.setattr(updater.sys, "prefix", str(tmp_path / "other"))
    monkeypatch.setattr(updater.sys, "base_prefix", str(tmp_path / "python"))

    with pytest.raises(ValueError, match="official HUNT-OS venv"):
        updater._installation_target()


def test_promote_restores_previous_environment_after_validation_failure(monkeypatch, tmp_path):
    home = tmp_path / "HunterOS"
    target = home / "venv"
    run = home / ".staging" / "update"
    candidate = run / "venv"
    wheel = run / "huntos-0.4.0-py3-none-any.whl"
    target.mkdir(parents=True)
    (target / "marker").write_text("old", encoding="utf-8")
    candidate.mkdir(parents=True)
    wheel.write_bytes(b"wheel")

    monkeypatch.setattr(updater, "_run_checked", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("validation failed")))

    with pytest.raises(ValueError, match="validation failed"):
        updater._promote(run, target, candidate, wheel, "0.4.0")

    assert (target / "marker").read_text(encoding="utf-8") == "old"
    assert not candidate.exists()


def test_check_mode_never_runs_pip(monkeypatch, tmp_path):
    wheel_name = "huntos-0.4.0-py3-none-any.whl"
    wheel_bytes = b"verified-wheel"
    digest = hashlib.sha256(wheel_bytes).hexdigest()
    manifest = f"{digest}  {wheel_name}\n"

    def fake_download(url, destination):
        if url.endswith("SHA256SUMS"):
            destination.write_text(manifest, encoding="utf-8")
        else:
            destination.write_bytes(wheel_bytes)

    monkeypatch.setattr(updater, "_download", fake_download)
    monkeypatch.setattr(updater.subprocess, "run", lambda *args, **kwargs: pytest.fail("pip must not run"))

    assert updater.update("0.4.0", check=True) == 0
