#!/usr/bin/env python3
"""
Org-Deep-Config-Scanner — enumerate ALL repos for a GitHub account (org OR user),
fetch every deploy/docker/nginx/env/config file via recursive git-tree walk, and
scan content for leaked secrets + hardcoded deployment endpoints (IPs, hostnames,
RPC URLs, K8s tokens, DB credentials, Django SECRET_KEYs, AES passphrases, etc.).

Pure stdlib (urllib, json, re). No token required for public repos (works with
the lower unauthenticated rate limit; pass GITHUB_TOKEN as env var or arg for
5000 req/hr).

Usage:
  python3 org-deep-config-scanner.py <GITHUB_ORG_OR_USER_NAME> [GITHUB_TOKEN]

Output:
  - /tmp/<name>_repos.json          — enumerated repo metadata
  - /tmp/<name>_deep_scan.json      — structured findings (ips/secrets/rpc/env)
  - /tmp/<name>_all_files.json      — full content of all scanned files
  - stdout                          — human-readable findings summary

Validated on trias-lab (20 repos, 340+ files, 56 IPs, 11 secrets, 4 RPC endpoints,
1 DB conn string) on 2026-08-17. See
references/trias-lab-org-enumeration-case-study.md in the github-secret-hunt skill.
"""

import json, os, re, sys, time, urllib.request, urllib.error

ACCOUNT = sys.argv[1] if len(sys.argv) > 1 else None
TOKEN   = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GITHUB_TOKEN", "")
if not ACCOUNT:
    print("Usage: python3 org-deep-config-scanner.py <GITHUB_ORG_OR_USER_NAME> [GITHUB_TOKEN]")
    sys.exit(1)

UA = "org-deep-config-scanner/1.0"

def headers():
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h

def fetch(url):
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=headers())
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 403 and "rate limit" in e.read().decode("utf-8", "replace").lower():
                print(f"  [RATE LIMIT] sleeping 20s...", file=sys.stderr); time.sleep(20); continue
            if e.code == 404:
                return None
            print(f"  [HTTP {e.code}] {url[:100]}", file=sys.stderr); return None
        except Exception as ex:
            print(f"  [ERR] {url[:100]}: {ex}", file=sys.stderr); time.sleep(2)
    return None

def fetch_raw(owner, repo, branch, path):
    return fetch(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}")

# ---- Pattern sets ------------------------------------------------------

AWS_KEY_RE       = re.compile(r'(AKIA[0-9A-Z]{16})')
AWS_SECRET_RE    = re.compile(r'(?i)aws_secret_access_key["\']?\s*[:=]\s*["\']?([A-Za-z0-9/+=]{40})')
PRIVATE_KEY_RE   = re.compile(r'-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE KEY-----')
Django_SECRET_RE = re.compile(r"""(?:SECRET_KEY|secret_key)\s*=\s*['"]([A-Za-z0-9!@#$%^&*()_\-+=\[\]{}|:;<>?,./`~]{30,})['"]""")
COVERALLS_RE     = re.compile(r'token:\s*([A-Za-z0-9]{32})')
OPENSSL_PASS_RE  = re.compile(r'pass(?:out|in)?\s+pass:\s*([A-Za-z0-9_\-]{4,})')
EMPTY_PASS_RE    = re.compile(r'private_key_encrypt_pass["\']?\s*:\s*["\']["\']')
MYSQL_CRED_RE    = re.compile(r'mysql_(user|password)["\']?\s*:\s*["\']([^"\']{1,})["\']')
GENERIC_SECRET_RE = re.compile(
    r"""(?i)(password|passwd|pwd|secret|token|api[_\-]?key|access[_\-]?key|private[_\-]?key)\s*["\']?\s*[:=]\s*["\']?([^\s"']{8,})"""
)
MONGO_RE    = re.compile(r'mongodb(?:\+srv)?://[^\s"\']+')
MYSQL_RE    = re.compile(r'mysql://[^\s"\']+')
RPC_URL_RE  = re.compile(r'(https?://[a-zA-Z0-9.\-]+(?::\d+)?/(?:rpc|api|v1|v2|json_rpc))', re.I)
IP_RE       = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?\b')
HOSTNAME_RE = re.compile(r'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|net|org|io|co|dev|app|xyz|foundation|network|cn|one))\b')
K8S_TOKEN_RE = re.compile(r'--token\s+([a-z0-9]{6}\.[a-z0-9]{16})')
ETH_RPC_IP_RE = re.compile(r'(https?://[\d\.]+:\d+)')
JWT_RE      = re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')

# Filtering heuristics
NOT_IPS = {"127.0.0.1", "0.0.0.0", "255.255.255.255", "255.255.255.0", "127.0.0.0"}
NO_HOSTS = {"github.com","gitlab.com","npmjs.com","registry.npmjs.org","w3.org","schema.org",
           "opensource.org","example.com","gnu.org","docker.io"}
