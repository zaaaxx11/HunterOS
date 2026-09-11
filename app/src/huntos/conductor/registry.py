"""Explicit, atomic registry for external HUNT-ADAPTER/1 executables."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from huntos.core.db import assert_no_secrets

from .jsonl_adapter import JsonlAdapter

DEFAULT_REGISTRY_PATH = Path.home() / ".huntos" / "adapters.json"


def configured_registry_path() -> Path:
    """Return the explicit test/automation override or the user registry."""
    override = os.environ.get("HUNT_ADAPTER_REGISTRY")
    return Path(override).expanduser() if override else DEFAULT_REGISTRY_PATH
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_SCHEMA = 1


def _registry_path(path: Path | None) -> Path:
    return Path(path).expanduser() if path is not None else configured_registry_path()


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError("BLOCKED: adapter name must match [A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
    if name.lower() == "mock":
        raise ValueError("BLOCKED: adapter name 'mock' is reserved")
    return name


def _validate_entry(entry) -> dict:
    if not isinstance(entry, dict) or set(entry) != {"name", "executable", "args"}:
        raise ValueError("BLOCKED: adapter registry entry has unknown schema")
    name = _validate_name(entry["name"])
    executable = entry["executable"]
    args = entry["args"]
    if not isinstance(executable, str) or not Path(executable).is_absolute():
        raise ValueError("BLOCKED: adapter executable must be an absolute path")
    if not Path(executable).is_file():
        raise ValueError(f"BLOCKED: adapter executable does not exist: {executable}")
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("BLOCKED: adapter args must be a list of strings")
    assert_no_secrets(executable, "adapter executable")
    for arg in args:
        assert_no_secrets(arg, "adapter argument")
    return {"name": name, "executable": executable, "args": list(args)}


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"BLOCKED: adapter registry is corrupt: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {"schema", "adapters"} or raw["schema"] != _SCHEMA or not isinstance(raw["adapters"], list):
        raise ValueError("BLOCKED: adapter registry has an unknown schema")
    entries = [_validate_entry(entry) for entry in raw["adapters"]]
    names = [entry["name"] for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError("BLOCKED: adapter registry contains duplicate names")
    return entries


def _write(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"schema": _SCHEMA, "adapters": entries},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp_name, 0o600)
        except OSError:
            pass
        os.replace(temp_name, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def add_adapter(name: str, executable: str, args: list[str] | None = None,
                path: Path | None = None) -> dict:
    registry_path = _registry_path(path)
    entry = _validate_entry({"name": name, "executable": executable, "args": args or []})
    entries = _load(registry_path)
    if any(item["name"] == entry["name"] for item in entries):
        raise ValueError(f"BLOCKED: adapter '{name}' is already registered")
    entries.append(entry)
    entries.sort(key=lambda item: item["name"].lower())
    _write(registry_path, entries)
    return dict(entry)


def list_adapters(path: Path | None = None) -> list[dict]:
    return [dict(entry) for entry in _load(_registry_path(path))]


def get_adapter(name: str, path: Path | None = None) -> dict | None:
    _validate_name(name)
    for entry in _load(_registry_path(path)):
        if entry["name"] == name:
            return dict(entry)
    return None


def remove_adapter(name: str, path: Path | None = None) -> bool:
    _validate_name(name)
    registry_path = _registry_path(path)
    entries = _load(registry_path)
    kept = [entry for entry in entries if entry["name"] != name]
    if len(kept) == len(entries):
        return False
    _write(registry_path, kept)
    return True


def build_registered_adapter(name: str, path: Path | None = None) -> JsonlAdapter:
    entry = get_adapter(name, path)
    if entry is None:
        raise ValueError(f"BLOCKED: adapter '{name}' is not registered")
    return JsonlAdapter(entry["executable"], entry["args"])
