#!/usr/bin/env python3
"""Claim gate - guard the engine's mouth.

A harness-agnostic hook: reads an AI engine's output (stdin, or a file path
in argv[1]) and vetoes the turn when the text makes strong claims the hunt db
cannot back. Markers: PROVEN, EXPLOITABLE (exact, case-sensitive) plus the
phrase "admin takeover" (case-insensitive). Every claim must name its object:
either an explicit bind — findings as PROVEN[F-3] / EXPLOITABLE[F-3], leads as
PROVEN[L-2] (v0.4, I13) — the marker immediately followed by the bracketed id,
which is the authoritative binding for that occurrence, or, as a fallback for
bare markers, the nearest finding id (F-<n> / #<n>) nearby (same line or 80
chars around; L-<n> occurrences are invisible to that scan). A finding-bound
claim passes only if that finding is 'proven-live'; a lead-bound claim passes
only if that lead's state is 'promoted'; an unbound claim is a veto, always —
proof of some other finding somewhere in the db backs a claim that names
nothing (the db decides which claims are proven). The db (HUNT_DB, default
~/.huntos/hunt.db) is opened read-only; missing/unreadable db is FAIL-CLOSED.
When a `.huntos-project` lock exists in the working directory, the opened db
is also verified against it (hunt project bind) — a fabricated HUNT_DB cannot
pass in a bound workspace.
Exit 0 = pass, 2 = veto. The packaged hook wrapper and wiring guide live in
huntos/_data/hooks/README.md; installed wrappers use only their adjacent
byte-copied gate and never fall back to a checkout or fetch remote code.

"""
from __future__ import annotations

import bisect
import json
import os
import re
import sqlite3
import sys
import urllib.parse

DEFAULT_DB = "~/.huntos/hunt.db"
NEIGHBORHOOD = 80  # chars of context around a marker where an id may live
PASS_LINE = "claim gate: no unbacked claims"
_LOCK_FILENAME = ".huntos-project"  # written by `hunt project bind`

# PROVEN / EXPLOITABLE are exact, case-sensitive tokens; the takeover phrase
# is not. Word boundaries keep ordinary prose ("unproven", "nonexploitable",
# lowercase "proven") clean.
_MARKERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bPROVEN\b"), "PROVEN"),
    (re.compile(r"\bEXPLOITABLE\b"), "EXPLOITABLE"),
    (re.compile(r"\badmin takeover\b", re.IGNORECASE), "admin takeover"),
)
_FINDING_ID = re.compile(r"(?:\bF-|#)(\d+)\b")
# v0.4 (I13): a lead binding. `L-<n>` (NEVER `#n`, which would collide with
# finding ids). A marker bound to a lead passes only when that lead's state is
# 'promoted' — a lead claim rides the lead's own state, not some finding's.
_LEAD_ID = re.compile(r"\bL-(\d+)\b")