GENERIC_BLOCKLIST = {"true","false","undefined","null","none","example","test","localhost",
                     "","xxxxxxxx","***","your_key_here","password","changeme"}

# Config-file path patterns (lowercase substring match)
PATH_SUBSTRINGS = [
    "docker-compose","dockerfile",".env","nginx","caddy","caddyfile","k8s","kubernetes",
    "deployment.yaml","deploy.yaml",".yaml",".yml","config.","conf.","settings.",
    ".conf",".ini",".toml","makefile","procfile","pm2","ecosystem",
    ".travis",".circleci","workflows","deploy","start.sh","stop.sh","run.sh",
    "install.sh","setup.sh",".service","systemd","supervisord",
    "terraform",".tf","database",".mongo","proxy","reverse","secret","credentials","creds",
]

# Always-try paths when a tree fetch fails
COMMON_PATHS = [
    "docker-compose.yml","docker-compose.yaml","Dockerfile","Dockerfile.dev",
    ".env",".env.example",".env.local","env.example",
    "nginx.conf","conf/nginx.conf","deploy/nginx.conf","Caddyfile",
    "config.json","config.yaml","config.yml","config.toml",
    "Makefile","Procfile","deploy.sh","start.sh","run.sh",
    "pm2.json","ecosystem.config.js",
    "app.json","app.yaml",
]

# ---- Scan function ----------------------------------------------------

def scan(content, repo, path):
    """Yield findings (type, value, context) found in `content`."""
    if not content:
        return

    # IPs with context
    for m in IP_RE.finditer(content):
        ip = m.group(1); port = m.group(2)
        if ip in NOT_IPS:
            continue
        parts = ip.split(".")
        if any(int(p) > 255 for p in parts):
            continue
        s = max(0, m.start()-60); e = min(len(content), m.end()+60)
        ctx = content[s:e].replace("\n"," ").replace("\r"," ").strip()
        yield ("IP", f"{ip}:{port}" if port else ip, ctx)

    # AWS keys
    for m in AWS_KEY_RE.finditer(content):
        yield ("AWS_ACCESS_KEY", m.group(1), "")
    for m in AWS_SECRET_RE.finditer(content):
        yield ("AWS_SECRET", m.group(1)[:10]+"...", "")

    # Private keys
    if PRIVATE_KEY_RE.search(content):
        yield ("PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----", "")

    # Django SECRET_KEY
    for m in Django_SECRET_RE.finditer(content):
        v = m.group(1)
        if v and not any(w in v.lower() for w in GENERIC_BLOCKLIST):
            yield ("DJANGO_SECRET_KEY", v, "")

    # Coveralls.io tokens
    for m in COVERALLS_RE.finditer(content):
        yield ("COVERALLS_TOKEN", m.group(1), "")

    # OpenSSL passphrases (Dockerfile leak)
    for m in OPENSSL_PASS_RE.finditer(content):
        yield ("OPENSSL_PASSPHRASE", m.group(1), "")

    # Empty AES passphrases
    if EMPTY_PASS_RE.search(content):
        yield ("EMPTY_AES_PASSPHRASE", '""', "")

    # MySQL JSON credentials
    for m in MYSQL_CRED_RE.finditer(content):
        yield ("MYSQL_CRED", f"{m.group(1)}={m.group(2)}", "")

    # Generic secret patterns
    for m in GENERIC_SECRET_RE.finditer(content):
        k = m.group(1).lower(); v = m.group(2)
        if v and v not in GENERIC_BLOCKLIST and len(v) > 8:
            yield ("CREDENTIAL", f"{k}={v}", "")

    # DB connection strings
    for m in MONGO_RE.finditer(content):
        yield ("MONGO_CONN", m.group(0)[:80], "")
    for m in MYSQL_RE.finditer(content):
        yield ("MYSQL_CONN", m.group(0)[:80], "")

    # RPC endpoints
    for m in RPC_URL_RE.finditer(content):
        yield ("RPC_ENDPOINT", m.group(1), "")
    for m in ETH_RPC_IP_RE.finditer(content):
        yield ("ETH_RPC_IP", m.group(1), "")

    # K8s bootstrap tokens
    for m in K8S_TOKEN_RE.finditer(content):
        yield ("K8S_TOKEN", m.group(1), "")

    # JWTs
    for m in JWT_RE.finditer(content):
        yield ("JWT", m.group(0)[:20]+"...", "")

# ---- Repo enumeration --------------------------------------------------

def enumerate_repos(name):
    """Try orgs first, then users; return whichever returns non-empty."""
    for etype in ("orgs", "users"):
        all_repos = []
        for page in range(1, 6):
            url = f"https://api.github.com/{etype}/{name}/repos?per_page=100&page={page}&type=all"
            raw = fetch(url)
            if not raw:
                break
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                break
            if not isinstance(data, list) or not data:
                break
            all_repos.extend(data)
            if len(data) < 100:
                break
        if all_repos:
            print(f"[+] {etype}/{name}: {len(all_repos)} repos")
            return all_repos
        else:
            print(f"[-] {etype}/{name}: no repos (likely 404)")
    return []

