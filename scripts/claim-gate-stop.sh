#!/bin/sh
# hunt-os Stop-hook adaptor: Stop JSON (stdin) -> claim_gate.py -> exit code.
#
# FAKTA SPEK (hooks-doc.md): Stop hooks receive JSON on stdin with
# `last_assistant_message` + `transcript_path`. The transcript file may lag
# the in-memory conversation, so hooks MUST use `last_assistant_message`.
# Exit 2 on Stop = "prevents Claude from stopping, continues the conversation".
# There is NO JSON decision:block for Stop (that belongs to PreToolUse-style
# events); the block signal is the exit code, stderr carries the reason.
#
# Behavior:
#   0 = pass (claim gate found no unbacked claims, or gate intentionally
#       downgraded — see below)
#   2 = veto (BLOCKED: reason on stderr, Claude continues the turn)
#
# Fail-closed cases (-> exit 2): gate file missing, stdin not JSON.
# Documented downgrade (-> exit 0 + warning on stderr): no hunt.db resolvable
# (HUNT_DB unset AND default ~/.huntos/hunt.db absent) — the gate would veto
# every turn on machines without a ledger, so we pass with a warning instead.
# stop_hook_active=true -> exit 0 (avoid the 8-continuation-cap infinite loop).
#
# Env: HUNT_DB (passthrough), HUNT_PYTHON (default python3),
#      HUNT_PROJECT_DIR (cd there first, passthrough to gate wrapper logic).

set -u

HOOK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || {
    echo "BLOCKED: claim-gate-stop cannot resolve its own directory" >&2
    exit 2
}
GATE="$HOOK_DIR/claim_gate.py"
PY="${HUNT_PYTHON:-python3}"

if [ ! -f "$GATE" ]; then
    echo "BLOCKED: claim gate missing beside the adaptor ($GATE)" >&2
    exit 2
fi

if [ -n "${HUNT_PROJECT_DIR:-}" ]; then
    cd -- "$HUNT_PROJECT_DIR" || {
        echo "BLOCKED: HUNT_PROJECT_DIR is not a usable directory: $HUNT_PROJECT_DIR" >&2
        exit 2
    }
fi

# (Default-db handling happens AFTER parsing + marker scan, below.)

# Read stdin JSON, extract last_assistant_message (+ stop_hook_active), write
# the message text to a temp file for the gate. python3 stdlib only.
# ORDER MATTERS: parse FIRST (fail-closed on malformed input), downgrade-check
# the db SECOND. A previous version downgraded before parsing, so malformed
# stdin silently passed — fixed (adversarial test TEST2).
MSG_FILE=$(mktemp) || {
    echo "BLOCKED: claim-gate-stop cannot create temp file" >&2
    exit 2
}
trap 'rm -f "$MSG_FILE"' EXIT INT TERM

"$PY" -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f"BLOCKED: claim-gate-stop: stdin is not valid Stop-hook JSON: {e}", file=sys.stderr)
    sys.exit(3)
if not isinstance(data, dict):
    print("BLOCKED: claim-gate-stop: Stop-hook JSON is not an object", file=sys.stderr)
    sys.exit(3)
if data.get("stop_hook_active") is True:
    sys.exit(7)  # already continuing because of a stop hook -> pass
msg = data.get("last_assistant_message", "")
if not isinstance(msg, str):
    msg = str(msg)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(msg)
' "$MSG_FILE"
py_rc=$?
if [ "$py_rc" -eq 7 ]; then
    exit 0  # stop_hook_active: already continuing because of a stop hook
fi
if [ "$py_rc" -ne 0 ]; then
    exit 2  # malformed stdin JSON (message already on stderr) — fail-closed
fi

# Empty message (e.g. brand-new session, tool-only turn) -> nothing to vet.
if [ ! -s "$MSG_FILE" ]; then
    exit 0
fi

# No-marker fast path: text without PROVEN/EXPLOITABLE/"admin takeover" can
# never trip the gate, so pass without requiring a ledger db. (The gate
# itself would also pass, but it opens the db first — without a db it would
# fail-closed veto a claim-free turn. Check markers first via grep.)
if ! grep -q -E '\bPROVEN\b|\bEXPLOITABLE\b|admin takeover' "$MSG_FILE"; then
    exit 0
fi

# Text carries a strong claim but no ledger db is resolvable -> documented
# downgrade: pass with a warning (a hard veto on every Stop would make the
# plugin unusable on machines without `hunt init`). Operator signal, not proof.
if [ -z "${HUNT_DB:-}" ] && [ ! -f "$HOME/.huntos/hunt.db" ]; then
    echo "hunt-os claim gate: strong claim markers present but no ledger db found (set HUNT_DB or run hunt init) - gate check SKIPPED, claims unverified" >&2
    exit 0
fi

exec "$PY" "$GATE" "$MSG_FILE"
