"""Static operational panels for the HUNT-OS operator surface.

Phase 4 of the orchestrator CLI redesign: visible work + workflow position
as STATIC reprints — no Live, no alternate-screen, no background threads.
Every panel reuses ``cli/terminal.py`` helpers only (stdlib), so width
clamps 60-120 and NO_COLOR/dumb/pipe safety come for free.

Contracts (the same laws as the rest of the CLI):
- import-light: stdlib + ``.terminal`` + ``.errors`` at top.  The database
  kernel is imported LAZILY inside ``position_block`` only, so ``hunt help``
  and other db-free paths never pay for it.
- append-only wiring: handlers keep their existing success lines
  byte-identical and APPEND panels/receipts, so substring test anchors keep
  passing.
- display never crashes a command: ``position_block`` catches everything and
  returns ``""`` (the caller skips it) instead of raising.
"""
from __future__ import annotations

import sys

from .errors import sanitize
from .terminal import pad_visible, style, supports_color, terminal_width, truncate_visible


def _columns(width=None, stream=None) -> int:
    columns = terminal_width(stream) if width is None else int(width)
    return max(60, min(120, columns))


def panel(title: str, rows: list, *, color=None, width=None, stream=None) -> str:
    """Render a bordered static panel: title + rows, width-clamped."""
    stream = sys.stdout if stream is None else stream
    use_color = supports_color(stream) if color is None else bool(color)
    columns = _columns(width, stream)
    inner = columns - 4
    border = "+" + "-" * (columns - 2) + "+"

    def frame(text: str, *, decorate: bool = False) -> str:
        content = pad_visible(truncate_visible(text, inner), inner)
        plain = f"| {content} |"
        return style(plain, green=True, bold=decorate, color=use_color) if decorate else plain

    lines = [style(border, green=True, color=use_color)]
    lines.append(frame(title, decorate=True))
    lines.append(style(border, green=True, color=use_color))
    for row in rows:
        lines.append(frame(row))
    lines.append(style(border, green=True, color=use_color))
    return "\n".join(lines)


def start_panel(session_id: str, *, target_id, rounds, adapter: str,
                color=None, width=None, stream=None) -> str:
    """The run-start panel: what opened, where to watch it."""
    name = str(adapter or "?")
    mode = (
        "SIMULATED — no external agents invoked"
        if name in {"mock", "mock-harness"}
        else f"ADAPTER {name} — SERIAL 4-LANE"
    )
    return panel(
        f"RUN STARTED / SESSION {session_id}",
        [
            f"target #{target_id} / rounds {rounds} / adapter {name}",
            mode,
            f"Next: hunt run status --session {session_id}",
        ],
        color=color, width=width, stream=stream,
    )


def end_panel(session_id: str, *, status: str,
              color=None, width=None, stream=None) -> str:
    """The run-end panel: terminal status + resume/view commands."""
    return panel(
        f"RUN {str(status).upper()} / SESSION {session_id}",
        [
            f"resume: hunt run status --session {session_id}",
            f"view:   hunt run status --session {session_id} --page",
        ],
        color=color, width=width, stream=stream,
    )


def error_panel(what: str, next_cmd: str | None,
                *, color=None, width=None, stream=None) -> str:
    """A static error panel ending with the Next: line (display only — the
    exit-2 BLOCKED contract still goes through cli/errors.py)."""
    rows = [f"what: {sanitize(str(what))}"]
    if next_cmd:
        rows.append(f"Next: {sanitize(str(next_cmd)).strip()}")
    return panel("RUN BLOCKED", rows, color=color, width=width, stream=stream)


def receipt(what: str, next_cmd: str | None = None) -> str:
    """One-line work receipt for non-conductor writes (plain text, greppable).

    ``DONE: <what> | NEXT: <exact cmd>`` — the success-side mirror of the
    BLOCKED|NEXT refusal shape.  Never carries a ``BLOCKED:`` prefix.
    """
    line = f"DONE: {sanitize(str(what)).strip()}"
    if next_cmd:
        line += f" | NEXT: {sanitize(str(next_cmd)).strip()}"
    return line


# --- pipeline position block (plan step 14) ---------------------------------
# WHERE am I: target phase + phase exit gate + wave state + leads/findings
# counts.  Read-only (SELECTs via the db kernel, imported lazily); never
# raises — any failure yields "" so display can never crash a command.
# Prefixes are WHERE:/EXIT:/WAVE:/WORK: (never NEXT:/WHY:, which `hunt next`
# owns — test_next pins exactly one NEXT + one WHY line on stdout).

