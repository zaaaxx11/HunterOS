"""EDUCATIONAL - deliberately vulnerable, localhost only.

PracticeVault: a tiny practice target for the HUNT-OS FIRST BLOOD run.
It is INTENTIONALLY insecure so the hunt engine has something real to find.
Binds 127.0.0.1 ONLY (hardcoded below) - never expose this to a network.

Deliberate flaws (each maps to a hunt lane):
  - /admin      the privilege decision is a client-asserted cookie (`role`);
                `role=admin` is a trivially forgeable full admin takeover.
                The admin panel reveals "SECRET: internal transfer keys".
  - /transfer   POST from,to,amount mutates the in-memory balance dict with
                NO authentication at all and no amount sanity checks
                (fund-theft path).
  - /api/users  returns usernames AND (unsalted md5) password hashes
                (info leak -> credential compromise).
  - /           harmless index.

Run:  python practice_app.py [port]   (default port 8765)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"  # hardcoded on purpose: localhost only, no exceptions
DEFAULT_PORT = 8765

# In-memory state (fresh on every restart).
BALANCES = {"vault": 1_000_000, "alice": 500, "bob": 300}

# Unsalted md5 "password hashes" (educational: crackable in seconds).
USERS = {
    "alice": hashlib.md5(b"password").hexdigest(),
    "bob": hashlib.md5(b"letmein").hexdigest(),
    "vault_service": hashlib.md5(b"qwerty123").hexdigest(),
}


def _page(title: str, body: str, code: int = 200) -> tuple[int, bytes]:
    html = f"<html><head><title>{title}</title></head><body>{body}</body></html>"
    return code, html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "PracticeVault/1.0"

    # -- helpers ---------------------------------------------------------
    def _reply(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._reply(code, json.dumps(obj, indent=2).encode("utf-8"), "application/json")

    def _cookie_role(self) -> str:
        """Client-asserted privilege: whatever the request says, wins.

        THE flaw: no session, no signature, no server-side store. Any client
        can declare itself admin with one header.
        """
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            if "=" in part:
                key, val = part.split("=", 1)
                if key.strip() == "role":
                    return val.strip()
        return "user"

    # -- routes ----------------------------------------------------------
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            body = (
                "<h1>PracticeVault</h1>"
                "<p>Educational practice target. Routes: /admin, /transfer (POST), /api/users</p>"
            )
            code, page = _page("PracticeVault index", body)
            self._reply(code, page)
        elif path == "/admin":
            role = self._cookie_role()
            if role == "admin":
                body = (
                    "<h1>PracticeVault ADMIN PANEL</h1>"
                    "<p>Welcome, administrator.</p>"
                    "<p>SECRET: internal transfer keys</p>"
                )
                code, page = _page("admin panel", body)
                self._reply(code, page)
            else:
                body = f"<h1>403</h1><p>access denied (role={role})</p>"
                code, page = _page("denied", body, code=403)
                self._reply(code, page)
        elif path == "/api/users":
            # Info leak: usernames AND password hashes in one unauthenticated dump.
            payload = {
                "users": [
                    {"username": name, "password_hash": digest}
                    for name, digest in USERS.items()
                ]
            }
            self._json(200, payload)
        elif path == "/transfer":
            body = "<h1>405</h1><p>transfer requires POST (from,to,amount)</p>"
            code, page = _page("method not allowed", body, code=405)
            self._reply(code, page)
        else:
            self._reply(404, b"<h1>404 not found</h1>")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/transfer":
            # Fund-theft path: NO authentication, NO ownership check, NO
            # amount validation (negative amounts mint money), NO
            # sufficient-balance check.
            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            src = form["from"][0]
            dst = form["to"][0]
            amount = int(form["amount"][0])  # crashes on junk: single-request DoS only
            BALANCES[src] -= amount
            BALANCES[dst] += amount
            self._json(
                200,
                {
                    "status": "ok",
                    "transferred": amount,
                    "from": src,
                    "to": dst,
                    "balances": BALANCES,
                },
            )
        else:
            self._reply(404, b"<h1>404 not found</h1>")

    def log_message(self, fmt: str, *args) -> None:  # keep default access log on stderr
        super().log_message(fmt, *args)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer((HOST, port), Handler)
    print(
        f"practice_app (EDUCATIONAL, deliberately vulnerable, localhost only) "
        f"listening on http://{HOST}:{port} pid={os.getpid()}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
