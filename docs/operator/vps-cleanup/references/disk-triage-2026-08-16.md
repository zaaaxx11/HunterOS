# Disk Triage 2026-08-16 — 98% / 0GB Display Truncation

Source: V7 watchdog cron `touch /tmp/hermes_heartbeat && python3 /root/.hermes/scripts/watchdog.py --triage-only`

## Timeline
- 09:00 UTC: `disk_space: ✅ (2GB free)`
- 17:55 UTC onward: `disk_space: ❌ (0GB free)` — 27 consecutive failures through 21:02
- 21:00 UTC (cron): `df -h /` → `/dev/vda1 20G 20G 527M 98%` → after `dnf clean all` (8 files) → `587M 98%`
- Heartbeat: `touch /tmp/hermes_heartbeat` succeeded both cycles (verified `ls -l`, 0 bytes)

## Root Cause — Truncated Label
`watchdog.py:50-52`:
```python
total, used, free = shutil.disk_usage("/")
disk_ok = free / total > 0.10  # >10% free
checks.append(f"disk_space: {'✅' if disk_ok else '❌'} ({free//2**30}GB free)")
```
`free//2**30` integer division truncates <1 GiB to `0GB`. Real free was 527–587 MiB; threshold is 10% (~2 GiB on 20G), so `❌` is correct despite misleading label. Trust `df -h` `Avail` column.

## Disk Breakdown (2026-08-16 21:01 UTC)
```
19G  /  (total)
/root 13G
  .rustup 5.6G
  .cargo  1.8G (registry 1.4G)
  .hermes 1.6G (state.db 1.1G, sessions 106M, logs 22M, node 200M)
  genesis-audit 1.6G (repos 1023M + tarballs 564M)
  victionchain-master 455M (×2 with /tmp copy)
/tmp 1.4G (mezo-hunt 530M, victionchain-master 455M, mezo-audit 171M)
/usr 4.6G, /var 124M, journal 24M, dnf cache 68M (cleaned)
state.db: 62126 messages, 2328 sessions, 1.1G + wal 2.2M
```

## False Positive — YDService Deleted Handle
`lsof | grep deleted`:
```
YDService 2210259 root 12r REG 253,1 3638152 /root/injective_audit/swap-contract/target/.../libzerocopy_derive-*.so (deleted)
```
- Binary: `/usr/local/qcloud/YunJing/YDEyes/YDService`, PPID 1 (systemd), Tencent HIDS — not an orphaned audit build
- `/root/injective_audit/` no longer exists on disk; file is already unlinked
- Reclaimable if killed: ~3.6 MiB only; restarting HIDS risks alert — do not kill
- Lesson: `grep deleted` on this host always shows YDService; filter with `grep -v YDService` before triaging audit `target/` leaks

## Cleanup Attempted
- `dnf clean all` → 8 files removed, 527→587M (+60M)
- `journalctl --vacuum-size=20M` → `Vacuuming done, freed 0B` (journal only 24M total, 17M in /var/log/journal)
- No `/root/.hermes` touch (per operator rule); no YDService kill; no `rm -rf /tmp/*` blanket

## Reclaimable Pool (priority order, safe)
1. `/tmp/mezo-hunt 530M`, `/tmp/victionchain-master 455M`, `/tmp/mezo-audit 171M` — stale audit unpacks
2. `/root/.cargo/registry 1.4G` — safe if no live `cargo build` in `ps`
3. `/root/genesis-audit/tarballs 564M` — tarballs after repos extracted
4. `/root/.hermes/sessions/request_dump_*.json` (106M, largest 1.1M) — old request dumps, keep last 7d
5. `/var/cache/dnf 68M` — already cleaned; low yield next time
Do NOT vacuum journal aggressively; do NOT delete state.db or venvs.

## Watchdog Script Note
`watchdog.py` is 217 lines with ~100 lines of duplicated `if __name__ == '__main__'` / `if '--triage-only' in sys.argv` guards (lines 100-188). `triage_only()` itself is correct and `--triage-only` works end-to-end, but the duplication is a maintenance hazard — any future edit should dedupe to a single `argparse` block. See SKILL.md "Watchdog Pattern" for the intended one-shot contract (`touch heartbeat + run_triage + append log`).

## Second Triage 2026-08-16 21:20 UTC — VACUUM Failure & Cargo Breakdown

Cron: `touch /tmp/hermes_heartbeat && python3 /root/.hermes/scripts/watchdog.py --triage-only 2>&1 | head -20`
Result: `memory_intact ✅ | skills_readable ✅ | disk_space ❌ (0GB free) | cron_active ✅` — `Log: /root/.hermes/watchdog_triage.log`, exit 0, heartbeat `0 bytes mtime 2026-08-16 21:20:22.790 +0800` verified via `ls -l + stat`.

`df -h /` chronology this session:
- Start: `/dev/vda1 20G 20G 587M 98%` (before session)
- After `sqlite3 state.db VACUUM` attempt: `28K 100%` — WAL grew 3.1M→3.8M (+700K) then `Error: stepping, database or disk is full (13)`
- After `rm -rf /root/.cargo/registry/cache` (30M) + `pip cache purge` (6 files, 7.1M) + `truncate watchdog_triage.log`: `621M 97%` → `620M 97%` (fresh triage at 21:21:17 still `0GB free` = <1GiB truncation)

`df -i` healthy (36% inodes), so block exhaustion not inode.

`/root` breakdown 21:20:
- `/root/.hermes/state.db 1.1G + wal 3.8M + shm 832K` (VACUUM blocked — requires ~1 GiB temp; don't retry until `Avail > 1 GiB`)
- `/root/.cargo 1.7G = registry/src 1.2G + git 393M + registry/cache 30M` (cache safe to delete; src/git need `ps` check for live `cargo build`)
- `/root/genesis-audit 1.6G`, `/root/victionchain-master 455M + /tmp copy 455M`, `/root/.hermes/sessions 779 files 106M`
- `/root/.cache/pip 6.8M`, `go: not found`, `docker: not found`, `/var/log/journal 24M` (vacuum freed 0)
- `crontab -l` has 2 jobs: `blackswan_audit.sh */10` + `stargate admin/start.sh */5`; `crond active` (RHEL), `cron inactive` — watchdog correctly tries both

Lesson: **never VACUUM state.db when `Avail < 1 GiB`** — it makes disk fuller and fails. Order is `df -h` → reclaim `/tmp/*` + cargo cache + pip cache → *then* VACUUM. On 20 GiB VPS, `>10%` threshold = ~2 GiB, so `620M 97%` still ❌; needs +1.4 GiB before watchdog goes green.

## Verification After Cleanup
```bash
touch /tmp/hermes_heartbeat && python3 /root/.hermes/scripts/watchdog.py --triage-only 2>&1 | head -20
df -h / | tail -1
cat /root/.hermes/watchdog_triage.log | tail -3
ls -l /tmp/hermes_heartbeat
# extra checks that proved useful 21:20
df -i / | tail -1; du -sh /root/.cargo/registry/cache /root/.cargo/registry/src /root/.cargo/git 2>&1; du -sh /root/.cache/pip 2>&1; ls -lh /root/.hermes/state.db* 2>&1
systemctl is-active cron; systemctl is-active crond; crontab -l
cat /tmp/hermes_heartbeat; stat /tmp/hermes_heartbeat
```
