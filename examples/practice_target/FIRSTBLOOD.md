# FIRST BLOOD — the first full pipeline hunt

- Date: 2026-09-05
- Engine: ZCode agent running the lane-runner round loop (soul/roles/lane-runner.md)
  under the HUNT-BRIDGE contract (soul/bridge/HUNT-BRIDGE.md)
- Target: PracticeVault — a deliberately vulnerable practice web app we built for
  this run (`practice_app.py`, stdlib `http.server`, binds 127.0.0.1 ONLY, port 8765)
- Hunt db: `examples/practice_target/firstblood.db` (HUNT_DB; gitignored — this log
  and REPORT.md are the kept artifacts)
- Working rules: every `hunt` command run from the `app/` directory with
  `PYTHONPATH=src HUNT_DB=<abs path to firstblood.db> python -m huntos ...`;
  everything through the CLI; no direct sqlite writes; all HTTP traffic to
  127.0.0.1 only; the practice app is the only target; app/ source untouched.

Result up front: **7 findings recorded, 6 proven-live, 1 overturned
(bookkeeping casualty, not a hunt kill), 2 waves, target archived.**
Zero process left on port 8765 (verified at the end).

---

## 0. The practice target (built first, hunted second)

Created `examples/practice_target/`:

- `practice_app.py` — EDUCATIONAL, deliberately vulnerable, localhost only.
  Four routes, four flaws, one per lane:
  - `/admin` — privilege decided by a client-asserted `role` cookie
    (`role=admin` = admin takeover; panel shows `SECRET: internal transfer keys`)
  - `/transfer` — POST `from,to,amount` mutates the balance dict with NO auth,
    no amount validation, no sufficient-balance check (fund-theft path)
  - `/api/users` — unauthenticated dump of usernames + unsalted md5 password hashes
  - `/` — harmless index
- `README.md` — educational-use explanation.
- Balances (fresh per restart): `vault: 1,000,000`, `alice: 500`, `bob: 300`.

App started in the background:

```
$ python practice_app.py
practice_app (EDUCATIONAL, deliberately vulnerable, localhost only) listening on http://127.0.0.1:8765 pid=...
```

## 1. Recon (real black-box probing of the running app)

Commands and what came back (all against 127.0.0.1:8765):

```
$ curl -s -i http://127.0.0.1:8765/
HTTP/1.0 200 OK
Server: PracticeVault/1.0 Python/3.13.7
...
<html><head><title>PracticeVault index</title></head><body><h1>PracticeVault</h1>
<p>Educational practice target. Routes: /admin, /transfer (POST), /api/users</p></body></html>

$ curl -s -i http://127.0.0.1:8765/admin          # no cookie
HTTP/1.0 403 Forbidden
...access denied (role=user)...

$ curl -s -i -H "Cookie: role=user" http://127.0.0.1:8765/admin
HTTP/1.0 403 Forbidden
...access denied (role=user)...     # the denial message names the deciding parameter

$ curl -s -i http://127.0.0.1:8765/api/users
HTTP/1.0 200 OK
{
  "users": [
    {"username": "alice", "password_hash": "5f4dcc3b5aa765d61d8327deb882cf99"},
    {"username": "bob", "password_hash": "0d107d09f5bbe40cade3de5c71e9e9b7"},
    {"username": "vault_service", "password_hash": "3fc0a7acf087f549ac2b266baf94b8b1"}
  ]
}

$ curl -s -i http://127.0.0.1:8765/transfer        # GET
HTTP/1.0 405 Method Not Allowed
...transfer requires POST (from,to,amount)...      # the 405 discloses the POST schema

$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/nonexistent
404
$ curl -s -o /dev/null -w "%{http_code}\n" -X OPTIONS http://127.0.0.1:8765/admin
501
```

Wrote `examples/practice_target/surface_map.md` from exactly these observations
(routes, trust boundaries TB1/TB2/TB3, assets, server banner disclosing the exact
Python version). Recorded through the gate.

## 2. Phase 0 — scoring, RoE, artifacts, phases

