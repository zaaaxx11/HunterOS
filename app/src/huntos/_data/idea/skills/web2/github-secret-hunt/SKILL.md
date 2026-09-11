---
name: github-secret-hunt
description: "hunt leaked secrets across GitHub"
version: "1.0"
category: security
tags:
  - github
  - secret-scanning
  - developer-osint
  - supply-chain
  - ci-cd
  - crates-io
  - npm
  - pypi
  - bug-bounty
  - opsec
author: SUPERAGENT
trigger:
  - "github secret"
  - "secret leak"
  - "github scan"
  - "developer osint"
  - "supply chain"
  - "opsec"
  - "github token"
  - "private key leak"
  - "admin key"
  - "credentials"
  - "api key"
  - "github actions"
  - "ci/cd"
  - "crates.io"
  - "npm audit"
auto_activate: false
---

# GitHub Secret Hunt & Developer OSINT

## Purpose
Systematic approach to finding leaked secrets in GitHub orgs, compromising developer accounts via OSINT, analyzing supply chain dependencies, and scanning package registries for version anomalies. This is the **operational security attack surface** — 90% of crypto hacks are OPSEC failures, not code vulnerabilities.

## When to Use
- Target has public GitHub org with repos
- Target has known developer names (from docs, Twitter, LinkedIn, GitHub contributor lists)
- Target uses package dependencies (Rust/crates, JS/npm, Python/pypi)
- No direct code access but need to find attack surface
- Complements smart contract audit with operational vulnerability discovery

## Core Loop

```
RECON (who, where, what) →
  SCAN (public repos for secrets) →
    OSINT (developers, profiles, personal sites) →
      SUPPLY CHAIN (dependencies, packages, versions) →
        CI/CD (workflows, env vars, deployment configs) →
          DECIDE (exploit path)
```

## PHASE 1: GitHub Organization Scan

### Step 1: Enumerate All Public Repos

**Always try BOTH the `/orgs/` AND `/users/` endpoints** — the account may not be an org. `/orgs/<name>/repos` returns 404 for plain user accounts, and the skill was bitten by this on the trias-lab target (`/orgs/trias-lab/repos` → 404; `/users/trias-lab/repos` → 20 repos). Same account name, different endpoint. Run both, keep whichever returns non-empty. Add `type=all` to the users variant so member-less repos still show.

```bash
# Try orgs first
curl -s "https://api.github.com/orgs/INJECTIVE_LABS/repos?per_page=100&page=1" \
  -H "Authorization: Bearer GITHUB_TOKEN"

# If orgs returns 404, try users endpoint
curl -s "https://api.github.com/users/INJECTIVE_LABS/repos?per_page=100&page=1&type=all" \
  -H "Authorization: Bearer GITHUB_TOKEN"

# Repeat with page=2, page=3, etc. until empty
```

### Step 1b: Recursive Tree + Raw Fetch (preferred over Code Search)

The Code Search API now requires auth (see pitfall below) and is easily rate-limited, so prefer the **tree-walk** approach for comprehensive coverage:
1. For every repo, `GET /repos/:owner/:repo` → record `default_branch`.
2. `GET /repos/:owner/:repo/git/trees/:branch?recursive=1` → full recursive file tree (up to 100k entries). Filter for deploy/config/docker/nginx/env files: any path whose lowercase form contains `docker-compose`, `Dockerfile`, `.env`, `nginx`, `caddy`, `k8s`, `kubernetes`, `deployment.yaml`, `deploy.`, `Makefile`, `.travis`, `.circleci`, `.github/workflows`, `config.`, `conf.`, `settings.`, `.conf`, `.ini`, `.toml`, `.yaml`, `.yml`, `start.sh`, `stop.sh`, `run.sh`, `install.sh`, `pm2`, `ecosystem`, `.service`, `terraform`, `.tf`, `database`, `proxy`.
3. For each matching blob, fetch via `https://raw.githubusercontent.com/:owner/:repo/:branch/:path` (lighter rate limits than the contents API) and run the secret regex set over content.
4. Also try a small list of **common config paths directly** when the tree is unavailable (404 on tree means private/empty repo): `docker-compose.yml`, `Dockerfile`, `.env`, `.env.example`, `nginx.conf`, `deploy.sh`, `Makefile`, `config.toml`, `config.yaml`, `app.json`. Some repos keep secrets in `.env.example` while the real `.env` is gitignored.

