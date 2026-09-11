#!/bin/bash
# PHASE 1: SUBDOMAIN ENUMERATION
# Passive → Resolve → Active (if Calculus says yes)
# Input: targets.yaml (with Calculus ranking)
# Output: subs.txt, live.txt

set -euo pipefail

TARGETS_FILE="${1:-targets.yaml}"
OUT_DIR="${OUT_DIR:-$(pwd)/recon-$(date +%Y%m%d-%H%M)}"
mkdir -p "$OUT_DIR"

SUBS_FILE="$OUT_DIR/subs.txt"
LIVE_FILE="$OUT_DIR/live.txt"
RESOLVED_FILE="$OUT_DIR/resolved.txt"
ASSUMPTIONS_LOG="$OUT_DIR/assumptions.log"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$ASSUMPTIONS_LOG"; }

log "=== PHASE 1: SUBDOMAIN ENUM ==="
log "Targets: $TARGETS_FILE"
log "Output: $OUT_DIR"

# Check if yq is available for YAML parsing
if ! command -v yq &> /dev/null; then
    log "WARNING: yq not found, treating each line in targets file as domain"
    DOMAINS=$(cat "$TARGETS_FILE" | grep -v '^#' | grep -v '^$')
else
    log "Parsing targets with Calculus ranking..."
    # Extract domains with priority >= threshold (default 50)
    PRIORITY_THRESHOLD="${PRIORITY_THRESHOLD:-50}"
    DOMAINS=$(yq -r ".[] | select(.priority >= $PRIORITY_THRESHOLD) | .domain" "$TARGETS_FILE")
fi

if [ -z "$DOMAINS" ]; then
    log "ERROR: No domains found"
    exit 1
fi

log "Domains to enumerate:"
echo "$DOMAINS" | while read d; do log "  - $d"; done

# ===== PASSIVE ENUMERATION =====
log "Running passive enumeration..."

# Subfinder (fast, high coverage)
log "  [1/4] subfinder..."
echo "$DOMAINS" | subfinder -all -silent | anew "$SUBS_FILE"

# Assetfinder (quick)
log "  [2/4] assetfinder..."
echo "$DOMAINS" | assetfinder --subs-only | anew "$SUBS_FILE"

# Amass (passive, deep - optional for high-value)
if [ "${RUN_AMASS:-true}" = "true" ]; then
    log "  [3/4] amass (passive)..."
    echo "$DOMAINS" | while read domain; do
        amass enum -passive -norecursive -noalts -d "$domain" | anew "$SUBS_FILE"
    done
else
    log "  [3/4] amass skipped (RUN_AMASS=false)"
fi

# Certificate transparency
log "  [4/4] crt.sh..."
echo "$DOMAINS" | while read domain; do
    curl -s "https://crt.sh/?q=%.${domain}&output=json" | \
        jq -r '.[].name_value' 2>/dev/null | anew "$SUBS_FILE"
done

SUBS_COUNT=$(wc -l < "$SUBS_FILE")
log "Passive subdomains found: $SUBS_COUNT"

# ===== RESOLVE =====
log "Resolving subdomains..."
if command -v puredns &> /dev/null; then
    log "Using puredns for resolution..."
    puredns resolve "$SUBS_FILE" -r /root/.config/predator-recon/resolvers.txt -w "$RESOLVED_FILE" 2>/dev/null || \
    puredns resolve "$SUBS_FILE" -w "$RESOLVED_FILE" 2>/dev/null
else
    log "puredns not found, using httpx for resolution..."
    cat "$SUBS_FILE" | httpx -silent -status-code -title -tech-detect | anew "$LIVE_FILE"
    RESOLVED_FILE="$LIVE_FILE"
fi

# ===== LIVE CHECK =====
log "Checking live hosts..."
cat "$RESOLVED_FILE" | httpx -silent -mc 200,301,302,403,401,404 -title -tech-detect -status-code -o "$LIVE_FILE"

LIVE_COUNT=$(wc -l < "$LIVE_FILE")
log "Live hosts: $LIVE_COUNT"

# ===== ACTIVE BRUTEFORCE (Calculus-gated) =====
if [ "${RUN_ACTIVE:-false}" = "true" ] && [ -f /root/.config/predator-recon/wordlists/best-dns-wordlist.txt ]; then
    log "Running active bruteforce (RUN_ACTIVE=true)..."
    echo "$DOMAINS" | while read domain; do
        puredns bruteforce /root/.config/predator-recon/wordlists/best-dns-wordlist.txt "$domain" \
            -r /root/.config/predator-recon/resolvers.txt | anew "$SUBS_FILE"
    done
    # Re-resolve and re-check
    puredns resolve "$SUBS_FILE" -w "$RESOLVED_FILE" 2>/dev/null
    cat "$RESOLVED_FILE" | httpx -silent -mc 200,301,302,403,401,404 -o "$LIVE_FILE"
    LIVE_COUNT=$(wc -l < "$LIVE_FILE")
    log "After active bruteforce - Live hosts: $LIVE_COUNT"
else
    log "Active bruteforce skipped (set RUN_ACTIVE=true and provide wordlist to enable)"
fi

# ===== SUBDOMAIN TAKEOVER CHECK =====
if command -v subzy &> /dev/null; then
    log "Checking subdomain takeover..."
    subzy run --targets "$LIVE_FILE" | anew "$OUT_DIR/takeover.txt"
fi

# ===== NUCLEI QUICK SCAN (exposures) =====
if command -v nuclei &> /dev/null; then
    log "Running nuclei exposure scan on live hosts..."
    nuclei -l "$LIVE_FILE" -t exposures/ -t misconfiguration/ -rate-limit 100 -silent -o "$OUT_DIR/nuclei-exposures.txt"
fi

log "=== PHASE 1 COMPLETE ==="
log "Outputs:"
log "  $SUBS_FILE (all subdomains)"
log "  $RESOLVED_FILE (resolved)"
log "  $LIVE_FILE (live with tech/title)"
log "  $OUT_DIR/takeover.txt (takeover candidates)"
log "  $OUT_DIR/nuclei-exposures.txt (exposures)"
log "  $ASSUMPTIONS_LOG (assumptions & decisions)"

# Export for next phase
echo "$LIVE_FILE" > "$OUT_DIR/.phase1-output"