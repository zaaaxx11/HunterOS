# SPEC — Universal Target Hunt + Static Four-Lane CLI

Status: LOCKED for builder handoff (2026-09-09)

## 0. Product sentence

HUNT-OS accepts an authorized URL, public GitHub repository, or local folder,
records it through the same ledger door, prepares a bounded target capsule, and
runs four serial lane attempts through either the deterministic mock or a
versioned external `HUNT-ADAPTER/1` executable. The terminal renders a static,
bounded four-lane control-room page. Mock output is always labelled
`SIMULATED — no external agents invoked`.

“Any harness” means any harness can use the skill-only CLI layer, and any
harness that implements and passes `HUNT-ADAPTER/1` can use managed mode. It
does not mean every installed harness is automatically controllable.

## 1. Laws

1. The hunt CLI remains the only write door. Wizards assemble argv and re-enter
   `huntos.cli.main.main`; they never write SQLite directly.
2. Every refusal is fail-closed: `BLOCKED:` and exit 2.
3. Runtime remains Python stdlib-only.
4. Infrastructure failure, mock prose, and assistant logs are never research
   evidence.
5. Four lanes are `architect`, `red_teamer`, `fuzz_engineer`, `chainer`; this
   release dispatches them serially and must never claim parallel execution.
6. Raw chain-of-thought is not persisted. Operational excerpts are redacted,
   capped, typed, and attempt-attributed.
7. URL input is not automatically crawled. GitHub preparation is a shallow,
   isolated public clone. Local folders are referenced without modification.
8. ANSI color is decoration only. `NO_COLOR`, non-TTY, `TERM=dumb`, or failed
   Windows VT support yields the same plain-text semantics.
9. Installation is additive. Managed mode requires an explicit conforming
   adapter executable; no adapter is loaded from an untrusted target tree.
10. `conductor.md` and `plans.md` are local scratch and stay untracked.

## 2. Locked target-source API

`huntos.core.target_source.TargetSource` has fields:

```text
kind: url|github|folder
canonical: str
display: str
workspace: str
revision: str
```

Public functions:

```python
classify_target_source(raw: str, *, cwd: Path | None = None) -> TargetSource
prepare_github_source(source: TargetSource, workspace_root: Path,
                      *, runner=subprocess.run, timeout=120) -> TargetSource
default_target_name(source: TargetSource) -> str
```

Local existing directories are classified before URL parsing. Supported GitHub
forms are HTTPS, `git@github.com:owner/repo.git`, `github.com/owner/repo`, and
`github:owner/repo`. Credentials, controls/NUL, unsupported schemes, invalid
ports, and GitHub query/fragment/extra path components are blocked.

DB owns `target_source` and public APIs:

```python
prepare_target(conn, name, source, chain, hosts, actions,
               authorization_note) -> int
get_target_source(conn, target_id) -> row | None
```

Target + source + RoE are one transaction. `authorization_note` is required.
Existing `target add` and `target roe` behavior stays compatible.

CLI:

```text
hunt target prepare SOURCE [--name NAME] [--chain NAME]
  [--hosts CSV] [--actions CSV] --authorization-note TEXT
  [--workspace-root PATH]
```

## 3. Locked capsule and event APIs

`huntos.conductor.capsule.build_lane_capsule(conn, session_id, attempt_id,
lane, round_no, model_profile, roles_root) -> tuple[dict, str]` returns canonical
JSON-compatible data plus SHA-256. It includes source, workspace, RoE, role text,
bounded brief, tool/output contract, model profile, and identifiers.

`conductor_event` rows have a per-attempt monotonic sequence and fields:
`session_id`, `attempt_id`, `lane`, `sequence`, `event_type`, `detail`,
`operation_id`, `created_at`. Closed event types:

```text
lane_start tool_request tool_result assistant_output usage
claim_gate completion error
```

Public DB APIs:

```python
record_conductor_event(conn, session_id, attempt_id, event_type, detail,
                       operation_id=None) -> row
list_conductor_events(conn, session_id, attempt_id=None, limit=100) -> list
```

`detail` is redacted and capped at 2000 characters. Assistant deltas and raw
reasoning are never recorded.

## 4. Locked `HUNT-ADAPTER/1` contract

`HuntAdapter` gains:

```python
submit_tool_result(attempt_id: str, result: ToolResult) -> None
```

The conductor must submit the actual mediated result immediately after every
`ToolRequest`. `MockAdapter` records submitted results.

