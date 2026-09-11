"""The Conductor orchestrator (blueprint C1 - conductor.md sections 8, 9, 12).

Drives the managed hunt loop synchronously over a :class:`HuntAdapter`:

- sessions/attempts/incidents are KERNEL rows (``huntos.core.db`` conductor
  API); the conductor never writes those tables directly, it only composes
  kernel calls, so every state change is CHECK-pinned, transition-guarded and
  ledger-logged by the kernel.
- tool requests are MEDIATED in-process through the hunt CLI entry
  (``huntos.cli.main.main``): the command list runs for real, stdout/stderr
  and the exit code are observed, and the CLI itself writes whatever ledger
  rows it writes. The conductor records nothing fake.
- assistant output goes through the REAL claim gate
  (``huntos/_data/bin/claim_gate.py``) as a subprocess (exit 2 = veto); the
  gate is never reimplemented here, and a gate that cannot run fails CLOSED.

Laws implemented here (each has a test in ``app/tests/test_conductor.py``):

- 12.1 managed run refused unless ``capabilities.meets_managed_requirements()``.
- 12.2 the kernel pins db_fingerprint at session create; its BLOCKED refusal
  surfaces unchanged.
- 12.6 a timeout before dispatch retries as a NEW child attempt
  (``parent_attempt_id``) — zero duplicate work.
- 12.7 a timeout after a possibly-mutating tool marks the attempt UNCERTAIN;
  retry is refused until the incident is reconciled.
- 12.8 provider auth/rate failures PAUSE the session — never a research
  result, never an empty lane.
- 12.9 disk full / invalid adapter protocol freeze the session
  (recovery_required); ALL dispatch is refused while frozen. For the protocol
  class the adapter circuit breaker also opens; ``doctor()`` passing is the
  only path that clears it.
- 12.10 no model fallback, ever: ``retry_attempt`` with a profile other than
  the session-pinned one is a refusal plus a ``reconfiguration_refused``
  incident.

Stdlib only. No network, no threads, no sleeps (the claim-gate subprocess is
the one deliberate exception — it is a local, deterministic process).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from huntos.core import db

from .capsule import build_lane_capsule, default_roles_root, skills_lock_hash as compute_skills_lock_hash
from .schemas import (
    AssistantDelta,
    AssistantOutput,
    AttemptCompleted,
    Capabilities,
    Event,
    Heartbeat,
    SchemaError,
    StructuredError,
    ToolRequest,
    ToolResult,
    Usage,
    parse_event,
)
from .summary import compute_next_action

# The in-process dispatch entry of the hunt CLI is imported LAZILY inside
# _mediate() (huntos.cli.main:main — how ``python -m huntos`` runs commands).
# Lazy on purpose: the CLI layer wires the conductor into its `hunt run`
# commands, so a module-level import here would be circular.


# --- tool mediation classification (explicit, documented set) ---------------
#
# A mediated `hunt` command is MUTATING unless it matches this explicit
# read-only set. FAIL CLOSED: any verb/subverb not listed — including unknown
# ones — counts as mutating, because a timeout after an unknown command must
# assume state may have changed (blueprint §9 "timeout after possibly
# mutating tool" -> uncertain). A read-only verdict only ever DOWNgrades the
# response for a hang; it never gates execution itself (the CLI's own gates
# do that).
READ_ONLY_COMMANDS = frozenset({
    ("status",),             # hunt status
    ("brief",),              # hunt brief <target>
    ("coverage",),           # hunt coverage <target>
    ("verify-report",),      # hunt verify-report <file> (pure file-level check)
    ("doctor",),             # hunt doctor (adapter discovery)
    ("target", "list"),
    ("lesson", "list"),
    ("klass", "list"),
    ("lead", "list"),
    ("surface", "list"),
    ("project", "status"),
    ("chain", "show"),
    ("chain", "novelty"),
    # read-only examples of the mutators' complements (NOT in this set, hence
    # mutating): finding add/promote/overturn, wave open/close/reaudit,
    # poc run, verify, challenge, target roe/archive/add, klass add,
    # lesson add, project bind, lead add/set-half/mutate/park/promote/...,
    # surface add, chain add/link, fuzz, phase, artifact.
})


# Observed tool output is preserved for the operator but never unbounded:
# both the dispatch log and the turn's observed record cap at this many
# characters, with an explicit note marking the truncation (the ledger never
# silently drops bytes).
MEDIATED_OUTPUT_CAP = 2000


def _cap_observed(text: str) -> str:
    """Cap mediated output at MEDIATED_OUTPUT_CAP chars, noting truncation."""
    if len(text) <= MEDIATED_OUTPUT_CAP:
        return text
    return (
        text[:MEDIATED_OUTPUT_CAP]
        + f"... [truncated: {len(text)} chars observed, "
        f"first {MEDIATED_OUTPUT_CAP} kept]"
    )


def is_mutating_command(command: list) -> bool:
    """True when the command may change state (fail closed for unknowns).

    ``hunt report`` is the one conditional row: reading a report to stdout is
    read-only, ``--out`` writes a file and leaves the ledger, so it mutates
    the world outside the db.
    """
    parts = list(command)
    if parts and parts[0] == "hunt":
        parts = parts[1:]
    if not parts:
        return True  # fail closed
    if parts[0] == "report":
        return "--out" in parts[1:]
    if (parts[0],) in READ_ONLY_COMMANDS:
        return False
    if len(parts) > 1 and (parts[0], parts[1]) in READ_ONLY_COMMANDS:
        return False
    return True


class _Turn:
    """Mutable bookkeeping for one attempt's event stream."""

    def __init__(self):
        self.dispatched_any = False      # any tool request mediated this turn
        self.dispatched_mutating = False  # a mutating-classified command ran
        self.observed: list = []         # [(operation_id, output, ok)] in order
        self.cancelled = False           # attempt reached a cancelled outcome
        self.stop = False                # stop processing this turn's events


