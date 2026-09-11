# EpixNet edge-case fuzz — Aug 2026 (Rust sinks, rusqlite boundary)

Session transcript condensed to file:line triggers + edge-case probes
+ verdicts. Read alongside the sibling skill `epixnet-ui-redteam` to get
the complete picture (F1-F9 WS-command-API findings are in the manual
sibling, this file holds the Aug 2026 F10-F13 + negatives).

## Audit target

EpixNet Rust source: `/root/epixnet-src/EpixNet-main/`. Main crates
audited (skip-list: `epix-worker`, `epix-ffi`, `epix-nmh`, `epix-search`,
`epix-feed`, `epix-runtime`, `epix-browser`, `epix-propagation`,
`epix-protocol`, `epix-peer`, `epix-discovery`, `epix-edx`,
`epix-build`, `epix-plugin`, `epix-plugins`, `epix-user`,
`epix-server`, `epix-reticulum`, `iptproxy-sys`, `xid-spike`).

## Sink inventory — chained findings

### F10 — `dbQuery` → `conn.prepare(sql)` with user-controlled `sql`

**Sink chain (file:line)**:
- `epix-ui/src/command.rs:1474-1497` `DbQuery::handle` — accepts `query` from `params[0]` (string, user-controlled).
- `epix-ui/src/state.rs:5986-6025` `AppState::db_query` — lazy-builds per-xite DB, calls `db.query_value(query, params)`.
- `epix-db/src/lib.rs:145-148` `Database::query_value` — routes to `populate::query_value`.
- `epix-db/src/populate.rs:451-505` `query_value` — branches on `params`:
  - `Value::Object(map)` when `sql.contains('?')` (line 453) → `expand_where_dict(sql, map)` (line 404-449) → `safe_sql_identifier` scrubs dict keys only.
  - `Value::Object(map)` otherwise → named-bind path (line 460-501): for each `(k, v)` in map, the named-bound placeholder expression `:key` is regex-replaced with `(name__0, …)` for arrays; the SQL string is rebuilt but the HEAD (e.g. `SELECT … FROM x`) is untouched.
  - `Value::Array(arr)` → `query(conn, sql, arr)` (line 502) — SQL passed verbatim.
- `epix-db/src/populate.rs:360-364` `query` — calls `conn.prepare(sql)` ; `rusqlite::Connection::prepare` rejects compound statements.

**Connection init (no `query_only` guard)**:
- `epix-db/src/lib.rs:39-49` `from_manager` runs only `c.execute_batch("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")` in `with_init`. No `PRAGMA query_only = ON` is ever issued on the per-xite pooled connection.

