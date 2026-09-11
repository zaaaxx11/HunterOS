#!/bin/bash
# Stream heartbeat for long-running Hermes tasks
# Emits a "still processing" line to stderr every 60s of idle time
# so Telegram users never see a silent stream.
#
# Protocol: touch /tmp/hermes_heartbeat after every real output line
# (the wrapper hermes_stream_safe.sh does this automatically).
#
# Usage: ./stream_heartbeat.sh &   # run in background alongside a task

HEARTBEAT_FILE="/tmp/hermes_heartbeat"
PID_FILE="/tmp/hermes_heartbeat.pid"

cleanup() {
    [ -f "$PID_FILE" ] && kill $(cat "$PID_FILE") 2>/dev/null
    rm -f "$HEARTBEAT_FILE" "$PID_FILE"
    exit 0
}

trap cleanup EXIT INT TERM

echo $$ > "$PID_FILE"
touch "$HEARTBEAT_FILE"

while true; do
    sleep 60
    if [ -f "$HEARTBEAT_FILE" ]; then
        LAST_MOD=$(stat -c %Y "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
        NOW=$(date +%s)
        IDLE=$(( (NOW - LAST_MOD) / 60 ))

        # Only emit when file hasn't been touched in >=1 minute
        if [ $IDLE -ge 1 ]; then
            echo "⏳ [$(date '+%H:%M:%S')] agent still processing... (${IDLE}m idle)" >&2
            touch "$HEARTBEAT_FILE"
        fi
    fi
done