def read_input(argv: list[str]) -> str:
    """Engine output: the argv[1] file, else stdin. No input -> empty string."""
    if len(argv) > 1:
        try:
            with open(argv[1], "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError as exc:
            print(f"BLOCKED: claim gate cannot read input file '{argv[1]}' ({exc})",
                  file=sys.stderr)
            raise SystemExit(2)  # fail-closed: an unvettable input cannot pass
    if sys.stdin is None or sys.stdin.isatty():
        return ""  # nothing piped
    return sys.stdin.read()


def nearest_binding(text: str, marker: re.Match[str]) -> tuple[int | None, int | None]:
    """Nearest object id around a marker: (finding_id, lead_id); at most one set.

    A fair distance race between finding ids (F-<n> / #<n>) and lead ids
    (L-<n>) in the window; on a distance tie the finding id wins (the v0.3
    behavior stays unchanged). Bare-marker fallback only — explicit binds
    never reach this scan."""
    line_start = text.rfind("\n", 0, marker.start()) + 1
    line_end = text.find("\n", marker.end())
    if line_end == -1:
        line_end = len(text)
    # neighborhood = the marker's own line, widened by NEIGHBORHOOD chars
    lo = max(0, min(line_start, marker.start() - NEIGHBORHOOD))
    hi = min(len(text), max(line_end, marker.end() + NEIGHBORHOOD))
    window = text[lo:hi]
    at = marker.start() - lo
    best_f: tuple[int, int] | None = None  # (distance, id)
    best_l: tuple[int, int] | None = None
    for m in _FINDING_ID.finditer(window):
        dist = min(abs(m.start() - at), abs(m.end() - at))
        if best_f is None or dist < best_f[0]:
            best_f = (dist, int(m.group(1)))
    for m in _LEAD_ID.finditer(window):
        dist = min(abs(m.start() - at), abs(m.end() - at))
        if best_l is None or dist < best_l[0]:
            best_l = (dist, int(m.group(1)))
    if best_f is not None and best_l is not None:
        if best_l[0] < best_f[0]:
            return (None, best_l[1])
        return (best_f[1], None)  # tie -> finding (unchanged behavior)
    if best_f is not None:
        return (best_f[1], None)
    if best_l is not None:
        return (None, best_l[1])
    return (None, None)


def _explicit_bind_id(text: str, m: re.Match[str]) -> int | None:
    """The id of an explicit bind (PROVEN[F-3] / EXPLOITABLE[F-3]), or None.

    The bind syntax is the marker immediately followed by the bracketed finding
    id; when present it is THE bound finding for that occurrence and the
    nearest-id heuristic is not consulted. Defined for the PROVEN and
    EXPLOITABLE tokens only (the takeover phrase has no bracket form).
    """
    if m.group(0) not in ("PROVEN", "EXPLOITABLE"):
        return None
    # E5: bound the slice — text[m.end():] on a 5 MB single-line dump copied
    # the whole tail per marker (O(M×N)). The bracket (if any) is adjacent.
    bracket = re.match(r"\[F-(\d+)\]", text[m.end():m.end() + 16])
    return int(bracket.group(1)) if bracket else None


def _explicit_lead_bind(text: str, m: re.Match[str]) -> int | None:
    """The lead id of an explicit lead bind (PROVEN[L-2]), or None.

    The lead bind syntax is the marker immediately followed by the bracketed
    lead id; when present it is THE binding for that occurrence (over both the
    finding bind and the nearest-id heuristic). Same bracket form as the
    finding bind, disambiguated by the L- prefix."""
    if m.group(0) not in ("PROVEN", "EXPLOITABLE"):
        return None
    # E5: bounded slice, same reason as _explicit_bind_id.
    bracket = re.match(r"\[L-(\d+)\]", text[m.end():m.end() + 16])
    return int(bracket.group(1)) if bracket else None


def claims(text: str) -> list[tuple[str, int | None, int | None]]:
    """One (marker, finding id | None, lead id | None) triple per occurrence.

    Binding precedence: explicit lead bind (PROVEN[L-2]) > explicit finding
    bind (PROVEN[F-3]) > nearest finding id in the window. At most one of the
    two ids is set.

    E5 (batch 3): all finding/lead id positions are collected in ONE pass over
    the text per id kind (O(N)), then each bare marker's nearest id is a linear
    scan over the positions inside its window (positions are globally sorted,
    so window slices stay sorted). The old shape re-scanned the full text per
    marker — O(M×N), ~100 s at 5 MB / 900 markers; the return shape is
    unchanged."""
    out: list[tuple[str, int | None, int | None]] = []
    # One pass per id kind: (start, end, id) — globally sorted by position.
    fpos = [(m.start(), m.end(), int(m.group(1))) for m in _FINDING_ID.finditer(text)]
    lpos = [(m.start(), m.end(), int(m.group(1))) for m in _LEAD_ID.finditer(text)]
    fstarts = [p[0] for p in fpos]
    lstarts = [p[0] for p in lpos]
    # E5: newline positions too — line bounds come from bisect, not two full
    # rfind/find scans per marker (O(N) each on long-line dumps).
    nl = [m.start() for m in re.finditer("\n", text)]

    def line_bounds(start: int, end: int) -> tuple[int, int]:
        line_start = nl[bisect.bisect_left(nl, start) - 1] + 1 if bisect.bisect_left(nl, start) else 0
        j = bisect.bisect_left(nl, end)
        line_end = nl[j] if j < len(nl) else len(text)
        return line_start, line_end

    def nearest_from_positions(
            positions: list[tuple[int, int, int]],
            starts: list[int], at: int, lo: int, hi: int) -> tuple[int, int] | None:
        """(distance, id) of the nearest id occurrence fully inside [lo, hi).

        Same match semantics as the old window re-scan (a regex match counts
        only when it lies entirely inside the window), but the candidates come
        from the precomputed position list via bisect — the text itself is
        never re-scanned. Positions are sorted by start, so the window slice
        is a contiguous run: O(log K + W)."""
        best: tuple[int, int] | None = None
        i = bisect.bisect_left(starts, lo)
        while i < len(positions):
            start, end, gid = positions[i]
            if start >= hi:
                break
            if end <= hi:  # fully inside the window (and start >= lo by bisect)
                dist = min(abs(start - at), abs(end - at))
                if best is None or dist < best[0]:
                    best = (dist, gid)
            i += 1
        return best

    for pattern, label in _MARKERS:
        for m in pattern.finditer(text):
            lid = _explicit_lead_bind(text, m)
            if lid is not None:
                out.append((label, None, lid))
                continue
            fid = _explicit_bind_id(text, m)
            if fid is None:
                # bare marker: the nearest id wins — finding or lead, by
                # distance (same race, same tie rule, from precomputed
                # positions instead of a re-scan of the text).
                line_start, line_end = line_bounds(m.start(), m.end())
                lo = max(0, min(line_start, m.start() - NEIGHBORHOOD))
                hi = min(len(text), max(line_end, m.end() + NEIGHBORHOOD))
                at = m.start()
                best_f = nearest_from_positions(fpos, fstarts, at, lo, hi)
                best_l = nearest_from_positions(lpos, lstarts, at, lo, hi)
                if best_f is not None and best_l is not None:
                    if best_l[0] < best_f[0]:
                        out.append((label, None, best_l[1]))
                        continue
                    out.append((label, best_f[1], None))  # tie -> finding
                    continue
                if best_f is not None:
                    fid = best_f[1]
                elif best_l is not None:
                    out.append((label, None, best_l[1]))
                    continue
            out.append((label, fid, None))
    return out


def db_path() -> str:
    return os.environ.get("HUNT_DB") or os.path.expanduser(DEFAULT_DB)


def open_ro(path: str) -> sqlite3.Connection:
    """Read-only handle: the gate is a reader, never a writer."""
    # URI filenames are parsed and percent-decoded by sqlite itself: a raw
    # path leaks URI syntax into the open — a '#' in the path silently ends
    # the path AND the query, dropping mode=ro so sqlite falls back to a
    # WRITABLE open (verified on Windows), defeating the reader-only
    # guarantee. Percent-encode the posix form instead; sqlite wants drive
    # paths as file:///C:/... (leading '/', drive colon unencoded) and posix
    # absolute paths as file:///abs/path.
    abs_posix = os.path.abspath(path).replace(os.sep, "/")
    quoted = urllib.parse.quote(abs_posix, safe="/:")
    prefix = "file://" if abs_posix.startswith("/") else "file:///"
    conn = sqlite3.connect(f"{prefix}{quoted}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _lock_check(conn: sqlite3.Connection, cwd: str | None = None) -> str | None:
    """Verify the opened db against the workspace lock (.huntos-project).

    The lock, written by `hunt project bind`, pins a directory to one db_id.
    None when the workspace is unbound (no lock file) or the lock matches the
    opened db; else a BLOCKED: line. A lock with malformed JSON or a
    missing/invalid db_id is malformed; a db whose meta table is absent (a
    foreign db) cannot prove its identity and is treated as a mismatch.
    Hooks may run from anywhere, so the lock is checked in cwd (os.getcwd()).
    """
    cwd = os.getcwd() if cwd is None else cwd
    path = os.path.join(cwd, _LOCK_FILENAME)
    if not os.path.exists(path):
        return None  # unbound workspace: behavior unchanged
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lock = json.loads(fh.read())
    except (ValueError, OSError):  # JSONDecodeError is a ValueError subclass
        return "BLOCKED: project lock file is malformed — rebind with hunt project bind"
    if (not isinstance(lock, dict) or not isinstance(lock.get("db_id"), str)
            or not lock["db_id"]):
        return "BLOCKED: project lock file is malformed — rebind with hunt project bind"
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='db_id'").fetchone()
        db_id = row[0] if row is not None else None
    except sqlite3.Error:
        db_id = None  # no meta table: this db cannot prove its identity
    if lock["db_id"] == db_id:
        return None
    shown = db_id[:12] if isinstance(db_id, str) else "unknown"
    return (
        f"BLOCKED: this project is bound to db {lock['db_id'][:12]} but HUNT_DB "
        f"points to {shown} — claims cannot be verified against the bound ledger"
    )


def vet(conn: sqlite3.Connection,
        found: list[tuple[str, int | None, int | None]]) -> str | None:
    """None when every claim is backed; else the BLOCKED line for the first that isn't.

    Two binding kinds, two evidence bars — both decided by the db:
      - finding-bound (F-<n> / #<n>): passes only if that finding is
        'proven-live'. Unchanged in v0.4.
      - lead-bound (L-<n>): passes only if that lead's state is 'promoted'
        (I13) AND the finding it minted is still 'proven-live' (R2-01: a
        promoted lead whose finding was later overturned must not back a
        strong claim — the lead state alone is a weaker bar than the
        finding's, exactly in the case that matters most).
    An unbound claim (no explicit bind, no finding id nearby) is a veto,
    always: proof of some other finding somewhere in the db backs a claim that
    names nothing — the db decides which findings are proven."""
    for marker, fid, lid in found:
        if lid is not None:
            row = conn.execute(
                "SELECT state, promoted_finding_id FROM leads WHERE id = ?", (lid,)
            ).fetchone()
            if row is not None and row["state"] == "promoted":
                pfid = row["promoted_finding_id"]
                frow = conn.execute(
                    "SELECT ladder_status FROM findings WHERE id = ?", (pfid,)
                ).fetchone() if pfid is not None else None
                fstatus = frow["ladder_status"] if frow is not None else "not found"
                if fstatus == "proven-live":
                    continue  # backed: lead promoted AND its finding alive
                return (
                    f"BLOCKED: engine claimed {marker} for lead L-{lid} but the finding "
                    f"it minted (#{pfid}) is '{fstatus}' — a lead claim dies with its "
                    "finding (hunt finding promote ... / overturn trail)"
                )
            state = row["state"] if row is not None else "not found"
            return (
                f"BLOCKED: engine claimed {marker} for lead L-{lid} but the database "
                f"says the lead is '{state}' — a lead claim is only backed when the "
                "lead is promoted (hunt lead promote ...)"
            )
        if fid is not None:
            row = conn.execute(
                "SELECT ladder_status FROM findings WHERE id = ?", (fid,)
            ).fetchone()
            if row is not None and row["ladder_status"] == "proven-live":
                continue  # backed; keep checking the remaining claims
            status = row["ladder_status"] if row is not None else "not found"
            return (
                f"BLOCKED: engine claimed {marker} for finding #{fid} but the database "
                f"says '{status}' — claims must be backed by proven-live rows "
                "(hunt finding promote ...)"
            )
        return (
            f'BLOCKED: unbound claim "{marker}" — bind it explicitly as '
            "PROVEN[F-<n>] or PROVEN[L-<n>] (the db decides which claims are proven)"
        )
    return None


def main() -> int:
    text = read_input(sys.argv)
    if not text.strip():
        print(PASS_LINE)
        return 0  # nothing to check
    found = claims(text)
    if not found:
        print(PASS_LINE)
        return 0
    path = db_path()
    conn = None
    try:
        conn = open_ro(path)
        # Lock check BEFORE any claim is evaluated: a fabricated HUNT_DB with a
        # planted proven-live row must not pass in a bound workspace. It runs
        # inside this same try on purpose — a missing db still fails closed
        # with the reachability message, lock or no lock.
        lock_msg = _lock_check(conn)
        verdict = lock_msg if lock_msg is not None else vet(conn, found)
    except (sqlite3.Error, OSError):
        print(
            f"BLOCKED: claim gate cannot reach the hunt db ({path}) — "
            "claims cannot be verified, so they cannot pass",
            file=sys.stderr,
        )
        return 2
    finally:
        if conn is not None:
            conn.close()
    if verdict is None:
        print(PASS_LINE)
        return 0
    print(verdict, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