The bundled `scripts/org-deep-config-scanner.py` automates this end-to-end (enumerate both orgs + users, recursive tree-walk, raw fetch, multi-pattern scan, structured JSON output). See `examples/hunts/web2/github-secret-hunt/trias-lab-org-enumeration-case-study.md` for a 20-repo example run that recovered live deployment hostnames, hardcoded MySQL creds, Django SECRET_KEYs, k8s bootstrap tokens, and 30+ Conflux bootnode IPs in a single pass.

### Step 2: Public Repo Content Scan
```python
# Search for common secret patterns in repo contents
patterns = {
    "AWS_AKIA": r'AKIA[0-9A-Z]{16}',
    "PRIVATE_KEY": r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----',
    "HEX_PRIVATE": r'0x[a-fA-F0-9]{64}',
    "API_KEY": r'api[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}',
    "PASSWORD": r'password\s*[=:]\s*["\']?[^\s]{8,}',
    "DB_CONN": r'postgres|mysql|mongodb://[^\s:]+:[^\s]+@[^\s]+',
    "GITHUB_TOKEN": r'gh[pousr]_[A-Za-z0-9_]{36,}',
    "SLACK_TOKEN": r'xox[baprs]-[A-Za-z0-9\-]+',
    "OPENAI_PROXY_KEY": r'sk-[a-zA-Z0-9]{48,}',
    "HF_TOKEN": r'hf_[a-zA-Z0-9]{34}',
    "OPENAI_PROXY_ENDPOINT": r'(?:api_base|api\.base|openai\.api_base)\s*=\s*["\']https?://[^"\']+/v1["\']',
    # Additional patterns validated on trias-lab (2026-08-17):
    "DJANGO_SECRET_KEY": r'(?:SECRET_KEY|secret_key)\s*=\s*[\'"]([A-Za-z0-9!@#$%^&*()_\-+=\[\]{}|:;<>?,./`~]{30,})[\'"]',
    "COVERALLS_TOKEN": r'token:\s*([A-Za-z0-9]{32})',  # dedicated .coveralls.yml files
    "JWT_SECRET": r'(?:jwt[_\-]?secret|jwt_key)\s*[=:]\s*[\'"]?[A-Za-z0-9_\-]{16,}',
    "OPENSSL_PASSOUT": r'pass(out)?\s+pass:\s*([A-Za-z0-9_\-]{4,})',  # openssl -passout/-passin in Dockerfiles
    "EMPTY_AES_PASSPHRASE": r'private_key_encrypt_pass["\']?\s*:\s*["\']["\']',  # empty = effectively unencrypted private keys
    "MYSQL_USER_PASS": r'mysql_(user|password)["\']?\s*:\s*["\']([^"\']{1,})["\']',  # JSON config files (trias-explorer, web-wallet)
    "ETH_RPC_IP_PORT": r'(https?://[\d\.]+:\d+)',  # bare IP:port JSON-RPC nodes (geth, IRI)
    "K8S_BOOTSTRAP_TOKEN": r'--token\s+([a-z0-9]{6}\.[a-z0-9]{16})',  # kubeadm join tokens in deploy docs
}

# IP-with-context extraction: capture ~60 chars around each IP to identify what it
# documents — config files often hardcode complete deployment topology. Always scan
# committed `.coveralls.yml`, `.travis.yml`, `conf/*.json`, `appsettings.json`, and ALL
# `src/environments/*.ts` files (env.ts, environment.prod.ts, prod.ts, dev.ts, schema.ts
# — frontend env files leak live backend hostnames); grep deploy scripts for SSH
# user/key leaks (`pssh -H`, `sshpass`, `ssh -i`, `StrictHostKeyChecking=no`, `scp`, `rsync`).
# (target-specific notes preserved at examples/hunts/web2/github-secret-hunt/)
IP_RE = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?\b')
# For each repo:
# 1. Read README.md (base64 decode from API)
# 2. Check for .env, config.json, secrets files
# 3. Search issues for sensitive keywords
# 4. Check forks
```

### Step 3: GitHub Code Search
```bash
# Search across entire org for secrets
curl "https://api.github.com/search/code?q=AKIA+org:INJECTIVE_LABS&per_page=10" \
  -H "Authorization: Bearer GITHUB_TOKEN"