```
$ hunt target add PracticeVault http://127.0.0.1:8765 --notes "practice, educational"
target #1 added: PracticeVault (http://127.0.0.1:8765) phase=scoring

$ hunt target roe 1 --hosts "127.0.0.1" --actions "recon,read,auth-test,mutate" --notes "own practice app - full authorization"
roe updated for target #1: actions=auth-test,mutate,read,recon hosts=127.0.0.1
(hosts are informational only — only actions are enforced; default-deny for mutate)

$ hunt score 1 7.0
target #1 scored ev=7.0

$ hunt artifact 1 surface_map ../examples/practice_target/surface_map.md
artifact surface_map recorded on target #1: ../examples/practice_target/surface_map.md

$ hunt phase 1 recon
target #1 phase -> recon

$ hunt artifact 1 attack_plan ../examples/practice_target/attack_plan.md
artifact attack_plan recorded on target #1: ../examples/practice_target/attack_plan.md

$ hunt phase 1 classify
target #1 phase -> classify

$ hunt phase 1 hunting
target #1 phase -> hunting
```

`attack_plan.md` names three real flaw hypotheses per lane (H-A1..H-A3 Architect,
H-R1..H-R3 Red-Teamer, H-F1..H-F3 Fuzz-Engineer, H-C1..H-C3 Chainer), each tied to
a trust boundary from the surface map, plus an honest round-1 scope note: type and
magnitude edges get fuzzed in round 1; SIGN edges are left as the round-2
blind-spot question.

RoE was set BEFORE any mutate finding existed — the `hunt status` retroactive-
authorization check would have flagged us otherwise. It stayed silent all run.

## 3. ROUND 1 (wave 1) — spawn, cross-correct, record

```
$ hunt wave open 1 "architect-trustgraph,redteam-invariant,fuzz-boundary,chain-handoff"
wave #1 opened (number 1) lanes=architect-trustgraph,redteam-invariant,fuzz-boundary,chain-handoff
```

### 3a. Lane probes (real requests, real responses)

**Red-Teamer (invariant breaker):**

```
[RT H-R1] forge role=admin:
$ curl -s -i -H "Cookie: role=admin" http://127.0.0.1:8765/admin
HTTP/1.0 200 OK
<html><head><title>admin panel</title></head><body><h1>PracticeVault ADMIN PANEL</h1>
<p>Welcome, administrator.</p><p>SECRET: internal transfer keys</p></body></html>

[RT H-R2] bare POST /transfer, zero credentials, impersonating vault:
$ curl -s -i -X POST http://127.0.0.1:8765/transfer -d "from=vault&to=attacker&amount=100"
(no response - curl exit 52)
```

The H-R1 forge works instantly: one header, full admin, secret included.
H-R2 produced a surprise: connection closed with NO response — the app log shows
`KeyError: 'attacker'`: the debit executed (`vault` 1,000,000 -> 999,900), then the
credit crashed on the unknown destination. A failed transfer DESTROYED 100 units.
Follow-up balance read via an amount=0 probe confirmed `vault: 999900` persisted.
Invariant broken: "a failed transfer leaves balances unchanged."

**Fuzz-Engineer (edge cases on /transfer):**

```
[FE H-F1a] amount=abc          -> connection reset (curl exit 52); server survived
[FE H-F1b] amount=1e3          -> connection reset; server survived
[FE H-F2]  missing amount      -> connection reset; server survived
[FE H-F3a] amount=0            -> 200 {"transferred": 0, ...balances echo...}
[FE H-F3b] amount=999999999    -> 200 {"transferred": 999999999,
                                   "balances": {"vault": -999000099,
                                                "bob": 1000000300, ...}}
```

Two real results: (1) junk input crashes the request handler but the server
survives every crash (next request succeeds) — a transient failure, not DoS;
(2) the overdraw went THROUGH — no sufficient-balance check, vault driven negative
by an unauthenticated request. Unbounded theft.

**Architect (trust graph):** works from the surface map + response behavior:
TB1 (`role` cookie = client-asserted privilege), TB2 (`/transfer` state write with
no visible principal concept anywhere), TB3 (`/api/users` storage->output crossing
emitting password hashes with no auth gate and no redaction). Hands TB1/TB2 to the
Red-Teamer (already broken above); claims TB3 as its own finding — the leak is
credential material, and the md5 digests are unsalted dictionary-crackable.

