#!/bin/bash
# PHASE 4: INFRASTRUCTURE & EXPOSURE
# Input: live-urls.txt, live-ips.txt
# Output: infra.txt, ports.txt, vhosts.txt, exposures.txt

set -euo pipefail

LIVE_URLS_FILE="${1}"
LIVE_IPS_FILE="${2}"
OUT_DIR="${OUT_DIR:-$(pwd)/recon-$(date +%Y%m%d-%H%M)}"
mkdir -p "$OUT_DIR"

ASSUMPTIONS_LOG="$OUT_DIR/assumptions.log"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$ASSUMPTIONS_LOG"; }

log "=== PHASE 4: INFRASTRUCTURE & EXPOSURE ==="

# ===== EXTRACT IPS FROM LIVE URLS =====
if [ ! -f "$LIVE_IPS_FILE" ] || [ ! -s "$LIVE_IPS_FILE" ]; then
    log "Extracting IPs from live URLs..."
    cat "$LIVE_URLS_FILE" | sed -E 's|https?://([^/]+)/.*|\1|' | sort -u | \
        xargs -I{} sh -c 'dig +short {} | grep -E "^[0-9]+\." | head -1' 2>/dev/null | \
        sort -u > "$OUT_DIR/live-ips.txt"
    LIVE_IPS_FILE="$OUT_DIR/live-ips.txt"
fi

IP_COUNT=$(wc -l < "$LIVE_IPS_FILE" 2>/dev/null || echo 0)
log "Live IPs: $IP_COUNT"

# ===== PORT SCANNING =====
if command -v naabu &> /dev/null; then
    log "Port scanning with naabu (top 1000)..."
    naabu -list "$LIVE_IPS_FILE" -top-ports 1000 -silent -o "$OUT_DIR/ports.txt" 2>&1 | tee -a "$ASSUMPTIONS_LOG"
else
    log "naabu not found, skipping port scan"
fi

# ===== VHOST DISCOVERY =====
if command -v virtual-host-discovery &> /dev/null; then
    log "Virtual host discovery..."
    cat "$LIVE_IPS_FILE" | while read ip; do
        # Get hostnames from SSL certs / PTR
        vhost-discovery --ip "$ip" --host "$(dig -x "$ip" +short | head -1 | sed 's/\.$//')" 2>/dev/null | \
            anew "$OUT_DIR/vhosts.txt"
    done
else
    log "virtual-host-discovery not found, trying manual..."
    # Manual: use httpx with Host header fuzzing
    if [ -f "$OUT_DIR/vhost-wordlist.txt" ]; then
        cat "$LIVE_IPS_FILE" | while read ip; do
            ffuf -u "http://$ip" -H "Host: FUZZ" -w "$OUT_DIR/vhost-wordlist.txt" \
                -mc 200,403 -fs 0 -silent -o "$OUT_DIR/vhost-ffuf.json" 2>/dev/null
        done
    fi
fi

# ===== SSL/TLS ANALYSIS =====
log "SSL/TLS analysis..."
if command -v sslscan &> /dev/null; then
    cat "$LIVE_IPS_FILE" | xargs -P 10 -I{} sslscan {} 2>/dev/null | anew "$OUT_DIR/sslscan.txt"
fi

# Check for weak SSL configs via nuclei
if command -v nuclei &> /dev/null; then
    nuclei -l "$LIVE_IPS_FILE" -t ssl/ -rate-limit 50 -silent -o "$OUT_DIR/nuclei-ssl.txt"
fi

# ===== SERVICE ENUMERATION =====
if command -v nmap &> /dev/null; then
    log "Service enumeration (nmap -sV on open ports)..."
    # Convert naabu output to nmap format
    if [ -f "$OUT_DIR/ports.txt" ]; then
        cat "$OUT_DIR/ports.txt" | sed 's/:/ /' | awk '{print $1" "$2}' | \
            while read ip port; do
                nmap -sV -p "$port" "$ip" -oN "$OUT_DIR/nmap-$ip-$port.txt" 2>&1 | tee -a "$ASSUMPTIONS_LOG"
            done
    fi
fi

# ===== EXPOSURE CHECKS =====
log "Checking common exposures..."

