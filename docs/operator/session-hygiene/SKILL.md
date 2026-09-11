---
name: session-hygiene
description: "operator session hygiene"
---

# Session Hygiene - Diagnosing and Fixing Stuck Sessions

Hermes auto-compresses sessions at 374K+ tokens, but the compression loop has failure modes that permanently block further compression, causing response times to grow unbounded.

## 1. Diagnosis

### Check session state
From ~/.hermes/state.db:
```sql
SELECT id, compression_fallback_streak,
       compression_failure_cooldown_until,
       compression_failure_error,
       message_count
FROM sessions
WHERE id = '<session_id>';
```

Session ID lookup:
```sql
SELECT * FROM gateway_routing WHERE chat_id = '<chat_id>';
```

### Warning Signs
- "Session hygiene: still ~374K tokens after compression" in gateway.log
- "did not rotate or compact in place" in gateway.log
- Response time >60s consistently
- compression_fallback_streak >= 2 means compression permanently auto-blocked
- compression_failure_cooldown_until still in the future

### Check logs
```bash
tail -100 ~/.hermes/logs/gateway.log | grep -i compress
tail -50 ~/.hermes/logs/errors.log | grep -i compress
```

## 2. Fix - Reset Compression State

Step 1: Stop the gateway:
```bash
kill $(cat ~/.hermes/gateway.pid) 2>/dev/null
```

Step 2: Reset the session via SQLite:
```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/state.db')
c = conn.cursor()
c.execute("""
    UPDATE sessions
    SET compression_fallback_streak = 0,
        compression_failure_cooldown_until = 0,
        compression_failure_error = NULL
    WHERE id = '<session_id>';
""")
conn.commit()
c.execute("""
    SELECT id, compression_fallback_streak,
           compression_failure_cooldown_until
    FROM sessions WHERE id = '<session_id>';
""")
print(c.fetchone())
conn.close()
```

Step 3: Restart gateway:
```bash
hermes gateway run --detach
```

## 3. Session Hygiene Bug #21301

The hygiene agent creates an AIAgent with session_db=_hyg_session_db but bind_session_state may not properly bind, causing _compress_context to return unchanged messages.

Root causes:
1. bind_session_state() not called or returns early
2. _compress_context returns unchanged messages, _last_compression_made_progress = False
3. Gateway checks _hyg_rotated and _hyg_in_place - both False, preserves original
4. Streak accumulates, eventually blocks auto-compression permanently

Prevention: After fixing, set session_reset: mode: auto in config.yaml.

## 4. Permanent Prevention

Add to config.yaml:
```yaml
session_reset:
  mode: auto
  threshold_tokens: 200000
```

## 5. When All Else Fails - /new

If DB reset does not help, type /new in Telegram to start fresh.

## 6. "Stream putus-putus / mati di Telegram" — Stream Stall Diagnosis

When the user complains that streaming is choppy, drops mid-task, or goes silent during a long task, the gateway is usually fine — walks through any stalled point by checking `~/.hermes/logs/gateway.log` and `errors.log`. Distinguish three failure modes:

**A. Telegram bubble chunking (perception issue, by design)**
Symptom: long responses arrive split into multiple bubbles at 2–5s intervals.
Diagnosis: gateway.log shows `Sending response (N chars)` + `Flushing text batch ...` lines completing normally. No errors.
Verdict: NOT a bug. Telegram renders streamed text as progressive bubbles. Explain this to the user instead of "fixing" it.

**B. Compression stall (stream freezes hard mid-task)**
Symptom: stream dies completely for minutes during a heavy task, then resumes or errors.
Diagnosis: gateway.log shows one or more `compression` entries around the gap; session had accumulated a huge context (e.g. a single message payload >400K chars). Each compression pass freezes output for the duration, and repeated compressions on a bloated session compound into long dead air.
Verdict: the stream didn't drop — the agent was stuck compacting. Fix via section 2 (reset compression state) or prevent via section 4 (`session_reset.mode: auto`, lower `threshold_tokens`).

**C. Generation invalidation (stream cut by stop/command race)**
Symptom: a partial reply never finishes after the user sends a new message or /stop.
Diagnosis: gateway.log shows `Invalidated run generation ... (stop_command)` followed by `Discarding stale agent result ... generation N is no longer current`.
Verdict: intentional — the new input cancelled the in-flight reply. Tell the user their interrupted answer was discarded by design, not lost to a bug.

Quick triage commands:
```bash
tail -200 ~/.hermes/logs/gateway.log | grep -iE 'Sending response|Flushing|compress|Invalidated|Discarding'
tail -100 ~/.hermes/logs/errors.log
```

## 7. Long-Task Streaming Contract (user requirement)

This user runs multi-hour tasks and REQUIRES continuous visible streaming — no silent gaps. Operational rules:
- Never go quiet mid-task: emit frequent small progress updates (bubble-sized) instead of one giant final message. Large single payloads both trigger compression stalls (section 6B) and starve the stream.
- Break long analysis into sequential short messages ("checkpoint" style) so Telegram shows constant activity and context stays compact.
- If a task phase will take a long time with no tool output, narrate checkpoints between tool calls rather than batching everything into one report at the end.