**Chainer (handoffs):** the gadget graph writes itself:
`/api/users` (names accounts + hashes) -> forged `role=admin` cookie (admin
context + the "internal transfer keys" secret) -> `/transfer` (theft). Entry:
unauthenticated at every handoff. Honest dead-ends recorded: H-C2 (replay cracked
passwords) dies — there is no login route to replay against; H-C3 (the admin
SECRET as key material) dies — the string is display-only decoy. Chain claim is
limited to what the gadgets actually did.

### 3b. CROSS-CORRECTION (attack every candidate before recording)

- Attacked the admin forge: tried `role=ADMIN` (403 — exact match required, but
  "admin" is trivially guessable), `role=admin; session=x` (200 — extra cookies
  ignored). No session establishment, no signature: the cookie IS the privilege.
  **SURVIVES.**
- Attacked the unauth transfer: fresh connection read back the same mutated
  balances — state is real and shared, not per-session fakery. Bare POST with zero
  headers is enough. **SURVIVES.**
- Attacked the info leak: "maybe the hashes are salted decoys" — `5f4dcc3b...` is
  the canonical unsalted md5 of a common dictionary word (crack proven later in
  poc2). **SURVIVES.**
- Attacked the destroyed-funds observation: repeated the crash with an unknown
  SOURCE (`from=ghost`) — balances unchanged (KeyError fires before any mutation).
  The destroy case is specifically unknown DESTINATION (debit executes, credit
  crashes). Rollback checked on a fresh connection: still debited. **SURVIVES.**
- **KILL 1 — "handler crash = DoS":** the server survived every crash; impact is a
  single dropped request. Killed, recorded as lesson #1.
- **KILL 2 — "cookie flags missing (HttpOnly/Secure)":** no XSS/injection sink
  exists to deliver a cookie-stealing script, and the role cookie is client-asserted
  anyway — there is nothing to steal that forging does not grant more cheaply.
  Killed, recorded as lesson #2.

### 3c. RECORD (the database is the only ledger)

```
$ hunt lesson add PracticeVault "handler-crash on bad input is a transient single-request failure, not DoS - server survived every crash; do not record availability findings without a persistence test" --target-id 1 --notes "cross-correction kill: fuzz lane candidate 'amount=abc DoS' fell"
lesson #1 recorded (skill): ...

$ hunt lesson add PracticeVault "missing cookie flags (HttpOnly/Secure) is not a finding without a delivery sink - no XSS sink existed and the role cookie is client-asserted, so there is nothing to steal that forging does not grant more cheaply" --target-id 1 --notes "cross-correction kill: architect lane candidate 'cookie flags' fell"
lesson #2 recorded (skill): ...

$ hunt finding add 1 "Admin panel takeover via client-asserted role cookie (forgeable in one header)" Access --severity critical --action auth-test --notes "..."
finding #1 added [critical] ... (theoretical, action=auth-test)

$ hunt finding add 1 "Unauthenticated /transfer mutates shared balances; no sufficient-balance check allows unbounded overdraw" Access --severity critical --action mutate --notes "..."
finding #2 added [critical] ... (theoretical, action=mutate)

$ hunt finding add 1 "/api/users dumps usernames and unsalted md5 password hashes to any unauthenticated client" Web2 --severity high --action read --notes "..."
finding #3 added [high] C:/Program Files/Git/api/users dumps usernames ... (theoretical, action=read)

$ hunt finding add 1 "Failed /transfer destroys funds: debit executes before credit, crash on unknown destination leaves balance debited" Logic --severity high --action mutate --notes "..."
finding #4 added [high] ... (theoretical, action=mutate)

$ hunt finding add 1 "Chain: /api/users recon -> forged admin cookie -> unauthenticated transfer = unauth to admin+theft in one script" Access --severity critical --action mutate --notes "..."
finding #5 added [critical] ... (theoretical, action=mutate)
```

**F-3's title was silently mangled by Git-Bash/MSYS path conversion** (the
leading-slash argument `/api/users` became `C:/Program Files/Git/api/users`).
There is no CLI command to edit a title, so the honest repair is: overturn the
corrupted row (audit trail kept), re-record cleanly, log a lesson:

