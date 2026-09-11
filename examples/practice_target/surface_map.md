# Surface Map: PracticeVault (http://127.0.0.1:8765)

Recon method: black-box probing of the running app (curl), 2026-09-05.
All traffic to 127.0.0.1 only. RoE: own practice app, full authorization.

## Routes observed

| # | Route          | Methods      | Observed response |
|---|----------------|--------------|-------------------|
| 1 | `/`            | GET          | 200, HTML index: "PracticeVault ... Routes: /admin, /transfer (POST), /api/users". Server banner `PracticeVault/1.0 Python/3.13.7` (exact Python version disclosed). |
| 2 | `/admin`       | GET          | 403 without cookie: `access denied (role=user)` - the denial message itself names the deciding parameter (`role`). With `Cookie: role=user`: same 403. The role value is echoed back into the body (reflection of client input). |
| 3 | `/api/users`   | GET          | 200, unauthenticated JSON dump of `username` AND `password_hash` for 3 accounts (alice, bob, vault_service). 32-hex-char hashes (md5-shaped, unsalted: `5f4dcc3b...` is the well-known digest of a dictionary word). |
| 4 | `/transfer`    | GET -> 405   | "transfer requires POST (from,to,amount)" - the error discloses the full expected POST parameter list. |
| 5 | `/nonexistent` | GET          | 404. |
| 6 | `/admin` OPTIONS | OPTIONS    | 501 Unsupported method (`BaseHTTPRequestHandler` default) - no method enumeration leak beyond that. |

## Trust boundaries inferred from observed behavior

- TB1 `/admin`: privilege decision made from the `Cookie: role=<v>` header
  (client-asserted). Denial message reflects the presented role back.
  Assumption to break: "the server validates role server-side".
- TB2 `/transfer`: POST form `from,to,amount` (disclosed by the 405 page).
  No auth headers seen required anywhere else; must test whether transfer
  requires any credential or none. State-mutating (balances).
- TB3 `/api/users`: credential material (password hashes) crosses the trust
  boundary to any unauthenticated client. Data flow: storage -> output with
  no redaction and no auth gate.

## Assets

- In-memory balance dict (at least: vault, alice, bob) - the value sink.
- Admin panel content: "SECRET: internal transfer keys" (protected string).
- Password hashes of 3 named accounts.

## Server stack

`PracticeVault/1.0 Python/3.13.7` - stdlib `http.server`-class server,
single banner, HTTP/1.0 responses, threading implied by prompt parallel
handling (to be confirmed by the Fuzz-Engineer lane under concurrent load).