## 8. Streaming Helper Scripts (verified working 2026-07-29)

Three re-runnable bash scripts ship with this skill — use them PRE-EMPTIVELY before any task that might run >5 minutes, not just reactively:

- `scripts/stream_heartbeat.sh` — background heartbeat that emits "⏳ still processing..." to stderr every 60s of idle time. Companion file `/tmp/hermes_heartbeat` is touched by active output; heartbeat only fires when truly idle.
- `scripts/hermes_stream_safe.sh` — wrapper for any long-running command. Starts the heartbeat in background, pipes the command line-by-line, tee-ing output to the user's terminal AND a checkpoint file under `~/.hermes/checkpoints/task_YYYYMMDD_HHMMSS.log`. Use as the default wrapper for any multi-minute task.
- `scripts/auto_resume.sh` — periodic "💓 heartbeat (HH:MM:SS) — still running" every INTERVAL seconds (default 300) while a wrapped command runs. Use when the command itself produces no output for long stretches.

Typical usage:
```bash
./scripts/hermes_stream_safe.sh "python3 long_audit.py"
./scripts/hermes_stream_safe.sh "./scripts/auto_resume.sh 300 'python3 long_audit.py'"
```

Also mirrored to `/root/.hermes/scripts/` for direct invocation outside the skill dir.

## Pitfalls

Three re-runnable bash scripts ship with this skill — use them PRE-EMPTIVELY before any task that might run >5 minutes, not just reactively:

