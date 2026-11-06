# Setup & Troubleshooting — Installation Guide

> Known-good install commands and common pitfalls for the exploit toolkit.
> Last verified: 2026-07-19.

## Prerequisites

- Go 1.22+ (required for Go-based tools)
- Python 3.11+ (security packages)
- Node.js (for some npm-based tools)

## Binary Tools

### Foundry
```bash
curl -L https://foundry.paradigm.xyz | bash
~/.foundry/bin/foundryup
# Verified: forge v1.7.1, cast v1.7.1, anvil v1.7.1, chisel v1.7.1
```

### Nuclei (Project Discovery)
```bash
# Get latest release from API
TAG=$(curl -s https://api.github.com/repos/projectdiscovery/nuclei/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
# Download the linux_amd64 ZIP
curl -L -o /tmp/nuclei.zip "https://github.com/projectdiscovery/nuclei/releases/download/${TAG}/nuclei_${TAG[1:]}_linux_amd64.zip"
unzip /tmp/nuclei.zip -d /tmp/
mv /tmp/nuclei /usr/local/bin/
chmod +x /usr/local/bin/nuclei
# Verified: v3.11.0
```

### HTTPX
```bash
curl -L -o /tmp/httpx.zip "https://github.com/projectdiscovery/httpx/releases/latest/download/httpx_1.10.0_linux_amd64.zip"
unzip /tmp/httpx.zip -d /tmp/
mv /tmp/httpx /usr/local/bin/
chmod +x /usr/local/bin/httpx
# Verified: v1.10.0
```

### Subfinder
```bash
# Uses .tar.gz format
curl -L -o /tmp/subfinder.tar.gz "https://github.com/projectdiscovery/subfinder/releases/latest/download/subfinder_2.14.0_linux_amd64.tar.gz"
tar -xzf /tmp/subfinder.tar.gz -C /tmp/
mv /tmp/subfinder /usr/local/bin/
chmod +x /usr/local/bin/subfinder
# Verified: v2.14.0
```

### FFUF
```bash
# Uses .tar.gz format for amd64 (NOT .zip)
curl -L -o /tmp/ffuf.tar.gz "https://github.com/ffuf/ffuf/releases/latest/download/ffuf_2.2.1_linux_amd64.tar.gz"
tar -xzf /tmp/ffuf.tar.gz -C /tmp/
mv /tmp/ffuf /usr/local/bin/
chmod +x /usr/local/bin/ffuf
# Verified: v2.2.1
```

## Python Security Packages

```bash
python3 -m pip install --prefix=/usr \
  scapy beautifulsoup4 lxml web3 py-solc-x \
  eth-abi eth-account pyopenssl paramiko \
  --break-system-packages
```

> **CRITICAL**: Use `--prefix=/usr` not `--target=`. On Debian-based systems, Python's sys.path points to `/usr/lib/python3.11/site-packages/` but pip without `--prefix` installs to `/usr/local/lib/...` which may NOT be in sys.path.

## Verification

```bash
# Binary tools
nuclei -version
httpx -version
subfinder -version
ffuf -version
forge --version
cast --version

# Python packages
python3 -c "import scapy, bs4, lxml, web3, solcx, eth_abi, eth_account, OpenSSL, paramiko; print('All OK')"
```

## Common Pitfalls

### 1. Architecture Mismatch (386 vs amd64)
GitHub API may return `linux_386` binaries by default. **Always verify with `file <binary>`**:
```
Expected: "ELF 64-bit LSB executable, x86-64, version 1 (SYSV)"
Wrong: "ELF 32-bit LSB executable, Intel 80386" → Exec format error
```

### 2. Compressed ELF Files
Some releases deliver gzip/XZ compressed ELF binaries. Fix:
```bash
gunzip -c compressed_binary > binary && chmod +x binary
# or
unxz compressed_binary && chmod +x binary
```

### 3. Script Disguised as Binary
`subfinder` sometimes ships as a shell script wrapper. Check:
```bash
file /usr/local/bin/subfinder
# If says "text, UTF-8" → NOT a binary, need to extract real binary from tar.gz
```

### 4. Python site-packages PATH Mismatch
Symptom: packages install successfully but `import` fails with "No module named".
Fix: use `--prefix=/usr` for pip install.

### 5. GitHub API Download Issues
Using `requests.get()` may get HTML redirect page. Fix:
- Use `stream=True` 
- Add `Accept: application/octet-stream` header
- Verify file magic bytes: ZIP = `PK\x03\x04` (504b0304), ELF = `\x7fELF`

### 6. FFUF Version Flag
FFUF uses `--version` not `-version`. Use:
```bash
ffuf --version
# NOT: ffuf -version (gives "flag provided but not defined: -version")
```