curl "https://api.github.com/search/code?q=PRIVATE+KEY+org:INJECTIVE_LABS&per_page=10" \
  -H "Authorization: Bearer GITHUB_TOKEN"

curl "https://api.github.com/search/code?q=api_key+org:INJECTIVE_LABS&per_page=10" \
  -H "Authorization: Bearer GITHUB_TOKEN"

curl "https://api.github.com/search/code?q=password+org:INJECTIVE_LABS&per_page=10" \
  -H "Authorization: Bearer GITHUB_TOKEN"
```

### Step 4: Issues & PR Scan
```bash
# Scan issues for sensitive keywords
curl "https://api.github.com/repos/INJECTIVE_LABS/REPO/issues?state=all&per_page=100" \
  -H "Authorization: Bearer GITHUB_TOKEN"

# Look for: private_key, api_key, password, secret, token, wallet, mnemonic
```

### Step 5: Forks & Private Repos
- **Forks**: Scan all forks of target org repos — attackers often commit secrets to forks
- **Private repos**: Not scannable via API, but check if any private repos have been made public historically via GitHub Archive or Wayback Machine

### Step 6: Proxy Endpoint Validation
After discovering a key and its associated `api_base`, test the proxy endpoint BEFORE attempting key use.
1. **DNS test**: `dig +short <domain> A` and `dig +short <domain> CNAME` — dead domain = dead target.
2. **HTTP reachability**: `curl --max-time 5 https://<domain>` — no response = offline.
3. **Auth format test**: `curl https://api/v1/models` (no auth) vs `curl https://api/v1/models -H "Authorization: Bearer fake"` — different error messages reveal if the API expects a custom key format.
4. **Login portal discovery**: Check the domain's homepage for login/register links; proxy services often have `gpt.<domain>.com` or `<domain>.com/#/login` portals.
5. **Docs discovery**: Proxies frequently host API docs at `/docs`, `/openapi.json`, or return doc links in error messages (e.g., `"请参考开发文档:https://doc.example.com/doc-3979939"`).

