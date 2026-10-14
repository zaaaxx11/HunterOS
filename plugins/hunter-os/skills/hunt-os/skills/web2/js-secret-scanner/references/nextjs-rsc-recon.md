# Next.js RSC & Build Manifest Recon — everlyn.ai Session Reference

Context: authorized bug-bounty static-analyst pass (AGENT 1 brief) against a Next.js 15
App Router target fronted by Cloudflare+ Vercel.

## 1. Chunk Download
Target served 85 chunks; main page 54,663 bytes. IPv4-only curl avoided stalls:

```bash
mkdir -p /tmp/ev_static/chunks && cd /tmp/ev_static
curl -4 -sS -D headers_main.txt -o main.html https://everlyn.ai
# extract chunk filenames from main.html script tags and webpack r.u map, loop-download
```

## 2. Key Discovery — buildConfig Route Leak
`d91f9d4dbebfb265-config.js` is fetched by layout chunk pre-auth and contains:

```json
buildConfig: {
  "admin/php_exports": "...",
  "admin/audio_export": "...",
  "admin/invites": "...",
  "admin/orders": "...",
  "admin/resellers": "...",
  "admin/export-generator": "..."
}
```
Pivot: existence of these names proves the admin area and its sub-features even when
`GET /_next/static/chunks/app/%5Blocale%5D/(admin)/admin/page.js` → 404.

## 3. RSC Auth Gate Response Shape
Unauthenticated `GET /admin` with RSC headers returns 200 HTML containing:

```
0:["$L1",["$","$L2",null,{"redirect":"/auth/signin","statusCode":307}]]
```

Plus `NEXT_REDIRECT;/auth/signin;307` in a later push line. Both are valid evidence
of the redirect target without ever following it.

## 4. App Router manifest layout (what actually exists)
```
/_next/static/<buildId>/_buildManifest.js   ✅ present
/_next/static/<buildId>/_ssgManifest.js     ✅ present
/_next/static/<buildId>/_ssgManifest.js.map 404 (source maps off — good hygiene)
```
`pages-manifest.json` is absent because App Router. Don't chase it.

## 5. Auth probe results (this target)
| Endpoint                          | Status | Note                                  |
|-----------------------------------|--------|---------------------------------------|
| /api/auth/providers               | 404    | Not NextAuth — custom auth in use     |
| /api/auth/signin (POST, creds)    | 500    | Server error on probe; investigate    |
| /admin (RSC)                      | 200    | Sign-in redirect embedded in payload  |

Session strategy pivot: when `/api/auth/*` 404s, stop guessing NextAuth internals and
look for custom JWT/cookie names in chunk strings instead.

## 6. Verified check-list of what NOT to claim
- A 404 on admin `page.js` alone ≠ "no admin area". Cite buildConfig leak instead.
- An RSC redirect inside `__next_f.push` is proof the route exists and its gate target.
- Cloudflare front-end will stall on IPv6 — `curl -4` is required, not optional.
