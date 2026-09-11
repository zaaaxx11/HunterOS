# EpixNet Gateway Command Taxonomy — Architect Pass (2026-08-17)

Source: `command.rs` lines 1-465, `state.rs`, `lib.rs` — EpixNet Rust node v0.4.17.
Cross-references the F1-F9 red-team findings in `epixnet-ui-redteam` skill.

## Complete command gate lists

### GATEWAY_READ_COMMANDS (command.rs:118-132)
```
announcerStats, channelJoinAllsite, chartDbQuery, chartGetPeerLocations,
feedQuery, feedSearch, notificationCount, notificationQuery,
optionalLimitStats, serverPortcheck, sidebarGetHtmlTag, sidebarGetPeers,
siteList
```
= 13 commands. These are the ONLY admin commands that execute on a
`ui_restrict=true` gateway. All other admin commands are refused with
`"{cmd} is disabled on this gateway"` (command.rs:346).

### WRITE_COMMANDS (command.rs:109-110)
```
fileWrite, fileDelete, siteSign, sitePublish, certAdd
```
= 5 commands. On restricted gateway, require `xite_owned(addr)` (line 365-374).

### NEW_XITE_COMMANDS (command.rs:99)
```
siteAdd, siteClone, mergerSiteAdd
```
Blocked by `no_new_xites()` (line 396-405).

### DELETE_XITE_COMMANDS (command.rs:103)
```
siteDelete, mergerSiteDelete
```
Blocked by `no_new_xites()` (line 406-413).

### ADMIN_COMMANDS (command.rs:21-91)
70 commands total. KEY: `permissionAdd` is intentionally EXCLUDED (comment
line 46 — "permissionAdd is intentionally NOT admin-gated"). All 70 are
listed in the red-team skill.

## Dispatch gate order (command.rs:335-465)

```
restrict = ui_restrict() && !session.trusted
(On gateway WS: trusted=false via WsSession::new, so restrict = true)

1. Admin gate (line 340):
   if is_admin_command(cmd):
     if restrict:
       if cmd not in GATEWAY_READ_COMMANDS → Err (blocked)
     else:
       elevated = trusted || req_id >= 1_000_000
       has_admin = xite_has_admin(session.xite)
       if !elevated && !has_admin → Err (blocked)

2. Write gate (line 365):
   if restrict && cmd in WRITE_COMMANDS:
     owns = xite_owned(session.xite)
     if !owns → Err (blocked) + push_notification

3. Plugin config gate (line 381-392):
   configSet/configList → need UiConfig plugin enabled
   pluginConfigSet/pluginList → need UiPluginManager plugin enabled

4. NoNewSites gate (line 396-413):
   if cmd in NEW_XITE_COMMANDS && no_new_xites → Err
   if cmd in DELETE_XITE_COMMANDS && no_new_xites → Err

5. `as` command (line 418-448):
   caller_elevated = trusted || req_id >= 1M || xite_has_admin(session.xite)
   allowed = caller_elevated || session.xite == target
   rebound = WsSession::new(state, Some(target))  ← trusted=FALSE
   inner_id = if caller_elevated { req_id.max(1M) } else { req_id }
   → re-dispatch(rebound, inner_cmd, inner_params, inner_id)

6. Plugin enabled gate (line 451-454):
   if cmd belongs to a plugin and plugin disabled → return Null

7. Fallback (line 456-463):
   if command not registered → return Null (no error)
```

## New findings from this Architect pass

### F10 — certSelect: non-admin identity swap

- `certSelect` (command.rs:3808-3839): NOT in ADMIN_COMMANDS, NOT in
  WRITE_COMMANDS. Executes freely on restricted gateway.
- Calls `s.state.cert_set(domain)` — same as admin-gated `certSet` but
  without the admin gate.
- `cert_set` (state.rs:6154-6157) calls `user.set_cert_global(d)` +
  `save_user()` → changes global selected identity.
- Only selects from already-stored certs (can't ADD new without certAdd,
  which IS write-gated on restricted gateway). But if operator has ANY
  stored cert, attacker can switch to it.
