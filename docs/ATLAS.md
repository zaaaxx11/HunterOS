# The crypto attack atlas (`hunt atlas`)

One routing table for crypto/EVM work: **symptom → attack family → detection
command → the skill that finishes it → the ledger record**. It replaces
re-deriving a taxonomy every session and stops findings being filed under
improvised names.

## What ships

| Path | Contents |
|---|---|
| `app/src/huntos/_data/idea/skills/web3/crypto-attack-atlas/SKILL.md` | the router skill |
| `.../crypto-attack-atlas/data/atlas.json` | machine-readable atlas (`huntos-atlas/1`) |
| `.../crypto-attack-atlas/references/attack-families.md` | all 18 families, narrated |
| `.../crypto-attack-atlas/scripts/atlas.py` | standalone reader (no CLI needed) |
| `app/src/huntos/core/atlas.py` | loader + `match`/`coverage`/`seed_leads` (read-only) |
| `app/src/huntos/cli/main.py` (`cmd_atlas`) | the `hunt atlas` verb |

## The 18 families

`A1` Reentrancy · `A2` Oracle manipulation · `A3` Flash-loan amplifier ·
`A4` Access control · `A5` Logic/accounting · `A6` Share/ERC4626 ·
`A7` Precision & arithmetic · `A8` Signature/permit replay ·
`A9` Proxy & initialization · `A10` Bridge verification ·
`A11` Token quirks · `A12` Liquidation/economics/MEV · `A13` Slippage & deadline ·
`A14` Governance · `A15` Key/operational compromise · `A16` Supply chain ·
`A17` Transient storage · `A18` Freeze/pause/blacklist.

Each family carries: the HUNT-OS `klass` it files under, the SWC ids, the
observable signals, the concrete commands to run, the mitigations (which double
as falsifiers), the sibling skills, and incident evidence from a 904-incident
dataset (DeFiHackLabs 2017–2026, SlowMist, rekt.news).

## Commands

```sh
hunt atlas list                        # families + incident evidence
hunt atlas list --klass Oracle         # filter by ledger klass
hunt atlas show A7                     # signals / detect / mitigate / real cases
hunt atlas match "share price jumps after deposit"
hunt atlas coverage                    # what the ledger proves, plus blind spots
hunt atlas seed --family A7 --target-id 3   # prints the `hunt lead add` line
```

Everything is read-only (`READ_ONLY_COMMANDS`), so it neither trips the
workspace lock nor bypasses the claim gate. `seed` **prints** a command; you run
it through the normal door.

## Why coverage, not a score

`hunt atlas coverage` reads recorded findings and leads and prints every family
with **no evidence at all**. That is the honest answer to "are we done?" — a
percentage hides gaps; a blind-spot list does not. Findings are attributed by
their ledger `klass` (enforced), leads by keyword match on their title (an
approximation, printed separately for that reason).

## Data honesty

- `loss_usd_parsed` is a **lower bound** — only incidents that state USD are
  summed; token-denominated losses are never converted.
- Family counts are keyword-classified over root-cause prose: one incident can
  land in several families. Frequency indicator, not a precise share.
- A match is a hypothesis generator. The evidence ladder still applies:
  theoretical → in-code/reproducible → verified.

## Regenerating the data

The atlas is built from the scraped corpus by `atlas_build.py` (in the
`crypto-audit-kb` workspace). The authoritative copy inside this repo is
`data/atlas.json`; `pytest tests/smoke/test_atlas.py` fails if a family cites a
`klass` the ledger would refuse, a skill that does not exist, or an SWC id that
is missing from the references.