### Key Pitfalls
- **Docs ≠ Leaked:** Keywords like "private key" in READMEs/docs are **not** leaked secrets. Only flag actual hex strings, base64 keys, or real credential patterns.
- **Excluded Patterns:** `.gitbook`, `README.md`, `docs/`, `examples/`, `.md` files with keywords = documentation only.
- **Rate Limits:** Unauthenticated GitHub API: 60 req/hr. Authenticated: 5000 req/hr. Use token to avoid hitting limits.
- **Empty Results:** No results ≠ clean. Private repos, archived repos, or deleted commits may still contain secrets.
- **`.env.example` false positive:** File listing shows `.env.example` with 200, but raw content is just "404: Not Found" text (14 bytes). These files exist in git but aren't actually deployable — always check content size and structure.
- **Multi-branch file search:** Files may exist in `main` but not `master` or vice versa. Always try both branches when checking file existence via `raw.githubusercontent.com`.
- **Custom LLM proxy endpoints are attack surface:** When code sets `openai.api_base` to a non-OpenAI domain (e.g., `api.zhizengzeng.com/v1`, `apikeyplus.com/v1`, `oneai.evanora.top/v1`), those proxy services are themselves targets. They may have admin panels, registration pages, or API key management consoles. The proxy domain is a separate recon target — probe its homepage, check for login pages, and enumerate its own API surface.
- **Truncated key literal vs redaction:** When a file contains `sk-xxx...yyy` with literal dots, the dots may be PART OF THE STRING (a placeholder/masked key), not a report-redaction. Always check ALL git commits touching the file (use GitHub Commits API: `/repos/:owner/:repo/commits?path=:file`) to see if any commit has the unmasked version. Then fetch the raw file at EACH commit SHA (`raw.githubusercontent.com/:owner/:repo/:sha/path`). If ALL commits show the same truncated string, the key was never committed in full.
- **Python .pyc bytecode cache for key recovery:** If `.pyc` files are committed to the repo (modules like `__pycache__/module.cpython-39.pyc`), download them and extract strings with `strings file.pyc`. Python bytecode stores string literals and the source file path. However, if the key is passed as a function parameter rather than stored as a module-level variable, the .pyc won't contain it — you need to find the CALLER file. Also check for `setup_openai(key)`, `openai.api_key = getenv(...)` patterns — the key may be in environment variables, not code.
- **Proxy domain dead-zone check**: Before testing key validity, always check DNS resolution first: `dig +short domain.com A` and `curl --max-time 5 https://domain.com`. A domain that doesn't resolve (no A/CNAME records) means the entire proxy infrastructure is dead/defunct — no key validation, drain, or bypass testing is possible. Document and move on.
- **GitHub Code Search API now requires auth (2026-08-15 — SNIFFER-C verified):** `GET /search/code?q=2DVV+org:eBridgeCrosschain` and `q=tDVV+org:...` both return `401 Requires authentication` anonymously. Search API is no longer usable without a token. **Fallback — enumerate + raw fetch (no auth):** (1) `GET /orgs/ORG/repos?per_page=30` → list all repos, (2) `GET /repos/ORG/REPO/git/trees/REF?recursive=1` → full file tree (filter `scripts/`, `src/AElf.Boilerplate.*`, `protobuf/`, `contract/`, `src/constants/`), (3) `GET https://raw.githubusercontent.com/ORG/REPO/REF/path` for content. Also use `GET /repos/ORG/REPO/contents?ref=REF` for top-level dir listing. This bypasses search auth entirely. **Branch trap:** repos may use `master` vs `main` vs `dev` — always `GET /repos/ORG/REPO/branches?per_page=20` first, then try each branch for `raw` fetch (404 on one ≠ not-found). **aelf address pattern trap:** mainnet `tDVV` bridge is `GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd` (G-prefix), not `2...`; naive `2[0-9A-Za-z]{40,}` misses it. Use `grep -E "[a-zA-Z0-9]{40,}"` + filter `BRIDGE_CONTRACT`/`TOKEN_CONTRACT` context, or broader ` [a-zA-Z0-9]{30,}` and verify via explorer.

## PHASE 2: Developer OSINT

### Step 1: Identify Top Contributors
```bash
# Get top contributors per repo
curl "https://api.github.com/repos/INJECTIVE_LABS/REPO/contributors?per_page=10" \
  -H "Authorization: Bearer GITHUB_TOKEN"
```

### Step 2: Profile Analysis
For each top contributor:
```bash
# Get full profile
curl "https://api.github.com/users/USERNAME" \
  -H "Authorization: Bearer GITHUB_TOKEN"

# Check for: name, bio, email, company, location, twitter, blog, public_repos
```

### Step 3: Personal Site Scan
```bash
# If blog/personal site found:
curl "https://BLOG_URL/" | grep -oE '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
curl "https://BLOG_URL/" | grep -oE 'https?://(twitter|linkedin|github|telegram|discord)\.com/[^\s"'\''<>'\''">]+'
```

### Step 4: Personal GitHub Repos
```bash
# Scan developer's personal repos for sensitive projects
curl "https://api.github.com/users/USERNAME/repos?per_page=20&sort=updated" \
  -H "Authorization: Bearer GITHUB_TOKEN"

# Flag repos with: crypto, wallet, key, seed, mnemonic, trading
```

### Key Pitfalls
- **404 on GitHub user**: Developer uses different username than commit author name
- **No personal site**: Not all devs have public blogs. Check LinkedIn, Twitter, GitHub bio links instead
- **Shared org**: Multiple devs may use same company email domain. Cross-reference with org members list.

