# EpixNet live-campaign pitfalls (cut from rust-p2p-edge-case-audit SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/web3/rust-p2p-edge-case-audit/SKILL.md` during the
S2b-2 content pass (EpixNet reference-target case material; preserved, not deleted).
The epixnet reference write-ups, exploit templates, and live-WS scripts live under
`examples/hunts/web3/rust-p2p-edge-case-audit/` (references/, templates/, scripts/).

---

- **`as` + id:1M is THE gateway restrict bypass (LIVE PROVEN Aug 2026**:**
  When auditing a `ui_restrict=true` gateway, the single most powerful
  technique is `as` + `id >= 1000001` targeting any other xite served by
  the node. The rebound session has `restrict=true` (inherited), but the
  restrict gate ONLY fires for `ADMIN_COMMANDS` (line 340) and
  `WRITE_COMMANDS` (line 365). EVERY other command executes freely on the
  rebound. This gives you: cross-xite `dbQuery` (read+write ALL xite
  databases), cross-xite `permissionAdd` (plant ADMIN+NOSANDBOX to ALL
  xites), cross-xite `fileGet` (read ANY xite's files), cross-xite
  `siteInfo` (leak auth_address). Always test `as` + id:1M FIRST when you
  hit a restrict gate — it opens more doors than any other technique on
  this class of platform.
- The F2 chain (self-grant ADMIN via `permissionAdd`) was supposed to be
  neutered by a user permission prompt in the wrapper, but `permissionAdd`
  is intentionally un-gated to match EpixNet's design (the prompt is
  supposed to gate the wrapper chrome, not the WS path). The framework
  ships with the same hole. Don't rely on the wrapper to gate anything.

- **F2-LIVE gateway bypass (verified Aug 2026 on gateway.epixnet.io):**
  `permissionAdd` is NOT in `ADMIN_COMMANDS`, so it EXECUTES even on a
  `ui_restrict=true` restricted gateway — the restrict gate at
  command.rs:339-360 only checks commands that ARE in `ADMIN_COMMANDS`.
  Result: any visitor can plant `permissionAdd "ADMIN"` on the dashboard
  xite via WS with `id=1` (no elevation). The grant persists to
  `permissions.json` (state.rs:7506). `permissionRemove` IS in
  `ADMIN_COMMANDS` (command.rs:89) → BLOCKED on gateway → the planted
  ADMIN CANNOT BE REMOVED via WS. This is a LATENT privilege plant:
  dormant while `restrict=true`, activates if operator ever flips
  `ui_restrict=false` or boots the data dir on a non-restricted node.
  The existing F2 pitfall text says "Don't rely on the wrapper to gate
  anything" — now extend it: "Don't rely on `ui_restrict` to gate
  `permissionAdd` either — it's not in `ADMIN_COMMANDS` so the restrict
  gate never fires for it."

- **`chartDbQuery` as a gateway recon primitive:** `chartDbQuery` is in
  `GATEWAY_READ_COMMANDS` (always allowed on restricted gateways) and
  accepts arbitrary `SELECT` SQL against the chart DB.
  `SELECT * FROM pragma_database_list` leaks the operator's data
  directory path (e.g. `/opt/epixnet/.local/share/EpixNet/`), and
  `SELECT * FROM sqlite_master` enumerates all chart DB tables. Use
  this at the start of every gateway audit to map the filesystem.
  `writefile()`/`readfile()` SQLite functions are NOT available (no
  FTS extension loaded), so this is recon-only, not file R/W.
- **ATTACH DATABASE as a file existence oracle** (`dbQuery`, pre-auth):
  `ATTACH DATABASE '/path/to/file' AS x` returns `[]` (empty success) if
  the file exists and `{"error": "unable to open..."}` if it does not —
  a blind file existence oracle via `dbQuery`. On the live gateway this
  confirmed `master_seed.json`, `users.json`, `permissions.json`,
  `config.json`, `wallet.json` all exist in `/opt/epixnet/.local/share/EpixNet/`.
  Then `CREATE TABLE x.t (a TEXT)` + `INSERT INTO x.t VALUES('a')` SUCCEED,
  which **corrupts** the attached file by appending SQLite page headers to
  what was JSON — a destructive file write via SQL. `readfile()`,
  `writefile()`, and `load_extension()` are NOT available in rusqlite.
  See `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep-2026-08.md` section 7.
- **Multi-xite dbQuery data exfiltration** (`dbQuery`, pre-auth, gateway):
  `dbQuery` is NOT admin-gated, so it works on restricted gateways. The
  DASHBOARD xite has no database, but Talk/Search/Post/Blog xites DO.
  Connect with each xite's address as `wrapper_key` and run `SELECT * FROM
  <table>` to dump all user content (comments, posts, follows, user IDs,
  timestamps). See `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep-2026-08.md` section 8.
- **chart.db is pre-attached as schema `chart`**: `PRAGMA database_list`
  from any xite's `dbQuery` shows chart.db is already attached as `chart`.
  Query `chart.site` (xite addresses) and `chart.data` (1M+ telemetry rows)
  without needing ATTACH. See `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep-2026-08.md`.
- **`certSelect` — non-admin identity swap (F10):** `certSelect`
  (command.rs:3808-3839) is NOT in ADMIN_COMMANDS and NOT in
  WRITE_COMMANDS, so it executes freely on a `ui_restrict=true` gateway.
  It calls `cert_set(domain)` (state.rs:6154-6157) — the SAME underlying
  operation as admin-gated `certSet`, but without the admin gate. An
  attacker can switch the operator's global selected cert identity to any
  stored cert domain. Only selects from already-stored certs (can't add
  new without `certAdd`, which IS write-gated). Chain: certSelect → swap
  auth_address → `bigfileUploadInit` (also non-admin/non-write) passes
  internal `is_signer` check (state.rs:7115-7128). See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-command-taxonomy-2026-08.md` F10.
- **Non-admin/non-write command matrix on restricted gateway (F11):**
  The restrict gate ONLY fires for commands in ADMIN_COMMANDS (line 340)
  and WRITE_COMMANDS (line 365). Any command NOT in either list executes
  freely. Besides `permissionAdd` (F2) and `dbQuery` (CRITICAL) and
  `certSelect` (F10), other notable ungated commands include `fileGet`
  (unrestricted file read — HIGH), `bigfileUploadInit` (Medium — internal
  own/signer check), `optionalFileDelete`/`optionalFilePin` (Medium —
  mutations without write gate), `optionalHelpRemove`, `siteblockIgnoreAddXite`,
  `userGetSettings`/`userGetGlobalSettings` (info leak). Full matrix in
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-command-taxonomy-2026-08.md` F11.
- **`as` rebound write-gate targets rebound xite (F12):** The `as`
  command creates a rebound session via `WsSession::new(state, Some(target))`
  (command.rs:446). Since `WsSession::new` hard-codes `trusted=false`
  (lib.rs:159-161), the rebound session still has `restrict=true` —
  admin gate still checks GATEWAY_READ_COMMANDS. BUT the write gate
  (line 365) on the rebound checks `xite_owned(rebound.xite)`, i.e.
  `xite_owned(target)` (line 367), NOT the caller's xite. If the target
  xite has `own=true` (operator-owned), WRITE_COMMANDS pass the
  ownership check on the rebound. Chain: permissionAdd("ADMIN") F2 →
  caller_elevated → `as <owned_xite> fileWrite` → write succeeds. Verify
  target with `siteList` (GATEWAY_READ, always allowed). See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-command-taxonomy-2026-08.md` F12.
- **`as` + id:1M = live cross-xite execution on restricted gateway (D1,
  PROVEN Aug 2026 session 3):** The `as` command with `id >= 1000001` makes
  `caller_elevated = true` (command.rs:436-441), passing Gate 1 for the `as`
  command itself. The rebound session (`WsSession::new`, NOT trusted) re-enters
  the dispatcher, but for commands NOT in `ADMIN_COMMANDS` and NOT in
  `WRITE_COMMANDS`, the restrict gate never fires — they execute freely
  regardless of `ui_restrict`. **Live-proven on gateway.epixnet.io:** `as` +
  `dbQuery` read ANY xite's database; `as` + `permissionAdd` planted ADMIN +
  NOSANDBOX to other xites; `as` + `siteInfo` leaked `auth_address` from other
  xites; `as` + `fileGet` read `content.json` from other xites. Admin commands
  (`configList`, `siteSetOwned`) and write commands (`fileWrite`) remain blocked
  on the rebound. This makes the gateway a **multi-xite administration
  primitive**: pre-auth attacker can manage ALL xites' databases and
  permissions from one socket. See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` section D1.
- **Mass cross-xite ADMIN + NOSANDBOX plant (D2, PROVEN):** Using `as` +
  `permissionAdd("ADMIN")` and `permissionAdd("NOSANDBOX")`, planted to 3+
  xites on the live gateway. Some xites return empty string (no-op if no
  matching entry in xites map); dashboard xite (`epix1dash...`) consistently
  returns "ok". Combined with D1, this is a **mass persistence plant** across
  all 18 xites served by the gateway. See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` section D2.
- **Cross-xite dbQuery database write (D3, PROVEN):** `as` + `dbQuery` INSERT
  into Search xite `site` table executed (column error confirmed SQL reached
  target). On Talk xite locally: `INSERT INTO json`, `UPDATE comment SET
  body='...'`, `CREATE TABLE main.audit_marker` + `INSERT` + `SELECT` all
  succeeded. **Pre-auth stored XSS** via modifying forum comment bodies
  (`UPDATE comment SET body='<script>...</script>'`), identity spoofing
  (`UPDATE json SET cert_user_id='...'`), and data destruction
  (`DELETE FROM` / `DROP TABLE`). See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` section D3.
- **SQLite 3.50.2 environment fingerprint (D4):** `json_tree`, `json_each`,
  `dbstat`, `fts5`, `rtree` virtual tables all compiled. `sqlite_blob` NOT
  available as a virtual table (unlike what some SQLite docs suggest).
  `readfile()`, `writefile()` NOT available. `load_extension()` compiled but
  returns "not authorized" at runtime. `USE_URI` compiled (URI-style ATTACH
  supported). `MAX_ATTACHED=10`. This confirms the file-content-read path is
  dead — no SQLite function or vtable can extract raw file bytes. See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` section D4.
- **Expanded file oracle: 27 paths (D5):** Added `/proc/self/environ`,
  `/proc/self/cmdline`, `/proc/self/status`, `/opt/epixnet/.env`,
  `/opt/epixnet/epixnet.toml`, `private/keys.json`, `private/wallet.json`,
  `private/data.json`, `private/chart.db`, 4 log files. ALL confirmed to exist
  via ATTACH oracle. `/etc/passwd` exists but ATTACH returns "file is not a
  database" (text file, not a valid ATTACH target even for oracle — this is
  because ATTACH reads the first 16 bytes as the SQLite header magic, and a
  text file fails the magic check differently than a missing file). See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` section D5.
- **Arbitrary file write to /tmp proven (D6):** `ATTACH '/tmp/poc_audit.epix'`
  + `CREATE TABLE` + `INSERT` + `SELECT` verified — arbitrary SQLite file
  creation at any writable path. Output is SQLite DB format, not text, so
  cannot directly overwrite TOML/JSON with valid content — but CAN corrupt
  any existing file by appending SQLite pages. See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` section D6.
- **12 auth user identities leaked (D7):** Full list of certified
  `cert_user_id` values from all xites: user-06, user-08 (operator), user-07,
  user-10, user-11, user-02, user-03, user-04, user-05, user-09, user-12, user-01.
  All `@xid.epix` format. See
  `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` section D7.
- **`xite_owned()` cannot be set non-admin:** `xite_owned` (state.rs:8406)
  reads `x.settings.own`, set only by `siteSetOwned` (ADMIN, blocked on
  gateway) or `recover_privatekey` (ADMIN, blocked). No non-admin path
  found to make `xite_owned` return true. So WRITE_COMMANDS on a gateway
  are only reachable if the target xite was ALREADY owned by the operator.
