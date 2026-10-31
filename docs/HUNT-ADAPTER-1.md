# HUNT-ADAPTER/1

Managed HunterOS adapters are explicit, long-lived executables speaking one UTF-8 JSON object per stdout line. Stdout is protocol-only; bounded human diagnostics belong on stderr. HunterOS starts the configured executable argv directly with `shell=False`.

Every envelope has exactly `protocol`, `request_id`, `type`, `method`, and `payload`. The protocol is `HUNT-ADAPTER/1`; type is `request`, `response`, or `event`; methods are `doctor`, `start_session`, `run_turn`, `tool_result`, `cancel_turn`, `get_attempt_status`, and `stop_session`. Responses correlate to unique request IDs. Events for a turn use its `run_turn` request ID until a terminal event and response.

`run_turn` receives the lane capsule and its SHA-256. A `tool_request` pauses adapter work. HunterOS mediates the command through its CLI and immediately sends a `tool_result` request containing the real `ToolResult`. The adapter acknowledges it, then may emit further turn events. Assistant deltas are never persisted. Operational output is typed, redacted, and bounded.

Protocol lines are limited to 1 MiB. Malformed JSON/UTF-8, unknown fields or methods, duplicate or mismatched IDs, timeout, process death, and unterminated streams fail closed.

The registry is `~/.huntos/adapters.json`. It stores only an adapter name, absolute executable path, and string argv. It never stores environment variables or credentials and never discovers executables in the current directory, target tree, or `PATH`. Provider credentials may be inherited from the operator process environment; they must not be emitted on stdout/stderr or included in protocol payloads.

The deterministic `examples/adapters/reference_jsonl.py` executable demonstrates the duplex contract. It identifies itself as a reference simulator and invokes no LLM or external agent. Register it cross-platform using the absolute Python interpreter as `--exec` and the script's absolute path as an argument.

## Real-harness adapters

Two adapters drive an actual agent CLI in headless mode, so a managed `hunt run` executes a real lane turn on a real model:

- `examples/adapters/hermes_cli.py` — runs `hermes --headless --print <capsule prompt>`.
- `examples/adapters/codex_cli.py` — runs `codex exec <capsule prompt>`.

Both share the same shape: the lane capsule (role doctrine, brief, RoE) becomes the prompt; the model's answer is scanned for a single `TOOL_REQUEST {"command": [...]}` line, and finding one pauses the turn so HunterOS mediates the command through its own CLI and sends the real result back. A turn whose answer carries no request completes as prose and still goes through the claim gate. Anything other than the exact line form is treated as prose, so a model that merely talks about tool requests cannot hijack a turn.

Configuration is by environment variable, never stored in the registry:

| Variable | Applies to | Default |
|---|---|---|
| `HUNT_ADAPTER_HERMES_BIN` | hermes adapter | `hermes` |
| `HUNT_ADAPTER_CODEX_BIN` | codex adapter | `codex` |
| `HUNT_ADAPTER_TIMEOUT` | both | `600` seconds |
| `HUNT_ADAPTER_MODEL` | both | unset (no `--model` passed) |

`doctor` resolves the executable before reporting capabilities, so a missing binary fails the preflight instead of dying on the first turn. A non-zero CLI exit, a timeout, or an unknown method all fail closed with exit 2.

Register with the absolute interpreter as `--exec` and the script as an argument:

```sh
hunt adapter add hermes-cli --exec "$(command -v python3)" \
  --arg /absolute/path/to/examples/adapters/hermes_cli.py
hunt adapter doctor hermes-cli
hunt run start --target 1 --rounds 2 --adapter hermes-cli
```
