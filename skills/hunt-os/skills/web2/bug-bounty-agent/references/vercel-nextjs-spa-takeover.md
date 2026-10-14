# Vercel/NextJS Static SPA Takeover Playbook

**Pattern**: Static Next.js SPA deployed on Vercel with RainbowKit wallet, no backend API, no admin panel, no on-chain protocol yet. Token-only project ($5-10K FDV).

## Target Spine
```
Vercel → Next.js 15 (Turbopack) → RainbowKit + wagmi → WalletConnect → Uniswap V3 token
```

## Phase 0: Reality Check (mandatory, 5 minutes)
1. `curl -sI target.xyz` → check: `server: Vercel`, `x-nextjs-*`, `x-vercel-cache`
2. DexScreener → token TVL
3. `eth_getCode` on any 0x addresses → verify bytecode

## Phase 1: Map the Surface

### 1. All standard paths return 404 SPA
Next.js SPA catches all 404s — `/admin`, `/login`, `/dashboard`, `/api/*`, `/vaults/*` all return the same SPA HTML with `404` in RSC payload, NOT distinct server-rendered pages.

### 2. Source Map
- `/^next/static/chunks/*.map` → usually **403** (explicitly blocked) on production
- 403 ≠ 404 → dev actively blocked it

### 3. Vercel Preview URLs
Vercel creates preview deployments on every git push. Try the Vercel project slug:
- `project-name.vercel.app` — production deploy
- `project-name-giam-main.vercel.app` — preview branch
- `project-name-<hash>.vercel.app` — specific preview

The preview URL often has different CORS settings or environment variables.

### 4. Vercel Project Info
- `https://api.vercel.com/v9/projects/<slug>/info` — needs auth, usually 404 without bearer
- `x-vercel-id` header encodes the deployment trace (region, deployment hash, component ID)
- `x-vercel-cache: HIT` — cached static build

### 5. Build ID
From RSC payload: `"b":"EU91t5Yef77yfLdLrWhjE"` → this is the Next.js build ID. Can be used to detect redeploy cycles.

### 6. Vercel CLI Token Leak
Check all paths for `Vercel` token patterns:
- `vercel_[a-zA-Z0-9]{24}` — Vercel tokens
- `/vercel.json`, `/package.json`, `.env`, `.env.local`, `.env.production` — all return 404 SPA

### 7. Alternative Domains
- `project.vercel.app`
- `www.project.vercel.app`
- `project-giam-main.vercel.app`
- `www.project-us.net` — Vercel domain with strict CSP

## Phase 2: If No Secrets Found

### 2.1 Certificate Transparency (crt.sh)
- Search domain → find associated entities → find admin emails
- Works for sites using custom domains with EV/OV certs

### 2.4 DNS Zone Transfers / Records
- `dig axfr domain.xyz @nameserver` — zone transfer (almost always blocked)
- `dig ANY domain.xyz` — TXT, SPF, DKIM records
- `dig NS domain.xyz` — who's the authoritative DNS provider?

### 2.5 GitHub Search
- `https://api.dev.github.com/search/repositories?q=projectname` → usually 0 for anonymous teams
- Check for forks or contributors

## Phase 4: Social Vector (last resort)
- Token Twitter/X account → DM/follow for emails, team info
- Vercel team page → `https://vercel.com/team/<slug>`
- DexScreener social links

## Quick Reference Commands

```sh
# Vercel preview URLs
curl -sI "https://project-name.vercel.app/"
curl -sI "https://project-name-giam-main.vercel.app/"

# Source map
curl -w '%{http_code}' "https://target.xyz/_next/static/chunks/main-hash.js.map"

# Vercel project info
curl -s "https://api.vercel.com/v9/projects/project-slug/info"

# Environment leaks
for f in ".env" ".env.local" ".env.production" ".env.development" \
  "vercel.json" "package.json" "next.config.js" "next.config.mjs"; do
  echo -n "$f → "
  curl -s -w '%{http_code}' -o /dev/null "https://target.xyz/$f"
done

# Build ID from RSC payload
curl -s "https://target.xyz/" -H 'RSC: 1' \
  -H 'Next-Router-State-Tree: %5B%5D' 2>/dev/null | grep -oP '"b":"[^"]+"'

# DexScreener
curl -s "https://api.dexscreener.com/latest/dex/search?q=PROJECTNAME"

# GitHub
curl -s "https://api.github.com/search/repositories?q=projectname"

# cirt.sh
curl -s "https://crt.sh/?q=%.target.xyz&output=json"
```

## When to Pivot

| Finding | Action |
|---------|--------|
| Token TVL < $10K, no protocol contracts | Tell operator, offer to pivot |
| Vercel preview → identical SPA content | No environment variance |
| GitHub → 0 public repos | No accidental source leak |
| All env files → 404 | No backend cluster exposed |
| Whois → private | Anonymous team |
| Sourcemap → 403 | Dev blocked production debugging |

**After exhausting all Vercel vectors and finding no backend, no secrets, and micro-cap token only: tell operator the target is a static frontend with no takeover surface and recommend pivoting to a target with on-chain TVL or a live backend.**

## Case Study: Pops Finance (2026-07-29)
- Robinhood chain POPS token: 0x7E07b... $9K community liquidity
- No vaults, no protocol contracts, no admin panel
- 85+ Turbopack chunks, 2.7MB combined JS → zero protocol artifacts
- Vercel preview URLs found (pops-finance.vercel.app), same SPA content
- GitHub → 0 public repos
- Post: within 1 hour, fully exhausted + pivoted