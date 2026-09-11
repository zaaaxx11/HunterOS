# V7 Bootstrap from ZIP Archives (2026-07-29)

Pattern for merging SUPERAGENT release ZIPs onto a running Hermes agent when the user provides them as file attachments.

## ZIP Attachment Extraction

The user provided two ZIPs via Telegram — the gateway saves them to `~/.hermes/cache/documents/`. Binary payloads are NOT auto-extracted; use `unzip` directly.

```bash
mkdir -p /tmp/super7_update && cd /tmp/super7_update
unzip -o /root/.hermes/cache/documents/doc_<hash>_SUPERAGENT7.1.zip
unzip -o /root/.hermes/cache/documents/doc_<hash>_SUPERAGENT-V7.zip
```

## Identifying What's New

Use `execute_code` with filecmp or stat to compare the extracted files against the installed tree:
- Check which files exist in the ZIP but not in `~/.hermes/`
- Check which files differ in size from their `~/.hermes/` counterparts
- Map "FOR BUGS BOUNTY/references/*.md" to existing skill reference directories

## Merge Strategy

1. **Copy references from the skill ZIP** (SUPERAGENT7.1) into the respective skill's `references/` directory — only if the ZIP versions are newer/different
2. **Copy bootstrap files** (AGENTS.md, CHANGELOG.md, INDEX.md, MEMORY.md, TIME.md, SKILLS.lock, pyproject.toml, .env.example, CONTRIBUTORS.md) from SUPERAGENT-V7 to `~/.hermes/`
3. **NEVER overwrite SOUL.md** with ZIP versions — user explicitly skips this file
4. **Check tool scripts** — the ZIP may contain references (like `tools/watchdog.py` → `~/.hermes/scripts/watchdog.py`) but these may already be installed. Verify what's actually missing before copying.

## Post-Install: Cron Jobs for V7 Runtime

After merging files, set up cron jobs for the runtime:

```python
# Watchdog — keep-alive daemon with triage checks
cronjob(action='create', name='super-agent-watchdog', schedule='*/10 * * * *',
        no_agent=True, script='watchdog.py', deliver='local',
        enabled_toolsets=['terminal'])

# Heartbeat orchestrator — 9-step V7 integrity check every 6h
cronjob(action='create', name='v7-heartbeat-orchestrator', schedule='0 */6 * * *',
        no_agent=True, script='heartbeat_v7.sh', deliver='local',
        enabled_toolsets=['terminal'])
```

## Pitfalls

- `@reboot` cron schedule is NOT supported by Hermes — use `*/N * * * *` intervals instead
- Memory tool entries accumulate quickly — consolidate small related entries into one after install
- The `SKILLS.lock` from SUPERAGENT-V7 covers OpenClaw skill paths, not Hermes skill paths — don't blindly adopt it without checking what files actually exist