# Common sensitive paths
EXPOSURE_PATHS=(
    "/.git"
    "/.env"
    "/.env.production"
    "/.env.local"
    "/.env.development"
    "/config.json"
    "/config.yaml"
    "/config.yml"
    "/docker-compose.yml"
    "/docker-compose.yaml"
    "/kubernetes.yml"
    "/k8s.yml"
    "/swagger.json"
    "/swagger.yaml"
    "/openapi.json"
    "/openapi.yaml"
    "/api-docs"
    "/docs"
    "/actuator"
    "/actuator/health"
    "/actuator/env"
    "/actuator/metrics"
    "/actuator/beans"
    "/actuator/mappings"
    "/metrics"
    "/health"
    "/debug"
    "/debug/pprof"
    "/server-status"
    "/server-info"
    "/phpinfo.php"
    "/info.php"
    "/test.php"
    "/admin"
    "/admin/"
    "/administrator"
    "/administrator/"
    "/wp-admin"
    "/wp-login.php"
    "/phpmyadmin"
    "/pma"
    "/mysql"
    "/dbadmin"
    "/adminer"
    "/.well-known/security.txt"
    "/.well-known/change-password"
    "/robots.txt"
    "/sitemap.xml"
    "/crossdomain.xml"
    "/clientaccesspolicy.xml"
    "/backup"
    "/backups"
    "/dump.sql"
    "/database.sql"
    "/data.sql"
    "/logs"
    "/log"
    "/storage"
    "/uploads"
    "/public/uploads"
    "/public/storage"
)

if [ -f "$LIVE_URLS_FILE" ]; then
    log "Testing exposure paths on live URLs..."
    cat "$LIVE_URLS_FILE" | while read url; do
        base=$(echo "$url" | sed -E 's|https?://([^/]+)/.*|https://\1|')
        for path in "${EXPOSURE_PATHS[@]}"; do
            if curl -s -o /dev/null -w "%{http_code}" -m 5 "$base$path" 2>/dev/null | grep -qE "^(200|301|302|403)$"; then
                echo "$base$path" | anew "$OUT_DIR/exposures.txt"
            fi
        done
    done
fi

# ===== CLOUD/INFRA EXPOSURES =====
log "Checking cloud metadata endpoints..."
cat "$LIVE_IPS_FILE" | while read ip; do
    for endpoint in \
        "http://169.254.169.254/latest/meta-data/" \
        "http://169.254.169.254/latest/user-data/" \
        "http://metadata.google.internal/computeMetadata/v1/" \
        "http://169.254.169.254/metadata/v1/" \
        "http://metadata.azure.internal/metadata/instance"; do
        if curl -s -m 2 -H "Metadata-Flavor: Google" "$endpoint" 2>/dev/null | grep -q "."; then
            echo "$ip: $endpoint" | anew "$OUT_DIR/cloud-metadata.txt"
        fi
    done
done

# ===== KUBERNETES/DOCKER API =====
log "Checking Kubernetes/Docker API exposure..."
cat "$LIVE_IPS_FILE" | while read ip; do
    for port in 10250 10255 2375 2376 6443 8443; do
        if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$ip/$port" 2>/dev/null; then
            echo "$ip:$port (k8s/docker API)" | anew "$OUT_DIR/k8s-docker-api.txt"
        fi
    done
done

# ===== BLIND SPOT CHECK =====
log "Blind Spot Scanner..."
cat > "$OUT_DIR/blind-spots.md" << 'EOF'
# Infrastructure Blind Spots - Manual Review
- Internal services accessible via SSRF
- Container escape vectors (privileged containers, host mounts)
- Kubernetes RBAC misconfigurations
- Cloud IAM over-permissions
- Supply chain (base images, dependencies)
- Network segmentation bypass
- Backup encryption / access
- Logging / monitoring gaps
- Incident response readiness
EOF

log "=== PHASE 4 COMPLETE ==="
log "Outputs:"
log "  $OUT_DIR/ports.txt (open ports)"
log "  $OUT_DIR/vhosts.txt (virtual hosts)"
log "  $OUT_DIR/sslscan.txt / nuclei-ssl.txt (SSL)"
log "  $OUT_DIR/nmap-*.txt (service enum)"
log "  $OUT_DIR/exposures.txt (exposed paths)"
log "  $OUT_DIR/cloud-metadata.txt (cloud metadata)"
log "  $OUT_DIR/k8s-docker-api.txt (container APIs)"
log "  $OUT_DIR/blind-spots.md (manual review)"

# Export for next phase
echo "$OUT_DIR" > "$OUT_DIR/.phase4-out"