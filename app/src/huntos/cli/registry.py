"""Single-source command registry for the HUNT-OS operator surface.

Phase 1 of the orchestrator CLI redesign: one table drives argparse
construction (main.py), shell completion/help (shell.py), and the grouped
``hunt help`` renderer.  This module must stay import-light: shell.py imports
it without importing the database kernel, so only stdlib + string constants
live here.  Syntax (verb names, action names, help strings) mirrors the
existing CLI exactly — the registry describes, never renames.
"""
from __future__ import annotations


# Pipeline groups for grouped help rendering (intake -> evidence -> leads ->
# waves -> report -> ops).  Every verb belongs to exactly one group.
GROUPS = (
    "intake",
    "evidence",
    "leads",
    "waves",
    "report",
    "ops",
)

# COMMAND_REGISTRY: verb -> metadata.  Fields:
#   group: one of GROUPS (for grouped help).
#   help: short help, identical to the argparse ``help=`` string.
#   actions: sub-action names in parser order (empty = leaf verb, no subparsers).
#   read_only: True when the verb never writes (mirrors READ_ONLY_COMMANDS).
#   no_db: True when the verb runs without opening the hunt db
#     (mirrors NO_DB_COMMANDS).
#   examples: copy-pasteable invocations shown by ``hunt help <verb>``.
#   next_hint: default NEXT suggestion used by the unified error formatter.
COMMAND_REGISTRY: dict[str, dict] = {
    "target": {
        "group": "intake",
        "help": "manage targets: add / list / roe / archive",
        "actions": ("prepare", "add", "list", "roe", "archive"),
        "read_only": False,
        "no_db": False,
        "examples": (
            "hunt target prepare https://example.com --name Demo --actions recon,read --authorization-note owner-approved",
            "hunt target list",
        ),
        "next_hint": "hunt target list",
    },
    "score": {
        "group": "intake",
        "help": "score a target's evidence (scoring phase only; ev must be > 0)",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt score 1 5",),
        "next_hint": "hunt score <id> <ev>",
    },
    "phase": {
        "group": "intake",
        "help": "advance the pipeline one phase (order + exit gates enforced)",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt phase 1 recon",),
        "next_hint": "hunt next --target <id>",
    },
    "finding": {
        "group": "evidence",
        "help": "the evidence ladder: add / promote / overturn / retitle",
        "actions": ("add", "promote", "overturn", "retitle"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt finding add 1 'weak auth' auth --severity high",),
        "next_hint": "hunt finding add <target> <title> <klass>",
    },
    "poc": {
        "group": "evidence",
        "help": "run a PoC inside the ledger (exit code + sha256 pinned; required before any promotion)",
        "actions": ("run",),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt poc run --id 1 --poc-path ./poc.py",),
        "next_hint": "hunt poc run --id <n> --poc-path <file>",
    },
    "verify": {
        "group": "evidence",
        "help": "record a verifier event on a finding (required before proven-live)",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt verify 1 tx_hash 0xabc",),
        "next_hint": "hunt verify <finding> <kind> <body>",
    },
    "challenge": {
        "group": "evidence",
        "help": "record an adversary review on a finding (required before proven-live)",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt challenge 1 'checked WAF bypass'",),
        "next_hint": "hunt challenge <finding> <notes>",
    },
    "artifact": {
        "group": "report",
        "help": "record a phase exit artifact (surface_map / attack_plan / disclosure_report)",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt artifact 1 surface_map ./surface.md",),
        "next_hint": "hunt artifact <target> <kind> <file>",
    },
    "wave": {
        "group": "waves",
        "help": "hunt waves: open / close / reaudit",
        "actions": ("open", "close", "reaudit"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt wave open 1 architect,red",),
        "next_hint": "hunt wave open <target> <lanes>",
    },
    "report": {
        "group": "report",
        "help": "generate the target's disclosure report (markdown, sha256-fingerprinted)",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt report 1 --out report.md",),
        "next_hint": "hunt report <target>",
    },
    "verify-report": {
        "group": "report",
        "help": "verify a report file against its hunt-report footer (BLOCKED on tampering)",
        "actions": (),
        "read_only": True,
        "no_db": False,
        "examples": ("hunt verify-report report.md",),
        "next_hint": "hunt verify-report <file>",
    },
    "project": {
        "group": "ops",
        "help": "workspace lock: bind this directory to the current db",
        "actions": ("bind", "status"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt project status",),
        "next_hint": "hunt project status",
    },
    "lesson": {
        "group": "report",
        "help": "lessons: add / list / reword (archive requires one bound to the target)",
        "actions": ("add", "list", "reword"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt lesson list",),
        "next_hint": "hunt lesson list",
    },
    "klass": {
        "group": "ops",
        "help": "the klass taxonomy: list / add (growth is retro-gated)",
        "actions": ("list", "add"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt klass list",),
        "next_hint": "hunt klass list",
    },
    "brief": {
        "group": "ops",
        "help": "opening read for the next hunt round (read-only)",
        "actions": (),
        "read_only": True,
        "no_db": False,
        "examples": ("hunt brief 1",),
        "next_hint": "hunt brief <target>",
    },
    "next": {
        "group": "ops",
        "help": "the ONE recommended next command for the hunt (read-only; never executes)",
        "actions": (),
        "read_only": True,
        "no_db": False,
        "examples": ("hunt next --target 1",),
        "next_hint": "hunt next",
    },
    "lead": {
        "group": "leads",
        "help": "the lead lifecycle: add / set-half / mutate / next / park / kill / promote / list",
        "actions": ("add", "set-half", "mutate", "set", "next", "park", "reopen", "kill", "promote", "list"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt lead list --target 1",),
        "next_hint": "hunt lead list --target <id>",
    },
    "oracle": {
        "group": "leads",
        "help": "deterministic observation oracle (baseline vs candidate feature JSON)",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt oracle --lead 1 --half trigger --baseline b.json --candidate c.json",),
        "next_hint": "hunt oracle --lead <n> --half trigger --baseline b.json --candidate c.json",
    },
    "surface": {
        "group": "leads",
        "help": "the attack-surface ledger: add / list",
        "actions": ("add", "list"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt surface list 1",),
        "next_hint": "hunt surface list <target>",
    },
    "coverage": {
        "group": "leads",
        "help": "per-surface lead/finding coverage + blind spots",
        "actions": (),
        "read_only": True,
        "no_db": False,
        "examples": ("hunt coverage 1",),
        "next_hint": "hunt coverage <target>",
    },
    "chain": {
        "group": "leads",
        "help": "the 0-day claim engine: add / link / show / novelty",
        "actions": ("add", "link", "show", "novelty"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt chain show 1",),
        "next_hint": "hunt chain show <id>",
    },
    "fuzz": {
        "group": "leads",
        "help": "fire the doctrine edge-case battery at one endpoint parameter",
        "actions": (),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt fuzz --url https://example.com/api --param q",),
        "next_hint": "hunt fuzz --url <url> --param <p>",
    },
    "status": {
        "group": "ops",
        "help": "the full ledger picture + contradiction report (read-only)",
        "actions": (),
        "read_only": True,
        "no_db": False,
        "examples": ("hunt status",),
        "next_hint": "hunt status",
    },
    "install": {
        "group": "ops",
        "help": "install the HUNT-OS skills layer into a harness",
        "actions": (),
        "read_only": False,
        "no_db": True,
        "examples": ("hunt install --adapter claude-code --check",),
        "next_hint": "hunt install --adapter claude-code --check",
    },
    "harness": {
        "group": "ops",
        "help": "list or diagnose built-in and explicitly registered harnesses",
        "actions": ("list", "doctor"),
        "read_only": False,
        "no_db": True,
        "examples": ("hunt harness list",),
        "next_hint": "hunt harness list",
    },
    "adapter": {
        "group": "ops",
        "help": "register and diagnose HUNT-ADAPTER/1 executables",
        "actions": ("add", "list", "doctor", "remove"),
        "read_only": False,
        "no_db": True,
        "examples": ("hunt adapter list",),
        "next_hint": "hunt adapter list",
    },
    "doctor": {
        "group": "ops",
        "help": "workspace preflight: cli, db, project lock, claim gate, skills layer, hook wrapper",
        "actions": (),
        "read_only": True,
        "no_db": True,
        "examples": ("hunt doctor",),
        "next_hint": "hunt doctor",
    },
    "run": {
        "group": "waves",
        "help": "the conductor: start / status / pause / resume / abort / retry / reconcile",
        "actions": ("start", "status", "pause", "resume", "abort", "retry", "reconcile"),
        "read_only": False,
        "no_db": False,
        "examples": ("hunt run status",),
        "next_hint": "hunt run status",
    },
    "shell": {
        "group": "ops",
        "help": "interactive operator console through the same CLI door",
        "actions": (),
        "read_only": True,
        "no_db": True,
        "examples": ("hunt shell",),
        "next_hint": "hunt shell",
    },
    "help": {
        "group": "ops",
        "help": "grouped command help, or per-verb examples: hunt help [verb]",
        "actions": (),
        "read_only": True,
        "no_db": True,
        "examples": ("hunt help", "hunt help lead"),
        "next_hint": "hunt help",
    },
}

# Shell completion + help verb list, derived from the registry so the shell
# can never drift from the parser.  Kept as a tuple for drop-in use where
# HUNT_VERBS was referenced.
VERBS: tuple[str, ...] = tuple(COMMAND_REGISTRY)

# Per-verb action tuples for completion, derived from the registry.
GROUP_ACTIONS: dict[str, tuple[str, ...]] = {
    verb: meta["actions"] for verb, meta in COMMAND_REGISTRY.items() if meta["actions"]
}


def resolve_command(name: str) -> dict | None:
    """Return the registry entry for *name*, or None when unknown."""
    return COMMAND_REGISTRY.get(name)


def verbs_in_group(group: str) -> tuple[str, ...]:
    """Return verb names belonging to *group*, in registry order."""
    return tuple(v for v, m in COMMAND_REGISTRY.items() if m["group"] == group)


def grouped_help() -> str:
    """Render grouped help lines: one section per pipeline group."""
    lines = []
    for group in GROUPS:
        lines.append(f"{group}:")
        for verb in verbs_in_group(group):
            meta = COMMAND_REGISTRY[verb]
            actions = f" ({'/'.join(meta['actions'])})" if meta["actions"] else ""
            lines.append(f"  {verb}{actions} — {meta['help']}")
    return "\n".join(lines)
