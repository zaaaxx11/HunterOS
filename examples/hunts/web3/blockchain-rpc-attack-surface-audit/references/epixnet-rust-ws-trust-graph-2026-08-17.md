# EpixNet Rust WS Command-API Trust Graph — 2026-08-17

Source tree: `/root/epixnet-src/EpixNet-main/crates/epix-ui/src/` + `crates/epix-node/src/`
Methodology: `blockchain-rpc-attack-surface-audit` 4-phase workflow applied to a Rust WS command API.
Output: 8 trust boundaries mapped, 4 bypass vectors identified, full file:line evidence.

## 0. Architecture

EpixNet is a Rust rewrite of ZeroNet-like P2P publishing. Each "xite" (site) is signed content-addressed data kept in `<data_root>/data/<address>/`. The UI server (`epix-ui`) is an axum HTTP + WebSocket server bound to `127.0.0.1:42222` by default (`node/lib.rs:52 DEFAULT_UI_ADDR`). A public-reverse-proxied deployment sets `ui_restrict=true` in config.json.

The command API lives at `/EpixNet-Internal/Websocket?wrapper_key=<xite address>` and dispatches per-connection `WsSession` through a `CommandRegistry`. A parallel Unix domain socket (`admin.sock`) provides a `trusted` operator channel.

## 1. Dispatch & Auth Model

### Entry points (per-connection)
| Channel                | Reachable by                              | `session.trusted` | Notes                                  |
|------------------------|-------------------------------------------|-------------------|----------------------------------------|
| UI HTTP/WS 127.0.0.1   | Any process on the loopback host          | false             | Default (`DEFAULT_UI_ADDR` node/lib.rs:52) |
| UI HTTP/WS LAN/public  | Anyone reachable on the bind IP           | false             | Requires operator-set `ui_ip` or explicit bind override |
| Admin Unix socket      | Local process w/ filesystem access to data dir | **true**  | `spawn_admin_socket` (lib.rs:237-343); mode 0600; `admin.sock` (or 0700 fallback on network-share data roots) |
| WS API via gateway     | Internet (reverse-proxy fronted)          | false             | Only if `ui_restrict=true` set by operator |

### Gate 1 (command.rs:340-360) — admin-command dispatch
`is_admin_command(cmd)` consults `ADMIN_COMMANDS` (command.rs:21-91). On a restricted gateway (command.rs:339 `restrict = state.ui_restrict() && !session.trusted`), admin commands are refused UNLESS on `GATEWAY_READ_COMMANDS` (command.rs:118-132). On a non-restricted node, admin is allowed if ANY of:
- `session.trusted == true`  (only the Unix admin socket)
- `req_id >= WRAPPER_ID_BASE` (≥ 1_000_000)  — **client-supplied, unverified** (lib.rs:3170)
- bound xite `state.xite_has_admin(addr)`  (state.rs:7540)

### Gate 2 (command.rs:365-375) — write-ownership under restrict
`WRITE_COMMANDS` (fileWrite, fileDelete, siteSign, sitePublish, certAdd) require `state.xite_owned(addr)` ONLY when `restrict` is true. On a non-restricted node, there is NO server-side ownership check on these commands.

### Gate 3 / Gate 4 (command.rs:381-413) — plugin and NoNewSites
ConfigSet/ConfigList require `UiConfig` plugin enabled; pluginConfigSet/pluginList require `UiPluginManager` enabled; `NoNewSites` blocks NEW_XITE_COMMANDS / DELETE_XITE_COMMANDS when set. All gated by `!session.trusted` — the admin socket bypasses all of them.

### Metacommand `as` (command.rs:418-448)
Rebinds `session.xite` to `target`, re-enters dispatcher. `caller_elevated = session.trusted || req_id >= WRAPPER_ID_BASE || xite_has_admin(self.xite)`. Inner id is `req_id.max(WRAPPER_ID_BASE)` when caller is elevated — the rebound session INHERITS the forged id.

## 2. Eight Trust Boundary Crossings  (file:line evidence)

### TB-1  Client-supplied `req_id` as admin auth  (HIGH)
- `command.rs:16` `const WRAPPER_ID_BASE: i64 = 1_000_000;`
- `command.rs:351` `let elevated = session.trusted || req_id >= WRAPPER_ID_BASE;`
- `lib.rs:3170` `let id = req.get("id").and_then(|v| v.as_i64()).unwrap_or(0);`  — source of `req_id`, no integrity check
- No shared secret / HMAC / signature binds `id` to the wrapper chrome. Any client that knows the convention can claim admin.

