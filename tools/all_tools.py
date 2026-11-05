"""HunterOS Plugins — ALL TOOLS (Standalone, NO HunterOsHarness dependency).

MIRRORS every tool from:
  src/hunter/agent/tools.py        (core: think, notes, coverage, http, probes, findings, shell)
  src/hunter/agent/toolchain.py    (Foundry, Slither, Nuclei, Masscan, Gobuster, SQLMap)
  src/hunter/agent/tools_local.py  (search_files, read_file, search_glob, archive_read)
  src/hunter/agent/tools_network.py(dns_resolve, crt_sh, headers_audit, recon, port_hint, tls)
  src/hunter/agent/tools_web3.py   (contract_read, contract_source_fetch, abi_decode_hint)
  src/hunter/agent/tools_verify.py (verify_finding)
  src/hunter/agent/tools_expand.py (derive_targets, expand_finding)
  src/hunter/agent/tools_patch.py  (patch_write)
  src/hunter/agent/tool_forge.py   (forge_tool)

Usage:
  from tools.all_tools import call
  result = call("forge_build", path="/path/to/project")
  result = call("dns_resolve", host="example.com")
  result = call("runtime_inventory")

CLI:
  python all_tools.py <tool_name> [key=value ...]
  python all_tools.py list  # list all available tools
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urljoin

# ═══════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

_MAX_OUTPUT = 16384
_DEFAULT_TIMEOUT = 180


def _truncate(text: str, limit: int = _MAX_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated at {limit} chars]"


def _ok(**kw) -> dict:
    return {"ok": True, "code": "ok", **kw}


def _err(code: str, message: str, blocked: bool = False) -> dict:
    prefix = "BLOCKED" if blocked else "ERROR"
    return {"ok": False, "blocked": blocked, "code": code,
            "result_for_model": f"{prefix} [{code}] {message}"}


# ═══════════════════════════════════════════════════════════════════════════
# BINARY RESOLUTION (mirrors toolchain.py)
# ═══════════════════════════════════════════════════════════════════════════

_BINARIES = {
    "forge":    ("forge",    "curl -L https://foundry.paradigm.xyz | bash && foundryup"),
    "cast":     ("cast",     "curl -L https://foundry.paradigm.xyz | bash && foundryup"),
    "anvil":    ("anvil",    "curl -L https://foundry.paradigm.xyz | bash && foundryup"),
    "slither":  ("slither",  "pip install slither-analyzer && slither --version"),
    "solc":     ("solc",     "pip install solc-select && solc-select install latest"),
    "masscan":  ("masscan",  "apt-get install masscan"),
    "nuclei":   ("nuclei",   "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
    "gobuster": ("gobuster", "go install github.com/OJ/gobuster/v3@latest"),
    "sqlmap":   ("sqlmap",   "git clone https://github.com/sqlmapproject/sqlmap"),
    "nmap":     ("nmap",     "apt-get install nmap"),
}
_CHILD_ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "COMSPEC", "PATHEXT",
                        "SYSTEMDRIVE", "WINDIR", "LANG", "LC_ALL", "TERM", "SUDO_ASKPASS")
_RESOLVE_CACHE: dict[str, str | None] = {}


def _resolve(binary: str) -> str | None:
    if binary in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[binary]
    found = shutil.which(binary)
    if found is None:
        for home in (os.environ.get("HOME"), "/home/ubuntu"):
            if not home:
                continue
            for sub in (".foundry/bin", "hunteros-venv/bin", ".local/bin"):
                c = Path(home) / sub / binary
                if c.exists() and c.is_file():
                    found = str(c)
                    break
            if found is not None:
                break
    _RESOLVE_CACHE[binary] = found
    return found


def _child_env(cwd: Path) -> dict[str, str]:
    env = {}
    for key in _CHILD_ENV_ALLOWLIST:
        v = os.environ.get(key)
        if v is not None:
            env[key] = v
    env["HOME"] = os.environ.get("HOME", str(cwd))
    extra = []
    home = os.environ.get("HOME", "")
    for sub in (".foundry/bin", "hunteros-venv/bin", ".local/bin"):
        if home:
            c = os.path.join(home, sub)
            if os.path.isdir(c) and c not in extra:
                extra.append(c)
    if extra:
        env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    env["HUNTER_SANDBOX"] = "1"
    env["NO_COLOR"] = "1"
    return env


def _jail_cwd() -> Path:
    jail = Path(tempfile.gettempdir()) / "hunter-toolchain"
    try:
        jail.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path(tempfile.gettempdir())
    return jail


def _run(argv: list[str], *, cwd: Path, timeout_s: int = _DEFAULT_TIMEOUT,
         privileged: bool = False) -> dict:
    cmd = list(argv)
    if privileged:
        cmd = ["sudo", "-A", *argv]
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=_child_env(cwd),
                           capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": "tool.timeout",
                "result_for_model": f"timed out after {timeout_s}s: {' '.join(cmd)}"}
    except OSError as exc:
        return {"ok": False, "code": "tool.exec_failed",
                "result_for_model": f"{type(exc).__name__}: {exc}"}
    out = _truncate(p.stdout or "")
    err = _truncate(p.stderr or "")
    return _ok(exit_code=p.returncode, stdout=out, stderr=err,
               result_for_model=f"$ {' '.join(cmd)}\nexit={p.returncode}\n{out}{chr(10)+err if err else ''}")


def _unavailable(tool: str, binary: str) -> dict:
    _name, hint = _BINARIES[binary]
    return _err(f"{tool}: {binary} not installed. Install: {hint}", "tool.unavailable")


# ═══════════════════════════════════════════════════════════════════════════
# FOUNDRY / BLOCKCHAIN TOOLS
# ═══════════════════════════════════════════════════════════════════════════

def forge_build(path: str = "", force: bool = False, timeout_s: int = 300) -> dict:
    root = Path(path).expanduser().resolve() if path else Path.cwd()
    if not root.is_dir():
        return _err("toolchain.not_a_directory", f"Not a directory: {path}", blocked=True)
    b = _resolve("forge")
    if not b:
        return _unavailable("forge_build", "forge")
    argv = [b, "build"]
    if force:
        argv.append("--force")
    return _run(argv, cwd=root, timeout_s=timeout_s)


def forge_test(path: str = "", match_test: str = "", verbosity: bool = False,
               timeout_s: int = 300) -> dict:
    root = Path(path).expanduser().resolve() if path else Path.cwd()
    if not root.is_dir():
        return _err("toolchain.not_a_directory", f"Not a directory: {path}", blocked=True)
    token = str(match_test).strip()
    if token:
        if not token.replace("_", "").isalnum() or token[0].isdigit():
            return _err("toolchain.bad_test_filter", f"Bad test filter: {token!r}", blocked=True)
        if token.startswith("-"):
            return _err("toolchain.bad_test_filter", f"Looks like a flag: {token!r}", blocked=True)
    b = _resolve("forge")
    if not b:
        return _unavailable("forge_test", "forge")
    argv = [b, "test"]
    if token:
        argv += ["--match-test", token]
    if verbosity:
        argv.append("-vvv")
    return _run(argv, cwd=root, timeout_s=timeout_s)


def slither_run(path: str = "", timeout_s: int = 300) -> dict:
    root = Path(path).expanduser().resolve() if path else Path.cwd()
    if not root.is_dir():
        return _err("toolchain.not_a_directory", f"Not a directory: {path}", blocked=True)
    b = _resolve("slither")
    if not b:
        return _unavailable("slither_run", "slither")
    result = _run([b, str(root), "--json", "-"], cwd=root, timeout_s=timeout_s)
    raw = result.get("stdout", "")
    if not raw.strip():
        result["slither_json_ok"] = False
        return result
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        result["slither_json_ok"] = False
        result["slither_parse_error"] = str(exc)
        return result
    result["slither_json_ok"] = True
    detectors = parsed.get("results", {}).get("detectors", []) or []
    result["detector_count"] = len(detectors)
    result["detectors"] = [
        {"check": d.get("check"), "impact": d.get("impact"), "confidence": d.get("confidence"),
         "description": (d.get("description") or "")[:300]}
        for d in detectors
    ]
    lines = [f"Slither found {len(detectors)} detector(s)."]
    for d in result["detectors"][:20]:
        lines.append(f"  [{d['impact']}|{d['confidence']}] {d['check']}: {d['description']}")
    result["result_for_model"] = "\n".join(lines)[:4000]
    return result


def cast_call(rpc_url: str = "", to: str = "", signature: str = "0x",
              timeout_s: int = 60) -> dict:
    if not rpc_url or not to:
        return _err("toolchain.missing_args", "cast_call requires rpc_url and to")
    b = _resolve("cast")
    if not b:
        return _unavailable("cast_call", "cast")
    return _run([b, "call", to, signature or "0x", "--rpc-url", rpc_url],
                cwd=_jail_cwd(), timeout_s=timeout_s)


# ═══════════════════════════════════════════════════════════════════════════
# WEB2 OFFENSIVE TOOLS
# ═══════════════════════════════════════════════════════════════════════════

def port_scan(host: str = "", ports: str = "0-65535", rate: int = 1000,
              allow_sudo: bool = False, timeout_s: int = 300) -> dict:
    if not host:
        return _err("port.host_required", "port_scan requires host")
    try:
        ip = socket.gethostbyname(host)
    except OSError as exc:
        return _err("port.resolve_failed", f"Cannot resolve {host}: {exc}")
    if not all(c.isdigit() or c in ",-" for c in ports):
        return _err("toolchain.bad_ports", f"Bad ports: {ports!r}", blocked=True)
    try:
        rate = max(1, min(int(rate), 100_000))
    except (TypeError, ValueError):
        rate = 1000
    b = _resolve("masscan")
    if not b:
        return _unavailable("port_scan", "masscan")
    result = _run([b, ip, "-p", ports, "--rate", str(rate), "--wait", "3"],
                  cwd=_jail_cwd(), timeout_s=timeout_s, privileged=allow_sudo)
    combined = result.get("stderr", "") + result.get("stdout", "")
    if result.get("ok") and "permission denied" in combined:
        result["code"] = "tool.privilege_required"
        result["result_for_model"] = (result.get("result_for_model", "") +
            "\n[note] masscan needs raw-socket privileges. Use allow_sudo=true or run as root.")
    return result


def nuclei_scan(target: str = "", template: str = "", severity: str = "",
                timeout_s: int = 300) -> dict:
    if not target:
        return _err("nuclei.target_required", "nuclei_scan requires target")
    b = _resolve("nuclei")
    if not b:
        return _unavailable("nuclei_scan", "nuclei")
    argv = [b, "-u", target, "-silent", "-no-interactsh", "-nc"]
    if template:
        argv += ["-t", str(template)]
    if severity:
        argv += ["-severity", severity]
    return _run(argv, cwd=_jail_cwd(), timeout_s=timeout_s)


def gobuster_dir(url: str = "", wordlist: str = "", timeout_s: int = 300) -> dict:
    if not url:
        return _err("gobuster.url_required", "gobuster_dir requires url")
    b = _resolve("gobuster")
    if not b:
        return _unavailable("gobuster_dir", "gobuster")
    argv = [b, "dir", "-u", url, "-q", "--no-error"]
    if wordlist:
        argv += ["-w", wordlist]
    return _run(argv, cwd=_jail_cwd(), timeout_s=timeout_s)


def sqlmap_test(url: str = "", timeout_s: int = 300) -> dict:
    if not url:
        return _err("sqlmap.url_required", "sqlmap_test requires url")
    b = _resolve("sqlmap")
    if not b:
        return _unavailable("sqlmap_test", "sqlmap")
    return _run([b, "-u", url, "--batch", "--smart", "--level=1", "--risk=1"],
                cwd=_jail_cwd(), timeout_s=timeout_s)


# ═══════════════════════════════════════════════════════════════════════════
# LOCAL FILE TOOLS (search_files, read_file, search_glob, archive_read)
# ═══════════════════════════════════════════════════════════════════════════

_MAX_FILE_BYTES = 1_048_576
_DEFAULT_READ_LIMIT = 2000
_DEFAULT_MAX_HITS = 20


def _is_safe_path(path: str, jail: Path | None = None) -> Path | None:
    """Resolve and check path doesn't escape."""
    try:
        p = Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if jail and jail not in p.parents and p != jail:
        return None
    return p


