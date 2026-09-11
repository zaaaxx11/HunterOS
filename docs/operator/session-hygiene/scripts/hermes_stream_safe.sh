#!/bin/bash
# Wrapper for long Hermes tasks with auto-checkpointing
# Keeps the Telegram stream alive and records a checkpoint log.
#
# Usage:
#   ./hermes_stream_safe.sh "python3 long_audit.py"
#   ./hermes_stream_safe.sh "./auto_resume.sh 300 'python3 long_audit.py'"
#
# Behavior:
#   - Starts stream_heartbeat.sh in background (emits every 60s of idle)
#   - Pipes the wrapped command through a loop that:
#       * forwards every line to the user's terminal (real stream)
#       * appends every line to a checkpoint file under ~/.hermes/checkpoints/
#       * touches /tmp/hermes_heartbeat so the heartbeat stays quiet on active output
#   - Reports duration + checkpoint path at the end; preserves exit code.

CHECKPOINT_DIR="/root/.hermes/checkpoints"
mkdir -p "$CHECKPOINT_DIR"

TASK_START=$(date +%s)
TASK_NAME="task_$(date +%Y%m%d_%H%M%S)"
CHECKPOINT_FILE="$CHECKPOINT_DIR/${TASK_NAME}.log"

echo "🚀 Task started: $TASK_NAME" | tee -a "$CHECKPOINT_FILE"
echo "⏱️ Start time: $(date)" | tee -a "$CHECKPOINT_FILE"
echo "---" | tee -a "$CHECKPOINT_FILE"

# Start heartbeat in background
/root/.hermes/scripts/stream_heartbeat.sh &
HEARTBEAT_PID=$!

# Run command with tee to capture output line-by-line
eval "$@" 2>&1 | while IFS= read -r line; do
    echo "$line"
    echo "[$(date '+%H:%M:%S')] $line" >> "$CHECKPOINT_FILE"
    touch /tmp/hermes_heartbeat 2>/dev/null || true
done

EXIT_CODE=${PIPESTATUS[0]}
TASK_END=$(date +%s)
DURATION=$(( (TASK_END - TASK_START) / 60 ))

kill $HEARTBEAT_PID 2>/dev/null || true

echo "---" | tee -a "$CHECKPOINT_FILE"
echo "✅ Task finished: $TASK_NAME" | tee -a "$CHECKPOINT_FILE"
echo "⏱️ Duration: ${DURATION}m" | tee -a "$CHECKPOINT_FILE"
echo "📁 Checkpoint: $CHECKPOINT_FILE" | tee -a "$CHECKPOINT_FILE"
echo "Exit code: $EXIT_CODE" | tee -a "$CHECKPOINT_FILE"

exit $EXIT_CODE
