#!/usr/bin/env python3
"""Generate the hunt-os plugin payload and the marketplace manifests at the repo root.

Write mode (default):  python scripts/build_plugin.py
Check mode:            python scripts/build_plugin.py --check
  Regenerates into a temp dir, diffs byte-for-byte against the committed
  skills/hunt-os payload, .claude-plugin/plugin.json and the two marketplace.json files, prints differing
  paths, exits 1 on drift, 0 when identical (prints OK).

Single source of truth for skills/roles/hooks is huntos.installer.build_plan("router"),
imported from app/src (PYTHONPATH is set in-process; no install needed).
Output is deterministic: sorted iteration, LF newlines, no timestamps.
Stdlib only.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_SRC = REPO / "app" / "src"
IDEA_DIR = APP_SRC / "huntos" / "_data" / "idea"
CLAIM_GATE_SRC = APP_SRC / "huntos" / "_data" / "bin" / "claim_gate.py"
PYPROJECT = REPO / "app" / "pyproject.toml"
PLUGIN_NAME = "hunt-os"
MARKET_NAME = "hunter-os"
PLUGIN_REL = Path(".")
MARKET_FILES = (REPO / "marketplace.json", REPO / ".claude-plugin" / "marketplace.json")

# Paths at the repo root that this generator owns. Everything else
# under the plugin (commands, hooks, .mcp.json) is hand-written source and is
# NOT regenerated or compared here.
CURATED_SKILL = "skills/hunt-os/SKILL.md"
GENERATED_PREFIXES = (
    "skills/hunt-os/",
    ".claude-plugin/plugin.json",
)


def read_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit("build_plugin: no version in app/pyproject.toml")
    return m.group(1)


def norm(text: str) -> bytes:
    return text.replace("\r\n", "\n").encode("utf-8")


def build_plan_payload() -> list[tuple[str, bytes, str, str]]:
    """Reuse huntos.installer.build_plan('router') as the single source of truth."""
    sys.path.insert(0, str(APP_SRC))
    try:
        from huntos import installer  # type: ignore
    finally:
        sys.path.pop(0)
    plan = installer.build_plan("router")
    return sorted(plan, key=lambda t: t[0])


def render_manifest(version: str) -> str:
    manifest = {
        "name": PLUGIN_NAME,
        "version": version,
        "description": (
            "HUNT-OS authorized security-assessment framework: RoE-gated hunt CLI, "
            "evidence ladder, and claim gate for Claude Code and ZCode."
        ),
        "author": {"name": "Mafaza Bagas"},
        "skills": "./skills",
        "commands": "./commands",
        "hooks": "./hooks/hooks.json",
        "mcpServers": ".mcp.json",
    }
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def render_marketplace(version: str) -> str:
    market = {
        "name": MARKET_NAME,
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": ".",
                "version": version,
                "description": (
                    "HUNT-OS authorized security-assessment framework with RoE gating "
                    "and claim-gate enforcement."
                ),
                "category": "security",
            }
        ],
    }
    return json.dumps(market, indent=2, ensure_ascii=False) + "\n"


def generate(out_root: Path) -> dict[str, bytes]:
    """Return {relpath-under-out_root: bytes} for the whole generated set."""
    version = read_version()
    files: dict[str, bytes] = {}

    # 1. Skill payload from the installer plan, prefix stripped.
    for rel, data, _src, _sha in build_plan_payload():
        if not rel.startswith("hunt-os/"):
            raise SystemExit(f"build_plugin: unexpected plan path {rel!r}")
        inner = rel[len("hunt-os/"):]
        if inner == "SKILL.md":
            continue
        files[f"skills/hunt-os/{inner}"] = norm_checkout(data)

    # 2. Claim gate copied byte-for-byte (sha256 recorded in the plan too).


    # 4. Manifest and marketplace.
    files[".claude-plugin/plugin.json"] = norm(render_manifest(version))
    market_bytes = norm(render_marketplace(version))
    files["marketplace.json"] = market_bytes
    files[".claude-plugin/marketplace.json"] = market_bytes
    return files


def write_tree(files: dict[str, bytes], root: Path) -> None:
    for rel, data in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def norm_checkout(data: bytes) -> bytes:
    """Undo core.autocrlf checkouts so the drift check is OS-independent."""
    return data.replace(b"\r\n", b"\n")


def committed_files(root: Path) -> dict[str, bytes]:
    """The committed files this generator owns (stale files under owned prefixes count as drift)."""
    out: dict[str, bytes] = {}
    base = root / PLUGIN_REL
    if base.exists():
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(base).as_posix()
            if rel == CURATED_SKILL:
                continue
            if rel.startswith(GENERATED_PREFIXES) or rel in GENERATED_PREFIXES:
                out[rel] = norm_checkout(path.read_bytes())
    for mk in MARKET_FILES:
        rel = mk.relative_to(REPO).as_posix()
        if mk.exists():
            out[rel] = norm_checkout(mk.read_bytes())
    return out


def check() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        expected = generate(Path(tmp))
    actual = committed_files(REPO)
    drift: list[str] = []
    for rel in sorted(set(expected) | set(actual)):
        want = expected.get(rel)
        got = actual.get(rel)
        if want != got:
            drift.append(rel)
            if want is not None and got is not None:
                diff = difflib.unified_diff(
                    got.decode("utf-8", "replace").splitlines(keepends=True),
                    want.decode("utf-8", "replace").splitlines(keepends=True),
                    fromfile=f"committed/{rel}",
                    tofile=f"generated/{rel}",
                    n=1,
                )
                sys.stdout.writelines(list(diff)[:20])
    if drift:
        print("DRIFT:")
        for rel in drift:
            print(f"  {rel}")
        print("run: python scripts/build_plugin.py")
        return 1
    print("OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="fail on drift; do not write")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    files = generate(REPO)
    # Clear the generated skill payload so removed skills do not linger.
    skill_dir = REPO / PLUGIN_REL / "skills" / "hunt-os"
    for stale in (skill_dir / "skills", skill_dir / "roles", skill_dir / "hooks"):
        if stale.exists():
            shutil.rmtree(stale)
    write_tree(files, REPO)
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
