"""End-to-end install proof for EVERY harness adapter, plus hooks.json health.

The `hermes` adapter was exercised by hand (install 252 files, uninstall
clean, MCP tools callable). This module proves the SAME full lifecycle for
all six entries in ``huntos.installer.HARNESS_ADAPTERS`` -- including the
five that only had unit coverage before -- and proves the hand-written
``hooks/hooks.json`` is well-formed and points at scripts that exist.

Hermetic by construction: no subprocesses, no network, no yaml dependency
(the frontmatter parser below is hand-rolled), stdlib + pytest only.

Lifecycle proven per adapter (one parametrized case each):

  1. project scope resolves inside ``tmp_path`` (``monkeypatch.chdir``);
     ``generic`` has no conventional location and is handed ``--dir``.
  2. install returns 0.
  3. the resolved destination exists and carries the router skill.
  4. the manifest exists, parses as JSON, and lists a non-empty file set.
  5. the SKILL.md frontmatter matches the adapter's dialect: strict loaders
     (hermes/codex/opencode/generic) get version/author/license/platforms/
     metadata; claude-code/zcode get the plain name/description form and
     MUST NOT carry the strict fields.
  6. the installed claim gate is byte-identical to the packaged source.
  7. ``--check`` on that tree exits 0 and reports clean.
  8. ``--uninstall`` removes the tree and leaves no manifest behind.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from huntos.installer import (
    ADAPTER_BASE,
    FRONTMATTER_STRICT_ADAPTERS,
    HARNESS_ADAPTERS,
    ROUTER_NAME,
)

REPO = Path(__file__).resolve().parents[2]
GATE_SRC = REPO / "app" / "src" / "huntos" / "_data" / "bin" / "claim_gate.py"
MANIFEST_NAME = ".hunt-os-manifest.json"
HOOKS_DEST = "hooks"

# The strict-loader frontmatter contract (Hermes skill loader and friends).
STRICT_KEYS = ("version", "author", "license", "platforms", "metadata")
# The plain dialect Claude Code / ZCode discover a skill from.
PLAIN_KEYS = ("name", "description")

# Tokens that mean a --check run found drift rather than verifying clean.
DRIFT_TOKENS = ("MISSING", "MODIFIED", "FAILED", "DRIFT")


# --------------------------------------------------------------------------
# tiny hand-rolled frontmatter parser (no yaml dependency in this repo)
# --------------------------------------------------------------------------

def parse_frontmatter(text: str) -> "dict[str, str]":
    """Return the top-level ``key -> value`` map of a leading YAML-ish block.

    The file must open with a ``---`` fence; collection stops at the closing
    ``---``. Indented lines are skipped so a nested block (``metadata:`` with
    its ``  hermes:`` children) never masquerades as extra top-level keys.
    """
    lines = text.splitlines()
    assert lines, "SKILL.md is empty"
    assert lines[0].strip() == "---", (
        f"SKILL.md must open with a '---' frontmatter fence, got {lines[0]!r}"
    )
    fields: "dict[str, str]" = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip() or line[:1] in (" ", "\t"):
            continue  # nested block content, not a top-level key
        match = re.match(r"^([A-Za-z0-9_.\-]+):(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    raise AssertionError("unterminated frontmatter: no closing '---' fence")


# --------------------------------------------------------------------------
# A. per-adapter end-to-end install
# --------------------------------------------------------------------------

@pytest.mark.parametrize("adapter", sorted(HARNESS_ADAPTERS))
def test_adapter_installs_end_to_end(adapter, tmp_path, monkeypatch, capsys):
    """install -> layout -> frontmatter -> gate -> --check -> uninstall."""
    from huntos import installer

    needs_dir = HARNESS_ADAPTERS[adapter][1]
    # Project scope resolves to <cwd>/<adapter base>; `generic` has no
    # conventional location, so it is handed --dir explicitly.
    monkeypatch.chdir(tmp_path)
    if needs_dir:
        dest = tmp_path / "explicit-dir"
        argv = ["--adapter", adapter, "--dir", str(dest)]
    else:
        dest = tmp_path / ADAPTER_BASE[adapter]
        argv = ["--adapter", adapter]

    capsys.readouterr()

    # -- 2. install succeeds ------------------------------------------------
    assert installer.main(argv) == 0, f"{adapter}: install returned non-zero"
    out = capsys.readouterr().out
    assert f"{adapter}" in out, f"{adapter}: install did not name the adapter"

    # -- 3. destination + router skill --------------------------------------
    assert dest.is_dir(), f"{adapter}: destination {dest} was not created"
    skill = dest / ROUTER_NAME / "SKILL.md"
    assert skill.is_file(), f"{adapter}: no {ROUTER_NAME}/SKILL.md in {dest}"

    # the destination must be exactly what the installer's own resolver says
    # (generic has no conventional location: it only resolves through --dir)
    resolved = installer.resolve_skills_dir(
        adapter, "project", str(dest) if needs_dir else None)
    assert resolved == dest, (
        f"{adapter}: resolved destination {resolved} != install target {dest}"
    )

    # the corpus, the role doctrine and the hook pack travel with the router
    assert (dest / ROUTER_NAME / "skills" / "INDEX.md").is_file(), adapter
    assert (dest / ROUTER_NAME / "roles" / "lane-runner.md").is_file(), adapter
    assert (dest / ROUTER_NAME / HOOKS_DEST / "claim_gate.py").is_file(), adapter
    assert (dest / ROUTER_NAME / HOOKS_DEST / "claim_gate_wrapper.sh").is_file(), adapter
    assert (dest / ROUTER_NAME / HOOKS_DEST / "hunt_os_hook.py").is_file(), adapter

    # -- 4. manifest --------------------------------------------------------
    manifest_path = dest / MANIFEST_NAME
    assert manifest_path.is_file(), f"{adapter}: no {MANIFEST_NAME} in {dest}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict), f"{adapter}: manifest is not a JSON object"
    files = manifest.get("files")
    assert isinstance(files, list) and files, (
        f"{adapter}: manifest 'files' must be a non-empty list"
    )
    assert manifest.get("adapter") == adapter, (
        f"{adapter}: manifest records adapter {manifest.get('adapter')!r}"
    )
    # every manifest entry is a path + sha256 pair
    for entry in files:
        assert isinstance(entry, dict) and entry.get("path") and entry.get("sha256"), (
            f"{adapter}: malformed manifest entry {entry!r}"
        )
    # the router skill itself is manifest-tracked
    assert f"{ROUTER_NAME}/SKILL.md" in {e["path"] for e in files}, adapter

    # -- 5. frontmatter dialect --------------------------------------------
    fields = parse_frontmatter(skill.read_text(encoding="utf-8"))
    if adapter in FRONTMATTER_STRICT_ADAPTERS:
        for key in STRICT_KEYS:
            assert key in fields, (
                f"{adapter}: strict loader frontmatter is missing {key!r} "
                f"(got {sorted(fields)})"
            )
        assert fields["name"] == ROUTER_NAME, adapter
        assert fields["description"], f"{adapter}: empty router description"
    else:
        for key in PLAIN_KEYS:
            assert key in fields, (
                f"{adapter}: plain frontmatter is missing {key!r} "
                f"(got {sorted(fields)})"
            )
        for key in STRICT_KEYS:
            assert key not in fields, (
                f"{adapter}: plain dialect must NOT carry the strict field "
                f"{key!r} (got {sorted(fields)})"
            )

    # -- 6. the claim gate is byte-identical to the packaged source --------
    installed_gate = dest / ROUTER_NAME / HOOKS_DEST / "claim_gate.py"
    assert installed_gate.read_bytes() == GATE_SRC.read_bytes(), (
        f"{adapter}: installed claim_gate.py differs from "
        f"{GATE_SRC}"
    )

    # -- 7. --check reports clean ------------------------------------------
    capsys.readouterr()
    assert installer.main(argv + ["--check"]) == 0, (
        f"{adapter}: --check returned non-zero on a fresh install"
    )
    check_out = capsys.readouterr().out
    assert "check OK" in check_out, (
        f"{adapter}: --check did not report OK: {check_out!r}"
    )
    for token in DRIFT_TOKENS:
        assert token not in check_out, (
            f"{adapter}: --check reported {token}: {check_out!r}"
        )

    # -- 8. uninstall removes the tree and the manifest --------------------
    capsys.readouterr()
    assert installer.main(argv + ["--uninstall"]) == 0, (
        f"{adapter}: uninstall returned non-zero"
    )
    capsys.readouterr()
    assert not manifest_path.exists(), (
        f"{adapter}: {MANIFEST_NAME} survived uninstall"
    )
    assert not skill.exists(), f"{adapter}: router SKILL.md survived uninstall"
    assert not dest.exists() or not any(dest.iterdir()), (
        f"{adapter}: uninstall left content behind in {dest}: "
        f"{sorted(p.name for p in dest.rglob('*')) if dest.exists() else []}"
    )


def test_every_adapter_is_covered_by_the_parametrized_case():
    """The parametrization above is driven by the table, not a hardcoded list."""
    from huntos.installer import HARNESS_ADAPTERS as table

    assert set(table) == {
        "claude-code", "zcode", "hermes", "codex", "opencode", "generic",
    }
    # exactly one adapter needs --dir, and it is the one with no base dir
    needing = {name for name, (_base, needs) in table.items() if needs}
    assert needing == {"generic"}
    assert table["generic"][0] == ""
    # the strict set is a subset of the registered adapters
    assert set(FRONTMATTER_STRICT_ADAPTERS) <= set(table)


def test_native_mode_also_installs_for_a_strict_adapter(tmp_path, monkeypatch, capsys):
    """Native mode is a distinct build_plan branch: prove it lands too."""
    from huntos import installer

    monkeypatch.chdir(tmp_path)
    dest = tmp_path / ADAPTER_BASE["hermes"]
    capsys.readouterr()
    assert installer.main(["--adapter", "hermes", "--mode", "native"]) == 0
    capsys.readouterr()

    # the router is still there ...
    assert (dest / ROUTER_NAME / "SKILL.md").is_file()
    # ... plus one namespaced skill dir per landed skill
    native = sorted(
        p.name for p in dest.iterdir()
        if p.is_dir() and p.name.startswith("hunt-")
    )
    assert native, "native mode installed no per-skill directories"
    for name in native:
        assert (dest / name / "SKILL.md").is_file(), name

    assert installer.main(["--adapter", "hermes", "--mode", "native",
                           "--check"]) == 0
    capsys.readouterr()
    assert installer.main(["--adapter", "hermes", "--mode", "native",
                           "--uninstall"]) == 0
    capsys.readouterr()
    assert not dest.exists() or not any(dest.iterdir())


# --------------------------------------------------------------------------
# B. hooks.json well-formedness
# --------------------------------------------------------------------------

_PLUGIN_ROOT_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)")


def _referenced_scripts(command: str) -> "list[str]":
    """Repo-relative script paths a hook command points at.

    Prefers the ``${CLAUDE_PLUGIN_ROOT}/...`` form the plugin uses; falls
    back to the first token when it is itself a path (a bare
    ``scripts/foo.sh`` invocation).
    """
    found = _PLUGIN_ROOT_RE.findall(command)
    if found:
        return found
    tokens = command.strip().split()
    if tokens and ("/" in tokens[0] or tokens[0].endswith((".sh", ".py"))):
        return [tokens[0]]
    return []


def _event_groups(data: dict) -> "dict[str, list]":
    """Normalise a hooks.json document to ``{event: [entry, ...]}``.

    Accepts the Claude Code plugin envelope (``{"hooks": {event: [...]}}``)
    and the flat form (``{event: [...]}``) so the assertions below describe
    one shape regardless of which envelope a harness expects.
    """
    if set(data) == {"hooks"} and isinstance(data["hooks"], dict):
        return data["hooks"]
    return data


def assert_hooks_json_wellformed(path: Path, repo_root: Path) -> None:
    """Assert one hooks.json document is well-formed and fully resolvable."""
    assert path.is_file(), f"missing hooks document: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path}: top level must be a JSON object"

    groups = _event_groups(data)
    assert groups, f"{path}: no hook events declared"

    for event, entries in groups.items():
        assert isinstance(event, str) and event.strip(), f"{path}: bad event name"
        # every value is a list
        assert isinstance(entries, list), (
            f"{path}: event {event!r} must map to a list, got "
            f"{type(entries).__name__}"
        )
        # every entry in those lists is a dict
        for entry in entries:
            assert isinstance(entry, dict), (
                f"{path}: event {event!r} has a non-dict entry {entry!r}"
            )
            # each entry has a non-empty "hooks" list
            hooks = entry.get("hooks")
            assert isinstance(hooks, list), (
                f"{path}: event {event!r} entry has no 'hooks' list"
            )
            assert hooks, f"{path}: event {event!r} entry has an empty 'hooks' list"
            # each hook there has a "type" and a "command"
            for hook in hooks:
                assert isinstance(hook, dict), (
                    f"{path}: event {event!r} has a non-dict hook {hook!r}"
                )
                assert hook.get("type"), (
                    f"{path}: event {event!r} hook is missing 'type'"
                )
                command = hook.get("command")
                assert isinstance(command, str) and command.strip(), (
                    f"{path}: event {event!r} hook is missing 'command'"
                )
                # the referenced command scripts actually exist on disk
                scripts = _referenced_scripts(command)
                assert scripts, (
                    f"{path}: event {event!r} command has no resolvable script "
                    f"path: {command!r}"
                )
                for rel in scripts:
                    assert (repo_root / rel).is_file(), (
                        f"{path}: event {event!r} points at a missing script: "
                        f"{rel} (resolved against {repo_root})"
                    )


def _repo_root() -> Path:
    """The checkout root: the installed package's parents[3], with a fallback."""
    import huntos

    from_package = Path(huntos.__file__).resolve().parents[3]
    if (from_package / "hooks" / "hooks.json").is_file():
        return from_package
    return REPO


