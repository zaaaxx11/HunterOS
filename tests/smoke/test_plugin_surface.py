"""Structure contract for the Claude Code / ZCode plugin surface.

Cheap, stdlib-only checks that run in every CI job: manifest JSON is valid,
every declared path exists, the version matches the package, hooks point at
real scripts, and each slash command has a frontmatter description.
"""
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = REPO


def _json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_plugin_manifest_is_valid_and_named():
    manifest = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    assert manifest["name"] == "hunt-os"
    assert manifest["version"]


def test_plugin_version_matches_package():
    manifest = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    pyproject = (REPO / "app" / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{manifest["version"]}"' in pyproject


def test_declared_skill_and_command_paths_exist():
    manifest = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    assert (PLUGIN / manifest["skills"].removeprefix("./")).is_dir()
    assert (PLUGIN / manifest["commands"].removeprefix("./")).is_dir()
    assert (PLUGIN / manifest["hooks"].removeprefix("./")).is_file()
    assert (PLUGIN / manifest["mcpServers"].removeprefix("./")).is_file() if isinstance(
        manifest.get("mcpServers"), str
    ) else True


def test_marketplace_source_resolves_to_plugin_root():
    market = _json(REPO / "marketplace.json")
    entry = next(p for p in market["plugins"] if p["name"] == "hunt-os")
    assert (REPO / entry["source"]).resolve() == PLUGIN.resolve()
    assert _json(REPO / ".claude-plugin" / "marketplace.json") == market


def test_hooks_reference_existing_scripts():
    hooks = _json(PLUGIN / "hooks" / "hooks.json")["hooks"]
    for event, groups in hooks.items():
        for group in groups:
            for hook in group["hooks"]:
                match = re.search(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^"\s]+)', hook["command"])
                assert match, f"{event}: no plugin-relative script in {hook['command']}"
                assert (PLUGIN / match.group(1)).is_file(), match.group(1)


def test_mcp_config_points_at_server():
    mcp = _json(PLUGIN / ".mcp.json")
    server = mcp["mcpServers"]["hunter-os"]
    script = next(a for a in server["args"] if a.endswith("server.py"))
    assert (PLUGIN / script.replace("${CLAUDE_PLUGIN_ROOT}/", "")).is_file()


def test_every_command_has_a_description():
    commands = sorted((PLUGIN / "commands").glob("*.md"))
    names = {c.stem for c in commands}
    assert {"start", "status", "brief", "finding", "lead", "verify", "report", "triage"} <= names
    for command in commands:
        text = command.read_text(encoding="utf-8")
        assert text.startswith("---\n"), command.name
        assert re.search(r"^description:\s*\S", text, re.MULTILINE), command.name


def test_router_skill_has_frontmatter():
    text = (PLUGIN / "skills" / "hunt-os" / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"^name:\s*hunt-os\s*$", text, re.MULTILINE)
    assert re.search(r"^description:\s*\S", text, re.MULTILINE)
