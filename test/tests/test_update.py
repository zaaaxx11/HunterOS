import hashlib
from pathlib import Path

import pytest

from huntos import updater
from huntos.cli.main import main as cli_main


def test_manifest_selects_requested_canonical_wheel():
    digest = "a" * 64
    manifest = f"{digest}  huntos-0.4.0-py3-none-any.whl\n"

    assert updater._manifest_entry(manifest, "v0.4.0") == (
        "huntos-0.4.0-py3-none-any.whl",
        digest,
    )


def test_manifest_rejects_ambiguous_wheels():
    manifest = "\n".join(
        f"{'a' * 64}  huntos-{version}-py3-none-any.whl"
        for version in ("0.3.0", "0.4.0")
    )

    with pytest.raises(ValueError, match="multiple HUNT-OS wheels"):
        updater._manifest_entry(manifest, None)


def test_verified_release_rejects_checksum_mismatch(tmp_path, monkeypatch):
    wheel_name = "huntos-0.4.0-py3-none-any.whl"
    manifest = f"{'a' * 64}  {wheel_name}\n"

    def fake_download(url, destination):
        if url.endswith("SHA256SUMS"):
            destination.write_text(manifest, encoding="utf-8")
        else:
            destination.write_bytes(b"not-the-listed-wheel")

    monkeypatch.setattr(updater, "_download", fake_download)
    with pytest.raises(ValueError, match="sha256 mismatch"):
        updater._verified_release("0.4.0", tmp_path)


def test_check_mode_verifies_without_running_pip(tmp_path, monkeypatch, capsys):
    wheel = tmp_path / "huntos-0.4.0-py3-none-any.whl"
    wheel.write_bytes(b"verified-wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    manifest = f"{digest}  {wheel.name}\n"

    def fake_download(url, destination):
        if url.endswith("SHA256SUMS"):
            destination.write_text(manifest, encoding="utf-8")
        else:
            destination.write_bytes(wheel.read_bytes())

    monkeypatch.setattr(updater, "_download", fake_download)
    monkeypatch.setattr(updater.subprocess, "run", lambda *args, **kwargs: pytest.fail("pip must not run"))

    assert updater.update("0.4.0", check=True) == 0
    assert "verified huntos-0.4.0-py3-none-any.whl" in capsys.readouterr().out


def test_update_command_is_database_free(monkeypatch):
    called = {}

    def fake_update(version, check):
        called.update(version=version, check=check)
        return 0

    monkeypatch.setattr(updater, "update", fake_update)
    monkeypatch.setenv("HUNT_DB", str(Path("this-path-must-not-be-opened")))

    assert cli_main(["update", "--check"]) == 0
    assert called == {"version": None, "check": True}