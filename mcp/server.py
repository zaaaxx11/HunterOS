#!/usr/bin/env python3
"""HunterOS MCP server: stdio JSON-RPC 2.0, stdlib only.

Exposes a fixed set of HunterOS CLI verbs as MCP tools. Every tool call runs
the CLI as a subprocess with an argv list (shell=False). Domain failures are
returned as tool results with isError=true, never as JSON-RPC protocol errors.

Command resolution, in order:
  1. HUNT_CLI env: a command prefix, split with shlex.
  2. repo app/src exists (mcp/../app/src):
     [sys.executable, "-m", "huntos"] with PYTHONPATH set to app/src.
  3. ["hunt"] from PATH.

Importing this module has no side effects.
"""
from __future__ import annotations

import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT = 60.0
MAX_STR = 4000


# ---------------------------------------------------------------------------
# Logging and paths
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    try:
        sys.stderr.write(f"[hunter-os mcp] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _app_dir() -> Path:
    # server.py lives at <repo>/mcp/server.py
    here = Path(__file__).resolve()
    return here.parents[1] / "app"


def _app_src() -> Path:
    return _app_dir() / "src"


def _server_version() -> str:
    try:
        text = (_app_dir() / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, IndexError):
        return "0.0.0"
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "0.0.0"


# ---------------------------------------------------------------------------
# CLI resolution
# ---------------------------------------------------------------------------

def _split_cli(spec: str) -> list[str]:
    # A spec that is itself a path (possibly containing spaces, e.g.
    # "C:\Program Files\...") is one token, not a command line.
    bare = spec.strip().strip('"').strip("'")
    if bare and os.path.exists(bare):
        return [bare]
    # Path-like spec whose leading word is not a PATH command (e.g. a missing
    # "C:\Program Files\...\hunt.exe"): treat the whole spec as one program path.
    words = bare.split()
    if words and any(c in words[0] for c in "/\\:") and shutil.which(words[0]) is None:
        return [bare]
    if os.name == "nt":
        # posix=True would eat backslashes in Windows paths.
        tokens = shlex.split(spec, posix=False)
        out = []
        for t in tokens:
            if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
                t = t[1:-1]
            out.append(t)
        return out
    return shlex.split(spec)


def resolve_cli(environ=None) -> tuple[list[str], dict]:
    """Return (command prefix, extra env vars). May raise ValueError."""
    env = os.environ if environ is None else environ
    spec = (env.get("HUNT_CLI") or "").strip()
    if spec:
        return _split_cli(spec), {}
    src = _app_src()
    if src.is_dir():
        prev = env.get("PYTHONPATH", "")
        pp = str(src) + (os.pathsep + prev if prev else "")
        return [sys.executable, "-m", "huntos"], {"PYTHONPATH": pp}
    return ["hunt"], {}


# ---------------------------------------------------------------------------
# Argument validation and argv construction
# ---------------------------------------------------------------------------

class ArgError(ValueError):
    """Invalid tool arguments (maps to JSON-RPC -32602)."""


def _check_str(name: str, value, spec: dict) -> None:
    if not isinstance(value, str):
        raise ArgError(f"'{name}' must be a string")
    if "\x00" in value:
        raise ArgError(f"'{name}' contains a NUL byte")
    if len(value) < spec.get("minLength", 0):
        raise ArgError(f"'{name}' must not be empty")
    if len(value) > spec.get("maxLength", MAX_STR):
        raise ArgError(f"'{name}' is too long")
    if "enum" in spec and value not in spec["enum"]:
        raise ArgError(f"'{name}' must be one of {spec['enum']}")


def _check_value(name: str, value, spec: dict) -> None:
    t = spec["type"]
    if t == "string":
        _check_str(name, value, spec)
    elif t == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgError(f"'{name}' must be an integer")
        if value < spec.get("minimum", -(2**63)):
            raise ArgError(f"'{name}' must be >= {spec['minimum']}")
    elif t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ArgError(f"'{name}' must be a number")
        if not math.isfinite(value):
            raise ArgError(f"'{name}' must be finite")
    elif t == "array":
        if not isinstance(value, list):
            raise ArgError(f"'{name}' must be an array")
        for i, item in enumerate(value):
            _check_value(f"{name}[{i}]", item, spec["items"])
    else:  # pragma: no cover - schemas are defined in this file
        raise ArgError(f"unsupported schema type for '{name}'")


def _validate(tool: dict, args: dict) -> None:
    schema = tool["inputSchema"]
    props = schema["properties"]
    unknown = sorted(k for k in args if k not in props)
    if unknown:
        raise ArgError(f"unknown argument(s): {', '.join(unknown)}")
    for req in schema.get("required", []):
        if req not in args:
            raise ArgError(f"missing required argument '{req}'")
    for key, value in args.items():
        _check_value(key, value, props[key])


def _positional(name: str, value: str) -> str:
    """Reject values that argparse could read as a flag."""
    if value.startswith("-"):
        raise ArgError(f"'{name}' must not start with '-'")
    return value


def _opt(out: list, a: dict, key: str, flag: str) -> None:
    # Always the --flag=value form so the value can never be read as a flag.
    if key in a:
        out.append(f"{flag}={a[key]}")


def _argv_status(a: dict) -> list[str]:
    return ["status"]


def _argv_brief(a: dict) -> list[str]:
    return ["brief", str(a["target_id"])]


def _argv_next(a: dict) -> list[str]:
    out = ["next"]
    _opt(out, a, "target", "--target")
    return out


def _argv_target_list(a: dict) -> list[str]:
    return ["target", "list"]


def _argv_lead_list(a: dict) -> list[str]:
    return ["lead", "list", f"--target={a['target']}"]


def _argv_verify_report(a: dict) -> list[str]:
    return ["verify-report", _positional("file", a["file"])]


def _argv_target_add(a: dict) -> list[str]:
    out = [
        "target", "add",
        _positional("name", a["name"]),
        _positional("url", a["url"]),
    ]
    _opt(out, a, "chain", "--chain")
    _opt(out, a, "age_days", "--age-days")
    _opt(out, a, "tvl", "--tvl")
    _opt(out, a, "notes", "--notes")
    return out


def _argv_finding_add(a: dict) -> list[str]:
    out = [
        "finding", "add",
        str(a["target_id"]),
        _positional("title", a["title"]),
        _positional("klass", a["klass"]),
    ]
    _opt(out, a, "severity", "--severity")
    _opt(out, a, "falsifier", "--falsifier")
    _opt(out, a, "action", "--action")
    _opt(out, a, "surface", "--surface")
    _opt(out, a, "notes", "--notes")
    return out


def _argv_lead_add(a: dict) -> list[str]:
    out = ["lead", "add", f"--target={a['target']}", f"--title={a['title']}"]
    _opt(out, a, "payload", "--payload")
    for pre in a.get("precondition", []) or []:
        out.append(f"--precondition={pre}")
    _opt(out, a, "surface", "--surface")
    return out


def _argv_report(a: dict) -> list[str]:
    out = ["report", str(a["target_id"])]
    if a.get("out"):
        out.append(f"--out={a['out']}")
    return out


# Schema helpers
def _s(desc: str, **kw) -> dict:
    d = {"type": "string", "description": desc, "maxLength": MAX_STR}
    d.update(kw)
    return d


def _i(desc: str, **kw) -> dict:
    d = {"type": "integer", "description": desc, "minimum": 1}
    d.update(kw)
    return d


def _obj(props: dict, required: list) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


_READ = {"readOnlyHint": True, "destructiveHint": False}
_WRITE = {"readOnlyHint": False, "destructiveHint": False}

_SEVERITY = ["critical", "high", "medium", "low", "info"]
_ACTION = ["recon", "read", "auth-test", "mutate"]

TOOLS: dict[str, dict] = {
    # --- read tools ---
    "hunt_status": {
        "description": "Show HunterOS status for the current ledger (HUNT_DB).",
        "annotations": _READ,
        "inputSchema": _obj({}, []),
        "argv": _argv_status,
    },
    "hunt_brief": {
        "description": "Show the brief for one target.",
        "annotations": _READ,
        "inputSchema": _obj({"target_id": _i("Target id.")}, ["target_id"]),
        "argv": _argv_brief,
    },
    "hunt_next": {
        "description": (
            "Recommend the next action for a target. Omit target when the "
            "ledger has exactly one non-archived target."
        ),
        "annotations": _READ,
        "inputSchema": _obj({"target": _i("Target id (optional).")}, []),
        "argv": _argv_next,
    },
    "hunt_target_list": {
        "description": "List targets in the ledger.",
        "annotations": _READ,
        "inputSchema": _obj({}, []),
        "argv": _argv_target_list,
    },
    "hunt_lead_list": {
        "description": "List leads for a target.",
        "annotations": _READ,
        "inputSchema": _obj({"target": _i("Target id.")}, ["target"]),
        "argv": _argv_lead_list,
    },
    "hunt_verify_report": {
        "description": (
            "Verify a report file against its sha256 footer. Fails with exit "
            "code 2 on tampering."
        ),
        "annotations": _READ,
        "inputSchema": _obj(
            {"file": _s("Path to the report file.", minLength=1)}, ["file"]
        ),
        "argv": _argv_verify_report,
    },
    # --- write tools ---
    "hunt_target_add": {
        "description": "Add a target (name and url) to the ledger.",
        "annotations": _WRITE,
        "inputSchema": _obj(
            {
                "name": _s("Target name.", minLength=1),
                "url": _s("Target URL.", minLength=1),
                "chain": _s("Chain name (optional)."),
                "age_days": {"type": "integer", "minimum": 0,
                             "description": "Contract age in days (optional)."},
                "tvl": {"type": "number", "description": "TVL (optional)."},
                "notes": _s("Free-text notes (optional)."),
            },
            ["name", "url"],
        ),
        "argv": _argv_target_add,
    },
    "hunt_finding_add": {
        "description": (
            "Record a finding on a target. klass must be a known class; the "
            "CLI refuses unknown classes."
        ),
        "annotations": _WRITE,
        "inputSchema": _obj(
            {
                "target_id": _i("Target id."),
                "title": _s("Finding title.", minLength=1),
                "klass": _s("Vulnerability class.", minLength=1),
                "severity": _s("Severity.", enum=_SEVERITY),
                "falsifier": _s("Observation that would prove this finding wrong."),
                "action": _s("Rules-of-engagement action scale.", enum=_ACTION),
                "surface": _i("Attack-surface row id (optional)."),
                "notes": _s("Free-text notes (optional)."),
            },
            ["target_id", "title", "klass"],
        ),
        "argv": _argv_finding_add,
    },
    "hunt_lead_add": {
        "description": "Record a lead on a target.",
        "annotations": _WRITE,
        "inputSchema": _obj(
            {
                "target": _i("Target id."),
                "title": _s("Lead title.", minLength=1),
                "payload": _s("Payload description (optional)."),
                "precondition": {
                    "type": "array",
                    "description": "Preconditions, each 'variable|value|description'.",
                    "items": _s("Precondition string."),
                },
                "surface": _i("Attack-surface row id (optional)."),
            },
            ["target", "title"],
        ),
        "argv": _argv_lead_add,
    },
    "hunt_report": {
        "description": (
            "Generate a target's disclosure report (markdown). If out is given, "
            "the report is also written to that file."
        ),
        "annotations": _WRITE,
        "inputSchema": _obj(
            {
                "target_id": _i("Target id."),
                "out": _s("Output file path (optional)."),
            },
            ["target_id"],
        ),
        "argv": _argv_report,
    },
}


def build_argv(tool_name: str, args: dict) -> list[str]:
    """Validate arguments and return the CLI argv *after* the command prefix.

    Example: build_argv("hunt_status", {}) -> ["--json", "status"].
    Raises ArgError for unknown tools or invalid arguments.
    """
    tool = TOOLS.get(tool_name)
    if tool is None:
        raise ArgError(f"unknown tool: {tool_name}")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ArgError("arguments must be an object")
    _validate(tool, args)
    # --json is a global flag and must precede the verb. It makes refusals
    # arrive as a JSON envelope on stdout; success output is unchanged.
    return ["--json"] + tool["argv"](args)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _tool_result(text: str, is_error: bool) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def parse_refusal(stdout: str) -> dict | None:
    """Return the refusal envelope {"ok": false, ...} if stdout carries one."""
    text = (stdout or "").strip()
    if not text:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    candidates = [text] + ([lines[-1]] if lines else [])
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("ok") is False and "error" in obj:
            return obj
    return None


def format_result(rc: int, stdout: str, stderr: str) -> dict:
    """Map a finished CLI run to an MCP tool result. Exit code is the truth."""
    if rc == 0:
        text = (stdout or "").replace("\r\n", "\n").rstrip() or "(no output)"
        if (stderr or "").strip():
            text += "\n\nstderr:\n" + stderr.strip()
        return _tool_result(text, False)

    env = parse_refusal(stdout)
    lines = [f"hunt exited with code {rc}"]
    if env is not None:
        lines.append(f"error: {env.get('error')}")
        if env.get("next"):
            lines.append(f"next: {env.get('next')}")
    if (stderr or "").strip():
        lines.append("stderr:\n" + stderr.strip())
    if env is None and (stdout or "").strip():
        lines.append("stdout:\n" + stdout.strip())
    return _tool_result("\n".join(lines), True)


def _timeout_seconds(environ) -> float:
    raw = environ.get("HUNT_MCP_TIMEOUT")
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        _log(f"invalid HUNT_MCP_TIMEOUT={raw!r}; using {DEFAULT_TIMEOUT}s")
        return DEFAULT_TIMEOUT
    if not math.isfinite(value) or value <= 0:
        _log(f"invalid HUNT_MCP_TIMEOUT={raw!r}; using {DEFAULT_TIMEOUT}s")
        return DEFAULT_TIMEOUT
    return value


def execute(sub_argv: list[str], environ=None) -> dict:
    """Run the CLI with sub_argv (from build_argv) and return a tool result."""
    env_src = os.environ if environ is None else environ
    try:
        prefix, extra = resolve_cli(env_src)
    except ValueError as exc:
        return _tool_result(f"invalid HUNT_CLI value: {exc}", True)
    if not prefix:
        return _tool_result("HUNT_CLI is set but contains no command", True)

    argv = prefix + sub_argv
    env = dict(env_src)
    env.update(extra)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    timeout = _timeout_seconds(env_src)

    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            shell=False,
        )
    except FileNotFoundError:
        return _tool_result(
            f"HunterOS CLI not found: {argv[0]!r}. Set HUNT_CLI to a working "
            "command prefix, or install the 'hunt' console script.",
            True,
        )
    except OSError as exc:
        return _tool_result(f"could not start HunterOS CLI {argv[0]!r}: {exc}", True)

    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass
        return _tool_result(
            f"timeout: hunt did not exit within {timeout:g}s and was killed "
            f"(set HUNT_MCP_TIMEOUT to change the limit)",
            True,
        )

    return format_result(
        proc.returncode,
        out.decode("utf-8", errors="replace"),
        err.decode("utf-8", errors="replace"),
    )