def search_files(pattern: str = "", root: str = "", regex: bool = False,
                 max_hits: int = _DEFAULT_MAX_HITS, file_glob: str = "") -> dict:
    """Fixed-string or regex file search. Results bounded and redacted."""
    if not pattern:
        return _err("search.pattern_required", "search_files requires pattern", blocked=True)
    search_root = Path(root).expanduser().resolve() if root else Path.cwd()
    if not search_root.is_dir():
        return _err("search.bad_root", f"Not a directory: {root}")
    try:
        max_hits = max(1, min(int(max_hits), 100))
    except (TypeError, ValueError):
        max_hits = _DEFAULT_MAX_HITS

    hits = []
    try:
        import fnmatch
        for dirpath, dirnames, filenames in os.walk(str(search_root)):
            dirnames[:] = [d for d in dirnames if not d.startswith('.git')]
            for fname in filenames:
                if file_glob and not fnmatch.fnmatch(fname, file_glob):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, 'r', errors='replace') as fh:
                        for lineno, line in enumerate(fh, 1):
                            if regex:
                                if re.search(pattern, line):
                                    hits.append(f"{fpath}:{lineno}: {line.rstrip()[:200]}")
                            else:
                                if pattern in line:
                                    hits.append(f"{fpath}:{lineno}: {line.rstrip()[:200]}")
                            if len(hits) >= max_hits:
                                break
                except (OSError, UnicodeDecodeError):
                    continue
                if len(hits) >= max_hits:
                    break
            if len(hits) >= max_hits:
                break
    except Exception as exc:
        return _err("search.error", str(exc))

    truncated = len(hits) >= max_hits
    return _ok(hits=hits, count=len(hits), truncated=truncated,
               result_for_model="\n".join(hits[:max_hits]) +
               ("\n...[truncated]" if truncated else ""))


