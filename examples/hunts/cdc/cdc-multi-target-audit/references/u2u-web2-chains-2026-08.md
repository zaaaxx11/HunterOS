# U2U Web2 Chain Analysis — CDC Agent 4 Reference

## Target
U2U Network (Chain 39) — Web2 attack surface: Next.js 15 main site, React SPA staking app, AA Bundler v0.7.0, public RPC with debug namespace.

## CHAIN Analysis Results

### CHAIN A: Prismic CMS Preview → Unauthenticated Revalidation → Cache Poisoning + DoS
- **Trigger:** GET `/api/preview` → sets `__prerender_bypass` cookie (no auth)
- **Trigger:** POST `/api/revalidate` → `{"revalidated":true}` (secret NOT validated)
- **Effect:** Anyone can enable preview mode AND trigger full site revalidation
- **Trust Boundary:** Public internet → Prismic CMS integration → Next.js ISR cache
- **Impact:** CRITICAL — content poisoning via cache manipulation, DoS via revalidation loop

### CHAIN B: Next.js Server Action → RCE
- **Verdict:** BLOCKED — no `$ACTION_ID` in RSC payload, purely static site from Prismic

### CHAIN C: Staking App → Wallet Drain via Malicious Contract Interaction
- **Trigger:** User connects wallet at staking.u2u.xyz → approve/stake
- **Effect:** Social engineering or XSS → inject malicious contract call → drain
- **Trust Boundary:** Browser → U2U chain (RPC)
- **Impact:** HIGH — requires XSS or supply chain compromise first

### CHAIN D: Bundler JSON-RPC → SSRF / Internal Network Access
- **Trigger:** POST bundler.u2u.xyz/rpc → eth_sendUserOperation
- **Effect:** Bundler → RPC `debug_traceCall` → reach K8s internal services
- **Trust Boundary:** Public internet → Bundler → RPC node → K8s internal network
- **Impact:** HIGH — SSRF chain, needs network topology confirmation

### CHAIN E: report.u2u.xyz → Admin Panel → Internal Data Dump
- **Verdict:** DEAD — 404, no admin panel found

### CHAIN F: RPC Debug API → File Write → Config Overwrite → RCE
- **Trigger:** POST debug_writeMemProfile/BlockProfile/MutexProfile/CpuProfile/GoTrace
- **Effect:** Arbitrary file write to RPC server filesystem (binary pprof content)
- **Trust Boundary:** Public internet → RPC node → filesystem (NO AUTH)
- **Impact:** CRITICAL — file write LIVE, config overwrite → restart → corrupted state

## Key Lessons for CDC Agent 4 (CHAINER)
1. Always verify live, don't just theorize — `rpc_modules` says `debug:1.0` but EACH method must be probed individually
2. `result:null` in JSON-RPC debug methods = SUCCESS, not error
3. Prismic revalidation is the #1 post-CMS finding — probe with wrong secret first
4. Bundler `/rpc` path is non-standard, try both `/` and `/rpc`
5. JS bundle is a recon goldmine — 4.2MB bundle = full infra map
6. Always distinguish BLOCKED from DEAD — BLOCKED means the feature exists but is validated; DEAD means the endpoint doesn't exist at all