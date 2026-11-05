---
name: hunter-loop
description: Run the HunterOs daemon-free state-driven loop — continuous hunting with goals and time budget. Use when the operator says "hunt for 6 hours", "loop this target", or "run continuous audit".
allowed-tools: Bash, Read, Grep
---
# HUNTER LOOP — State-driven continuous hunt

## Quick start

```bash
hunter loop <target> --time 6h --goals rce-min:1,exploitable-min:1,findings-min:500 --engine llm --yes
```

## CONCEPTS

**Time > goals** — wall clock ALWAYS wins. If 20,000 seconds expire before every
goal is met, the loop stops with `completion_reason: "time-expired"` and the
operator reads `state.json` to see what was achieved.

**State durability** — every cycle writes to `<state>/hunt_runs/<slug>/state.json`.
A crash, a cron restart, or a manual `hunter loop` re-invocation picks up exactly
where it left off.

**No daemon** — zero background processes. Each hunt cycle runs as a subprocess
worker; the parent waits `idle_seconds` (default 15s), then spawns the next.

## OPTIONS

| Flag | Default | Description |
|------|---------|-------------|
| `--time` | 0 (unlimited) | Wall clock budget `[Nh][Nm][Ns]` |
| `--min-time` | 0 | Minimum floor before early stop |
| `--idle` | 15 | Pause between cycles (seconds) |
| `--goals` | `exploitable-min:1` | Comma-separated goals |
| `--engine` | `llm` | `deterministic` or `llm` |
| `--scope` | — | Scope manifest JSON |
| `--yes` | false | Auto-authorize minimal scope |

## GOALS REFERENCE

| Kind | Matches | Example |
|------|---------|---------|
| `rce-min` | Pure RCE (code-exec, command-injection) | `rce-min:1` |
| `exploitable-min` | RCE + reentrancy + access-control | `exploitable-min:1` |
| `findings-min` | All findings (any severity) | `findings-min:500` |
| `verified-min` | VERIFIED+ findings only | `verified-min:100` |

Multiple goals use AND logic — all must be satisfied before the loop stops.

## STATE FILE FORMAT

```json
{
  "target": "/path/to/repo",
  "target_slug": "path-to-repo",
  "goals": [{"kind": "exploitable-min", "count": 1}],
  "wall_seconds": 21600,
  "run_count": 12,
  "total_findings": 11981,
  "verified_findings": 8090,
  "exploitable": 460,
  "rce": 0,
  "completed": false,
  "completion_reason": ""
}
```

## CRON DEPLOYMENT

```bash
# Run every 15 minutes — idempotent, resumes from state
*/15 * * * * cd /path/to/target && hunter loop . --time 6h --goals rce-min:1 --yes
```

The first invocation creates the mission; subsequent cron ticks reload the
existing state and continue from the last completed cycle.

## EXIT CODES

| Code | Meaning |
|------|---------|
| 0 | Goals met or time expired (normal) |
| 3 | Invalid target / refused scope |
| 8 | Invalid configuration |