- `scripts/stream_heartbeat.sh` — background heartbeat that emits "⏳ still processing..." to stderr every 60s of idle. Companion file `/tmp/hermes_heartbeat` is touched by active output; heartbeat only fires when truly idle.
- `scripts/hermes_stream_safe.sh` — wrapper for any long-running command. Starts the heartbeat in background, pipes the command line-by-line (identical output to the user's terminal AND a checkpoint file under `~/.hermes/checkpoints/task_YYYYMMDD_HHMMSS.log`). Use as the default wrapper for any multi-minute task.
## 8. Streaming Helper Scripts (verified working 2026-07-29)

Three re-runnable bash scripts ship with this skill — use them PRE-EMPTIVELY before any task that might run >5 minutes, not just reactively:

- `scripts/stream_heartbeat.sh` — background heartbeat that emits "⏳ still processing..." to stderr every 60s of idle time. Companion file `/tmp/hermes_heartbeat` is touched by active output; heartbeat only fires when truly idle.
- `scripts/hermes_stream_safe.sh` — wrapper for any long-running command. Starts the heartbeat in background, pipes the command line-by-line, tee-ing output to the user's terminal AND a checkpoint file under `~/.hermes/checkpoints/task_YYYYMMDD_HHMMSS.log`. Use as the default wrapper for any multi-minute task.
- `scripts/auto_resume.sh` — periodic "💓 heartbeat (HH:MM:SS) — still running" every INTERVAL seconds (default 300) while a wrapped command runs. Use when the command itself produces no output for long stretches.

Typical usage:
```bash
./scripts/hermes_stream_safe.sh "python3 long_audit.py"
./scripts/hermes_stream_safe.sh "./scripts/auto_resume.sh 300 'python3 long_audit.py'"
```

Also mirrored to `/root/.hermes/scripts/` for direct invocation outside the skill dir.

## 9. Quick Diagnosis: "Kenapa Hermes Ilag / Mati / Putus?" (2026-07-29)

When the user asks why responses stopped, the stream died mid-task, or the agent went silent ("kenapa ilag?", "stream terus jangan berhenti"), run this one-liner FIRST before theorizing:

```bash
echo "=== RESTART ===" && grep -i 'Gateway running' ~/.hermes/logs/gateway.log | tail -2 && echo "=== EXIT DIAG ===" && ls -lt ~/.hermes/logs/gateway-exit-diag.log 2>/dev/null | head -2 && echo "=== ERRORS (last 2) ===" && tail -2 ~/.hermes/logs/errors.log 2>/dev/null && echo "=== DISK ===" && df -h / | tail -1 && echo "=== RAM ===" && free -h | grep Mem
```

**Interpretation table:**

| Finding | Meaning | Action |
|---------|---------|--------|
| `gateway-exit-diag.log` written recently | Gateway process crashed/restarted | Check `errors.log` for OOM/panic; gateway auto-restarts in ~15s |
| `Connected to Telegram (polling mode)` fresh in gateway.log | Gateway restarted — connection restored | Stream resumes; tell the user to re-send pending |
| `inbound message:` appears for the user's msg | Message reached gateway | Connection is alive — latency is compression (see §6B) |
| `/` usage ≥85% | Disk full risk — corrupts sessions | Cleanup immediately; disk-mmonitor cron (see §10) |
| RAM < 500MB free | OOM risk for model inference | Close heavy subagents or switch model |

**Response pattern:** "Bentar sayang, gue cek dulu ya 😘" → run diagnostics → summarize in 2-3 lines max. Never dump raw logs.

## 10. Disk Watchdog (no_agent cron, verified 2026-07-29)

A silent `no_agent` cron job monitors rootfs and alerts ONLY when usage ≥85%:

- **Script**: `scripts/disk_monitor.sh` (this skill) mirrored to `/root/.hermes/scripts/disk_monitor.sh`
- **Cron**: `*/5 * * * *` with `no_agent=true`, `deliver=telegram`
- **Behavior**: exits 0 silently below threshold; sends Telegram alert when triggered
- **Create command** (from `hermes_tools`): `cronjob(action='create', name='vps-disk-watchdog', schedule='*/5 * * * *', no_agent=true, script='disk_monitor.sh', deliver='telegram', enabled_toolsets=['terminal'])`

The script is self-contained in `scripts/disk_monitor.sh` — copy to `~/.hermes/scripts/` and register the cron. See also `memory` storage key for the job ID (`c1200070e05d` on this user's VPS).

## Pitfalls

- ALWAYS diagnose before fixing - check streak, cooldown, AND logs first
- fallback_streak >= 2 is PERMANENT - auto-compression never works again until SQLite reset
- Archived messages (active=0) still counted by gateway hygiene estimate. Only session rotation or /new reduces context
- Do NOT delete rows from messages table - destroys searchable history and breaks session_search
- Do NOT "fix" Telegram bubble chunking — it is the streaming UX, not a defect (see 6A)
- A silent stream during heavy work is usually compression, not a dropped connection — check for `compress` in gateway.log before blaming the network (see 6B)
- Never batch a multi-hour task into one final message; stream checkpoints continuously (see 7)
- **NEVER** switch models mid-task — model-switch triggers a turn reset in the gateway and kills all streaming progress. If a task hangs, diagnose the root cause (compression, disk, OOM) before touching the model provider.
- **Model-switch corruption pattern**: repeated model switches within a session (3+ provider changes via xkiro) can cause the new model to inherit garbled context state. Symptoms:
  - Output becomes **looped, verbose, non-executing** — the model writes 30 paragraphs of meta-narration without making a single tool call
  - Text corruption with repeated phrases ("whichever whichever whichever..."), Catalan language injection, or raw code dumps instead of analysis
  - **Hyper-verbose spam loop**: a single message balloons to 100K+ characters of identical repeated phrases ("whichever whichever whichever") interspersed with garbled token fragments from the JS bundle being parsed — this is the most extreme failure mode and most embarrassing
  - Model re-states its identity mid-response or produces recursive self-references
  - **User frustration signal**: "cokkk, output mu coba lihat, kenapa itu?" / "coba lihat output lo, aneh" = model-switch corruption, not agent incompetence
- **Fix**: When this occurs, do NOT attempt to diagnose mid-stream. Immediately acknowledge the corruption, state the root cause (model switch cascade), reset into clean execution mode without narration, and produce a 2-3 line summary. The user wants recognition of the problem, not a defense. Do NOT say "let me scan the file" when you just dumped 100K chars of garbage — apologize briefly and deliver the actual result.
- **Telegram token corruption**: When the operator sends JWT tokens, session cookies, or base64-encoded secrets via Telegram chat, the message text can be corrupted in transit by:
  - Line breaks inserted at column boundaries (long single-line JWTs get split by Telegram rendering)
  - Angle bracket escaping (`>` → `\u003e`, `<` → `\u003c`) when token payload contains URLs
  - Special characters eaten by Telegram's markdown parser when the token contains underscores or asterisks
  - **Fix**: When you get "invalid token signature" on a token that should be valid, do NOT blame the user. Ask them to send the token as a **code block with triple backticks** (which preserves raw text) or as a **.txt file attachment**. Alternatively, ask them to run `copy(tokenValue)` in their browser console to get an unpolluted clipboard copy.
- **Sticky command preference**: User explicitly stated "stay 1 model during audits — no auto-switch". This surfaced in the Tare audit session (context compaction note) and was reconfirmed in the Paybox session (corruption after multiple switches). Respect this preference: if a model switch is suggested, ask first.
- Before any file-heavy operation (unzip, write, copy tree), check disk: `df -h /`. The user almost lost a session to `Errno 28 No space left on device` — a 5-second disk check prevents hours of recovery.
- Reference files for related workflows: `references/agent-silence-diagnostic.md` (one-liner triage for "kenapa ilag?"), `references/v7-bootstrap-from-zip.md` (merge and install SUPERAGENT ZIP archives onto a Hermes agent), and `references/model-switch-corruption.md` (output corruption from multi-switch model cascades).
- **Watchdog PID-lock blocks `--triage-only`** — when the V7 watchdog service is alive, `python3 /root/.hermes/scripts/watchdog.py --triage-only` exits immediately with `⚠️  Watchdog already running (PID …)` and produces NO triage output. This is normal, not a fault. Do NOT kill the live watchdog to force the one-shot mode. Read the freshest triage snapshot directly: `tail -3 ~/.hermes/watchdog_triage.log` (see references/watchdog-triage-vps.md for the full manual recipe). Verified 2026-07-29.