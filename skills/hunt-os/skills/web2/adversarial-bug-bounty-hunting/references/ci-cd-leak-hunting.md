# CI/CD Leak Hunting — Automated Key Acquisition Methodology
**Validated:** 2026-08-04 | **Target:** Everlyn Labs GitHub org | **Status:** Clean (no CI/CD)

---

## METHODOLOGY

### 1. Target Identification
```bash
# Find org repos
curl -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/orgs/ORG/repos?per_page=100"
```

### 2. Workflow Discovery
```bash
# Check for GitHub Actions
curl -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/ORG/REPO/contents/.github/workflows"

# Check for GitLab CI
curl "https://gitlab.com/api/v4/projects/ORG%2FREPO/repository/tree?path=.gitlab"

# Check other CI configs
for file in .gitlab-ci.yml .circleci/config.yml azure-pipelines.yml Jenkinsfile .travis.yml; do
  curl -s "https://api.github.com/repos/ORG/REPO/contents/$file"
done
```

### 3. Secret Pattern Search
```bash
# Common patterns in workflow files
patterns=(
  "secret" "SECRET" "token" "TOKEN" "key" "KEY" 
  "password" "PASSWORD" "cred" "CRED"
  "aws_access_key_id" "aws_secret" "gcp" "azure"
  "validator" "keypair" "solana" "vote-account"
  "private_key" "PRIVATE_KEY" "mnemonic" "MNEMONIC"
)
```

### 4. Automated Monitoring (24/7)
```python
# /tmp/cicd_leak_hunter_v2.py
# - Polls GitHub Actions & GitLab CI every hour
# - Downloads build logs from public runs
# - Regex matches keypair patterns (base58 88-chars, JSON arrays, file paths)
# - Validates keys (derives pubkey, checks stake)
# - Alerts via Telegram/Email
# - Rate limited: 60 req/hr (no token) / 5000 req/hr (with GH_TOKEN)
```

### 5. Rate Limit Management
```bash
# Without token: 60 req/hr → hourly cycles only
# With GH_TOKEN (classic PAT, repo + actions:read): 5000 req/hr
# Required env vars:
# GITHUB_TOKEN=ghp_xxx
# GITLAB_TOKEN=xxx
# TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

---

## EVERLYN LABS CASE STUDY (2026-08-04)

| Check | Result |
|-------|--------|
| GitHub Actions workflows | None (404 on all 4 repos) |
| GitLab CI / CircleCI / Azure / Jenkins / Travis | None |
| GitHub Releases | None |
| PyPI packages | None |
| Docker Hub images | None |
| TruffleHog scan | Clean |

**Conclusion:** Pure research repos — no CI/CD pipeline to attack.

---

## VALIDATION REQUIREMENTS

For bug bounty reports:
1. **Public workflow URL** with leaked secret
2. **Commit SHA** where leak occurred
3. **Key validity proof** (derive pubkey, check stake/balance)
4. **Timeline** — when leaked, when rotated
5. **Impact** — validator identity, stake amount, funds at risk

---

## TOOLCHAIN

| Tool | Purpose |
|------|---------|
| `gh` CLI / GitHub API | List workflows, download logs |
| `gitlab` CLI / GitLab API | List pipelines, download job logs |
| `gitleaks` / `trufflehog` | Secret scanning |
| Custom Python | Regex matching, validation, alerting |
| `jq` | JSON parsing |

---

## PRIORITY TARGETS FOR SOLANA VALIDATORS

| Priority | Target Type | Why |
|----------|-------------|-----|
| **P0** | Staking provider repos (Figment, P2P, Chorus One, Blockdaemon) | High stake validators |
| **P1** | Individual validator repos with Actions | Direct key access |
| **P2** | Docker Hub images `solana-validator` | Embedded keypairs in layers |
| **P3** | GitHub Gists with `validator-keypair.json` | Accidental paste |

---

## PITFALLS

1. **Rate limiting without token** — 60 req/hr, need PAT for real monitoring
2. **Private repos inaccessible** — Only public repos scannable without access
3. **False positives** — Base58 strings in test data, example configs
3. **Log retention** — GitHub Actions logs retained 90 days, GitLab varies
4. **Secret rotation** — Leaked keys may be rotated before you find them