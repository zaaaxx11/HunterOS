"""Interactive and scriptable operator console for the HUNT-OS CLI.

``hunt shell`` accepts ordinary hunt commands without the ``hunt`` prefix.
Bare ``hunt`` opens the guided target flow; ``hunt <args>`` removes the
redundant prefix and dispatches through the ordinary CLI door. Built-ins
provide ``help``, ``macros``, ``last``, aliases (``n``, ``b``, and
``s``), and clean exit commands.  The ``firstblood``, ``wave``, and ``report``
macros guide common workflows; an argument after ``wave`` or ``report`` still
runs the ordinary CLI verb.

``hunt shell --script FILE`` replays one UTF-8 command per line, ignores blank
and ``#`` comment lines, and stops fail-closed at the first non-zero exit.  The
shell is only an argv front-end: it never opens the ledger itself, and every
real command crosses ``huntos.cli.main.main`` so the normal project lock,
evidence gates, and ``BLOCKED:`` exit contract remain authoritative.
"""
from __future__ import annotations

import cmd
import io
import os
import re
import shlex
import sqlite3
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Callable, Sequence

from .terminal import strip_ansi

# Unified refusal shape (Phase 3, cli/errors.py): BLOCKED: <what> | NEXT:
# <exact cmd>.  Import-light (stdlib re only), so the shell keeps its
# no-DB-import startup contract; the fallback preserves the bare prefix.
try:
    from .errors import blocked as _blocked_line
except ImportError:  # pragma: no cover - errors is shipped; fallback only
    def _blocked_line(what, next_cmd=None):  # type: ignore[misc]
        text = str(what)
        if not text.startswith("BLOCKED:"):
            text = f"BLOCKED: {text}"
        return f"{text} | NEXT: {next_cmd}" if next_cmd else text

# Identity prompt reads the single-source context resolver (cli/context.py):
# current target + phase + open wave + latest conductor session, resolved via
# read-only queries that never create or write the db.  The resolver is
# stdlib-only (sqlite3/os), so importing it cannot pull in the database
# kernel; the fallback keeps the bare prompt when it is unavailable.
try:
    from .context import format_context_line, format_prompt, resolve_context
except ImportError:  # pragma: no cover - context is shipped; fallback only
    def resolve_context(db_path=None):  # type: ignore[misc]
        return {"target_id": None}

    def format_prompt(ctx) -> str:  # type: ignore[misc]
        return "hunt> "

    def format_context_line(ctx) -> str:  # type: ignore[misc]
        return "(no target in context)"


MACROS = ("firstblood", "wave", "report")

# Verb/action discovery reads the single-source registry (cli/registry.py) so
# completion and help can never drift from the argparse parser.  The literal
# fallback preserves the no-DB-import startup contract when the registry is
# unavailable: completion and help must not import the database kernel merely
# to discover verbs.
try:
    from .registry import GROUP_ACTIONS as _REGISTRY_ACTIONS
    from .registry import VERBS as _REGISTRY_VERBS

    HUNT_VERBS: tuple[str, ...] = _REGISTRY_VERBS
    _GROUP_ACTIONS: dict[str, tuple[str, ...]] = dict(_REGISTRY_ACTIONS)
except ImportError:  # pragma: no cover - registry is shipped; fallback only
    HUNT_VERBS = (
        "target",
        "score",
        "phase",
        "finding",
        "poc",
        "verify",
        "challenge",
        "artifact",
        "wave",
        "report",
        "verify-report",
        "project",
        "lesson",
        "klass",
        "brief",
        "next",
        "lead",
        "oracle",
        "surface",
        "coverage",
        "chain",
        "fuzz",
        "status",
        "install",
        "harness",
        "doctor",
        "adapter",
        "run",
        "shell",
        "help",
    )

    _GROUP_ACTIONS = {
        "target": ("prepare", "add", "list", "roe", "archive"),
        "adapter": ("add", "list", "doctor", "remove"),
        "finding": ("add", "promote", "overturn", "retitle"),
        "poc": ("run",),
        "wave": ("open", "close", "reaudit"),
        "project": ("bind", "status"),
        "lesson": ("add", "list", "reword"),
        "klass": ("list", "add"),
        "lead": ("add", "set-half", "mutate", "set", "next", "park", "reopen", "kill", "promote", "list"),
        "surface": ("add", "list"),
        "chain": ("add", "link", "show", "novelty"),
        "run": ("start", "status", "pause", "resume", "abort", "retry", "reconcile"),
    }

