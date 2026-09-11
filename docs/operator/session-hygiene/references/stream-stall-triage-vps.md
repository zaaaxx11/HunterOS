# Stream Stall Triage — VPS / Telegram Only (2026-07-29 update)

This reference captures the 2026-07-29 session where the operator reported "putus-putus ketika chat di tele" and "ga stream terus, padahal need 6 hours". Root cause + fixes.

## Root Cause Analysis (from logs)

**The gateway itself was healthy.** All messages were being received and replied to. What looked like dropouts were:

1. **Telegram bubble chunking (by design)** — long streamed responses split into multiple bubbles at 2-5s intervals. NOT a bug. See `Sending response (N chars)` + `Flushing text batch` lines in gateway.log.

2. **Context compression freeze** — the session had accumulated 473K chars ≈ 118K tokens → 8 compressions/events. Each compression pass freezes output completely. Compounded into multi-minute dead air.

3. **Generation invalidation from stop commands** — user pressed /stop or sent a new message mid-stream → `Invalidated run generation ... (stop_command)` followed by `Discarding stale agent result`. Reply was discarded BY DESIGN.

4. **API errors compounding the freeze**:
   - `TimeoutError` on OpenRouter call
   - `429 rate limit` on Google fallback
   - `604s tool execution timeout`
   - 23 fallback events

## Triage Command Pattern

```bash
# Confirm stream actually completed, not dropped:
tail -200 ~/.hermes/logs/gateway.log | grep -iE 'Sending response|Flushing|Invalidated|Discarding'

# Check error log for compression/fallback cascade:
tail -100 ~/.hermes/logs/errors.log | grep -iE 'compression|TimeoutError|429|fallback'

# Verify current session state:
ls -la /root/.hermes/sessions/ | head -20
```

## Prevention — Wrap Any Task >5 Min In Safe Wrapper

```bash
# Simple streaming + checkpointing:
/root/.hermes/scripts/hermes_stream_safe.sh "python3 long_audit.py"

# With auto-resume heartbeat baked in (for totally silent phases):
/root/.hermes/scripts/hermes_stream_safe.sh \
  "/root/.hermes/scripts/auto_resume.sh 300 'python3 long_audit.py'"
```

Wrapper scripts live at:
- `/root/.hermes/scripts/stream_heartbeat.sh` — 60s idle pulse
- `/root/.hermes/scripts/hermes_stream_safe.sh` — line-by-line tee to user + checkpoint file
- `/root/.hermes/scripts/auto_resume.sh` — periodic 💓 ticker even when silent

## V7 Ops Toolkit (deployed 2026-07-29)

All in `/root/.hermes/scripts/`:

| Tool | Purpose |
|------|---------|
| `skill_integrity.py` | SHA256 baseline of all skills, detect tampering |
| `reflection.py` | Daily self-improvement: scan recent memories, auto-execute SAFE_AUTO_ACTIONS |
| `briefing.py` | Daily summary push (once/day guard) |
| `profit_ledger.py` | Session + running P&L tracking (revenue/costs/gas) |
| `watchdog.py` | 10s heartbeat daemon + triage every 2 min |

## Cron Safety (from session history)

Disk-full event on 2026-07-28 corrupted Hermes session DB → memories lost mid-stream. Prevention:
- Cronjob `c1200070e05d` runs `/root/.hermes/scripts/disk_monitor.sh` every 5 min
- Alerts Telegram only when / usage >= 85% (silent otherwise)
- Verified working; do not disable

## Never Do

- Never claim a file was received in Telegram until verified on disk. Attachment markers (`[image attachment]`) in logs ≠ bytes saved. See `telegram-attachments.md` reference.
- Never delete rows from `messages` table to "reduce context" — destroys session_search history.
- Never batch a 6-hour audit into one final report message. Stream checkpoints continuously.
