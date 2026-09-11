# Agent Silence Diagnostic (2026-07-29)

Quick triage for user complaints: "kenapa ilag?", "stream mati di tengah", "kok ga streaming?"

## One-Liner Diagnostics

```bash
echo "=== RESTART ===" && grep -i 'Gateway running' ~/.hermes/logs/gateway.log | tail -2 && echo "=== EXIT DIAG ===" && ls -lt ~/.hermes/logs/gateway-exit-diag.log 2>/dev/null | head -2 && echo "=== ERRORS ===" && tail -2 ~/.hermes/logs/errors.log 2>/dev/null && echo "=== DISK ===" && df -h / | tail -1 && echo "=== RAM ===" && free -h | grep Mem
```

## Interpretation Table

| Finding | Meaning | Action |
|---------|---------|--------|
| `gateway-exit-diag.log` written recently | Gateway crashed/restarted | Check errors.log for OOM/panic; gateway auto-restarts in ~15s |
| `Connected to Telegram (polling mode)` fresh in gateway.log | Gateway restarted, connection restored | Tell user to re-send pending |
| `inbound message:` for user's msg | Message reached gateway | Connection alive — latency is compression |
| `/` usage ≥85% | Disk full risk | Cleanup; disk-monitor cron should have alerted |
| RAM < 500MB free | OOM risk | Close heavyweight subagents or switch model |

## Understanding Compression Stalls (❌ silent mid-task)

When the stream goes silent for minutes during heavy work:
- Check gateway.log for `compression` entries around the gap
- Context can bloat to 374K+ tokens, triggering compression that freezes output
- Fix: set `session_reset.mode: auto` with `threshold_tokens: 200000` in config.yaml
- Prevent: use checkpoint-style streaming instead of one giant message at the end

## Model Switch = Turn Reset (2026-07-29)

When the user or automation switches models mid-turn (e.g., from DeepSeek-V4-Pro to moonshotai/Kimi-K3), the gateway discards the in-flight turn and re-routes to the new model session. This kills streaming instantly. If the user runs batch audit or multi-agent research, remind them: "Jangan switch model dulu — biarin stream finish wave ini 😌". The agent must NEVER voluntarily switch models as a "fix" during a task — pin the model for the session duration.

## The Long-Task Streaming Contract

This user REQUIRES continuous visible streaming — no silent gaps:
- Emit frequent small progress updates instead of one giant final message
- For silent phases, start `stream_heartbeat.sh` in background
- Wrap long commands in `hermes_stream_safe.sh` for live output + disk checkpoint