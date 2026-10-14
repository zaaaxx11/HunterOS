# TanStack Start SSR Audit — Server Function Extraction & Exploitation

## Context (July 2026 — ColibriSwap audit)
TanStack Start is a full-stack React SSR framework. Server functions use the `createServerFn`/$ pattern and are called via `/_serverFn/<hash>` with seroval serialization protocol.

## Server Function Setup Pattern
```javascript
// In TanStack Start: $ helper creates a serverFn
import { $ } from './createServerFn-B8CHxd_0.js'
const myFn = $(...).handler(r('hash-of-function-id'))
```

## How to Identify
1. Check loaded JS bundles for `createServerFn` imports
2. ServerFn IDs are SHA256 hashes stored as `r('hash...')` call
3. In the server bundle: `import{n as r}from"./createServerFn-..."` maps to the factory

## How to Extract Server Function IDs
```bash
# 1. Find hashes (64-char hex) in the relevant page bundle
curl -sL "https://TARGET/assets/PAGE-BUNDLE.js" | grep -oE 'r\(["'\'']([a-f0-9]{64})["'\'']\)' 

# 2. Trace function mapping
# In bundle: D(w) = send-min, D(b) = send-est-reverse, D(T) = actual-execution
# where D() maps from index-Bgy5r6e4.js which registers server functions
```

## API Call Protocol
```bash
# Correct format for calling TanStack server functions:
curl -X POST 'https://TARGET/_serverFn/<SHA256-HASH>' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/x-tss-framed, application/x-ndjson, application/json' \
  -H 'x-tsr-serverFn: true' \
  -d '{"data":{...}}'
```

## Response Format
- Success: Seroval-serialized JSON with `{"t":...,"i":...,"f":...,"m":...}`
- Error: `{"t":25,"i":0,"s":{"message":{"t":1,"s":"Seroval Error (step: 3)"}},"c":"$TSR/Error"}`
- The `x-tss-serialized: true` header indicates seroval protocol
- Server functions respond to POST with JSON body wrapped in `{data: {payload}}`

## Privy Auth in TanStack
- Privy SDK is a peer npm dependency, not server function
- AppId is injected at provider level (not in JS bundles)
- Works via `usePrivy()` hook → `login()`, `sendCode()`, `loginWithCode()` → POST to `https://auth.privy.io/api/v1/...`
- Key indicators:
  - `OAuth_authorize` endpoint: `/api/v1/apps/{appId}/oauth/authorize`
  - `OTP sendCode`: call `sendCode({email})` posted to `auth.privy.io`
  - OTP `6-digit` numeric code
  - Chains configured: USDC addresses stored per chain for funding
  - Supports: CrossApp auth, external OAuth (Google, Twitter, Discord, etc.)

## Dashboard/Admin Detection
- Card overlay function: `function admin() {}` 
- Privy is the auth system — admin == user with elevated Privy role
- Check if email domain whitelisting exists: search bundles for `admin@`, `@colibri`, role strings
- The "Business" route on colibriswap implies there might be partner portal

## Pitfalls

> **See `references/tanstack-start-pitfalls.md` for session-specific hard blocks with workarounds.**

Key class-level blocks:
- **Server functions not directly accessible** — TanStack returns `{"error":"Only HTML requests are supported here"}`. This is a class-level architectural write; all server functions are gated behind the SSR streaming protocol. See pitfalls doc #SP-001 for workaround strategy.
- **Privy AppId not embedded** — injected server-side, not findable in client bundles via static analysis

## Static SPA Detection — Cloudflare CDN Behind TanStack Start

When probing a TanStack Start app and getting `"Only HTML requests are supported here"` (HTTP 500) on POST to any route, the app is deployed as a **static SPA on Cloudflare CDN** — there is no server-side rendering or server function execution happening at the CDN edge. Server functions are frontend-only proxies that call a separate backend (typically Supabase) directly from the browser.

### Detection Signals

```bash
# 1. POST to any route returns this error (the definitive SPA signal)
curl -s -X POST "https://<target>/panel-admin" \
  -H "Content-Type: application/json" \
  -d '<anything>' 
# → {"error":"Only HTML requests are supported here"} (HTTP 500)

# 2. Server response headers confirm CDN
curl -sI "https://<target>" | grep -i "server:\\|cf-ray:\\|x-deployment"
# server: cloudflare                    → CDN
# cf-ray: <id>                          → Cloudflare
# x-deployment-id: <hash>               → Cloudflare Pages build ID

# 3. No .data / .rpc / _server endpoints work — all CDN-blocked
curl -s "https://<target>/route.data"       → 500 or 307 redirect to HTML
curl -s -X POST "https://<target>/_server"  → 500 ("Only HTML requests")
```

### What This Means for Exploitation

- Server functions in the JS bundle are **browser-only** — they call Supabase/backend from the user's browser
- TanStack Start build was done with static export / SPA mode (`ssr: false`)
- **No SSR exploitation path**: no server-side injection, no token extraction from server context
- The attack surface is the **client-side JS bundle** and the **separate backend API** (Supabase)
- The `.data` suffix and `/_server` endpoints do NOT work — rejected at the CDN edge

### Where to Pivot When CDN Static SPA

1. **Extract Supabase credentials from JS bundle** → try hitting Supabase directly
2. **Check if Supabase project DNS resolves** — if NXDOMAIN, project paused/deleted (see `references/supabase-backend-exploitation.md` § NXDOMAIN)
3. **Extract API keys, endpoints, auth patterns** from all chunk files
4. **Brute-force admin via the actual backend** (not the CDN frontend)
5. **Focus on bundle analysis** — the entire app architecture is in minified JS

### Real-World Example (ColibriSwap, July 2026)

```bash
$ curl -X POST https://colibriswap.com/panel-x7k9m2q3 \
  -H "Content-Type: application/json" \
  -d '{"email":"admin","password":"test"}'
{"error":"Only HTML requests are supported here"}  # Static CDN SPA confirmed

$ curl -sI https://colibriswap.com | grep -i "server:\\|cf-ray:\\|x-deployment"
server: cloudflare
cf-ray: a226351bcbea-SIN
x-deployment-id: 9c9029226b008b5abd06ab26fd6c1c91af8a653a3c63dc9b52b48dbb42a4ff18

# Confirmed: Cloudflare Pages static SPA. Server functions call Supabase from browser.
# Supabase NXDOMAIN → project paused. Attack surface narrowed to bundle analysis.
```
- **0x bytecode contracts**: Non-custodial aggregators use frontend only, no smart contract — funds never held; exploit must target backend/API. See `references/non-custodial-aggregator-audit.md` for full pivot sequence.