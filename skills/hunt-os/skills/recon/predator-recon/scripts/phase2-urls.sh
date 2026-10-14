#!/bin/bash
# PHASE 2: URL & PARAMETER HARVEST
# Input: live.txt (from phase1)
# Output: urls.txt, params.txt, js-files.txt

set -euo pipefail

LIVE_FILE="${1}"
OUT_DIR="${OUT_DIR:-$(pwd)/recon-$(date +%Y%m%d-%H%M)}"
mkdir -p "$OUT_DIR"

URLS_FILE="$OUT_DIR/urls.txt"
LIVE_URLS_FILE="$OUT_DIR/live-urls.txt"
PARAMS_FILE="$OUT_DIR/params.txt"
JS_FILES_FILE="$OUT_DIR/js-files.txt"
ASSUMPTIONS_LOG="$OUT_DIR/assumptions.log"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$ASSUMPTIONS_LOG"; }

if [ ! -f "$LIVE_FILE" ]; then
    log "ERROR: Live file not found: $LIVE_FILE"
    exit 1
fi

log "=== PHASE 2: URL & PARAM HARVEST ==="
log "Input: $LIVE_FILE"
log "Output: $OUT_DIR"

# ===== HISTORICAL URLS =====
log "Collecting historical URLs..."

# Waymore (comprehensive)
log "  [1/4] waymore..."
cat "$LIVE_FILE" | awk '{print $1}' | waymore -i - -mode U -oU "$OUT_DIR/waymore.txt" 2>/dev/null || true
cat "$OUT_DIR/waymore.txt" 2>/dev/null | anew "$URLS_FILE"

# GAU (fast)
log "  [2/4] gau..."
cat "$LIVE_FILE" | awk '{print $1}' | gau | anew "$URLS_FILE"

# Katana (crawling + JS discovery)
log "  [3/4] katana (crawling)..."
cat "$LIVE_FILE" | awk '{print $1}' | while read url; do
    katana -u "$url" -jc -kf all -silent -d 3 2>/dev/null | anew "$URLS_FILE"
done

# GitHub endpoints (if token available)
if [ -n "${GITHUB_TOKEN:-}" ]; then
    log "  [4/4] github-endpoints..."
    cat "$LIVE_FILE" | awk '{print $1}' | sed 's|https://||; s|http://||; s|/.*||' | sort -u | while read domain; do
        python3 /root/.local/bin/github-endpoints.py -t "$GITHUB_TOKEN" -d "$domain" 2>/dev/null | anew "$URLS_FILE"
    done
else
    log "  [4/4] github-endpoints skipped (no GITHUB_TOKEN)"
fi

URL_COUNT=$(wc -l < "$URLS_FILE")
log "Total URLs collected: $URL_COUNT"

# ===== DEDUP & FILTER LIVE =====
log "Deduplicating and filtering live URLs..."
cat "$URLS_FILE" | uro | anew "$URLS_FILE.dedup"
cat "$URLS_FILE.dedup" | httpx -silent -mc 200 -o "$LIVE_URLS_FILE"
LIVE_URL_COUNT=$(wc -l < "$LIVE_URLS_FILE")
log "Live URLs (200 OK): $LIVE_URL_COUNT"

# ===== EXTRACT PARAMETERS =====
log "Extracting parameters..."
cat "$LIVE_URLS_FILE" | grep "=" | anew "$PARAMS_FILE"
PARAM_COUNT=$(wc -l < "$PARAMS_FILE")
log "URLs with parameters: $PARAM_COUNT"

# ===== EXTRACT JS FILES =====
log "Extracting JavaScript files..."
cat "$LIVE_URLS_FILE" | grep -E "\.js($|\?)" | httpx -mc 200 -silent | anew "$JS_FILES_FILE"
JS_COUNT=$(wc -l < "$JS_FILES_FILE")
log "JS files found: $JS_COUNT"

# ===== CALCULUS FILTER (Tag high-value params) =====
if [ -f "$PARAMS_FILE" ] && [ -s "$PARAMS_FILE" ]; then
    log "Tagging high-value parameters (Calculus filter)..."
    # High-value keywords: auth, payment, admin, api, wallet, token, contract, swap, bridge, stake
    cat "$PARAMS_FILE" | grep -iE "(auth|login|signin|password|token|key|secret|wallet|payment|admin|api|swap|bridge|stake|contract|withdraw|deposit|transfer|mint|burn|govern|vote|dao|oracle|price)" | anew "$OUT_DIR/high-value-params.txt"
    HV_COUNT=$(wc -l < "$OUT_DIR/high-value-params.txt" 2>/dev/null || echo 0)
    log "High-value parameters: $HV_COUNT"
fi

# ===== BLIND SPOT CHECK =====
log "Blind Spot Scanner check..."
# What did we NOT look at?
# - URLs without parameters (might have path-based vulns)
cat "$LIVE_URLS_FILE" | grep -v "=" | anew "$OUT_DIR/no-param-urls.txt"
# - Non-HTML endpoints (API, GraphQL, WebSocket)
cat "$LIVE_URLS_FILE" | grep -iE "(graphql|api/|ws://|wss://|\.json$|\.xml$)" | anew "$OUT_DIR/api-endpoints.txt"

log "=== PHASE 2 COMPLETE ==="
log "Outputs:"
log "  $URLS_FILE (all URLs)"
log "  $LIVE_URLS_FILE (live 200 OK)"
log "  $PARAMS_FILE (URLs with params)"
log "  $JS_FILES_FILE (JS files)"
log "  $OUT_DIR/high-value-params.txt (Calculus-tagged)"
log "  $OUT_DIR/no-param-urls.txt (blind spot)"
log "  $OUT_DIR/api-endpoints.txt (blind spot)"
log "  $ASSUMPTIONS_LOG"

# Export for next phase
echo "$LIVE_URLS_FILE" > "$OUT_DIR/.phase2-urls"
echo "$PARAMS_FILE" > "$OUT_DIR/.phase2-params"
echo "$JS_FILES_FILE" > "$OUT_DIR/.phase2-js"