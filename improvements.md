# improvements.md — the v0.4 enforcement wishlist — ALL SHIPPED

> **STATUS: ARCHIVED (2026-09-07).** Every item below shipped in the v0.4
> enforcement wave and is now regression-pinned, not aspirational:
> (1) bridge = `soul/bridge/HUNT-BRIDGE.md` + `bridge/claim_gate.py` (exit 2);
> (2-3) ladder/wave/retro/adversary/score laws live in `app/src/huntos/core/db.py`
> triggers + guards, pinned by `app/tests/test_enforcement.py`;
> (4) klass/severity allow-lists as data (`hunt klass`), report ladder-status
> only; (5) RoE row on target, default-deny mutate at promote, token-shape
> refusal at storage, display redact; (6) full argparse CLI + test suite.
> This file is kept as history of what the Colb session taught us. The live
> roadmap is `ROADMAP.md`; the live honest ledger is `pr/OPEN-PROBLEMS.md`.

---

1. Bind Hermes to the CLI
The Colb session never touched HUNT-OS. Until that is impossible, the laws are a prompt.

Add a hunt-bridge skill (this is the v0.5 item in the README): every finding, wave, phase, and report goes through hunt, not chat.
A Hermes hook that fails the turn if the assistant writes PROVEN / EXPLOITABLE / admin takeover and the DB has no matching proven-live row.
hunt report is the only report. Ban markdown reports written from memory, which is what happened at 22:25.
src/huntos/core/ stays engine-agnostic. The bridge lives in soul/ + a skill file that shells out to hunt.

2. Make the ladder mean “work happened”
Today os.path.exists is enough. That is why a dummy file can become proven-live.

In db.py / models.py:

Block adding a finding as in-code. Only theoretical on insert.
Store poc_sha256 at promote time. Refuse the same hash for both steps.
Require a new evidence_ref per step (the Colb write-up reused one story as the whole chain).
proven-live also needs a verifier event: role name + artifact type (fork_receipt | tx_hash | http_transcript) + non-empty body. File-exists is in-code only.
Add SQL CHECK constraints on phase, ladder_status, ev_verdict so sqlite3 cannot quietly rewrite the story.
3. Enforce the laws that are currently comments
These are the holes the logs would have walked through if the CLI had been used:

Law	Code change
Score before hunt
Cannot leave scoring unless ev_score was set. Optional: refuse ev_score <= 0.
Economic stop
findings_new is COUNT(*) for that wave, not a typed integer. Two closed waves with 0 new findings → only exhausted or pivot.
Retro
set_phase(..., "archived") / finish retro requires ≥1 lesson for that target.
Adversary
No proven-live until an adversary_pass or overturn attempt is logged on that finding.
Waves
open_wave only in hunting. No findings/waves after archived.
Re-audit
Require a summary over N chars and counts: confirmed / overturned. Empty --summary dies.
Also add findings.wave_id and lessons.target_id as real FKs. Right now a finding is not tied to a wave, so “wave 2 found nothing new” cannot be checked.

4. Stop label inflation
The Colb parent called public package.json a “MASSIVE FIND” and env('ADMIN_JWT_SECRET') a secret leak.

Finding klass and severity must be in the allow-lists in models.py.
Report templates print ladder status only. No PROVEN badge unless ladder_status == proven-live.
Soul/skill rule, one line: env var name ≠ leaked secret; HTTP 200 HTML shell ≠ file disclosure; user JWT ≠ admin.
hunt status should show contradictions: claimed critical with no evidence, waves with 0 linked findings, reports with no proven-live.
5. Scope and secret hygiene
The live session registered users, pulled a DB, reset admin passwords, and wrote the password into Hermes state.

HUNT-OS should carry a rules-of-engagement row on the target: authorized hosts, allowed actions (recon / read / auth-test / mutate). hunt finding promote to proven-live for a mutate action outside RoE is blocked.

On promote/report:

Redact tokens, passwords, reset codes in events.detail and report output.
Refuse to store raw credentials as evidence_ref. Store “reset token present in table X” / “login 200 as role Y”, not the secret.
That is process enforcement, not more attack surface.

6. CLI and tests so the new rules stay closed
cli/main.py needs a real parser per action (add vs promote vs overturn), required args, and validation of severity/class. connect() should not makedirs("") on a bare filename.

Extend tests/test_enforcement.py for the cases that pass today:

add as in-code
reuse one PoC file for both promotions
continue after two empty waves
wave on scoring or archived
findings_new=99 when the table has 0
empty re-audit
skip score, skip lesson
proven-live without adversary event
Fix .gitignore (__pycache__, .venv, *.db).

What I would not do yet
Do not jump to the v1.0 multi-user API. The product is still a single-operator state machine that the engine ignores. An API on top of honor-system flags just scales the lie.

Do not add more soul adjectives. The Colb prompt already had 6-hour persistence, adversary, and “no theoretical.” The engine ignored all of it because nothing returned exit code 2.

Order
Bridge + “no PROVEN unless DB says so” — stops the failure mode in the log.
Ladder + SQL constraints + computed wave counts — makes the CLI honest if used.
RoE + redaction — stops the session from becoming a credential dump.
Report-from-DB-only + tests — locks it.
If you want this in the repo, the first slice is (1)+(2) in db.py / models.py / tests, plus a soul or examples bridge that shows Hermes calling hunt after each finding.