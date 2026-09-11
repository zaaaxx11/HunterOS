"""HUNT-OS skills-layer installer.

Loads the HUNT-OS skills corpus (``huntos/_data/idea/skills``) into any
harness's native skills directory. Stdlib only -- this is product tooling, so
no third-party imports (CI enforces this).

Design law (plans.md P5): installation is ADDITIVE and namespaced. It never
overwrites a harness's own identity files; it only writes inside the target
skills directory. Before writing any file, a target path that already exists
AND is not recorded in a previous HUNT-OS manifest is refused (exit 1) unless
``--force`` is given.

Usage:
    python -m huntos.installer --adapter claude-code|zcode|hermes|generic
                               [--scope project|user]      # default: project
                               [--mode router|native]      # default: router
                               [--dir PATH]                # override base dir
                               [--force] [--check] [--uninstall]
    (identical surface through the CLI door: ``hunt install ...``)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 1.0.0: skills corpus + embedded bridge, manifest with per-file sha256 +
#        source_tree_hash. 1.1.0: manifest-tracked roles and POSIX hook pack.
# 1.2.0: cross-platform Python claim wrapper plus safe stale-path cleanup when
#        changing install modes or reinstalling a changed source tree.
# 1.3.0: the whole layer moved INTO the package (huntos/_data): the wheel is
#        self-contained, no checkout is needed to install. source_rel strings
#        and the source_tree_hash basis shift accordingly — a pre-1.3 install
#        reports one informational source-drift WARNING after `--check`; the
#        exit-code contract is unchanged and a re-install refreshes the tree.
SKILLS_VERSION = "1.3.0"

# The packaged idea layer. DATA_ROOT is the single base for every source the
# installer copies or embeds; it resolves inside the installed package, so an
# editable checkout and a wheel read the SAME bytes from the same relative
# layout. _data/attic is doctrine archive: tracked in git, never installed.
DATA_ROOT = Path(__file__).resolve().parent / "_data"
SKILLS_SRC = DATA_ROOT / "idea" / "skills"              # the corpus
BRIDGE_SRC = DATA_ROOT / "idea" / "HUNT-BRIDGE.md"
ROLES_SRC = DATA_ROOT / "roles"                         # the lane-role doctrine
GATE_SRC = DATA_ROOT / "bin" / "claim_gate.py"          # the mouth guard
HOOK_WRAPPER_SRC = DATA_ROOT / "hooks" / "claim_gate_wrapper.sh"
PY_HOOK_WRAPPER_SRC = DATA_ROOT / "hooks" / "claim_gate_wrapper.py"

MANIFEST_NAME = ".hunt-os-manifest.json"
ROUTER_DIR = "hunt-os"
CORPUS_DEST = "skills"                                  # nested inside ROUTER_DIR
ROLES_DEST = "roles"                                    # nested inside ROUTER_DIR
HOOKS_DEST = "hooks"                                    # nested inside ROUTER_DIR

# Law 5 (roles travel with the hunt layer): an engine that only has the
# installed skills tree must be able to read every lane role without the git
# checkout. These are the roles the installed layer MUST contain.
REQUIRED_ROLES = (
    "lane-runner", "architect", "red-teamer", "fuzz-engineer",
    "chainer", "adversary", "verifier",
)

# Subdirectories of a skill that travel with it in native mode.
SKILL_SUBDIRS = ("assets", "examples", "references", "scripts")

ADAPTER_BASE = {
    "claude-code": ".claude/skills",
    "zcode": ".zcode/skills",
}

ROUTER_NAME = "hunt-os"


def router_description() -> str:
    """Stable router prose with the current landed skill count."""
    return (
        "HUNT-OS hunting skills router - load during security, bug-bounty, "
        "web2/web3 audit, and offensive-recon work; routes into the HUNT-OS "
        f"hunting skills corpus ({len(collect_skill_dirs())} skills across the "
        "catalog) one skill at a time, on demand."
    )

HERMES_INSTRUCTION = """\
Hermes adapter: nothing to copy. Hermes loads the idea layer directly from
the package -- inject these files into every hunt session:

    huntos/_data/idea/skills/INDEX.md              (the router -- read FIRST)
    huntos/_data/idea/skills/<category>/<name>/SKILL.md   (on demand, one at a time)
    huntos/_data/idea/IDEA.md                      (the doctrine)
    huntos/_data/idea/HUNT-BRIDGE.md               (the hunt-ledger contract)