An external adapter is a long-lived executable. UTF-8 stdout is protocol-only,
stderr is bounded diagnostics. Each JSON line is a closed object containing:

```text
protocol: HUNT-ADAPTER/1
request_id: unique string
type: request|response|event
method: doctor|start_session|run_turn|tool_result|cancel_turn|
        get_attempt_status|stop_session
payload: object
```

Requests and responses correlate by `request_id`; turn events carry the
request ID until a terminal event. Limits: 1 MiB per line, explicit timeouts,
no `shell=True`, strict event parsing, process cleanup, attempt/session identity
checks, and fail-closed malformed/duplicate/unknown responses.

Registry file defaults to `~/.huntos/adapters.json`, written atomically with
0600 best effort. It stores adapter name and executable argv only—no environment
or credential data. CLI:

```text
hunt adapter add NAME --exec ABSOLUTE_PATH [--arg ARG ...]
hunt adapter list
hunt adapter doctor NAME
hunt adapter remove NAME
```

Built-in `mock` is not stored. Registered adapter names resolve to
`JsonlAdapter`; session retry/resume reconstructs the session's recorded
adapter rather than silently falling back to mock.

A deterministic example executable may prove the protocol but must identify
itself as a reference adapter, not an LLM or external subagent.

## 5. Locked shell and page behavior

Bare `hunt` starts the guided target flow only when stdin and stdout are TTY.
Non-TTY bare invocation prints help and returns 2 without prompting.

Inside `hunt shell`:
- bare `hunt` starts the wizard;
- `hunt <args>` strips the redundant prefix and dispatches normally;
- script mode never prompts.

Wizard asks source, actions, authorization note, adapter, and confirmation. It
runs exact `target prepare` then `run start --rounds 1 --page` commands. Mock is
allowed only after printing the SIMULATED warning.

CLI additions:

```text
hunt shell --guided
hunt run start ... --page [--no-color]
hunt run status ... --page [--no-color]
```

`control_room_summary()` remains backward compatible.
`control_room_page(conn, session_id, *, color=None, width=None) -> str` renders:
header, target/source, mode label, exactly four lane panels, bounded operational
lines, and NEXT. Missing lanes render `READY / no attempt yet`. Width clamps to
60..120 and uses ASCII borders.

`huntos.cli.terminal` owns TTY/NO_COLOR/Windows-VT policy, ANSI bright green,
ANSI stripping, visible-width truncate/pad, and terminal width. Stored content
and `HuntShell.last_output` remain ANSI-free.

## 6. Installation contract

Recommended installation remains from a checkout:

```text
python -m pip install --editable ./app --no-deps
```

The checkout remains required for skill/role/bridge resources; this release
must not claim a self-contained wheel or PyPI install.

Skill-only installation remains:

```text
hunt install --adapter claude-code|zcode
hunt install --adapter generic --dir PATH
```

Managed mode additionally requires `hunt adapter add` with a conforming
executable.

The hook pack adds manifest-tracked `claim_gate_wrapper.py`, with the same
`HUNT_DB`, `HUNT_PROJECT_DIR`, stdin, and exit-code contract as the POSIX shell
wrapper. Router description derives the landed skill count rather than using a
stale hardcoded number.

Version becomes 0.2.0 in package metadata and `huntos.__version__`; runtime
dependencies stay empty.

## 7. Acceptance

1. URL/GitHub/folder classification, refusal, and transactional persistence are
   tested without public network calls.
2. Four lanes receive distinct role-bearing capsule hashes.
3. Operational logs are ordered, capped, redacted, and reproduce the page after
   process exit; raw deltas/CoT are absent.
4. A fake JSONL adapter proves duplex tool request -> real CLI result -> next
   event; malformed, oversized, timeout, crash, and identity failures close.
5. Mock page always contains the SIMULATED sentence. External pages name the
   exact adapter/version and serial mode.
6. ANSI tests cover TTY, `NO_COLOR`, non-TTY, `TERM=dumb`, and Windows fallback;
   plain output has identical words.
7. Wizard cancellation writes nothing; non-TTY/script paths never prompt.
8. POSIX and PowerShell editable-install commands are documented and an
   installed `hunt` runs from a fresh cwd.
9. Python wrapper installs, checks, executes, and uninstalls on both OSes.
10. Every tracked Python file compiles; product imports are stdlib/local only;
    full existing suite stays green.