```
$ hunt finding overturn --id 3 --by "lane-runner: title corrupted by Git-Bash POSIX path conversion (leading-slash arg became C:/Program Files/Git/api/users); re-recorded as F-6"
finding #3 OVERTURNED by ... (audit trail kept)

$ MSYS_NO_PATHCONV=1 hunt finding add 1 "/api/users dumps usernames and unsalted md5 password hashes to any unauthenticated client" Web2 --severity high --action read --notes "... (re-record after shell mangling)"
finding #6 added [high] /api/users dumps usernames ... (theoretical, action=read)

$ hunt lesson add PracticeVault "Git-Bash/MSYS converts leading-slash CLI arguments into Windows paths ...; quote-guard with MSYS_NO_PATHCONV=1 or avoid leading-slash args; a mangled finding title cannot be edited, only overturned and re-recorded" --target-id 1 --notes "..."
lesson #3 recorded (skill): ...
```

(The lesson's own text got mangled mid-string too — `C:/Program Files/Git/...`
inside the sentence was re-converted to `C;C:\Program Files\Git\...` and lessons
cannot be edited either. See friction log.)

### 3d. The action-label decision (required by the mission)

Cookie forge recorded as **auth-test**, not mutate: the RoE action scale describes
what the exploit DOES to the target. Forging `role=admin` and reading `/admin`
sends a crafted credential and reads — no server-side state changes. Mutate is
reserved for exploits that write target state: `/transfer` (F-2, F-4, F-5, F-7).
Read for pure reads: `/api/users` (F-6). All four RoE actions were authorized
up front; had they not been, F-2/F-4/F-5/F-7 could never have reached proven-live
(the promote gate enforces mutate-in-RoE, default-deny).

### 3e. The ladder (per finding: poc1 -> in-code, verify + challenge, poc2 -> proven-live)

Every ladder step used a DIFFERENT, really-run PoC file and a fresh evidence ref.
All PoCs are real runnable scripts in `examples/practice_target/poc/` (stdlib only,
exit 0 = reproduced). Verifier bodies are actual captured transcripts; digests and
plaintexts are withheld from the ledger text (the gate refuses raw secrets).

**F-1 (admin cookie forge):**
- `poc1_admin_cookie_forge.py` — baseline 403, control role=user 403, forged
  role=admin 200 + secret panel. `REPRODUCED`.
  `hunt finding promote --id 1 ... --poc-path ../examples/practice_target/poc/poc1_admin_cookie_forge.py`
  -> `finding #1 promoted -> in-code`
- `hunt verify 1 http_transcript "GET /admin ... Cookie: role=admin || HTTP/1.0 200 OK ... SECRET: internal transfer keys"`
  -> recorded. `hunt challenge 1 "attacked the forge: role=ADMIN 403, padded cookie 200, no other header needed; attacked impact - panel carries the protected SECRET string"` -> recorded.
- `poc2_admin_secret_extraction.py` — 403/200 differential from one header swap +
  protected asset EXTRACTED + stability re-request. `REPRODUCED`.
  `hunt finding promote --id 1 ... --poc-path .../poc2_admin_secret_extraction.py`
  -> `finding #1 promoted -> proven-live`

**F-2 (unauth transfer / overdraw):**
- `poc1_transfer_unauth.py` — zero-credential POST moved 1 unit bob->alice;
  amount=0 balance-echo probes read real state before/after (+1/-1). `REPRODUCED`
  -> in-code. verify: transcript of the bare POST 200 with balances echo.
  challenge: attacked auth requirement (no token to miss), state reality (fresh
  connection sees mutations), probe semantics.
- `poc2_transfer_overdraw.py` — single unauth request transferred 1,000,000,000
  from vault; vault driven to -1,999,000,112. No sufficient-balance check: theft
  is unbounded. `REPRODUCED` -> **proven-live**.

**F-4 (failed transfer destroys funds):**
- `poc1_failed_transfer_destroys_funds.py` — transfer to `ghost_account` crashed
  the handler; alice debited 7 (493 -> 486) anyway. `REPRODUCED` -> in-code.
  (Friction: the PoC itself first crashed with `RemoteDisconnected` uncaught —
  fixed the PoC, not the target, and re-ran.)
  verify: transcript with the server-side KeyError from the app log.
  challenge: attacked atomicity (unknown source = harmless; destroy needs unknown
  destination), rollback (fresh-connection read stays debited), severity.
- `poc2_failed_transfer_drain_loop.py` — 5 failed transfers burned 5,000,000 vault
  units: repeatable asset destruction. `REPRODUCED` -> **proven-live**.

