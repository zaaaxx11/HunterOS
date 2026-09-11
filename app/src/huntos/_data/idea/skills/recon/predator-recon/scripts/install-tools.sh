#!/bin/bash
# INSTALL TOOLS — Predator Recon Arsenal
# Run once to install all required tools
# SOUL.md: "Complete runnable code, imports + run command + error handling"

set -euo pipefail

log() { echo "[$(date +%H:%M:%S)] $*"; }

# Check Go
if ! command -v go &> /dev/null; then
    log "ERROR: Go not installed. Install from https://golang.org/dl/"
    exit 1
fi

log "Go version: $(go version)"

# Set GOPATH if not set
export GOPATH="${GOPATH:-$HOME/go}"
export PATH="$PATH:$GOPATH/bin"

log "Installing Go tools..."

# ProjectDiscovery tools
tools=(
    "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
    "github.com/projectdiscovery/httpx/cmd/httpx@latest"
    "github.com/projectdiscovery/katana/cmd/katana@latest"
    "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"
    "github.com/projectdiscovery/puredns/v2@latest"
    "github.com/projectdiscovery/dnsx/cmd/dnsx@latest"
    "github.com/projectdiscovery/uncover/cmd/uncover@latest"
    "github.com/projectdiscovery/alterx/cmd/alterx@latest"
    "github.com/projectdiscovery/mapcidr/cmd/mapcidr@latest"
)

# Other Go tools
other_tools=(
    "github.com/tomnomnom/assetfinder@latest"
    "github.com/tomnomnom/anew@latest"
    "github.com/tomnomnom/qsreplace@latest"
    "github.com/tomnomnom/gf@latest"
    "github.com/tomnomnom/hacks/kxss@latest"
    "github.com/tomnomnom/waybackurls@latest"
    "github.com/lc/gau/v2/cmd/gau@latest"
    "github.com/hahwul/dalfox/v2@latest"
    "github.com/Ractiurd/jscracker@latest"
    "github.com/LukaSikic/subzy@latest"
    "github.com/Tanmay-N/CORS-Scanner@latest"
    "github.com/ffuf/ffuf/v2@latest"
    "github.com/owasp-amass/amass/v3/...@master"
)

# Install ProjectDiscovery tools
for tool in "${tools[@]}"; do
    log "Installing $tool..."
    go install -v "$tool" 2>&1 | tail -5
done

# Install other tools
for tool in "${other_tools[@]}"; do
    log "Installing $tool..."
    go install -v "$tool" 2>&1 | tail -5
done

# Python tools
log "Installing Python tools..."
pip3 install --upgrade pip 2>/dev/null
pip3 install --upgrade \
    waymore \
    uro \
    paramspider \
    sqlmap \
    arjun \
    tplmap \
    corscanner \
    github-endpoints \
    2>&1 | tail -10

# Nuclei templates
log "Updating nuclei templates..."
nuclei -update-templates 2>&1 | tail -5

# GF patterns
log "Setting up gf patterns..."
mkdir -p ~/.gf
git clone https://github.com/1ndianl33t/Gf-Patterns ~/.gf 2>/dev/null || (cd ~/.gf && git pull)
cp ~/.gf/*.json ~/.gf/ 2>/dev/null || true

# Wordlists
log "Setting up wordlists..."
mkdir -p ~/wordlists
cd ~/wordlists

# Assetnote
wget -q https://wordlists.assetnote.io/best-dns-wordlist.txt -O best-dns-wordlist.txt 2>/dev/null || true
wget -q https://wordlists.assetnote.io/subdomains.txt -O subdomains.txt 2>/dev/null || true
wget -q https://wordlists.assetnote.io/raft-large-directories.txt -O raft-large-directories.txt 2>/dev/null || true
wget -q https://wordlists.assetnote.io/raft-large-files.txt -O raft-large-files.txt 2>/dev/null || true
wget -q https://wordlists.assetnote.io/raft-large-words.txt -O raft-large-words.txt 2>/dev/null || true

# Resolvers
wget -q https://raw.githubusercontent.com/trickest/resolvers/main/resolvers.txt -O resolvers.txt 2>/dev/null || true

# SecLists
git clone --depth 1 https://github.com/danielmiessler/SecLists.git SecLists 2>/dev/null || (cd SecLists && git pull)

# Foundry (for on-chain)
if ! command -v forge &> /dev/null; then
    log "Installing Foundry..."
    curl -L https://foundry.paradigm.xyz | bash
    export PATH="$PATH:$HOME/.foundry/bin"
    foundryup 2>&1 | tail -10
fi

# Virtual Host Discovery
if ! command -v virtual-host-discovery &> /dev/null; then
    log "Installing virtual-host-discovery..."
    git clone https://github.com/jobertabma/virtual-host-discovery.git /tmp/vhd
    cd /tmp/vhd && gem install bundler && bundle install
fi

# JSScanner
if ! command -v JSScanner.py &> /dev/null; then
    log "Installing JSScanner..."
    git clone https://github.com/dark-warlord14/JSScanner.git /tmp/jsscanner
    cd /tmp/jsscanner && pip3 install -r requirements.txt 2>/dev/null
    ln -sf /tmp/jsscanner/JSScanner.py ~/go/bin/JSScanner.py
fi

# Pinkerton
if ! command -v pinkerton &> /dev/null; then
    log "Installing Pinkerton..."
    git clone https://github.com/kljun/pinkerton.git /tmp/pinkerton
    cd /tmp/pinkerton && pip3 install -r requirements.txt 2>/dev/null
    ln -sf /tmp/pinkerton/main.py ~/go/bin/pinkerton
fi

log "=== INSTALLATION COMPLETE ==="
log "Verify with: ~/go/bin/subfinder -version"
log "Tools installed in: ~/go/bin/"
log "Wordlists in: ~/wordlists/"
log "Nuclei templates: $(nuclei -version 2>&1 | grep -o 'templates.*' || echo 'check manually')"