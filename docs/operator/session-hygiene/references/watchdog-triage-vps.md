# VPS Watchdog Triage Reference

**Verified**: 2026-07-29

## Watchdog Singleton Guard Behavior

The `/root/.hermes/scripts/watchdog.py` script has a **singleton lock** — when invoked with `--triage-only`, it checks for an existing running instance and refuses to spawn a duplicate:

```bash
$ python3 /root/.hermes/scripts/watchdog.py --triage-only 2>&1 | head -20
⚠️  Watchdog already running (PID 3374354)
```

**Exit code is still 0** — the guard outputs the warning but does not fail. This is intentional: the script is designed to be cron-safe, preventing duplicate watchdog processes that would compete for the same PID file and heartbeat.

## What This Means for Cron Jobs

When the V7 watchdog cron job runs:

1. **Heartbeat is always touched** (`touch /tmp/hermes_heartbeat`) — this succeeds regardless
2. **Triage-only may be skipped** if watchdog is already active — this is correct behavior
3. **No action needed** when you see "already running" — the existing watchdog is handling monitoring

## Health Verification Checklist

If you need to verify watchdog health beyond the triage script:

```bash
# Check if PID is alive (substitute PID from triage output)
ps -p 3374354 -o pid,etime,cmd

# Check heartbeat freshness
stat --format='%y' /tmp/hermes_heartbeat
# Or as age in seconds:
python3 -c "import os,time; print(f'{(time.time()-os.path.getmtime(\"/tmp/hermes_heartbeat\")):.0f}s ago')"

# Check watchdog process
pgrep -af watchdog.py

# Check hermes/gateway processes
pgrep -af hermes
```

## Related Files

| File | Purpose |
|------|---------|
| `/tmp/hermes_heartbeat` | Touch target for "still alive" signal |
| Watchdog PID (from triage output) | Long-running monitoring process |
| `/root/.hermes/scripts/watchdog.py` | Main watchdog script |

## When to Actually Worry

The "already running" message is routine. Investigate only if:
- Heartbeat is stale (>5 minutes old while watchdog claims to be alive)
- PID printed by triage is dead (`ps -p <pid>` returns nothing → stale lock)
- No heartbeat file exists at all
</parameter>