**F-5 (the chain):**
- `poc1_chain_leak_forge_transfer.py` — stage1 leak (3 accounts), stage2 forged
  admin (200 + secret), stage3 mutation (transferred=13). One script, zero
  credentials at every handoff. `REPRODUCED` -> in-code.
  verify: 3-stage transcript. challenge: attacked chain necessity, credential
  assumption, and the dead-end hypotheses honestly (no login route for replay;
  admin SECRET is display-only decoy — recorded as limitations).
- `poc2_chain_full_breach.py` — amplified chain: 3/3 hashes cracked, admin secret
  extracted, vault driven negative by 100,000,000 unauth transfer. `REPRODUCED`
  -> **proven-live**.

**F-6 (users hash leak):**
- `poc1_users_hash_leak.py` — unauthenticated GET returns 3 username+hash pairs.
  `REPRODUCED` -> in-code. verify: transcript (digests truncated for hygiene).
  challenge: attacked hash authenticity (canonical unsalted md5), impact.
- `poc2_users_hash_crack.py` — 3/3 leaked digests recovered with a 5-word
  dictionary: the leak is credential compromise, not noise. `REPRODUCED`
  -> **proven-live**.

### 3f. Close round 1

```
$ hunt wave close --wave-id 1 --verdict continue
wave #1 closed findings_new=6 verdict=continue

$ hunt wave reaudit --wave-id 1 --summary "5 survivors recorded, all climbed to proven-live with distinct poc1/poc2 scripts (F-1,F-2,F-4,F-5,F-6); 1 row (F-3) overturned as a bookkeeping casualty - its title was corrupted by shell path conversion and re-recorded as F-6, not a real hunt kill; 2 candidates died in cross-correction before recording (crash!=DoS, cookie-flags-without-sink) and are kept as lessons 1-2"
wave #1 re-audit recorded: ...
```

## 4. ROUND 2 (wave 2) — the blind-spot round

```
$ hunt wave open 2 "blindspot-sign-edges,blindspot-idor,blindspot-concurrency,blindspot-methods"
BLOCKED: not found: id = ?
```
Wrong syntax — `hunt wave open` takes the TARGET id, not the wave number (the wave
number is implicit). Corrected:
```
$ hunt wave open 1 "blindspot-sign-edges,blindspot-idor,blindspot-concurrency,blindspot-methods"
wave #2 opened (number 2) lanes=blindspot-sign-edges,blindspot-idor,blindspot-concurrency,blindspot-methods
```

Blind-spot questions and honest answers:

- **Is /transfer pre-auth reachable without any cookie?** Re-verified with zero
  headers: yes — but that is F-2's root cause, no new finding. (Documented.)
- **IDOR angle?** There is no ownership model AT ALL — any `from` account is
  impersonable. Same root cause as F-2, merged, no new finding. (Documented.)
- **SIGN edges (the thing round 1 never tested):**
  ```
  [BS-2] self-transfer, negative: from=alice to=alice amount=-1000000
  -> 200 {"transferred": -1000000, ..., "balances": {"alice": 486, ...}}
     alice UNCHANGED. The naive "self-transfer mint" is a NO-OP:
     debit(+1M) and credit(-1M) cancel. HYPOTHESIS KILLED BY THE PROBE.
  [BS-3] negative to another account: from=alice to=bob amount=-1000000
  -> alice 1000486, bob 2099000312: direction reversal, sum conserved.
  [BS-4] negative + UNKNOWN destination: from=alice to=ghost amount=-100
  -> connection dropped (crash). Read-back: alice 1000486 -> 1000586. +100 MINTED.
  ```
  The combination is the weapon: `amount=-X` flips the debit into a credit, then
  the unknown-destination KeyError crashes before any debit lands. Credit without
  debit, repeatable: **ledger inflation from nothing.**
- **Concurrency (honest negative):** 100 concurrent 1-unit transfers, 50 each
  direction across 10 threads — `sum before=-3999214 sum after=-3999214
  conserved=True`. No observable race anomaly. Not recorded as a finding.
- **HTTP methods (honest negative):** PUT/DELETE on /transfer -> 501. No surface.

