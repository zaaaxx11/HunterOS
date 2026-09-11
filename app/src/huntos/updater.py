"""Download and install a verified HUNT-OS release wheel."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_REPO = "zaaaxx11/Hunter"
WHEEL_RE = re.compile(r"^huntos-(?P<version>[A-Za-z0-9][A-Za-z0-9._-]*?)-(?P<tags>[^/]+)\.whl$")


def _release_base(version: str | None) -> str:
    override = os.environ.get("HUNTOS_BASE_URL")
    if override:
        return override.rstrip("/")
    repo = os.environ.get("HUNTOS_REPO", DEFAULT_REPO)
    requested = (version or os.environ.get("HUNTOS_VERSION", "")).strip()
    if requested and requested.lower() != "latest":
        return f"https://github.com/{repo}/releases/download/v{requested.lstrip('v')}"
    return f"https://github.com/{repo}/releases/latest/download"


def _download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "huntos-updater"})
    with urlopen(request, timeout=30) as response, destination.open("wb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)


def _manifest_entry(manifest: str, requested_version: str | None) -> tuple[str, str]:
    entries: list[tuple[str, str]] = []
    for line in manifest.splitlines():
        fields = line.strip().split()
        if len(fields) < 2:
            continue
        digest, name = fields[0].lower(), fields[-1].lstrip("*")
        match = WHEEL_RE.fullmatch(Path(name).name)
        if match and re.fullmatch(r"[0-9a-f]{64}", digest):
            entries.append((name, digest))
    requested = (requested_version or "").lstrip("v")
    if requested and requested.lower() != "latest":
        entries = [entry for entry in entries if WHEEL_RE.fullmatch(entry[0]).group("version") == requested]
    if not entries:
        raise ValueError("SHA256SUMS does not list a valid canonical HUNT-OS wheel")
    if len(entries) > 1:
        raise ValueError("SHA256SUMS lists multiple HUNT-OS wheels; set HUNTOS_VERSION to select one")
    return entries[0]


def _verified_release(version: str | None, directory: Path) -> tuple[Path, str, str]:
    base = _release_base(version)
    manifest_path = directory / "SHA256SUMS"
    wheel_path: Path | None = None
    try:
        _download(f"{base}/SHA256SUMS", manifest_path)
        name, expected = _manifest_entry(manifest_path.read_text(encoding="utf-8"), version)
        wheel_path = directory / Path(name).name
        _download(f"{base}/{Path(name).name}", wheel_path)
        actual = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"sha256 mismatch for {wheel_path.name}")
        return wheel_path, name, base
    except OSError as exc:
        raise ValueError(f"could not download release artifacts: {exc}") from exc


def update(version: str | None = None, check: bool = False) -> int:
    """Verify and optionally install one release; return the CLI exit code."""
    requested = version or os.environ.get("HUNTOS_VERSION") or "latest"
    with tempfile.TemporaryDirectory(prefix="huntos-update-") as temporary:
        wheel, name, base = _verified_release(requested, Path(temporary))
        print(f"verified {name} from {base}")
        if check:
            return 0
        command = [
            sys.executable,
            "-m",
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "--no-input",
            "install",
            "--no-index",
            "--no-deps",
            "--force-reinstall",
            str(wheel),
        ]
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            raise ValueError(f"pip failed while installing the verified wheel (exit {completed.returncode})")
    print("HUNT-OS updated successfully")
    return 0