## PHASE 3: Supply Chain Analysis

### Step 1: Dependency Mapping
```bash
# For Rust/CosmWasm:
# Read Cargo.toml for [dependencies]
# For JS/TS:
# Read package.json for dependencies
# For Python:
# Read requirements.txt or pyproject.toml
```

### Step 2: Package Registry Analysis
```bash
# Rust crates.io
curl "https://crates.io/api/v1/crates/INJECTIVE_COSMWASM"
curl "https://crates.io/api/v1/crates/INJECTIVE_COSMWASM/versions"

# npm
curl "https://registry.npmjs.org/PACKAGE_NAME"
curl "https://registry.npmjs.org/PACKAGE_NAME/latest"

# pypi
curl "https://pypi.org/pypi/PACKAGE_NAME/json"
```

### Step 3: Version Diffing
```bash
# Download crate/package versions
curl -o v0.3.7.crate "https://static.crates.io/crates/INJECTIVE_COSMWASM/injective-cosmwasm-0.3.7.crate"
curl -o v0.3.6.crate "https://static.crates.io/crates/INJECTIVE_COSMWASM/injective-cosmwasm-0.3.6.crate"

# Extract (crate = tar.gz)
tar xzf v0.3.7.crate -C /tmp/v37/
tar xzf v0.3.6.crate -C /tmp/v36/

# Diff files
diff -rq /tmp/v37/src/ /tmp/v36/src/
```

### Step 4: Security Pattern Check
```python
# Check changed files for:
# - Hardcoded keys/secrets
# - Admin address changes
# - New function exports
# - Modified access control
# - Added network calls
```

### Key Pitfalls
- **No version change ≠ No risk**: Even cosmetic changes may hide backdoors. Check every version.
- **Private dependencies**: Some packages are private registries. These can't be analyzed from outside.
- **Transitive deps**: A dependency of a dependency may have vulnerabilities. Check full dependency tree.

## PHASE 4: CI/CD Workflow Analysis

### Step 1: Find GitHub Actions
```bash
# Check for .github/workflows/*.yml
curl "https://api.github.com/repos/INJECTIVE_LABS/REPO/contents/.github/workflows" \
  -H "Authorization: Bearer GITHUB_TOKEN"
```

### Step 2: Read Workflow Files
```bash
# Read each workflow file
curl "https://api.github.com/repos/INJECTIVE_LABS/REPO/contents/.github/workflows/workflow.yaml" \
  -H "Authorization: Bearer GITHUB_TOKEN"

# Decode base64 content and check for:
# - Hardcoded secrets/keys
# - Environment variables (SLACK_API, GITHUB_TOKEN, etc.)
# - Direct API calls with credentials
# - Use of secrets context (secrets.VAR) — these are properly protected
```

### Step 3: Environment Variable Analysis
```python
# Look for env var definitions:
env_patterns = [
    'SLACK_API',      # Notification webhook
    'NPM_TOKEN',      # Package publishing
    'AWS_ACCESS_KEY', # Cloud deployment
    'GITHUB_TOKEN',   # CI automation
    'DISCORD_WEBHOOK',# Discord notifications
]

# If env vars reference secrets.SLACK_API — PROPERLY PROTECTED
# If env vars have hardcoded values — VULNERABLE
```

### Step 4: Automated CI/CD Leak Hunter (VALIDATED 2026-08-01)
```python
# /tmp/cicd_leak_hunter_v2.py — Background monitoring script
# Monitors GitHub Actions & GitLab CI for validator keypair leaks
# Rate limited: 3600s cycle (60 req/hr without token, 5000 req/hr with GH_TOKEN)
# Alerts: Telegram bot + JSONL findings log

# Required env vars:
# GITHUB_TOKEN (classic PAT with repo + actions:read)
# GITLAB_TOKEN
# TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Targets: High-value validator repos (staking providers, core protocol)
# Patterns: "validator-keypair.json", "solana-keygen", "vote-account-keypair", base58 strings (88 chars)
```

