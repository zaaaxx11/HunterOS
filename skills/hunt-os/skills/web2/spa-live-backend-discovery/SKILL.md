---
name: spa-live-backend-discovery
description: "CDP-driven discovery of the real API base behind an SPA"
metadata:
  version: 1.0.0
  hermes:
    tags: [web2, spa, cdp, network-capture, api-discovery, recon, nextjs, backend-host]
    category: security
---

# SPA Live Backend Discovery (CDP Network Capture)

## Why this skill exists (2026-09 ed3.xyz lesson)
Born from a 2026-09 hunt where a subdomain-fleet Next.js SPA (ed3.xyz) 404'd every
guessed backend and the real one (`user.<d>.xyz`) surfaced only when the app itself
was loaded in a controlled browser and its own outbound requests were captured —
the app knows its backend; static guesses do not.
(Full origin preserved at examples/hunts/web2/spa-live-backend-discovery/ed3-origin.md)
## Core rule
**Route-based 404 (`Cannot GET /health`) ≠ host down.** An Express/Node host can be 100% up
and serving the SPA fallback while having zero routes for the path you probed — the real API
lives on a DIFFERENT subdomain the app actually calls. The authoritative answer is the app's
own outbound requests. When your guessed hosts all return "Cannot GET", stop guessing and go
capture live network traffic.

## Workflow

### 1) Read the runtime multi-env config from the bundle FIRST (free, fast)
SPAs ship an env-config object. Extract it before any host probing:
```bash
grep -oE '\{"config":\{"default":"[^"]*","dev":"[^"]*","staging":"[^"]*"[^}]*\}' app.js
# {"config":{"default":"staging","dev":"https://api-dev.<d>","staging":"https://api-staging.<d>","prod":"https://api.<d>","launchpad":{...}}}
```
- `config.default` selects which env is live. Each key (`api`/`launchpad`/`utility`/`user`)
  is a **separate backend subdomain** — the SPA fans out across many hosts, not one.
- Distinguish them: launchpad→`launchpad.*`, quest/points→`user.*`, marketplace→`utility.*`.

### 2) Extract the API route-constant object (endpoint name map)
SPAs ship endpoint names as one object:
```bash
grep -oE '\{[^}]*GET_[A-Z_]+:"/[a-z0-9/_-]+"[^}]*\}' app.js
# {GET_TASKS_DATA:"/score/details",GET_USER_POINTS:"/score/user",GET_ALL_SEASON:"/season",
#  VERIFY_USER_WALLET_CONNECTION:"/auth/login",REGISTER_REFERRAL:"/refer/wallet",...}
```
These SHORT paths (`/score/details`, `/score/status/{wallet}?season=N`) are the real routes on
the backend host. Test them with correct JSON on EACH candidate subdomain — 500-with-app-JSON
(`{"error":"..."}`) = the route exists on THAT host.

### 3) DESTINY: capture real network via CDP (the definitive step)
Load the SPA in a browser you drive and record `Network.requestWillBeSent` / `responseReceived`.
This shows the exact backend hosts + routes the app uses, eliminating all guesswork.

**Launch a browser you control** (browser-use harness often reports "Chrome isn't running" — drive your own):
```bash
google-chrome-stable --headless=new --no-sandbox --disable-gpu \
  --remote-debugging-port=9222 --remote-allow-origins=* \
  --user-data-dir=/tmp/chrome-prof about:blank &
```
- `--remote-allow-origins=*` is MANDATORY — without it the websocket handshake 403s with
  `Rejected ... use --remote-allow-origins=*` and you'll burn time debugging the wrong layer.
- Verify: `curl http://localhost:9222/json/version` → `"Browser": "Chrome/..."`.

**Capture (python `websocket-client`):** connect to a page `webSocketDebuggerUrl`, and to match
`--remote-allow-origins=*` send the websocket with header `{"Origin":"http://localhost:9222"}`:
```python
import json, urllib.request, websocket
pages = json.loads(urllib.request.urlopen("http://localhost:9222/json").read())
ws = websocket.create_connection(
    [p for p in pages if p['type']=='page'][0]['webSocketDebuggerUrl'],
    header={"Origin":"http://localhost:9222"})
# send Page.enable, Network.enable, Page.navigate {url: TARGET}
# collect every Network.requestWillBeSent url containing the org domain
```
Loaded `https://ed3.xyz/` fired `user.<d>/season?chainId=NaN&onlyActive=true`,
`utility.<d>/utility`, `utility.<d>/staticType/all`, `api.<d>/chainBlockByPriority` — the real
hosts + routes. Static grep showed `api-dev` in the config, live capture showed `user`/`utility`
were the ones actually called. That gap is the whole point.

### 4) Points/quest gate honesty
Points-acquisition endpoints (mutating `POST /score`) often exist but are **gate-filtered**, not
auth-bypassed. Distinguish a real bypass from a gate:
- `GET /season` (all) vs `GET /season?onlyActive=true` (server-side filter). If the filtered query
  returns `data:[]` and all seasons have END dates in the past, the mutator answers
  `{"success":false,"error":"No active seasons found"}` — the gate holds, point inflation BLOCKED.
- Task scoring needing real on-chain verification (`buyToken`/`createCollection`) = not free-claim.
- **Referral ID generation is often the unauth survivor** (`GET /refer/generateId/{wallet}` → 201,
  any wallet, no ownership proof) — report THAT as unauth surface, not "unlimited points claim."
- Honest verdict format: `[Trigger → Effect → Trust Boundary] + Exploitable vs Blocked + curl evidence`.

## Pitfalls
- **`/health` 404 on every candidate ≠ all down.** Express `Cannot GET` = host up, route absent.
  The real API is on a subdomain you haven't matched yet. Go capture live network.
- **`GET_POINTS_VALUE:"/score"` is a route prefix, not necessarily a host.** `POST /score` mutating /
  `GET /score/{wallet}` read / `GET /score/details?season=` read — same constant feeds several verbs
  and sub-routes. Test verb+verb-suffix combos on the right subdomain, not just the bare constant.
- **500-with-app-JSON is the "route exists here" oracle**, not the 404-Express body.** `{"error":"req.body.data is not iterable"}` proves the route + a schema, so refine the body.
- **`config.default` is the truth for which env is live** — don't size up all 5 subdomain options;
  the SPA already picked one. Read the config line, then confirm with capture.
- **`name()`/`symbol()`/ERC-165/metadata `GET` on every EVM facet is expected noise** — supportsInterface
  `name`/`symbol` are view functions that succeed on ANY path; don't count them as findings.
- **SNI/User-Agent gating:** python urllib bare UA gets 403 on chunks; always `Mozilla/5.0`. Some
  CDN frontends need `-H "Referer: https://<app>/"` on API calls too.
- **Don't confuse the dying route list in `/health` with real dead infra** — the SPA is not dead
  just because one guessed API subdomain 404s.

## References
- `examples/hunts/web2/spa-live-backend-discovery/ed3-xyz-unauth-ipfs-upload-2026-09.md` — ed3.xyz
  case session. (An earlier bullet pointed at a file that never existed — removed 2026-09-07 cull.)

## Related
- `web2-spa-recon`, `web2-attack-surface-audit`, `js-secret-scanner` — static bundle/direct-host
  analysis; this skill is the DYNAMIC complement (execute the app to learn its own backend).
  Those three are user-owned (protected); recommend `hermes curator adopt` to enable edits.