_BANNER = (
    "HUNT-OS shell — the same CLI gate and the same BLOCKED exit 2.\n"
    "Enter hunt commands without the 'hunt' prefix.\n"
    "help [verb] | macros | aliases: n=next, b=brief, s=status | quit\n"
)


Ask = Callable[[str], str | None]


class _TerminalCapture(io.StringIO):
    """Capture text while preserving the outer stream's terminal capability."""

    def __init__(self, stream):
        super().__init__()
        self._stream = stream

    def isatty(self) -> bool:
        try:
            return bool(self._stream.isatty())
        except (AttributeError, OSError):
            return False

    def fileno(self) -> int:
        return self._stream.fileno()


def split_hunt_args(line: str, windows: bool | None = None) -> list[str]:
    """Split one shell line while preserving native Windows path separators.

    POSIX mode follows ordinary shell quoting and escaping.  In Windows mode,
    quotes still group whitespace but backslashes are ordinary characters, so
    paths such as ``C:\\Users\\operator\\poc.py`` arrive unchanged.
    """
    if windows is None:
        windows = os.name == "nt"
    if not line.strip() or line.lstrip().startswith("#"):
        return []
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    # Only comment-only lines are special.  An unquoted '#' may legitimately
    # be part of a URL, report path, finding title, or evidence reference.
    lexer.commenters = ""
    if windows:
        lexer.escape = ""
    return list(lexer)


def _cli_module():
    """Load the CLI only when a command actually needs to cross its gate."""
    # This import form is the shell's contract.  Older package __init__ files
    # exported the function under the same name, so retain a compatibility
    # fallback while ensuring execution still goes through module.main(argv).
    from . import main as cli_main

    if hasattr(cli_main, "main"):
        return cli_main
    module = sys.modules.get(f"{__package__}.main")
    if module is None:
        import importlib

        module = importlib.import_module(".main", __package__)
    return module


def _display_argv(argv: Sequence[str]) -> str:
    return "hunt " + shlex.join([str(part) for part in argv])


