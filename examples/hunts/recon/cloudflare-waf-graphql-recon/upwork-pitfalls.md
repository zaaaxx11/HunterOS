# Upwork pitfalls — cloudflare-waf-graphql-recon

Cut verbatim from `soul/skills/recon/cloudflare-waf-graphql-recon/SKILL.md`
during the 2026-09-07 skills cull (S2b-1); body keeps the generalized
class method.

## Pitfalls — Upwork 2026-08-19
- Upwork `www.upwork.com/*` + `api.upwork.com/api/*` all `403 Cf-Mitigated` (Turnstile `__cf_chl_opt`), only `api.upwork.com/graphql` is `401 JSON` — sole unauth entry. Fuzz `amount 0/-1`, `__typename`, `createOffer` all `401`, no public query found yet.
- `cloudscraper` still `403` — managed challenge not simple CF, need real browser or pivot
- Desktop `/downloads` also `403` — Electron update RCE path blocked same way
- APK mirrors `apkpure.com` also `403 Cf-Mitigated` — use alternative mirror or GitHub release
