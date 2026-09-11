#!/bin/bash
# Auto-resume / periodic nudge wrapper for very long tasks.
# Sends a "💓 heartbeat" line every INTERVAL seconds while CMD runs, so
# any consumer watching stdout sees constant activity even when the
# wrapped command itself is silent for long stretches.
#
# Usage: ./auto_resume.sh [interval_seconds] "command to run"
# Default interval: 300s (5 minutes)

INTERVAL="${1:-300}"
shift
CMD="$@"

if [ -z "$CMD" ]; then
    echo "Usage: $0 [interval_seconds] \"command\"" >&2
    exit 1
fi

# Launch command in background, capture stdout+stderr to a fifo
FIFO=$(mktemp -u)
mkfifo "$FIFO"

eval "$CMD" > "$FIFO" 2>&1 &
CMD_PID=$!

cleanup() {
    kill $CMD_PID 2>/dev/null
    rm -f "$FIFO"
}
trap cleanup EXIT INT TERM

# Reader: forward lines as they arrive
(
    while IFS= read -r line < "$FIFO"; do
        echo "$line"
    done
) &
READER_PID=$!

# Heartbeat ticker
while kill -0 $CMD_PID 2>/dev/null; do
    sleep "$INTERVAL"
    if kill -0 $CMD_PID 2>/dev/null; then
        echo "💓 heartbeat ($(date '+%H:%M:%S')) — still running"
    fi
done

wait $CMD_PID
EXIT_CODE=$?
kill $READER_PID 2>/dev/null
exit $EXIT_CODE
