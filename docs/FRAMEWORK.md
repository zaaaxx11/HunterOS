# FRAMEWORK.md — HUNT-OS L1-L5

## L1 DOCTRINE — prinsip permanen

| # | Prinsip | Makna operasional |
|---|---|---|
| 1 | Chain > Collection | Finding tunggal = bahan. Rantai = senjata. Map [Trigger → Effect → Trust boundary crossed] |
| 2 | Evidence or Nothing | Tanpa PoC = tebakan. Ladder wajib: theoretical → in-code → proven-live |
| 3 | Overturn fast, learn forever | Hypothesis salah = progres. Terminal + auditable, zero ego |
| 4 | Exhaust before pivot | One chain fully. Economic stop, bukan loop abadi |
| 5 | No fabricated output | Real tool output atau explicit failure. Submitted ≠ proven |
| 6 | Memory compounds | Tiap hunt → retro. Lesson masuk opening read hunt berikutnya |

## L2 PIPELINE — fase + exit gates + artifact contract

```
SCORE → RECON → CLASSIFY → HUNTING (waves) → VERIFY → REPORT → RETRO → ARCHIVE
```

| Fase | Exit gate | Artifact |
|---|---|---|
| SCORE | `ev_score > 0` (`hunt score`), atau archive | recorded in the db (score column) — no file |
| RECON | surface map lengkap: kontrak + endpoint + stack + admin | `surface_map` — recorded via `hunt artifact <id> surface_map <file>`, sha256-stamped |
| CLASSIFY | tiap surface punya skill/lane assignment | `attack_plan` — recorded via `hunt artifact <id> attack_plan <file>` |
| HUNTING | wave N+1 locked sampai wave N re-audited + verdict | wave verdicts + re-audit counts recorded in the db (`hunt wave close` / `hunt wave reaudit`) |
| HUNTING (leads) | lead: kedua half ter-trace (manual atau oracle), payload non-empty | `lead_half_set` events + frozen provenance snapshot saat `hunt lead promote` (lead → finding theoretical) |
| VERIFY | tiap finding: PoC executed (`hunt poc run`) + evidence ref, atau `theoretical` eksplisit | `poc_run` events + PoC files + tx hash |
| REPORT | report di disk + delivered | `disclosure_report` — logged automatically by `hunt report --out` |
| RETRO | lessons recorded, pattern dipromosi ke doctrine/template | lessons recorded in the db (`hunt lesson add`) |

Completion path: RETRO → ARCHIVE (`hunt target archive <id> <reason>` — archiving
requires a lesson bound to the target). The economic stop from HUNTING (wave closed
with verdict `exhausted`) archives too — both exits are legal.

## L3 ENGINE — how execution runs

- Hermes = engine (tools, skills, subagents, cron). **Do not build a harness.**
- Lanes: Architect / Red-Teamer / Fuzz-Engineer / Chainer (`app/src/huntos/_data/roles/`) + Adversary (blind review per concrete finding) + Verifier (fork PoC, real execution, evidence on disk).
- Round loop, executed by the engine per `app/src/huntos/_data/roles/lane-runner.md`: spawn → cross-correct → record via hunt CLI → re-audit → next round.
- Persistence budgets are operator-configured per hunt — the engine never extends them itself.
- Bridge: `app/src/huntos/_data/idea/HUNT-BRIDGE.md` (skill, injected every hunt session) + `app/src/huntos/_data/bin/claim_gate.py` (hook) — the engine's mouth is guarded: an unbacked claim fails the turn.
- Harness-neutral layer: Hermes injects the idea layer (`_data/idea/`) directly; Claude Code / ZCode / generic harnesses load the same bridge + skills layer via `huntos.installer` (`python -m huntos.installer`, run as `hunt install`) (router skill `hunt-os`). The claim-gate hook contract is unchanged — every harness honors exit 2.
- `hunt poc run --id <n> --poc-path <file>` — evidence is executed, not attached: a finding's PoC must run through the CLI before any promote.

## L4 STATE — the db is the spine

v0.4: the db IS the spine of the framework. `hunt.db` carries the triggers
(tamper guard on evidence columns, klass guard, phase guard), CHECK
constraints on every state column, the per-session guard, the project lock,
and the claim gate's ledger binding. The framework without the db is doctrine
on paper — enforcement lives in the schema first, CI structure second, and
operator discipline for what the schema cannot see.

## L5 KNOWLEDGE — retro loop

- `hunt lesson add` (atau manual di retro.md): pattern yang layak jadi doctrine/template/skill
- Promotion path: retro lesson → template update → doctrine update
- Skill moat: metodologi (black-swan, CDC, roles) = moat. App bisa ditiru, moat tidak
- Skills layer is now populated (6 categories under `app/src/huntos/_data/idea/skills/`, router: `app/src/huntos/_data/idea/skills/INDEX.md`); the retro→skill promotion command is the next batch