RECORD: F-7 added (Arithmetic, high, mutate) — `poc1_negative_amount_mint.py`
(kills the self-transfer hypothesis in-script, then mints +100) -> in-code;
`hunt verify 7` (crash transcript + credited read-back); `hunt challenge 7`
(attacked the no-op first — "a 'mint' claim there would have been false"; then
rollback, repeatability, credentials, exactness); `poc2_ledger_control.py` —
minted 1,000,000,000 onto alice in crashed chunks and set the overdrawn vault from
-2,104,000,112 to EXACTLY +500,000: arbitrary ledger write. -> **proven-live**.

(Friction: poc2's first run FAILED — my delta math was inverted for a negative
balance. Fixed the exploit script and re-ran: `REPRODUCED`. The ladder gate never
saw the broken attempt because promote happens after the PoC actually works — an
operator could be tempted to promote a PoC that "worked once"; the gate cannot
check that. Known Class B limit, felt in practice.)

Close round 2 — reaudit, then the archive-required retro lesson, then the
exhausted close (which triggers the archive):

```
$ hunt wave reaudit --wave-id 2 --summary "blind-spot round: 1 confirmed (F-7 mint, proven-live with scale+ledger-control PoC); 1 candidate overturned by live probe before recording (negative self-transfer is a no-op, not a mint - the lesson is written down); honest negatives documented: concurrency sum conserved over 100 concurrent transfers, PUT/DELETE give 501, pre-auth /transfer and IDOR angles both reduce to F-2's root cause (no ownership model)"
wave #2 re-audit recorded: ...

$ hunt lesson add PracticeVault "blind-spot rounds must attack SIGN boundaries, not just TYPE boundaries: ..." --scope skill --target-id 1 --notes "retro lesson for archive; also recorded the honest negative results"
lesson #4 recorded (skill): ...

$ hunt wave close --wave-id 2 --verdict exhausted
wave #2 closed findings_new=1 verdict=exhausted
```

The exhausted verdict archived the target immediately (phase jumped hunting ->
archived, skipping the verify/report/retro PHASES entirely — see friction log).

## 5. Report, verification, claim gate

```
$ hunt report 1 --out ../examples/practice_target/REPORT.md
BLOCKED: target #1 is archived — the hunt is closed          (stderr, advisory)
report written to ../examples/practice_target/REPORT.md      (stdout)
exit 0

$ hunt verify-report ../examples/practice_target/REPORT.md
report matches its fingerprint
```

The report contains all 7 findings (6 proven-live, F-3 overturned with its
mangled title preserved as audit trail), both waves, and the hunt-report sha256
footer. `hunt verify-report` recomputes the digest: match.

Claim gate demo (bridge/claim_gate.py, HUNT_DB pointing at firstblood.db):

```
$ printf 'F-1 is PROVEN\n' | python bridge/claim_gate.py
claim gate: no unbacked claims
exit=0                                   <- backed by a proven-live row: PASS

$ printf 'F-99 is PROVEN\n' | python bridge/claim_gate.py
BLOCKED: engine claimed PROVEN for finding #99 but the database says 'not found' — claims must be backed by proven-live rows (hunt finding promote ...)
exit=2                                   <- fabricated claim: VETO (fail-closed)
```

## 6. Final state

```
$ hunt status
db 888b9c57e901 created 2026-09-05T18:23:15Z
#1 PracticeVault          phase=archived   ev=  7.0 | findings=7 proven=6 waves=2
    F-1 [PROVEN]     critical Admin panel takeover via client-asserted role cookie (forgeable in one header)
    F-2 [PROVEN]     critical Unauthenticated /transfer mutates shared balances; no sufficient-balance check allows unbounded overdraw
    F-3 [OVERTURNED] high     C:/Program Files/Git/api/users dumps usernames and unsalted md5 password hashes to any unauthenticated client
    F-4 [PROVEN]     high     Failed /transfer destroys funds: debit executes before credit, crash on unknown destination leaves balance debited
    F-5 [PROVEN]     critical Chain: /api/users recon -> forged admin cookie -> unauthenticated transfer = unauth to admin+theft in one script
    F-6 [PROVEN]     high     /api/users dumps usernames and unsalted md5 password hashes to any unauthenticated client
    F-7 [PROVEN]     high     Negative-amount transfer to unknown destination mints credits: source credited with no offsetting debit (repeatable ledger inflation)
```

