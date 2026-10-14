---
name: disk-space-session-safety
description: "disk-space and session safety for long runs"
category: security
tags:
  - session-safety
  - disk-space
  - multi-agent
  - poc-reverification
  - workflow
---

# Disk & Session Safety — Long-Running Multi-Agent Audits

## Trigger

Use before ANY long-running audit/delegation burst (multi-agent waves >1h, heavy PoC artifacts, cached sessions), especially when the operator says:

- "stream terus jangan berhenti"
- "kenapa kepotong potong"
- agent runtime session errors (see docs/operator/session-hygiene)
- Old `*-poc/` directories with scripts that print "PoC COMPLETE"

## Rule

> Before spawning agents, verify disk space + kill stale background processes + plan to stream progress. A crashed session loses more context than an unstarted wave.

## Workflow

```text
1. PRE-FLIGHT CHECK
   df -h /                        # abort/clean if >85% or < ~500MB free
   du -sh <agent-runtime-session-dir>  # bloated session dir → accelerate no-space crash

2. CLEAN STALE PROCESSES
   process list                   # kill leftover proc_* running old PoC scripts
                                  # they can revive stale "COMPLETE" banners

3. WATCHDOG (operator VPS)
   Cron job: vps-disk-watchdog
   script: disk_monitor.sh (check df ≥85% → send Telegram alert)
   schedule: every 5 minutes
   no_agent: true (no LLM/token cost)

4. STREAM MENTALITY
   Narrate each major step (clone → recon → agent wave → result)
   Never disappear into a tool call for a long audit.
```

## Why

From ops (Everlyn/Colibri swap 2026-07-29):

1. **Session store corruption**: the session store hit 100% → agent runtime session errors (see docs/operator/session-hygiene) during continued conversation → context compaction swallowed parts of the timeline → operator had to re-explain.
2. **Stale positive**: an old PoC script kept printing "PoC COMPLETE" as a background process, leading the agent to believe the vector was still open before the live test showed the main chain had been patched.
3. **Silent failures**: long audit bursts with tool-call gaps made the operator think the agent had abandoned the task. Frequent streaming updates prevent this.

## Local-First Disk Budget
On small hosts, check free space and budget BEFORE spinning a local harness: prefer the
smallest proof artifact that settles the claim (single-crate POC <200M over full node
harness 3-4G+); present the cheap-vs-full choice to the operator instead of auto-spawning.
(target-specific session notes preserved at examples/hunts/web2/disk-space-session-safety/)
## Notes

- Don't clean `venv/` inside Hermes runtime paths; that breaks the agent. Only clean tmp/log/pyc and stale PoC transcripts.
- If disk is tight, prefer smaller proof artifacts: truncate stdout snippets, limit `du -h` scans, or rotate old delegation live transcripts under `~/.hermes/cache/delegation/live/`.

## Related skills

- `bug-bounty-agent` — overall methodology and phase gates
- `poc-reverification` — re-verify against the live target before quoting stale scripts
