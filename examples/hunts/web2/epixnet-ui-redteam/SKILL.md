---
name: epixnet-ui-redteam
description: "red-team UI surfaces exposing WebSocket commands"
triggers:
  - audit epix-ui command dispatcher (handle_text in lib.rs:3164, dispatch in command.rs:321)
  - EpixNet WebSocket privilege-escalation / req_id spoofing / permissionAdd self-elevation
  - certAdd unverified cert blob / siteRecoverPrivatekey master-seed key derivation
---

# EpixNet `epix-ui` WebSocket API — red-team findings

## Inventory
- `crates/epix-ui/src/lib.rs` — HTTP routes, WS handler `handle_text` (line 3164), `handle_ws` (3008), `ws_upgrade` (2974), `bigfile_upload` (2678)
- `crates/epix-ui/src/command.rs` — CommandRegistry.dispatch (321), `WRAPPER_ID_BASE = 1_000_000` (16), `ADMIN_COMMANDS` (21-91), `WRITE_COMMANDS` (109-110), `as` command (414-449)
- `crates/epix-ui/src/state.rs` — `ui_restrict` (1811), `is_ws_origin_allowed` (14293), `add_permission` (7484 — NO whitelist), `xite_has_admin` (7540), `config_set` (2478 — NO key whitelist), `recover_privatekey` (10091), `sign_xite` (10342)
- `crates/epix-xite/src/storage.rs::path` (24) — sole path-traversal defence
- `crates/epix-user/src/lib.rs::add_cert` (251) — stores cert_sign WITHOUT sig verification

## Findings (sorted by severity)

### F1 — CRITICAL: req_id spoof → wrapper chrome elevation (command.rs:3164-3183 + 351)
- `handle_text` reads `id = req.get("id").and_then(as_i64).unwrap_or(0)` from the CLIENT JSON, then passes it as-is to `dispatch(..., req_id)`.
- dispatch's admin gate at line 351 ONLY elevation check: `let elevated = session.trusted || req_id >= WRAPPER_ID_BASE;`. `session.trusted == false` for every WS-originated connection (WsSession::new at lib.rs:3010 hard-codes trusted=false).
- A client sending `{"cmd":"siteList","id":1000001,"params":[]}` runs ANY admin command. No integrity check on `id` — it is just a number from the wire.
- Pre-auth YES on a loopback-bound node for any local process / DNS-rebinding tab; on a public gateway ONLY IF the operator did NOT set `ui_restrict=true` (ui_restrict refuses admin outright at line 341-347).
- [Trigger] `{"cmd":"siteList","id":1000001,"params":[]}` → [Effect] admin command runs as the trusted wrapper chrome → TB crossed: client → trusted wrapper chrome.

### F2 — CRITICAL: `permissionAdd("ADMIN")` → permanent self-elevation (command.rs:3113-3137 + state.rs:7484-7507)
- `permissionAdd` is INTENTIONALLY not admin-gated (command.rs:46-49). `add_permission` (state.rs:7484) inserts ANY string into the xite's `permissions` array with NO whitelist, NO user prompt, NO broker.
- `xite_has_admin` (state.rs:7540) literally reads `permissions.iter().any(|p| p == "ADMIN")`.
- A xite (or attacker bound to a xite) issues `permissionAdd "ADMIN"` with id=1 → the same xite then passes the admin gate at line 352 (`has_admin`) WITHOUT ever touching the WRAPPER_ID_BASE id-proof path. Persists across restarts via `permissions.json`.
- [Trigger] `{"cmd":"permissionAdd","id":1,"params":"ADMIN"}` then later `{"cmd":"siteList","id":1,"params":[]}` → [Effect] admin from a low id → TB crossed: xite operator → wrapper permission-prompt gate.
- This is *worse* than F1 — it's a single-message permanent backdoor reachable from any non-admin WS connection, even one whose browser wrapper would not normally show the ADMIN permission prompt.

### F3 — CRITICAL: `siteRecoverPrivatekey` → remote private-key recovery (command.rs:1885-1896 + state.rs:10091-10114)
- ADMIN command (command.rs:67). Reads `address` from the BOUND session (`s.address()` — the wrapper_key in the WS URL), so the caller chooses the target by URL, not by params.
- `recover_privatekey` (state.rs:10091) reads the master seed straight from in-memory user state (state.rs:10100), derives the xite private key by `address_index` from that xite's content.json, validates it against the address, and SAVES it as the saved xite private key — all WITHOUT prompting the operator for the seed.
- Combined with F1/F2 a remote attacker who can bind WS to a node and target the bound xite that has `address_index` set can silently produce the xite's private key.
- [Trigger] F1 or F2 gives admin → `siteRecoverPrivatekey` → [Effect] attacker-controlled client obtains/sets the xite's private key, ready to be exfiltrated on a subsequent publish or via `userSetSitePrivatekey`/signing path → TB crossed: remote WS caller → identity key material.

### F4 — CRITICAL: `configSet` accepts ANY key (command.rs:1038 + state.rs:2478)
- `ConfigSet` (admin) calls `state.config_set(key, value)`; `config_set` (state.rs:2478) inserts the key with NO allowlist — only `data_dir` is special-cased at command.rs:1060.
- Once elevated (F1 or F2), an attacker can set `ui_restrict=false` (state.rs:1811), `ui_password=""` (1820), `no_new_xites=false`, or `ui_host="attacker-controlled-domain"`. The `ui_restrict=false` setting specifically destroys the ONLY defence ArchiteCT put in front of the F1 spoof on a public gateway — so F1 + F4 compounds: spoof id → become admin → disable the very lock that would have stopped you.
- [Trigger] `{"cmd":"configSet","id":1000001,"params":["ui_restrict",false]}` → [Effect] permanent unlock of admin UI → TB crossed: xite operator → data-dir config file.

