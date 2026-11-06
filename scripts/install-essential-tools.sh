#!/usr/bin/env bash
# install-essential-tools.sh — 5 non-overlapping essential tools for HUNT-OS
# Runs on Windows (Git Bash / WSL) and Unix. ~10 min total.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅${NC} $1"; }
fail() { echo -e "${RED}❌${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }

echo "=== HUNT-OS Essential Tools Installer ==="
echo ""

# --- Go ---
if command -v go &>/dev/null; then
  ok "go $(go version | awk '{print $3}')"
else
  warn "go not found — installing..."
  if command -v winget &>/dev/null; then
    winget install --source winget GoLang.Go --accept-package-agreements
  elif command -v brew &>/dev/null; then
    brew install go
  else
    fail "Install go manually: https://go.dev/dl/"
    exit 1
  fi
  ok "go installed"
fi

# --- jq ---
if command -v jq &>/dev/null; then
  ok "jq $(jq --version)"
else
  warn "jq not found — installing..."
  if command -v winget &>/dev/null; then
    winget install --source winget jqlang.jq --accept-package-agreements
  elif command -v brew &>/dev/null; then
    brew install jq
  else
    fail "Install jq manually: https://jqlang.github.io/jq/download/"
    exit 1
  fi
  ok "jq installed"
fi

# --- subfinder ---
if command -v subfinder &>/dev/null; then
  ok "subfinder $(subfinder -version 2>&1 | head -1)"
else
  warn "subfinder not found — installing..."
  go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
  ok "subfinder installed"
fi

# --- nuclei ---
if command -v nuclei &>/dev/null; then
  ok "nuclei $(nuclei -version 2>&1 | head -1)"
else
  warn "nuclei not found — installing..."
  go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
  ok "nuclei installed"
fi

# --- httpx ---
if command -v httpx &>/dev/null; then
  ok "httpx $(httpx -version 2>&1 | head -1)"
else
  warn "httpx not found — installing..."
  go install github.com/projectdiscovery/httpx/cmd/httpx@latest
  ok "httpx installed"
fi

# --- paramspider ---
if python3 -c "import paramspider" 2>/dev/null; then
  ok "paramspider (pip)"
else
  warn "paramspider not found — installing..."
  pip install paramspider
  ok "paramspider installed"
fi

echo ""
echo "=== Done ==="
echo "Essential tools: go, jq, subfinder, nuclei, httpx, paramspider"
echo "Web3 (Foundry): cast, forge, anvil, chisel"
echo "See TOOLS.md for full matrix"