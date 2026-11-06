# TanStack Start SSR — Pitfalls & Hard Blocks

## P1: SSR-Only Server Functions — "Only HTML requests are supported here"

**Finding**: TanStack Start v2 blocks ALL non-HTML requests with `{"error":"Only HTML requests are supported here"}`.

**Impact**: Server function fuzzing, admin login brute-force, and direct API calls via curl are ALL impossible. This is not a per-endpoint guard — it's a framework-level behavior that rejects anything not matching the TanStack streaming protocol (`$TSR` SSR barrier).

**Workaround**: Attack the backend that TanStack proxies TO (Privy, Supabase, ChangeNOW), rather than the server functions themselves. Browser automation (Playwright/Puppeteer) is the only direct path when server functions must be exercised.

**Verified on**: ColibriSwap (July 2026) — all admin-login, admin-stats, swap-estimate POSTs to /panel-x7k9m2q3 returned the SSR page shell with no server function execution.

## P2: Supabase DNS Resolvability Must Be Checked First

**Finding**: When a target uses Supabase (`*.supabase.co`), the project URL may be paused/deleted. In ColibriSwap '26, the project URL returned `NXDOMAIN` — the project was unreachable even though the Edge Functions gateway still confirmed the project ID.

**Check**: Always run `nslookup/dig <PROJECT>.supabase.co` before doing a full Phase 1-8 supabase exploitation. If DNS fails, pivot to:
- Edge Functions gateway (still resolves even when main API is dead)
- Proxy-through-target approach (call colibriswap.com endpoints, which proxy to Supabase server-side)
- Target the admin panel for credential brute-force instead

## P3: Privy AppId Extraction Pattern — Vite Env Inlining

**Finding**: The appId is NOT in the Privy-specific bundle. It's inlined via Vite: `var <shortname> = 'cm...'` at the top of the 2-3MB main index bundle. Usage: grep on main bundle for the pattern.

**Verified on**: ColibriSwap, T3tris. Pattern holds across Vite builds.

**Critical follow-up**: Privy API origin-gates ALL non-browser requests. Even with correct `privy-app-id`, `Origin`, and `Referer` headers, curl/script-based requests are rejected with `{"error":"Invalid Privy app ID"}`. Browser automation (Playwright/Puppeteer) is required to interact with Privy endpoints.

## P4: Admin Panel Discovery in TanStack

**Finding**: Admin panels live as lazy-loaded routes NOT linked in navigation. Discovery via:
1. Robots meta: `<meta name="robots" content="noindex, nofollow">` — indicates deliberate hiding
2. Route manifest in SSR barrier — unusual route names (e.g., `/panel-x7k9m2q3`)
3. The bundle preload includes chunks that are not in the main navigation

**Post-discovery**: Download the admin-specific bundle and reverse the auth mechanism (`queryKey: ["admin-me"]` indicates a server function identity check; `t?.admin ? <Dashboard> : <LoginForm>` confirms client-side gating).

## P6: Browser Automation as the Only Path When Both TanStack + Privy Block curl

**Finding**: When TanStack SSR rejects all non-HTML POST AND Privy origin-gates all curl requests, browser automation (Playwright/Puppeteer) is the ONLY viable attack path. In ColibriSwap '26, Playwright was installed but `libgbm.so.1` was missing on TencentOS — preventing headless Chromium launch.

**Fix**: Before relying on Playwright, verify: `npx playwright install` + system deps (`libgbm`, `libdrm`). On RPM-based distros, `mesa-libgbm` provides `libgbm.so.1` — if missing, `dnf install mesa-libgbm` or fall back to the `chromium_headless_shell` that ships with `npx playwright install chromium`.

**If Playwright fails**, pivot to:
1. Fake JWT injection in localStorage
2. Proxy through target's own SSR (call colibriswap.com to reach Privy/Supabase)
3. Cloudflare Workers direct access
4. Abandon target if ALL above dead

## P5: The Pivot Sequence for Non-Custodial Aggregators

```
Multi-chain check → 0x bytecode on all chains 
     → Recognized: Non-custodial frontend aggregator
     → Extract partners: ChangeNOW, HoudiniSwap (from bundles)
     → Extract providers: Supabase (sb_publishable key), Privy (appId)
     → Phase 1: Supabase access → anon key probes + table access attempts
     → Phase 2: Auth attempt → Direct Supabase/Privy brute force fails (DNS/Origin block)
     → Phase 3: Admin panel discovery via route probing
     → Phase 4: Admin bundle analyzed (login flow, post-login capabilities)
     → Deadlock: Can't execute server functions without browser; backend may be paused
     → Decision: Walk away if no exploitable fund surface found
```