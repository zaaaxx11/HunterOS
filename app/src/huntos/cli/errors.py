"""Unified BLOCKED|NEXT error formatter for the HUNT-OS operator surface.

Phase 3 of the orchestrator CLI redesign: every refusal speaks one shape::

    BLOCKED: <what went wrong> | NEXT: <exact copy-pasteable command>

This module must stay import-light (stdlib ``re`` only): shell.py imports it
without importing the database kernel, and main.py's ``ValueError`` handler
uses it on the hot refusal path.  Syntax mirrors the existing contract —
``BLOCKED:`` prefix and exit 2 are unchanged; the ``| NEXT:`` suffix is
appended, so existing substring assertions keep passing.

Helpers:
  sanitize() — strip C0/C1 control characters (except ``\\n``/``\\t``) so a
    hostile ledger value cannot smear the terminal.
  redact() — minimal safety-net redaction for error text.  The canonical
    patterns live in ``huntos.core.db.redact``; the subset here is duplicated
    on purpose so this module never imports the db kernel.  Keep both lists
    in sync when adding new secret shapes.
  blocked() — idempotent formatter: a message that already starts with
    ``BLOCKED:`` is unwrapped first, so wiring an existing raise site
    through ``blocked(str(exc))`` never double-prefixes.
"""
from __future__ import annotations

import re


# --- MSYS leading-slash guard (L2.2, FIRSTBLOOD #2), canonical home ---------
# On Windows Git Bash, a POSIX-style argument that BEGINS with '/' is silently
# rewritten into a Windows path under the Git installation directory:
# '/api/users' arrives as 'C:/Program Files/Git/api/users'.  Only FREE-TEXT
# positionals are guarded (finding titles, lesson patterns/sources); real
# file-path arguments are never guarded.  main.py re-exports these names so
# existing imports (``from huntos.cli.main import _MSYS_BLOCKED_MSG``) keep
# working; new code should import from here.
MSYS_MANGLED_RE = re.compile(r"^[A-Za-z]:[\\/]+Program Files[\\/]+Git[\\/]+")

MSYS_BLOCKED_MSG = (
    "BLOCKED: argument looks MSYS-mangled (leading '/' became a Git path). "
    "Prefix the command with MSYS_NO_PATHCONV=1, or do not start the argument with /."
)


def is_msys_mangled(text: str) -> bool:
    """True when free text arrived with the MSYS Git-path mangling shape."""
    return bool(text) and bool(MSYS_MANGLED_RE.match(text))


# --- sanitization ------------------------------------------------------------
# C0 controls + DEL + C1 controls, except \t and \n which error text may
# legitimately contain (multi-line wave summaries, script stop lines).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def sanitize(text: str) -> str:
    """Strip terminal-smearing control characters; never raises."""
    if not text:
        return text
    return _CONTROL_RE.sub("", text)


# --- secret redaction (safety net; canonical list in huntos.core.db) ---------
# Subset of db._SECRET_PATTERNS / db._ASSIGNMENT_PATTERNS, duplicated so this
# module stays import-light.  An error message should never carry a secret,
# but a ledger value echoed back in a refusal (e.g. "title contains ...")
# could — redact before printing.
_REDACT_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED-PRIVATE-KEY]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "[REDACTED-JWT]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED-AWS-KEY]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED-GH-TOKEN]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED-KEY]"),
]

_REDACT_ASSIGNMENTS = [
    (re.compile(r"(?i)\b(password|passwd)\s*[=:]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(token|secret|api[_-]?key)\s*[=:]\s*(\S{12,})"), r"\1=[REDACTED]"),
]


def redact(text: str) -> str:
    """Conservative redaction for error text; never raises."""
    if not text:
        return text
    for pattern, label in _REDACT_PATTERNS:
        text = pattern.sub(label, text)
    for pattern, repl in _REDACT_ASSIGNMENTS:
        text = pattern.sub(repl, text)
    return text


# --- the unified shape --------------------------------------------------------
_BLOCKED_PREFIX = "BLOCKED:"
_NEXT_SEP = " | NEXT: "


def blocked(what: str, next_cmd: str | None = None) -> str:
    """Format the unified refusal line.

    ``blocked("wave #3 still open", "hunt wave close --wave-id 3 --verdict exhausted")``
    returns::

        BLOCKED: wave #3 still open | NEXT: hunt wave close --wave-id 3 --verdict exhausted

    Idempotent: ``what`` may already carry the ``BLOCKED:`` prefix (e.g.
    ``str(exc)`` from a ``raise ValueError("BLOCKED: ...")`` site) — it is
    unwrapped before re-emitting, never doubled.  ``next_cmd=None`` emits the
    bare ``BLOCKED:`` line for refusals whose remediation is inline (the MSYS
    guard message already names the fix).
    """
    text = what if isinstance(what, str) else str(what)
    text = sanitize(redact(text))
    if text.startswith(_BLOCKED_PREFIX):
        text = text[len(_BLOCKED_PREFIX):].lstrip()
    # A pre-shaped line that already carries NEXT passes through untouched.
    if _NEXT_SEP in text:
        return f"{_BLOCKED_PREFIX} {text}"
    line = f"{_BLOCKED_PREFIX} {text}"
    if next_cmd:
        line += f"{_NEXT_SEP}{sanitize(str(next_cmd)).strip()}"
    return line


def split_blocked(line: str) -> tuple[str, str | None]:
    """Split a formatted BLOCKED line into ``(error, next_cmd)``.

    Inverse of :func:`blocked` for the ``--json`` machine surface: the
    ``BLOCKED:`` prefix is stripped and the ``| NEXT:`` suffix (when
    present) becomes the ``next`` field.  Returns ``(error, None)`` for a
    bare refusal whose remediation is inline (e.g. the MSYS guard).
    Never raises.
    """
    text = line if isinstance(line, str) else str(line)
    if text.startswith(_BLOCKED_PREFIX):
        text = text[len(_BLOCKED_PREFIX):].lstrip()
    if _NEXT_SEP in text:
        error, next_cmd = text.split(_NEXT_SEP, 1)
        return error.strip(), (next_cmd.strip() or None)
    return text.strip(), None