- **Chain**: certSelect → swap auth_address → bigfileUploadInit (also
  non-admin/non-write) passes internal is_signer check (state.rs:7115-7128)
  if new auth_address is a signer on target content.json.

### F11 — Non-admin/non-write command matrix on restricted gateway

Commands that pass ALL gates on `ui_restrict=true` gateway:

| Command | Risk | Notes |
|---|---|---|
| permissionAdd | CRITICAL (F2) | Grants ADMIN, persists |
| permissionRemove | BLOCKED | In ADMIN_COMMANDS (line 51) |
| certSelect | MEDIUM (F10) | Identity swap |
| certXid | Medium | xID identity flow |
| fileGet | HIGH | Read any file in any served xite |
| dbQuery | CRITICAL | ATTACH DATABASE, arbitrary SQL |
| bigfileUploadInit | Medium | Internal own/signer check at state.rs:7115 |
| optionalFileDelete | Medium | Mutation without write gate |
| optionalFilePin | Medium | Mutation |
| optionalHelpRemove | Medium | Mutation |
| siteblockIgnoreAddXite | Medium | Mutation |
| userGetSettings | Info leak | Read user settings |
| userGetGlobalSettings | Info leak | Read global settings |
| fileList / dirList | Info leak | Directory listing |
| muteAdd / muteRemove | Low | Mute management |
| wrapperNonce | Potential CSRF | Get nonce |

### F12 — `as` rebound: restrict persists, write gate targets rebound xite

- Rebound session: `WsSession::new(state, Some(target))` (command.rs:446).
  `WsSession::new` → `trusted=false` (lib.rs:159-161).
- Rebound restrict: `ui_restrict() && !trusted = true && !false = true`.
  **Restrict persists on rebound — admin gate still checks GATEWAY_READ_COMMANDS.**
- BUT write gate (line 365) on rebound checks `xite_owned(rebound.xite)` =
  `xite_owned(target)` (line 367). If target xite has `own=true`,
  WRITE_COMMANDS pass the ownership check on the rebound.
- **Chain**: permissionAdd("ADMIN") F2 → caller_elevated (xite_has_admin) →
  `as <owned_xite> fileWrite` → rebound xite_owned(target)=true → write
  succeeds on operator's own xite.
- Verify target with own=true via `siteList` (always allowed on gateway).

### Asymmetry: permissionAdd vs permissionRemove

- `permissionAdd` → NOT in ADMIN_COMMANDS (line 46 comment) → runs on gateway
- `permissionRemove` → IS in ADMIN_COMMANDS (line 51) → BLOCKED on gateway
- Result: Once ADMIN is planted via permissionAdd on a restricted gateway, it
  CANNOT be removed via WS while the gateway remains restricted. This is a
  LATENT privilege plant: dormant while restrict=true, but it persists to
  `permissions.json` (state.rs:7506 save_grants) and activates the moment
  the operator sets `ui_restrict=false` or reboots on a non-restricted node.

### xite_owned() and xite_has_admin() (state.rs)

```rust
// state.rs:7540-7547
fn xite_has_admin(address) -> bool {
    xites.get(address).map(|x|
        x.settings.permissions.iter().any(|p| p == "ADMIN")
    ).unwrap_or(false)
}
// → True if "ADMIN" in permissions array. Set via permissionAdd (ungated).

// state.rs:8406-8409
fn xite_owned(address) -> bool {
    xites.get(address).map(|x| x.settings.own).unwrap_or(false)
}
// → True if settings.own flag set. Set via siteSetOwned (ADMIN, blocked on
//   gateway) or recover_privatekey (ADMIN, blocked). NO non-admin path found
//   to make xite_owned return true.
```

### ui_restrict() (state.rs:1811-1816)
```rust
fn ui_restrict() -> bool {
    config_get("ui_restrict").await
        .map(|v| v.as_bool()
             .unwrap_or_else(|| v.as_str() == Some("true")))
        .unwrap_or(false)
}
```
Set via `configSet` (ADMIN, blocked on gateway). No bypass found to flip
ui_restrict via WS on a restricted gateway.
