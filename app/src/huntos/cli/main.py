"""HUNT-OS CLI - the operator surface.

Commands:
  hunt target add <name> <url> [--chain evm] [--age-days 0] [--tvl 0] [--notes ""]
  hunt target list
  hunt target prepare SOURCE [--name NAME] [--chain NAME] [--hosts CSV]
                      [--actions CSV] --authorization-note TEXT [--workspace-root PATH]
                                             # classify and transactionally record URL,
                                             # GitHub checkout, or local folder intake
  hunt score <target_id> <ev_score>          # gate: only in scoring phase, must be > 0
  hunt phase <target_id> <next_phase>        # pipeline order + phase exit gates enforced
  hunt artifact <target_id> <surface_map|attack_plan|disclosure_report> <file>
                                             # phase exit artifact, sha256-stamped in events
  hunt finding add <target_id> <title> <klass> [--severity info] [--action read] [--notes ""]
                                             [--surface <id>]
                                             # always inserted as theoretical; --action is the
                                             # rules-of-engagement scale (recon/read/auth-test/mutate);
                                             # --surface pins the finding to an attack-surface row
  hunt finding promote --id <n> --evidence-ref <s> --poc-path <s>
                                             # BLOCKED without both + existing path
  hunt finding retitle --id <n> --title "..."   # bookkeeping retitle (not evidence):
                                             # proven-live may retitle; BLOCKED on
                                             # overturned findings / archived targets
  hunt finding overturn --id <n> --by <name>
  hunt target roe <target_id> --hosts "host1,host2" --actions "recon,read" [--notes ""]
                                             # rules of engagement, DEFAULT-DENY for mutate.
                                             # NOTE: --hosts is INFORMATIONAL ONLY — the DB cannot
                                             # verify what host a PoC touched; only --actions are
                                             # enforced (the mutate proven-live gate)
  hunt target archive <target_id> <reason...>
                                             # deliberate close of a hunt (a retro lesson is
                                             # required). Normal completion walks the phases to
                                             # retro; the economic stop stays available via
                                             # wave close exhausted
  hunt verify <finding_id> <fork_receipt|tx_hash|http_transcript> <body> [--role verifier]
  hunt challenge <finding_id> <notes> [--role adversary]   # required before proven-live
  hunt poc run --id <n> --poc-path <file> [--timeout 120]
                                             # run the PoC inside the ledger: exit code + output
                                             # tail recorded, file sha256 pinned at run time —
                                             # a PoC that never ran clean cannot back a promotion
  hunt wave open <target_id> <lanes>         # BLOCKED until previous wave closed properly
  hunt wave close --wave-id N --verdict <continue|exhausted|pivot>   # findings_new is computed from wave-linked findings
  hunt wave reaudit --wave-id N --summary "..."   # min 20 chars; confirmed/overturned counted from the DB
  hunt report <target_id> [--out report.md]   # --out also logs the disclosure_report artifact
  hunt verify-report <file>                  # recompute the report body's sha256 and compare
                                             # against the hunt-report footer (BLOCKED on
                                             # tampering or a missing footer)
  hunt lesson add <source_target> <pattern> [--scope skill] [--target-id N] [--notes ""]
                                             # archive requires one bound to the target
  hunt lesson reword --id <n> --pattern "..." [--notes "..."]
                                             # rewrite a lesson's pattern (+notes); allowed
                                             # even on archived targets (memory corrections)
  hunt lesson list
  hunt klass list                            # the klass taxonomy (lives as DATA in the taxonomies table)
  hunt klass add <name> [--from-finding <id>]   # retro-gated growth; re-tags the quarantined finding
  hunt brief <target_id>                     # opening read for the next hunt round: lessons,
                                             # contradictions, wave history, findings by ladder,
                                             # taxonomy, leads (read-only)
  hunt lead add --target T --title "..." [--payload "..."]
                                             [--precondition "var|value|deskripsi"] (repeatable)
                                             [--surface <id>]
                                             # register an observation; payload optional at add
                                             # (recon-origin legal) but required before the mutation loop;
                                             # --surface pins the lead to an attack-surface row
  hunt lead set-half --lead N --half trigger|impact --verdict proven|refuted --evidence "..."
                                             # manual verdicts; 'ambiguous' is oracle-exclusive (BLOCKED)
  hunt lead mutate --lead N --variable v --old o --new n --result advanced|unchanged|refuted|unknown
                  --evidence "..." [--plan "var|value|deskripsi"] [--resolve <precondition_id>]
                                             # one loop step; anti-repeat on (variable,new_value);
                                             # result=unknown MUST give birth to a new precondition (--plan)
  hunt lead next --lead N                    # the deterministic next missing, never-tried precondition
                                             # (exhausted -> a park suggestion, not an error)
  hunt lead park --lead N --retrigger "observable :: check"
                                             # park with a mandatory testable tripwire (no lazy parks)
  hunt lead kill --lead N --trigger-refutation "..." --impact-refutation "..." [--retrigger "..."]
                                             # both halves refuted + evidence -> killed; a one-sided
                                             # kill is REFUSED: auto-park + dismissal_count++ (needs --retrigger)
  hunt lead promote --lead N --klass <taxonomy> --severity critical|high|medium|low|info
                                             # both halves proven -> finding (frozen provenance snapshot)
  hunt lead list --target T                  # the target's leads with verdicts and states
  hunt oracle --lead N|--finding N --half trigger|impact --baseline b.json --candidate c.json
                                             # deterministic observation oracle; the verdict (+ both
                                             # feature JSONs) is stored as an oracle_verdict event;
                                             # unknown sets the half 'ambiguous' (the only path there)
  hunt surface add <target_id> <kind> <name> [--notes ""]
                                             # the attack-surface ledger; kind is one of
                                             # endpoint|trust_boundary|invariant|component (db.SURFACE_KINDS)
  hunt surface list <target_id>              # the target's recorded surfaces
  hunt coverage <target_id>                  # per-surface lead/finding coverage, then blind spots:
                                             # trust boundaries that never grew a lead or a finding
  hunt chain add <target_id> <name> [--entry s] [--impact s] [--notes s]
                                             # the 0-day claim engine: a claim is a chain —
                                             # entry, linked steps, impact — proven, novel, honest
  hunt chain link <chain_id> <position> <finding|lead> <ref_id>
  hunt chain show <chain_id>                 # markdown render of the chain
  hunt chain novelty <chain_id>              # has this (class, entry, impact) pattern been claimed before?
  hunt fuzz --url URL [--method GET] [--param p]... [--timeout 10] [--target-id N] [--max 12]
                                             # fire the doctrine edge-case battery at one parameter
                                             # (one probe call per --param, baseline + battery, capped
                                             # by --max); every probe is a fuzz_probe event (redacted),
                                             # flinches print "!! anomaly:" lines — leads stay manual
  hunt project bind                          # bind this working directory (.huntos-project)
                                             # to the current db (deliberate, logged rebind)
  hunt project status                        # workspace lock vs the current db
  hunt next [--target ID]                    # the ONE recommended next command for the hunt
                                             # (read-only; prints NEXT/WHY, never executes,
                                             # never writes — judgment stays a read: brief/status)
  hunt status                                # full picture + contradiction report
  hunt install --adapter claude-code|zcode|hermes|generic
              [--scope project|user] [--mode router|native] [--dir PATH]
              [--force] [--check] [--uninstall]
                                             # install the skills layer into a harness
                                             # (delegates to huntos.installer: additive,
                                             # manifest-tracked, same flags + exit codes;
                                             # needs no hunt db and creates none)
  hunt doctor [--adapter claude-code|zcode|hermes|generic|mock]
              [--scope project|user] [--dir PATH]
                                             # workspace preflight: cli, db, project lock,
                                             # claim gate, skills layer, hook wrapper —
                                             # each ok / FAIL; --adapter mock adds the
                                             # conductor capability dump
  hunt adapter add NAME --exec ABSOLUTE_PATH [--arg ARG ...]
  hunt adapter list|doctor NAME|remove NAME     # managed adapter registry
  hunt shell [--script FILE] [--guided] [--no-hint] [--quiet]
                                             # interactive operator console through the
                                             # same CLI door; builtins: help, macros, last,
                                             # quit, exit, Ctrl-D; aliases: n, b, s;
                                             # macros: firstblood, wave, report
                                             # script mode reads one command per line,
                                             # ignores # comments, stops fail-closed on the
                                             # first nonzero, and returns rc 0 only if all succeed
  hunt run start --target <id> --rounds N [--adapter mock] [--model-profile P]
                                             [--budget-per-attempt T]
                                             # open a conductor session, drive the loop,
                                             # print session id + final status + the
                                             # control-room summary
  hunt run status [--session S]              # control-room summary (default: latest session)
  hunt run pause --session S                 # session lifecycle one-liners (also:
  hunt run resume --session S                # resume, abort)
  hunt run retry --attempt A [--model-profile P]
                                             # re-run an interrupted/uncertain attempt
                                             # (a NEW attempt id; never a recycled one)
  hunt run reconcile --attempt A --resolution "..."
                                             # resolve the incident on an uncertain attempt
  hunt help [verb]                           # grouped command help (no db needed);
                                             # with a verb: examples + the NEXT hint

Claim discipline (enforced by huntos/_data/bin/claim_gate.py, which vetoes engine output):
every strong claim (PROVEN / EXPLOITABLE / "admin takeover") must name its finding —
bind it explicitly as PROVEN[F-<n>] / EXPLOITABLE[F-<n>] (or keep the F-<n> id next
to the marker). An unbound claim is a veto; the db decides which findings are proven.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import shlex
import sqlite3
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from ..core import db, fuzz
from ..core.models import PHASE_ARTIFACTS, ROE_ACTIONS, SEVERITY
from ..conductor.adapter import MockAdapter
from .errors import (
    MSYS_BLOCKED_MSG as _MSYS_BLOCKED_MSG,
    MSYS_MANGLED_RE as _MSYS_MANGLED_RE,
    blocked as _blocked_line,
    is_msys_mangled as _is_msys_mangled,
    split_blocked as _split_blocked,
)

# SURFACE_KINDS lives in db.py (capability stack db layer): the surface
# subparser validates kinds against the same DATA the db enforces.
SURFACE_KINDS = db.SURFACE_KINDS

# Read-only commands run even when the workspace lock mismatches (hard warning
# instead of BLOCKED) — inspecting state must not require rebinding first.
# Simple command names (nothing but reads behind them):
READ_ONLY_COMMANDS = ("verify-report", "status", "brief", "next", "doctor", "coverage", "help")
# Groups that MIX reads and writes: the ACTION decides, not the command name —
# `hunt target add` / `hunt klass add` / `hunt run start` stay lock-blocked
# while their `list` / `show` / `novelty` / `status` actions pass with a warning.
READ_ONLY_ACTIONS = {
    "target": {"list"},
    "adapter": {"list", "doctor"},
    "harness": {"list", "doctor"},
    "klass": {"list"},
    "lesson": {"list"},
    "lead": {"list"},
    "surface": {"list"},
    "chain": {"show", "novelty"},
    "run": {"status"},
}

# Commands that run WITHOUT opening the hunt db (L3): `install` needs no db
# and must not silently create one as an install side effect; `doctor` runs
# its own checklist where "db open" is a per-check FAIL line (a corrupt db is
# a doctor FAIL, not the global BLOCKED exit). `shell` holds/opens no db itself:
# every entered line returns through main(), preserving the same connection
# lifecycle and workspace-gate path as the ordinary CLI.
NO_DB_COMMANDS = ("install", "doctor", "adapter", "harness", "shell", "help")

# The package's shipped data root, resolved from this file
# (<package>/huntos/_data). `hunt install` delegates to the in-package
# huntos.installer; doctor's no-adapter checks use _data for the packaged
# claim gate and hook pack, so the CLI is self-contained (no checkout).
# Tests may monkeypatch huntos.cli.main._DATA_ROOT to point the doctor at a
# fake workspace (the *_path() helpers read it at call time).
_DATA_ROOT = Path(__file__).resolve().parents[1] / "_data"


def _is_read_only(args) -> bool:
    """Lock-exemption check (L1.2): command-name allowlist PLUS, for groups that
    mix read and write actions, the parsed action."""
    if args.cmd in READ_ONLY_COMMANDS:
        return True
    action = getattr(args, "action", None)
    return action is not None and action in READ_ONLY_ACTIONS.get(args.cmd, ())


# --- MSYS leading-slash guard (L2.2, FIRSTBLOOD #2) ---------------------------
# On Windows Git Bash, a POSIX-style argument that BEGINS with '/' is silently
# rewritten into a Windows path under the Git installation directory:
# '/api/users' arrives here as 'C:/Program Files/Git/api/users' (or with
# backslashes). Recorded verbatim, that mangled string is ledger poison — and
# retitling it away later is exactly what L2.1 exists for. The guard refuses
# the mangled SHAPE at the door instead. Only FREE-TEXT positionals are guarded
# (finding titles, lesson patterns/sources); real file-path arguments
# (poc-path, artifact paths, --out) are never guarded — a real
# 'C:\\Users\\...\\poc.py' does not match the pattern and must keep working.

# Canonical shape lives in cli/errors.py (imported above as _MSYS_*); only
# FREE-TEXT positionals are guarded (finding titles, lesson patterns/sources);
# real file-path arguments are never guarded.  The module-level names stay
# importable here for backward compatibility (tests import _MSYS_BLOCKED_MSG).


def _reject_msys_mangled(text: str) -> None:
    """Refuse a free-text argument that arrived MSYS-mangled (L2.2)."""
    if _is_msys_mangled(text):
        raise ValueError(_MSYS_BLOCKED_MSG)


def _emit_refusal(line: str, as_json: bool) -> None:
    """Refusal output (Phase 3, Strix human/machine duality).

    Human default: the ``BLOCKED: ... | NEXT: ...`` line to stderr (stdout
    stays machine-clean).  With ``--json``: a machine envelope to stdout::

        {"ok": false, "code": 2, "error": "<what>", "next": "<cmd>" | null}

    ``next`` is null for bare refusals whose remediation is inline (the MSYS
    guard, the workspace-lock line).  The exit code is always 2 — argparse
    misuse stays 2 as well.  Success output is unchanged by ``--json``.
    """
    if not as_json:
        print(line, file=sys.stderr)
        return
    error, next_cmd = _split_blocked(line)
    print(json.dumps({"ok": False, "code": 2, "error": error, "next": next_cmd}))


def cmd_target(args, conn) -> int:
    if args.action == "prepare":
        from ..core.target_source import (
            classify_target_source,
            default_target_name,
            prepare_github_source,
        )

        source = classify_target_source(args.source)
        if source.kind == "github":
            root = Path(args.workspace_root).expanduser() if args.workspace_root else \
                Path.home() / ".huntos" / "workspaces"
            source = prepare_github_source(source, root)
        name = args.name or default_target_name(source)
        tid = db.prepare_target(
            conn, name, source, args.chain, args.hosts, args.actions,
            args.authorization_note,
        )
        print(f"target #{tid} prepared: {name}")
        print(f"kind: {source.kind}")
        print(f"canonical: {source.canonical}")
        print(f"workspace: {source.workspace or '(none)'}")
        print(f"revision: {source.revision or '(none)'}")
        if source.kind == "url":
            print("URL recorded only — no automatic probe or crawl was performed")
    elif args.action == "add":
        tid = db.add_target(conn, args.name, args.url, args.chain, args.age_days, args.tvl, args.notes)
        print(f"target #{tid} added: {args.name} ({args.url}) phase=scoring")
    elif args.action == "roe":
        # `hunt target roe <target_id> ...` — the target id is a required
        # positional on the roe subparser (parse-time enforced).
        tid = args.target_id
        db.set_roe(conn, tid, args.hosts, args.actions, args.notes)
        row = db.get_roe(conn, tid)
        print(f"roe updated for target #{tid}: actions={row['actions']} hosts={row['hosts']}")
        print("(hosts are informational only — only actions are enforced; default-deny for mutate)")
    elif args.action == "list":
        rows = db.list_targets(conn)
        if not rows:
            print("(no targets)")
        for r in rows:
            print(f"#{r['id']} {r['name']:24} {r['url']:40} chain={r['chain']:8} "
                  f"age={r['age_days']}d tvl=${r['tvl_usd']:,.0f} phase={r['phase']} ev={r['ev_score']}")
    elif args.action == "archive":
        # `hunt target archive <target_id> <reason...>` (A16): a completed hunt
        # must not strand in retro forever — archiving is a first-class command.
        # The lesson gate lives in db.archive_target (memory compounds or the
        # hunt never closed).
        row = conn.execute("SELECT phase FROM targets WHERE id = ?", (args.target_id,)).fetchone()
        if row is None:
            raise ValueError(f"BLOCKED: target #{args.target_id} not found")
        if row["phase"] == "archived":
            raise ValueError(f"BLOCKED: target #{args.target_id} is already archived")
        reason = " ".join(args.reason).strip()
        if not reason:
            raise ValueError("BLOCKED: archive requires a reason — why is this hunt closing?")
        db.archive_target(conn, args.target_id, reason)
        print(f"target #{args.target_id} archived: {reason}")
    return 0


def cmd_score(args, conn) -> int:
    # Parse-time honesty (A8/A5): argparse's float() happily accepts 'nan'/'inf',
    # and NaN would bind as NULL in sqlite, bricking every later status/phase
    # print. The db also rejects, but this check gives the clean message first.
    if not math.isfinite(args.ev):
        raise ValueError("BLOCKED: ev_score must be a finite number > 0")
    db.score_target(conn, args.target_id, args.ev)
    print(f"target #{args.target_id} scored ev={args.ev}")
    return 0


def cmd_phase(args, conn) -> int:
    db.set_phase(conn, args.target_id, args.phase)
    print(f"target #{args.target_id} phase -> {args.phase}")
    return 0


def _surface_kwarg(surface_id) -> dict:
    """--surface passthrough: the db contract's optional surface_id on
    add_finding / add_lead, passed only when the flag is set."""
    return {"surface_id": surface_id} if surface_id is not None else {}


def cmd_finding(args, conn) -> int:
    if args.action == "add":
        # MSYS guard (L2.2): titles are free text; a mangled Git path must be
        # refused at the door, not recorded as a finding title.
        _reject_msys_mangled(args.title)
        fid = db.add_finding(conn, args.target_id, args.title, args.klass, args.severity,
                             notes=args.notes, action=args.finding_action,
                             falsifier=args.falsifier, **_surface_kwarg(args.surface))
        # L1.4 (FIRSTBLOOD #13), echo what was recorded: add_finding silent-links
        # to the latest OPEN wave; read the linkage back from the row and say so
        # (add_finding's return contract stays the int finding id).
        wave_id = db.get_finding_wave_id(conn, fid)
        linkage = f"linked to open wave #{wave_id}" if wave_id is not None else "no open wave"
        print(f"finding #{fid} added [{args.severity}] {args.title} (theoretical, action={args.finding_action})"
              + (f" surface=#{args.surface}" if args.surface is not None else "")
              + f" — {linkage}")
    elif args.action == "retitle":
        # L2.1: bookkeeping retitle (mangled titles are not an overturn). The
        # MSYS guard runs on the NEW title; db.retitle_finding enforces the
        # archived/overturned/secrets gates and logs finding_retitled.
        _reject_msys_mangled(args.title)
        db.retitle_finding(conn, args.id, args.title)
        print(f"finding #{args.id} retitled: {args.title}")
    elif args.action == "promote":
        new_status = db.promote_finding(conn, args.id, args.evidence_ref, args.poc_path)
        print(f"finding #{args.id} promoted -> {new_status} (evidence: {args.evidence_ref})")
    elif args.action == "overturn":
        db.overturn_finding(conn, args.id, args.by)
        print(f"finding #{args.id} OVERTURNED by {args.by} (audit trail kept)")
    return 0


def cmd_verify(args, conn) -> int:
    db.record_verification(conn, args.finding_id, args.artifact_type, args.body, args.role)
    print(f"verification recorded on finding #{args.finding_id}: {args.artifact_type} (by {args.role})")
    return 0


def cmd_challenge(args, conn) -> int:
    db.record_adversary(conn, args.finding_id, args.notes, args.role)
    print(f"adversary review recorded on finding #{args.finding_id} (by {args.role})")
    return 0


def cmd_poc(args, conn) -> int:
    # `hunt poc run --id <n> --poc-path <file>` (A7): turns "PoC exists" into
    # "PoC ran, exit 0, hash pinned". The db-side record_poc_run validates the
    # finding and the file, requires exit 0, and logs the poc_run event with the
    # file's sha256 — promote_finding then requires a matching event, so a PoC
    # that never ran clean cannot back a promotion.
    row = conn.execute("SELECT id FROM findings WHERE id = ?", (args.id,)).fetchone()
    if row is None:
        raise ValueError(f"BLOCKED: finding #{args.id} not found — hunt status lists finding ids")
    if args.timeout <= 0:
        raise ValueError("BLOCKED: --timeout must be a positive number of seconds")
    path = os.path.expanduser(args.poc_path)
    if not os.path.isfile(path):
        raise ValueError(f"BLOCKED: poc path is not a file: {args.poc_path}")
    if path.endswith(".py"):
        cmd = [sys.executable, path]
    else:
        cmd = [path]  # executed directly; a non-executable file fails with OSError below
    try:
        # stdout+stderr combined, decoded leniently (a PoC may print non-UTF-8
        # bytes; the tail is evidence color, not structured data).
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=args.timeout)
    except subprocess.TimeoutExpired:
        # subprocess.run has killed the child; a timed-out run is a failed run.
        raise ValueError(
            f"BLOCKED: poc run exceeded {args.timeout}s and was killed — "
            "a timed-out run is a failed run (no poc_run event recorded)"
        )
    except OSError as exc:
        raise ValueError(f"BLOCKED: cannot execute poc {path} ({exc})")
    tail = (proc.stdout or b"").decode("utf-8", errors="replace")[-500:]
    with open(path, "rb") as fh:  # the hash pinned at run time is the file's own
        digest = hashlib.sha256(fh.read()).hexdigest()
    db.record_poc_run(conn, args.id, args.poc_path, proc.returncode, tail)
    print(f"poc run recorded: exit={proc.returncode} sha256:{digest[:12]}")
    return 0


def cmd_artifact(args, conn) -> int:
    db.record_phase_artifact(conn, args.target_id, args.artifact_type, args.path)
    print(f"artifact {args.artifact_type} recorded on target #{args.target_id}: {args.path}")
    return 0


def cmd_wave(args, conn) -> int:
    if args.action == "open":
        wid = db.open_wave(conn, args.target_id, args.lanes)
        w = db.list_waves(conn, args.target_id)[-1]
        print(f"wave #{wid} opened (number {w['number']}) lanes={args.lanes}")
    elif args.action == "close":
        db.close_wave(conn, args.wave_id, args.verdict)
        w = conn.execute(
            "SELECT findings_new, ev_verdict FROM waves WHERE id=?",
            (args.wave_id,),
        ).fetchone()
        if w["ev_verdict"] == "exhausted":
            # L2.5: the economic stop ARCHIVED the target (existing kernel law,
            # unchanged) — the echo must say so instead of a bare "closed".
            print(
                f"wave #{args.wave_id} closed findings_new={w['findings_new']} "
                f"verdict=exhausted — target archived (economic stop; report/retro skipped)"
            )
        else:
            print(f"wave #{args.wave_id} closed findings_new={w['findings_new']} verdict={args.verdict}")
    elif args.action == "reaudit":
        if not args.summary:
            raise ValueError(
                "BLOCKED: --summary is required (min 20 chars) — "
                "what was confirmed, what was overturned, and why"
            )
        db.record_reaudit(conn, args.wave_id, args.summary)
        print(f"wave #{args.wave_id} re-audit recorded: {args.summary}")
    return 0


def cmd_report(args, conn) -> int:
    out = db.export_report(conn, args.target_id)
    if args.out:
        # L2.4 fail-closed: --out is only a success when the disclosure_report
        # artifact stamp lands too (the stamp is the phase-exit evidence).
        # Pre-check the deterministic stamp gates BEFORE writing anything, so a
        # target that cannot stamp never gets a report file written for it:
        #   1. archived target (or a target outside the report phase, the
        #      artifact's owner phase) -> BLOCKED, nothing written, exit 2;
        #   2. write + stamp both succeed -> exit 0;
        #   3. write succeeds but the stamp still fails -> the file may remain
        #      (user data is never deleted), the command still BLOCKS (exit 2)
        #      and never claims success.
        t = db.get_target(conn, args.target_id)
        if t["phase"] == "archived":
            raise ValueError(
                f"BLOCKED: target #{args.target_id} is archived — report --out refused, "
                "no file written (an archived hunt takes no new artifacts)"
            )
        owner_phase = db._ARTIFACT_OWNER_PHASE.get("disclosure_report")
        if t["phase"] != owner_phase:
            raise ValueError(
                f"BLOCKED: disclosure_report belongs to the {owner_phase} phase "
                f"(current phase: {t['phase']}) — report --out refused, no file written"
            )
        # utf-8 explicit (A14): locale-dependent writes make the report
        # undecodable on stock Windows (cp1252) and break fingerprint checks.
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        # A stamp failure past this point is case 3: the ValueError/OSError
        # propagates to main()'s BLOCKED handler (exit 2), the file stays.
        db.record_phase_artifact(conn, args.target_id, "disclosure_report", args.out)
        print(f"report written to {args.out}")
    else:
        print(out)
    return 0


def cmd_verify_report(args, conn) -> int:
    # conn is unused: verification is a pure file-level check (footer vs body
    # hash) so it also works when HUNT_DB points anywhere else.
    print(db.verify_report_file(args.file))
    return 0


def cmd_project(args, conn) -> int:
    cwd = os.getcwd()
    if args.action == "bind":
        db_id = db.bind_project(conn, cwd)
        print(f"project bound to db {db_id[:12]} ({db.LOCK_FILENAME})")
    elif args.action == "status":
        lock = db.read_project_lock(cwd)
        current_id = db.get_meta(conn, "db_id")
        if lock is None:
            print(f"no lock file ({db.LOCK_FILENAME} not found in {cwd}) — "
                  f"run: hunt project bind")
        elif not isinstance(lock, dict) or not isinstance(lock.get("db_id"), str):
            print(f"{db.LOCK_FILENAME} in {cwd} is malformed — "
                  "fix or delete it, or rebind: hunt project bind", file=sys.stderr)
        else:
            locked_id = lock["db_id"]
            bound_at = lock.get("bound_at", "?")
            if locked_id == current_id:
                print(f"{db.LOCK_FILENAME}: bound to db {locked_id[:12]} at {bound_at} "
                      f"— match with current db {current_id[:12]}")
            else:
                print(f"{db.LOCK_FILENAME}: bound to db {locked_id[:12]} at {bound_at} "
                      f"— MISMATCH with current db {current_id[:12]}")
                print("deliberate switch? rebind first: hunt project bind", file=sys.stderr)
    return 0


def cmd_lesson(args, conn) -> int:
    if args.action == "add":
        # MSYS guard (L2.2): source and pattern are free text.
        _reject_msys_mangled(args.source)
        _reject_msys_mangled(args.pattern)
        lid = db.add_lesson(conn, args.source, args.pattern, args.scope, args.notes,
                            target_id=args.target_id)
        print(f"lesson #{lid} recorded ({args.scope}): {args.pattern}")
    elif args.action == "reword":
        # L2.1: rewrite the pattern (optionally --notes). Lessons stay rewordable
        # on archived targets (memory additions are not history rewrites); the
        # MSYS guard runs on the NEW pattern.
        _reject_msys_mangled(args.pattern)
        db.reword_lesson(conn, args.id, args.pattern,
                         notes=args.notes if args.notes is not None else None)
        line = f"lesson #{args.id} reworded: {args.pattern}"
        if args.notes is not None:
            line += " (notes updated)"
        print(line)
    elif args.action == "list":
        for r in db.list_lessons(conn):
            print(f"#{r['id']} [{r['scope']}] {r['source_target']}: {r['pattern']}")
    return 0


def cmd_klass(args, conn) -> int:
    if args.action == "list":
        rows = conn.execute(
            "SELECT kind, value, source FROM taxonomies ORDER BY kind, value"
        ).fetchall()
        if not rows:
            print("(taxonomy empty)")
        for r in rows:
            print(f"{r['kind']:8} {r['value']:24} source={r['source']}")
    elif args.action == "add":
        name = db.add_klass(conn, args.name, from_finding=args.from_finding)
        if args.from_finding is not None:
            line = f"klass '{name}' added — finding #{args.from_finding} re-tagged"
            lesson = conn.execute(
                "SELECT id FROM lessons WHERE pattern=? ORDER BY id DESC LIMIT 1",
                (f"new klass '{name}' promoted from finding #{args.from_finding}",),
            ).fetchone()
            if lesson is not None:
                line += f" (lesson #{lesson['id']} recorded)"
            print(line)
        else:
            print(f"klass '{name}' added to taxonomy (source=cli)")
    return 0


def _fmt_duration(created_at: str) -> str:
    """Human duration since a sqlite datetime('now') UTC stamp, e.g. 2h14m.

    Returns '' when the stamp is missing or unparseable (display must never
    crash on it)."""
    try:
        since = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return ""
    minutes = max(0, int((datetime.now(timezone.utc) - since).total_seconds()) // 60)
    if minutes >= 60:
        return f"{minutes // 60}h{minutes % 60:02d}m"
    return f"{minutes}m"


def cmd_brief(args, conn) -> int:
    # Read-only: prints the opening read for the next hunt round. No lock
    # interaction beyond the normal main() flow, nothing written.
    print(db.export_brief(conn, args.target_id))
    return 0


def _resolve_next_target(conn, target_arg) -> int:
    """`hunt next` target resolution (spec L1.1): --target wins; else the single
    non-archived target; else BLOCKED listing the ids (hunt target list)."""
    if target_arg is not None:
        row = conn.execute("SELECT id FROM targets WHERE id=?", (target_arg,)).fetchone()
        if row is None:
            raise ValueError(
                f"BLOCKED: target #{target_arg} not found — hunt target list shows the ids"
            )
        return int(row["id"])
    active = conn.execute(
        "SELECT id, phase FROM targets WHERE phase != 'archived' ORDER BY id"
    ).fetchall()
    if len(active) == 1:
        return int(active[0]["id"])
    every = conn.execute("SELECT id, phase FROM targets ORDER BY id").fetchall()
    ids = ", ".join(f"#{r['id']}" for r in every)
    if not every:
        raise ValueError(
            "BLOCKED: no target to recommend a next for (the ledger is empty) — "
            "add one: hunt target add <name> <url> (hunt target list shows ids)"
        )
    if active:
        active_ids = ", ".join(f"#{r['id']}" for r in active)
        raise ValueError(
            f"BLOCKED: {len(active)} active targets — pass --target <id>; "
            f"active ids: {active_ids} (hunt target list)"
        )
    raise ValueError(
        "BLOCKED: no active target (every hunt is archived) — pass --target <id>; "
        f"ids: {ids} (hunt target list)"
    )


def cmd_next(args, conn) -> int:
    """`hunt next [--target ID]` (L1.1): the operator's mouth. Prints exactly
    NEXT/WHY and exits 0 (archived included) — it NEVER executes the command it
    names and never writes (db.next_command is a pure ledger read). Exit 2 only
    on BLOCKED (no resolvable target / unknown id; a corrupt db is refused by
    main()'s connect handler)."""
    tid = _resolve_next_target(conn, args.target)
    nxt, why = db.next_command(conn, tid)
    print(f"NEXT: {nxt}")
    print(f"WHY: {why}")
    return 0


def _parse_precondition(raw: str) -> tuple[str, str, str]:
    """'var|value|deskripsi' -> (var, value, deskripsi); both sides non-empty."""
    parts = raw.split("|")
    if len(parts) != 3 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(
            f"BLOCKED: --precondition must be 'variable|value|description' with a "
            f"non-empty variable and value; got {raw!r}"
        )
    return parts[0].strip(), parts[1].strip(), parts[2].strip()


def cmd_lead(args, conn) -> int:
    if args.action == "add":
        preconditions = None
        if args.precondition:
            preconditions = [_parse_precondition(p) for p in args.precondition]
        lid = db.add_lead(conn, args.target, args.title, payload=args.payload,
                          preconditions=preconditions, **_surface_kwarg(args.surface))
        lead = db.get_lead(conn, lid)
        print(f"lead L-{lid} added (number {lead['number']}, state=open) on target "
              f"#{args.target}: {args.title}"
              + ("" if lead["payload"] else " [payload empty]")
              + (f" surface=#{args.surface}" if args.surface is not None else ""))
    elif args.action == "set-half":
        db.set_lead_half(conn, args.lead, args.half, args.verdict, args.evidence)
        lead = db.get_lead(conn, args.lead)
        print(f"lead L-{args.lead} {args.half} -> {args.verdict} "
              f"(state={lead['state']}, trigger={lead['trigger_verdict']}, "
              f"impact={lead['impact_verdict']})")
    elif args.action == "mutate":
        mid = db.mutate_lead(conn, args.lead, args.variable, args.old, args.new,
                             args.result, args.evidence, plan=args.plan,
                             resolve=args.resolve)
        lead = db.get_lead(conn, args.lead)
        followup = ""
        if args.result == "unknown":
            row = conn.execute(
                "SELECT followup_precondition_id FROM lead_mutations WHERE id=?", (mid,)
            ).fetchone()
            followup = f", followup precondition #{row['followup_precondition_id']}"
        print(f"lead L-{args.lead} mutation #{mid} recorded: {args.variable} "
              f"{args.old!r} -> {args.new!r} result={args.result} "
              f"(state={lead['state']}{followup})")
    elif args.action == "set":
        db.set_lead_payload(conn, args.lead, args.payload)
        print(f"lead L-{args.lead} payload set ({len(args.payload.strip())} chars)")
    elif args.action == "next":
        lead = db.get_lead(conn, args.lead)
        nxt = db.next_mutation(conn, args.lead)
        if nxt is None:
            print(f"lead L-{args.lead}: no untried missing preconditions left — "
                  "consider parking it with a retrigger condition "
                  "(hunt lead park --lead N --retrigger \"observable :: check\")")
        else:
            print(f"lead L-{args.lead} next: precondition #{nxt['precondition_id']} "
                  f"{nxt['variable']}={nxt['value']!r}"
                  + (f" ({nxt['description']})" if nxt["description"] else ""))
    elif args.action == "park":
        db.park_lead(conn, args.lead, args.retrigger)
        print(f"lead L-{args.lead} parked — tripwire: {args.retrigger}")
    elif args.action == "kill":
        outcome = db.kill_lead(conn, args.lead, args.trigger_refutation,
                               args.impact_refutation, retrigger=args.retrigger)
        lead = db.get_lead(conn, args.lead)
        if outcome == "killed":
            print(f"lead L-{args.lead} killed (state=killed) — both halves refuted")
        else:
            print(f"kill refused -> parked (dismissal #{lead['dismissal_count']}) — "
                  f"lead L-{args.lead} tripwire: {lead['retrigger_condition']}")
    elif args.action == "promote":
        fid = db.promote_lead(conn, args.lead, args.klass, args.severity,
                              action=args.roe_action)
        print(f"lead L-{args.lead} promoted -> finding #{fid} "
              f"[{args.severity}] {args.klass} (provenance snapshot frozen)")
    elif args.action == "reopen":
        db.reopen_lead(conn, args.lead, args.evidence)
        print(f"lead L-{args.lead} reopened (state=open) — tripwire fired, "
              "the lead is back in the mutation loop")
    elif args.action == "list":
        rows = db.list_leads(conn, args.target)
        if not rows:
            print("(no leads)")
        for r in rows:
            print(f"L-{r['id']} [{r['state']:8}] #{r['number']} {r['title']:32} "
                  f"trigger={r['trigger_verdict']:8} impact={r['impact_verdict']:8} "
                  f"dismissals={r['dismissal_count']}"
                  + (f" -> finding #{r['promoted_finding_id']}" if r["promoted_finding_id"] else ""))
    return 0


def cmd_oracle(args, conn) -> int:
    if (args.lead is None) == (args.finding is None):
        raise ValueError(
            "BLOCKED: the oracle needs exactly one target — pass --lead N or --finding N"
        )
    if args.lead is not None:
        target = ("lead", args.lead)
        lead_id = args.lead
        db.get_lead(conn, lead_id)  # existence + state gates run inside record_oracle_verdict
    else:
        target = ("finding", args.finding)
        # The finding-anchored oracle reuses the finding's lead: findings carry
        # lead_id after a lead promote. A finding without a lead has no
        # observation loop to serve — fail with a message that says so.
        row = conn.execute("SELECT lead_id FROM findings WHERE id=?", (args.finding,)).fetchone()
        if row is None:
            raise ValueError(f"BLOCKED: finding #{args.finding} not found")
        if row["lead_id"] is None:
            raise ValueError(
                f"BLOCKED: finding #{args.finding} has no lead bound (lead_id IS NULL) — "
                "the oracle traces lead observations (hunt lead add ... first)"
            )
        lead_id = row["lead_id"]
    baseline = db._read_oracle_feature(args.baseline, "baseline", lead_id)
    candidate = db._read_oracle_feature(args.candidate, "candidate", lead_id)
    verdict, event_id = db.record_oracle_verdict(conn, lead_id, args.half, baseline, candidate)
    label = f"{'lead' if target[0] == 'lead' else 'finding'} #{target[1]}"
    print(f"oracle verdict for {label} {args.half}: {verdict} "
          f"(oracle_verdict event #{event_id} stored with both feature JSONs)")
    if verdict == "unknown":
        print(f"lead L-{lead_id} {args.half} set to 'ambiguous' "
              "(oracle-exclusive; re-run when the timing settles)")
    else:
        print(f"lead L-{lead_id} {args.half} set to "
              f"{'proven' if verdict == 'confirmed' else 'refuted'}")
    return 0


def _capget(mapping, key, default=None):
    """Read a key off a contract dict OR a sqlite3.Row (dict.get is absent on
    Row; Row raises IndexError on a missing key). Display must never crash on
    a shape it did not expect."""
    try:
        value = mapping[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def cmd_surface(args, conn) -> int:
    if args.action == "add":
        sid = db.add_surface(conn, args.target_id, args.kind, args.name, notes=args.notes)
        print(f"surface #{sid} added ({args.kind}): {args.name}")
    elif args.action == "list":
        rows = db.list_surfaces(conn, args.target_id)
        if not rows:
            print("(no surfaces recorded — hunt surface add <target_id> <kind> <name>)")
        for r in rows:
            print(f"#{r['id']} {r['kind']:14} {r['name']}")
    return 0


def cmd_coverage(args, conn) -> int:
    # The blind-spot scanner made mechanical: the db computes per-surface
    # lead/finding coverage; the CLI only displays it.
    cov = db.surface_coverage(conn, args.target_id)
    rows = _capget(cov, "rows", []) or []
    if not rows:
        print("(no surfaces recorded — hunt surface add <target_id> <kind> <name>)")
    for r in rows:
        lead = "has-lead" if r["has_lead"] else "no-lead"
        finding = "has-finding" if r["has_finding"] else "no-finding"
        print(f"[{lead}] [{finding}] {r['kind']} {r['name']}")
    print("blind spots (trust boundaries with no lead or finding):")
    blind = _capget(cov, "blind_spots", []) or []
    if not blind:
        print("(none — every trust boundary has been probed)")
    for b in blind:
        name = b["name"] if isinstance(b, dict) else b
        print(f"!! {name}")
    return 0


def cmd_chain(args, conn) -> int:
    if args.action == "add":
        cid = db.add_chain(conn, args.target_id, args.name, entry=args.entry,
                           impact=args.impact, notes=args.notes)
        print(f"chain #{cid} added: {args.name}")
    elif args.action == "link":
        if args.kind not in ("finding", "lead"):
            raise ValueError("BLOCKED: a chain step links a 'finding' or a 'lead'")
        db.link_step(conn, args.chain_id, args.position, args.kind, args.ref_id)
        print(f"chain #{args.chain_id} step {args.position} <- {args.kind} #{args.ref_id}")
    elif args.action == "show":
        print(db.chain_detail(conn, args.chain_id))
    elif args.action == "novelty":
        # The 0-day honesty check: a claim that already appeared in the ledger
        # is not a 0-day — the db owns the pattern comparison, the CLI the words.
        res = db.chain_novelty(conn, args.chain_id)
        print(f"pattern: {_capget(res, 'pattern', '')}")
        if _capget(res, "novel", False):
            print("novel: yes — this (class, entry, impact) pattern has never appeared in your ledger")
        else:
            seen_in = _capget(res, "seen_in", []) or []
            names = ", ".join(str(s) for s in seen_in) if seen_in else "(no prior claim recorded)"
            print(f"novel: NO — seen in: {names}")
    return 0


def cmd_fuzz(args, conn) -> int:
    if args.max < 1:
        raise ValueError("BLOCKED: --max must be at least 1 (one probe = one request)")
    if args.timeout <= 0:
        raise ValueError("BLOCKED: --timeout must be a positive number of seconds")
    params = args.param or [None]
    shown = ", ".join(p if p else fuzz.DEFAULT_PARAM for p in params)
    print(f"fuzz battery: {args.url} method={args.method.upper()} param(s)={shown} max={args.max}")
    if args.target_id is None:
        print("(no --target-id given: fuzz_probe events are recorded globally, target_id=NULL)")
    budget = args.max
    truncated = False
    flagged = []  # (param_name, probe_row, baseline_status)
    total = 0
    for param in params:
        if budget <= 0:
            truncated = True
            break
        param_name = param if param else fuzz.DEFAULT_PARAM
        # --max caps probes FIRED (baseline included), so the battery list is
        # trimmed before the requests go out, not after.
        n_battery = min(len(fuzz.BATTERY), budget - 1)
        if n_battery < len(fuzz.BATTERY):
            truncated = True
        results = fuzz.probe(args.url, method=args.method, param=param,
                             payloads=fuzz.BATTERY[:n_battery], timeout=args.timeout)
        budget -= len(results)
        total += len(results)
        baseline_status = results[0]["status"] if results else "?"
        anomalous = {id(r) for r in fuzz.anomalies(results)}
        print(f"param {param_name}:")
        for r in results:
            mark = " !!" if id(r) in anomalous else ""
            err = f" err={r['error'][:48]}" if r.get("error") else ""
            print(f"  {r['payload_name']:14} status={r['status']:<4} {r['elapsed_ms']:>5}ms "
                  f"len={r['body_len']:>6} sha={r['body_hash'] or '-':16}{err}{mark}".rstrip())
            # every probe is an event, through the normal log path (redaction
            # applies); target_id rides along or the event is global.
            db.log_event(conn, args.target_id, "fuzz_probe",
                         detail=f"{param_name}={r['payload_name']} status={r['status']} "
                                f"{r['elapsed_ms']}ms sha={r['body_hash']}")
            if id(r) in anomalous:
                flagged.append((param_name, r, baseline_status))
    conn.commit()
    if truncated:
        print(f"(--max {args.max} reached: battery truncated)")
    if flagged:
        print(f"anomalies: {len(flagged)} of {total} probes")
        for param_name, r, baseline_status in flagged:
            print(f"!! anomaly: {param_name}={r['payload_name']} status={r['status']} "
                  f"(baseline {baseline_status})")
            print(f"   consider: hunt lead add --target <id> --title \"fuzz flinch: "
                  f"{param_name}={r['payload_name']}\" (leads stay manual — engine judgment)")
    else:
        print(f"anomalies: none — {total} probes came back clean")
    return 0


def cmd_status(args, conn) -> int:
    print(f"db {db.get_meta(conn, 'db_id')[:12]} created {db.get_meta(conn, 'db_created')}")
    targets = db.list_targets(conn)
    if not targets:
        print("(empty - add a target: hunt target add <name> <url>)")
    for t in targets:
        findings = db.list_findings(conn, t["id"])
        waves = db.list_waves(conn, t["id"])
        live = [f for f in findings if f["ladder_status"] == "proven-live"]
        print(f"#{t['id']} {t['name']:22} phase={t['phase']:10} ev={t['ev_score']:>5} | "
              f"findings={len(findings)} proven={len(live)} waves={len(waves)}")
        # Budget visibility (informational only, never a gate): how long the
        # target has been hunting and how many re-audits its waves recorded.
        # Budgets themselves are operator-set; this line only makes the spend
        # visible. A missing phase event skips the duration, not the line.
        if t["phase"] == "hunting":
            parts = []
            since = conn.execute(
                "SELECT created_at FROM events WHERE target_id=? AND kind='phase' "
                "AND detail LIKE '%-> hunting' ORDER BY id DESC LIMIT 1",
                (t["id"],),
            ).fetchone()
            if since is not None:
                duration = _fmt_duration(since["created_at"])
                if duration:
                    parts.append(f"hunting {duration}")
            reaudits = conn.execute(
                "SELECT COALESCE(SUM(reaudit_done), 0) AS n FROM waves WHERE target_id=?",
                (t["id"],),
            ).fetchone()["n"]
            parts.append(f"re-audits: {reaudits} (budgets are operator-set)")
            print("    " + " · ".join(parts))
        for f in findings:
            # L2.6: the ledger's own name is `proven-live` — the status line
            # prints it (once) instead of inventing a second status word. The
            # PROVEN[F-n] markers stay claim-gate vocabulary, untouched.
            mark = {"proven-live": "[proven-live]", "in-code": "[IN-CODE]",
                    "theoretical": "[THEORY]", "overturned": "[OVERTURNED]"}[f["ladder_status"]]
            print(f"    F-{f['id']} {mark:14} {f['severity']:8} {f['title']}")
        # honesty report: the contradiction engine lives in db.py (single source
        # of truth, including the RoE retroactive and tx_hash-mismatch flags) —
        # the CLI only displays what it returns.
        for line in db.find_contradictions(conn, t["id"]):
            print(f"    {line}")
    return 0


# --- conductor CLI (slice C2) ------------------------------------------------
# `hunt doctor` + the `hunt run` surface over the conductor kernel (slice C1:
# conductor.Conductor / summary.control_room_summary). The kernel modules are
# imported LAZILY inside the handlers so the rest of the CLI stays importable
# (and every non-conductor command keeps working) regardless of landing order;
# a missing kernel surfaces as a clean BLOCKED line, never a traceback.

# Adapter registry: registry key -> HuntAdapter class. `hunt doctor --adapter X`
# and `hunt run start --adapter X` validate against exactly this mapping.
CONDUCTOR_ADAPTERS = {"mock": MockAdapter}

# Harness integrations are deliberately explicit.  We inspect only configured
# skill destinations and the explicit adapter registry; we never scan running
# processes, credentials, PATH entries, or a target tree.
HARNESS_SKILL_ADAPTERS = ("claude-code", "zcode", "hermes")


def _adapter_registry_module():
    try:
        from ..conductor import registry
    except ImportError as exc:
        raise ValueError(f"BLOCKED: adapter registry not available ({exc})") from None
    return registry


def _build_adapter(name):
    """Resolve the built-in mock or a registered HUNT-ADAPTER/1 process."""
    cls = CONDUCTOR_ADAPTERS.get(name)
    if cls is not None:
        return cls()
    registry = _adapter_registry_module()
    try:
        return registry.build_registered_adapter(name)
    except TypeError:
        return registry.build_registered_adapter(name, registry.DEFAULT_REGISTRY_PATH)


def _close_adapter(adapter) -> None:
    close = getattr(adapter, "close", None)
    if callable(close):
        close()


def _adapter_preflight(name: str, *, smoke: bool = True) -> dict:
    """Run a bounded, side-effect-free adapter handshake before any run write."""
    adapter = _build_adapter(name)
    try:
        capabilities, diagnostics = adapter.doctor()
        if not capabilities.meets_managed_requirements() or not bool(
            capabilities.features.get("subagents")
        ):
            raise ValueError(
                "BLOCKED: adapter doctor failed managed capabilities "
                "(hunt_tool, post_output_hook, headless_turn, and subagents required)"
            )
        result = {
            "name": name,
            "adapter_id": capabilities.adapter_id,
            "version": capabilities.version,
            "features": dict(capabilities.features),
            "diagnostics": list(diagnostics),
            "status": "SIMULATED" if name == "mock" else "READY",
        }
        if not smoke:
            return result
        from ..conductor.schemas import AttemptCompleted, ToolRequest, ToolResult

        receipt = adapter.start_session({"session_id": "doctor-smoke", "doctor": True})
        mediated = completed = False
        try:
            for event in adapter.run_turn({
                "session_id": "doctor-smoke", "attempt_id": "doctor-attempt",
                "lane": "architect", "round": 1, "model_profile": "doctor",
                "prompt_hash": "0" * 64, "capsule_hash": "0" * 64,
                "capsule": {"doctor": True},
            }):
                if isinstance(event, ToolRequest):
                    adapter.submit_tool_result(
                        "doctor-attempt",
                        ToolResult(event.operation_id, "doctor smoke: exit 0\n", True),
                    )
                    mediated = True
                if isinstance(event, AttemptCompleted):
                    completed = True
        finally:
            adapter.stop_session(_capget(receipt, "session_id", "doctor-smoke"))
        if not mediated or not completed:
            raise ValueError(
                "BLOCKED: adapter doctor duplex smoke did not mediate and complete a turn"
            )
        result["duplex_smoke"] = "ok"
        return result
    finally:
        _close_adapter(adapter)


def cmd_harness(args, conn=None) -> int:
    """Discover and diagnose only explicitly supported harness integrations."""
    registry = _adapter_registry_module()
    if args.action == "list":
        print("mock (built-in; deterministic; simulated)")
        for name in HARNESS_SKILL_ADAPTERS:
            detail = "idea-injection; no process discovery" if name == "hermes" else "skills integration"
            print(f"{name} (built-in; {detail})")
        for entry in registry.list_adapters():
            print(f"{_capget(entry, 'name', '?')} (registered adapter)")
        return 0

    name = args.name
    if name in HARNESS_SKILL_ADAPTERS:
        # A known integration is not automatically a ready installation. Reuse
        # the existing installed-layer checklist before allowing guided intake.
        print(f"harness: {name}")
        return cmd_doctor(
            argparse.Namespace(adapter=name, scope="project", dir=None), conn
        )

    # The mock and registered names are the only names that may cross the
    # adapter boundary. _adapter_preflight owns capability, duplex, and cleanup
    # checks; unknown names fail closed without consulting PATH or processes.
    result = _adapter_preflight(name)
    print(f"harness: {result['name']}")
    print(f"adapter: {result['adapter_id']} v{result['version']}")
    print(f"status: {result['status']}")
    print("duplex smoke: ok")
    return 0


def _conductor_kernel():
    """Lazy import of the slice-C1 conductor kernel (fails clean when the
    modules are not on disk yet)."""
    try:
        from ..conductor.conductor import Conductor
        from ..conductor.summary import control_room_summary
    except ImportError as e:
        raise ValueError(f"BLOCKED: conductor kernel not available ({e})")
    return Conductor, control_room_summary


# --- L3.1: hunt install (wraps huntos.installer) ------------------------------
# The CLI delegates to the in-package installer module instead of forking its
# logic: huntos.installer ships inside the wheel, so the package is
# self-contained (no checkout, no file-location loading, stdlib only). Same
# flags, same exit contract: success = 0; conflict/refusal and failed --check
# = 1; argparse misuse = SystemExit(2). `install` never opens the hunt db
# (NO_DB_COMMANDS), so installing cannot create a db as a side effect.


def cmd_install(args, conn=None) -> int:
    """`hunt install` (L3.1): forward the parsed flags to huntos.installer's
    own parser. The installer prints its own output; its exit codes pass
    through unchanged (0 ok / 1 conflict or failed check). conn is always
    None — main() skips the db-open for this command."""
    from huntos import installer
    argv = ["--adapter", args.adapter, "--scope", args.scope, "--mode", args.mode]
    if args.dir:
        argv += ["--dir", args.dir]
    for flag in ("force", "check", "uninstall"):
        if getattr(args, flag):
            argv.append(f"--{flag}")
    try:
        return installer.main(argv) or 0
    except SystemExit as exc:
        # The installer signals failure with SystemExit(code) (its _fail
        # helper); preserve the documented exit contract instead of letting
        # SystemExit escape main().
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1


def cmd_help(args, conn) -> int:
    """`hunt help [verb]`: grouped command help, or per-verb examples.

    Read-only and db-free: help must work on a bare machine with no hunt db
    (the first thing a fresh install reaches for).  Bare `hunt help` prints
    the registry's grouped verb list; `hunt help <verb>` prints that verb's
    short help, copy-pasteable examples, and its NEXT hint.  An unknown verb
    is a BLOCKED ValueError (exit 2), matching the unknown-adapter contract.
    """
    from .registry import COMMAND_REGISTRY, grouped_help

    if not args.verb:
        print(grouped_help())
        print("macros (inside hunt shell): firstblood, wave, report")
        print("details: hunt help <verb> | hunt <verb> --help")
        return 0
    meta = COMMAND_REGISTRY.get(args.verb)
    if meta is None:
        raise ValueError(
            f"BLOCKED: unknown command {args.verb!r} — try 'hunt help' "
            "| NEXT: hunt help"
        )
    actions = f" ({'/'.join(meta['actions'])})" if meta["actions"] else ""
    print(f"{args.verb}{actions} — {meta['help']}")
    for example in meta["examples"]:
        print(f"  e.g. {example}")
    print(f"  next: {meta['next_hint']}")
    return 0


def cmd_shell(args, conn) -> int:
    # conn is always None; lazy import avoids a cycle while each line re-enters main().
    from .shell import run_shell
    return run_shell(args)


def cmd_adapter(args, conn=None) -> int:
    """Manage explicit HUNT-ADAPTER/1 executable registrations."""
    registry = _adapter_registry_module()
    if args.action == "list":
        print("mock (built-in; deterministic; not removable)")
        for entry in registry.list_adapters():
            name = _capget(entry, "name", "?")
            argv = [entry["executable"], *entry["args"]]
            print(f"{name}: {shlex.join(argv)}")
        return 0
    if args.action == "add":
        executable = Path(args.executable).expanduser()
        if not executable.is_absolute():
            raise ValueError("BLOCKED: adapter --exec must be an absolute path")
        argv = [str(executable), *args.arg]
        registry.add_adapter(args.name, str(executable), list(args.arg))
        print(f"adapter {args.name} added: {shlex.join(argv)}")
        return 0
    if args.action == "remove":
        if args.name == "mock":
            raise ValueError("BLOCKED: built-in mock adapter is not removable")
        if not registry.remove_adapter(args.name):
            raise ValueError(f"BLOCKED: adapter '{args.name}' is not registered")
        print(f"adapter {args.name} removed")
        return 0
    if args.action == "doctor":
        adapter = _build_adapter(args.name)
        try:
            return _cmd_adapter_doctor(adapter)
        finally:
            _close_adapter(adapter)
    raise ValueError(f"BLOCKED: unknown adapter action {args.action!r}")


def _cmd_adapter_doctor(adapter) -> int:
    capabilities, diagnostics = adapter.doctor()
    required = capabilities.meets_managed_requirements()
    subagents = bool(capabilities.features.get("subagents"))
    print(f"adapter: {capabilities.adapter_id} v{capabilities.version}")
    for key, enabled in capabilities.features.items():
        print(f"  {key}: {'on' if enabled else 'off'}")
    for line in diagnostics:
        print(f"  {line}")
    if not required or not subagents:
        raise ValueError(
            "BLOCKED: adapter doctor failed managed capabilities "
            "(hunt_tool, post_output_hook, headless_turn, and subagents required)"
        )
    from ..conductor.schemas import AttemptCompleted, ToolRequest, ToolResult

    session_id = "doctor-smoke"
    attempt_id = "doctor-attempt"
    receipt = adapter.start_session({"session_id": session_id, "doctor": True})
    completed = False
    mediated = False
    try:
        for event in adapter.run_turn({
            "session_id": session_id, "attempt_id": attempt_id, "lane": "architect",
            "round": 1, "model_profile": "doctor", "prompt_hash": "0" * 64,
            "capsule_hash": "0" * 64, "capsule": {"doctor": True},
        }):
            if isinstance(event, ToolRequest):
                adapter.submit_tool_result(
                    attempt_id, ToolResult(event.operation_id, "doctor smoke: exit 0\n", True)
                )
                mediated = True
            if isinstance(event, AttemptCompleted):
                completed = True
        if not mediated or not completed:
            raise ValueError("BLOCKED: adapter doctor duplex smoke did not mediate and complete a turn")
    finally:
        adapter.stop_session(_capget(receipt, "session_id", session_id))
    print("duplex smoke: ok")
    return 0


# --- L3.4: hunt doctor (the workspace preflight) ------------------------------
# Adapter names doctor understands. Deliberately NOT argparse choices: an
# unknown adapter stays a clean BLOCKED ValueError (exit 2), matching the
# conductor adapter registry behavior.
DOCTOR_ADAPTERS = ("claude-code", "zcode", "hermes", "generic", "mock")
# Adapters whose installed destination doctor inspects (--dir required for
# generic, exactly like install). hermes is the explicit no-op adapter.
SKILLS_ADAPTERS = ("claude-code", "zcode", "generic")

# The installed layer's fixed layout (huntos.installer constants, mirrored):
# everything lives under the `hunt-os` router dir inside the skills dir.
ROUTER_DIR_NAME = "hunt-os"
MANIFEST_NAME = ".hunt-os-manifest.json"


def resolve_installed_dest(adapter: str, scope: str, dir_override) -> Path:
    """Resolve the adapter's skills dir EXACTLY as `hunt install` does.

    Mirror of huntos.installer.resolve_skills_dir (same base dirs, same
    precedence: --dir wins, then <cwd|~>/<adapter base>); the parity test
    pins it against the installer's own function so they cannot drift."""
    if dir_override:
        return Path(dir_override)
    base = {"claude-code": ".claude/skills", "zcode": ".zcode/skills"}.get(adapter)
    if base is None:  # generic without --dir (parser rejects it upstream too)
        raise ValueError(f"BLOCKED: adapter {adapter!r} requires --dir")
    if scope == "user":
        return Path.home() / base
    return Path.cwd() / base


def _source_gate_path() -> Path:
    """The packaged claim gate shipped in the wheel (no-adapter doctor checks)."""
    return _DATA_ROOT / "bin" / "claim_gate.py"


def _source_hook_wrapper_path() -> Path:
    """The packaged hook pack wrapper (no-adapter doctor check)."""
    return _DATA_ROOT / "hooks" / "claim_gate_wrapper.sh"


def cmd_doctor(args, conn) -> int:
    """`hunt doctor` (L3.4): the workspace preflight. Each check prints
    `ok` or `FAIL: ...`; exit 2 when any check failed. Default = no adapter:
    the packaged claim gate and hook pack (huntos/_data) are checked, no
    installed destination is inferred, and no mock capability dump is printed.
    Diagnostic only: no provider calls, no network, and no writes to any
    manifest or hook file. The db connection is unused (main() skips the
    eager db-open for doctor; each check opens what it needs)."""
    adapter = args.adapter
    if adapter is not None and adapter not in DOCTOR_ADAPTERS:
        raise ValueError(
            f"BLOCKED: unknown adapter {adapter!r} — available adapters: "
            + ", ".join(DOCTOR_ADAPTERS)
        )
    if adapter == "generic" and not args.dir:
        # user-input failure, exactly like install: BLOCKED + exit 2 (law 2),
        # not a checklist FAIL line
        raise ValueError(
            "BLOCKED: --adapter generic requires --dir (exactly as for hunt install)"
        )
    fails = 0

    def report(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        if ok:
            print(f"{name}: ok" + (f" ({detail})" if detail else ""))
        else:
            fails += 1
            print(f"{name}: FAIL: {detail}")

    # -- 1. CLI import: the current entry can run — `hunt status` against the
    # current HUNT_DB without a traceback (empty db is ok; a corrupt db is
    # check 2's FAIL, not a traceback).
    try:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            main(["status"])
        report("cli-import", True)
    except Exception as exc:  # a traceback here IS the failure
        report("cli-import", False, f"hunt status raised: {type(exc).__name__}: {exc}")

    # -- 2 + 3. DB open (same handler shape as main()); project lock against
    # the opened db, evaluated in the operator's cwd. A mismatch FAILs but
    # the checklist continues.
    db_path = os.environ.get("HUNT_DB", os.path.expanduser("~/.huntos/hunt.db"))
    conn2 = None
    try:
        try:
            conn2 = db.connect()
            report("db-open", True)
        except (sqlite3.Error, OSError, ValueError) as e:
            report("db-open", False,
                   f"BLOCKED: cannot open the hunt db ({db_path}): {e}")
        cwd = os.getcwd()
        if conn2 is None:
            report("project-lock", False,
                   "cannot evaluate — the hunt db did not open")
        elif not os.path.exists(db.project_lock_path(cwd)):
            report("project-lock", True, "unbound")
        else:
            lock_msg = db.check_project_lock(conn2, cwd)
            report("project-lock", lock_msg is None,
                   "" if lock_msg is None else lock_msg)
    finally:
        if conn2 is not None:
            conn2.close()

    # -- 4..6. Adapter destination resolution: for claude-code/zcode/generic
    # the destination resolves EXACTLY as `hunt install` resolves it, and the
    # same resolved dir backs the manifest, installed-gate, and hook checks.
    # Without an adapter (or for the no-op hermes) nothing is inferred and the
    # packaged gate and hook pack (huntos/_data) are checked.
    dest = None
    if adapter in SKILLS_ADAPTERS:
        dest = resolve_installed_dest(adapter, args.scope, args.dir)
    gate = (dest / ROUTER_DIR_NAME / "hooks" / "claim_gate.py") if dest \
        else _source_gate_path()
    wrapper = (dest / ROUTER_DIR_NAME / "hooks" / "claim_gate_wrapper.sh") if dest \
        else _source_hook_wrapper_path()

    # -- 4. Claim gate: the resolved source or installed gate runs on empty
    # stdin and exits 0 (empty input never touches the db; fail-closed
    # behavior is the gate's own, byte-copied for installed layers).
    if not gate.is_file():
        report("claim-gate", False, f"claim gate not found at {gate}")
    else:
        try:
            proc = subprocess.run(
                [sys.executable, str(gate)], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            report("claim-gate", False, f"could not run {gate}: {exc}")
        else:
            if proc.returncode == 0:
                report("claim-gate", True)
            else:
                tail = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
                last = tail.splitlines()[-1] if tail else "(no output)"
                report("claim-gate", False,
                       f"exit {proc.returncode} on empty stdin: {last}")

    # -- 5. Skills layer: manifest present at the adapter destination.
    if adapter in SKILLS_ADAPTERS and dest is not None:
        manifest = dest / MANIFEST_NAME
        if manifest.is_file():
            report("skills-layer", True)
        else:
            report("skills-layer", False,
                   f"no {MANIFEST_NAME} in {dest} — run: hunt install "
                   f"--adapter {adapter} first")
    elif adapter == "hermes":
        # Hermes is the explicit no-op adapter: the layer is idea-injected
        # from the package, so there is nothing on disk to check — remind, never FAIL.
        print("skills-layer: ok (hermes is a no-op adapter — inject huntos/_data/idea/skills "
              "directly into every hunt session, reading huntos/_data/idea/IDEA.md and "
              "huntos/_data/idea/HUNT-BRIDGE.md as the idea layer; nothing is copied to disk)")

    # -- 6. Hook wrapper: the resolved installed wrapper exists and is runnable.
    if not wrapper.is_file():
        report("hook-wrapper", False,
               f"guarded mode unwired; see huntos/_data/hooks/README.md "
               f"(no wrapper at {wrapper})")
    elif os.access(wrapper, os.X_OK) or wrapper.suffix == ".sh":
        # runnable = executable bit (the installer chmods the installed copy
        # 0o755 on POSIX) or a .sh script invoked as `sh <file>` — the
        # documented attachment form, which needs no bit (a fresh checkout of
        # the source pack may legitimately be 0644).
        report("hook-wrapper", True)
    else:
        report("hook-wrapper", False,
               f"installed wrapper is not executable: {wrapper}")

    # -- 7. Conductor capability dump: ONLY for --adapter mock.
    if adapter == "mock":
        conductor_adapter = _build_adapter("mock")
        Conductor, _ = _conductor_kernel()
        capabilities, diagnostics = Conductor(conductor_adapter).doctor()
        print(f"adapter: {capabilities.adapter_id} v{capabilities.version}")
        for key, enabled in capabilities.features.items():
            print(f"  {key}: {'on' if enabled else 'off'}")
        print("diagnostics:")
        for line in diagnostics:
            print(f"  {line}")

    return 2 if fails else 0


def _adapter_for_session(conn, session_id: str):
    session = db.get_conductor_session(conn, session_id)
    if session is None:
        raise ValueError(
            f"BLOCKED: conductor session '{session_id}' does not exist "
            "| NEXT: hunt run status"
        )
    recorded = session["adapter_id"] or ""
    if recorded in {"mock", "mock-harness"}:
        return _build_adapter("mock")
    registry_name = session["adapter_registry_name"]
    if not registry_name:
        raise ValueError(
            f"BLOCKED: session {session_id} used adapter {recorded!r} but has no "
            "registry name for recovery"
        )
    return _build_adapter(registry_name)


def cmd_run(args, conn) -> int:
    """`hunt run ...`: the conductor operator surface. Refusals from the kernel
    (ValueError 'BLOCKED: ...') propagate to main()'s exit-2 handler untouched."""
    Conductor, control_room_summary = _conductor_kernel()
    from ..conductor.summary import control_room_page

    action = args.action

    if action == "start":
        # Preflight must pass before the conductor can create a ledger session.
        # This is intentionally bounded and adapter-only; no target/process/PATH
        # discovery is performed.
        _adapter_preflight(args.adapter)
        registry_name = None if args.adapter == "mock" else args.adapter
        adapter = _build_adapter(args.adapter)
        conductor = Conductor(adapter, adapter_registry_name=registry_name)
        try:
            session = conductor.start_run(
                conn, args.target, args.rounds,
                model_profile=args.model_profile,
                budget_per_attempt=args.budget_per_attempt,
            )
        finally:
            _close_adapter(adapter)
        sid = _capget(session, "id", "?")
        print(f"session {sid} -> status={_capget(session, 'status', '?')} "
              f"(target #{args.target}, rounds={args.rounds}, adapter={args.adapter})")
        if args.page:
            print(control_room_page(
                conn, sid, color=False if args.no_color else None, stream=sys.stdout
            ))
        else:
            print(control_room_summary(conn, sid))
        return 0

    if action == "status":
        if args.session is None:
            session = db.latest_conductor_session(conn)
            if session is None:
                raise ValueError(
                    "BLOCKED: no conductor sessions in this ledger — "
                    "start one: hunt run start --target <id> --rounds N"
                )
            print(f"(latest session {session['id']})")
            renderer = control_room_page if args.page else control_room_summary
            if args.page:
                print(renderer(
                    conn, session["id"], color=False if args.no_color else None,
                    stream=sys.stdout,
                ))
            else:
                print(renderer(conn, session["id"]))
            return 0
        # Existence is checked here so a bogus --session is a clean BLOCKED
        # even before the summary renderer runs.
        if db.get_conductor_session(conn, args.session) is None:
            raise ValueError(
                f"BLOCKED: conductor session '{args.session}' does not exist "
                "| NEXT: hunt run status"
            )
        if args.page:
            print(control_room_page(
                conn, args.session, color=False if args.no_color else None,
                stream=sys.stdout,
            ))
        else:
            print(control_room_summary(conn, args.session))
        return 0

    if action in ("pause", "resume", "abort"):
        adapter = _adapter_for_session(conn, args.session)
    elif action == "retry":
        recorded_attempt = db.get_conductor_attempt(conn, args.attempt)
        if recorded_attempt is None:
            raise ValueError(
                f"BLOCKED: conductor attempt '{args.attempt}' does not exist "
                "| NEXT: hunt run status"
            )
        adapter = _adapter_for_session(conn, recorded_attempt["session_id"])
    else:
        adapter = _build_adapter("mock")
    registry_name = None
    if action in ("pause", "resume", "abort"):
        recorded_session = db.get_conductor_session(conn, args.session)
        if recorded_session and recorded_session["adapter_id"] not in {"mock", "mock-harness"}:
            registry_name = recorded_session["adapter_registry_name"]
    elif action == "retry":
        recorded_session = db.get_conductor_session(conn, recorded_attempt["session_id"])
        if recorded_session and recorded_session["adapter_id"] not in {"mock", "mock-harness"}:
            registry_name = recorded_session["adapter_registry_name"]
    conductor = Conductor(adapter, adapter_registry_name=registry_name)

    if action in ("pause", "resume", "abort"):
        verb = {"pause": "paused", "resume": "resumed", "abort": "aborted"}[action]
        method = {"pause": conductor.pause_run,
                  "resume": conductor.resume_run,
                  "abort": conductor.abort_run}[action]
        try:
            session = method(conn, args.session)
            print(f"session {args.session} {verb} -> "
                  f"status={_capget(session, 'status', '?')}")
            return 0
        finally:
            _close_adapter(adapter)

    if action == "retry":
        try:
            attempt = conductor.retry_attempt(conn, args.attempt,
                                              model_profile=args.model_profile)
            print(f"retry -> attempt {_capget(attempt, 'id', '?')} "
                  f"status={_capget(attempt, 'status', '?')}")
            return 0
        finally:
            _close_adapter(adapter)

    if action == "reconcile":
        conductor.reconcile_attempt(conn, args.attempt, args.resolution)
        # reconcile_attempt returns the resolved INCIDENT row (no status key);
        # the promised "-> attempt status=..." suffix reads the attempt's
        # CURRENT status from the kernel instead (reconcile never auto-retries,
        # so an uncertain attempt stays 'uncertain' here by design).
        attempt = db.get_conductor_attempt(conn, args.attempt)
        line = (f"incident reconciled: attempt {args.attempt} "
                f"resolution={args.resolution}")
        status = _capget(attempt, "status")
        if status:
            line += f" -> attempt status={status}"
        print(line)
        return 0
    else:
        # Safety net: argparse restricts the action choices to the subparsers
        # today, so this is unreachable — but a future `run` subparser added
        # without a handler must fail loudly here instead of falling through
        # to a silent success.
        raise ValueError(f"BLOCKED: unknown run action {action!r}")


def main(argv=None) -> int:
    supplied_argv = list(sys.argv[1:] if argv is None else argv)
    bare = not supplied_argv
    p = argparse.ArgumentParser(prog="hunt", description="HUNT-OS - hunt framework state machine")
    # Identity flag (Phase 2): `hunt --show-context <verb> ...` prints the
    # same where-am-I line the shell prompt shows (target + phase + open
    # wave + session) to stderr before running the verb.  Read-only and
    # db-safe: the resolver opens the ledger mode=ro and never creates it.
    p.add_argument(
        "--show-context", action="store_true",
        help="print the current target/phase/wave/session line to stderr, then run",
    )
    # Machine surface (Phase 3, step 11): `hunt --json <verb> ...` emits the
    # refusal envelope {"ok","code","error","next"} to stdout instead of the
    # human BLOCKED line to stderr.  Human text stays the default; success
    # output is unchanged.  Exit codes: 0 ok, 1 installer conflict/check
    # failure, 2 every refusal + argparse misuse.
    p.add_argument(
        "--json", action="store_true",
        help="emit refusals as a JSON envelope {ok, code, error, next} on stdout",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("target", help="manage targets: add / list / roe / archive")
    # Per-action subparsers: same user-facing syntax as the old flat parser,
    # but wrong usage now fails at parse time with a usage message instead of
    # surfacing late as a runtime "not found" error.
    pt_sub = pt.add_subparsers(dest="action", required=True)

    pta = pt_sub.add_parser("add", help="add a target (starts in the scoring phase)")
    pta.add_argument("name")
    pta.add_argument("url")
    pta.add_argument("--chain", default="evm")
    pta.add_argument("--age-days", dest="age_days", type=int, default=0)
    pta.add_argument("--tvl", type=float, default=0)
    pta.add_argument("--notes", default="")
    pta.set_defaults(fn=cmd_target)

    ptp = pt_sub.add_parser(
        "prepare", help="classify and atomically record a URL, GitHub repository, or folder",
    )
    ptp.add_argument("source")
    ptp.add_argument("--name", default=None)
    ptp.add_argument("--chain", default="evm")
    ptp.add_argument("--hosts", default="")
    ptp.add_argument("--actions", default="recon,read")
    ptp.add_argument("--authorization-note", required=True)
    ptp.add_argument("--workspace-root", default=None,
                     help="GitHub checkout root (default: ~/.huntos/workspaces)")
    ptp.set_defaults(fn=cmd_target)

    ptl = pt_sub.add_parser("list", help="list targets (newest first)")
    ptl.set_defaults(fn=cmd_target)

    ptr = pt_sub.add_parser("roe", help="rules of engagement (default-deny for mutate)")
    ptr.add_argument("target_id", type=int)
    ptr.add_argument("--hosts", required=True,
                     help="rules of engagement hosts (INFORMATIONAL ONLY — only actions are enforced)")
    ptr.add_argument("--actions", required=True,
                     help="comma list from: recon, read, auth-test, mutate (default-deny for mutate)")
    ptr.add_argument("--notes", default="")
    ptr.set_defaults(fn=cmd_target)

    pta = pt_sub.add_parser(
        "archive",
        help="archive a target (deliberate close; requires a retro lesson). "
             "Normal completion walks the phases to retro; the economic stop stays "
             "available via wave close exhausted",
    )
    pta.add_argument("target_id", type=int)
    pta.add_argument("reason", nargs="+", help="why this hunt is closing (stored with the archive event)")
    pta.set_defaults(fn=cmd_target)

    ps = sub.add_parser("score", help="score a target's evidence (scoring phase only; ev must be > 0)")
    ps.add_argument("target_id", type=int)
    ps.add_argument("ev", type=float)
    ps.set_defaults(fn=cmd_score)

    pp = sub.add_parser("phase", help="advance the pipeline one phase (order + exit gates enforced)")
    pp.add_argument("target_id", type=int)
    pp.add_argument("phase", choices=["recon", "classify", "hunting", "verify", "report", "retro"])
    pp.set_defaults(fn=cmd_phase)

    pf = sub.add_parser("finding", help="the evidence ladder: add / promote / overturn / retitle")
    # Per-action subparsers: add/promote/overturn each get exactly the
    # arguments they need, so misuse fails at parse time (exit 2) instead of
    # surfacing late as a runtime "BLOCKED: not found: id = ?" error.
    pf_sub = pf.add_subparsers(dest="action", required=True)

    pfa = pf_sub.add_parser("add", help="record a theoretical finding (ladder starts here)")
    pfa.add_argument("target_id", type=int)
    pfa.add_argument("title")
    pfa.add_argument("klass")
    pfa.add_argument("--severity", choices=SEVERITY, default="info",
                     help="critical|high|medium|low|info (default: info; bad values fail at parse time)")
    pfa.add_argument("--notes", default="")
    # dest is `finding_action` because `action` is taken by the subcommand choice
    pfa.add_argument("--falsifier", default="",
                     help="the observation that would prove this finding wrong (recorded in the ledger)")
    pfa.add_argument("--action", dest="finding_action", choices=ROE_ACTIONS, default="read",
                     help="rules-of-engagement action scale (default: read)")
    pfa.add_argument("--surface", dest="surface", type=int, default=None,
                     help="attack-surface row this finding was found on (hunt surface add)")
    pfa.set_defaults(fn=cmd_finding)

    pfp = pf_sub.add_parser("promote", help="climb the evidence ladder (theoretical -> in-code -> proven-live)")
    pfp.add_argument("--id", dest="id", type=int, required=True)
    pfp.add_argument("--evidence-ref", dest="evidence_ref", required=True)
    pfp.add_argument("--poc-path", dest="poc_path", required=True)
    pfp.set_defaults(fn=cmd_finding)

    pfo = pf_sub.add_parser("overturn", help="adversary wins: status drops to overturned (audit trail kept)")
    pfo.add_argument("--id", dest="id", type=int, required=True)
    pfo.add_argument("--by", dest="by", required=True)
    pfo.set_defaults(fn=cmd_finding)

    pfret = pf_sub.add_parser(
        "retitle",
        help="retitle a finding (bookkeeping, not evidence — a mangled title is "
             "not an overturn; proven-live may retitle; BLOCKED overturned/archived)",
    )
    pfret.add_argument("--id", dest="id", type=int, required=True, help="finding id to retitle")
    pfret.add_argument("--title", dest="title", required=True,
                       help="the NEW title (secrets gate applies)")
    pfret.set_defaults(fn=cmd_finding)

    ppoc = sub.add_parser("poc", help="run a PoC inside the ledger (exit code + sha256 pinned; "
                                      "required before any promotion)")
    ppoc_sub = ppoc.add_subparsers(dest="action", required=True)
    ppr = ppoc_sub.add_parser(
        "run",
        help="run a PoC inside the ledger: exit code + output tail recorded, "
             "file sha256 pinned at run time (a poc_run event is required before "
             "a finding can promote)",
    )
    ppr.add_argument("--id", dest="id", type=int, required=True, help="finding id the PoC belongs to")
    ppr.add_argument("--poc-path", dest="poc_path", required=True, help="path to the PoC file")
    ppr.add_argument("--timeout", type=int, default=120,
                     help="seconds before the run is killed (default: 120)")
    ppr.set_defaults(fn=cmd_poc)

    pv = sub.add_parser("verify", help="record a verifier event on a finding (required before proven-live)")
    pv.add_argument("finding_id", type=int)
    pv.add_argument("artifact_type", choices=["fork_receipt", "tx_hash", "http_transcript"])
    pv.add_argument("body")
    pv.add_argument("--role", default="verifier")
    pv.set_defaults(fn=cmd_verify)

    pch = sub.add_parser("challenge", help="record an adversary review on a finding "
                                           "(required before proven-live)")
    pch.add_argument("finding_id", type=int)
    pch.add_argument("notes")
    pch.add_argument("--role", default="adversary")
    pch.set_defaults(fn=cmd_challenge)

    part = sub.add_parser("artifact", help="record a phase exit artifact (surface_map / attack_plan / "
                                           "disclosure_report), sha256-stamped in events")
    part.add_argument("target_id", type=int)
    part.add_argument("artifact_type", choices=sorted(set(PHASE_ARTIFACTS.values())))
    part.add_argument("path")
    part.set_defaults(fn=cmd_artifact)

    pw = sub.add_parser("wave", help="hunt waves: open / close / reaudit")
    pw_sub = pw.add_subparsers(dest="action", required=True)

    pwo = pw_sub.add_parser("open", help="open wave N+1 (BLOCKED until the previous wave is "
                                         "closed AND re-audited)")
    pwo.add_argument("target_id", type=int)
    pwo.add_argument("lanes")
    pwo.set_defaults(fn=cmd_wave)

    pwc = pw_sub.add_parser("close", help="close a wave with a verdict (findings_new is computed "
                                          "from wave-linked findings; exhausted archives)")
    pwc.add_argument("--wave-id", dest="wave_id", type=int, required=True)
    pwc.add_argument("--verdict", choices=["continue", "exhausted", "pivot"], required=True)
    pwc.set_defaults(fn=cmd_wave)

    pwr = pw_sub.add_parser("reaudit", help="record the wave's re-audit (min 20 chars; unlocks wave N+1)")
    pwr.add_argument("--wave-id", dest="wave_id", type=int, required=True)
    pwr.add_argument("--summary", required=True)
    pwr.set_defaults(fn=cmd_wave)

    pr = sub.add_parser("report", help="generate the target's disclosure report (markdown, "
                                       "sha256-fingerprinted; --out also stamps the artifact)")
    pr.add_argument("target_id", type=int)
    pr.add_argument("--out", default="")
    pr.set_defaults(fn=cmd_report)

    pvr = sub.add_parser("verify-report", help="verify a report file against its hunt-report "
                                               "sha256 footer (BLOCKED on tampering)")
    pvr.add_argument("file")
    pvr.set_defaults(fn=cmd_verify_report)

    pproj = sub.add_parser("project", help="workspace lock: bind this directory to the current "
                                           "db / show lock status")
    pproj_sub = pproj.add_subparsers(dest="action", required=True)
    ppb = pproj_sub.add_parser("bind", help="bind the current directory (.huntos-project) to "
                                            "the current db")
    ppb.set_defaults(fn=cmd_project)
    pps = pproj_sub.add_parser("status", help="show the workspace lock vs the current db")
    pps.set_defaults(fn=cmd_project)

    pl = sub.add_parser("lesson", help="lessons: add / list / reword (archive requires one "
                                       "bound to the target)")
    # Per-action subparsers: source + pattern are required on add (parse-time),
    # so `hunt lesson add` without a pattern no longer reaches the database.
    pl_sub = pl.add_subparsers(dest="action", required=True)

    pla = pl_sub.add_parser("add", help="record a lesson (archive requires one bound to the target)")
    pla.add_argument("source")
    pla.add_argument("pattern")
    pla.add_argument("--scope", default="skill")
    pla.add_argument("--notes", default="")
    pla.add_argument("--target-id", dest="target_id", type=int, default=None)
    pla.set_defaults(fn=cmd_lesson)

    pll = pl_sub.add_parser("list", help="list lessons (newest first)")
    pll.set_defaults(fn=cmd_lesson)

    plr2 = pl_sub.add_parser(
        "reword",
        help="rewrite a lesson's pattern (optionally --notes); allowed even on "
             "archived targets — memory corrections are not history rewrites",
    )
    plr2.add_argument("--id", dest="id", type=int, required=True, help="lesson id to reword")
    plr2.add_argument("--pattern", dest="pattern", required=True,
                      help="the NEW pattern (secrets gate applies)")
    plr2.add_argument("--notes", dest="notes", default=None,
                      help="optional replacement notes (omitted: notes stay unchanged)")
    plr2.set_defaults(fn=cmd_lesson)

    pk = sub.add_parser("klass", help="the klass taxonomy: list / add (growth is retro-gated)")
    pk_sub = pk.add_subparsers(dest="action", required=True)
    pkl = pk_sub.add_parser("list", help="list the taxonomy (klass allow-list as DATA)")
    pkl.set_defaults(fn=cmd_klass)
    pka = pk_sub.add_parser("add", help="grow the taxonomy at retro (--from-finding re-tags a "
                                        "quarantined 'Unknown' finding)")
    pka.add_argument("name")
    pka.add_argument("--from-finding", dest="from_finding", type=int, default=None)
    pka.set_defaults(fn=cmd_klass)

    pb = sub.add_parser("brief", help="opening read for the next hunt round (read-only)")
    pb.add_argument("target_id", type=int)
    pb.set_defaults(fn=cmd_brief)

    pn = sub.add_parser(
        "next",
        help="the ONE recommended next command for the hunt (read-only; never executes it)",
    )
    pn.add_argument("--target", dest="target", type=int, default=None,
                    help="target id (default: the single non-archived target; "
                         "BLOCKED listing ids when ambiguous)")
    pn.set_defaults(fn=cmd_next)

    pl2 = sub.add_parser("lead", help="the lead lifecycle: add / set-half / mutate / next / "
                                      "park / kill / promote / list")
    pl2_sub = pl2.add_subparsers(dest="action", required=True)

    pla2 = pl2_sub.add_parser("add", help="register an observation (payload optional at add, "
                                          "required before the mutation loop)")
    pla2.add_argument("--target", dest="target", type=int, required=True)
    pla2.add_argument("--title", required=True)
    pla2.add_argument("--payload", default="")
    pla2.add_argument("--precondition", dest="precondition", action="append", default=None,
                      help="'variable|value|description'; repeatable")
    pla2.add_argument("--surface", dest="surface", type=int, default=None,
                      help="attack-surface row this lead was found on (hunt surface add)")
    pla2.set_defaults(fn=cmd_lead)

    plh = pl2_sub.add_parser("set-half", help="set a half's verdict by hand "
                                              "('ambiguous' is oracle-exclusive)")
    plh.add_argument("--lead", dest="lead", type=int, required=True)
    plh.add_argument("--half", choices=["trigger", "impact"], required=True)
    plh.add_argument("--verdict", choices=["proven", "refuted"], required=True,
                     help="manual verdicts: proven|refuted only ('ambiguous' needs the oracle)")
    plh.add_argument("--evidence", required=True)
    plh.set_defaults(fn=cmd_lead)

    plm = pl2_sub.add_parser("mutate", help="one step of the mutation loop (anti-repeat on "
                                            "(variable, new_value); unknown must plan a new precondition)")
    plm.add_argument("--lead", dest="lead", type=int, required=True)
    plm.add_argument("--variable", required=True)
    plm.add_argument("--old", dest="old", default="")
    plm.add_argument("--new", dest="new", required=True)
    plm.add_argument("--result", choices=list(db.MUTATION_RESULTS), required=True)
    plm.add_argument("--evidence", required=True)
    plm.add_argument("--plan", default=None,
                     help="'variable|value|description' — REQUIRED when --result unknown "
                          "(the unknown gives birth to a new precondition)")
    plm.add_argument("--resolve", dest="resolve", type=int, default=None,
                     help="precondition id to mark 'present' alongside this mutation")
    plm.set_defaults(fn=cmd_lead)

    pls = pl2_sub.add_parser("set", help="set the payload of an active lead (required before "
                                         "the mutation loop when add left it empty)")
    pls.add_argument("--lead", dest="lead", type=int, required=True)
    pls.add_argument("--payload", required=True)
    pls.set_defaults(fn=cmd_lead)

    pln = pl2_sub.add_parser("next", help="the deterministic next mutation (first missing, "
                                          "never-tried precondition)")
    pln.add_argument("--lead", dest="lead", type=int, required=True)
    pln.set_defaults(fn=cmd_lead)

    plp = pl2_sub.add_parser("park", help="park with a mandatory testable retrigger condition")
    plp.add_argument("--lead", dest="lead", type=int, required=True)
    plp.add_argument("--retrigger", required=True, help="'observable :: check'")
    plp.set_defaults(fn=cmd_lead)

    plr = pl2_sub.add_parser("reopen", help="parked -> open: the tripwire fired, "
                                            "wake the lead (E1/R2-04)")
    plr.add_argument("--lead", dest="lead", type=int, required=True)
    plr.add_argument("--evidence", required=True,
                     help="the observation that fired the retrigger condition")
    plr.set_defaults(fn=cmd_lead)

    plk = pl2_sub.add_parser("kill", help="kill a lead (both halves refuted + evidence); "
                                          "a one-sided kill is refused -> auto-park")
    plk.add_argument("--lead", dest="lead", type=int, required=True)
    plk.add_argument("--trigger-refutation", dest="trigger_refutation", required=True)
    plk.add_argument("--impact-refutation", dest="impact_refutation", required=True)
    plk.add_argument("--retrigger", default=None,
                     help="'observable :: check' — required for the auto-park on a refused kill")
    plk.set_defaults(fn=cmd_lead)

    plp2 = pl2_sub.add_parser("promote", help="lead -> finding (both halves proven; frozen "
                                              "provenance snapshot)")
    plp2.add_argument("--lead", dest="lead", type=int, required=True)
    plp2.add_argument("--klass", required=True)
    # E22: dest must NOT be "action" — the lead subparsers dispatch on
    # args.action ("add"/"set-half"/.../), so a flag named --action silently
    # overwrote the dispatch and turned promote into a rc=0 no-op. The RoE
    # action rides as --roe-action.
    plp2.add_argument("--roe-action", dest="roe_action", required=True,
                      choices=["read", "mutate", "auth-test"],
                      help="R2-02/E22: no silent default — a mutate-flavored lead "
                           "must be declared mutate at promote time, so the RoE "
                           "default-deny gate fires exactly as it does for "
                           "direct findings")
    plp2.add_argument("--severity", choices=SEVERITY, required=True)
    plp2.set_defaults(fn=cmd_lead)

    pll2 = pl2_sub.add_parser("list", help="list a target's leads")
    pll2.add_argument("--target", dest="target", type=int, required=True)
    pll2.set_defaults(fn=cmd_lead)

    po = sub.add_parser("oracle", help="deterministic observation oracle (baseline vs candidate "
                                       "feature JSON)")
    po.add_argument("--lead", dest="lead", type=int, default=None)
    po.add_argument("--finding", dest="finding", type=int, default=None)
    po.add_argument("--half", choices=["trigger", "impact"], required=True)
    po.add_argument("--baseline", required=True, help="path to the baseline feature JSON")
    po.add_argument("--candidate", required=True, help="path to the candidate feature JSON")
    po.set_defaults(fn=cmd_oracle)

    psurf = sub.add_parser("surface", help="the attack-surface ledger: add / list")
    psurf_sub = psurf.add_subparsers(dest="action", required=True)
    psa = psurf_sub.add_parser("add", help="record an attack-surface row "
                                           "(kind from db.SURFACE_KINDS)")
    psa.add_argument("target_id", type=int)
    psa.add_argument("kind", choices=SURFACE_KINDS,
                     help="endpoint | trust_boundary | invariant | component")
    psa.add_argument("name")
    psa.add_argument("--notes", default="")
    psa.set_defaults(fn=cmd_surface)
    psl = psurf_sub.add_parser("list", help="list a target's surfaces")
    psl.add_argument("target_id", type=int)
    psl.set_defaults(fn=cmd_surface)

    pcov = sub.add_parser("coverage", help="per-surface lead/finding coverage + blind spots "
                                           "(trust boundaries never probed)")
    pcov.add_argument("target_id", type=int)
    pcov.set_defaults(fn=cmd_coverage)

    pchain = sub.add_parser("chain", help="the 0-day claim engine: add / link / show / novelty")
    pchain_sub = pchain.add_subparsers(dest="action", required=True)
    pcha = pchain_sub.add_parser("add", help="open a chain: entry -> linked steps -> impact")
    pcha.add_argument("target_id", type=int)
    pcha.add_argument("name")
    pcha.add_argument("--entry", dest="entry", default="",
                      help="the entry point the chain starts from")
    pcha.add_argument("--impact", dest="impact", default="",
                      help="the claimed end impact of the chain")
    pcha.add_argument("--notes", default="")
    pcha.set_defaults(fn=cmd_chain)
    pchl = pchain_sub.add_parser("link", help="attach a step: <chain_id> <position> <finding|lead> <ref_id>")
    pchl.add_argument("chain_id", type=int)
    pchl.add_argument("position", type=int)
    pchl.add_argument("kind", choices=["finding", "lead"])
    pchl.add_argument("ref_id", type=int)
    pchl.set_defaults(fn=cmd_chain)
    pchs = pchain_sub.add_parser("show", help="render the chain (markdown)")
    pchs.add_argument("chain_id", type=int)
    pchs.set_defaults(fn=cmd_chain)
    pchn = pchain_sub.add_parser("novelty", help="has this (class, entry, impact) pattern "
                                                 "appeared in the ledger before?")
    pchn.add_argument("chain_id", type=int)
    pchn.set_defaults(fn=cmd_chain)

    pfz = sub.add_parser("fuzz", help="fire the doctrine edge-case battery at one endpoint "
                                      "parameter (anomalies print !! lines; leads stay manual)")
    pfz.add_argument("--url", required=True, help="target endpoint (practice targets: localhost only)")
    pfz.add_argument("--method", default="GET", help="HTTP method for every probe (default: GET)")
    pfz.add_argument("--param", dest="param", action="append", default=None,
                     help="parameter to fuzz (query var for GET, form field for POST; "
                          "default: 'q'); repeatable — one battery per --param")
    pfz.add_argument("--timeout", type=float, default=10.0,
                     help="per-request timeout in seconds (default: 10)")
    pfz.add_argument("--target-id", dest="target_id", type=int, default=None,
                     help="attribute the fuzz_probe events to a target (default: global)")
    pfz.add_argument("--max", type=int, default=12,
                     help="max probes fired in total, baseline included (default: 12)")
    pfz.set_defaults(fn=cmd_fuzz)

    pst = sub.add_parser("status", help="the full ledger picture + contradiction report (read-only)")
    pst.set_defaults(fn=cmd_status)

    # --- L3.1: hunt install (delegates to huntos.installer) ---
    pi = sub.add_parser(
        "install",
        help="install the HUNT-OS skills layer into a harness (delegates to "
             "huntos.installer: additive, manifest-tracked, same flags and "
             "exit codes; needs no hunt db)",
    )
    pi.add_argument(
        "--adapter", required=True,
        choices=("claude-code", "zcode", "hermes", "generic"),
        help="target harness adapter (hermes = no-op idea-injection pointer; "
             "generic requires --dir)",
    )
    pi.add_argument(
        "--scope", choices=("project", "user"), default="project",
        help="project (<cwd>/.<adapter>/skills) or user (~/.<adapter>/skills); "
             "default: project",
    )
    pi.add_argument(
        "--mode", choices=("router", "native"), default="router",
        help="router = one 'hunt-os' skill with the full corpus, roles, and "
             "hook pack nested inside (default); native = one "
             "hunt-<category>-<name> skill per skill PLUS the router",
    )
    pi.add_argument(
        "--dir", default=None,
        help="override the base skills dir (works for every adapter; "
             "required for generic)",
    )
    pi.add_argument(
        "--force", action="store_true",
        help="overwrite existing files even if they are not in a previous "
             "HUNT-OS manifest",
    )
    pi.add_argument(
        "--check", action="store_true",
        help="verify every manifest file hash (roles and hooks included); "
             "exit 1 on drift",
    )
    pi.add_argument(
        "--uninstall", action="store_true",
        help="remove exactly the manifest's files (and now-empty dirs)",
    )
    pi.set_defaults(fn=cmd_install)

    # --- safe harness discovery and diagnosis ---
    pharness = sub.add_parser(
        "harness", help="list or diagnose built-in and explicitly registered harnesses",
    )
    pharness_sub = pharness.add_subparsers(dest="action", required=True)
    phl = pharness_sub.add_parser("list", help="list safe, explicit harness integrations")
    phl.set_defaults(fn=cmd_harness)
    phd = pharness_sub.add_parser("doctor", help="diagnose one explicit harness")
    phd.add_argument("name")
    phd.set_defaults(fn=cmd_harness)

    # --- managed adapter registry ---
    padapter = sub.add_parser(
        "adapter", help="register and diagnose HUNT-ADAPTER/1 executables",
    )
    padapter_sub = padapter.add_subparsers(dest="action", required=True)
    pada = padapter_sub.add_parser("add", help="register an absolute executable argv")
    pada.add_argument("name")
    pada.add_argument("--exec", dest="executable", required=True)
    pada.add_argument("--arg", action="append", default=[])
    pada.set_defaults(fn=cmd_adapter)
    padl = padapter_sub.add_parser("list", help="list built-in and registered adapters")
    padl.set_defaults(fn=cmd_adapter)
    padd = padapter_sub.add_parser("doctor", help="verify protocol and managed capabilities")
    padd.add_argument("name")
    padd.set_defaults(fn=cmd_adapter)
    padr = padapter_sub.add_parser("remove", help="remove a registered adapter")
    padr.add_argument("name")
    padr.set_defaults(fn=cmd_adapter)

    # --- conductor (slice C2) ---
    pdoc = sub.add_parser(
        "doctor",
        help="workspace preflight: cli, db, project lock, claim gate, skills "
             "layer, hook wrapper — each prints ok / FAIL; --adapter mock adds "
             "the conductor capability dump",
    )
    pdoc.add_argument(
        "--adapter", default=None,
        help="claude-code|zcode|generic checks the installed layer, resolved "
             "exactly as hunt install resolves it; hermes prints the "
             "idea-injection reminder (no-op adapter); mock opts into the "
             "conductor capability dump (default: workspace preflight, no "
             "adapter checks)",
    )
    pdoc.add_argument(
        "--scope", choices=("project", "user"), default="project",
        help="scope used to resolve the adapter destination (default: project)",
    )
    pdoc.add_argument(
        "--dir", default=None,
        help="override the base skills dir (required for --adapter generic, "
             "exactly as for hunt install)",
    )
    pdoc.set_defaults(fn=cmd_doctor)

    pshell = sub.add_parser(
        "shell",
        help="interactive operator console (macros, script mode)",
    )
    pshell.add_argument(
        "--script", metavar="FILE", default=None,
        help="replay one command per line; # comments; stop fail-closed on first nonzero",
    )
    pshell.add_argument(
        "--guided", action="store_true",
        help="start the target wizard after the banner (interactive TTY only)",
    )
    pshell.add_argument(
        "--no-hint", dest="hint", action="store_false",
        help="do not show hunt next after successful writes",
    )
    pshell.add_argument(
        "--quiet", action="store_true",
        help="suppress the startup banner",
    )
    pshell.add_argument(
        "--no-history", dest="no_history", action="store_true",
        help="do not read or write readline history",
    )
    pshell.set_defaults(fn=cmd_shell)

    phelp = sub.add_parser(
        "help",
        help="grouped command help, or per-verb examples: hunt help [verb]",
    )
    phelp.add_argument(
        "verb", nargs="?", default=None,
        help="show examples and the NEXT hint for one command",
    )
    phelp.set_defaults(fn=cmd_help)

    prun = sub.add_parser("run", help="the conductor: start / status / pause / resume / "
                                      "abort / retry / reconcile")
    prun_sub = prun.add_subparsers(dest="action", required=True)

    prs = prun_sub.add_parser("start", help="open a conductor session and drive the loop "
                                            "(prints session id, final status, summary)")
    prs.add_argument("--target", dest="target", type=int, required=True)
    prs.add_argument("--rounds", type=int, required=True)
    prs.add_argument("--adapter", default="mock", help="adapter registry key (default: mock)")
    prs.add_argument("--model-profile", dest="model_profile", default="mock",
                     help="model profile for the attempts (default: mock)")
    prs.add_argument("--budget-per-attempt", dest="budget_per_attempt", type=int, default=None,
                     help="token budget per attempt (default: unlimited)")
    prs.add_argument("--page", action="store_true",
                     help="render the static four-lane page instead of the legacy summary")
    prs.add_argument("--no-color", action="store_true",
                     help="disable ANSI decoration on the page")
    prs.set_defaults(fn=cmd_run)

    prst2 = prun_sub.add_parser("status", help="control-room summary "
                                               "(default: the latest session)")
    prst2.add_argument("--session", dest="session", default=None,
                       help="session id (default: latest_conductor_session)")
    prst2.add_argument("--page", action="store_true",
                       help="render the static four-lane page instead of the legacy summary")
    prst2.add_argument("--no-color", action="store_true",
                       help="disable ANSI decoration on the page")
    prst2.set_defaults(fn=cmd_run)

    for verb in ("pause", "resume", "abort"):
        prx = prun_sub.add_parser(verb, help=f"{verb} a conductor session")
        prx.add_argument("--session", dest="session", required=True)
        prx.set_defaults(fn=cmd_run)

    prr = prun_sub.add_parser("retry", help="re-run an interrupted/uncertain attempt "
                                            "(minted a NEW attempt id)")
    prr.add_argument("--attempt", dest="attempt", required=True)
    prr.add_argument("--model-profile", dest="model_profile", default=None,
                     help="override the model profile for the retry (default: inherit)")
    prr.set_defaults(fn=cmd_run)

    prc = prun_sub.add_parser("reconcile", help="resolve the incident on an uncertain attempt")
    prc.add_argument("--attempt", dest="attempt", required=True)
    prc.add_argument("--resolution", required=True,
                     help="how the incident was resolved (non-empty; stored in the ledger)")
    prc.set_defaults(fn=cmd_run)

    if bare:
        stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
        stdout_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        if stdin_tty and stdout_tty:
            supplied_argv = ["shell", "--guided"]
        else:
            p.print_help()
            return 2
    args = p.parse_args(supplied_argv)
    if args.show_context:
        # Identity line (Phase 2): the same where-am-I the shell prompt
        # shows.  Emitted to stderr so stdout stays machine-clean; the
        # resolver never writes and never creates a missing db.
        from .context import format_context_line, resolve_context

        print(format_context_line(resolve_context()), file=sys.stderr)
    # L3: `install`, `doctor`, and `shell` skip the eager db-open/lock path.
    # install must not create a db as a side effect; doctor's checklist owns
    # its own db handling (a corrupt db is a FAIL line, not a global BLOCKED).
    # Shell opens no db itself: each entered line returns through main().
    conn = None
    if args.cmd not in NO_DB_COMMANDS:
        try:
            conn = db.connect()
        except (sqlite3.Error, OSError, ValueError) as e:
            # A8: a bad HUNT_DB (a text file, an unreadable path) must speak the
            # same BLOCKED contract, not leak a traceback from connect(). ValueError
            # added (E3): db.connect() wraps corrupt/foreign db files as ValueError
            # ("BLOCKED: cannot open hunt db ...") — sqlite3.Error only catches the
            # directory-path case, so a garbage FILE leaked a raw traceback.
            path = os.environ.get("HUNT_DB", os.path.expanduser("~/.huntos/hunt.db"))
            _emit_refusal(_blocked_line(f"cannot open the hunt db ({path}): {e}"), args.json)
            return 2
    try:
        # Workspace lock (P5): the db is the project's single notebook. A
        # .huntos-project in cwd pins the workspace to one db_id; a mismatch
        # blocks every command before it runs. Exceptions:
        #   - the `project` group bypasses the lock (otherwise no rebind);
        #   - read-only commands and read-only ACTIONS of mixed groups
        #     (`target list`, `klass list`, `chain show`, `run status`, ...)
        #     pass with a hard warning line, still exit 0 — L1.2: inspecting
        #     state must not require rebinding first, but `target add` and
        #     friends stay lock-blocked (the action decides, not the group).
        #   - install/doctor/shell never open a db (NO_DB_COMMANDS), so there is
        #     no lock to check; doctor reports the lock as its own checklist item,
        #     while each command entered in shell re-enters main() independently.
        if conn is not None and args.cmd != "project":
            lock_msg = db.check_project_lock(conn, os.getcwd())
            if lock_msg is not None:
                if _is_read_only(args):
                    detail = lock_msg[len("BLOCKED: "):] if lock_msg.startswith("BLOCKED: ") else lock_msg
                    print(f"WARNING: {detail} (read-only command — allowed)", file=sys.stderr)
                else:
                    _emit_refusal(_blocked_line(lock_msg), args.json)
                    return 2
        rc = args.fn(args, conn)
    except ValueError as e:
        # Phase 3: every refusal speaks the unified BLOCKED|NEXT shape via
        # cli/errors.py.  blocked() is idempotent — a message that already
        # carries the prefix (or a NEXT suffix from an audited raise site)
        # passes through without doubling.  --json emits the machine
        # envelope {ok, code, error, next} to stdout instead.
        _emit_refusal(_blocked_line(str(e)), args.json)
        return 2
    except sqlite3.Error as e:
        # A8: db-level failures (locked database, integrity violations, a
        # foreign db) speak the same contract as the gates.
        _emit_refusal(_blocked_line(f"database error: {e}"), args.json)
        return 2
    except OSError as e:
        # A8: report --out into a missing directory, unreadable files, ...
        # every user-input failure is a BLOCKED line, never a traceback.
        _emit_refusal(_blocked_line(str(e)), args.json)
        return 2
    finally:
        if conn is not None:
            conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
