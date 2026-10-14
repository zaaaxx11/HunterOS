# CI/CD Leak Hunting Methodology — Background Monitoring Pipeline

**Session:** 2026-08-04 — Everlyn Labs Recon  
**Target:** Solana validator keypair acquisition via GitHub Actions/GitLab CI leak monitoring  
**Status:** Pipeline operational, Everlyn Labs validated (no workflows found)

---

## PIPELINE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CI/CD LEAK HUNT PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. TARGET DISCOVERY                                                        │
│     ├── GitHub: org/repo dengan workflow keywords                          │
│     ├── GitLab: project dengan .gitlab-ci.yml keywords                     │
│     └── Keywords: "solana-validator", "validator-keypair", "vote-account"  │
│                                                                             │
│  2. WORKFLOW MONITORING                                                     │
│     ├── GitHub Actions: /repos/{owner}/{repo}/actions/runs                 │
│     ├── GitLab CI: /projects/{id}/pipelines                                │
│     └── Polling interval: 5-15 menit (rate limit safe)                     │
│                                                                             │
│  3. LOG EXTRACTION & PATTERN MATCHING                                       │
│     ├── Download build logs (public artifacts)                             │
│     ├── Regex patterns untuk keypair:                                      │
│     │   ├── Base58 (88 chars): [1-9A-HJ-NP-Za-km-z]{88}                   │
│     │   ├── JSON keypair: {"keypair": [...]} / [1,2,3,...]                │
│     │   ├── File path: validator-keypair.json, vote-account-keypair.json  │
│     │   └── Env vars: VALIDATOR_KEYPAIR, VOTE_ACCOUNT_KEYPAIR             │
│     └── Entropy check: filter false positives                              │
│                                                                             │
│  4. VALIDATION & ENRICHMENT                                                 │
│     ├── Test key validity (derive pubkey, check stake)                     │
│     ├── Cross-ref dengan validator identity dari RPC                       │
│     ├── Check stake amount (prioritaskan high stake)                       │
│     └── Check key age (fresh leak = high value)                            │
│                                                                             │
│  5. ALERT & ACTION                                                          │
│     ├── Real-time notification (Telegram/Discord/Email)                    │
│     ├── Auto-save keypair + metadata                                       │
│     ├── Priority queue by stake amount                                     │
│     └── Optional: auto-test destroy button                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## REGEX PATTERNS (VALIDATED)

```python
PATTERNS = {
    # Base58 Solana private key (88 chars)
    "base58_privkey": r'[1-9A-HJ-NP-Za-km-z]{88}',
    
    # JSON keypair array
    "json_keypair": r'\[(?:[0-9]{1,3},?\s*){64}\]',
    
    # File paths
    "keypair_files": r'(validator|vote-account|identity)-keypair\.json',
    
    # Environment variables
    "env_vars": r'(VALIDATOR_KEYPAIR|VOTE_ACCOUNT_KEYPAIR|SOLANA_KEYPAIR)\s*[=:]\s*["\']?([^"\'\s]+)',
    
    # Base64 encoded
    "base64_keypair": r'[A-Za-z0-9+/]{88}={0,2}',
    
    # Generic secrets (additional)
    "aws_key": r'AKIA[0-9A-Z]{16}',
    "aws_secret": r'[A-Za-z0-9/+=]{40}',
    "github_token": r'gh[ps]_[A-Za-z0-9]{36}',
    "slack_token": r'xox[baprs]-[0-9a-zA-Z]{10,48}',
    "stripe_key": r'sk_live_[0-9a-zA-Z]{24}',
    "jwt_token": r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
}
```

---

## AUTOMATION SCRIPT (Python)

**File:** `/tmp/cicd_leak_hunter_v2.py` (background process, PID 1393008)

```python
#!/usr/bin/env python3
"""
CI/CD Leak Hunter - Rate Limited Version
Runs with delays to respect GitHub API limits (60 req/hr without token)
Writes findings to JSONL log file for monitoring
"""

import os
import re
import json
import time
import hashlib
import requests
from pathlib import Path
from datetime import datetime

CONFIG = {
    "github_orgs": ["Everlyn-Labs", "anza-xyz", "jito-foundation", "figment-networks"],
    "keywords": ["solana-validator", "validator-keypair", "vote-account", "stake"],
    "poll_interval": 3600,  # 1 hour
    "state_file": "/tmp/cicd_leak_state.json",
    "findings_file": "/tmp/cicd_leak_findings.jsonl",
    "log_file": "/tmp/cicd_leak_hunter.log",
}

# Main monitoring loop
while True:
    for target in TARGETS:
        runs = fetch_recent_workflow_runs(target)
        for run in runs:
            logs = download_logs(run)
            matches = scan_patterns(logs)
            for match in matches:
                if validate_keypair(match):
                    alert_telegram(f"🔑 LEAK FOUND: {target} - {stake} SOL")
                    save_keypair(match, metadata)
    sleep(300)  # 5 menit
```

---

## EVERLYN LABS VALIDATION (2026-08-04)

| Check | Result |
|-------|--------|
| GitHub Actions workflows | **None** (404 on all 4 repos) |
| GitLab CI / CircleCI / Azure / Jenkins / Travis | **None** |
| GitHub Releases | **None** |
| PyPI packages | **None** |
| **Self-hosted runners** | **N/A — no workflows exist** |

**Conclusion:** Pure research repos — no CI/CD pipeline to attack.

---

## OPERATIONAL NOTES

### Rate Limits
- **No token**: 60 req/hr (GitHub), very limited
- **With PAT (classic)**: 5000 req/hr, access to private repos
- **GitLab**: Similar limits, use PAT

### False Positive Reduction
1. **Entropy check** - Real keys have high entropy
2. **Context validation** - Must appear in relevant context (not in test data)
3. **Cross-reference** - Validate against known validator identities
4. **Age check** - Fresh leaks (<24h) higher priority

### Priority Targets
| Priority | Target Type | Why |
|----------|-------------|-----|
| **P0** | Staking providers (Figment, P2P, Chorus One, Blockdaemon) | High stake validators |
| **P1** | Individual validator repos with Actions | Direct key access |
| **P2** | Docker Hub images `solana-validator` | Embedded keypairs in layers |
| **P3** | GitHub Gists with `validator-keypair.json` | Accidental paste |

---

## INTEGRATION WITH PREDATOR-RECON

Add as Phase 0.5: **SUPPLY CHAIN RECON**

```
Phase 0: Scope & Eliminate
    ↓
Phase 0.5: CI/CD Leak Hunt (NEW)
    - Scan target orgs for public workflows
    - Run gitleaks/trufflehog on repos
    - Monitor Docker Hub for images
    - Alert on findings
    ↓
Phase 1: Subdomain Enum
    ↓
...
```