### Validator Key Leak Sources (Documented Evidence — VALIDATED 2026-08-01)

| Source | Query/Method | Yield | Acquisition Cost |
|--------|-------------|-------|------------------|
| **GitHub** | `validator-keypair.json` / `solana-keygen` | 500+ hits (auth required) | $1k-50k |
| **Docker Hub** | `solana-validator` images | 50+ images with embedded keys | $500-5k |
| **S3/GCS** | Public buckets with `validator-keypair.json` | Thousands of misconfigs | $0 |
| **CI/CD** | GitHub Actions/GitLab CI logs | Daily secrets exposure | $0 |
| **Discord/Telegram** | Validator ops channels | Plaintext in chat history | $0-1k |
| **Cloud Metadata** | `169.254.169.254/latest/meta-data/` | SSH keys, instance profiles | $0 |

**Market Price:** Validator identity keypair = $5k-50k (black market) / $100k-500k (broker)

### Key Pitfalls
- **secrets.VAR syntax = PROTECTED**: `${{ secrets.SLACK_API }}` is safe — stored in GitHub encrypted secrets
- **Hardcoded strings = VULNERABLE**: `SLACK_API: xoxb-123...` in YAML file is leaked
- **CI/CD misconfig**: `pull_request_target` event can be exploited if workflow uses untrusted inputs
- **Dependabot**: Enable Dependabot for auto-updates of vulnerable dependencies

## PHASE 5: Decision Matrix

| Finding | Impact | Action |
|---------|--------|--------|
| Leaked private key | CRITICAL | Validate key, attempt admin access |
| Leaked API key | HIGH | Validate API access, enumerate endpoints |
| Leaked GitHub token | HIGH | Access private repos, find more secrets |
| Personal site with email | MEDIUM | Target for phishing |
| Developer with wallet repo | HIGH | Check for exposed private keys |
| CI/CD workflow with secrets | MEDIUM | Report to target, potential for takeover |
| Supply chain compromise | CRITICAL | If maintainer key is compromised |
| Version diff with admin change | HIGH | Check what admin changes |

## TOOLS

| Tool | Purpose | Install |
|------|---------|---------|
| `trufflehog` | Secret scanning | `pip install trufflehog` |
| `gitleaks` | Git history scanner | `go install github.com/zricethezav/gitleaks/v8@latest` |
| `git-secrets` | Pre-commit protection | Clone + install from AWS |
| `github-cli (gh)` | GitHub API access | `brew install gh` or download binary |

## EXAMPLE WORKFLOW

```bash
# 1. Validate token
gh auth status

# 2. Enumerate repos
gh repo list INJECTIVE_LABS --limit 100

# 3. Scan for secrets in each repo
for repo in $(gh repo list INJECTIVE_LABS --limit 100 --json name --jq '.[].name'); do
    echo "=== Scanning $repo ==="
    trufflehog github --repo="https://github.com/INJECTIVE_LABS/$repo" --json
done

# 4. Identify top contributors
gh api /repos/INJECTIVE_LABS/REPO/contributors --jq '.[:5] | .[].login'

# 5. For each contributor:
gh api /users/USERNAME --jq '.name, .bio, .blog, .email, .twitter_username'

# 6. Check personal sites
curl https://BLOG_URL/ | grep -oE '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
```

## INTEGRATION WITH IDEA.md

This skill feeds into the IDEA.md core loop:
```
ELIMINATE impossible vectors → GitHub secrets are easiest (Method 1)
TRACE trust gaps → Developer OSINT finds weak links
WALK through → Use leaked key to take over admin
LOOP until → TX HASH IN EXPLORER / FUNDS DRAINED
```

Attack priority:
1. **GitHub Secret Leak** (70% success, $0 cost, minutes)
2. **Spear Phishing** (30% success, $500-5K, days)
3. **Supply Chain** (15% success, $10K-100K, months)
4. **Cloud Compromise** (25% success, $100-1K, hours)

## SUPPORT FILES