def _has_artifact(conn, target_id: int, artifact_type: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM events WHERE target_id=? AND kind='phase_artifact' "
        "AND detail LIKE ? LIMIT 1",
        (target_id, artifact_type + ":%"),
    ).fetchone()
    return row is not None


def _exit_gate(conn, target: dict) -> tuple:
    """(gate_text, try_command) mirroring db.next_command rows 1-6 + defaults."""
    tid = target["id"]
    phase = target["phase"]
    if phase == "scoring":
        if (target["ev_score"] or 0) <= 0:
            return ("score the target (ev=0 blocks every exit)",
                    f"hunt score {tid} <ev>")
        return ("advance to recon", f"hunt phase {tid} recon")
    if phase == "recon":
        if not _has_artifact(conn, tid, "surface_map"):
            return ("record the surface_map exit artifact",
                    f"hunt artifact {tid} surface_map <path>")
        return ("advance to classify", f"hunt phase {tid} classify")
    if phase == "classify":
        if not _has_artifact(conn, tid, "attack_plan"):
            return ("record the attack_plan exit artifact",
                    f"hunt artifact {tid} attack_plan <path>")
        return ("advance to hunting", f"hunt phase {tid} hunting")
    if phase in ("hunting", "verify"):
        last = conn.execute(
            "SELECT * FROM waves WHERE target_id=? ORDER BY number DESC LIMIT 1",
            (tid,),
        ).fetchone()
        if last is not None and last["ev_verdict"] and not last["reaudit_done"]:
            return ("record the re-audit (next wave stays locked)",
                    f"hunt wave reaudit --wave-id {last['id']} --summary \"...\"")
        open_wave = conn.execute(
            "SELECT * FROM waves WHERE target_id=? AND ev_verdict='' "
            "ORDER BY number DESC LIMIT 1",
            (tid,),
        ).fetchone()
        if open_wave is not None:
            return ("work or close the open wave",
                    f"hunt wave close --wave-id {open_wave['id']} --verdict exhausted")
        return ("open the next round with the brief", f"hunt brief {tid}")
    if phase == "report":
        return ("write the disclosure report", f"hunt report {tid}")
    if phase == "retro":
        return ("record the retro lesson (the hunt never closes without it)",
                f"hunt lesson add <source> <pattern> --target-id {tid}")
    if phase == "archived":
        return ("hunt closed — read-only from here", "hunt target list")
    return ("unknown phase — inspect the ledger", "hunt status")


def position_block(conn, target_id: int) -> str:
    """Four-line WHERE/EXIT/WAVE/WORK block for status/brief/next.  Read-only,
    never raises: returns "" when the target cannot be read."""
    try:
        from ..core import db as _db

        target = _db.get_target(conn, int(target_id))
        tid = target["id"]
        lines = [f"WHERE t{tid} {target['name']} phase={target['phase']}"]
        gate, attempt = _exit_gate(conn, target)
        lines.append(f"EXIT  {gate} — try: {attempt}")
        waves = list(_db.list_waves(conn, tid))
        if not waves:
            lines.append("WAVE  (no waves)")
        else:
            open_wave = next((w for w in waves if not w["ev_verdict"]), None)
            if open_wave is not None:
                lines.append(
                    f"WAVE  open #{open_wave['id']} (number {open_wave['number']}) "
                    f"lanes={open_wave['lanes']}"
                )
            else:
                last = waves[-1]
                reaudit = "done" if last["reaudit_done"] else "pending"
                lines.append(
                    f"WAVE  last #{last['id']} (number {last['number']}) "
                    f"verdict={last['ev_verdict']} reaudit={reaudit}"
                )
        leads = list(_db.list_leads(conn, tid))
        live = sum(1 for l in leads if l["state"] in ("open", "mutating"))
        parked = sum(1 for l in leads if l["state"] == "parked")
        killed = sum(1 for l in leads if l["state"] == "killed")
        findings = list(_db.list_findings(conn, tid))
        counts = {"theoretical": 0, "in-code": 0, "proven-live": 0, "overturned": 0}
        for f in findings:
            counts[f["ladder_status"]] = counts.get(f["ladder_status"], 0) + 1
        lines.append(
            f"WORK  leads=open:{live} parked:{parked} killed:{killed} | "
            f"findings=theoretical:{counts['theoretical']} "
            f"in-code:{counts['in-code']} proven-live:{counts['proven-live']} "
            f"overturned:{counts['overturned']}"
        )
        return "\n".join(sanitize(line) for line in lines)
    except Exception:
        return ""