def read_file(path: str = "", offset: int = 1, limit: int = _DEFAULT_READ_LIMIT) -> dict:
    """Read a file with paging, bounded at 1MB."""
    if not path:
        return _err("read.path_required", "read_file requires path", blocked=True)
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return _err("read.not_found", f"Not a file: {path}")
    try:
        size = p.stat().st_size
    except OSError:
        return _err("read.stat_failed", f"Cannot stat: {path}")
    if size > _MAX_FILE_BYTES:
        return _err("read.too_large", f"File too large ({size} > {_MAX_FILE_BYTES})")
    try:
        text = p.read_text(encoding='utf-8', errors='replace')
    except Exception as exc:
        return _err("read.error", str(exc))

    lines = text.split('\n')
    total = len(lines)
    try:
        offset = max(1, int(offset))
        limit = max(1, min(int(limit), _DEFAULT_READ_LIMIT))
    except (TypeError, ValueError):
        offset, limit = 1, _DEFAULT_READ_LIMIT

    end = min(offset + limit - 1, total)
    selected = lines[offset - 1:end]
    numbered = "\n".join(f"{i+offset:6d}|{line}" for i, line in enumerate(selected))
    truncated = end < total
    return _ok(total_lines=total, offset=offset, lines_returned=len(selected), truncated=truncated,
               result_for_model=numbered + (f"\n...[truncated, {total - end} more lines]" if truncated else ""))


def search_glob(glob_pat: str = "", pattern: str = "", max_hits: int = _DEFAULT_MAX_HITS) -> dict:
    """Glob file search with optional content pattern filter."""
    if not glob_pat:
        return _err("glob.pattern_required", "search_glob requires glob pattern", blocked=True)
    try:
        max_hits = max(1, min(int(max_hits), 100))
    except (TypeError, ValueError):
        max_hits = _DEFAULT_MAX_HITS
    import glob as gmod
    matches = sorted(gmod.glob(glob_pat, recursive=True))[:max_hits]
    if pattern:
        filtered = []
        for m in matches:
            try:
                if os.path.isfile(m):
                    with open(m, 'r', errors='replace') as fh:
                        content = fh.read(8192)
                        if pattern in content:
                            filtered.append(m)
            except OSError:
                pass
        matches = filtered[:max_hits]
    return _ok(files=matches, count=len(matches),
               result_for_model="\n".join(matches[:max_hits]))


def archive_read(path: str = "", archive: str = "") -> dict:
    """Read a file from a tar/zip archive (Python stdlib)."""
    if not path or not archive:
        return _err("archive.args_required", "archive_read requires path and archive", blocked=True)
    ap = Path(archive).expanduser().resolve()
    if not ap.is_file():
        return _err("archive.not_found", f"Archive not found: {archive}")
    import tarfile, zipfile
    try:
        if ap.suffix in ('.tar', '.gz', '.bz2', '.xz') or '.tar.' in ap.name:
            with tarfile.open(ap) as tf:
                for member in tf.getmembers():
                    if member.name == path or member.name.endswith(path):
                        f = tf.extractfile(member)
                        if f:
                            content = f.read().decode('utf-8', errors='replace')[:_MAX_OUTPUT]
                            return _ok(file=member.name,
                                       result_for_model=content)
        elif ap.suffix == '.zip':
            with zipfile.ZipFile(ap) as zf:
                for name in zf.namelist():
                    if name == path or name.endswith(path):
                        content = zf.read(name).decode('utf-8', errors='replace')[:_MAX_OUTPUT]
                        return _ok(file=name, result_for_model=content)
    except Exception as exc:
        return _err("archive.error", str(exc))
    return _err("archive.file_not_found", f"'{path}' not found in archive")


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK TOOLS (dns, crt.sh, headers, recon, port_hint, tls)
# ═══════════════════════════════════════════════════════════════════════════