No contradiction `!!` lines: RoE was set before the first mutate finding, no
Unknown-class findings, no hollow waves, report fingerprint matches.

Findings summary (ids, classes, actions, final ladder states):

| ID | Lane | klass | action | severity | final state |
|----|------|-------|--------|----------|-------------|
| F-1 | Red-Teamer | Access | auth-test | critical | proven-live |
| F-2 | Fuzz-Engineer | Access | mutate | critical | proven-live |
| F-3 | (re-record attempt) | Web2 | read | high | overturned (shell-mangled title; audit trail kept) |
| F-4 | Red-Teamer | Logic | mutate | high | proven-live |
| F-5 | Chainer | Access | mutate | critical | proven-live |
| F-6 | Architect | Web2 | read | high | proven-live |
| F-7 | blind-spot round | Arithmetic | mutate | high | proven-live |

Lessons recorded: 4 (2 cross-correction kills, 1 shell-mangling process lesson,
1 retro lesson for the archive gate).

Files created (all under the worktree, nothing committed):

- `examples/practice_target/practice_app.py` — the educational vulnerable app
- `examples/practice_target/README.md`
- `examples/practice_target/surface_map.md` — recon artifact
- `examples/practice_target/attack_plan.md` — classify artifact
- `examples/practice_target/poc/poc1_admin_cookie_forge.py` / `poc2_admin_secret_extraction.py`
- `examples/practice_target/poc/poc1_transfer_unauth.py` / `poc2_transfer_overdraw.py`
- `examples/practice_target/poc/poc1_users_hash_leak.py` / `poc2_users_hash_crack.py`
- `examples/practice_target/poc/poc1_failed_transfer_destroys_funds.py` / `poc2_failed_transfer_drain_loop.py`
- `examples/practice_target/poc/poc1_chain_leak_forge_transfer.py` / `poc2_chain_full_breach.py`
- `examples/practice_target/poc/poc1_negative_amount_mint.py` / `poc2_ledger_control.py`
- `examples/practice_target/REPORT.md` — generated by `hunt report`, fingerprint-verified
- `examples/practice_target/firstblood.db` — gitignored; the log is the artifact
- `examples/practice_target/FIRSTBLOOD.md` — this file

Cleanup: practice app process stopped; `netstat` shows nothing listening on 8765
and a curl to 127.0.0.1:8765 is refused (curl exit 7).

---

## Friction log

Every awkward moment from the run, in the order they bit (or were noticed).
Nothing in app/ source was modified; these are inputs for the next improvements.

1. **Path contradiction between the two instructions.** "Run every hunt command
   from the app dir" + literal artifact paths like `examples/practice_target/...`
   cannot both hold: from `app/`, that relative path points into
   `app/examples/...` (does not exist; the artifact gate requires an existing
   file). I used `../examples/practice_target/...` everywhere. Consequence: the
   DB's stored poc/artifact paths are `../examples/...` — correct only relative to
   `app/`, and nothing ever re-validates them. An absolute-path option, or paths
   resolved/stored relative to the db, would remove the fragility.

2. **Git-Bash/MSYS silently mangles leading-slash arguments.** `hunt finding add 1
   "/api/users dumps..."` stored the title as `C:/Program Files/Git/api/users
   dumps...`. It is not a hunt bug — it is the shell — but the effect inside the
   hunt was painful: **there is no `hunt finding edit`**, so the only repair was
   `overturn` + re-add, which pollutes the ledger with a bookkeeping casualty
   (F-3) that shows up in reaudit's overturned count and in the report next to
   real findings. The mangling also hit a lesson string MID-SENTENCE (`C:/Program
   Files/Git/...` inside the text became `C;C:\Program Files\Git\...`), and
   lessons cannot be edited either. `MSYS_NO_PATHCONV=1` guards new commands, but
   nothing tells you this until it has already eaten a title.

3. **`hunt wave open <target_id> <lanes>` reads like it wants a wave number.**
   I typed `hunt wave open 2 "..."` for wave 2 and got `BLOCKED: not found: id = ?`
   — which does not say "no such TARGET 2". The wave number being implicit is
   fine; the error message being a bare `id = ?` is not.

4. **The exhausted verdict archives the target instantly, out of pipeline order.**
   Closing wave 2 with `exhausted` jumped the phase hunting -> archived, skipping
   the verify/report/retro PHASES entirely (the phase trigger permits archived
   from any phase). The mission's own command order (close exhausted, THEN report)
   is the natural reading of the walkthrough, and it locks you out: see next item.

