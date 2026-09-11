# HUNT-ADAPTER/1

Managed HunterOS adapters are explicit, long-lived executables speaking one UTF-8 JSON object per stdout line. Stdout is protocol-only; bounded human diagnostics belong on stderr. HunterOS starts the configured executable argv directly with `shell=False`.

Every envelope has exactly `protocol`, `request_id`, `type`, `method`, and `payload`. The protocol is `HUNT-ADAPTER/1`; type is `request`, `response`, or `event`; methods are `doctor`, `start_session`, `run_turn`, `tool_result`, `cancel_turn`, `get_attempt_status`, and `stop_session`. Responses correlate to unique request IDs. Events for a turn use its `run_turn` request ID until a terminal event and response.

`run_turn` receives the lane capsule and its SHA-256. A `tool_request` pauses adapter work. HunterOS mediates the command through its CLI and immediately sends a `tool_result` request containing the real `ToolResult`. The adapter acknowledges it, then may emit further turn events. Assistant deltas are never persisted. Operational output is typed, redacted, and bounded.

Protocol lines are limited to 1 MiB. Malformed JSON/UTF-8, unknown fields or methods, duplicate or mismatched IDs, timeout, process death, and unterminated streams fail closed.

The registry is `~/.huntos/adapters.json`. It stores only an adapter name, absolute executable path, and string argv. It never stores environment variables or credentials and never discovers executables in the current directory, target tree, or `PATH`. Provider credentials may be inherited from the operator process environment; they must not be emitted on stdout/stderr or included in protocol payloads.

The deterministic `examples/adapters/reference_jsonl.py` executable demonstrates the duplex contract. It identifies itself as a reference simulator and invokes no LLM or external agent. Register it cross-platform using the absolute Python interpreter as `--exec` and the script's absolute path as an argument.
