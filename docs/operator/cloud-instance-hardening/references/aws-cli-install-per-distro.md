# AWS CLI Installation — Per-Distro Matrix

## Quick Reference

| OS Family | Distro | Package Manager | Package Name | Notes |
|-----------|--------|-----------------|--------------|-------|
| **RHEL-based** | Amazon Linux 2/2023 | dnf/yum | `awscli` | Available in default repos |
| | RHEL 8/9 | dnf | `awscli` | Enable EPEL: `dnf install -y epel-release` |
| | CentOS Stream 8/9 | dnf | `awscli` | Enable EPEL |
| | Fedora | dnf | `awscli` | In default repos |
| | **TencentOS Server** | dnf | **NOT AVAILABLE** | Use pip3 (see below) |
| | AlmaLinux / Rocky | dnf | `awscli` | Enable EPEL |
| **Debian-based** | Ubuntu 20.04+ | apt | `awscli` | In universe repo |
| | Debian 11+ | apt | `awscli` | In main repo |
| | Linux Mint | apt | `awscli` | Ubuntu-based |
| **Alpine** | Alpine 3.15+ | apk | `aws-cli` | In community repo |
| **Arch** | Arch / Manjaro | pacman | `aws-cli-v2` | AUR: `aws-cli-v2-bin` |
| **SUSE** | openSUSE Leap/Tumbleweed | zypper | `aws-cli` | In default repos |

---

## Universal Install Methods (When Package Missing)

### Method 1: pip3 (Recommended for RHEL-based without package)
```bash
# Ensure pip3 installed
dnf install -y python3-pip  # or yum/apt/apk

# Install/upgrade AWS CLI v1 (Python-based)
pip3 install --upgrade awscli

# Verify
aws --version
# aws-cli/1.x.x Python/3.x.x Linux/x.x.x botocore/1.x.x
```

**Pros**: Works everywhere with Python 3.7+
**Cons**: v1 only (v2 not on PyPI), slower startup

### Method 2: Official AWS CLI v2 Binary (Linux x86_64)
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
# Installs to /usr/local/aws-cli, symlink in /usr/local/bin/aws
```

### Method 3: Official AWS CLI v2 Binary (Linux ARM64 / Graviton)
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### Method 4: Homebrew (macOS / Linux)
```bash
brew install awscli
```

### Method 5: Chocolatey (Windows)
```powershell
choco install awscli
```

### Method 6: MSI Installer (Windows)
Download: https://awscli.amazonaws.com/AWSCLIV2.msi

---

## Version Pinning (Production)

```bash
# Pin to specific version via pip
pip3 install awscli==1.45.52

# Pin via binary installer (v2)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-2.15.0.zip" -o "awscliv2.zip"
# Version in URL: 2.15.0
```

**Check latest versions**:
- v1 (PyPI): `pip index versions awscli`
- v2 (GitHub): https://github.com/aws/aws-cli/tags

---

## Virtualenv Best Practice (Isolated Environments)

```bash
# Create dedicated venv
python3 -m venv ~/.aws-cli-venv
source ~/.aws-cli-venv/bin/activate
pip install --upgrade pip awscli

# Add to PATH permanently
echo 'export PATH="$HOME/.aws-cli-venv/bin:$PATH"' >> ~/.bashrc
```

**Why**: Avoids system Python conflicts, easy cleanup, reproducible versions.

---

## Verification & Troubleshooting

```bash
# Check version
aws --version

# Check install location
which aws
ls -la $(which aws)

# Test credentials
aws sts get-caller-identity

# Common error: "aws: command not found"
# → PATH issue. Check /usr/local/bin in PATH, or source ~/.bashrc

# Common error: "Unable to locate credentials"
# → Run `aws configure` or attach IAM instance profile

# Common error: "Exec format error" on ARM64
# → Downloaded x86_64 binary on ARM. Use aarch64 URL.
```

---

## TencentOS Server Specific (This Session)

```bash
# TencentOS Server 4 (RHEL-based) — dnf has NO awscli package
# Solution: pip3 install
dnf install -y python3-pip
pip3 install --upgrade awscli

# Verified working: aws-cli/1.45.52 Python/3.11.6
```

---

## Container Images (Docker)

```dockerfile
# Amazon Linux 2023 (includes awscli v2)
FROM public.ecr.aws/amazonlinux/amazonlinux:2023

# Ubuntu (install via apt)
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y awscli && rm -rf /var/lib/apt/lists/*

# Alpine (minimal)
FROM alpine:3.19
RUN apk add --no-cache aws-cli

# Multi-arch (x86_64 + ARM64) — use official AWS image
FROM public.ecr.aws/aws-cli/aws-cli:latest
```

---

## References

- AWS CLI v2 Install Guide: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2-linux.html
- AWS CLI v1 Install Guide: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv1-linux.html
- AWS CLI Release Notes: https://github.com/aws/aws-cli/blob/v2/CHANGELOG.rst
- PyPI awscli: https://pypi.org/project/awscli/