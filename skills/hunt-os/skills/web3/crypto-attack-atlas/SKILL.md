---
name: crypto-attack-atlas
description: "One routing atlas for crypto attack families A1-A18: symptom to family, family to detection commands, tool, and the HUNT-OS skill that finishes the job"
trigger_keywords: [atlas, attack-family, vuln-taxonomy, reentrancy, oracle, flash-loan, erc4626, transient-storage, bridge, freeze, pause, blacklist, swc, dexn, defihacklabs, findings, coverage, klass, triage]
tags: [web3, smart-contract, audit, taxonomy, triage, findings, coverage, swc, defi, solana, bridge, ops]
---

# Crypto Attack Atlas

The single map from **symptom → attack family → detection → ledger record**. It
exists so an agent does not re-derive a taxonomy every session, and so a
finding is filed under a stable name instead of prose free text.

The atlas is 18 families (`A1`–`A18`), each bound to a HUNT-OS `klass`, the SWC
ids, the signals to look for, the commands to run, the mitigations, and the
skills that already cover part of it. Data lives beside this file in
`data/atlas.json`; the narration lives in `references/attack-families.md`.

Authority first: this skill grants nothing. Every test you run from here needs
an approved RoE (`hunt target roe`), and every result needs a ledger record.
The CLI is the only write door — `hunt atlas` **prints** the next commands and
never writes them for you.

## WHEN TO USE THIS SKILL

- You have a target and need the shortest path to a real hypothesis.
- You found behavior worth reporting and need the right `klass`.
- You are mid-hunt and want to know which families are still blind.
- You want the specific static/fuzz command for a family, not generic advice.

Do **not** use it to bulk-load every family into context. Pick one family per
hypothesis; the references are for lookup, not reading end-to-end.

## THE LOOP (uses the atlas, keeps the evidence ladder honest)

```text
symptom -> atlas match -> one family -> signals -> 1 minimal test
        -> hunt lead add (theoretical) -> mutate -> verify
        -> finding promote (only with evidence + PoC)
```

1. **Name the symptom** in observable terms (e.g. "share price jumps between
   deposit and redeem", "withdraw reverts only while paused").
2. **Match it**: `hunt atlas match "<symptom>"` → ranked families with the
   keyword hits that caused the ranking. Read the top one only.
3. **Read the family**: `hunt atlas show A6` → signals, detection commands,
   mitigation, real cases. The mitigation block is also the falsifier.
4. **Write the hypothesis into the ledger BEFORE testing**:
   `hunt lead add --target <id> --title "..."` — it starts `theoretical`.
5. **Run the smallest permitted test** from the family's detect list. Local
   fixture or fork first. A submitted call is not a result.
6. **Verify independently** (`hunt verify`, `hunt challenge`) and only then
   promote. Refuted is a valid, valuable outcome — park or kill the lead.

## FAMILY ROUTER (symptom → family)

| Symptom / smell | Family | klass |
|---|---|---|
| Re-enterable value path, callback token, LP state seen mid-write | A1 Reentrancy | Reentrancy |
| Price movable in one tx, stale feed, LP used as collateral | A2 Oracle | Oracle |
| "Attacker can't have that much capital" assumption | A3 Flash loan | Logic |
| Setter/init/mint reachable by the wrong actor | A4 Access control | Access |
| Accounting mismatch that no tool flagged | A5 Logic | Logic |
| Vault share/asset ratio manipulable, first depositor edge | A6 ERC4626 | Logic |
| Divide-before-multiply, downcast, dust loop | A7 Precision | Arithmetic |
| `ecrecover`, permit, nonce, stale approval | A8 Signature | Sig |
| `initialize`, proxy, `delegatecall`, storage gap | A9 Proxy | Upgradeable |
| Message proof accepted on the destination chain | A10 Bridge | Logic |
| Fee-on-transfer, rebasing, non-standard return | A11 Token quirks | ExternalCall |
| Liquidation/LTV/emission/MEV economics | A12 Economics | Logic |
| `minOut = 0`, infinite deadline, user-supplied path | A13 Slippage | Logic |
| Proposal can move treasury | A14 Governance | Access |
| Key/signer/devops compromise, no contract bug | A15 Key compromise | Access |
| Frontend/dependency/DNS trust | A16 Supply chain | Web2 |
| `tstore`/`tload` reuse, EIP-1153 leftovers | A17 Transient storage | Logic |
| Funds cannot move: pause, blacklist, forced upgrade | A18 Freeze | Access |

## THE CLI (read-only; prints, never writes)

```sh
hunt atlas list                      # the 18 families + incident evidence
hunt atlas list --klass Oracle       # families that file under one klass
hunt atlas show A7                   # one family: signals, detect, mitigate, cases
hunt atlas match "share price jumps on deposit"
hunt atlas coverage                  # what the ledger already proves, per family
hunt atlas seed --family A7          # the `hunt lead add` line to run yourself
```

`coverage` reads recorded findings and leads and prints the families with **no
evidence at all** — that is the blind-spot list, and it is the honest way to
answer "are we done?" without a percentage that hides gaps.

## TOOLCHAIN BY LAYER (pick by the question, not by habit)

| Question | Tool | Family it serves |
|---|---|---|
| Known bad pattern present? | `slither`, `aderyn`, `solhint` | A4, A7, A8, A9, A11 |
| Can I break this invariant? | `echidna`, `medusa`, Foundry invariant | A1, A5, A6, A12 |
| Is this property always true? | `halmos`, Certora | A5, A6 |
| Can I actually take the money? | Foundry fork + PoC | A2, A3, A10, A13 |
| Has this pattern been reported before? | Solodit, Code4rena, Sherlock | all |
| Where did the funds go? | Phalcon, Tenderly, Nansen/Arkham | A15, A10 |

None of these finds A5 logic flaws on its own: 238 of the 904 catalogued
incidents are logic bugs, and the only detector is an invariant a human wrote.

## BINDING A FINDING (label discipline)

`hunt finding add` refuses a `klass` outside the ledger taxonomy. The atlas
`klass` per family is exactly a value the ledger accepts, so use it verbatim:

```sh
hunt atlas show A2                                   # klass: Oracle
hunt finding add 1 "stale oracle price lets borrow over-value" Oracle --severity high
```

If the taxonomy genuinely lacks a class, grow it the sanctioned way
(`hunt klass add <name> --from-finding <id>`, retro-gated) — never via raw
SQLite, never by stuffing a new name into a title.

## HONEST LIMITS OF THE DATA

- Family counts are keyword-classified over root-cause prose; one incident can
  land in several families. They indicate frequency, not precise shares.
- `loss_usd_parsed` is a **lower bound**: only incidents that state USD are
  summed; token-denominated losses are never converted.
- Coverage of incidents is partial (the corpus documents incidents with PoCs).
- A family match is a hypothesis generator, not evidence. The gate still
  applies: theoretical → in-code → verified.

## REFERENCES

- `references/attack-families.md` — all 18 families with variants, signals,
  commands, mitigations, and real cases.
- `references/toolchain.md` — the consolidated tool inventory (install + run
  line per tool), grouped by the question it answers, mapped to families.
- `data/atlas.json` — the machine-readable atlas (`huntos-atlas/1`).
- `scripts/atlas.py` — standalone reader for harnesses without the CLI:
  `python3 scripts/atlas.py list|show|match|klass`.
- Sibling skills to load once a family is chosen: `evm-contract-audit`,
  `black-swan-engine`, `defi-protocol-analysis`, `token-transfer-audit`,
  `on-chain-exploit-workflow`, `on-chain-forensics`, `l2-rollup-audit`.
