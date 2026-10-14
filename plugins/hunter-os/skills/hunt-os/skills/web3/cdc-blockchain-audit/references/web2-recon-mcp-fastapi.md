# Web2 Recon for Blockchain Targets: Docs-MCP Oracle, FastAPI Probes, Metrics Mining

Distilled from the Cantor8 (Canton Network) full-surface audit. Use when the marketing
site is static and the real attack surface hides behind docs/identity/scanner services.

## 1. The docs-as-oracle cascade (worked top-to-bottom)

Static marketing site (Webflow etc.) = dead end for RCE. Pivot chain that works:

1. Subdomain enum (`dig +short <sub>.<domain>` over a ~80-word infra list: docs app api
   wallet id auth sso scan scanner collector metrics exchange support admin …) + crt.sh.
2. Fetch every docs host. Frame-redirects reveal real hosts
   (`docs.X` → `<frame src="https://public-docs.vercel.app/...">`).
3. Mintlify docs → fetch `/.well-known/mcp/server-card.json`, `/.well-known/agent-card.json`.
   Mintlify exposes an **unauthenticated JSON-RPC MCP endpoint at `/mcp`** with tools like
   `search_*` and `query_docs_filesystem_*` (shell-like: rg/cat/head/awk/jq/sed over all .mdx).
4. Use that tool to mine the FULL docs tree for live backend URLs:
   `rg -io 'https?://[a-z0-9./_-]+' / | sort | uniq -c` — this is how internal hosts
   (`wallet-backend.main.digik.X.tech`, `id.X.tech`, scanner/collector services) surface.
   Also read deployment/docker-compose pages: they leak env var names, backend URLs,
   auth modes (e.g. `AUTH_TYPE=noop` option), and which env needs no signup coupon.

MCP call template (initialize first, then tools/call; responses are SSE `data:` frames):

```python
import json, urllib.request, re
def mcp(cmd):
    payload={"jsonrpc":"2.0","id":1,"method":"tools/call",
      "params":{"name":"query_docs_filesystem_<site>","arguments":{"command":cmd}}}
    req=urllib.request.Request("https://<sub>.mintlify.app/mcp",
        data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    body=urllib.request.urlopen(req,timeout=40).read().decode(errors='ignore')
    m=re.search(r'"text":"((?:[^"\\]|\\.)*)"',body)
    return m.group(1).encode().decode('unicode_escape',errors='ignore') if m else body
```

## 2. Mintlify MCP sandbox: awk coproc bypass (PROVEN technique)

`query_docs_filesystem` claims "in-memory virtual FS, nothing runs on any machine."
Reality on at least one deployment: real bash jail (pid=1, read-only FS, no net, no
secrets). Injection handling: `;id`, `$(id)`, backticks reach bash but `system()`-class
calls are filtered. **Bypass: awk coproc is NOT filtered**:

```
awk "BEGIN{\"head /etc/hostname\" | getline x; print x}"
jq -n "env"        # env dump works too
```

Contained impact (read-only, no egress, no /proc) but a real code-exec primitive and a
false-security-claim finding. Report pattern: CWE-78 mitigated by sandbox; severity
depends on what shares the jail. Always test: `id`, `ls -la /`, `cat /etc/passwd`,
`/dev/tcp` egress, secrets in env.

## 3. FastAPI/uvicorn fingerprint → spec-driven probing

`server: uvicorn` header ⇒ probe in this order:

```
/docs /redoc /openapi.json /healthz /metrics /api/metrics
```

- `/openapi.json` on a wallet backend = full endpoint inventory + per-op `security`
  flags + request schemas. Diff it against the PUBLIC documented API (e.g. GitHub Pages
  spec) — endpoints in live spec but not public docs (and vice versa) are the gaps.
- `/api/metrics` (Prometheus) is a recon goldmine when public: grep label values
  `path="..."` / `endpoint="..."` → reveals REMOVED/hidden routes (`/api/admin`,
  `/api/accounts/recovery_v3`), real party/account IDs, internal users
  (`validator-backend@clients`), JWT issuers, upstream services. Removed-route names
  tell you where account-recovery logic USED to live — hunt it on other envs.

## 4. Declared auth ≠ enforced auth (highest-value check)

Scanner service spec declared `security: [httpAuth]` on every path — server enforced
NOTHING. Result: 19MB `/contracts/active` dump + full tx history endpoints, no auth.

**Always:** for every spec-listed endpoint, fire one unauthenticated request. 401/403 =
enforced; 200 with data = finding. Spec security blocks are aspirations, not controls.
Also re-test `000`/timeout responses once — flaky hosts, not auth.

## 5. JWT verified-negative checklist (don't retest on same target)

All → uniform 401 `Invalid or expired token` = well-pinned verifier:
- alg=none; garbage token; RS256 with bad signature
- RS256→HS256 confusion keyed with (a) JWK-JSON string, (b) raw modulus from public JWKS
- unknown kid (forces JWKS refetch path); duplicate/comma-separated Authorization headers
- SQLi `' OR 1=1--` on query params (parameterized = clean `{"exists":false}`)

Uniform error text for missing vs bad token = no oracle. `debug=False` confirmed when
malformed bodies (deep nesting, wrong types, %00) yield 422/500 with NO traceback.

## 6. Auth architecture notes that matter for chaining

- Two token classes (`user` vs `_m2m` suffixed routes) = two issuers often BOTH accepted.
  m2m tokens may move funds for ARBITRARY parties by design — one m2m token = total theft.
  Class-confusion (user token on `_m2m` route) is the test; needs any valid token first.
- Token-issuance choke point: if the IdP host only exposes `/.well-known/jwks.json` +
  `/health` (no /token, /authorize), the issuance flow lives in the mobile app —
  decompile the APK (package id leaks via `/api/config/version_v2` store links).
- Client-chosen idempotency keys (`command_id`, `request_id`) on fund-moving prepares
  = double-execution/race candidates; batch endpoints amplify.