# ---------------------------------------------------------------------------
# JSON-RPC / MCP protocol
# ---------------------------------------------------------------------------

class _RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _error_response(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message}}


def _valid_id(value) -> bool:
    if value is None or isinstance(value, str):
        return True
    return isinstance(value, int) and not isinstance(value, bool)


def _public_tools() -> list[dict]:
    out = []
    for name, tool in TOOLS.items():
        out.append({
            "name": name,
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
            "annotations": tool["annotations"],
        })
    return out


def _tools_call(params: dict) -> dict:
    name = params.get("name")
    if not isinstance(name, str) or not name:
        raise _RpcError(-32602, "tools/call requires a string 'name'")
    args = params.get("arguments", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise _RpcError(-32602, "'arguments' must be an object")
    if name not in TOOLS:
        raise _RpcError(-32602, f"unknown tool: {name}")
    try:
        argv = build_argv(name, args)
    except ArgError as exc:
        raise _RpcError(-32602, str(exc))
    return execute(argv)


def _dispatch(method: str, params: dict):
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "hunter-os", "version": _server_version()},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": _public_tools()}
    if method == "tools/call":
        return _tools_call(params)
    if method.startswith("notifications/"):
        return None
    raise _RpcError(-32601, f"method not found: {method}")


def handle(message) -> dict | None:
    """Handle one parsed JSON-RPC message. Returns the response or None."""
    if not isinstance(message, dict):
        return _error_response(None, -32600, "invalid request: expected an object")

    has_id = "id" in message
    req_id = message.get("id")
    if has_id and not _valid_id(req_id):
        return _error_response(None, -32600,
                               "invalid request: id must be a string, number or null")

    def reply_error(code: int, msg: str):
        return _error_response(req_id, code, msg) if has_id else None

    if message.get("jsonrpc") != "2.0":
        return reply_error(-32600, "invalid request: jsonrpc must be '2.0'")

    method = message.get("method")
    if not isinstance(method, str):
        return reply_error(-32600, "invalid request: missing method")

    params = message.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return reply_error(-32602, "params must be an object")

    try:
        result = _dispatch(method, params)
    except _RpcError as exc:
        return reply_error(exc.code, exc.message)
    except Exception:
        _log("internal error:\n" + traceback.format_exc())
        return reply_error(-32603, "internal error")

    if not has_id:
        return None
    return {"jsonrpc": "2.0", "id": req_id,
            "result": {} if result is None else result}