### TB-2  wrapper_key == public xite address  (HIGH)
- `lib.rs:2968-2972` `WsQuery { wrapper_key, xite }` — query string
- `lib.rs:2992-2994` `let xite = match q.wrapper_key.or(q.xite) { Some(key) => Some(ctx.state.canonical_key(&key).await), None => None };`
- `state.rs:2787-` `canonical_key` resolves a `.epix` name to bech32 address; returns input unchanged for unknown names. No secret checked.
- "Authentication" is purely the bind; authorization is Gate 1 (id elevation / xite_has_admin).

### TB-3  `is_ws_origin_allowed` allowlist any loopback Origin satisfies  (MEDIUM)
- `state.rs:14293-14302`
```
if origin_host.is_empty() || origin_host == request_host { return true; }
let host_only = origin_host.split(':').next().unwrap_or(origin_host);
if host_only == "127.0.0.1" || host_only == "localhost" || host_only == "[::1]" { return true; }
self.allowed_ws_origins.lock().unwrap().contains(origin_host)
```
- Any `Origin` whose host is loopback ⇒ WS upgrade accepted. Same-origin guarantee for browsers, but NOT an auth layer for non-browser clients (curl, scripts).

### TB-4  `as` metacommand rebinds + inherits forged id  (HIGH when combined with TB-1)
- `command.rs:446` `let rebound = WsSession::new(session.state.clone(), Some(target));`  (NOT trusted)
- `command.rs:447` `let inner_id = if caller_elevated { req_id.max(WRAPPER_ID_BASE) } else { req_id };`
- `command.rs:448` re-enters `self.dispatch(&rebound, &inner_cmd, &inner_params, inner_id)`
- Combined with TB-1: forged `id ≥ 1M` ⇒ `caller_elevated` ⇒ rebind to ANY served xite, inner admin commands run with `id ≥ 1M`.

### TB-5  `permissionAdd` self-grants ADMIN with no server-side gate  (HIGH)
- `command.rs:46-49` comment: "permissionAdd is intentionally NOT admin-gated (matches EpixNet): a xite grants itself a permission after the user confirms it in the wrapper, over its own non-admin WS."
- `command.rs:3115-3134` `permissionAdd` impl — takes `permission: &str` from params, calls `state.add_permission(address, permission)`.
- `state.rs:7484-7506` `add_permission` — no validation, no denylist, no confirm-token check, just `x.settings.permissions.push(permission.to_string())` + persists to `permissions.json`.
- `state.rs:7540-7547` `xite_has_admin` checks `x.settings.permissions.iter().any(|p| p == "ADMIN")` ⇒ Gate 1's third arm passes.
- On `ui_restrict=true` gateway: `permissionAdd` is NOT in ADMIN_COMMANDS, so Gate 1's admin path never runs and the command always succeeds. The grant persists to `permissions.json` — latent privilege plant that activates if `ui_restrict` ever turns off.
- `ADMIN_COMMANDS` list explicitly omits `permissionAdd` (see comment command.rs:46-49). The omission is BY DESIGN but the server does not enforce the wrapper-confirmation invariant.

### TB-6  `dbQuery` not admin-gated, runs local SQLite  (INFO — SSRF NEGATIVE)
- `command.rs:1474-1497` `DbQuery` — reads `query` and `params` from params, calls `state.db_query(address, query, &params)`.
- NOT in `ADMIN_COMMANDS`. NOT in `WRITE_COMMANDS`. Allowed on restricted gateways.
- `state.rs:5986-6024` `db_query` — purely local SQLite (`db.query_value(query, params)`). No URL/host parsing, no outbound dial.
- SSRF verdict: NEGATIVE. Data-exfil scoped to the bound xite's own schema. Cross-xite reads gated by `resolve_target` → `Cors:`/`Merger:` permission checks (command.rs:210-216).