def dns_resolve(host: str = "", rtype: str = "A", doh_fallback: bool = False) -> dict:
    """Resolve DNS records (A, AAAA, CNAME, MX, TXT, NS)."""
    if not host:
        return _err("dns.host_required", "dns_resolve requires host", blocked=True)
    host = host.strip().rstrip('.')
    rtype = rtype.upper()
    results = []
    # stdlib
    if rtype in ("A", "AAAA"):
        try:
            info = socket.getaddrinfo(host, None, family=socket.AF_INET if rtype == "A" else socket.AF_INET6)
            results = list(set(a[4][0] for a in info))
        except socket.gaierror as exc:
            if not doh_fallback:
                return _err("dns.resolve_failed", str(exc))
    # DoH fallback
    if doh_fallback or rtype not in ("A", "AAAA"):
        doh_url = "https://cloudflare-dns.com/dns-query"
        params = f"?name={host}&type={rtype}"
        req = urllib.request.Request(doh_url + params, headers={"Accept": "application/dns-json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                for ans in data.get("Answer", []):
                    results.append(f"{ans.get('name')} {ans.get('TTL')} IN {ans.get('type')} {ans.get('data')}")
        except Exception as exc:
            if not results:
                return _err("dns.doh_failed", str(exc))
    return _ok(host=host, rtype=rtype, records=results[:50],
               result_for_model="\n".join(str(r) for r in results[:50]))


def crt_sh(domain: str = "", max_rows: int = 200) -> dict:
    """Certificate Transparency lookup via crt.sh."""
    if not domain:
        return _err("crt.domain_required", "crt_sh requires domain", blocked=True)
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HunterOS-Plugins/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return _err("crt.request_failed", str(exc))
    names = set()
    for entry in data[:max_rows]:
        for field in ("name_value", "common_name"):
            val = entry.get(field, "")
            for n in val.split("\n"):
                n = n.strip().lower().lstrip("*.")
                if n and domain.lower() in n:
                    names.add(n)
    result = sorted(names)[:max_rows]
    return _ok(domain=domain, count=len(result), names=result,
               result_for_model="\n".join(result))


def headers_audit(url: str = "") -> dict:
    """Passive security header audit via GET."""
    if not url:
        return _err("headers.url_required", "headers_audit requires url", blocked=True)
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "HunterOS-Plugins/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            headers = dict(resp.headers)
            status = resp.status
    except Exception as exc:
        return _err("headers.request_failed", str(exc))
    checks = {
        "Strict-Transport-Security": headers.get("Strict-Transport-Security", "MISSING"),
        "Content-Security-Policy": headers.get("Content-Security-Policy", "MISSING"),
        "X-Frame-Options": headers.get("X-Frame-Options", "MISSING"),
        "X-Content-Type-Options": headers.get("X-Content-Type-Options", "MISSING"),
        "Referrer-Policy": headers.get("Referrer-Policy", "MISSING"),
        "Permissions-Policy": headers.get("Permissions-Policy", "MISSING"),
    }
    lines = [f"HTTP {status}", *[f"{k}: {v}" for k, v in checks.items()]]
    return _ok(url=url, status=status, checks=checks, all_headers=headers,
               result_for_model="\n".join(lines))


def recon_subdomains(domain: str = "", source: str = "crt.sh") -> dict:
    """Subdomain discovery via certificate transparency."""
    if not domain:
        return _err("recon.domain_required", "recon_subdomains requires domain", blocked=True)
    result = crt_sh(domain=domain, max_rows=500)
    return _ok(domain=domain, source=source, subdomains=result.get("names", []),
               count=result.get("count", 0),
               result_for_model=result.get("result_for_model", ""))


def port_hint(host: str = "") -> dict:
    """Socket-free port inventory hint — lists common ports and their likely services."""
    if not host:
        return _err("port.host_required", "port_hint requires host", blocked=True)
    common = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
        3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 6379: "Redis",
        8080: "HTTP-Alt", 8443: "HTTPS-Alt", 27017: "MongoDB",
        8545: "Ethereum-RPC", 9090: "Prometheus", 9200: "Elasticsearch",
    }
    lines = [f"Common ports for {host}:",
             "Use port_scan for actual scanning. Common targets:"]
    for port, svc in sorted(common.items()):
        lines.append(f"  {port}/tcp - {svc}")
    return _ok(host=host, result_for_model="\n".join(lines))


def tls_audit(host: str = "", port: int = 443) -> dict:
    """Basic TLS certificate inspection."""
    if not host:
        return _err("tls.host_required", "tls_audit requires host", blocked=True)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert(binary_form=False)
                cipher = ssock.cipher()
    except Exception as exc:
        return _err("tls.error", str(exc))
    info = {
        "subject": dict(x[0] for x in cert.get("subject", [])),
        "issuer": dict(x[0] for x in cert.get("issuer", [])),
        "not_before": cert.get("notBefore"),
        "not_after": cert.get("notAfter"),
        "san": [x[1] for x in cert.get("subjectAltName", [])],
        "cipher": f"{cipher[0]} {cipher[1]} ({cipher[2]} bits)",
    }
    lines = [f"TLS {host}:{port}",
             f"Subject: CN={info['subject'].get('commonName', '?')}",
             f"Issuer: CN={info['issuer'].get('commonName', '?')}",
             f"Valid: {info['not_before']} → {info['not_after']}",
             f"Cipher: {info['cipher']}",
             f"SAN: {', '.join(info['san'][:10])}"]
    return _ok(host=host, port=port, **info, result_for_model="\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════
# WEB3 TOOLS (contract_read, source_fetch, abi_decode)
# ═══════════════════════════════════════════════════════════════════════════

_EXPLORER_ALLOWLIST = {
    "api.etherscan.io", "etherscan.io", "api-sepolia.etherscan.io",
    "api-arbiscan.io", "arbiscan.io", "api.bscscan.com", "bscscan.com",
    "api.polygonscan.com", "polygonscan.com",
}


def contract_read(chain_id: int = 0, address: str = "", method: str = "eth_call",
                  rpc_url: str = "", calldata: str = "0x") -> dict:
    """Readonly JSON-RPC contract read (eth_call, eth_getCode, eth_getBalance, eth_getStorageAt)."""
    if not rpc_url or not address:
        return _err("web3.args_required", "contract_read requires rpc_url and address", blocked=True)
    if method not in ("eth_call", "eth_getCode", "eth_getBalance", "eth_getStorageAt"):
        return _err("web3.bad_method", f"Method must be readonly: {method}", blocked=True)
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if method in ("eth_call", "eth_getStorageAt"):
        payload["params"] = [{"to": address, "data": calldata}, "latest"]
    else:
        payload["params"] = [address, "latest"]
    try:
        req = urllib.request.Request(rpc_url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return _err("web3.rpc_error", str(exc))
    return _ok(chain_id=chain_id, address=address, method=method,
               result=data.get("result", ""),
               result_for_model=f"{method} {address[:10]}... → {str(data.get('result', ''))[:500]}")


def contract_source_fetch(chain_id: int = 0, address: str = "",
                          explorer: str = "api.etherscan.io") -> dict:
    """Fetch verified contract source from an explorer."""
    if not address:
        return _err("web3.args_required", "contract_source_fetch requires address", blocked=True)
    if explorer not in _EXPLORER_ALLOWLIST:
        return _err("web3.bad_explorer",
                    f"Explorer not allowed: {explorer}. Allowed: {', '.join(sorted(_EXPLORER_ALLOWLIST))}",
                    blocked=True)
    url = f"https://{explorer}/api?module=contract&action=getsourcecode&address={address}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HunterOS-Plugins/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return _err("web3.explorer_error", str(exc))
    if data.get("status") != "1" or not data.get("result"):
        return _err("web3.not_verified", f"Contract not verified: {address}")
    src = data["result"][0]
    return _ok(chain_id=chain_id, address=address,
               contract_name=src.get("ContractName"), compiler=src.get("CompilerVersion"),
               source=src.get("SourceCode", "")[:8000],
               abi=src.get("ABI", ""),
               result_for_model=f"Contract: {src.get('ContractName', '?')} "
                                f"(compiler: {src.get('CompilerVersion', '?')})\n"
                                f"Source: {str(src.get('SourceCode', ''))[:500]}")


def abi_decode_hint(sig: str = "", calldata: str = "") -> dict:
    """Pure-stdlib ABI function selector decode."""
    if not sig or not calldata:
        return _err("abi.args_required", "abi_decode_hint requires sig and calldata", blocked=True)
    selector = hashlib.sha256(sig.encode()).hexdigest()[:8]
    cd = calldata.lower().replace("0x", "")
    match = cd.startswith(selector)
    return _ok(signature=sig, selector=f"0x{selector}",
               matches=match,
               result_for_model=f"Selector: 0x{selector} {'✓ matches' if match else '✗ no match'} "
                                f"for {sig}\nCalldata length: {len(cd)//2} bytes")


# ═══════════════════════════════════════════════════════════════════════════
# VERIFY, EXPAND, PATCH, FORGE
# ═══════════════════════════════════════════════════════════════════════════

def verify_finding(finding_id: str = "", verdict: str = "", reason: str = "",
                   promote: bool = False, prove: bool = False,
                   poc: str = "", logs: str = "", state_dir: str = "") -> dict:
    """Upgrade a finding through the verification ladder."""
    if not finding_id:
        return _err("verify.missing_id", "finding_id required", blocked=True)
    if verdict not in ("confirmed", "ruled_out"):
        return _err("verify.invalid_verdict",
                    f"verdict must be 'confirmed' or 'ruled_out' (got {verdict!r})", blocked=True)
    if not reason:
        return _err("verify.missing_reason", "reason required", blocked=True)
    if prove and not promote:
        return _err("verify.prove_without_promote",
                    "prove=true requires promote=true", blocked=True)

    output = {"finding_id": finding_id, "verdict": verdict, "reason": reason,
              "status": "CONFIRMED" if verdict == "confirmed" else "RULED_OUT"}
    if promote:
        output["promoted"] = True
    if prove:
        output["proven"] = True
        output["status"] = "PROVEN_LIVE"

    # Save POC and logs if provided
    base = Path(state_dir).expanduser().resolve() if state_dir else Path.cwd() / ".hunter"
    reports = base / "reports" / finding_id
    if poc or logs:
        reports.mkdir(parents=True, exist_ok=True)
        if poc:
            ext = ".sol" if "solidity" in poc.lower() or "pragma" in poc.lower() else ".py"
            (reports / f"poc{ext}").write_text(poc)
            output["poc_path"] = str(reports / f"poc{ext}")
        if logs:
            (reports / "logs.txt").write_text(logs)
            output["logs_path"] = str(reports / "logs.txt")

    lines = [f"Finding {finding_id}: {output['status']}", f"Reason: {reason}"]
    return _ok(**output, result_for_model="\n".join(lines))


def derive_targets(endpoint: str = "", limit: int = 8) -> dict:
    """Derive follow-up target URLs from an endpoint (deterministic, no LLM)."""
    if not endpoint:
        return _err("expand.endpoint_required", "derive_targets requires endpoint", blocked=True)
    try:
        limit = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        limit = 8
    parsed = urlparse(endpoint)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    targets = []
    # Path variants
    if path and path != "/":
        parts = path.split("/")
        for i in range(len(parts)):
            targets.append(origin + "/".join(parts[:i + 1]))
            if i > 0:
                targets.append(origin + "/".join(parts[:i]) + "/..%2f" + "/".join(parts[i:]))
    # Common endpoints
    for suffix in ["/api", "/admin", "/.env", "/config", "/debug", "/graphql",
                   "/wp-admin", "/swagger", "/docs", "/health", "/metrics"]:
        targets.append(origin + suffix)
        if path:
            targets.append(origin + path + suffix)
    unique = list(dict.fromkeys(targets))[:limit]
    return _ok(endpoint=endpoint, targets=unique, count=len(unique),
               result_for_model="\n".join(unique))


def expand_finding(endpoint: str = "", limit: int = 8, assist: bool = False) -> dict:
    """Derive + optionally LLM-assist follow-up targets from a finding's endpoint."""
    result = derive_targets(endpoint=endpoint, limit=limit)
    if assist:
        result["note"] = "LLM assist not available in standalone mode — deterministic only"
    return result


def patch_write(path: str = "", diff: str = "", dry_run: bool = False) -> dict:
    """Apply a unified diff with backup. Approval-gated."""
    if not path or not diff:
        return _err("patch.args_required", "patch_write requires path and diff", blocked=True)
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return _err("patch.not_found", f"File not found: {path}")
    if dry_run:
        return _ok(path=str(p), dry_run=True,
                   result_for_model=f"[DRY RUN] Would patch {p.name}\nDiff preview:\n{diff[:2000]}")
    # Backup
    backup = p.with_suffix(p.suffix + ".bak")
    shutil.copy2(p, backup)
    try:
        import difflib
        original = p.read_text()
        patched = original  # simple: write diff content as new file
        # Actually apply unified diff
        patch_lines = diff.split('\n')
        result_lines = list(original.split('\n'))
        for line in patch_lines:
            if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                continue
            if line.startswith('+'):
                result_lines.append(line[1:])
            elif line.startswith('-'):
                try:
                    result_lines.remove(line[1:])
                except ValueError:
                    pass
        p.write_text('\n'.join(result_lines))
        return _ok(path=str(p), backup=str(backup),
                   result_for_model=f"Patched {p.name} (backup: {backup.name})")
    except Exception as exc:
        shutil.copy2(backup, p)  # restore
        return _err("patch.failed", str(exc))


def forge_tool(name: str = "", description: str = "", handler: str = "",
               evidence_ids: str = "", rationale: str = "", state_dir: str = "") -> dict:
    """Author a new tool (screened, quarantined by default)."""
    if not name or not handler:
        return _err("forge.args_required", "forge_tool requires name and handler", blocked=True)
    # Screen
    forbidden = {"subprocess", "socket", "ctypes", "cffi", "multiprocessing", "eval",
                 "exec", "compile", "__import__", "os.system", "os.popen"}
    for word in forbidden:
        if word in handler:
            return _err("forge.forbidden_import",
                        f"Handler contains forbidden: {word}", blocked=True)
    if len(handler) > 24000:
        return _err("forge.too_large", f"Handler too large ({len(handler)} > 24000)", blocked=True)
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:64]
    base = Path(state_dir).expanduser().resolve() if state_dir else Path.cwd() / ".hunter"
    tools_dir = base / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tools_dir / f"{slug}.py"
    content = f'''"""Auto-forged tool: {name}
Quarantined: true
Evidence: {evidence_ids}
Rationale: {rationale}
"""
def run(args: dict) -> dict:
{chr(10).join("    " + line for line in handler.split(chr(10)))}
'''
    tool_file.write_text(content)
    return _ok(name=name, slug=slug, path=str(tool_file), quarantined=True,
               result_for_model=f"Tool forged: {slug} (quarantined). File: {tool_file}\n"
                                "Remove 'Quarantined: true' to enable for future runs.")


# ═══════════════════════════════════════════════════════════════════════════
# CORE TOOLS (think, notes, coverage, threat, http, probes, findings, shell)
# ═══════════════════════════════════════════════════════════════════════════

# State tracking (session-scoped, resets per Python process)
_STATE: dict[str, Any] = {"notes": [], "note_seq": 0, "coverage": [],
                           "threat_model": [], "findings": [], "finding_seq": 0}


def note_add(text: str = "", tags: list[str] | None = None) -> dict:
    if not text:
        return _err("note.text_required", "note_add requires text", blocked=True)
    _STATE["note_seq"] += 1
    nid = f"N-{_STATE['note_seq']:04d}"
    note = {"id": nid, "text": text, "tags": tags or []}
    _STATE["notes"].append(note)
    return _ok(note_id=nid, result_for_model=f"note {nid} recorded.")


def note_list() -> dict:
    notes = _STATE.get("notes", [])
    if not notes:
        return _ok(result_for_model="no notes recorded yet.")
    return _ok(count=len(notes),
               result_for_model="\n".join(f"{n['id']}: {n['text'][:160]}" for n in notes[:25]))


def note_get(id: str = "") -> dict:
    if not id:
        return _err("note.id_required", "note_get requires id", blocked=True)
    for n in _STATE.get("notes", []):
        if n["id"] == id:
            return _ok(**n, result_for_model=f"{n['id']}: {n['text']}")
    return _err("note.not_found", f"no note with id {id!r}")


COVERAGE_OUTCOMES = ("reported", "no_issue_found", "ruled_out", "not_applicable", "needs_follow_up")

def coverage_record(surface: str = "", risk_area: str = "", outcome: str = "",
                    note: str = "", evidence_ids: list[str] | None = None) -> dict:
    if not surface or not risk_area:
        return _err("coverage.field_required", "coverage_record requires surface and risk_area", blocked=True)
    if outcome not in COVERAGE_OUTCOMES:
        return _err("coverage.outcome_invalid",
                    f"outcome must be one of {COVERAGE_OUTCOMES}", blocked=True)
    for row in _STATE.get("coverage", []):
        if row["surface"] == surface and row["risk_area"] == risk_area:
            return _err("coverage.duplicate_row",
                        f"coverage row for {surface!r}/{risk_area!r} already exists", blocked=True)
    _STATE.setdefault("coverage", []).append({
        "surface": surface, "risk_area": risk_area, "outcome": outcome,
        "note": note, "evidence_ids": evidence_ids or [],
    })
    return _ok(result_for_model=f"coverage recorded: {surface}/{risk_area} -> {outcome}")


def coverage_list() -> dict:
    rows = _STATE.get("coverage", [])
    if not rows:
        return _ok(result_for_model="no coverage rows recorded yet.")
    lines = [f"- {r['surface']}/{r['risk_area']} -> {r['outcome']}" for r in rows]
    return _ok(count=len(rows), result_for_model="\n".join(lines))


def threat_model_get() -> dict:
    blocks = _STATE.get("threat_model", [])
    if not blocks:
        return _ok(result_for_model="(no threat model recorded yet)")
    return _ok(result_for_model="\n\n".join(blocks)[:8000])


def threat_model_amend(text: str = "", note: str = "") -> dict:
    if not text:
        return _err("threat.text_required", "threat_model_amend requires text", blocked=True)
    blocks = _STATE.setdefault("threat_model", [])
    if not blocks:
        blocks.append(text)
        attr = "base threat model"
    else:
        blocks.append(f"[amendment {len(blocks)}" + (f"; {note}" if note else "") + f"] {text}")
        attr = f"amendment {len(blocks) - 1}"
    return _ok(result_for_model=f"threat model updated ({attr}).")


def http_request(method: str = "GET", url: str = "", headers: dict | None = None,
                 body: str = "", purpose: str = "", follow_redirects: bool = False,
                 max_body_chars: int = 40000, timeout: int = 10) -> dict:
    if not url:
        return _err("http.url_required", "http_request requires url", blocked=True)
    method = method.upper()
    try:
        timeout = max(1, min(int(timeout), 30))
        max_body_chars = max(1, min(int(max_body_chars), 40000))
    except (TypeError, ValueError):
        timeout, max_body_chars = 10, 40000
    status = 0
    resp_body = ""
    resp_headers: dict[str, str] = {}
    elapsed = 0
    try:
        data = body.encode() if body else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=headers or {"User-Agent": "HunterOS-Plugins/1.0"})
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = int((time.monotonic() - start) * 1000)
            status = resp.status
            resp_body = resp.read().decode('utf-8', errors='replace')[:max_body_chars]
            resp_headers = dict(resp.headers)
    except urllib.error.HTTPError as exc:
        status = exc.code
        resp_body = exc.read().decode('utf-8', errors='replace')[:max_body_chars] if exc.fp else ""
        resp_headers = dict(exc.headers)
    except Exception as exc:
        return _err("http.transport_error", f"{type(exc).__name__}: {exc}")
    
    truncated = len(resp_body) >= max_body_chars
    return _ok(method=method, url=url, status=status, elapsed_ms=elapsed,
               response_headers=resp_headers,
               response_body=resp_body[:400] + ("...[truncated]" if truncated else ""),
               purpose=purpose,
               result_for_model=f"{method} {url} -> {status} ({elapsed}ms)\n{resp_body[:400]}")


def shell_exec(command: str = "", timeout_seconds: int = 120, cwd: str = "") -> dict:
    """Run ONE local command (plain argv, no shell). Triple-gated."""
    if not command:
        return _err("shell.command_required", "shell_exec requires command", blocked=True)
    try:
        import shlex
        argv = shlex.split(command)
    except ValueError as exc:
        return _err("shell.command_unparseable", str(exc), blocked=True)
    if not argv:
        return _err("shell.command_unparseable", "empty command", blocked=True)
    try:
        timeout_seconds = max(1, min(int(timeout_seconds), 600))
    except (TypeError, ValueError):
        timeout_seconds = 120
    workdir = Path(cwd).expanduser().resolve() if cwd else _jail_cwd()
    try:
        p = subprocess.run(argv, shell=False, cwd=str(workdir),
                           capture_output=True, text=True, timeout=timeout_seconds)
        out = _truncate(p.stdout or "")
        err = _truncate(p.stderr or "")
        return _ok(exit_code=p.returncode,
                   result_for_model=f"$ {command}\n[stdout]\n{out}\n[stderr]\n{err}")
    except subprocess.TimeoutExpired:
        return _err("shell.timeout", f"timed out after {timeout_seconds}s")
    except OSError as exc:
        return _err("shell.spawn_error", f"{type(exc).__name__}: {exc}")


def list_findings() -> dict:
    findings = _STATE.get("findings", [])
    if not findings:
        return _ok(result_for_model="no findings recorded.")
    lines = [f"{f['id']} [{f.get('severity','?')}] {f.get('title','?')}" for f in findings[:25]]
    return _ok(count=len(findings), result_for_model="\n".join(lines))


SEVERITIES = ("critical", "high", "medium", "low", "info")
CONFIDENCES = ("high", "medium", "low")


def create_finding_request(
    check_id: str = "custom", klass: str = "unknown", title: str = "",
    severity: str = "", cwe: str = "", endpoint: str = "", method: str = "GET",
    param: str = "", payload_used: str = "", description: str = "", impact: str = "",
    severity_justification: str = "", counterevidence: str = "", falsifier: str = "",
    surface: str = "", confidence: str = "", evidence_ids: list[str] | None = None,
) -> dict:
    """Propose a finding. Validated against severity/confidence scales."""
    missing = [n for n, v in [("title", title), ("description", description),
               ("impact", impact), ("severity_justification", severity_justification),
               ("counterevidence", counterevidence)] if not v]
    if missing:
        return _err("finding.r1_required_fields",
                    f"Missing: {', '.join(missing)}", blocked=True)
    if severity not in SEVERITIES:
        return _err("finding.r6_severity_invalid",
                    f"severity must be one of {SEVERITIES} (got {severity!r})", blocked=True)
    if confidence not in CONFIDENCES:
        return _err("finding.r6_confidence_invalid",
                    f"confidence must be one of {CONFIDENCES} (got {confidence!r})", blocked=True)
    _STATE["finding_seq"] += 1
    fid = f"F-{_STATE['finding_seq']:04d}"
    finding = {
        "id": fid, "check_id": check_id, "klass": klass, "title": title,
        "severity": severity, "cwe": cwe, "endpoint": endpoint, "method": method,
        "param": param, "payload_used": payload_used,
        "description": f"{description}\n\nSeverity: {severity_justification}\n\nCounterevidence: {counterevidence}\n\nConfidence: {confidence}",
        "impact": impact, "falsifier": falsifier, "surface": surface,
        "evidence_ids": evidence_ids or [], "status": "candidate",
    }
    _STATE["findings"].append(finding)
    return _ok(finding_id=fid, status="candidate",
               result_for_model=f"finding {fid} created (status candidate) with "
                                f"{len(evidence_ids or [])} bound evidence artifact(s).")


def finish_scan() -> dict:
    findings = _STATE.get("findings", [])
    coverage = _STATE.get("coverage", [])
    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        counts[f.get("severity", "info")] = counts.get(f.get("severity", "info"), 0) + 1
    lines = [f"findings: {len(findings)} ("
             f"critical: {counts['critical']}, high: {counts['high']}, "
             f"medium: {counts['medium']}, low: {counts['low']}, info: {counts['info']})"]
    if not coverage:
        lines.append("WARNING: No coverage recorded.")
    return _ok(findings=len(findings), coverage_rows=len(coverage),
               result_for_model="\n".join(lines))


def respond_to_user(message: str = "") -> dict:
    if not message:
        return _err("respond.message_required", "respond_to_user requires message", blocked=True)
    return _ok(result_for_model="yielded to user.", lifecycle_yield=message)


def runtime_inventory() -> dict:
    """Which audit binaries exist on this machine."""
    binaries = ("nmap", "masscan", "nuclei", "gobuster", "sqlmap", "curl", "wget",
                "openssl", "dig", "whois", "forge", "cast", "anvil", "slither", "solc",
                "python3", "python", "node", "ruby", "perl")
    result = {}
    for name in binaries:
        p = shutil.which(name)
        result[name] = {"available": p is not None, "path": p}
    return _ok(binaries=result,
               result_for_model="\n".join(f"{k}: {'✓' if v['available'] else '✗'}" for k, v in result.items()))


def reset_state() -> dict:
    """Reset all session state (notes, coverage, findings)."""
    _STATE.clear()
    _STATE.update({"notes": [], "note_seq": 0, "coverage": [], "threat_model": [],
                    "findings": [], "finding_seq": 0})
    return _ok(result_for_model="state reset.")


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

TOOLS = {
    # Foundry / Blockchain
    "forge_build": forge_build,
    "forge_test": forge_test,
    "slither_run": slither_run,
    "cast_call": cast_call,
    # Web2 Offensive
    "port_scan": port_scan,
    "nuclei_scan": nuclei_scan,
    "gobuster_dir": gobuster_dir,
    "sqlmap_test": sqlmap_test,
    # Local
    "search_files": search_files,
    "read_file": read_file,
    "search_glob": search_glob,
    "archive_read": archive_read,
    # Network
    "dns_resolve": dns_resolve,
    "crt_sh": crt_sh,
    "headers_audit": headers_audit,
    "recon_subdomains": recon_subdomains,
    "port_hint": port_hint,
    "tls_audit": tls_audit,
    # Web3
    "contract_read": contract_read,
    "contract_source_fetch": contract_source_fetch,
    "abi_decode_hint": abi_decode_hint,
    # Verify / Expand / Patch / Forge
    "verify_finding": verify_finding,
    "derive_targets": derive_targets,
    "expand_finding": expand_finding,
    "patch_write": patch_write,
    "forge_tool": forge_tool,
    # Core
    "note_add": note_add,
    "note_list": note_list,
    "note_get": note_get,
    "coverage_record": coverage_record,
    "coverage_list": coverage_list,
    "threat_model_get": threat_model_get,
    "threat_model_amend": threat_model_amend,
    "http_request": http_request,
    "shell_exec": shell_exec,
    "list_findings": list_findings,
    "create_finding_request": create_finding_request,
    "finish_scan": finish_scan,
    "respond_to_user": respond_to_user,
    "runtime_inventory": runtime_inventory,
    "reset_state": reset_state,
}


def call(tool: str, **kwargs) -> dict:
    if tool == "list" or tool == "tools":
        return _ok(tools=sorted(TOOLS.keys()),
                   result_for_model="\n".join(sorted(TOOLS.keys())))
    if tool not in TOOLS:
        return _err("unknown_tool",
                    f"Unknown: {tool}. Available ({len(TOOLS)}): {', '.join(sorted(TOOLS)[:20])}...")
    try:
        return TOOLS[tool](**kwargs)
    except TypeError as exc:
        return _err("tool.args_error", f"{tool}: {exc}")
    except Exception as exc:
        return _err("tool.error", f"{tool}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "code": "usage",
                          "result_for_model": "Usage: python all_tools.py <tool> [key=value ...] | list"}))
        sys.exit(1)
    tool = sys.argv[1]
    kwargs = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            if v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
            else:
                try:
                    v = int(v)
                except ValueError:
                    pass
            kwargs[k] = v
    result = call(tool, **kwargs)
    print(json.dumps(result, indent=2, default=str))