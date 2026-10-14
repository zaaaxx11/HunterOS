---
name: rust-p2p-edge-case-audit
description: "Rust P2P edge-case audit"
metadata:
  version: 1.0.0
  hermes:
    tags: [rust, p2p, decentralized, epixnet, fuzz, edge-case, sqli, content-verification, merkle, vrf, chain-attestation, toctou]
    category: security
---

# Rust P2P / Decentralized Content Platform Edge-Case Audit

Class-level methodology + canonical reference for fuzzing Rust-based
peer-to-peer decentralized content platforms. The reference target is
EpixNet (a Zeronet-style P2P website platform written in Rust); the
methodology generalizes to any Rust platform with a similar layered
architecture: SQLite-per-site database, content-addressed blob store,
signed `content.json` verification, WebSocket command API, BitTorrent / DHT
peer layer, Tor/I2P transports, and a chain-attestation trust layer.

## When to load

Load this skill when the operator hands a "FUZZ-ENGINEER" or "edge-case"
brief against a Rust codebase named anything containing `epix-`, `epixnet`,
`xite`, or any Rust P2P platform with the structure above. Also load when
auditing:

- A Rust SQLite layer that uses rusqlite + r2d2 pools and exposes a WS
  `dbQuery` command.
- A content/signature verification chain with `state_digest` + finality
  cache.
- A WS command API with an `as` delegation primitive.
- A content-addressed blob store with sparse files + slab packfiles.
- A BitTorrent magnet parser + DHT peer store.

Do NOT load for: smart-contract auditing (use `cosmwasm-contract-audit` or
`token-transfer-audit`), Web2 admin hunts (use `web2-admin-hunt`), or Go
node audits (use `go-edge-case-audit`).

## Triggers

- FUZZ-ENGINEER: find edge cases on high-risk sinks in Rust P2P / decentralized content
- audit EpixNet SQLite query path / `dbQuery` SQL string user-controlled
- content.json signature verification bypass / `signed_data` canonicalization
- archive zip-slip in `importBundle` / `FilePack` archive read
- `as` command recursion / `inner_id` clamp-up escalation
- Merkle proof forgery / VRF bias / DHT/RPC injection
- Tor/I2P protocol abuse / onion-key loading
- integer overflow in blob sizes / race condition in sparse writers

## Methodology

### 1. Map the trust graph BEFORE listing sinks

