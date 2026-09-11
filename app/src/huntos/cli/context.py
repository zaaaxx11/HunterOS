"""Operator identity: where am I in the hunt pipeline.

Phase 2 of the orchestrator CLI redesign.  The resolver answers one
question — current target + phase + open wave + latest conductor session —
so the shell prompt can show the ``hunt t1:scoring`` form and one-shot
invocations can print the same line with ``hunt --show-context``.

Contracts (the same laws as the rest of the CLI):
- never writes: the db is opened read-only (SQLite ``mode=ro`` URI); a
  missing db file is an empty context, never a created db.
- unknown-safe defaults: any failure (missing file, corrupt db, bad env
  override) yields the empty context, never a traceback.
- import-light: stdlib sqlite3/os only — shell.py imports this at startup,
  so the database kernel must not load merely to render a prompt.
"""
from __future__ import annotations

import os
import sqlite3


def _db_path(db_path=None) -> str:
    if db_path:
        return os.fspath(db_path)
    return os.environ.get("HUNT_DB", os.path.expanduser("~/.huntos/hunt.db"))


def _open_ro(path: str):
    """Read-only connection, or None when the db cannot be opened that way."""
    if not os.path.isfile(path):
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn
    except (sqlite3.Error, OSError, ValueError):
        return None


def _target_row(conn, target_id: int):
    try:
        return conn.execute(
            "SELECT id, name, phase FROM targets WHERE id=?", (target_id,)
        ).fetchone()
    except sqlite3.Error:
        return None


def _single_active(conn):
    """The single non-archived target id, or None when zero/ambiguous."""
    try:
        rows = conn.execute(
            "SELECT id FROM targets WHERE phase != 'archived' ORDER BY id"
        ).fetchall()
    except sqlite3.Error:
        return None
    if len(rows) == 1:
        return int(rows[0]["id"])
    return None


def _open_wave(conn, target_id: int):
    """Latest wave number with no ev_verdict yet, or None."""
    try:
        row = conn.execute(
            "SELECT number FROM waves WHERE target_id=? AND ev_verdict='' "
            "ORDER BY number DESC LIMIT 1",
            (target_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    return int(row["number"]) if row is not None else None


def _session_row(conn, session_id: str):
    try:
        return conn.execute(
            "SELECT id, status FROM conductor_session WHERE id=?", (session_id,)
        ).fetchone()
    except sqlite3.Error:
        return None


def _latest_session(conn, target_id: int):
    """Latest conductor session for the target, ordered by numeric id suffix
    (the same ordering the kernel's latest_conductor_session uses)."""
    try:
        return conn.execute(
            "SELECT id, status FROM conductor_session WHERE target_id=? "
            "ORDER BY CAST(SUBSTR(id, 3) AS INTEGER) DESC LIMIT 1",
            (target_id,),
        ).fetchone()
    except sqlite3.Error:
        return None


def resolve_context(db_path=None) -> dict:
    """Return the operator's current context; never raises, never writes.

    Resolution order: HUNT_TARGET env override wins when it names a real
    target; otherwise the single non-archived target wins; zero or several
    active targets mean "no context" (the context line says how to pick).
    HUNT_SESSION pins the session suffix when it names a real session;
    otherwise the target's latest session is shown.
    """
    empty: dict = {
        "target_id": None,
        "target_name": "",
        "phase": "",
        "wave": None,
        "session_id": None,
        "session_status": None,
        "source": "none",
    }
    try:
        path = _db_path(db_path)
        conn = _open_ro(path)
        if conn is None:
            return empty
        try:
            target_id = None
            source = "none"
            env_target = os.environ.get("HUNT_TARGET", "").strip()
            if env_target:
                try:
                    row = _target_row(conn, int(env_target))
                except (TypeError, ValueError):
                    row = None
                if row is not None:
                    target_id = int(row["id"])
                    source = "env"
            if target_id is None:
                single = _single_active(conn)
                if single is not None:
                    target_id = single
                    source = "single"
            if target_id is None:
                return empty
            row = _target_row(conn, target_id)
            if row is None:
                return empty
            ctx = {
                "target_id": int(row["id"]),
                "target_name": row["name"] or "",
                "phase": row["phase"] or "",
                "wave": _open_wave(conn, target_id),
                "session_id": None,
                "session_status": None,
                "source": source,
            }
            session = None
            env_session = os.environ.get("HUNT_SESSION", "").strip()
            if env_session:
                session = _session_row(conn, env_session)
            if session is None:
                session = _latest_session(conn, target_id)
            if session is not None:
                ctx["session_id"] = session["id"]
                ctx["session_status"] = session["status"]
            return ctx
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError):
        return empty


def format_prompt(ctx: dict) -> str:
    """The shell prompt: ``hunt t1:scoring> `` with an optional session
    suffix, or the bare ``hunt> `` when there is no context."""
    if not ctx or ctx.get("target_id") is None:
        return "hunt> "
    base = f"hunt t{ctx['target_id']}:{ctx['phase']}"
    if ctx.get("session_id"):
        base += f" {ctx['session_id']}:{ctx['session_status']}"
    return base + "> "


def format_context_line(ctx: dict) -> str:
    """The one-line 'where am I' used by --show-context and shell context."""
    if not ctx or ctx.get("target_id") is None:
        return (
            "(no target in context — hunt target add <name> <url> "
            "| HUNT_TARGET=<id> to pin one)"
        )
    line = f"t{ctx['target_id']} {ctx['target_name']} ({ctx['phase']})"
    if ctx.get("wave") is not None:
        line += f" | wave {ctx['wave']} open"
    if ctx.get("session_id"):
        line += f" | {ctx['session_id']} {ctx['session_status']}"
    else:
        line += " | no conductor session"
    return line
