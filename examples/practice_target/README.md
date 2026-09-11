# PracticeVault - educational practice target

**EDUCATIONAL - deliberately vulnerable, localhost only.**

`practice_app.py` is a tiny stdlib (`http.server`) web app built for the
HUNT-OS FIRST BLOOD run. It is intentionally insecure so the hunt engine has
something real (and harmless) to find. It binds `127.0.0.1` ONLY and must
never be exposed to a network.

Run it:

```bash
python practice_app.py          # default port 8765
python practice_app.py 9000     # port override via argv
```

Deliberate flaws (each maps to a hunt lane):

| Route       | Flaw                                                                 |
|-------------|----------------------------------------------------------------------|
| `/admin`    | Privilege is a client-asserted cookie (`role`); `role=admin` is a trivially forgeable admin takeover. Panel shows `SECRET: internal transfer keys`. |
| `/transfer` | POST `from,to,amount` mutates balances with NO authentication, no amount validation (negative amounts mint money), no sufficient-balance check. |
| `/api/users`| Unauthenticated dump of usernames AND unsalted md5 password hashes.  |
| `/`         | Harmless index.                                                      |

In-memory balances reset on every restart (`vault: 1,000,000`, `alice: 500`,
`bob: 300`). The `poc/` directory holds the ladder PoCs used in the FIRST
BLOOD run (`poc1_*` = in-code step, `poc2_*` = proven-live step).
`firstblood.db` is the hunt database for the run (gitignored - the run log
`FIRSTBLOOD.md` is the artifact that gets kept).

Do not run this app anywhere but your own machine, and do not point it at
anything you do not own.
