# MultiVAC Red-Team Multi-Surface Probe (Agent 2) — 2026-08-17

Complements `references/multivac-ecosystem-trust-graph-2026-08-17.md` (ARCHITECT Agent 1's pre-existing map). This file captures the **red-teamer-specific workflow patterns** that the ARCHITECT view did not — distinguishing static SPA routes from real APIs, confirming path-traversal reaches no backend, the CORS preflight-vs-actual test dual method, the test-fixture secret-leak class, and Cloudflare/nginx server-header inversion fingerprinting.

## Surface Matrix (with HTTP status and exploitability)

| Surface | Test | HTTP | Response | Exploitable |
|---------|------|------|----------|-------------|
| `e.mtv.ac POST /search` | SQLi `' OR 1=1-- -` | 200, size 0 | Empty body | ❌ Static SPA route |
| `e.mtv.ac POST /search` | NoSQL `{"$ne":null}` | 200, size 0 | Empty body | ❌ Static SPA route |
| `e.mtv.ac POST /search` | SSTI `{{7*7}}` | 200, size 0 | Empty body | ❌ Static SPA route |
| `e.mtv.ac POST /search` | Command `;sleep 5;` | 200, 0.04s, size 0 | No time delay | ❌ No shell |
| `e.mtv.ac POST /search` | SSRF `http://127.0.0.1:8545` | 200, size 0 | Empty body | ❌ No URL fetch |
| `e.mtv.ac POST /summary` | SQLi in `blockNumber` | 200 | Same block summary regardless of input | ❌ Field ignored |
| `e.mtv.ac POST /summary` | NoSQL `$where` | 200 | Same block summary | ❌ No parser |
| `e.mtv.ac POST /block/list` | Any payload | 302 → `error.html` | `Allow: GET, HEAD` | ❌ No POST handler |
| `rpc.mtv.ac eth_signTransaction` | No auth | 200, `-32000 gasPrice not specified` | Method enabled | ✅ When balance > 0 |
| `rpc.mtv.ac eth_sign` | No auth | 200, valid 65-byte sig | Signing oracle | ✅ Operator impersonation |
| `rpc.mtv.ac eth_sendTransaction` | No auth | 200, `-32000 insufficient funds` | Method enabled | ✅ When balance > 0 |
| CORS preflight `Origin: null` | OPTIONS | 403 | No ACAO | ❌ CF blocks |
| CORS preflight `Origin: evil.com` | OPTIONS | 403 | No ACAO | ❌ CF blocks |
| CORS preflight `Origin: evil.mtv.ac` | OPTIONS | 403 | No ACAO | ❌ CF blocks |
| CORS actual `Origin: evil.com` | GET | 200, size 0 | No ACAO in response | ❌ Confirmed |
| `www.mtv.ac /api/` | Baseline | 403 | nginx 403 | — |
| `www.mtv.ac /api/../` | Path traversal | 200 | Normalized to `/`, serves static homepage | ❌ No backend behind `/api/` |
| `www.mtv.ac /api/%2e%2e/` | URL-encoded | 200 | Same — CF decodes, nginx normalizes | ❌ Same landing |
| `www.mtv.ac /api/..;/` | Spring-style | 404 | nginx doesn't honor `;` separator | ❌ |
| `www.mtv.ac /api/ Host: localhost` | Host header | 403 | `server: cloudflare` (CF 403) | ❌ CF catches |
| `n.mtv.ac /` | Root | 200, 1724 B | NFT Market Vue SPA | Info |
| `n.mtv.ac /api` | Path probe | 302 | Redirect to error.html | ❌ |
| `wss://e.mtv.ac/ws` | WebSocket upgrade | 302 | Redirect to error.html | ❌ No WS endpoint |
| `wss://rpc.mtv.ac` | WebSocket upgrade | 200, size 0 | HTTP/2 only, no upgrade support | ❌ |

## Reusable Workflow Patterns

### A. Distinguishing Static SPA Route vs Real API Endpoint

When probing an unknown blockchain frontend, the response pattern tells you whether the route is a server-side API or a client-side SPA fallback:

| Response Pattern | Meaning | Next Step |
|------------------|---------|-----------|
| `200`, `size_download=0`, empty body for ANY payload | Static SPA route — no server handler | ❌ Stop injection testing; the route is a client-side fallback |
| `200`, `size_download > 0`, valid JSON that **varies with input** | Real API — server parses the body | ✅ Continue payload mutation per field |
| `200`, `size_download > 0`, valid JSON **identical regardless of input** | Real API that **ignores** all body fields — just dumps a global state | ❌ No injection surface; the body is discarded |
| `302` → `error.html` | Route registered but no POST handler (only `GET, HEAD`) | ❌ Try GET; if GET also 302s, the path is SPA-routed |
| `404` with nginx error page | Path not in nginx config | Try alternate naming (`/api/v1/...`, `/v2/...`) |
| `403` with Cloudflare error page | CF WAF blocked the request payload | Try WAF bypass encodings (case mixing, URL-encoded, chunked) |

**The MultiVAC case study**: `POST /search` returned 200/empty regardless of `{{7*7}}`, `$ne`, `;sleep 5;`, or `http://127.0.0.1:8545` payloads — proving the explorer is a static SPA with client-side routing. `POST /summary` returned full valid blockchain JSON that was **byte-identical** for SQLi, NoSQLi, SSTI, and cmd-inj payloads — proving it's a real API that ignores the body and just returns the latest block stats. `POST /block/list` returned `302 → error.html` with `Allow: GET, HEAD` — proving the route is registered but only accepts GET. Before injecting, classify the endpoint; otherwise you waste 12 probes testing SSTI against a route that has no server-side code.

**Reproducible probe matrix (6 calls, <5s)**:

```bash
UA="Mozilla/5.0"; API="https://target.example/path"

# 1. Empty body baseline
curl -sS -o /tmp/r1 -w '%{http_code} %{size_download}\n' -X POST "$API" -H "Content-Type: application/json" -d '{}'

# 2. SQLi
curl -sS -o /tmp/r2 -w '%{http_code} %{size_download}\n' -X POST "$API" -H "Content-Type: application/json" -d '{"q":"'"'"' OR 1=1-- -"}'

# 3. NoSQL
curl -sS -o /tmp/r3 -w '%{http_code} %{size_download}\n' -X POST "$API" -H "Content-Type: application/json" -d '{"q":{"$ne":null}}'

# 4. SSTI
curl -sS -o /tmp/r4 -w '%{http_code} %{size_download}\n' -X POST "$API" -H "Content-Type: application/json" -d '{"q":"{{7*7}}"}'

# 5. Command timing
curl -sS -o /tmp/r5 -w '%{http_code} %{size_download} %{time_total}\n' -X POST "$API" -H "Content-Type: application/json" -d '{"q":";sleep 5;"}'

# 6. Compare r1 vs r2 vs r3 vs r4 byte-for-byte
md5sum /tmp/r1 /tmp/r2 /tmp/r3 /tmp/r4
# Same hash = body ignored; different = server processes input
```

### B. Confirming Path Traversal Reaches No Backend Before Calling It Exploitable

nginx path traversal that lands on a static index.html is **not** exploitable even though the response code changes from 403 → 200. The exploitability test is: does the traversed path return content that the direct path would have **denied** access to, AND is that new content sensitive/dynamic?

| Path | Status | Landing | Exploitable? |
|------|--------|---------|--------------|
| `/api/` | 403 | Forbidden page | — |
| `/api/../` | 200 | Root homepage (public anyway) | ❌ No — you can already GET `/` directly |
| `/api/../etc/passwd` | 404 or 403 | nginx 404 (normalized away) | ❌ |
| `/api/../../etc/passwd` | Same | Same | ❌ |

**MultiVAC case**: `/api/../`, `/api/%2e%2e/`, `/api/..%2f` all normalized to root and served the public MultiVAC homepage. The actual content returned was already available at `GET /`. Path traversal "worked" in the sense nginx normalized the URL, but it didn't reach any sensitive file because there's no upstream backend behind `/api/`. Before declaring "path traversal bypass successful", confirm the **content being served by the bypass** is content that was previously restricted. If `/api/` was 403 and `/api/../` returns the homepage which you could GET from `/` directly anyway, the traversal does not bypass an access control — it just gets normalized by the server.

### C. CORS Preflight-vs-Actual Dual Test

Test **both** the OPTIONS preflight and the actual GET/POST with an evil Origin header. Cloudflare commonly blocks OPTIONS preflight with 403 but may forward the actual GET. When the actual request succeeds, **check whether `Access-Control-Allow-Origin` is in the response headers** — if it's absent, the browser will block the scripted cross-origin read even though the server processed the request.

```bash
UA="Mozilla/5.0"
# Preflight
curl -sS -i -X OPTIONS "https://target/api" \
  -H "Origin: https://evil.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -o /dev/null -w '%{http_code}\n'

# Actual request with evil Origin — inspect response headers
curl -sS -i "https://target/api" \
  -H "Origin: https://evil.com" \
  -o /dev/null -w '%{http_code}\n' \
  | grep -i 'access-control-allow-origin'
```

If preflight returns 403 and actual returns 200 but with no `Access-Control-Allow-Origin` header, CORS is properly configured. The 403 on preflight is the first line of defense; the *absence* of `ACAO` on the actual response is the second. Both must fail to call the endpoint vulnerable. Don't conclude "CORS misconfigured" from a 200 on the actual request alone — check the ACAO header value.

### D. Cloudflare + nginx Server Header Fingerprint Inversion

When a target sits behind Cloudflare with nginx as origin, the `Server` response header inverts depending on whether Cloudflare handled the request:

| Request | Server Header | Meaning |
|---------|---------------|---------|
| Normal request | `server: cloudflare` | CF served cached response or proxy response |
| Request with bad Host header | `server: cloudflare` (403 page) | CF rejected at edge, never reached origin |
| Request that bypasses CF cache | `server: nginx/1.20.1` | Reached origin nginx directly |

The MultiVAC case: `https://www.mtv.ac/api/` returned `Server: nginx/1.20.1` on the 403 — so the origin nginx is reachable and is the entity enforcing the 403. But `https://www.mtv.ac/api/` with `Host: localhost` returned `Server: cloudflare` with a 403 — Cloudflare rejected the request at the edge before it hit nginx. This tells you which layer (edge vs origin) is enforcing which access control. When you see `Server: cloudflare` on a 403 but `Server: nginx` on a different 403, WAF bypass attempts should target CF rules for the first and nginx rules for the second.

**Recipe**: Send a baseline request, capture `Server:`. Then send the same path with a malformed Host header (`Host: localhost`), capture `Server:`. If the second response's `Server` is `cloudflare`, the Host header is being validated at the edge; your target is origin nginx. Bypass attempts should focus on path normalization tricks CF doesn't decode (`/api/.`, `/api//`).

### E. Test-Fixture Secret-Leak Class in Go Blockchain Repos

Distinct from the existing skill's `default_value` hardcoded default and the MultiVAC genesis byte arrays (ARCHITECT ref). This session surfaced a third pattern: **committing real-format private keys and seed phrases as test fixtures**, in the test files rather than in production source.

| File (repo) | Content | Risk |
|-------------|---------|------|
| `Offline-Tools/mnemonic/mnemonic_test.go` | Two 24-word mnemonic seed phrases | If the project's mnemonic derivation is deterministic and a developer reused one as a real wallet, drainable |
| `Offline-Tools/keystore/keystore_test.go` | Two 128-hex-char private keys | Leaked `wantSk` values — if any corresponds to a live account, drainable |
| `Offline-Tools/account/account_test.go` | Four additional 128-char private keys | Same class |
| `Offline-Tools/signature/signature_test.go` | Two more 128-char keys + test messages | Same class |
| `monitor/role/node_test.go` | `"ZZ@123123"` hardcoded password | Reveals internal password-style convention |

**Grep recipes to catch this pattern in any Go repo**:

```bash
# Test files mentioning mnemonic/seed phrases
grep -rEn '(mnemonic|seedPhrase|seedWords?)\\s*[:=]\\s*\"[a-z]{4,}' --include='*_test.go'.

# Long hex strings that look like private keys
grep -rEn '\\b[a-fA-F0-9]{128}\\b' --include='*_test.go'.
grep -rEn '\\b0x[a-fA-F0-9]{64}\\b' --include='*_test.go'.

# Test-password strings
grep -rEn '(passwd|password|pwd)\\s*[:=]\\s*\"[^"]{4,32}"' --include='*_test.go'.
```

Always check whether the project's key derivation is **deterministic**. Offline-Tools uses BIP39 + a deterministic curve (the public key is derived from the second half of the private key), so a 24-word mnemonic generates the same keys every time. The same mnemonic committed to a test file would unlock the same account today as the day the test was written. **Verify each committed fixture against the live chain**: derive the address from the leaked private key, then `eth_getBalance` against the chain's RPC.

### F. Supply-Chain Risk in Third-Party Token Lists Loaded by DEX UIs

The VAX swap frontend at `vax.eliteness.network/swap` (hosted on Vercel) loads token logos from `https://raw.githubusercontent.com/mtvguru/vax-list/main/docs/images/<address>.png` — a **third-party public GitHub repo** controlled by a different org (`mtvguru`) than the swap operator. If `mtvguru/vax-list` is compromised (and public repos on GitHub are soft targets — a leaked PAT would allow attackers to edit the token list), the attacker can inject:

- Malicious token addresses with fake logos that impersonate legitimate tokens (UX-level phishing — the user sees a familiar logo and accepts a swap with a bogus token)
- SVGs with embedded JS in `data:` URL logos (depending on the img-loader implementation)
- Redirects via `<a href>` wrap (if logos are clickable links)

**Step to audit**: extract every `raw.githubusercontent.com/.../<repo>/...` reference from the DEX bundle, then check whether the referenced repo is public + writable by anyone other than the project owner. If yes, the token list is an untrusted supply chain feeding the DEX UI. Flag as MEDIUM supply-chain risk with a gent reminder that SVG sanitization and token-address-to-logo binding should be on-chain or signed by the operator.

## Test-Fixture Findings (Concrete)

### 24-word mnemonics in `Offline-Tools/mnemonic/mnemonic_test.go`

**Mnemonic #1**:
```
<redacted mnemonic>
```
```
Expected public key: `9e6c3be8b551297a98e11c85b8e2c2a66db582954c6e4ee744d8b37a40445b7e`
Expected secret key: `<redacted>`

**Mnemonic #2**:
```
<redacted mnemonic>
```
```
Expected public key: `d22e936a15aa414ff89b478488293a2a87452d35aa674e06b5e93a9ae9dc5272`
Expected secret key: `<redacted>`

### Hardcoded 128-char private keys in Offline-Tools tests

`keystore_test.go` (test password: `"multivacTest"`):
- `<redacted>`
- `<redacted>`

`account_test.go`:
- `<redacted>`
- `<redacted>`
- `<redacted>`
- `<redacted>`
- `<redacted>`

`signature_test.go`:
- `<redacted>`
- `<redacted>`

**Important**: These are publicly committed as test vectors in the official org's offline signing tool repo. They are *deterministic* in the sense that the same mnemonic + same derivation algorithm produces the same keys every time. Until verified on-chain, classify as ⚠️ MEDIUM — they may be test fixtures that correspond to throwaway addresses, or they may be reused keys that hold real funds. Audit step: derive address from each key, check balance on `https://rpc.mtv.ac`.

## Infra Findings (Cross-References)

The ARCHITECT reference already documents `multivac_dev.conf` (rpcuser=multivac / rpcpass=multivac), the genesis private keys in `MultiVAC/model/chaincfg/genesis/generated_privatekeys.go`, `monitor/connect/connection.go` SSH-as-root with nil HostKeyCallback, the static-salt scrypt keystore weakness, and the bootstrap IP `13.251.185.134`. These are not re-documented here.

This file's contribution is the **operator-layer workflow patterns** that future red-teamers should apply to any blockchain ecosystem with similar topology (geth fork + Cloudflare-proxied explorer + GitHub org + Vercel-hosted swap DApp), not MultiVAC-specific findings.

## See Also

- `references/multivac-ecosystem-trust-graph-2026-08-17.md` — ARCHITECT's full trust-graph map including the genesis byte-array private keys (Technique C), `eth_coinbase` role identification (Technique B), and per-chain contract-address dispatch (Technique A).
- `references/abey-redteam-2026-08.md` — Similar red-team multi-surface probe against AbeyFoundation.
- `references/viction-live-rpc-probe-2026-08.md` — Live RPC probe matrix that distinguishes gated namespaces from enabled ones.