def test_repo_hooks_json_is_wellformed():
    """hooks/hooks.json parses, is shaped right, and every script exists."""
    root = _repo_root()
    assert_hooks_json_wellformed(root / "hooks" / "hooks.json", root)


def test_hooks_json_declares_the_four_contract_events():
    """The hook pack wires SessionStart, PreToolUse, PostToolUse and Stop."""
    root = _repo_root()
    data = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    events = set(_event_groups(data))
    assert {"SessionStart", "PreToolUse", "PostToolUse", "Stop"} <= events, (
        f"hooks.json is missing contract events; got {sorted(events)}"
    )
    # the Stop hook must reach the claim gate, not a stub
    stop = _event_groups(data)["Stop"]
    commands = [h["command"] for entry in stop for h in entry["hooks"]]
    assert any("claim-gate-stop" in c for c in commands), (
        f"Stop hook does not reach the claim gate: {commands}"
    )


def test_skills_tree_hook_pack_copy_matches_repo_root():
    """If a hooks.json copy ships under skills/hunt-os/hooks/, it is identical.

    The installer's hook pack (claim_gate.py, both wrappers, the universal
    4-point contract) is generated into that directory; a hooks.json copy is
    optional, so a missing file is recorded rather than failed here.
    """
    root = _repo_root()
    packaged = root / "skills" / ROUTER_NAME / HOOKS_DEST / "hooks.json"
    source = root / "hooks" / "hooks.json"
    if not packaged.is_file():
        pytest.skip(
            f"no hooks.json copy under skills/{ROUTER_NAME}/{HOOKS_DEST}/ "
            f"(only the repo-root document is shipped)"
        )
    assert_hooks_json_wellformed(packaged, root)
    assert packaged.read_bytes() == source.read_bytes(), (
        f"{packaged} drifted from {source}"
    )