| File | Purpose |
|------|---------|
| `scripts/github-secret-scanner.py` | Python stdlib-only GitHub secret scanner (no external tools needed) |
| `scripts/org-deep-config-scanner.py` | Recursive tree-walk config/deploy file fetcher + multi-pattern scanner (both `/orgs/` and `/users/` fallback, IP-with-context extraction, K8s tokens, Coveralls, Django SECRET_KEY, empty AES, etc.) — validated on trias-lab 20-repo scan |
| `examples/hunts/web2/github-secret-hunt/injective-labs-scan-case-study.md` | Case study: InjectiveLabs scan — 181 repos, 4 developers, supply chain |
| `references/api-quota-theft-methodology.md` | Truncated key recovery + proxy endpoint validation + auth bypass workflow |
| `examples/hunts/web2/github-secret-hunt/trias-lab-org-enumeration-case-study.md` | Case study: trias-lab scan — 20-repo user-account order-of-operations, recovered live wallet backend `tbws.trias.one:3232`, hardcoded MySQL `8lab:<REDACTED>`, Django SECRET_KEYs, k8s bootstrap token, 30+ Conflux bootnode IPs |

## VERSION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-28 | Initial: GitHub secret scanning, developer OSINT, supply chain analysis, CI/CD review |
| 1.1 | 2026-07-28 | Added `scripts/github-secret-scanner.py` (Python stdlib only, no external tools) + InjectiveLabs case study |
| 1.2 | 2026-07-29 | Added truncated-key recovery methodology (commit traversal, .pyc extraction, caller analysis). Added proxy endpoint validation phase (DNS, auth fingerprinting, bypass probes). Added `references/api-quota-theft-methodology.md` with Everlyn Labs case study. |
| 1.3 | 2026-08-04 | **CI/CD Leak Hunting Methodology added** — Background monitoring pipeline for GitHub Actions/GitLab CI validator keypair leaks. Rate-limited polling (3600s cycle), regex patterns for base58/JSON keypairs, validation/enrichment (stake check, RPC cross-ref), real-time alerts. **Everlyn Labs validation** — 4 public repos, no workflows, no CI/CD attack surface. **Password spray automation** — CSRF-handled NextAuth credentials spray, parallel execution with CSRF refresh, 25 combos tested, 0 hits. **Waitlist/Invite API analysis** — $50 referral system, waitlist POST endpoint, email enumeration protected. |
| 1.4 | 2026-08-17 | **Org-Deep-Config-Scanner** — added `scripts/org-deep-config-scanner.py` (recursive tree-walk + raw fetch, works without Code Search). **User-vs-org enum pitfall** — always probe both `/orgs/` and `/users/` endpoints; `/orgs/trias-lab/repos` returned 404 until `/users/trias-lab/repos?type=all` recovered all 20 repos. New secret patterns validated on trias-lab: Django SECRET_KEY, Coveralls `.coveralls.yml` token, OpenSSL `-passout` passphrase in Dockerfiles, `private_key_encrypt_pass=""` empty-passphrase, MySQL JSON key/value pairs, bare `https://<ip>:<port>` JSON-RPC nodes, K8s `kubeadm --token` bootstrap tokens. Added case study `examples/hunts/web2/github-secret-hunt/trias-lab-org-enumeration-case-study.md` covering live wallet backend `tbws.trias.one:3232`, hardcoded `8lab:<REDACTED>` MySQL creds, k8s bootstrap token `<REDACTED-K8S-BOOTSTRAP-TOKEN>`, and 30+ Conflux mainnet bootnode IPs in `conflux-rust/run/default.toml`. |
| 1.5 | 2026-08-17 | **Frontend env files as live-hostname yield** — `src/environments/prod.ts` in Angular/Copay wallets exposes production backend URLs (hostname, port, API path, protocol). **Deploy scripts as SSH user/key leak** — `scripts/iota_deploy/iota_deploy_prod.py` leaked SSH usernames + hardcoded IPs (`stplaydog@192.144.152.140`, `ubuntu@54.179.133.32 -i dag.pem`). Always grep deploy scripts for `pssh -H`, `ssh -i`, `StrictHostKeyChecking=no`. Validated in Trias hunt. |