def _write(stdout, payload, framed: bool) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if framed:
        stdout.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
    else:
        stdout.write(data + b"\n")
    stdout.flush()


def serve(stdin, stdout) -> None:
    """Serve JSON-RPC over binary streams until EOF.

    Accepts newline-delimited JSON (CRLF or LF) and LSP-style Content-Length
    framing. Replies use the framing the request arrived in.
    """
    while True:
        first = stdin.readline()
        if not first:
            break
        stripped = first.strip()
        if not stripped:
            continue

        framed = stripped.lower().startswith(b"content-length:")
        if framed:
            header_lines = [stripped]
            while True:
                line = stdin.readline()
                if not line:
                    return  # EOF inside headers
                if not line.strip():
                    break
                header_lines.append(line.strip())
            length = None
            for h in header_lines:
                name, _, val = h.partition(b":")
                if name.strip().lower() == b"content-length":
                    try:
                        length = int(val.strip())
                    except ValueError:
                        length = None
            if length is None or length < 0:
                _write(stdout, _error_response(None, -32700,
                                               "parse error: invalid Content-Length"),
                       True)
                continue
            body = stdin.read(length)
            if len(body) < length:
                return  # EOF inside body
            raw = body
        else:
            raw = stripped

        try:
            msg = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            _write(stdout, _error_response(None, -32700, "parse error"), framed)
            continue

        try:
            if isinstance(msg, list):
                if not msg:
                    _write(stdout, _error_response(None, -32600,
                                                   "invalid request: empty batch"),
                           framed)
                    continue
                replies = [r for r in (handle(m) for m in msg) if r is not None]
                if replies:
                    _write(stdout, replies, framed)
            else:
                reply = handle(msg)
                if reply is not None:
                    _write(stdout, reply, framed)
        except BrokenPipeError:
            return


def main() -> None:
    try:
        serve(sys.stdin.buffer, sys.stdout.buffer)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
