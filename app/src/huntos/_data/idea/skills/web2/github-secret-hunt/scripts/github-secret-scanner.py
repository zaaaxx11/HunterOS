#!/usr/bin/env python3
"""
GitHub Secret Scanner — Python stdlib only, no external tools required.
Scans a GitHub org for leaked secrets in public repos, issues, and code.

Usage:
  python3 github_secret_scanner.py <GITHUB_TOKEN> <ORG_NAME>

Requirements:
  - Python 3.6+
  - Only stdlib: urllib, json, base64, re, sys
"""

import sys
import json
import base64
import re
import urllib.request
import urllib.error
from collections import defaultdict

def scan_org(token, org, max_pages=10):
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "GitHubSecretScanner/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Patterns to scan for
    secret_patterns = {
        "AWS_ACCESS_KEY": re.compile(r'AKIA[0-9A-Z]{16}'),
        "AWS_SECRET_KEY": re.compile(r'(?i)(aws_secret_access_key|aws_secret)\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}'),
        "PRIVATE_KEY": re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'),
        "HEX_PRIVATE_KEY": re.compile(r'0x[a-fA-F0-9]{64}'),
        "GITHUB_TOKEN": re.compile(r'gh[pousr]_[A-Za-z0-9_]{36,}'),
        "SLACK_TOKEN": re.compile(r'xox[baprs]-[A-Za-z0-9\-]{10,}'),
        "API_KEY": re.compile(r'(?i)(api[_\-]?key)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}'),
        "PASSWORD": re.compile(r'(?i)(password|passwd|pass)\s*[=:]\s*["\']?[^\s"\']{8,}'),
        "DB_CONNECTION": re.compile(r'(postgres|mysql|mongodb|redis)://[^\s:]+:[^\s]+@[^\s]+'),
        "STRIPE_KEY": re.compile(r'sk_live_[A-Za-z0-9]{24,}'),
        "GENERIC_SECRET": re.compile(r'(?i)(secret|token|credential)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}'),
    }
    
    # Skip patterns (docs, examples)
    skip_patterns = [
        r'\.md$', r'/docs/', r'/examples/', r'/test/',
        r'\.gitbook', r'README', r'tutorial', r'wiki'
    ]
    
    all_findings = defaultdict(list)
    repos = enumerate_repos(headers, org, max_pages)
    
    print(f"[+] Scanning {len(repos)} repos in {org}...")
    print("=" * 70)
    
    for repo in repos:
        repo_name = repo["name"]
        
        # 1. Check README
        readme = fetch_file(headers, org, repo_name, "README.md")
        if readme:
            check_content(readme, repo_name, "README.md", secret_patterns, all_findings, skip_patterns)
        
        # 2. Check common secret files
        secret_files = [".env", ".env.local", "config.json", "secrets.json", 
                       "api-keys.json", "credentials.json", ".aws/credentials"]
        for sf in secret_files:
            content = fetch_file(headers, org, repo_name, sf)
            if content:
                check_content(content, repo_name, sf, secret_patterns, all_findings, skip_patterns)
        
        # 3. Check issues for sensitive keywords
        issues = fetch_issues(headers, org, repo_name)
        for issue in issues:
            title = issue.get("title", "").lower()
            body = issue.get("body", "").lower()
            if any(kw in title or kw in body for kw in ["secret", "key", "password", "token", "leak"]):
                if "security bump" not in title and "bump " not in title:
                    all_findings[f"{repo_name}"].append({
                        "type": "SENSITIVE_ISSUE",
                        "title": issue["title"],
                        "url": issue["html_url"],
                        "file": "issue"
                    })
    
    # 4. GitHub code search
    print(f"\n[+] Running GitHub code search...")
    print("=" * 70)
    search_queries = [
        "AKIA", "PRIVATE KEY", "api_key", "password", ".env",
        "BEGIN RSA PRIVATE KEY", "ghp_", "xoxb-", "sk_live_"
    ]
    for query in search_queries:
        search_all_org(token, org, headers, query, all_findings)
    
    # 5. Print results
    print(f"\n\n{'='*70}")
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    if all_findings:
        total = sum(len(v) for v in all_findings.values())
        print(f"\n  ⚠️  {total} findings across {len(all_findings)} repos:")
        for repo, findings in sorted(all_findings.items()):
            print(f"\n  {repo} ({len(findings)} findings):")
            for f in findings:
                print(f"    • [{f['type']}] {f['file']}: {f.get('title', '')[:80]}")
                if 'url' in f:
                    print(f"      {f['url']}")
    else:
        print(f"\n  ✓ No obvious secrets found in {len(repos)} repos")
        print(f"\n  Note: This only covers PUBLIC repos. Private repos and")
        print(f"  forks may still contain secrets. Consider using TruffleHog")
        print(f"  for deeper scanning.")
    
    return all_findings


def enumerate_repos(headers, org, max_pages):
    repos = []
    page = 1
    while page <= max_pages:
        url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
                if not data:
                    break
                repos.extend(data)
                page += 1
        except urllib.error.HTTPError as e:
            break
    return repos


def fetch_file(headers, org, repo, path):
    try:
        url = f"https://api.github.com/repos/{org}/{repo}/contents/{path}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
            content = base64.b64decode(d["content"]).decode("utf-8", errors="ignore")
            return content
    except urllib.error.HTTPError:
        return None


def fetch_issues(headers, org, repo, max_issues=50):
    try:
        url = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page={max_issues}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except:
        return []


def check_content(content, repo, filepath, patterns, findings, skip_patterns):
    for skip in skip_patterns:
        if re.search(skip, filepath, re.IGNORECASE):
            return  # Skip docs/examples
    
    for i, line in enumerate(content.split("\n"), 1):
        for pat_name, pat in patterns.items():
            m = pat.search(line)
            if m:
                findings[repo].append({
                    "type": pat_name,
                    "file": f"{filepath}:{i}",
                    "url": f"https://github.com/{org}/{repo}/blob/main/{filepath}#L{i}",
                    "match": m.group(0)[:50]
                })


def search_all_org(token, org, headers, query, all_findings):
    try:
        url = f"https://api.github.com/search/code?q={urllib.request.quote(query)}+org:{org}&per_page=5"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
            total = d.get("total_count", 0)
            items = d.get("items", [])
            
            if total == 0:
                print(f"  {query}: {total} results")
            else:
                # Check if results are real or docs
                real_results = []
                for item in items:
                    path = item["path"]
                    repo = item["repository"]["full_name"]
                    # Skip docs
                    is_skip = any(sp in path.lower() for sp in ['.gitbook', '.md', 'docs/', 'examples/'])
                    if not is_skip:
                        real_results.append((repo, path, item.get("html_url", "")))
                
                if real_results:
                    print(f"  ⚠️  {query}: {total} total, {len(real_results)} non-doc results:")
                    for repo, path, url in real_results[:3]:
                        print(f"    {repo}/{path}")
                        print(f"    {url}")
                else:
                    print(f"  {query}: {total} results (all docs/examples)")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"  {query}: Rate limited (HTTP 403)")
        else:
            print(f"  {query}: HTTP {e.code}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 github_secret_scanner.py <GITHUB_TOKEN> <ORG_NAME>")
        sys.exit(1)
    
    token = sys.argv[1]
    org = sys.argv[2]
    scan_org(token, org)
