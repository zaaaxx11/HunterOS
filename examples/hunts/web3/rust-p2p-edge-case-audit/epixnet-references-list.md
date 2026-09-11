# Reference-file index carried by the SKILL.md (all 11 refs moved to examples 2026-09-07)

Cut verbatim from `soul/skills/web3/rust-p2p-edge-case-audit/SKILL.md` during the
S2b-2 content pass (EpixNet reference-target case material; preserved, not deleted).
The epixnet reference write-ups, exploit templates, and live-WS scripts live under
`examples/hunts/web3/rust-p2p-edge-case-audit/` (references/, templates/, scripts/).

---

## References
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/edge-case-fuzz-rustdb-2026-08.md` — Aug 2026 EpixNet
  edge-case fuzz pass: file:line triggers, rustqlite single-statement vs
  multi-statement behavior, populate.rs `insert_row` interpolation
  surface, cache-asymmetry TOCTOU trace, blocked-vs-chained analysis of
  every Rust sink enumerated in `## Negative confirmations` of the
  sibling `epixnet-ui-redteam` skill.
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-live-2026-08.md` — Aug 2026 live
  verification on gateway.epixnet.io: F2 `permissionAdd ADMIN` plant
  succeeds on restricted gateway, persists to `permissions.json`, cannot
  be removed via WS. Gateway recon techniques: `chartDbQuery` +
  `pragma_database_list` data-dir leak, `serverInfo`/`siteList`
  enumeration. 4-agent CDC delegation results. PoC script reference.
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep-2026-08.md` — Aug 2026 deep gateway
  exploit (session 2): ATTACH DATABASE file existence oracle (confirms
  master_seed.json, users.json, permissions.json, config.json exist), file
  corruption via CREATE TABLE + INSERT, multi-xite dbQuery data exfiltration
  (Talk/Search/Post/Blog xites — full user content dumped pre-auth),
  chart.db already-attached shortcut, 49 SQLite fuzz techniques, second
  4-agent CDC delegation results.
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-deep2-2026-08-17.md` — Aug 2026 session 3
  deep gateway exploit: `as`+id:1M cross-xite execution LIVE PROVEN (D1),
  mass ADMIN+NOSANDBOX plant across all xites (D2), cross-xite dbQuery write+
  stored XSS via comment modification (D3), SQLite 3.50.2 fingerprint with
  virtual table availability (D4), expanded file oracle (27 paths including
  /proc/self/environ, .env, private/keys.json — D5), arbitrary /tmp file
  write (D6), 12 auth user identities leaked (D7), Post xite content dump
  (D8). Also documents what still blocked: file content read impossible
  (sqlite_blob not compiled), fileWrite blocked by WRITE_COMMANDS gate,
  no non-restricted Rust multiuser node found despite 2367 IP scan.
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-gateway-command-taxonomy-2026-08.md` — Complete
  GATEWAY_READ_COMMANDS / WRITE_COMMANDS / NEW_XITE_COMMANDS /
  DELETE_XITE_COMMANDS lists with line numbers. Dispatch gate order
  (7 gates, lines 335-465). New findings: F10 (certSelect non-admin
  identity swap), F11 (visitor-executable command matrix on
  ui_restrict=true), F12 (`as` rebound session — restrict persists via
  WsSession::new trusted=false, but write gate checks xite_owned(target)
  on rebound, enabling write-to-owned-xite chains).
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-proven-exploits-2026-08-17.md` — Aug 2026 session 4:
  7 standalone PoC scripts (file oracle, arb file write, file corruption,
  user leak, mass admin plant, cross-xite dump, chart exfil) all tested
  live on gateway.epixnet.io. SQLite 3.50.2 full environment fingerprint.
  File-content-read impossibility verdict after 49+ techniques.
  Templates: `examples/hunts/web3/rust-p2p-edge-case-audit/templates/ (epixnet_exploit_01/05/06)` (compressed PoC
  versions for quick deployment; full versions at `/root/exploit_0*.py`).
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-final-poc-suite-2026-08-17.md` — Aug 2026 session 5:
  Final 7-script PoC suite with complete live output. Key techniques:
  `as`+id:1M cross-xite mass ADMIN+NOSANDBOX plant (18/18 xites),
  ATTACH DATABASE file oracle (26 paths confirmed), arbitrary /tmp file write,
  cross-xite dbQuery dump (529 rows, 7 DBs), chart.db exfil (1.09M rows).
  SQLite 3.50.2 fingerprint with all available functions and vtable modules.
  12 leaked user identities. File-content-read impossibility verdict.
  Full live output in `output_0{1-7}_*.txt` files + `epixnet_exploit_results.tar.gz`.
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-final-poc-economic-2026-08-18.md` — Aug 2026 session 6:
  7 PoC scripts re-tested live with full output capture. EPIX token economic
  assessment (price $0.00009, mcap $796K, volume $1,452, operator balance 0).
  bech32→EVM address conversion technique for balance checking.
  User communication preferences: paste output inline, assess financial
  worth proactively, send all results not selectively.
  SQLite ATTACH destructive-write technical note (corrupts, cannot read).
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-economic-assessment-2026-08-18.md` — Aug 2026 session 7:
  Complete economic assessment workflow: CoinGecko market data, bech32→EVM
  address conversion code, Blockscout v2 API rich-list discovery, EVM RPC
  balance check, verdict framework. EpixNet results: 36,964 addresses,
  50,937 txs, top holder 22.3T EPIX ($1.99B notional), operator 0 EPIX.
  Zip delivery pattern (exploits + outputs + reports + skills + memory +
  config + scan-data + README).
- `examples/hunts/web3/rust-p2p-edge-case-audit/references/epixnet-p2p-node-discovery-2026-08.md` — Aug 2026 live
  exploitation: harvesting P2P peer IPs via BitTorrent tracker announce +
  WS `announcerStats`, scanning for non-restricted UI bindings,
  wrapper_key extraction from dashboard HTML, full takeover of
  171.224.80.92:42222 (ui_ip=0.0.0.0, ui_restrict=false). Python-old
  vs Rust-new behavior comparison table.