### TB-7  `chartDbQuery` admin-gated AND on GATEWAY_READ_COMMANDS
- `command.rs:26` (ADMIN_COMMANDS), `command.rs:122` (GATEWAY_READ_COMMANDS). On a restricted gateway, any visitor may invoke it.
- `state.rs:7562-7564` `chart_query` → `chart.query(sql, params)` — underlying chart DB query helper not reviewed in `epix-db`. Worth checking whether it enforces SELECT-only. If it accepts DDL/DML, this is a public-gateway SQL injection / data manipulation primitive.

### TB-8  `serverPortcheck` — read-only, NOT SSRF
- `command.rs:128` (GATEWAY_READ_COMMANDS), `command.rs:1185-1197` impl — params ignored, polls cached UPnP port status via `state.port_status()`. No external address supplied by client. Not an SSRF surface.

## 3. security_gate analysis (lib.rs:404-464)

Order: `host_allowed` → `OPTIONS` preflight → `unsafe_method_is_same_origin` → conditional `is_cross_origin_request`.

### `host_allowed` (lib.rs:486-505)
- empty Host ⇒ true (HTTP/1.0)
- `localhost` / IP literal ⇒ true (DNS-rebinding safe)
- `.epix` names and bare `epix1…` proxy hosts ⇒ true (lib.rs:661-664 `is_proxy_host`)
- operator `ui_host` config ⇒ per-line list (state.rs reads `config_get("ui_host")`)

### `unsafe_method_is_same_origin` (lib.rs:474-482)
- `Sec-Fetch-Site: same-origin|none` ⇒ accept (browser-set, unforgeable)
- else `Origin` compared to `Host` via `url_is_same_host`
- **else `None ⇒ true`** (lib.rs:480-481) — non-browser clients (curl, scripts) omit both headers and are treated as same-origin. Explicitly justified in lib.rs:470-473 as "non-browser clients have no ambient credentials to abuse." Per-handler CSRF tokens close the gap for actual state-changing routes (config, plugins, backup, logout).

### `is_cross_origin_request` (lib.rs:516-568)
- `sec-fetch-mode: navigate` ⇒ not cross-origin (user nav)
- `/StatsJson` ⇒ not cross-origin (public gateway stats)
- `origin.is_none() && referer.is_none() && !is_public_ui_path(path)` ⇒ cross-origin (untraceable)
- `Origin` host != request host ⇒ cross-origin
- Same-xite requests pass; cross-xite needs `Cors:<target>` permission on the source xite

### `ui_check_cors` default-off for non-loopback (state.rs:4244-4249) — MEDIUM
- `match config_get("ui_check_cors") { Some(v) => v.as_bool, None => *self.ui_loopback.read().await }`
- A LAN-bound node (operator `ui_ip=0.0.0.0`) defaults `ui_check_cors = false` ⇒ cross-origin xite-content reads (enumeration of which xites are served) are permitted. Unsafe-method CSRF check still runs unconditionally so state changes are still gated.

## 4. Admin Unix socket (lib.rs:236-343, node/lib.rs:2496)
- `spawn_admin_socket(data_root/admin.sock)` (node/lib.rs:2496). Unix domain socket, mode 0600 (lib.rs:332). NOT remotely reachable.
- Connection handler `WsSession::new_trusted` (lib.rs:382) dispatched with `id = i64::MAX` (lib.rs:385) — clears every gate.
- Network-share fallback (lib.rs:262-303): if data root is on SMB/NFS, socket relocates to `XDG_RUNTIME_DIR` or `$HOME/.cache/epix-admin-<hash>/admin.sock` in a 0700 re-owned dir. The path is recorded in `admin.sock.path` next to the data root — a writable share can swap it (symlink attack, equivalent to existing filesystem compromise).

## 5. Restricted gateway (ui_restrict=true) command tiers

| Tier | Commands                                              | Reachable from |
|------|-------------------------------------------------------|----------------|
| Non-admin (always allowed, not in ADMIN_COMMANDS) | `dbQuery`, `fileGet`, `fileRules`, `fileNeed`, `optionalFileInfo`, `channelJoin/Allsite`, `permissionAdd`, `corsPermission`, `feedItemQuery`, `xidResolve`, etc. | Public visitor |
| GATEWAY_READ_COMMANDS (admin but safe for public) | `announcerStats`, `channelJoinAllsite`, `chartDbQuery`, `chartGetPeerLocations`, `feedQuery`, `feedSearch`, `notificationCount`, `notificationQuery`, `optionalLimitStats`, `serverPortcheck`, `sidebarGetHtmlTag`, `sidebarGetPeers`, `siteList` | Public visitor |
| Admin (refused on gateway) | `siteDelete`, `siteAdd`, `configSet`, `userSet`, `certSet`, `serverShutdown`, `serverUpdate`, `userShowMasterSeed`, `siteRecoverPrivatekey`, etc. | Server-side only (admin socket) |
| WRITE_COMMANDS (require `xite_owned` on gateway) | `fileWrite`, `fileDelete`, `siteSign`, `sitePublish`, `certAdd` | Owner of the bound xite only |

