#!/bin/sh
# HUNT-OS claim gate wrapper (the installed hook pack).
#
# Pipe the engine's output to this script's stdin. The claim gate COPIED
# BESIDE this wrapper (claim_gate.py in this same directory) vets the text,
# and the gate's exit code is propagated unchanged:
#   0 = pass, 2 = veto (one BLOCKED: line on stderr).
# The gate opens HUNT_DB read-only and never writes. No network.
#
# Environment contract:
#   HUNT_DB            passthrough to the gate (default ~/.huntos/hunt.db)
#   HUNT_PROJECT_DIR   when set, this script cd's there before invoking the
#                      gate, so the gate evaluates the .huntos-project lock in
#                      the operator's project root even when the harness does
#                      not preserve cwd
#   HUNT_PYTHON        python interpreter for the gate (default: python)
#
# The gate is resolved relative to this wrapper's own directory and NEVER
# falls back to a source checkout. A missing gate is a fail-closed veto.

set -u

HOOK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || {
    echo "BLOCKED: claim gate wrapper cannot resolve its own directory" >&2
    exit 2
}
GATE="$HOOK_DIR/claim_gate.py"

if [ ! -f "$GATE" ]; then
    echo "BLOCKED: claim gate missing beside the wrapper ($GATE) - reinstall the hook pack (hunt install)" >&2
    exit 2
fi

if [ -n "${HUNT_PROJECT_DIR:-}" ]; then
    cd -- "$HUNT_PROJECT_DIR" || {
        echo "BLOCKED: HUNT_PROJECT_DIR is not a usable directory: $HUNT_PROJECT_DIR" >&2
        exit 2
    }
fi

exec "${HUNT_PYTHON:-python}" "$GATE"
