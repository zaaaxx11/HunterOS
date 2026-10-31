# Toolchain — one inventory, grouped by the question it answers

Picking a tool by habit is how audits turn into noise. Pick by the question.
Every tool below is free/open-source unless marked; `A#` maps to the attack
families in `references/attack-families.md`.

## 1. "Is a known bad pattern present?" — static

| Tool | Install | Serves |
|---|---|---|
| Slither | `pip install slither-analyzer` | A4, A7, A8, A9, A11 |
| Aderyn | `curl -L https://raw.githubusercontent.com/Cyfrin/aderyn/main/cyfrinup/install \| bash` | A4, A9 (centralization, proxy) |
| solhint | `npm i -g solhint` | style + a few security rules |
| Mythril | `pip install mythril` | bytecode-level symbolic execution |
| Surya | `npm i -g surya` | call graph / inheritance / function map |
| Diffyscan | `pip install diffyscan` | deployment drift (source vs verified bytecode) |

```sh
slither . --print human-summary
slither . --detect reentrancy-eth,reentrancy-no-eth,arbitrary-send-eth,unprotected-upgrade,divide-before-multiply,tx-origin,suicidal,unchecked-transfer
aderyn .                                    # markdown report, agent-friendly
slither . --print storage-layout            # A9: diff across versions
```

## 2. "Can I break this invariant?" — fuzzing

| Tool | Install | Notes |
|---|---|---|
| Foundry | `curl -L https://foundry.paradigm.xyz \| bash && foundryup` | fork tests + invariant; the PoC vehicle |
| Echidna | release binary (`crytic/echidna`) | property-based, industry default |
| Medusa | `go install github.com/crytic/medusa@latest` | coverage-guided, parallel |
| ItyFuzz | `curl -L https://ity.fuzz.land/ \| bash` | bytecode hybrid, fast on unverified code |

```sh
forge test --fuzz-runs 10000
forge test --fork-url $RPC -vvv             # A2/A3/A10/A13: the money test
echidna test/invariants.sol --contract Invariants --test-mode assertion
medusa fuzz --config medusa.json
```

Invariants worth writing first (they are the only detector for A5, 238/904 cases):

```text
sum(balances) == token.balanceOf(this)
totalDebt <= totalAssets
share price never decreases without a loss event
no user can withdraw more than deposited + entitled yield
```

## 3. "Is this property always true?" — formal

| Tool | Install | Notes |
|---|---|---|
| Halmos | `pip install halmos` | symbolic testing in Foundry style |
| Certora Prover | hosted CLI + CVL spec | proves rules over all inputs |

```sh
halmos --function check_ --solver-timeout-assertion 60000
```

## 4. "Has this pattern been reported before?" — knowledge

| Source | What it gives | Serves |
|---|---|---|
| Solodit (web) | 10k+ audit findings, searchable | all |
| Code4rena / Sherlock / Cantina reports | contest findings = real patterns | all |
| DeFiHackLabs (GitHub) | 900+ incidents with Foundry PoCs | all |
| DeFiVulnLabs (GitHub) | 48 bug classes, one PoC each | all |
| SWC Registry | stable ids for communication (`SWC-107`) | all |
| Secureum pitfalls | classes tooling misses | A5, A6, A8 |

## 5. "Where did the money go?" — trace & forensics

| Tool | Use | Serves |
|---|---|---|
| Phalcon Explorer | tx trace + state diff + decode | A1, A10, A15 |
| Tenderly | fork simulation, debugger | A2, A3 |
| EigenPhi | MEV / sandwich analysis | A12 |
| 4byte / openchain.xyz | selector + signature lookup | all |
| Nansen / Arkham / MetaSleuth | fund-flow tracing, attribution | A15 |
| Tx2Poc | turn a real exploit tx into a Foundry PoC | A10, A15 |

## 6. Agent-side tooling (use, but verify)

| Tool | Note |
|---|---|
| slither-mcp | exposes Slither as agent tools — real value, deterministic output |
| AuditHub MCP + skills | Veridise scanners, invariant discovery |
| `pashov/skills`, `web3-bug-bounty-hunting-ai-skills` | workflow skills, not detectors |
| `hunt atlas` (this repo) | routing: symptom → family → the command above |

Agent output is a lead, never a finding: a claim still needs a PoC that ran and
an independent verification recorded in the ledger.

## Minimum viable stack (order of work)

```text
1. slither + aderyn         sweep known classes          (minutes)
2. surya + grep arsenal     map architecture, assumptions
3. manual review            value sinks backwards, role-based re-read
4. forge fork + PoC         prove the hypothesis         (the money test)
5. echidna / medusa         invariants you cannot eyeball
6. halmos / certora         prove the critical property
7. solodit + contests       find-similar on the suspicious function
8. phalcon / tenderly       confirm real impact and fund flow
```