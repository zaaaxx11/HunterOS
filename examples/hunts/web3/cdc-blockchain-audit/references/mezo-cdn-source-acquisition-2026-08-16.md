# Mezo CDN Source Acquisition Recipe — 2026-08-16

## Context
Host: TencentOS 4, git 2.49.0 at /usr/local/bin/git, missing /usr/local/libexec/git-core/git-remote-https → all `git clone https://` fail with `remote helper 'https' aborted`. GitHub API unauthenticated = 60/h → `403 API rate limit exceeded` after ~60 calls (X-RateLimit-Remaining: 0, reset 1786843705). Target org: mezo-org (24 repos: mezod 15★, musd 16★, tigris, validator-kit, NTT bridges).

## Working Acquisition Chain (order matters)
1. **Tarball fallback (fast clone):** `curl -L https://github.com/<org>/<repo>/archive/refs/heads/main.tar.gz | tar -xz` — bypasses git entirely. Works even when git-remote-https missing. For tags: `/archive/refs/tags/<tag>.tar.gz`.
2. **CDN raw file fetch (deep read):** `curl -sL https://cdn.jsdelivr.net/gh/<org>/<repo>@<branch>/<path>` — most reliable after API 403. Validated on mezod: 30+ files (precompile/*, x/bridge/*, x/poa/*) after API hit 0. Check with `curl -sI ... | grep HTTP` (200=exists, 404=missing). Alternative: `raw.githubusercontent.com/<org>/<repo>/<branch>/<path>` but same rate shaping as API.
3. **HTML scraping for dir listing:** When `GET /repos/<org>/<repo>/contents/<path>` returns 403, scrape tree HTML: `curl -sL https://github.com/<org>/<repo>/tree/<branch>/<path> | grep -o 'title="[^"]*\.go"' | sort -u`. Gives file list without API. Then fetch each via CDN (step 2). Used for precompile/ (8 subdirs), x/bridge, solidity/contracts/.
4. **JS bundle mining for web2:** `curl -sL https://cdn.jsdelivr.net/gh/<org>/<repo>@main/<js-chunk>` + `grep -o 'https://[^"]*api[^"]*'` for endpoint discovery when frontend is static SSR (mezo.org is Remix SPA with /_assets/*.js).

## Pitfalls
- Do NOT `dnf install git-core` on TencentOS 4 — no package. Go straight to tarball/CDN.
- `raw.githubusercontent.com` 404 may be transient rate-limit 403 misreported as 404 string. Retest via CDN.
- `/usr/local/libexec/git-core/` missing vs `/usr/libexec/git-core/` — check both.
- CDN caching delay: new commits may lag ~5min on jsDelivr. For latest, use `raw.githubusercontent.com` with query `?flush`.

## Files Proven via CDN on 2026-08-16
precompile/contract.go, method.go, converter.go, assetsbridge/{assets_bridge.go,bridge_out.go,triparty.go,pause.go,erc20.go}, erc20/{permit.go,approve.go,transfer.go}, validatorpool/{validatorpool.go,privilege.go}, maintenance/{precompiles.go,self_destruct.go,evm.go}, upgrade/{upgrade.go,plan.go}, x/poa/keeper/keeper.go, x/bridge/keeper/triparty.go, musd solidity BorrowerOperationsSignatures.sol, etc. (full list in session transcript).

## One-liner probe script
```bash
for f in precompile/contract.go x/bridge/keeper/keeper.go; do
  echo "=== $f ==="; curl -sI https://cdn.jsdelivr.net/gh/mezo-org/mezod@main/$f | grep HTTP
  curl -sL https://cdn.jsdelivr.net/gh/mezo-org/mezod@main/$f | head -n 5
done
```
