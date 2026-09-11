---
name: vps-audit
description: "VPS security audit"
version: "0.2.0"
source: "https://github.com/nuver-labs/vps-audit"
---

# VPS Audit

## When to Use

- User asks to audit a VPS/server security posture or health
- Quickly assess SSH hardening, firewall, fail2ban, open ports, SUID risk, resources
- Need a quick baseline report before/after changes

Script bundled in `scripts/vps-audit.sh` (no network download needed if present).

Security + performance audit for Linux VPS using [nuver-labs/vps-audit](https://github.com/nuver-labs/vps-audit).

## Quick Start

```bash
# Download (skip if already present)
wget -q https://raw.githubusercontent.com/nuver-labs/vps-audit/main/vps-audit.sh -O /tmp/vps-audit.sh
chmod +x /tmp/vps-audit.sh

# Run
sudo /tmp/vps-audit.sh
```

## What It Checks

### Security
- SSH config (root login, password auth, port)
- Firewall (UFW/firewalld/iptables/nftables)
- Fail2ban/CrowdSec jail config
- Failed login attempts
- System updates status
- Sudo logging
- Password policy (pwquality.conf)
- SUID files detection

### Performance
- Disk usage
- Memory usage
- CPU usage
- Running services count
- Open ports count
- Active connections

## Output

- Console: color-coded 🟢PASS / 🟡WARN / 🔴FAIL
- Report file: `vps-audit-report-YYYYMMDD_HHMMSS.txt`

## Thresholds (configurable in script)

| Check | WARN | FAIL |
|-------|------|------|
| Disk/Memory/CPU | ≥50% | ≥80% |
| Running services | ≥20 | ≥40 |
| Failed logins | ≥10 | ≥50 |
| Open ports | ≥10 | ≥20 |
| Password minlen | <12 | — |

## Remote Execution (SSH)

For remote VPS, pipe the script via SSH:

```bash
ssh -i key.pem user@host 'wget -q https://raw.githubusercontent.com/nuver-labs/vps-audit/main/vps-audit.sh -O /tmp/vps-audit.sh && chmod +x /tmp/vps-audit.sh && sudo /tmp/vps-audit.sh'
```

## Pitfalls

- Requires root/sudo access
- On minimal systems, may need `ufw` installed for firewall checks
- Report file created in CWD — use `/tmp/` for remote runs
- Script is ~600 lines, runs in ~5-10 seconds
- `auth.log` check may fail on systemd-based distros using journald (not a blocker)
- Script calls `curl https://api.ipify.org` to fetch the public IP — needs outbound internet; Public IP field will be empty without it
- `find /` SUID scan can be slow on large filesystems; excludes standard paths and known SUID bins