class HuntShell(cmd.Cmd):
    """A thin command loop over the normal ``hunt`` CLI entry point."""

    prompt = "hunt> "

    def __init__(
        self,
        hint: bool = True,
        ask: Ask | None = None,
        use_banner: bool = True,
        use_history: bool = True,
    ):
        super().__init__()
        self.hint = hint
        self.ask = ask or input
        self.use_banner = use_banner
        self.use_history = use_history
        self.intro = _BANNER if use_banner else None
        self.last_rc = 0
        self.last_output = ""
        self.last_argv: list[str] = []
        self._readline = None
        hunt_home = os.environ.get("HUNT_HOME")
        history_root = Path(hunt_home).expanduser() if hunt_home else Path.home() / ".huntos"
        self._history_path = history_root / "shell_history"
        self._setup_readline()
        self.refresh_prompt()

    # --- identity: where am I ---------------------------------------------

    def refresh_prompt(self) -> str:
        """Re-resolve context (read-only) and set the identity prompt.

        Called once at startup and after every command via postcmd: the
        prompt always names the current target + phase (``hunt t1:scoring``)
        with an optional session suffix, or falls back to the bare
        ``hunt> `` when the ledger is empty or ambiguous.  No background
        thread — one bounded read per command, unknown-safe.
        """
        self.prompt = format_prompt(resolve_context())
        return self.prompt

    # --- command dispatch -------------------------------------------------

    def emptyline(self):
        """An empty line is a no-op, never a repeat of the last write."""
        return False

    def postcmd(self, stop, line: str):
        """Only explicit exit built-ins may stop the interactive loop.

        ``cmd.Cmd`` normally treats any truthy command result as a request to
        exit.  Hunt handlers return exit code 2 for a refusal, so forwarding
        that value directly would turn an ordinary BLOCKED gate into an
        accidental shell exit.  Every command also refreshes the identity
        prompt (read-only context re-resolve), so the prompt always names
        the current target + phase.
        """
        self.refresh_prompt()
        command = line.strip().split(maxsplit=1)[0] if line.strip() else ""
        return bool(stop) and command in {"quit", "exit", "EOF"}

    def default(self, line: str):
        try:
            argv = split_hunt_args(line)
        except ValueError as exc:
            return self._blocked(f"cannot parse command: {exc}")
        return self.run_command(argv)

    def run_command(self, argv: Sequence[str]) -> int:
        """Run argv through the regular CLI while retaining its last result."""
        if not argv:
            return self.last_rc

        command = [str(part) for part in argv]
        if command[0] == "shell":
            message = "BLOCKED: hunt shell cannot run inside hunt shell"
            print(message, file=sys.stderr)
            self.last_rc = 2
            self.last_output = ""
            self.last_argv = command
            return 2

        cli_main = _cli_module()
        real_stdout, real_stderr = sys.stdout, sys.stderr
        stdout_buffer = _TerminalCapture(real_stdout)
        stderr_buffer = _TerminalCapture(real_stderr)
        rc = 0
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            try:
                result = cli_main.main(list(command))
                rc = result if isinstance(result, int) else 0
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else 2
            except KeyboardInterrupt:
                print("^C — command interrupted", file=sys.stderr)
                rc = 2

        captured_out = stdout_buffer.getvalue()
        captured_err = stderr_buffer.getvalue()
        if captured_out:
            print(captured_out, end="", file=real_stdout)
        if captured_err:
            print(captured_err, end="", file=real_stderr)

        self.last_rc = rc
        self.last_output = strip_ansi(captured_out)
        self.last_argv = command
        self.maybe_hint(command, rc)
        return rc

    def maybe_hint(self, argv: Sequence[str], rc: int) -> None:
        """Print ``hunt next`` after a successful ledger write."""
        if not self.hint or rc != 0 or not argv:
            return
        # argparse help exits zero but performs no write.
        if "-h" in argv or "--help" in argv:
            return
        command = str(argv[0])
        if command in {"install", "doctor", "shell"}:
            return
        cli_main = _cli_module()
        if command in getattr(cli_main, "READ_ONLY_COMMANDS", ()):
            return
        action = str(argv[1]) if len(argv) > 1 else None
        if action in getattr(cli_main, "READ_ONLY_ACTIONS", {}).get(command, ()):
            return
        try:
            cli_main.main(["next"])
        except SystemExit:
            # A hint cannot change a command that already succeeded.
            pass

    # --- scripts ----------------------------------------------------------

    def run_script(self, path: str | os.PathLike[str]) -> int:
        shown_path = os.fspath(path)
        script_path = Path(os.path.expanduser(shown_path))
        if not script_path.is_file():
            print(f"BLOCKED: script not found: {shown_path}", file=sys.stderr)
            return 2
        try:
            lines = script_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            print(f"BLOCKED: cannot read script {shown_path}: {exc}", file=sys.stderr)
            return 2

        completed = 0
        for line_number, raw_line in enumerate(lines, 1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                argv = split_hunt_args(raw_line)
            except ValueError as exc:
                print(f"BLOCKED: cannot parse script line {line_number}: {exc}", file=sys.stderr)
                print(f"script stopped at line {line_number} (rc 2): {raw_line}", file=sys.stderr)
                return 2
            if argv and argv[0] == "shell":
                print(
                    f"BLOCKED: hunt shell cannot run inside hunt shell (script line {line_number})",
                    file=sys.stderr,
                )
                print(f"script stopped at line {line_number} (rc 2): {raw_line}", file=sys.stderr)
                return 2
            rc = self.run_command(argv)
            if rc != 0:
                print(f"script stopped at line {line_number} (rc {rc}): {raw_line}", file=sys.stderr)
                return 2
            completed += 1
        print(f"script complete: {completed} command(s), all exit 0")
        return 0

    # --- shell built-ins --------------------------------------------------

    def do_help(self, arg: str):
        """Show grouped command help, or run ``hunt <verb> --help``."""
        arg = arg.strip()
        if not arg:
            self.stdout.write(_BANNER)
            try:
                from .registry import grouped_help

                self.stdout.write(grouped_help() + "\n")
            except ImportError:  # pragma: no cover - registry fallback
                self.stdout.write("commands: " + " ".join(HUNT_VERBS) + "\n")
            self.stdout.write("macros: firstblood, wave, report\n")
            return 0
        try:
            words = split_hunt_args(arg)
        except ValueError as exc:
            return self._blocked(f"cannot parse help request: {exc}")
        if not words:
            return 0
        return self.run_command([words[0], "--help"])

    def do_macros(self, _arg: str):
        """List the guided, fail-closed workflows."""
        self.stdout.write("firstblood  add a target, set RoE, then open its brief and next step\n")
        self.stdout.write("wave        open, close, and re-audit one hunt wave\n")
        self.stdout.write("report      write and verify a disclosure report\n")
        return 0

    def do_last(self, _arg: str):
        """Show the argv and exit code of the last CLI command."""
        if not self.last_argv:
            self.stdout.write("(no command yet)\n")
            return 0
        self.stdout.write(f"rc {self.last_rc}: {' '.join(self.last_argv)}\n")
        return self.last_rc

    def do_context(self, _arg: str):
        """Show where you are: target + phase + open wave + session."""
        self.stdout.write(format_context_line(resolve_context()) + "\n")
        return 0

    def do_refresh(self, _arg: str):
        """Re-resolve context now and show the new prompt line."""
        self.stdout.write(self.refresh_prompt() + "\n")
        return 0

    def do_quit(self, _arg: str):
        """Leave the hunt shell."""
        return True

    def do_exit(self, arg: str):
        """Leave the hunt shell."""
        return self.do_quit(arg)

    def do_EOF(self, _arg: str):
        """Leave the shell on Ctrl-D/Ctrl-Z."""
        self.stdout.write("\n")
        return True

    def do_hunt(self, arg: str):
        """Strip a redundant hunt prefix, or open target intake when bare."""
        if not arg.strip():
            return self.target_wizard()
        try:
            argv = split_hunt_args(arg)
        except ValueError as exc:
            return self._blocked(f"cannot parse hunt arguments: {exc}")
        return self.run_command(argv)

    def target_wizard(self) -> int:
        """Preflight the selected harness, then assemble confirmed CLI argv."""
        from huntos.core.target_source import classify_target_source, default_target_name

        first = self._answer("harness [mock] (or target source for mock): ")
        # Keep the older one-step mock wizard script-compatible: a URL/path in
        # the first answer implies mock, while an adapter name explicitly opts
        # into that harness before any target questions are asked.
        looks_like_target = (
            "://" in first or first.startswith((".", "~/", "/", "\\"))
            or Path(first).exists()
            or first.startswith(("github:", "github.com/", "git@github.com:"))
        )
        if looks_like_target:
            adapter, source_raw = "mock", first
        else:
            adapter = first or "mock"
            source_raw = self._answer("target source (URL, GitHub, or folder): ")
        if not _run_harness_preflight(adapter):
            return 2
        if adapter == "mock":
            self.stdout.write("SIMULATED — no external agents invoked\n")
        if not source_raw:
            self.stdout.write("wizard cancelled; nothing recorded\n")
            self.last_rc = 2
            return 2
        try:
            source = classify_target_source(source_raw)
        except ValueError as exc:
            return self._blocked(str(exc))
        self.stdout.write(f"detected: {source.kind}\n")
        self.stdout.write(f"canonical: {source.canonical}\n")
        self.stdout.write(f"workspace: {source.workspace or '(none)'}\n")

        actions = self._answer("allowed actions [recon,read]: ") or "recon,read"
        authorization = self._answer("authorization note (required): ")
        if not authorization:
            self.stdout.write("wizard cancelled; nothing recorded\n")
            self.last_rc = 2
            return 2
        if looks_like_target:
            # Compatibility slot for the original mock-first wizard scripts.
            legacy_adapter = self._answer("adapter [mock]: ")
            if legacy_adapter:
                return self._blocked(
                    "harness must be selected before target intake; restart the wizard"
                )
        prepare = [
            "target", "prepare", source_raw,
            "--name", default_target_name(source),
            "--actions", actions,
            "--authorization-note", authorization,
        ]
        self.stdout.write(_display_argv(prepare) + "\n")
        if not self._answer("prepare this target? [y/N] ").lower().startswith("y"):
            self.stdout.write("wizard cancelled; nothing recorded\n")
            self.last_rc = 2
            return 2
        if self.run_command(prepare) != 0:
            self.stdout.write("wizard stopped: target preparation failed\n")
            return 2
        match = re.search(r"target #(\d+) prepared", self.last_output)
        if match is None:
            return self._blocked("could not read prepared target id from CLI output")
        target_id = match.group(1)

        if adapter == "mock":
            self.stdout.write("SIMULATED — no external agents invoked\n")
        start = [
            "run", "start", "--target", target_id, "--rounds", "1",
            "--adapter", adapter, "--page",
        ]
        self.stdout.write(_display_argv(start) + "\n")
        if not self._answer("start this run? [y/N] ").lower().startswith("y"):
            self.stdout.write(
                f"target #{target_id} remains recorded; run not started\n"
            )
            self.last_rc = 2
            return 2
        return self.run_command(start)

    def do_n(self, arg: str):
        """Alias for ``next``."""
        return self._run_alias("next", arg)

    def do_b(self, arg: str):
        """Alias for ``brief``."""
        return self._run_alias("brief", arg)

    def do_s(self, arg: str):
        """Alias for ``status``."""
        return self._run_alias("status", arg)

    def _run_alias(self, verb: str, arg: str) -> int:
        try:
            extra = split_hunt_args(arg)
        except ValueError as exc:
            return self._blocked(f"cannot parse alias arguments: {exc}")
        return self.run_command([verb, *extra])

    # --- guided macros ----------------------------------------------------

    def do_firstblood(self, _arg: str):
        """Guide the minimum target + RoE + opening-read workflow."""
        name = self._required("target name: ", "firstblood requires a target name")
        if name is None:
            return 2
        url = self._required("target url: ", "firstblood requires a target URL")
        if url is None:
            return 2
        chain = self._answer("chain [evm]: ") or "evm"
        if self._macro_write(["target", "add", name, url, "--chain", chain]) != 0:
            return 2
        match = re.search(r"target #(\d+) added", self.last_output)
        if match is None:
            self.stdout.write("macro stopped: could not read the new target id from output\n")
            self.last_rc = 2
            return 2
        target_id = match.group(1)

        hosts = self._answer("allowed hosts (comma-separated, optional): ")
        actions = self._answer("allowed actions [recon,read]: ") or "recon,read"
        roe_argv = ["target", "roe", target_id, "--actions", actions]
        if hosts:
            roe_argv.extend(["--hosts", hosts])
        if self._macro_write(roe_argv) != 0:
            return 2
        if self._macro_read(["brief", target_id]) != 0:
            return 2
        if self._macro_read(["next", "--target", target_id]) != 0:
            return 2
        self.stdout.write("macro complete\n")
        return 0

    def do_wave(self, arg: str):
        """Run ``hunt wave ...`` or guide a wave when called without arguments."""
        if arg.strip():
            return self._run_alias("wave", arg)
        target_id = self._required("target id: ", "wave requires a target id")
        if target_id is None:
            return 2
        lanes = self._answer("lanes [4]: ") or "4"
        if self._macro_write(["wave", "open", target_id, lanes]) != 0:
            return 2
        match = re.search(r"wave #(\d+)", self.last_output)
        if match is None:
            wave_id = self._required("wave id: ", "wave requires a wave id")
            if wave_id is None:
                return 2
        else:
            wave_id = match.group(1)

        if self._macro_read(["next", "--target", target_id]) != 0:
            return 2
        verdict = self._required(
            "verdict [continue|exhausted|pivot]: ", "verdict must be continue|exhausted|pivot"
        )
        if verdict is None:
            return 2
        verdict = verdict.lower()
        if verdict not in {"continue", "exhausted", "pivot"}:
            return self._blocked("verdict must be continue|exhausted|pivot")
        if self._macro_write(
            ["wave", "close", "--wave-id", wave_id, "--verdict", verdict]
        ) != 0:
            return 2

        summary = self._required(
            "re-audit summary (min 20 chars): ",
            "reaudit summary needs at least 20 characters",
        )
        if summary is None:
            return 2
        if len(summary.strip()) < 20:
            return self._blocked("reaudit summary needs at least 20 characters")
        if self._macro_write(
            ["wave", "reaudit", "--wave-id", wave_id, "--summary", summary]
        ) != 0:
            return 2
        self.stdout.write("macro complete\n")
        return 0

    def do_report(self, arg: str):
        """Run ``hunt report ...`` or guide a report when called without arguments."""
        if arg.strip():
            return self._run_alias("report", arg)
        target_id = self._required("target id: ", "report requires a target id")
        if target_id is None:
            return 2
        output = self._answer("output [report.md]: ") or "report.md"
        if self._macro_write(["report", target_id, "--out", output]) != 0:
            return 2
        if self._macro_read(["verify-report", output]) != 0:
            return 2
        self.stdout.write("macro complete\n")
        return 0

    def _answer(self, prompt: str) -> str:
        try:
            answer = self.ask(prompt)
        except (EOFError, KeyboardInterrupt):
            print("", file=self.stdout)
            return ""
        return "" if answer is None else str(answer).strip()

    def _required(self, prompt: str, _message: str) -> str | None:
        answer = self._answer(prompt)
        if not answer:
            self.stdout.write("macro aborted\n")
            self.last_rc = 2
            return None
        return answer

    def _macro_write(self, argv: Sequence[str]) -> int:
        print(_display_argv(argv), file=self.stdout)
        answer = self._answer("run it? [y/N] ")
        if not answer.lower().startswith("y"):
            self.stdout.write("macro aborted\n")
            self.last_rc = 2
            return 2
        rc = self.run_command(argv)
        if rc != 0:
            self.stdout.write(f"macro stopped: {_display_argv(argv)} exited {rc}\n")
        return rc

    def _macro_read(self, argv: Sequence[str]) -> int:
        print(f"[read-only] {_display_argv(argv)}", file=self.stdout)
        rc = self.run_command(argv)
        if rc != 0:
            self.stdout.write(f"macro stopped: {_display_argv(argv)} exited {rc}\n")
        return rc

    def _blocked(self, message: str, next_cmd: str | None = None) -> int:
        text = _blocked_line(message, next_cmd)
        print(text, file=sys.stderr)
        self.last_rc = 2
        self.last_output = text + "\n"
        return 2

    # --- completion and history ------------------------------------------

    def completenames(self, text: str, *ignored):
        names = set(super().completenames(text, *ignored))
        names.update(HUNT_VERBS)
        names.update(MACROS)
        return sorted(name for name in names if name.startswith(text))

    def completedefault(self, text: str, line: str, begidx: int, _endidx: int):
        try:
            before = split_hunt_args(line[:begidx])
        except ValueError:
            return []
        if len(before) == 1:
            candidates = _GROUP_ACTIONS.get(before[0], ())
            return [item for item in candidates if item.startswith(text)]
        return []

    def _setup_readline(self) -> None:
        if not self.use_history:
            return
        try:
            import readline
        except ImportError:
            return
        self._readline = readline
        try:
            readline.set_completer_delims(" \t\n")
            if self._history_path.is_file():
                readline.read_history_file(str(self._history_path))
        except (OSError, ValueError):
            pass

    def postloop(self) -> None:
        if self._readline is None or not self.use_history:
            return
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._readline.write_history_file(str(self._history_path))
        except OSError:
            pass


def _ledger_has_targets() -> bool:
    """Return whether a readable ledger has a target, without producing output."""
    db_path = os.path.expanduser(os.environ.get("HUNT_DB") or "~/.huntos/hunt.db")
    if not os.path.exists(db_path):
        return False
    try:
        with sqlite3.connect(db_path) as conn:
            return conn.execute("SELECT 1 FROM targets LIMIT 1").fetchone() is not None
    except (OSError, sqlite3.Error):
        return False


def _run_harness_preflight(name: str = "mock") -> bool:
    """Check one explicit harness before guided intake asks questions."""
    try:
        cli_main = _cli_module()
        if name in getattr(cli_main, "HARNESS_SKILL_ADAPTERS", ()):
            return cli_main.main(["harness", "doctor", name]) == 0
        cli_main._adapter_preflight(name)
    except (Exception, KeyboardInterrupt) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("^C — guided hunt cancelled", file=sys.stderr)
        else:
            message = str(exc) or "harness preflight failed"
            print(_blocked_line(message), file=sys.stderr)
        return False
    return True


def run_shell(args) -> int:
    """Run script mode or an interactive hunt shell from argparse arguments."""
    script = getattr(args, "script", None)
    if script:
        return HuntShell(hint=False, use_banner=False, use_history=False).run_script(script)

    quiet = bool(getattr(args, "quiet", False))
    shell = HuntShell(
        hint=bool(getattr(args, "hint", True)),
        use_banner=False,
        use_history=not bool(getattr(args, "no_history", False)),
    )
    if not quiet:
        print(_BANNER, end="")
    guided = bool(getattr(args, "guided", False))
    if guided:
        stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
        stdout_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        if stdin_tty and stdout_tty:
            if not _run_harness_preflight():
                return 2
            if shell.target_wizard() != 0:
                return 2
    if _ledger_has_targets():
        shell.run_command(["next"])
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\n^C — leaving hunt shell")
        shell.postloop()
    except EOFError:
        # stdin exhausted (piped input ends without quit/EOF): leave cleanly.
        shell.postloop()
    return 0
