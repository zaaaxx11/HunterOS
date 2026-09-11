"""Download and transactionally install a verified HUNT-OS release wheel."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
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
        if match and match.group("tags") == "py3-none-any" and re.fullmatch(r"[0-9a-f]{64}", digest):
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


def _official_home() -> Path:
    configured = os.environ.get("HUNTOS_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".HunterOS").resolve()


def _installation_target() -> tuple[Path, Path]:
    prefix = Path(sys.prefix).resolve()
    home = _official_home()
    target = (home / "venv").resolve()
    if prefix != target:
        raise ValueError(
            f"self-update is supported only from the official HUNT-OS venv ({target}); "
            f"current interpreter is {sys.executable}. Use the release installer or pipx's own upgrade command."
        )
    if Path(sys.base_prefix).resolve() == prefix:
        raise ValueError("current interpreter is not a virtual environment; refusing to modify global Python")
    return home, target


def _run_checked(command: list[str], message: str) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise ValueError(f"{message} (exit {completed.returncode})")


def _validate(python: Path, expected_version: str | None = None) -> None:
    probe = "import huntos, sys; assert sys.prefix == sys.exec_prefix; assert huntos.__version__; "
    if expected_version:
        probe += f"assert huntos.__version__ == {expected_version!r}; "
    probe += "print(huntos.__version__)"
    _run_checked([str(python), "-c", probe], "candidate package validation failed")
    _run_checked([str(python), "-m", "huntos", "--help"], "candidate CLI validation failed")


def _stage(home: Path, wheel: Path, version: str | None) -> tuple[Path, Path]:
    run = home / ".staging" / f"update-{os.getpid()}-{next(tempfile._get_candidate_names())}"
    run.mkdir(parents=True, exist_ok=False)
    candidate = run / "venv"
    _run_checked([sys.executable, "-m", "venv", str(candidate)], "candidate venv creation failed")
    candidate_python = candidate / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run_checked(
        [str(candidate_python), "-m", "pip", "--isolated", "--disable-pip-version-check", "--no-input",
         "install", "--no-index", "--no-deps", str(wheel)],
        "verified wheel installation failed",
    )
    _validate(candidate_python, version)
    return run, candidate


def _promote(run: Path, target: Path, candidate: Path, wheel: Path, version: str | None) -> None:
    backup = run / "previous-venv"
    moved_old = False
    promoted = False
    try:
        if target.exists():
            target.replace(backup)
            moved_old = True
        candidate.replace(target)
        promoted = True
        final_python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _run_checked(
            [str(final_python), "-m", "pip", "--isolated", "--disable-pip-version-check", "--no-input",
             "install", "--no-index", "--no-deps", "--force-reinstall", str(wheel)],
            "final launcher repair failed",
        )
        _validate(final_python, version)
    except Exception:
        if promoted and target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if moved_old and backup.exists() and not target.exists():
            backup.replace(target)
        raise
    shutil.rmtree(backup, ignore_errors=True)
    shutil.rmtree(run, ignore_errors=True)


def _promote_after_exit(run: Path, target: Path, candidate: Path, wheel: Path, version: str | None) -> None:
    deadline = time.monotonic() + 30
    while True:
        try:
            _promote(run, target, candidate, wheel, version)
            return
        except (OSError, PermissionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)


def _helper_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="complete a staged HUNT-OS update")
    parser.add_argument("--promote", nargs=4, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    run, target, candidate, wheel = map(Path, args.promote)
    _promote_after_exit(run, target, candidate, wheel, args.version)
    return 0


def update(version: str | None = None, check: bool = False) -> int:
    """Verify and transactionally install a release into the official venv."""
    requested = version or os.environ.get("HUNTOS_VERSION") or "latest"
    current_version = __import__("huntos").__version__
    with tempfile.TemporaryDirectory(prefix="huntos-update-") as temporary:
        wheel, name, base = _verified_release(requested, Path(temporary))
        candidate_version = WHEEL_RE.fullmatch(name).group("version")
        print(f"current: {current_version}; candidate: {candidate_version}")
        print(f"verified {name} from {base}")
        if check:
            return 0
        home, target = _installation_target()
        run, candidate = _stage(home, wheel, candidate_version)
        staged_wheel = run / Path(wheel).name
        shutil.copy2(wheel, staged_wheel)
        if os.name == "nt":
            helper = run / "update-helper.py"
            shutil.copy2(Path(__file__), helper)
            base_python = Path(sys.base_prefix) / "python.exe"
            subprocess.Popen(
                [
                    str(base_python),
                    str(helper),
                    "--promote",
                    str(run),
                    str(target),
                    str(candidate),
                    str(staged_wheel),
                    "--version",
                    candidate_version,
                ],
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            print("HUNT-OS update staged; the new environment will activate after this command exits")
            return 0
        _promote(run, target, candidate, staged_wheel, candidate_version)
    print("HUNT-OS updated successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(_helper_main(sys.argv[1:]))
