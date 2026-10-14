#!/usr/bin/env python3
"""
RPC Edge-Case Fuzzer for Blockchain JSON-RPC Endpoints
Fuzzes: overflow values, massive slots, negative gas, 0x0 address, type confusion, large calldata
Adapted from MultiVAC mainnet fuzz 2026-08-17.

Usage: python3 rpc_fuzz.py <RPC_URL> [CONTRACT_ADDR]
Default: https://rpc.mtv.ac 0x2781bcbdad5c702eb9258d82ac32a94f3db95e69

Output: stdout + rpc_fuzz_results.json
"""
import json
import requests
import sys
import time

RPC_URL = sys.argv[1] if len(sys.argv) > 1 else "https://rpc.mtv.ac"
CONTRACT = sys.argv[2] if len(sys.argv) > 2 else "0x2781bcbdad5c702eb9258d82ac32a94f3db95e69"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
HEADERS = {"Content-Type": "application/json", "User-Agent": UA}
TIMEOUT = 20
MAX_UINT = "0x" + "f" * 64

results = []
def log(name, status, body, exploit):
    snippet = body[:500] if body else ""
    results.append({"test": name, "status": status, "body": snippet, "exploitability": exploit})
    print(f"\n{'='*60}\nTEST: {name}\nSTATUS: {status}\nBODY: {snippet}\nEXPLOIT: {exploit}\n{'='*60}")

def rpc(method, params, id=1):
    try:
        r = requests.post(RPC_URL, json={"jsonrpc":"2.0","method":method,"params":params,"id":id}, headers=HEADERS, timeout=TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)

# --- Overflow tests ---
for field in ["value", "gas", "gasPrice"]:
    params = {"to": CONTRACT, "data": "0x", field: MAX_UINT}
    s, b = rpc("eth_call", [params, "latest"])
    log(f"eth_call overflow {field} (max uint256)", s, b, f"MEDIUM - {field} overflow handling")

# --- Negative tests ---
for field in ["gas", "gasPrice"]:
    params = {"to": CONTRACT, "data": "0x", field: "-0x1"}
    s, b = rpc("eth_call", [params, "latest"])
    log(f"eth_call negative {field} (-0x1)", s, b, f"HIGH - negative {field} handling")

# --- Zero address ---
s, b = rpc("eth_call", [{"to": "0x" + "0"*40, "data": "0x"}, "latest"])
log("eth_call to 0x0 address", s, b, "INFO")
for size_name, size in [("5KB", 5000), ("50KB", 50000), ("500KB", 500000)]:
    s, b = rpc("eth_call", [{"to": "0x" + "0"*40, "data": "0x" + "ff" * size, "gas": "0xffffffff"}, "latest"])
    log(f"eth_call to 0x0 with {size_name} calldata", s, b, f"HIGH - {size_name} calldata OOM test")

# --- Storage slot fuzz ---
s, b = rpc("eth_getStorageAt", [CONTRACT, MAX_UINT, "latest"])
log("eth_getStorageAt massive slot (max uint256)", s, b, "LOW")
s, b = rpc("eth_getStorageAt", [CONTRACT, "-0x1", "latest"])
log("eth_getStorageAt negative slot (-0x1)", s, b, "LOW")

# --- sendTransaction fuzz ---
for desc, params in [
    ("negative gas", {"from": CONTRACT, "to": "0x"+"0"*40, "gas": "-0x1", "value": "0x0"}),
    ("overflow gas", {"from": CONTRACT, "to": "0x"+"0"*40, "gas": MAX_UINT, "value": "0x0"}),
    ("overflow value", {"from": CONTRACT, "to": "0x"+"0"*40, "gas": "0x5208", "value": MAX_UINT}),
    ("negative value", {"from": CONTRACT, "to": "0x"+"0"*40, "gas": "0x5208", "value": "-0x1"}),
]:
    s, b = rpc("eth_sendTransaction", [params])
    log(f"eth_sendTransaction {desc}", s, b, "CRITICAL" if "negative" in desc or "overflow" in desc else "MEDIUM")

# --- Missing 'to' field ---
s, b = rpc("eth_call", [{"data": "0x6080604052"}, "latest"])
log("eth_call missing 'to' (contract creation simulation)", s, b, "MEDIUM")

# --- All overflow combo ---
params = {"to": CONTRACT, "gas": MAX_UINT, "gasPrice": MAX_UINT, "value": MAX_UINT, "data": "0x"}
s, b = rpc("eth_call", [params, "latest"])
log("eth_call all overflow (gas+gasPrice+value)", s, b, "HIGH")

# --- estimateGas overflow ---
s, b = rpc("eth_estimateGas", [{"to": CONTRACT, "value": MAX_UINT, "gas": MAX_UINT, "gasPrice": MAX_UINT}])
log("eth_estimateGas overflow params", s, b, "MEDIUM")

# --- Invalid hex ---
s, b = rpc("eth_call", [{"to": CONTRACT, "data": "0xZZZZ"}, "latest"])
log("eth_call invalid hex (0xZZZZ)", s, b, "LOW - error message may leak impl details")

# --- Error revelation ---
s, b = rpc("eth_call", None)
log("eth_call null params", s, b, "MEDIUM - may reveal stack trace")
s, b = rpc("eth_call", ["just_a_string", "latest"])
log("eth_call string param (type confusion)", s, b, "MEDIUM - Go struct name leak")
s, b = rpc("eth_call", [{"to": CONTRACT, "data": "0x", "from": {"$ne": None}}, "latest"])
log("eth_call NoSQL-like params in RPC", s, b, "MEDIUM")
s, b = rpc("eth_call", [])
log("eth_call empty params", s, b, "LOW")

# --- Malformed / empty JSON ---
try:
    r = requests.post(RPC_URL, data="this is not json", headers=HEADERS, timeout=15)
    log("Malformed non-JSON POST", r.status_code, r.text, "MEDIUM - may reveal server type")
except Exception as e:
    log("Malformed non-JSON POST", -1, str(e), "ERROR")
try:
    r = requests.post(RPC_URL, json={}, headers=HEADERS, timeout=15)
    log("Empty JSON object", r.status_code, r.text, "LOW")
except Exception as e:
    log("Empty JSON object", -1, str(e), "ERROR")

# --- Large calldata OOM ---
for size_name, size in [("50KB", 50000), ("500KB", 500000)]:
    s, b = rpc("eth_call", [{"to": CONTRACT, "data": "0x" + "ab" * size}, "latest"])
    log(f"eth_call {size_name} calldata (OOM test)", s, b, "HIGH")

with open("rpc_fuzz_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nTotal tests: {len(results)}\nResults: rpc_fuzz_results.json")