Crucial: `permissionAdd` is in the FIRST tier (non-admin), so the TB-5 latent-plant issue applies on a gateway: any visitor can grant ADMIN to a xite they bind to. The grant doesn't help them ON the gateway (Gate 1's admin arm is refused outright before the `xite_has_admin` check at command.rs:348-359), but the grant persists and activates on a later switch to a non-restricted deployment.

## 6. Summary matrix

| # | Class                | Severity | Remote-gateway? | Remote-LAN? | Loopback-only? | Code anchor |
|---|----------------------|----------|------------------|-------------|----------------|-------------|
| BP-1 | forged req_id admin | HIGH     | blocked by restrict | YES if restrict unset | YES | command.rs:351, lib.rs:3170 |
| BP-2 | permissionAdd self-grant | HIGH on loopback/LAN, LATENT on gateway | persistence-only | YES | YES | command.rs:3115, state.rs:7484 |
| BP-3 | `as` rebinds + inherits id | MEDIUM (needs BP-1) | blocked | YES | YES | command.rs:446-448 |
| BP-4 | ui_check_cors default off | MEDIUM (info disclosure) | YES (reads) | YES | no | state.rs:4244, lib.rs:457 |
| — | dbQuery SSRF | INFO (NEGATIVE) | n/a | n/a | n/a | state.rs:5986 |
| — | admin socket | INFO (NEGATIVE) | remote-blocked | remote-blocked | filesystem-only | lib.rs:236-343 |

## 7. Suggested code-level mitigations

1. **BP-1**: bind admin elevation to a per-session HMAC token issued by the wrapper (server-held secret via a bootstrap POST), not to a client-supplied integer.
2. **BP-2**: denylist `permissionAdd` against the literal `"ADMIN"` when the connection is not `session.trusted`; OR require a server-issued confirmation nonce that the wrapper must include.
3. **BP-3**: when `as`'s caller is NOT trusted, force `inner_id = min(req_id, WRAPPER_ID_BASE - 1)` to deny the cross-xite escalation primitive.
4. **BP-4**: when `ui_loopback == false` and `ui_restrict == false`, default `ui_check_cors` to TRUE (inverse of today's default). A non-loopback bind without restrict is already a privileged multi-client deployment.

## 8. Pitfalls observed during this audit

1. **Reading the dispatch comments as enforcement.** The comment at command.rs:46-49 says permissionAdd is unadmin-gated "after the user confirms it in the wrapper." A passive read accepts that as a control. The control is the wrapper UI, which a non-wrapper client bypasses entirely — confirm by reading `state.add_permission` (state.rs:7484) and confirming there is no server-side check.
2. **Treating `id >= 1M` as wrapper-only because "only the wrapper sends that."** The constant is in open-source code (`WRAPPER_ID_BASE = 1_000_000`, command.rs:16). Anyone reading the repo knows it. It is not a secret.
3. **Stopping the trust graph at Gate 1.** The `as` metacommand's `inner_id = req_id.max(WRAPPER_ID_BASE)` (command.rs:447) means Gate 1's check on the inner command passes trivially — the metacommand is a separate boundary, not just a re-dispatch.
4. **Assuming `ui_restrict` defaults to true.** It does not — `state.rs:1811-1816` defaults FALSE. A loopback-bound node never sets it; a misconfigured LAN-bound node that doesn't set it is fully admin-pwnable by anyone reachable on the bind. Document the deployment invariant explicitly.
5. **Missing the latent-privilege-plant angle on gateways.** `permissionAdd` runs even when `ui_restrict=true` (not in ADMIN_COMMANDS ⇒ Gate 1 doesn't refuse it) and persists to `permissions.json`. The grant doesn't help on the gateway but activates if `ui_restrict` ever turns off — long-dormant privilege escalation.
