# skills/ — the skills landing pad

Skills are the third rung of the memory ladder: a retro lesson that keeps
proving itself becomes law, and a law that needs procedure becomes a skill.
This directory is where imported operator skills live next to the ones this
repo grows itself.

## Category structure

Skills live in category folders; `INDEX.md` is the router over all of them:

```
skills/                 # app/src/huntos/_data/idea/skills/ in the git tree
  INDEX.md           # the router — the engine reads this FIRST, never bulk-loads
  README.md          # this contract
  recon/             # targeting and attack-surface discovery
  web2/              # web application and API attack
  web3/              # blockchain and protocol audit
  cdc/               # CDC multi-agent hunt methodology
  verification/      # evidence discipline and engineering rigor
```

Every landed skill is a folder under one category; the catalog of all five
categories lives in `INDEX.md` (including the loading doctrine and the
per-lane loadouts).

## Reference integrity

Every `skill_view(name='X')` written anywhere in `IDEA.md` must resolve
to a landed `SKILL.md` somewhere under `skills/` — by folder name or by the
`name:` field of its front matter. CI's `Skills reference integrity` check in
`.github/workflows/ci.yml` enforces this contract. A reference that resolves to
nothing is a broken promise to the lane that tried to load it.

## Format

One folder per skill, kebab-case, verb-free, singular:

```
skills/
  black-swan-engine/
    SKILL.md          # required — the skill itself
    assets/           # optional — scripts, checklists, wordlists, fixtures
    examples/         # optional — worked runs, gold outputs
```

`SKILL.md` opens with a front-matter block (plain `key: value` lines): `name:`
and `description:` are required — native harness loaders (Claude Code / ZCode)
discover skills by frontmatter, and the description is what they use to decide
when to surface the skill (single line, sourced from the skill's `INDEX.md`
bullet). `lanes:`/`scope:` are the HUNT-OS extensions on top:

```
name: black-swan-engine
description: 19 universal laws of EVM vulnerability (CDC backbone)   # single line, from the INDEX.md bullet
lanes: architect,red-teamer    # which lanes load it; `all` for role-agnostic
scope: contract | web2 | node  # the surface it applies to
```

## What a skill may do

- Teach procedure: how to enumerate, what invariants to attack, how to read a
  fork, how to structure a fuzzing matrix.
- Reference the hunt CLI by exact command (`hunt finding add ...`,
  `hunt verify ...`) so the lane never has to guess the gate's syntax.
- Define heuristics and priorities for a lane (what to try first, when to
  declare BLOCKED).
- Carry worked examples — real commands and real output shapes, marked as
  such.

## What a skill may never do

- **Bypass the gate.** No skill may instruct raw sqlite writes, direct file
  edits of `hunt.db`, or any route that skips the CLI. Enforcement lives in
  the CLI and the database — exit code 2 is law, and no document outranks it.
- **Self-assign the ladder.** A skill may describe how to earn `in-code` or
  `proven-live`; it may never claim, assert, or narrate a rung the db does
  not hold. The claim gate reads output regardless of which skill wrote it.
- **Extend the taxonomy at insert time.** New classes are born only at retro
  (`hunt klass add`). A skill uses `Unknown` and waits.
- **Move phases or close waves.** Wave verdicts, phase moves, and archiving
  are operator-level CLI actions, not lane procedures.
- **Store secrets.** Skills reference the shape of evidence, never live
  credentials; the gates refuse raw secrets and every skill must assume the
  same posture.

## Loading (how lanes get them)

The engine injects `app/src/huntos/_data/idea/HUNT-BRIDGE.md` every session;
role files live in `app/src/huntos/_data/roles/`. A skill is loaded when a
role file or the bridge names it for the lane running (`lanes:` front matter
is the contract). IDEA.md's own references (e.g.
`skill_view(name='black-swan-engine')`) point here: the import target is
`skills/<category>/<name>/SKILL.md`.

A harness without idea-injection gets the same layer via the separate
stdlib skills installer: `hunt install --adapter claude-code|zcode|hermes|generic`
(or equivalently `python -m huntos.installer ...`) copies the skills into the
harness's native skill directory (router skill `hunt-os`, or one native skill
per SKILL.md with `--mode native`). This command assumes the CLI bootstrap has
already installed `hunt`; it does not install Python or the CLI. Hermes itself
needs no filesystem install: it loads `huntos/_data/idea/` directly.

## Promotion path

```
retro lesson (scope=skill)  ->  law_candidate (hunt lesson add --scope law_candidate)
      ->  recurring across targets  ->  skills/<category>/<name>/SKILL.md
```

A skill earns its folder the way a finding earns proven-live: repeated,
surviving evidence that the procedure produces confirmed findings. When a
skill is promoted, record the lessons it grew from in its `examples/` —
skills with provenance beat skills with adjectives.

The next batch is the promotion command: retro lessons currently marked
`scope=skill` graduate to `law_candidate` and, on promotion, land here as a
new skill folder + an `INDEX.md` entry in the same change. A skill that is
landed but not indexed is invisible to the engine — the pair is atomic.