### F5 — HIGH: `certAdd` stores an UNVERIFIED cert (command.rs:3752 + epix-user/src/lib.rs:251)
- `certAdd` is NOT in ADMIN_COMMANDS (only `certList`/`certSet` are). On a non-restricted node any bound xite can call it.
- `User::add_cert` (epix-user/src/lib.rs:251) stores the supplied `cert_sign` blob verbatim — it does NOT verify the cert is signed by the relevant ID provider over (domain, auth_address, auth_type, auth_user_name). The auth_privatekey is just attached for future use; it is never used to validate the incoming cert_sign.
- A xite can therefore install `certAdd("evil.example","web","attacker","FAKE-STRING")` and `certSet("evil.example")` → whoever trusts the cert's "issued by provider" status (peer handshake, xID linker) can be fooled.
- This is the only find that does NOT require F1/F2 — `certAdd` is broken at the trust-model level for any bound xite.
- [Trigger] `certAdd` with arbitrary `cert_sign` (small id) → [Effect] cert stored and globally selected, no issuer signature proof → TB crossed: ID provider signing key → xite operator.

### F6 — DoS only: `serverShutdown` (command.rs:1220-1237)
- ADMIN command, calls `s.state.shutdown(restart)` → process exits. Pure DoS once F1/F2 holds. No RCE: process is restarted by the supervisor (or stays down with restart=false). Worse than RCE in some contexts since repeated restart exhausts the supervised respawn window. No signed config; no kernel-level RCE.
- `serverUpdate` (command.rs:1202) is a NO-OP that returns an error message — no in-place updater, no RCE surface.

### F7 — NEGATIVE: fileWrite / fileDelete / bigfile_upload path traversal is BLOCKED
- All file writes funnel through `XiteStorage::write` (storage.rs:43) which calls `XiteStorage::path` (storage.rs:24-33). `path` iterates `Path::new(inner_path).components()` and rejects anything that isn't `Component::Normal` or `Component::CurDir`. So `../`, absolute paths, prefix `\\?\` etc. all raise `unsafe inner_path` BEFORE the FS write.
- `bigfile_upload_init` only `trim_start_matches('/')` the inner_path at state.rs:7131, but the actual `storage.write` later still goes through `path()` — so even crafted `inner_path` cannot escape `data/<address>/`.
- `resolve_target` (command.rs:210) merges `cors-`/`merged-` prefixed inner paths to other xites, but each routed target is still ONLY writable under ITS OWN storage root — no cross-xite escape.

### F8 — NEGATIVE: `as` command is not a separate bypass
- `as` re-enters dispatch on a rebound session (command.rs:448). It is itself not in `ADMIN_COMMANDS`, so its admin gate is bypassed, but the rebound call re-applies the inner command's admin gate at the same lines 340-360. With `req_id` spoofing or ADMIN-permission grant already in place, `as` simply fan-outs to OTHER bound xites — it's not a new primitive. Inner_id inheritance: `if caller_elevated { req_id.max(WRAPPER_ID_BASE) }` at line 447 — same numeric proof.

### F9 — `userShowMasterSeed` (command.rs:3317) — needs `--features multiuser`
- Returns `multiuser_current_seed()` directly (command.rs:3327). ADMIN command, behind `#[cfg(feature="multiuser")]` AND plugin-enabled. Available only on multiuser feature builds. If the operator built with `--features multiuser`, F1/F2 → `userShowMasterSeed` → whole identity master seed leaked remotely. Single-quick-look *default* builds don't compile this command. Always check whether the live gateway was built multiuser.

## Remediation order
1. Per-connection proof of trust: replace the `req_id >= WRAPPER_ID_BASE` test (command.rs:351) with a server-issued HMAC/nonce the wrapper chrome must echo, generated at the same point the wrapper page is rendered (alongside `wrapper_nonce` at lib.rs:1203). Stop trusting an unsigned client-supplied integer.
2. `permissionAdd` allowlist: in `add_permission` (state.rs:7484), reject `permission == "ADMIN"` (and a small allowlist of unsafe nouns) when the caller is not `session.trusted` / not server-side. Mirrors how the wrapper chrome is supposed to gate ADMIN via the prompt.
3. `siteRecoverPrivatekey`: require an explicit operator confirm/prompt before deriving a xite key from the master seed. The bound-xite check is too weak: the wrapper_key URL field is PUBLIC.
4. `configSet` allowlist + write-protect `ui_restrict`, `ui_password`, `no_new_xites`, `ui_host` to server-side-only writes (CLI / admin Unix socket). Anything that disables the F1 guard must not be settable OVER the F1 guard.
5. `certAdd`: verify `cert_sign` is a valid signature by the configured ID provider over `(auth_address, domain, auth_type, auth_user_name)` before storing — accept the cert iff valid.

## Live PoC deposit
`/root/epixnet-src/EpixNet-main/red_team_poc.py` exercises F1, F2, F3, F4, and the negatives (fileWrite `../`, certAdd unverified). It is a no-payload check, exits non-zero only if elevation succeeds. Run with a reachable target: `python3 red_team_poc.py epix1<address>`.