class Conductor:
    """Orchestrates the managed hunt loop over a HuntAdapter (sections 8-9).

    The adapter is the ONLY channel to the harness; the kernel (huntos.core.db
    conductor API) is the ONLY writer of session/attempt/incident state; the
    hunt CLI is the ONLY path for agent tool actions; the bridge claim gate is
    the ONLY judge of assistant claims.
    """

    def __init__(self, adapter, adapter_registry_name: Optional[str] = None) -> None:
        self._adapter = adapter
        self._adapter_registry_name = adapter_registry_name
        # Adapter circuit breaker (§9 invalid adapter protocol): opens on a
        # protocol violation, cleared ONLY by a passing doctor().
        self._circuit_open = False
        # The REAL gate, shipped inside the package and located relative to
        # this file: huntos/_data/bin/claim_gate.py. Overridable for tests.
        self.claim_gate_path = str(
            Path(__file__).resolve().parents[1] / "_data" / "bin" / "claim_gate.py"
        )
        # Observability of what this conductor actually did (mediated commands
        # + gate verdicts). Tests use it to prove zero-duplicate work.
        self.dispatch_log: list = []
        self._last_diagnostics: list = []
        # session_id -> profile name this conductor pinned (an in-process aid;
        # the durable pin is the sha256 in conductor_session.model_profile_hash)
        self._profiles: dict = {}
        self.roles_root = default_roles_root()
        self._capsules: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # capability discovery / circuit breaker (§9, §12.1)
    # ------------------------------------------------------------------

    def doctor(self) -> "tuple[Capabilities, list[str]]":
        """Adapter health + capability discovery; the ONLY circuit-breaker
        clearing path. A doctor that meets the managed requirements closes the
        breaker; anything else leaves it exactly as it was."""
        caps, diagnostics = self._adapter.doctor()
        diagnostics = list(diagnostics)
        if caps.meets_managed_requirements():
            if self._circuit_open:
                diagnostics.append("circuit breaker: cleared — adapter doctor() passed")
            self._circuit_open = False
        elif self._circuit_open:
            diagnostics.append(
                "circuit breaker: still OPEN — managed requirements unmet "
                "(hunt_tool, post_output_hook, headless_turn)"
            )
        self._last_diagnostics = diagnostics
        return caps, diagnostics

    # ------------------------------------------------------------------
    # managed run (§8 workflow)
    # ------------------------------------------------------------------

    def start_run(self, conn, target_id: int, rounds: int,
                  model_profile: str = "mock",
                  budget_per_attempt: Optional[int] = None,
                  skills_lock_hash: Optional[str] = None) -> dict:
        """Preflight, session create, and the whole managed loop, synchronously.

        Returns the final session row (plain dict). If a mid-loop event pauses
        or recovery_requires the session, the loop STOPS and the session row is
        returned as-is (paused / degraded / recovery_required).

        The declared per-attempt budget is recorded on the session row's
        ``budget`` column (the kernel's only budget slot).
        """
        # Preflight (§8 step 2): adapter capability discovery. A healthy
        # doctor() here is also the documented clearing path for a circuit
        # breaker left open by an earlier protocol incident.
        caps, diagnostics = self.doctor()
        if (
            not caps.meets_managed_requirements()
            or not caps.features["subagents"]
        ):
            raise ValueError(
                "BLOCKED: adapter lacks the universal four-lane capabilities "
                "(hunt_tool, post_output_hook, headless_turn, subagents) — "
                "managed run refused"
            )
        if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
            raise ValueError(f"BLOCKED: rounds must be an integer >= 1; got {rounds!r}")
        if budget_per_attempt is not None and (
            isinstance(budget_per_attempt, bool)
            or not isinstance(budget_per_attempt, int)
            or budget_per_attempt < 1
        ):
            raise ValueError(
                "BLOCKED: budget_per_attempt must be a positive integer or None; "
                "0 is refused — every attempt would be cancelled the moment it "
                "reports usage (None means no budget); "
                f"got {budget_per_attempt!r}"
            )
        profile_hash = _profile_hash(model_profile)
        source = db.get_target_source(conn, target_id)
        workspace = source["workspace"] if source is not None else os.getcwd()
        if skills_lock_hash is None:
            skills_lock_hash = compute_skills_lock_hash(self.roles_root)
        # §12.2: the kernel pins db_fingerprint and validates the target; its
        # ValueError("BLOCKED: ...") surfaces unchanged.
        session = db.create_conductor_session(
            conn, target_id, workspace, db.db_fingerprint(conn), budget_per_attempt,
            caps.adapter_id, caps.version, profile_hash, skills_lock_hash,
            rounds=rounds, adapter_registry_name=self._adapter_registry_name,
        )
        sid = session["id"]
        self._profiles[sid] = model_profile
        session = db.set_conductor_session_status(conn, sid, "running")
        self._adapter.start_session({
            "session_id": sid, "target_id": target_id, "rounds": rounds,
            "model_profile": model_profile, "adapter_id": caps.adapter_id,
            "adapter_version": caps.version,
        })
        self._run_rounds(conn, sid, rounds, budget_per_attempt)
        final = db.get_conductor_session(conn, sid)
        if final["status"] == "completed":
            self._adapter.stop_session(sid)
        return final

    def _run_rounds(self, conn, sid: str, rounds: int, budget_per_attempt) -> None:
        """The managed loop: round 1..rounds x 4 lanes, one dispatch per cell.

        Used by start_run (fresh cells) and resume_run (pending cells alike):
        a cell with a research result is skipped, an uncertain cell blocks its
        lane until reconciled, anything else gets a (new) attempt dispatched.
        """
        for round_no in range(1, rounds + 1):
            for lane in db.CONDUCTOR_LANES:
                session = db.get_conductor_session(conn, sid)
                if session["status"] not in ("running", "degraded"):
                    return  # paused/recovery_required/aborted mid-loop: stop (law)
                attempt = self._pending_or_new_attempt(conn, sid, lane, round_no)
                if attempt is None:
                    continue  # done, or blocked until reconciliation
                db.set_conductor_attempt_status(conn, attempt["id"], "running")
                if self._dispatch(conn, sid, lane, round_no, attempt["id"],
                                  budget_per_attempt):
                    return  # stop new dispatch (crash/pause/freeze)
        session = db.get_conductor_session(conn, sid)
        # completed means "the managed run finished with nothing pending", not
        # "every lane produced a result" — interrupted/uncertain/cancelled are
        # pending work (§5), so a session carrying any stays running. A cell
        # counts through its LATEST attempt: a superseded interrupted parent
        # behind a completed child is done.
        if session["status"] == "running" and not self._has_pending_work(conn, sid, rounds):
            db.set_conductor_session_status(conn, sid, "completed")

    def _pending_or_new_attempt(self, conn, sid: str, lane: str, round_no: int):
        """The cell's next attempt, or None when the cell needs nothing."""
        latest = self._latest_attempt(conn, sid, lane, round_no)
        if latest is None:
            return self._create_attempt(conn, sid, lane, round_no, parent_id=None)
        status = latest["status"]
        if status in ("completed", "research_blocked"):
            return None                      # a research result: done
        if status == "uncertain":
            return None                      # blocks its lane until reconciled (§12.7)
        if status == "ready":
            return latest                    # born, never dispatched: zero work done
        # running / interrupted / cancelled: a retry is a NEW attempt (§12.6) —
        # an id names exactly one attempt, so the same id is never re-run.
        return self._create_attempt(conn, sid, lane, round_no, parent_id=latest["id"])

    def _create_attempt(self, conn, sid: str, lane: str, round_no: int,
                        parent_id: Optional[str]) -> dict:
        profile = self._pinned_profile(conn, sid, parent_id)
        legacy_hash = hashlib.sha256(
            f"{sid}:{lane}:{round_no}".encode("utf-8")
        ).hexdigest()
        attempt = db.create_conductor_attempt(
            conn, sid, lane, round_no, parent_attempt_id=parent_id,
            model_profile=profile, prompt_hash=legacy_hash,
        )
        session = db.get_conductor_session(conn, sid)
        if session is not None and db.get_target_source(conn, session["target_id"]) is not None:
            capsule, capsule_hash = build_lane_capsule(
                conn, sid, attempt["id"], lane, round_no, profile, self.roles_root
            )
            attempt = db.set_conductor_attempt_prompt_hash(
                conn, attempt["id"], capsule_hash
            )
            self._capsules[attempt["id"]] = capsule
        return attempt

    def _dispatch(self, conn, sid: str, lane: str, round_no: int, attempt_id: str,
                  budget_per_attempt) -> bool:
        """Run one turn and process its events. Returns True when the WHOLE
        loop must stop (provider pause, crash stop-new-dispatch, freeze)."""
        attempt = db.get_conductor_attempt(conn, attempt_id)
        capsule = self._capsules.get(attempt_id)
        session = db.get_conductor_session(conn, sid)
        if capsule is None and session is not None and db.get_target_source(conn, session["target_id"]) is not None:
            capsule, capsule_hash = build_lane_capsule(
                conn, sid, attempt_id, lane, round_no, attempt["model_profile"], self.roles_root
            )
            if capsule_hash != attempt["prompt_hash"]:
                return self._protocol_error(
                    conn, sid, attempt_id, "persisted capsule hash does not match rebuilt capsule", _Turn()
                )
        config = {
            "attempt_id": attempt_id, "session_id": sid, "lane": lane,
            "round": round_no, "model_profile": attempt["model_profile"],
            "prompt_hash": attempt["prompt_hash"], "capsule_hash": attempt["prompt_hash"],
            "capsule": capsule,
        }
        turn = _Turn()
        db.record_conductor_event(conn, sid, attempt_id, "lane_start",
                                  f"lane={lane} round={round_no}")
        try:
            stream = self._adapter.run_turn(config)
            for item in stream:
                try:
                    event = item if isinstance(item, Event) else parse_event(item)
                except SchemaError as exc:
                    return self._protocol_error(conn, sid, attempt_id, str(exc), turn)
                stop_run = self._handle_event(conn, sid, attempt_id, budget_per_attempt,
                                              turn, event)
                if stop_run:
                    return True
                if turn.stop:
                    break
        except Exception as exc:
            return self._protocol_error(conn, sid, attempt_id, str(exc), turn)
        # A stream that ends without a terminal event is an interrupted turn,
        # never a result (§5: infrastructure silence is not evidence).
        current = db.get_conductor_attempt(conn, attempt_id)
        if current["status"] == "running":
            db.set_conductor_attempt_status(conn, attempt_id, "interrupted")
            db.record_conductor_incident(
                conn, sid, "unterminated_turn",
                f"attempt {attempt_id}: turn ended without a terminal event",
            )
        return False

    def _handle_event(self, conn, sid: str, attempt_id: str, budget_per_attempt,
                      turn: _Turn, event: Event) -> bool:
        """Process one adapter event; returns True when the loop must stop."""
        if isinstance(event, (Heartbeat, AssistantDelta)):
            return False  # liveness/streaming prose: never a record
        if isinstance(event, ToolRequest):
            db.record_conductor_event(
                conn, sid, attempt_id, "tool_request",
                "command=" + repr(event.command), event.operation_id,
            )
            result = self._mediate(event, attempt_id, turn)
            db.record_conductor_event(
                conn, sid, attempt_id, "tool_result",
                f"ok={result.ok} output={_cap_observed(result.output)}", result.operation_id,
            )
            try:
                self._adapter.submit_tool_result(attempt_id, result)
            except Exception as exc:
                return self._protocol_error(conn, sid, attempt_id,
                                            f"tool result submission failed: {exc}", turn)
            return False
        if isinstance(event, ToolResult):
            turn.observed.append((event.operation_id, event.output, event.ok))
            db.record_conductor_event(
                conn, sid, attempt_id, "tool_result",
                f"ok={event.ok} output={_cap_observed(event.output)}", event.operation_id,
            )
            return False
        if isinstance(event, Usage):
            db.record_conductor_event(conn, sid, attempt_id, "usage",
                                      f"tokens={event.tokens}")
            return self._on_usage(conn, sid, attempt_id, budget_per_attempt, turn, event)
        if isinstance(event, AssistantOutput):
            db.record_conductor_event(conn, sid, attempt_id, "assistant_output",
                                      _cap_observed(event.text))
            return self._on_output(conn, sid, attempt_id, turn, event)
        if isinstance(event, AttemptCompleted):
            # §12.3: the kernel owns the completed transition (distinct ids,
            # recorded profile/hash happened at create). A vetoed/cancelled
            # attempt never advances.
            if event.attempt_id == attempt_id and not turn.cancelled:
                current = db.get_conductor_attempt(conn, attempt_id)
                if current["status"] == "running":
                    db.set_conductor_attempt_status(conn, attempt_id, "completed")
                    db.record_conductor_event(conn, sid, attempt_id, "completion",
                                              event.status_hint)
            return False
        if isinstance(event, StructuredError):
            db.record_conductor_event(conn, sid, attempt_id, "error",
                                      f"{event.error_class}: {event.detail}")
            return self._on_structured_error(conn, sid, attempt_id, turn, event)
        return False

    # ------------------------------------------------------------------
    # tool mediation (§12.4: every agent action follows the CLI/kernel gates)
    # ------------------------------------------------------------------

    def _mediate(self, request: ToolRequest, attempt_id: str, turn: _Turn) -> ToolResult:
        """Run the requested command through the hunt CLI, in-process.

        The CLI opens its own ledger connection (HUNT_DB) and writes whatever
        it writes — the conductor records the OBSERVED output and exit code,
        nothing else. Unknown exceptions from the CLI are observed as a failed
        mediation (ok=False), never silently swallowed.
        """
        mutating = is_mutating_command(request.command)
        argv = list(request.command)
        if argv and argv[0] == "hunt":
            argv = argv[1:]
        from ..cli.main import main as _cli_main  # lazy: avoids the CLI->conductor cycle
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = _cli_main(argv)
        except SystemExit as exc:  # argparse usage errors exit(2)
            code = exc.code
            rc = code if isinstance(code, int) else (0 if code is None else 1)
        except Exception as exc:  # an unexpected CLI crash is observed, not hidden
            err.write(f"BLOCKED: mediation crashed: {exc!r}")
            rc = 1
        text = out.getvalue() + err.getvalue()
        result = ToolResult(operation_id=request.operation_id, output=text,
                            ok=(rc == 0))
        turn.dispatched_any = True
        if mutating:
            turn.dispatched_mutating = True
        # turn.observed is bounded like dispatch_log: full tool output is
        # never retained in memory past the cap (the truncation is noted).
        turn.observed.append((request.operation_id, _cap_observed(text), result.ok))
        self.dispatch_log.append({
            "kind": "tool", "attempt_id": attempt_id,
            "operation_id": request.operation_id, "command": list(request.command),
            "mutating": mutating, "ok": result.ok, "exit_code": rc,
            "output": _cap_observed(text),
        })
        return result

    # ------------------------------------------------------------------
    # claim gate (§12.5) — the REAL packaged gate, subprocess, exit 2 = veto
    # ------------------------------------------------------------------

    def _claim_gate(self, text: str) -> "tuple[str, str]":
        """Run huntos/_data/bin/claim_gate.py over the output. Returns
        (verdict, detail): verdict is "pass", "veto" (exit 2) or "unavailable"
        (missing/unrunnable gate — fail closed)."""
        gate = self.claim_gate_path
        if not gate or not os.path.isfile(gate):
            return "unavailable", f"claim gate not found at {gate}"
        try:
            proc = subprocess.run(
                [sys.executable, gate], input=text, capture_output=True,
                text=True, timeout=60, env=os.environ.copy(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "unavailable", f"claim gate failed to run ({exc})"
        if proc.returncode == 0:
            return "pass", ""
        if proc.returncode == 2:
            return "veto", (proc.stderr or "").strip()
        return "unavailable", (
            f"claim gate exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout or '').strip()}"
        )

    def _on_output(self, conn, sid: str, attempt_id: str, turn: _Turn,
                   event: AssistantOutput) -> bool:
        verdict, detail = self._claim_gate(event.text)
        self.dispatch_log.append(
            {"kind": "claim_gate", "attempt_id": attempt_id, "verdict": verdict}
        )
        db.record_conductor_event(conn, sid, attempt_id, "claim_gate",
                                  f"verdict={verdict}" + (f" detail={detail}" if detail else ""))
        if verdict == "pass":
            return False  # the turn may complete via AttemptCompleted
        # VETO (or a gate that cannot run): the output is rejected and the
        # turn does not advance state (§12.5). Fail closed either way.
        klass = "claim_gate_unavailable" if verdict == "unavailable" else "claim_veto"
        suffix = f" — {detail}" if detail else ""
        db.record_conductor_incident(
            conn, sid, klass,
            f"attempt {attempt_id}: output rejected (fail closed){suffix}",
        )
        db.set_conductor_attempt_status(conn, attempt_id, "cancelled",
                                        error_class="cancelled")
        turn.cancelled = True
        turn.stop = True
        return False

    # ------------------------------------------------------------------
    # usage / budget
    # ------------------------------------------------------------------

    def _on_usage(self, conn, sid: str, attempt_id: str, budget_per_attempt,
                  turn: _Turn, event: Usage) -> bool:
        if event.attempt_id != attempt_id:
            # §9 invalid adapter protocol: the adapter reported usage under a
            # DIFFERENT attempt id. Usage is never silently applied to another
            # row on the event's say-so — the turn fails through the existing
            # protocol path (incident + interrupted + circuit breaker +
            # recovery_required).
            return self._protocol_error(
                conn, sid, attempt_id,
                f"usage event names attempt {event.attempt_id!r} while the "
                f"turn is {attempt_id!r} — usage misattribution refused",
                turn,
            )
        row = db.record_attempt_usage(conn, attempt_id, event.tokens)
        if budget_per_attempt is not None and (row["usage"] or 0) > budget_per_attempt:
            # Over budget: cancelled — NOT a research result — and the lane is
            # skipped (no completion, no further events processed).
            db.record_conductor_incident(
                conn, sid, "budget_exceeded",
                f"attempt {attempt_id}: usage {row['usage']} tokens exceeds "
                f"the per-attempt budget {budget_per_attempt}",
            )
            db.set_conductor_attempt_status(conn, attempt_id, "cancelled",
                                            error_class="cancelled")
            turn.cancelled = True
            turn.stop = True
        return False

    # ------------------------------------------------------------------
    # structured errors (§9 table, row by row)
    # ------------------------------------------------------------------

    def _on_structured_error(self, conn, sid: str, attempt_id: str, turn: _Turn,
                             event: StructuredError) -> bool:
        klass = event.error_class
        if klass == "timeout":
            if turn.dispatched_mutating:
                # §12.7: a possibly-mutating tool ran — UNCERTAIN; retry only
                # after reconciliation, the action is never repeated blindly.
                db.set_conductor_attempt_status(conn, attempt_id, "uncertain",
                                                error_class="timeout")
                db.record_conductor_incident(
                    conn, sid, "uncertain_mutation",
                    f"attempt {attempt_id}: hung after a possibly-mutating tool — "
                    f"target state requires reconciliation{self._observed_note(turn)}",
                )
            elif turn.dispatched_any:
                # §9: read-only tool observed — preserve output, no answer.
                db.set_conductor_attempt_status(conn, attempt_id, "interrupted",
                                                error_class="timeout")
                db.record_conductor_incident(
                    conn, sid, "timeout_after_readonly",
                    f"attempt {attempt_id}: hung after a read-only tool"
                    f"{self._observed_note(turn)}",
                )
            else:
                # §12.6: nothing was dispatched — retry is a NEW attempt.
                db.set_conductor_attempt_status(conn, attempt_id, "interrupted",
                                                error_class="timeout")
                db.record_conductor_incident(
                    conn, sid, "timeout_before_dispatch",
                    f"attempt {attempt_id}: hung before any tool dispatch — "
                    "retry is a NEW attempt with zero duplicate work",
                )
            turn.stop = True
            return False
        if klass in ("auth", "rate_limit"):
            # §12.8: provider failure -> PAUSE. Never a research result, never
            # an empty lane; resume continues pending work after remediation.
            db.set_conductor_attempt_status(conn, attempt_id, "interrupted",
                                            error_class=klass)
            db.record_conductor_incident(
                conn, sid,
                "provider_auth" if klass == "auth" else "provider_rate_limit",
                f"attempt {attempt_id}: {event.detail}",
            )
            db.set_conductor_session_status(conn, sid, "paused")
            turn.stop = True
            return True  # stop the loop
        if klass == "crash":
            # §9 crash row: stop new dispatch, mark interrupted if safe.
            db.set_conductor_attempt_status(conn, attempt_id, "interrupted",
                                            error_class="crash")
            db.record_conductor_incident(conn, sid, "crash",
                                         f"attempt {attempt_id}: {event.detail}")
            session = db.get_conductor_session(conn, sid)
            if session["status"] in ("running", "degraded"):
                db.set_conductor_session_status(conn, sid, "degraded")
            turn.stop = True
            return True  # stop new dispatch
        if klass == "protocol":
            return self._protocol_error(conn, sid, attempt_id, event.detail, turn)
        if klass == "disk_full":
            # §12.9: freeze — recovery_required, all dispatch refused.
            db.set_conductor_attempt_status(conn, attempt_id, "interrupted",
                                            error_class="disk_full")
            db.record_conductor_incident(conn, sid, "disk_full",
                                         f"attempt {attempt_id}: {event.detail}")
            session = db.get_conductor_session(conn, sid)
            if session["status"] in ("running", "degraded"):
                db.set_conductor_session_status(conn, sid, "recovery_required")
            turn.stop = True
            return True
        # klass == "cancelled": the harness reported the turn cancelled.
        db.set_conductor_attempt_status(conn, attempt_id, "cancelled",
                                        error_class="cancelled")
        db.record_conductor_incident(conn, sid, "cancelled",
                                     f"attempt {attempt_id}: {event.detail}")
        turn.cancelled = True
        turn.stop = True
        return False

    def _protocol_error(self, conn, sid: str, attempt_id: str, detail: str,
                        turn: _Turn) -> bool:
        """§9 invalid adapter protocol: incident + interrupted attempt +
        circuit breaker OPEN + session recovery_required. doctor() passing is
        the only path forward."""
        db.record_conductor_event(conn, sid, attempt_id, "error",
                                  f"protocol: {detail}")
        db.record_conductor_incident(conn, sid, "protocol_violation",
                                     f"attempt {attempt_id}: {detail}")
        current = db.get_conductor_attempt(conn, attempt_id)
        if current["status"] == "running":
            db.set_conductor_attempt_status(conn, attempt_id, "interrupted",
                                            error_class="protocol")
        with contextlib.suppress(Exception):
            self._adapter.cancel_turn(attempt_id)  # best-effort teardown
        session = db.get_conductor_session(conn, sid)
        if session["status"] in ("running", "degraded"):
            db.set_conductor_session_status(conn, sid, "recovery_required")
        self._circuit_open = True
        turn.stop = True
        return True

    @staticmethod
    def _observed_note(turn: _Turn) -> str:
        if not turn.observed:
            return ""
        operation_id, output, _ok = turn.observed[-1]
        return f" — observed output of {operation_id}: {output.strip()[:300]}"

    # ------------------------------------------------------------------
    # pause / resume / abort (§5 graph via the kernel)
    # ------------------------------------------------------------------

    def _reattach_external_session(self, session: dict) -> None:
        if not self._adapter_registry_name:
            return
        self._adapter.start_session({
            "session_id": session["id"],
            "target_id": session["target_id"],
            "rounds": session["rounds"],
            "reattach": True,
        })

    def pause_run(self, conn, session_id: str) -> dict:
        """Pause an active session; running adapter turns are cancelled.
        Illegal pauses (terminal sessions, preflight) surface the kernel's
        BLOCKED refusal."""
        session = self._session_or_block(conn, session_id)
        self._reattach_external_session(session)
        for attempt in db.list_conductor_attempts(conn, session["id"]):
            if attempt["status"] == "running":
                self._adapter.cancel_turn(attempt["id"])
        return db.set_conductor_session_status(conn, session["id"], "paused")

    def resume_run(self, conn, session_id: str) -> dict:
        """Resume PENDING work: for round 1..session.rounds x 4 lanes, a cell
        is pending when its latest attempt is missing or ready/running/
        interrupted/cancelled; completed/research_blocked cells are done; an
        uncertain cell blocks its lane until reconciled. Refuses a frozen
        (recovery_required) session outright."""
        session = self._session_or_block(conn, session_id)
        sid = session["id"]
        if session["status"] == "recovery_required":
            raise ValueError(
                f"BLOCKED: session {sid} is recovery_required — resume refused; "
                "doctor() the adapter, then recover or abort (blueprint §9/§12.9)"
            )
        if session["status"] not in ("paused", "degraded", "running"):
            raise ValueError(
                f"BLOCKED: session {sid} is '{session['status']}' — only a paused, "
                "degraded or running session can resume"
            )
        if self._circuit_open:
            raise ValueError(
                "BLOCKED: adapter circuit breaker is open — run conductor.doctor(); "
                "until it passes, all dispatch is refused"
            )
        rounds = session["rounds"]
        if rounds is None:
            raise ValueError(
                f"BLOCKED: session {sid} has no declared rounds — cannot resume"
            )
        self._reattach_external_session(session)
        db.set_conductor_session_status(conn, sid, "running")
        self._run_rounds(conn, sid, rounds, session["budget"])
        final = db.get_conductor_session(conn, sid)
        if final["status"] == "completed":
            self._adapter.stop_session(sid)
        return final

    def abort_run(self, conn, session_id: str) -> dict:
        """Abort from any active state (running/degraded/paused/
        recovery_required). Terminal sessions and preflight surface the
        kernel's BLOCKED refusal. After abort, all new dispatch is refused."""
        session = self._session_or_block(conn, session_id)
        sid = session["id"]
        if session["status"] in ("completed", "aborted"):
            raise ValueError(
                f"BLOCKED: session {sid} is already '{session['status']}' — a "
                "terminal session cannot be aborted"
            )
        self._reattach_external_session(session)
        for attempt in db.list_conductor_attempts(conn, sid):
            if attempt["status"] == "running":
                self._adapter.cancel_turn(attempt["id"])
        self._adapter.stop_session(sid)
        return db.set_conductor_session_status(conn, sid, "aborted")

    # ------------------------------------------------------------------
    # retry / reconcile (§12.6, §12.7, §12.10)
    # ------------------------------------------------------------------

    def retry_attempt(self, conn, attempt_id: str,
                      model_profile: Optional[str] = None) -> dict:
        """Retry as a NEW child attempt (parent_attempt_id) and re-run the
        turn. Gates: session running/degraded; no unresolved uncertain attempt
        on that lane; the model profile must equal the session-pinned one
        (a different profile is a refusal PLUS a reconfiguration_refused
        incident — no fallback without explicit re-configuration, §12.10)."""
        attempt = db.get_conductor_attempt(conn, attempt_id)
        if attempt is None:
            raise ValueError(f"BLOCKED: conductor attempt '{attempt_id}' does not exist")
        sid = attempt["session_id"]
        session = db.get_conductor_session(conn, sid)
        if self._circuit_open:
            raise ValueError(
                "BLOCKED: adapter circuit breaker is open — run conductor.doctor(); "
                "until it passes, all dispatch is refused"
            )
        if session["status"] == "recovery_required":
            raise ValueError(
                f"BLOCKED: session {sid} is recovery_required — dispatch is frozen; "
                "doctor() the adapter, then recover or abort (blueprint §12.9)"
            )
        if session["status"] not in ("running", "degraded"):
            raise ValueError(
                f"BLOCKED: session {sid} is '{session['status']}' — retries need a "
                "running or degraded session"
            )
        self._refuse_unresolved_uncertain(conn, session, attempt)
        self._refuse_profile_change(conn, session, attempt, model_profile)
        self._reattach_external_session(session)
        child = self._create_attempt(conn, sid, attempt["lane"], attempt["round"],
                                     parent_id=attempt_id)
        db.set_conductor_attempt_status(conn, child["id"], "running")
        self._dispatch(conn, sid, attempt["lane"], attempt["round"], child["id"],
                       session["budget"])
        return db.get_conductor_attempt(conn, child["id"])

    def _refuse_unresolved_uncertain(self, conn, session: dict, attempt: dict) -> None:
        """§12.7: a possibly-mutating action is never repeated automatically —
        every uncertain attempt on the lane needs its incident reconciled.

        The incident gates are structural (class ``uncertain_mutation``,
        ``resolved_at`` set); the incident->attempt link is the detail's
        anchored ``attempt <id>: `` needle — never a bare ``attempt <id>``
        substring, which collides across ids ("attempt A-1" also occurs
        inside "attempt A-10: ...")."""
        attempts = db.list_conductor_attempts(conn, session["id"])
        incidents = db.list_conductor_incidents(conn, session["id"])

        def reconciled(aid: str) -> bool:
            return any(
                i["class"] == "uncertain_mutation"
                and i["resolved_at"] is not None
                and _incident_names_attempt(i, aid)
                for i in incidents
            )

        blocked = [
            a["id"] for a in attempts
            if a["lane"] == attempt["lane"] and a["status"] == "uncertain"
            and not reconciled(a["id"])
        ]
        if blocked:
            raise ValueError(
                f"BLOCKED: lane '{attempt['lane']}' has unresolved uncertain "
                f"attempt(s) {blocked} — reconcile first (blueprint §12.7: a "
                "possibly-mutating action is never repeated automatically)"
            )

    def _refuse_profile_change(self, conn, session: dict, attempt: dict,
                               model_profile: Optional[str]) -> None:
        if model_profile is None:
            return  # the pinned profile rides again
        pinned_hash = session["model_profile_hash"]
        mismatch = False
        if pinned_hash:
            mismatch = _profile_hash(model_profile) != pinned_hash
        parent_profile = attempt["model_profile"]
        if parent_profile is not None:
            mismatch = mismatch or model_profile != parent_profile
        if mismatch:
            db.record_conductor_incident(
                conn, session["id"], "reconfiguration_refused",
                f"retry of {attempt['id']} refused: requested model profile "
                f"'{model_profile}' differs from the session-pinned profile — "
                "no fallback without explicit re-configuration",
            )
            raise ValueError(
                f"BLOCKED: model_profile '{model_profile}' does not match the "
                f"profile pinned on session {session['id']} — reconfiguration "
                "refused (blueprint §12.10: no model fallback, ever, without "
                "explicit re-configuration)"
            )

    def reconcile_attempt(self, conn, attempt_id: str, resolution: str) -> dict:
        """Resolve the uncertain attempt's incident (the operator asserts what
        actually happened to the target). Does NOT auto-retry: the attempt
        stays uncertain; the next retry creates the child.

        The lookup is structural first — class ``uncertain_mutation`` and
        ``resolved_at is None`` (unresolved) — and the incident->attempt link
        is the detail's anchored ``attempt <id>: `` needle, so resolving A-1
        can never pick up A-10's incident (the bare-substring form did)."""
        attempt = db.get_conductor_attempt(conn, attempt_id)
        if attempt is None:
            raise ValueError(f"BLOCKED: conductor attempt '{attempt_id}' does not exist")
        if attempt["status"] != "uncertain":
            raise ValueError(
                f"BLOCKED: attempt {attempt_id} is '{attempt['status']}' — only an "
                "uncertain attempt has an incident to reconcile (blueprint §12.7)"
            )
        incidents = [
            i for i in db.list_conductor_incidents(conn, attempt["session_id"])
            if i["class"] == "uncertain_mutation" and i["resolved_at"] is None
            and _incident_names_attempt(i, attempt_id)
        ]
        if not incidents:
            raise ValueError(
                f"BLOCKED: no unresolved uncertain_mutation incident found for "
                f"attempt {attempt_id}"
            )
        return db.resolve_conductor_incident(conn, incidents[-1]["id"], resolution)

    # ------------------------------------------------------------------
    # status / helpers
    # ------------------------------------------------------------------

    def status(self, conn, session_id: Optional[str] = None) -> dict:
        """{"session": ..., "attempts": [...], "incidents": [...],
        "next_action": str} — the latest session when session_id is None."""
        if session_id is None:
            session = db.latest_conductor_session(conn)
            if session is None:
                raise ValueError(
                    "BLOCKED: no conductor session exists yet — start one first"
                )
        else:
            session = db.get_conductor_session(conn, session_id)
            if session is None:
                raise ValueError(
                    f"BLOCKED: conductor session '{session_id}' does not exist"
                )
        attempts = db.list_conductor_attempts(conn, session["id"])
        incidents = db.list_conductor_incidents(conn, session["id"])
        return {
            "session": session,
            "attempts": attempts,
            "incidents": incidents,
            "next_action": compute_next_action(session, attempts, incidents),
        }

    def _session_or_block(self, conn, session_id: str) -> dict:
        session = db.get_conductor_session(conn, session_id)
        if session is None:
            raise ValueError(f"BLOCKED: conductor session '{session_id}' does not exist")
        return session

    @staticmethod
    def _latest_attempt(conn, sid: str, lane: str, round_no: int):
        rows = [
            a for a in db.list_conductor_attempts(conn, sid)
            if a["lane"] == lane and a["round"] == round_no
        ]
        return rows[-1] if rows else None  # ids are ascending

    @staticmethod
    def _has_pending_work(conn, sid: str, rounds: int) -> bool:
        """True when any (round, lane) cell's LATEST attempt is not a research
        result (missing/ready/running/interrupted/cancelled/uncertain all
        count as pending — §5: they are never results)."""
        for round_no in range(1, rounds + 1):
            for lane in db.CONDUCTOR_LANES:
                latest = Conductor._latest_attempt(conn, sid, lane, round_no)
                if latest is None or latest["status"] not in ("completed",
                                                              "research_blocked"):
                    return True
        return False

    def _pinned_profile(self, conn, sid: str, parent_id: Optional[str]) -> str:
        """The model profile name pinned by the session (verified against the
        sha256 recorded at create — §12.10)."""
        candidate = None
        if parent_id:
            parent = db.get_conductor_attempt(conn, parent_id)
            if parent is not None and parent["model_profile"]:
                candidate = parent["model_profile"]
        if candidate is None:
            for a in reversed(db.list_conductor_attempts(conn, sid)):
                if a["model_profile"]:
                    candidate = a["model_profile"]
                    break
        if candidate is None:
            candidate = self._profiles.get(sid)
        if candidate is None:
            raise ValueError(
                f"BLOCKED: cannot determine the model profile pinned by session "
                f"{sid} — no attempt records one and this conductor did not "
                "start the session"
            )
        session = db.get_conductor_session(conn, sid)
        pinned_hash = session["model_profile_hash"] if session else None
        if pinned_hash and _profile_hash(candidate) != pinned_hash:
            raise ValueError(
                f"BLOCKED: model profile '{candidate}' does not match the hash "
                f"pinned on session {sid} — refusing to dispatch against a "
                "re-pinned profile"
            )
        return candidate


def _profile_hash(model_profile: str) -> str:
    """The session's durable profile pin: sha256 of the profile name."""
    return hashlib.sha256(str(model_profile).encode("utf-8")).hexdigest()


def _incident_names_attempt(incident: dict, attempt_id: str) -> bool:
    """The incident->attempt link over the incident's detail text.

    The conductor records incident details as ``attempt <id>: ...``, so the
    match is anchored on that exact needle (colon included). A bare
    ``attempt <id>`` substring collides across ids — "attempt A-1" also
    occurs inside "attempt A-10: ..." — which once let reconciling A-10
    unblock A-1's retry and let reconcile_attempt(A-1) resolve A-10's
    incident. The kernel carries no attempt_id column on conductor_incident,
    so this anchored needle is the link; the class/resolved_at gates on the
    incident lookup stay structural.
    """
    return f"attempt {attempt_id}: " in (incident.get("detail") or "")