No files were written and none need to be."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _fail(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _within(base: Path, candidate: Path) -> bool:
    """True if candidate is base or lives under base."""
    try:
        candidate.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True


def _extract_section(text: str, heading: str) -> str:
    """Return the body of a '## <heading>' section (heading line included)."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


# --------------------------------------------------------------------------
# source corpus
# --------------------------------------------------------------------------

def _is_skipped(path: Path) -> bool:
    return "__pycache__" in path.parts


def _iter_files(root: Path):
    """Yield every file under root (sorted), skipping __pycache__."""
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and not _is_skipped(path):
            yield path


def collect_corpus() -> "list[tuple[str, Path]]":
    """(posix relpath under _data/idea/skills, absolute source) for the corpus."""
    return [
        (p.relative_to(SKILLS_SRC).as_posix(), p) for p in _iter_files(SKILLS_SRC)
    ]


def collect_skill_dirs() -> "list[tuple[str, Path]]":
    """(category, skill dir) for every landed skill folder with a SKILL.md."""
    out = []
    if not SKILLS_SRC.is_dir():
        return out
    for cat in sorted(p for p in SKILLS_SRC.iterdir() if p.is_dir()):
        for d in sorted(p for p in cat.iterdir() if p.is_dir()):
            if d.name == "__pycache__":
                continue
            if (d / "SKILL.md").is_file():
                out.append((cat.name, d))
    return out


def collect_bridge() -> "tuple[str, bytes]":
    rel = BRIDGE_SRC.relative_to(DATA_ROOT).as_posix()
    return rel, BRIDGE_SRC.read_bytes()


def source_fingerprint(entries: "list[tuple[str, str]]") -> str:
    """sha256 over the sorted 'relpath:sha256' lines of every source file."""
    lines = sorted(f"{rel}:{sha}" for rel, sha in entries)
    return _sha256_bytes("\n".join(lines).encode("utf-8"))


def source_tree_hash() -> str:
    """sha256 over the sorted 'rel:sha256' lines of every SOURCE file the
    installer copies or embeds -- the whole idea/skills corpus, the role
    doctrine (roles/), HUNT-BRIDGE.md, the claim gate, and the hook
    wrapper -- not just the files a given mode copies. Any of those added,
    edited, or REMOVED after an install changes this hash. Recorded in the
    manifest at install time; ``--check`` recomputes it to report source
    drift (informational only: installed-file drift stays the sole exit-1
    condition).
    """
    entries = [(rel, _sha256_file(path)) for rel, path in _source_files()]
    return source_fingerprint(entries)


def _source_files() -> "list[tuple[str, Path]]":
    """(posix relpath, absolute path) for every source file the installer
    copies or embeds into the installed layer."""
    files = list(collect_corpus())
    files.append((BRIDGE_SRC.relative_to(DATA_ROOT).as_posix(), BRIDGE_SRC))
    files.extend(
        (p.relative_to(DATA_ROOT).as_posix(), p) for p in _iter_files(ROLES_SRC)
    )
    for extra in (GATE_SRC, HOOK_WRAPPER_SRC, PY_HOOK_WRAPPER_SRC):
        if extra.is_file():
            files.append((extra.relative_to(DATA_ROOT).as_posix(), extra))
    return files


# --------------------------------------------------------------------------
# the router SKILL.md
# --------------------------------------------------------------------------

def _router_skill_md(mode: str) -> str:
    bridge_rel, bridge_bytes = collect_bridge()
    bridge_text = bridge_bytes.decode("utf-8")
    one_rule = _extract_section(bridge_text, "THE ONE RULE")
    index_text = (SKILLS_SRC / "INDEX.md").read_text(encoding="utf-8")

    parts = [
        "---",
        f"name: {ROUTER_NAME}",
        f"description: {router_description()}",
        "---",
        "",
        "# HUNT-OS - hunting skills router",
        "",
        f"Installed by HUNT-OS v{SKILLS_VERSION} ({mode} mode).",
    ]
    if mode == "native":
        parts += [
            "",
            "NATIVE MODE: every skill is ALSO installed as its own"
            " `hunt-<category>-<name>` skill directory. Prefer loading those"
            " individual skills directly; this router remains the map and the"
            " contract.",
        ]
    parts += [
        "",
        # _extract_section keeps the "## THE ONE RULE" heading itself
        one_rule if one_rule else (
            "## THE ONE RULE\n\n"
            "The database is the only ledger. Everything you find, claim,"
            " climb, or report MUST go through the hunt CLI."
        ),
        "",
        "## WHO OWNS THE LOOP",
        "",
        "Before running any hunt loop yourself (spawning lanes, opening a"
        " wave, re-auditing), ask the ledger: `hunt status`. If there is a"
        " conductor session with status RUNNING, HUNT-OS is the orchestrator"
        " — you are a judgment service. Execute ONLY the attempt you were"
        " given, never spawn lanes or open waves. If no such session exists,"
        " this layer runs solo and you follow the bridge and lane-runner"
        " doctrine yourself. One owner per session: the answer always comes"
        " from the ledger, never from guessing which doctrine was loaded.",
        "",
        "## SKILLS INDEX (read first, load on demand)",
        "",
        index_text.strip(),
        "",
        "## HUNT-BRIDGE - the hunt-ledger contract",
        "",
        f"(source: `huntos/_data/{bridge_rel}`)",
        "",
        bridge_text.strip(),
        "",
        "## WHERE THE SKILL BODIES LIVE",
        "",
        f"Skill bodies live at `{CORPUS_DEST}/<category>/<name>/SKILL.md`,"
        " relative to this SKILL.md file. Never bulk-load them: pick the"
        " category from the index above, then read the one skill the lane"
        " needs.",
        "",
        "## ROLE DOCTRINE (installed paths - read roles from HERE)",
        "",
        "The lane roles travel with this installed layer (law: roles travel"
        " with the hunt layer). lane-runner, architect, red-teamer,"
        " fuzz-engineer, chainer, adversary, and verifier live at"
        f" `{ROLES_DEST}/<name>.md`, relative to this SKILL.md file. When"
        " HUNT-BRIDGE (embedded above) points at `huntos/_data/roles/...`,"
        " the packaged location for idea-injected harnesses -- in THIS"
        f" installed layer read `{ROLES_DEST}/lane-runner.md` (and the other"
        " roles) from beside this file, without the package checkout.",
        "",
    ]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# install plan: every file we intend to write, as (posix rel, bytes)
# --------------------------------------------------------------------------

def build_plan(mode: str) -> "list[tuple[str, bytes, str, str]]":
    """Return (dest_rel, content, source_rel, source_sha) tuples.

    source_rel is the repo-relative path of the copied source (empty for
    generated files, which are excluded from the source fingerprint).
    """
    plan: "list[tuple[str, bytes, str, str]]" = []
    fingerprint_entries: "list[tuple[str, str]]" = []

    # corpus -> nested under hunt-os/skills/ (both modes: the router carries it)
    corpus = collect_corpus()
    for rel, src in corpus:
        data = src.read_bytes()
        plan.append((f"{ROUTER_DIR}/{CORPUS_DEST}/{rel}", data,
                     f"idea/skills/{rel}", _sha256_bytes(data)))

    # role doctrine -> hunt-os/roles/ (both modes, law 5: roles travel with
    # the layer, so an engine with only the installed tree can read them)
    for src in sorted(ROLES_SRC.glob("*.md")):
        data = src.read_bytes()
        plan.append((f"{ROUTER_DIR}/{ROLES_DEST}/{src.name}", data,
                     src.relative_to(DATA_ROOT).as_posix(),
                     _sha256_bytes(data)))

    # hook pack -> hunt-os/hooks/ (both modes): POSIX and cross-platform Python
    # wrappers plus the gate BYTE-COPIED at install time, all manifest-tracked.
    for src, dest_name in (
            (HOOK_WRAPPER_SRC, "claim_gate_wrapper.sh"),
            (PY_HOOK_WRAPPER_SRC, "claim_gate_wrapper.py"),
            (GATE_SRC, "claim_gate.py")):
        data = src.read_bytes()
        plan.append((f"{ROUTER_DIR}/{HOOKS_DEST}/{dest_name}", data,
                     src.relative_to(DATA_ROOT).as_posix(),
                     _sha256_bytes(data)))

    # generated router SKILL.md (not a copied source -> not fingerprinted)
    plan.append((f"{ROUTER_DIR}/SKILL.md",
                 _router_skill_md(mode).encode("utf-8"), "", ""))

    # native mode: one namespaced skill dir per landed skill
    if mode == "native":
        for cat, skill_dir in collect_skill_dirs():
            dest_root = f"hunt-{cat}-{skill_dir.name}"
            # SKILL.md (frontmatter intact) ...
            skill_md = skill_dir / "SKILL.md"
            data = skill_md.read_bytes()
            plan.append((f"{dest_root}/SKILL.md", data,
                         skill_md.relative_to(DATA_ROOT).as_posix(),
                         _sha256_bytes(data)))
            # ... plus its optional content subdirs
            for sub in SKILL_SUBDIRS:
                sub_dir = skill_dir / sub
                for src in _iter_files(sub_dir):
                    rel = src.relative_to(skill_dir).as_posix()
                    data = src.read_bytes()
                    plan.append((f"{dest_root}/{rel}", data,
                                 src.relative_to(DATA_ROOT).as_posix(),
                                 _sha256_bytes(data)))

    return plan


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------

def _manifest_path(skills_dir: Path) -> Path:
    return skills_dir / MANIFEST_NAME


def _load_manifest(skills_dir: Path) -> "dict | None":
    path = _manifest_path(skills_dir)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _previous_paths(skills_dir: Path) -> "set[str]":
    manifest = _load_manifest(skills_dir)
    if not manifest:
        return set()
    return {f.get("path", "") for f in manifest.get("files", [])}


def _remove_empty_dirs(skills_dir: Path) -> None:
    """Remove empty descendants without crossing the install boundary."""
    if not skills_dir.is_dir():
        return
    dirs = sorted(
        (d for d in skills_dir.rglob("*") if d.is_dir()),
        key=lambda d: len(d.parts), reverse=True,
    )
    for directory in dirs:
        try:
            if _within(skills_dir, directory) and not any(directory.iterdir()):
                directory.rmdir()
        except OSError:
            pass


def _remove_clean_manifest_paths(
        skills_dir: Path, entries: "list[dict]",
        *, excluding: "set[str] | None" = None) -> "tuple[int, list[str]]":
    """Remove only paths whose bytes still match their manifest hash.

    Operator-modified and malformed/out-of-bound entries are retained. This is
    used by mode transitions and uninstall so a manifest never grants a future
    install permission to destroy changed operator content.
    """
    excluding = excluding or set()
    removed = 0
    retained: "list[str]" = []
    for entry in entries:
        rel = entry.get("path", "")
        target = skills_dir / rel
        if not rel or rel in excluding or not _within(skills_dir, target):
            continue
        if not target.exists():
            continue
        if (not target.is_file()
                or _sha256_file(target) != entry.get("sha256")):
            retained.append(rel)
            continue
        target.unlink()
        removed += 1
    _remove_empty_dirs(skills_dir)
    return removed, retained


def _write_manifest(skills_dir: Path, adapter: str, mode: str, scope: str,
                    landed: "list[tuple[str, bytes]]",
                    fingerprint: str) -> Path:
    manifest = {
        "version": SKILLS_VERSION,
        "adapter": adapter,
        "mode": mode,
        "scope": scope,
        "installed_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source_fingerprint": fingerprint,
        "source_tree_hash": source_tree_hash(),
        "files": [
            {"path": rel, "sha256": _sha256_bytes(data)}
            for rel, data in sorted(landed)
        ],
    }
    path = _manifest_path(skills_dir)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def resolve_skills_dir(adapter: str, scope: str, dir_override: "str | None") -> Path:
    if dir_override:
        return Path(dir_override)
    base = ADAPTER_BASE.get(adapter)
    if base is None:  # generic without --dir is rejected by the parser
        _fail(f"adapter {adapter!r} requires --dir")
    if scope == "user":
        return Path.home() / base
    return Path.cwd() / base


def cmd_install(args: argparse.Namespace) -> int:
    skills_dir = resolve_skills_dir(args.adapter, args.scope, args.dir)
    if skills_dir.exists() and not skills_dir.is_dir():
        _fail(f"target skills dir path exists but is a file: {skills_dir}")
    if not SKILLS_SRC.is_dir():
        _fail(f"skills corpus not found at {SKILLS_SRC}")
    if not BRIDGE_SRC.is_file():
        _fail(f"bridge contract not found at {BRIDGE_SRC}")

    # Law 5 + hook pack: the installed layout PROMISES hunt-os/roles/ (all
    # seven roles) and hunt-os/hooks/ (wrapper + gate). A broken source
    # workspace must fail the install, not ship a layer missing its doctrine
    # or its mouth guard.
    missing_roles = [r for r in REQUIRED_ROLES if not (ROLES_SRC / f"{r}.md").is_file()]
    if missing_roles:
        _fail(f"role doctrine incomplete at {ROLES_SRC}: missing "
              f"{', '.join(missing_roles)}")
    if not GATE_SRC.is_file():
        _fail(f"claim gate not found at {GATE_SRC}")
    if not HOOK_WRAPPER_SRC.is_file():
        _fail(f"hook wrapper not found at {HOOK_WRAPPER_SRC}")
    if not PY_HOOK_WRAPPER_SRC.is_file():
        _fail(f"Python hook wrapper not found at {PY_HOOK_WRAPPER_SRC}")

    plan = build_plan(args.mode)

    # ADDITIVE LAW: refuse to touch anything that is not ours.
    old_manifest = _load_manifest(skills_dir)
    previous = _previous_paths(skills_dir)
    conflicts = [
        rel for rel, _data, _srel, _sha in plan
        if (skills_dir / rel).exists() and rel not in previous
    ]
    if conflicts and not args.force:
        _fail(
            "refusing to overwrite files not installed by HUNT-OS "
            f"(re-run with --force to overwrite): {', '.join(conflicts[:10])}"
            + (f" ... and {len(conflicts) - 10} more" if len(conflicts) > 10 else "")
        )

    landed: "list[tuple[str, bytes]]" = []
    for rel, data, _srel, _sha in plan:
        target = skills_dir / rel
        if not _within(skills_dir, target):
            _fail(f"refusing to write outside the skills dir: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if rel.endswith(".sh"):
            # the hook wrapper must be RUNNABLE as installed (doctor's
            # hook-wrapper check asserts the executable bit on POSIX); mode
            # is not part of the manifest hash, so --check stays clean.
            try:
                target.chmod(0o755)
            except OSError:
                pass  # best-effort on filesystems/platforms without exec bits
        landed.append((rel, data))

    # A router/native transition may leave old manifest-owned native paths that
    # are absent from the new plan. Remove only byte-identical old files; retain
    # operator-modified paths and report them rather than deleting them.
    new_paths = {rel for rel, _data, _srel, _sha in plan}
    retained_stale: "list[str]" = []
    if old_manifest:
        _removed, retained_stale = _remove_clean_manifest_paths(
            skills_dir, old_manifest.get("files", []), excluding=new_paths)

    fingerprint_entries = [
        (srel, sha) for _rel, _data, srel, sha in plan if srel
    ]
    manifest_path = _write_manifest(
        skills_dir, args.adapter, args.mode, args.scope, landed,
        source_fingerprint(fingerprint_entries),
    )

    print(
        f"HUNT-OS v{SKILLS_VERSION} installed: {len(landed)} files "
        f"({args.mode} mode, {args.adapter}, {args.scope} scope) -> {skills_dir}"
    )
    print(f"manifest: {manifest_path}")
    if retained_stale:
        print(
            "WARNING: retained modified stale manifest paths: "
            + ", ".join(retained_stale[:10])
            + (f" ... and {len(retained_stale) - 10} more"
               if len(retained_stale) > 10 else "")
        )
    return 0


def _warn_source_drift(manifest: dict) -> None:
    """Print a warning when the source corpus changed since the install.

    Informational only -- never changes the exit code. The installed files
    may still be exactly what the manifest recorded while the SOURCE moved on
    (a skill added, edited, or removed), leaving the installed tree a stale
    superset; re-installing refreshes it. Manifests written before this field
    existed (and a missing source, e.g. checking an install on another
    machine) are skipped silently.
    """
    recorded = manifest.get("source_tree_hash")
    if not recorded or not SKILLS_SRC.is_dir():
        return
    if source_tree_hash() != recorded:
        print("WARNING: source changed since install (re-install to refresh)")


def cmd_check(args: argparse.Namespace) -> int:
    skills_dir = resolve_skills_dir(args.adapter, args.scope, args.dir)
    manifest = _load_manifest(skills_dir)
    if not manifest:
        _fail(f"no {MANIFEST_NAME} in {skills_dir} - nothing to check")

    missing, modified = [], []
    files = manifest.get("files", [])
    for entry in files:
        rel = entry.get("path", "")
        target = skills_dir / rel
        if not _within(skills_dir, target):
            modified.append(f"{rel} (outside skills dir)")
            continue
        if not target.is_file():
            missing.append(rel)
        elif _sha256_file(target) != entry.get("sha256"):
            modified.append(rel)

    total = len(files)
    if missing or modified:
        for rel in missing:
            print(f"MISSING: {rel}")
        for rel in modified:
            print(f"MODIFIED: {rel}")
        print(
            f"check FAILED: {len(missing)} missing, {len(modified)} modified "
            f"of {total} files in {skills_dir}"
        )
        _warn_source_drift(manifest)
        return 1
    print(f"check OK: {total} files verified clean in {skills_dir}")
    _warn_source_drift(manifest)
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    skills_dir = resolve_skills_dir(args.adapter, args.scope, args.dir)
    manifest = _load_manifest(skills_dir)
    if not manifest:
        _fail(f"no {MANIFEST_NAME} in {skills_dir} - refusing to uninstall")

    files = manifest.get("files", [])
    removed, retained = _remove_clean_manifest_paths(skills_dir, files)

    manifest_path = _manifest_path(skills_dir)
    if manifest_path.is_file():
        manifest_path.unlink()
        removed += 1

    if skills_dir.is_dir() and not any(skills_dir.iterdir()):
        try:
            skills_dir.rmdir()
        except OSError:
            pass

    print(f"HUNT-OS uninstalled: {removed} files removed from {skills_dir}")
    if retained:
        print(
            "WARNING: retained modified manifest paths: "
            + ", ".join(retained[:10])
            + (f" ... and {len(retained) - 10} more" if len(retained) > 10 else "")
        )
    return 0


def cmd_hermes(args: argparse.Namespace) -> int:
    if args.check:
        print("hermes adapter: nothing installed on disk, nothing to check.")
        return 0
    if args.uninstall:
        print("hermes adapter: nothing installed on disk, nothing to uninstall.")
        return 0
    print(HERMES_INSTRUCTION)
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m huntos.installer",
        description=(
            "Install the HUNT-OS idea layer (huntos/_data) into a harness's "
            "native skills directory. ADDITIVE and namespaced: only writes "
            "inside the target skills dir, never overwrites foreign files "
            "(unless --force)."
        ),
    )
    parser.add_argument(
        "--adapter", required=True,
        choices=("claude-code", "zcode", "hermes", "generic"),
        help="target harness adapter (hermes = no-op soul-injection pointer; "
             "generic requires --dir)",
    )
    parser.add_argument(
        "--scope", choices=("project", "user"), default="project",
        help="project (<cwd>/.<adapter>/skills) or user (~/.<adapter>/skills); "
             "default: project",
    )
    parser.add_argument(
        "--mode", choices=("router", "native"), default="router",
        help="router = one 'hunt-os' skill with the full corpus nested inside "
             "(default); native = one hunt-<category>-<name> skill per skill "
             "PLUS the router",
    )
    parser.add_argument(
        "--dir", default=None,
        help="override the base skills dir (works for every adapter; "
             "required for generic)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="overwrite existing files even if they are not in a previous "
             "HUNT-OS manifest",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="verify every manifest file hash; exit 1 on drift. A change in "
             "the source corpus since install is reported as a WARNING line "
             "only (exit code unchanged)",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="remove exactly the manifest's files (and now-empty dirs)",
    )
    return parser


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)

    if args.adapter == "hermes":
        return cmd_hermes(args)

    if args.adapter == "generic" and not args.dir:
        _fail("--adapter generic requires --dir")

    if args.check:
        return cmd_check(args)
    if args.uninstall:
        return cmd_uninstall(args)
    return cmd_install(args)


if __name__ == "__main__":
    raise SystemExit(main())
