# Next.js Build Manifest Route Leak — Session 2026-07-29

## Scenario
Target `everlyn.ai` (Next.js App Router, App-host chunk `2516-config.js`).
`/admin` returns RSC `0:["$L1",["$","$L2",null,{"redirect":"/auth/signin","statusCode":307}]]`
— tempting to conclude “admin not reachable”. Build manifest told otherwise.

## Reproduction

```bash
# 1. Find config chunk
grep -rl 'buildConfig' /tmp/ev_static/chunks/*.js | head
# → /tmp/ev_static/chunks/2516-config.js

# 2. Pull admin route names out of the pre-auth config chunk
grep -oE '"(admin/[a-zA-Z0-9_\-]+)"' /tmp/ev_static/chunks/*.js | sort -u
```

Output (excerpt):
```
"admin/ambar-import"
"admin/assistance"
"admin/audio_export"
"admin/calculator"
"admin/clients"
"admin/export-generator"
"admin/general-config"
"admin/invites"
"admin/leads"
"admin/mutabaah-exercise"
"admin/news"
"admin/notification-center"
"admin/orders"
"admin/page-content"
"admin/php_exports"
"admin/referral-banners"
"admin/resellers"
"admin/reseller-config"
"admin/super-admin-config"
"admin/translation-config"
"admin/users"
```

## Why it matters
- Route names leak product surface (`resellers`, `php_exports`, `leads`,
  `mutabaah-exercise` ⇒ Indonesian EdTech + affiliate) before any auth.
- Lets hunter probe exact paths (`/admin/php_exports`, `/admin/users`) with
  targeted wordlists instead of blind fuzzing of 100k+ wordlist.
- Pairs with RSC `?dpl=` preview probing and `_next/data/<buildId>/admin.json`
  attempts (both returned 404/401 here — auth enforced, but route names
  still valid intel).

## Reporting phrasing (verified)
> **Pre-auth information disclosure (low)** — Next.js `buildConfig` in
> chunk `2516-config.js` discloses 22 admin route names including
> `/admin/php_exports`, `/admin/users`, `/admin/reseller-config`. Auth is
> enforced (307 → /auth/signin) so impact is recon-only, but route names
> should not ship to anonymous clients.

## Verification checklist
- [ ] `grep -n` line numbers from config chunk included in report.
- [ ] Each admin path probed once with `curl -4 -I` and status recorded.
- [ ] `/api/auth/providers` probed to confirm NextAuth stack.
- [ ] Chunk hash + deployment URL fingerprinted for retest.