List every cross-trust-boundary input → sink pair. The EpixNet trust
boundaries (verify against your target's equivalents):

| Source | Sink | Boundary |
|--------|------|----------|
| Bound xite WS page | `dbQuery` SQL string | xite operator → per-xite SQLite FS / DDL |
| Bound xite WS page | `permissionAdd` string | xite operator → wrapper permission gate |
| Bound xite WS page | `certAdd` cert_sign | xite operator → ID-provider signature key |
| Xite-author `dbschema.json` | `populate::insert_row` interpolations | xite author → operator xite-local SQLite |
| Peer content.json | `verify_content_file` / `state_digest` | peer → attested-content-trust |
| Peer torrent metainfo `length` | `PieceStore::file.set_len` | peer → sparse file size |
| Peer archive entry | `read_from_archive` | peer → WS response bytes (in-memory only) |
| Chain RPC response | `is_finalized` boolean | RPC endpoint → content acceptance |
| Caller `req_id` | `dispatch` admin gate | client JSON → wrapper-chrome elevation |

For every cell, the test is: does an attacker at the source reach the sink
with data they controlled, and does the sink enforce a check? If the check
is "the file is signed" ask: signed by whom and over what canonicalization?

### 2. Categorize every sink as `chained` or `blocked`

- `chained` — attacker reaches the sink with attacker-controlled data and
  the sink's check is bypassable or absent.
- `blocked` — the check holds under edge-case input.
- `blocked-bounded` — the check holds but the sink has a smaller
  vulnerability (e.g. unauth-but-capped DoS).

Triage `chained` for chainability: can two or three chained findings
produce a remote, cross-trust-boundary effect? List the chain explicitly.

### 3. Edge-case input inventory to fire per sink

For EVERY sink, regardless of what it does, fire these:

- `0`, `1`, `u64::MAX`, `u64::MAX - 1`, `i64::MIN`, `i64::MAX`, `-1`,
  `null` (`serde_json::Null`).
- Empty string, unicode whitespace (`\u200B`, `\uFEFF`), embedded null
  (`\x00`), embedded quote (`'`, `"`, backtick), control chars
  (`\x01`-`\x1F`).
- Deeply nested JSON (1000-level object/array), array of 1M elements,
  object with 1M keys.
- Path traversal: `..`, `../`, `..%2f`, absolute
  (`/etc/passwd`, `C:\windows`), Windows device (`CON`, `PRN`, `COM1`).
- SQL compound statement (`;`) — expect to fail under `conn.prepare`,
  succeed under `conn.execute_batch`.
- Statement without `?` placeholder — bypasses `expand_where_dict`
  sanitization if the sanitizer is gated on `?` presence.
- Reentrancy / recursion: call the same sink inside its own handler (e.g.
  `as` → `as`).
- Cache asymmetry: two caches with different TTLs keyed on the same value
  (TOCTOU).
- Saturating vs wrapping arithmetic — read the type signatures (`u64` wrap
  in release, `saturating_*` doesn't overflow, plain `+` does).

### 4. Verify rusqlite's single-statement boundary in the source

CRITICAL — `rusqlite::Connection::prepare` and `Connection::execute` only
prepare a SINGLE statement (;-joined compound fails with a multi-statement
error). `Connection::execute_batch` is the one that runs multiple. When you
see `format!("INSERT OR REPLACE INTO {table} ...")` with user-controlled
`table`, the classic stacked SQLi (`...; DROP TABLE x`) does NOT execute —
but:

- `UPDATE x SET y = z` (single statement) DOES execute.
- `ATTACH DATABASE '/path' AS evil` (single statement) DOES execute.
- `INSERT INTO a SELECT * FROM b` (single statement, including `UNION`)
  DOES execute — including reads from any table in the same DB.
- The `sqlite_master` table is readable — schema reconnaissance.

So a "the table name is user-controlled" finding is still high-severity
even when rusqlite blocks stacked statements: UNION-based read across the
xite's DB tables is reachable, and `ATTACH` lets the attacker plant a
sqlite-side file outside the operator's expected data tree.

### 5. Distinguish archive extraction from archive read

For "zip-slip" / "tar-slip" claims, ASK:

- Does the code call `extract` / `unpack` / write an entry to a path under
  the operator's filesystem? → Real zip-slip surface.
- Does the code call `zip.by_name(path)` / `tar.entries().read_to_end(out)`
  and return the bytes to the caller? → In-memory read. No extraction, no
  zip-slip. The remaining surface is OOM on huge entries and the
  response-size DoS.

`read_from_archive` in `epix-ui/state.rs:14637-14660` is the second case.
Document it as `blocked` for zip-slip, but flag the OOM surface.

### 6. Cache-asymmetry TOCTOU protocol

When two caches protect the same decision and one has a longer TTL than
the other, AND their keys overlap (e.g. both keyed by digest string):

1. Identify the two caches and their TTLs.
2. Identify whether each cache is keyed by the value alone or value + an
   authoritative context (e.g. chain `height`).
3. If `cache_fast.key == cache_slow.key` AND `cache_fast.TTL < cache_slow.TTL`,
   there is a window where `cache_slow` returns a stale answer for a value
   that `cache_fast` has already rotated past.
4. If the agent ever reads `cache_slow` for the FAST cache's current value,
   the agent can be tricked into accepting content that the FAST cache
   would reject.

For EpixNet's `ChainAttestation`: `DIGEST_TTL = 15s`, `ATTESTATION_TTL = 30s`.
Both keyed by digest. `verify_digest` reads the live (FAST) digest and
checks finality via the SLOW cache. The finality cache keyed by the OLD
digest returns stale `true` IF the digest has rotated under the same key —
but the content.json must carry the NEW digest to pass the live check.
So the realistic attack vector is not the cache asymmetry per se — it's
that the boolean RPC `/xid/v1/attestations?digest=` is unverified (no
validator-set signature) so a MITM that controls the RPC controls the
boolean.

### 7. Recursion depth in delegation primitives

For every `as` / `actAs` / `sudo` / `impersonate` command:

1. Tracing the recursion: does the inner handler re-enter the dispatcher?
2. Does the inner handler carry over the original elevated id, clamped UP,
   or clamped DOWN?
3. Is there a depth counter?

If the inner id is clamped UP at any depth, a single ADMIN grant at depth 0
escalates to wrapper-chrome-level at every depth. If there is no depth
counter, the chain is unbounded. EpixNet's `as` (command.rs:447) clamps
`inner_id = if caller_elevated { req_id.max(WRAPPER_ID_BASE) } else req_id`
— UP, and no depth counter.

### 8. Content-verification canonicalization pitfall

`signed_data(content)` strips `sign` / `signs` and dumps with
sorted keys. The pitfalls to test:

- Is the canonicalization byte-stable across implementations? (Python
  `json.dumps(sort_keys=True)` vs Rust `serde_json::to_string` — must
  match byte-for-byte, otherwise cross-implementation signature breaks.)
- Does the strip list include ALL signature fields? If a field like
  `signers_sign` is signed OVER the signer list, AND the strip list does
  not strip `signers_sign` itself, the signature is over
  `signers_sign`-included content, which is wrong.
- Are numbers encoded the same way? `1.0` vs `1` will diverge.

EpixNet's `signed_data` (epix-content/src/lib.rs:29-36) strips only `sign`
and `signs` — this is fine because `signers_sign` is a SEPARATE signature
over `format!("{required}:{joined_signers}")` (verify.rs:516-521), not a
signature over the canonical content.

### 9. Look for `safe_identifier` validation gaps

When a Rust SQL layer validates identifiers (table names, column names)
before interpolation into DDL/DML, the check is usually applied to ONE
field (often the top-level table list). Look for OTHER fields that get
interpolated:

- `to_table[i].table` — the target table referenced in INSERT.
- `key_col`, `val_col` — dict-mapping column names.
- `import_cols[]` — per-entry allow-list of column names.
- `to_json_table[]`, `to_keyvalue[]` — meta-table column names.
- Index DDL strings (`table.indexes[]`) — these run as raw
  `conn.execute_batch(&format!("{idx};"))` and bypass every identifier
  check.

For EpixNet: `safe_identifier` (epix-db/src/schema.rs:125-134) validates
ONLY `schema.tables.keys()`. `to_table.table`, `key_col`, `val_col`,
`import_cols`, AND the raw `table.indexes[]` strings all bypass it. The
indexes bypass is the worst: `conn.execute_batch(&format!("{idx};"))` at
schema.rs:189 runs arbitrary SQL the xite-author put in
`dbschema.json["tables"][name]["indexes"][i]`. Stacked statements ARE
allowed under `execute_batch`. **Re-verify this index-DDL injection
vector during the next audit — it was identified but not chain-tested
in the Aug 2026 pass because the dbschema was treated as trusted
content.**

## Pitfalls

- `conn.prepare` vs `conn.execute_batch`: a "user-controlled SQL string"
  finding framed as stacked-statement SQLi will be FALSE if the sink
  uses `prepare` / single `execute`. Re-frame as "single-statement
  arbitrary execution (UPDATE / INSERT / ATTACH / CREATE / UNION SELECT
  reads)" — that is still HIGH severity.
- "Zip-slip in FilePack" claims are FALSE for `read_from_archive`:
  in-memory read only, no extraction. Don't open a zip-slip section for
  a code path that doesn't extract to disk.
- The `truthful` claim is "rustqlite blocks stacked statements". The
  attack surface is single-statement arbitrary execution. Two different
  things; don't conflate.
- Caches keyed ONLY by digest (not by `(digest, chain_height)`) are
  rotation-fragile. ALWAYS look for whether the cache key includes a
  monotonic context.
- A `safe_identifier` check applied to `tables.keys()` only is NOT a
  defense for `to_table`-referenced table names. Verify by grep — the
  validate function is usually called from ONE call site.
- The `as` recursion being depth-unbounded is invisible without reading
  both the outer handler and the inner-id clamp expression together.
  Inspect the clamp.
- EpixNet live-campaign pitfalls — the `as`+id:1M gateway-restrict bypass, the
  F2/F2-LIVE `permissionAdd` self-grant plants, `chartDbQuery` recon, the ATTACH
  DATABASE file-oracle, multi-xite `dbQuery` exfiltration, `certSelect` F10,
  the F11 ungated-command matrix, the F12 rebound write-gate, and the D1-D7
  live-proven findings — are preserved at
  examples/hunts/web3/rust-p2p-edge-case-audit/epixnet-live-pitfalls.md.

- Onion-key / Ed25519-expanded-key loading is OK if the path is
  data-dir-derived; flag if the path is user-param-derived.
- `signed_data` canonicalization: ANY number that round-trips differently
  between Python-and-Rust breaks cross-implementation signatures. Test
  with `1e10`, `0.1`, very large integers as f64-equivalent.
- **WS Origin bypass for non-browser clients:** `is_ws_origin_allowed`
  (state.rs:14293-14302) returns `true` when `origin_host.is_empty()`.
  Python's `websockets` library sends no Origin by default → passes the
  check. This is the primary technique for connecting to a live gateway
  WS without a browser. Don't assume Origin is always present.
## Inputs

- **crate_root** — e.g. `/root/epixnet-src/EpixNet-main`
- **target_crates** — the crates to fuzz: `epix-db`, `epix-content`,
  `epix-blob`, `epix-bt`, `epix-chain`, `epix-dht`, `epix-ui`,
  `epix-xite`, `epix-tor`, `epix-i2p`.
- **out_dir** — where PoC scripts go (default `/tmp/epixnet-fuzz/`).

## Workflow

1. **Read the trust graph (step 1 above)** before opening any source.
2. Read sink files in parallel: `lib.rs`, the `*.rs` handling the WS
   command, the `*.rs` implementing the verification / store. Batch
   `read_file` calls.
3. For every chained finding, give a `[Trigger] → [Effect] → [Trust
   Boundary Crossed]` triple.
4. For every blocked finding, give the file:line of the defense and the
   edge-case input that did not bypass it.
5. Run a "chainability" pass: can two or three findings be combined into
   a single hostile page's actions? List the composite explicitly.
6. Deposit any live PoC at `/root/epixnet-src/EpixNet-main/edge_case_poc.py`
   — exercises the chains. Do NOT deposit if the target is live; the
   operator runs PoCs themselves.

## Live exploitation: finding non-restricted nodes via P2P peer enumeration

(The EpixNet peer-harvest + UI-port fingerprinting + wrapper_key extraction pipeline,
with the proven node takeovers and the Python-old vs Rust-new comparison table —
preserved at examples/hunts/web3/rust-p2p-edge-case-audit/epixnet-live-exploitation-peer-enumeration.md.)

## References

(EpixNet case evidence — 11 reference write-ups, 3 exploit templates, 3 live-WS scripts —
is preserved at examples/hunts/web3/rust-p2p-edge-case-audit/ (references/, templates/,
scripts/); moved out of the product layer 2026-09-07. Body sections above cite the
individual files.)

## Full exploit chain (CHAINER consolidator pass)

(The EpixNet Branch A restricted-gateway / Branch B non-restricted-multiuser chain
matrix with file:line evidence at every gate, the `dbQuery` vs `chartDbQuery`
filtering asymmetry, and the two debrief answers — preserved at
examples/hunts/web3/rust-p2p-edge-case-audit/epixnet-full-exploit-chain.md. Reusable CHAINER
rule: build `action | prerequisite | code evidence (file:line) | proven status |
what could fail` per step, and discard any chain leg you cannot anchor to a real
code path.)

## Economic viability assessment (post-exploit)

Before investing more time in a deep chain, assess the financial worth of the target:

1. **Token check**: Query CoinGecko `/coins/<name>` for price, market cap, 24h volume, rank.
   - Market cap < $1M + volume < $5K = **illiquid, not worth stealing tokens**
   - Rank > #2000 = micro-cap, limited exit liquidity
2. **Operator balance**: Convert the operator's bech32 address to EVM hex, then
   `eth_getBalance` on the chain's EVM RPC. If balance = 0, there's nothing to steal
   even with full master seed compromise.
3. **bech32→EVM conversion** (proven for `epix1...` addresses):
   ```python
   charset = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'
   addr = 'epix1nvpckrh3pk0j0resrwazlrw8d8fd60uz76q4pr'
   data = addr[5:]  # strip 'epix1' prefix
   decoded = [charset.index(c) for c in data]
   # convertbits(decoded[:-6], 5, 8, False) → hex bytes → '0x...' EVM address
   ```
4. **Chain ID discovery**: `eth_chainId` on the EVM RPC endpoint from `configList`
   (EpixNet chain 1916 = epix.zone). Verify the chain is actually live before
   assuming token value.
5. **Verdict framework**: If operator balance = 0 AND market cap < $1M AND
   24h volume < $5K, pivot to bug bounty or switch targets. Don't spend hours
   on a master seed theft chain for a network with $0 in the vault.

(Proven-case numbers from the Aug 2026 EpixNet assessment — token price/mcap/volume and operator balance — preserved at examples/hunts/web3/rust-p2p-edge-case-audit/epixnet-economic-proven-2026-08.md.)

### Blockscout v2 API rich-list discovery (proven Aug 2026)

For custom EVM chains that use Blockscout as their block explorer, the v2 API
exposes a rich-list endpoint that does NOT require the `limit` parameter:

```
GET https://scan.<chain>.zone/api/v2/addresses?sort=balance&order=desc
GET https://scan.<chain>.zone/api/v2/stats  → total_addresses, total_transactions
```

Returns up to 50 addresses sorted by balance. Each item has `coin_balance`
(hex), `transactions_count`, optional `name`/`ens_domain_name`. Use this to:
1. Identify whether top holders match operator/dev addresses from the audit.
2. Cross-reference with bech32→EVM converted operator addresses.
3. Assess if ANY address has enough tokens to justify a theft chain.

(EpixNet rich-list outcome preserved at examples/hunts/web3/rust-p2p-edge-case-audit/epixnet-economic-proven-2026-08.md.)

## User communication preferences

(The operator's delivery and communication preferences from the EpixNet campaign — paste output inline, proactive financial-worth assessment, bundle/jatidiri delivery, Telegram file-splitting — are preserved as operator notes at docs/operator/rust-p2p-operator-notes.md, not hunting methodology.)

## Sibling skills
- `epixnet-ui-redteam` — the F1-F9 WS-command-API red-team findings from the
  prior pass, preserved as a case at `examples/hunts/web2/epixnet-ui-redteam/`. This skill
  extends that map with the Aug 2026 edge-case-fuzz findings (F10-F13)
  and adds the methodology around them. Read both when auditing EpixNet.
  **Note**: when both skills are loaded, the `epixnet-ui-redteam` SKILL.md
  lists F8 as "not a new primitive"; the Aug 2026 pass found that the
  F8/`as` clamp-up behavior IS a chainable escalation when combined with
  F2 — see the F10-composite section in the reference file.
  **CHAINER pass (2026-08-17)**: when consolidating, the F1-F9 catalog gives you
  the individual findings; the "Full exploit chain" section above gives you the
  assembled Branch A / Branch B matrix with file:line evidence at every gate.
  Read both before drafting a chain matrix, and store the full step-by-step
  walkthrough in `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-full-chain-2026-08-17.md`.