**Verdict**: CHAINED. The SQL head is fully attacker-controlled; `safe_sql_identifier` only scrubs dict-KEYS within the `WHERE` clause and only when `?` appears. An SQL string with no `?` placeholder bypasses sanitization entirely and feeds raw into `conn.prepare`.
- `conn.prepare` rejects compound `;`-joined statements (multi-statement error) — so `DROP TABLE x; --` fails.
- Single-statement arbitrary execution IS reachable: `UPDATE`, `INSERT`, `DELETE`, `CREATE TABLE`, `ATTACH DATABASE`, `DETACH`, `SELECT … FROM sqlite_master`, `INSERT INTO a SELECT * FROM b`, `INSERT INTO a SELECT … UNION SELECT …`.
- `ATTACH DATABASE '/path/evil.db' AS evil` writes a file outside the xite tree via sqlite-side paths (bypasses `XiteStorage::path`'s `Component::Normal` filter, which only covers xite-tree writes).
- `SELECT load_extension('/x.so')` — DISABLED by rusqlite default `SQLITE_OMIT_LOAD_EXTENSION` (NOT RCE).
- `dbQuery` is NOT in `ADMIN_COMMANDS` (only `chartDbQuery` / `feedQuery` are) and NOT in `WRITE_COMMANDS` (`command.rs:109-110`). Any bound xite page can call it.

**Edge-case inputs that probe the boundary**:
| Input | Expected | Observed |
|---|---|---|
| `"SELECT * FROM post"` | read | ✅ basic case |
| `"SELECT * FROM post; DROP TABLE x; --"` | error (multi-statement) | blocked by `conn.prepare` |
| `"ATTACH DATABASE ':memory:' AS e"` | executed | chained — file write |
| `"INSERT INTO foo SELECT * FROM json"` | execute | lateral read across `json` table |
| `"CREATE TABLE scratch(x)"` | executed | local DoS surface |
| `"SELECT load_extension('/x.so')"` | disabled | OMIT_LOAD_EXTENSION |
| query with 0 `?` and dict params | bypasses `expand_where_dict` | confirmed at line 453 |

**Trust boundary crossed**: bound xite operator (WS page originator) → per-xite SQLite filesystem / operator disk via `ATTACH` / cross-table DML on the operator's xite-local DB rows.

**Recommended fix**: open the per-xite DB read-only via `SqliteConnectionManager::file(...).read_only(true)`, OR add `PRAGMA query_only = ON` to the `with_init` batch at `epix-db/src/lib.rs:41-43`.

### F11 — Merger `dbQuery` lateral read across merged xites

**Sink chain**:
- `epix-ui/src/state.rs:6013` — `db_query` calls `rebuild_xite_db` then `populate::populate_xite_prefixed` per merged xite.
- `epix-db/src/populate.rs:290-298` `populate_xite_prefixed` — calls `populate_xite_filtered(..., xite, &[], path_prefix)`.
- `populate_xite_filtered` (populate.rs:303-342) — writes rows with `xite` column to `json` table; tags each row by `(site, directory, file_name)` for schema v3.
- `populate.rs:50-54` (version 1) / `:64-67` (version 3) — `INSERT OR IGNORE INTO json (site, directory, file_name) VALUES (?, ?, ?)` per merged xite's data files.
- `populate.rs:233-265` — to_table rows land in the same merger DB.

**Verdict**: CHAINED. The merger DB aggregates raw merged-xite rows. A `dbQuery` from the merger page (NOT admin-gated — see F10) returns rows from every merged xite without author consent being asserted at query time. The `exclude` filter (`populate_xite_filtered`, populate.rs:303-342) is populate-time only; once rows are in SQLite, queries bypass it.

**Trust boundary crossed**: per-xite consent model (each merged author signs only their own `content.json`) → aggregator-wide lateral read by a single merger consumer.

**Compounds F10**: a hostile merger page that ALSO uses F10 (`ATTACH`) can exfiltrate every merged xite's records from `json`/post tables to a sqlite-side file on the operator's disk.

### F12 — `state_digest` chain-attestation cache asymmetry TOCTOU

**Sink**:
- `epix-chain/src/attestation.rs:70-121` `verify_digest`:

```
1. state_digest  (cached 15s — DIGEST_TTL, attestation.rs:71-86)
2. content_state_digest == chain.digest  (attestation.rs:114)
3. is_finalized(&chain.digest)  (cached 30s — ATTESTATION_TTL, attestation.rs:91-105)
```

- `is_finalized` (line 99): `data.get("finalized").and_then(|v| v.as_bool()).unwrap_or(false)` — a bare boolean from `/xid/v1/attestations?digest=…` RPC. NO validator-set signature on the boolean.

**Verdict**: CHAINED with conditions. The cache asymmetry is real (15s / 30s, both keyed by digest string only), but `verify_digest` always reads the LIVE (FAST, 15s) digest and then checks finality via the SLOW (30s) cache. So:
- A content.json carrying the OLD digest fails at step 2 (mismatch with current digest).
- A content.json carrying the CURRENT digest passes step 2 and checks finality via the cache, which has been populated against the SAME key. So the cache asymmetry per se is not the bypass.

The actual bypass requires RPC MITM: if an attacker controls `/xid/v1/attestations?digest=` (via TLS-MITM against `rpc_url`, or by compromising a single validator since the boolean does NOT require validator-set consensus — only the chain's own finality needs 2/3+ but the RPC response is unverified boolean), they can return `{"finalized": true}` for any digest content.json claims.

**Mitigations in place** (line 151 of vrf.rs / attestation.rs): `crate::chain_egress_ok()` — refuses clearnet egress before Tor is ready in `Always` mode, AND the HTTP client goes through a SOCKS-rebuilt reqwest client (line 90-101 of attestation.rs). So clearnet MITM is mitigated. The remaining trust is the RPC endpoint's boolean honesty (validator-set signature missing).

**Trust boundary crossed**: per-name Merkle proof (`XidResolver`) → chain-consensus attestation. A Merkle-proof-less xite with `state_digest` keys its way past per-name proofs.

**Recommended fix**: (1) make `DIGEST_TTL == ATTESTATION_TTL` (e.g. both 15s); (2) key both caches by `(digest, chain_height)` so digest rotation invalidates the finality cache; (3) replace the boolean RPC with a signed-validators-attestation payload (a bare boolean is not a proof).

### F13 — `populate::insert_row` column / table interpolation gaps

**Sink**:
- `epix-db/src/populate.rs:94-116` `insert_row`:

```rust
fn insert_row(conn, table, allowed, row, json_id) -> ... {
  for (k, v) in row {
    if allowed.iter().any(|c| c == k) && k != "json_id" {
      cols.push(k);
      params.push(to_sql(v));
    }
  }
  ...
  let sql = format!("INSERT OR REPLACE INTO {table} ({}) VALUES ({})", cols.join(", "), ...);
  conn.execute(&sql, ...);
}
```

- `epix-db/src/schema.rs:125-134` `safe_identifier` validates ONLY `schema.tables.keys()` (line 149-151 of schema.rs applies it). It does NOT validate:
  - `to_table[i].table` — the target table referenced in the INSERT.
  - `to_table[i].key_col`, `to_table[i].val_col` — `allowed_cols` (populate.rs:124-139) returns these verbatim.
  - `import_cols[]` strings — same path.
  - `table.indexes[]` strings — `schema.rs:188-190` runs `conn.execute_batch(&format!("{idx};"))` — STACKED statements ARE allowed under `execute_batch`, so a malicious xite author can run arbitrary SQL via `indexes` strings (an UNCONFIRMED-but-strong chain vector — see Recommended Follow-Up below).

**Verdict**: chained. The dbschema author controls table names AND column names interpolated into DML. `conn.execute` (single-statement) blocks `;`-stacked SQLi, but UNION-based reads via `to_table.table = "realpost UNION SELECT json_id, path, '' FROM json --"` bypass the `tables.keys()` check and read across the xite's own SQLite DB.

**Trust boundary crossed**: xite author (publisher of `dbschema.json`) → operator's per-xite DB rows outside the dbschema's declared schema.

**Recommended Follow-Up (NOT closed in Aug 2026)**: the `table.indexes[]` path at `schema.rs:188-190` goes through `execute_batch` which DOES allow stacked statements. A `dbschema.json` with `tables.X.indexes = ["CREATE INDEX a ON x(y); DROP TABLE json; --"]` executes BOTH statements. The next audit should construct a malicious `dbschema.json` and chain-test it against a live per-xite DB to confirm. If confirmed, this upgrades F13 to CRITICAL (since the dbschema is served over the WS to peers during a clone, and the operator's node will FETCH and apply it without the operator inspecting the indexes field).

## Negative confirmations (Aug 2026)

### Merkle proof

- Sink: `epix-chain/src/merkle.rs:10-30` `verify_proof(leaf_hash, leaf_index, siblings, expected_root)`.
- Pure recomputation; SHA-256 over `current || sibling` (or `sibling || current` when `idx % 2 == 1`), `idx /= 2` per level. `idx` is u64 — `idx / 2` underflows no.
- Edge inputs: tampered sibling (test at merkle.rs:55-57), wrong index (line 54), wrong root — all reject.
- Phantom-leaf concern: non-power-of-2 leaf count has empty slot; whether a forged proof occupies the empty slot depends on the chain's leaf-set encoding, not this verifier. NOT exploitable at this layer.
- **Verdict**: BLOCKED. No forgery surface in `verify_proof` itself.

### VRF `derive_random` / `combine_beacons`

- `epix-chain/src/vrf.rs:45-65`. Pure `SHA256(beacon_hex_utf8 || seed_utf8 || decimal(i)_utf8)`. No peer input. `latest_beacon` (line 153) uses `block.height - 1` so the un-finalized current block is skipped.
- `multi_block_beacon` (line 160-177): bounds `blocks ∈ [1, 256]`, rejects `end_height < blocks`.
- Tests at vrf.rs:213-232 byte-pin the encoding (UTF-8 bytes for beacon hex string, decimal ASCII for `i`).
- **Verdict**: BLOCKED. No bias insertable by a peer; only the chain RPC and validator-set are trust roots.

### DHT `PeerStore`

- `epix-dht/src/store.rs:1-68`. Unauthenticated `add(key, peer)` accepts any `PeerAddr`. Capped per-key at `MAX_PEERS_PER_KEY = 128` (line 14) with TTL eviction (line 32-43 — drops oldest when over cap after dropping expired).
- Test `dht/store.rs:90-108` confirms cap is enforced under floods.
- **Verdict**: BLOCKED-BOUNDED. DoS surface (peer list pollution up to 128) bounded by the cap and TTL. Not exploitable to crash; only to skew `get()` returns.

### Tor / I2P

- `epix-tor/src/lib.rs:1-120`: Arti-managed; no separate control-port string parsing in THIS crate. `OnionKey::load` (line 91-107) reads from a fixed `data_dir/tor/state/keystore/hss/<nickname>/ks_hs_id.ed25519_expanded_private` path — nickname not attacker-controlled at this layer.
- `epix-i2p/src/lib.rs:1-120`: SAMv3 via `yosemite`. `b32` derivation is `B64-decode → SHA256 → base32`. No injection surface in `create_session`/`connect` — `peer.dest` is dialled directly, no quoting needed.
- **Verdict**: BLOCKED for this layer. Trust roots rest on Arti's transport layer and yosemite's SAM, not on user-supplied strings flowing through THIS crate.

### FilePack archive read (no zip-slip)

- `epix-ui/src/state.rs:14626-14660` `split_archive_path` / `read_from_archive`.
- `read_from_archive` calls `zip.by_name(within)` (line 14641) and `entry.read_to_end(&mut out)` (line 14644), or iterates `tar.entries()` matching `path.to_string_lossy() == within` and `read_to_end` (line 14654). NO extraction to the filesystem; bytes returned to the WS response.
- **Verdict**: BLOCKED for zip-slip because there is NO extraction-to-disk code path.
- BOUNDED DoS surface: a 100MB tar.gz entry returns 100MB to the WS frame — OOM/request-size DoS. The response is bounded only by the in-memory `out: Vec<u8>`.

### `XiteStorage::path` (path traversal guard)

- `epix-xite/src/storage.rs:24-33`. Iterates `Path::new(inner_path).components()` — rejects any `Component` other than `Normal`/`CurDir`. `..`, RootDir (absolute), `Prefix` (Windows drive) all raise `unsafe inner_path`.
- Tests at `storage.rs:185-191` cover `../escape`, `/etc/passwd`, `a/../../b`.
- ALL file ops funnel through this: `fileWrite` (command.rs:1759-1791), `fileDelete` (1795-1811), `fileGet` (663-726), `list_dir` (state.rs:12046-12070), `walk_files` (12074-12099), `bigfile_upload_init` (state.rs:7131).
- **Verdict**: BLOCKED. Sufficient single-point defense.

### bt `PieceStore`

- `epix-bt/src/store.rs:43-55` `PieceStore::open` — `OpenOptions::new().create(true).truncate(true).open(path)` then `file.set_len(len).await?`. `len: u64` from untrusted metainfo `length`.
- Edge input: `length = u64::MAX` → `set_len` returns ENOSPC on most filesystems BUT the open file's previous content was already wiped by `truncate(true)` before the reservation check.
- A malicious torrent metainfo can wipe a same-path file before the `set_len` failure surfaces. (Realistic only if the operator's `path` for the bt file collides with a same-path user file — but the engine picks the path, not a peer.)
- **Verdict**: BOUNDED DoS / partial-data-wipe-by-collision. The bt metainfo parse should bound `length` (e.g. reject > a known swarm ceiling) BEFORE `PieceStore::open`.

### Blob store

- `epix-blob/src/store.rs:51-65`: `MAX_OBJECT_BYTES = 64 << 30 = 64 GiB`; `MAX_RESERVED_BYTES = 2 * MAX_OBJECT_BYTES` — no u64 multiply overflow.
- `ObjRecord::held` (line 204-219): uses `saturating_mul` / `saturating_add` for byte accounting — no overflow.
- `bits_from_local` (line 112-125): uses `saturating_add` for run-length accumulation. No overflow.
- `sparse_writers` mutex (line 265-268) held ACROSS delete + unlink; `evict_holds` mutex (line 276-278) held ACROSS post-completion work. Inspection: acyclic, properly scoped.
- **Verdict**: BLOCKED. No overflow or acyclic-race surface in this layer.

### Content verification (`verify_content_file` / `signed_data`)

- `epix-content/src/lib.rs:29-36` `signed_data` strips `sign` and `signs` only, dumps with sorted keys. `signers_sign` is signed SEPARATELY over `format!("{required}:{joined_signers}")` (verify.rs:516-521) — not over the canonical content, so stripping it from the canonical body is correct.
- `verify_content_file` (verify.rs:501-558): tries BOTH classic `verify` and `verify_keccak` (line 544-547). `sign_required` hard-codes to 1 (verify.rs:101-103) — same as EpixNet; a content.json `signs_required > 1` is silently ignored (NOT a bypass — defaults stricter).
- `verify_cert_sign` (verify.rs:107-116) — signs subject `format!("{user_address}#{auth_type}/{user_name}")`. Chain-delegated bypass when `issuers.contains("chain")` (line 356-358) — acknowledged TODO for full on-chain verification.
- `is_valid_relative_path` (verify.rs:601-633) — segment-level `..` / `.` check (not substring), Windows device names. Tests confirm Windows reserved names reject.
- **Verdict**: BLOCKED for content-verification crypto primitives. The chain-delegate path is a known-trust-extension, not a bypass.

## Composite chain (Aug 2026)

Hostile merged/merger xite on a non-restricted (loopback-bound) node:

1. `permissionAdd "ADMIN"` (F2 — see sibling skill `epixnet-ui-redteam`) — self-elevate permanently.
2. `as` recursion (F8 updated — Aug 2026 found that line 447 of `command.rs` clamps `inner_id` UP) — chain fans out elevated `req_id` to ANY target address; depth unbounded.
3. `dbQuery("ATTACH '/tmp/exfil.db' AS e; CREATE TABLE e.exf AS SELECT * FROM json; --", {})` WILL FAIL (multi-statement); use TWO queries: `dbQuery("ATTACH '/tmp/exfil.db' AS e", {})` then `dbQuery("CREATE TABLE e.exf AS SELECT * FROM json", {})` — both single-statement. F10 → exfiltrates every merged-xite's `json` rows to a file on the operator's disk.
4. `configSet("ui_restrict", false)` (F4 sibling) — neutralize the restricted-gateway guard.
5. `dbQuery("SELECT user_name, post_id, body FROM post JOIN json USING(json_id)", {})` (F11) — lateral read across every merged xite's records.

## Follow-ups for next audit

1. **(CRITICAL, UNTESTED)** F13 `table.indexes[]` path at `schema.rs:188-190` uses `execute_batch` — stacked-statement arbitrary SQL injection IS reachable via xite-author-controlled `indexes` strings in `dbschema.json`. Construct a malicious `dbschema.json` and chain-test against a live per-xite DB to confirm. This bypasses the single-statement defense F10 rode on.
2. Construct a live PoC at `/root/epixnet-src/EpixNet-main/edge_case_poc.py` exercising F10 + F11 against a fresh `Database::open_in_memory()` (offline; no network needed). Three queries: `ATTACH`, `CREATE TABLE exfil AS SELECT …`, `DETACH`. Assert files appear at the attach path.
3. Verify whether `read_only(true)` SqliteConnectionManager in `from_manager` (epix-db/src/lib.rs:39-49) breaks populate (populate does need write access on the schema-build path). If so, split: read-only pool for `dbQuery`, write pool for populate.