5. **`hunt report` on an archived target gives mixed signals in one invocation.**
   It printed `BLOCKED: target #1 is archived — the hunt is closed` (the
   disclosure_report artifact could not be stamped), yet it also wrote the report
   and exited 0. Result: the report exists and verifies, but the
   disclosure_report artifact is permanently missing from the event log — the
   report phase's exit gate can never be satisfied post-archive. Either refuse
   cleanly before writing, or stamp first: the current half-success is the worst
   of both.

6. **Reaudit-before-close vs close-before-reaudit are both accepted.** Wave 1 I
   closed then reaudited (walkthrough order); wave 2 I reaudited then closed
   (mission order). Nothing distinguishes them, and the confirmed/overturned
   counts are appended as free text into `waves.notes` rather than stored as
   structured columns, so nothing downstream can actually check the re-audit
   beyond the flag bit.

7. **`findings_new` counts rows, not survivors.** Wave 1 reported
   `findings_new=6` including the overturned F-3 bookkeeping casualty. A
   "confirmed new" count (excluding overturned) would make wave economics honest
   at a glance, especially for the two-consecutive-empty-waves economic stop.

8. **The secret gates are subtle regexes the operator must reverse-engineer.**
   Writing verify transcripts required knowing that `password_hash` does NOT match
   the credential-assignment pattern (underscore is a word character, so no
   boundary after "password"), that `SECRET: internal transfer keys` passes
   because `\S{12,}` cannot span spaces, and that `assert_no_secrets` REFUSES at
   the gates while `redact` silently rewrites at display time — an asymmetry that
   is documented in code comments but is a trap in practice. A "transcript would
   have been refused because X" dry-run would help.

9. **The ladder cannot see whether the PoC ever ran.** promote checks existence,
   non-emptiness, and sha-distinctness between steps. My poc2_ledger_control.py
   FAILED on first run (my own math bug); I fixed it and re-ran before promoting —
   but nothing in the framework would have stopped me from promoting a script that
   never exited 0. This is the documented Class B limit ("content authenticity is
   closed by process, not schema") and it is exactly where an operator under
   pressure would cheat themselves.

10. **PoC file contents matter more than the gate can express.** Evidence refs and
    transcripts must be hand-trimmed (digests truncated, plaintexts withheld,
    "recovered word length 8" instead of the word). That is the right trade
    (store the fact, not the secret), but the gate gives no feedback about what a
    GOOD body looks like — I imitated the walkthrough's `hunt verify 1 tx_hash
    0xdeadbeef...` style and guessed the rest.

11. **Small wording/cosmetic papercuts.** `hunt status` prints `[PROVEN]` for
    ladder_status `proven-live` (two names for one state); `hunt target add`
    defaults `--chain evm` for what was a web target (harmless, chain is free
    text, but "evm" in a web-hunt report reads odd); `hunt finding promote`
    requires `--id`/`--evidence-ref`/`--poc-path` BEFORE the positionals are
    obvious, and the per-action subparsers mean `hunt finding promote --id 2 ...`
    and `hunt finding add 2 ...` use "2" for different things (finding id vs
    target id) — correct, but easy to fat-finger fast.

12. **Crash responses have no HTTP representation.** The practice app's handler
    exceptions close the connection (curl exit 52, http:000). Transcripts of
    crash-based findings therefore need the server-side traceback from the app's
    own log as corroboration — fine here (we control the app), impossible on a
    real black-box target. Noted as an app-infra quirk that shaped the evidence.

13. **No convenience for "what did I just record?"** After each finding add I ran
    `hunt status` to confirm ids/links (wave auto-linking is silent — nothing in
    the `finding add` output says which wave, if any, absorbed the finding). One
    echo line in the add output ("linked to open wave #1") would have saved a
    dozen status calls.

14. **Claim gate binding is positional luck.** It binds the nearest F-<n> within
    80 chars of the claim marker. Worked perfectly for `F-1 is PROVEN` and
    `F-99 is PROVEN`, but a sentence mentioning two ids near a marker binds to
    whichever is nearest — an operator quoting findings in prose could get a pass
    or veto they did not intend.