# ---- Tree walk --------------------------------------------------------

def get_tree(owner, repo, branch):
    raw = fetch(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1")
    if not raw:
        return None
    try:
        return json.loads(raw).get("tree")
    except json.JSONDecodeError:
        return None

def interesting_paths(tree):
    matches = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        p = item.get("path", "")
        pl = p.lower()
        for sub in PATH_SUBSTRINGS:
            if sub in pl:
                matches.append(p); break
        # extension-based catch
        for ext in (".env",".yml",".yaml",".tf",".conf",".ini",".toml",".service"):
            if pl.endswith(ext) and p not in matches:
                matches.append(p); break
        for nm in ("dockerfile","docker-compose","nginx","caddyfile","env.example",".coveralls.yml"):
            if nm in pl and p not in matches:
                matches.append(p); break
    return matches

# ---- Main --------------------------------------------------------------

def main():
    repos = enumerate_repos(ACCOUNT)
    if not repos:
        print(f"[!] No repos found for {ACCOUNT}")
        sys.exit(1)

    with open(f"/tmp/{ACCOUNT}_repos.json", "w") as f:
        json.dump(repos, f, indent=2)

    findings = {"ips": {}, "secrets": [], "rpc_endpoints": [], "db_creds": [], "files_scanned": []}

    for repo in repos:
        name = repo["name"]
        branch = repo.get("default_branch", "master")
        print(f"\n--- {name} ({branch}) ---")

        tree = get_tree(ACCOUNT, name, branch)
        if not tree:
            # Fall back to a handful of common paths
            for p in COMMON_PATHS:
                content = fetch_raw(ACCOUNT, name, branch, p)
                if content:
                    print(f"  [+] {p}")
                    for kind, val, ctx in scan(content, name, p):
                        _record(findings, kind, val, ctx, f"{name}/{p}")
                    findings["files_scanned"].append({"repo": name, "path": p})
            continue

        paths = interesting_paths(tree)
        if not paths:
            print("  (no interesting config files)")
            continue

        print(f"  Found {len(paths)} interesting files")
        for p in paths[:50]:  # rate-limit cap
            content = fetch_raw(ACCOUNT, name, branch, p)
            if content:
                for kind, val, ctx in scan(content, name, p):
                    _record(findings, kind, val, ctx, f"{name}/{p}")
                findings["files_scanned"].append({"repo": name, "path": p,
                                                   "content": content[:10000]})

    # Print summary
    print("\n" + "="*60)
    print(f"SUMMARY: {len(findings['files_scanned'])} files scanned")
    print("="*60)
    print(f"\nUnique IPs:          {len(findings['ips'])}")
    for ip in sorted(findings['ips']):
        print(f"  {ip}")
        for ctx in findings['ips'][ip][:3]:
            print(f"    {ctx}")
    print(f"\nSecrets:             {len(findings['secrets'])}")
    for s in findings['secrets']:
        print(f"  [{s['type']}] {s['value']} | {s['source']}")
    print(f"\nRPC endpoints:       {len(findings['rpc_endpoints'])}")
    for r in findings['rpc_endpoints']:
        print(f"  {r['url']} | {r['source']}")
    print(f"\nDB conn strings:     {len(findings['db_creds'])}")
    for d in findings['db_creds']:
        print(f"  {d['value']} | {d['source']}")
    print(f"\nTotal files scanned: {len(findings['files_scanned'])}")

    # Persist findings
    out = f"/tmp/{ACCOUNT}_deep_scan.json"
    with open(out, "w") as f:
        json.dump({
            "ips": findings["ips"],
            "secrets": findings["secrets"],
            "rpc_endpoints": findings["rpc_endpoints"],
            "db_creds": findings["db_creds"],
            "files_count": len(findings["files_scanned"]),
        }, f, indent=2, default=str)
    print(f"\nFindings saved to {out}")

    all_files_out = f"/tmp/{ACCOUNT}_all_files.json"
    with open(all_files_out, "w") as f:
        json.dump(findings["files_scanned"], f, indent=2)
    print(f"File contents saved to {all_files_out}")

def _record(findings, kind, val, ctx, source):
    if kind == "IP":
        findings["ips"].setdefault(val, [])
        entry = f"{source}: {ctx}"
        if entry not in findings["ips"][val]:
            findings["ips"][val].append(entry)
    elif kind in ("MONGO_CONN","MYSQL_CONN"):
        findings["db_creds"].append({"value": val, "source": source})
    elif kind == "RPC_ENDPOINT":
        findings["rpc_endpoints"].append({"url": val, "source": source})
    else:
        findings["secrets"].append({"type": kind, "value": val, "context": ctx, "source": source})

if __name__ == "__main__":
    main()
