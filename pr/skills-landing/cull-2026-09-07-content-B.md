# Skills cull — 2026-09-07 (S2b-2 CONTENT pass, batch B)

Executed on branch `conductor`, working-tree only (no commit/push). Scope: the
29 shipped skills under `soul/skills/web3/` (18), `soul/skills/cdc/` (5),
`soul/skills/verification/` (6). Structural moves (S2a) were already done and
committed; this pass moved case material out of shipped SKILL.md bodies and
`references/` trees to `examples/hunts/`, preserved verbatim, with one-line
pointers left behind. All moves via `git mv`; `git rm` for the one targeting
state file.

**Totals: 140 files moved (135 refs + 4 scripts + 3 templates — wait, see
per-skill table), 1 file `git rm`-d, 10 body sections cut to examples (verbatim
+ pointer), 6 sections/pitfalls genericized in place (originals preserved),
~170 secret-shape scrub edits across 25+ files.**

Corrected file-move count (from the per-skill table below):
**131 case refs + 4 scripts + 3 templates + 2 dated case files = 140 moved;
1 git-rm.**

## Per-skill log

| Skill | Action | Files moved (from soul/skills/…/references unless noted) |
|---|---|---|
| web3/black-swan-engine | verify only — clean (no refs, no case-target markers, no key shapes) | — |
| web3/blockchain-node-audit | 21 case refs → `examples/hunts/web3/blockchain-node-audit/references/`; body kept (checklists/pitfalls stay, they are the methodology); ~34 body pointers re-pointed at examples; Reference section compacted. KEPT: `references/geth-debug-rpc-file-write-vector.md` (generic class writeup), `scripts/node-audit-poc.py` | abey x8, beacon-kit/berachain x2, chain33, multivac x2, multiversx, plasma x2, sisir, viction x4 |
| web3/blockchain-rpc-attack-surface-audit | 15 case refs → examples; body kept (probe playbooks, chain33/bityuan class sections stay per manifest); Reference Files section compacted; KEPT: the 4 generic fuzz scripts (`scripts/{rpc,explorer,advanced,smuggling}_fuzz.py`) | bityuan x6, chain33-wallet, multivac x3, aioz, epixnet, partisia, theta, u2u |
| web3/cdc-blockchain-audit | 11 case refs → examples; body kept (playbooks stay); Reference Files section compacted; KEPT: exploit-first-key-ownership-proof, fastapi-backend-trust-mapping, web2-recon-mcp-fastapi, rust-blockchain-node-audit, validator-detection-via-debug + jwt_confusion_probe.py | aptos x3, aelf, berachain, mezo x2, multiversx x2, plasma, trias |
| web3/cross-contract-chain-builder | 1 case ref → examples; body untouched (no pointers to it existed) | viction-chain-analysis |
| web3/custom-chain-rpc-exploit | 2 case refs + 1 case-weaponized script (`naox-module-fuzzer.py`) → examples; body Case Study sections (U2U/Naoris/Berachain/MultiVAC) LEFT IN PLACE per manifest (only refs were listed); pointers fixed incl. 3 cross-skill pointers to examples | berachain-txpool-cors, naoris-naox-chain-case-study, naox-module-fuzzer.py |
| web3/defi-audit-verification | 1 case ref → examples; Reference line re-pointed | tizi-verification |
| web3/defi-protocol-analysis | 12 case refs → examples; **`git rm` `references/web3-next-targets.md`** (per-operator targeting state, not methodology — recoverable from git history); curriculum table `NEXT_TARGETS.md` row dropped; References section regrouped (12 methodology refs kept, listed; case section replaced with pointer + removal note). KEPT per manifest: cheatsheet, curriculum, exploit-chain-building, governance-patterns, bytecode-only-fuzzing, tooling + (unlisted-but-methodology, kept): web3-case-studies, cross-contract-chain-builder.md, erc4337-bundler-architecture-bugbank.md, llm-hallucinated-shell-trap.md, orderbook-dex-relayer-audit.md, skim-exploit-diagnostic.md | yuzu x2, t3tris x2, injective/cosmwasm x3, mezo-musd-tigris-fuzz, qtum, ample, uxlink-aa-paymaster, yzsyrup |
| web3/erc4337-bundler-audit | 1 case ref → examples; 2 pointers re-pointed | aa-bundler-u2u |
| web3/evm-contract-audit | verify only — clean | — |
| web3/l2-rollup-audit | 1 case ref → examples; pointer fixed; KEPT: `scripts/l2-key-check.py`. NOTE: the "Update: EIP-7702 Funds Forwarding (Session 2026-08-15)" body section is Plasma session residue but was NOT in the manifest — left in place, flagged in report | plasma-org-findings |
| web3/lending-protocol-fork-audit | verify only — clean | — |
| web3/on-chain-exploit-workflow | 4 case refs → examples; References section re-pointed; KEPT: `references/eip7702-forwarding-pattern.md` (per manifest, though it is Plasma-derived) | camp, grnd, plasma-org-audit, viction-bytecode-verification |
| web3/on-chain-forensics | 9 case refs → examples; 12 body pointers re-pointed; References section reworked; KEPT: `references/base-chains.md` + `references/web3-private-core-audit-recon.md`. NOTE: Gimo/Sonic/FlyingTulip/Camp body sections left in place (not in manifest for cutting) | flyingtulip x2, yuzu, plasma, hyperliquid, gimo, push4-divergence, squatter, vault-fuzz |
| web3/rate-limited-chain-recon | 6 case refs → examples; **3 body sections cut verbatim → examples + pointers**: Target Worth Matrix (FT vs SaaS) → `sonic-ft-target-worth-matrix.md`, LSaaS StakePool Red-Team (Gimo) → `gimo-lsaas-stakepool-redteam.md`, Governance Re-Read Signal (Naoris) → `naoris-governance-re-read.md` (with 1-sentence reusable rule left inline). Throttle table/workflow/pitfalls/operator-style core KEPT. References section compacted (also dropped 2 stale bullets for files that never existed: governance-re-read-naox-2026-08-11.md, gimo-0g-lsdt-misconfig-2026-08-12.md) | sonic-ft-case, gimo-stakepool-redteam, naoris x3 (architect-a1, a2-redteamer, bsc-ccip-recon), bsc-rpc-50block-limit (dated BSC case, case by LAW 4 — flagged in report) |
| web3/rust-p2p-edge-case-audit | ALL epixnet-* materials → examples: 11 refs + 3 exploit templates + 3 live-WS scripts (`scripts/epixnet-{chain-builder,peer-harvest,ws-exploit}.py`). SKILL.md surgery: generic Rust P2P fuzz methodology body KEPT (intro/when-to-load/triggers/methodology 1-9, generic pitfalls incl. onion-key + signed_data + WS-Origin); **cut verbatim → examples + pointers**: epixnet live pitfalls (18 case bullets F2/F10/F11/F12/D1-D7) → `epixnet-live-pitfalls.md`, Live exploitation peer-enumeration section → `epixnet-live-exploitation-peer-enumeration.md`, CHAINER Full exploit chain (Branch A/B) → `epixnet-full-exploit-chain.md` (reusable CHAINER rule left inline), economic proven-case numbers x2 → `epixnet-economic-proven-2026-08.md`, reference index → `epixnet-references-list.md`. Sibling-skills pointer re-pointed at `examples/hunts/web2/epixnet-ui-redteam/`. User-communication-preferences section KEPT (operator preference content, sovereign-ops precedent) | 17 files |
| web3/smart-contract-exploit-pocs | verify only — clean | — |
| web3/token-transfer-audit | 2 case refs → examples; Case Studies section re-pointed | trias-try-simple, viction-audit |
| cdc/cdc-device-audit | **"Meraki-Specific Patterns" body section cut verbatim → `examples/hunts/cdc/cdc-device-audit/meraki-patterns.md` + pointer**; 4 meraki refs → examples | meraki x4 |
| cdc/cdc-lending-audit-foundry-poc | verify only — clean | — |
| cdc/cdc-web-app-bug-bounty | 19 case refs → examples; **3 case-derived pitfalls genericized in place (<=2 sentences target-agnostic) with originals preserved → `examples/hunts/cdc/cdc-web-app-bug-bounty/case-derived-pitfall-originals.md`**: Strapi V5 Vite `?raw??` family (Colb), Django DEBUG=True (gorealtime), on-chain mirror-URL SSRF (Chia). KEPT: cdc-thinking-cheatsheet.md, user-workflow-preferences.md, 4 templates, scripts/verify_poc.py. NOTE: frontmatter description still names "(Arkose/Chia/Wyze/EDBank case refs)" — left (frontmatter is trigger text; tests pin name/description only) | arkose x2, chia x6, wyze x4, colb, edbank, ed3, grafana, nestjs, nextauth-enum, nextjs-persisted-graphql |
| cdc/multi-target-cdc-audit | **2 body sections cut verbatim → `examples/hunts/cdc/multi-target-cdc-audit/aelf-ebridge-berachain-case-sections.md` + pointers**: Berachain-Specific Patterns subsection, AElf / eBridge Specific Patterns section (incl. its disk-safety + output-style subsections — kept verbatim in examples; the disk-safety/output-style content is substantially duplicated in the kept merged ledger bullets); generic mempool/CORS overflow methodology KEPT. 8 case refs → examples. Merged "From cdc-multi-target-audit" ledger section KEPT untouched per manifest — but its 85+ `references/…` citations were re-pointed to `examples/hunts/cdc/cdc-multi-target-audit/references/` (and 2 to `examples/hunts/recon/web2-spa-recon/`, 1 to examples epixnet-economic) so nothing dangles. 4 ledger citations remain for files that never landed anywhere (aelf-ebridge-real-contract-2026-08-15, alltoscan x2, viction-corrections, viction-multi-batch-cdc — pre-existing dangling, left as-is) | u2u, naoris-fuzz, layer1-batch-scan, berachain-mempool-cors, aelf-ebridge-hunt, genesisL1, trias x2 |
| cdc/sovereign-ops-protocol | 1 case ref → examples; References line re-pointed; curl-hardline/style-protocol/vendor-pivot sections left as-is (operator preference, ruled KEEP). NOTE: JS Bundle Recon section carries Klarna-specific fingerprints (klarnacdn.net, Keycloak kid) — left per manifest (only the ref was listed), flagged in report | klarna-2026-08-20 |
| verification/audit-verification-methodology | **2 per-target body sections generalized in place (originals preserved → `examples/hunts/verification/audit-verification-methodology/ebridge-auditor1-sections.md`)**: CROSS-AUDIT FILTER (eBridge 2026-08-15) — class table + output contract kept, four canonical traps compressed to a 4-part generic demotion-checklist sentence + pointer; RE-AUDIT RPC AUTH (AUDITOR-1 bityuan) — compressed to a 2-sentence VERIFIED-FACT-vs-ASSUMPTION + PoC-matrix lesson + pointer. 2 case-log refs → examples; KEPT: `references/bls-signature-verification-deep-audit-2026.md`. Alpenglow REAL-WORLD EXAMPLE section + version history left (not in manifest), flagged in report | aelf-ebridge-cross-audit-filter, alpenglow-audit-verification-log |
| verification/dynamic-fuzz-testing | 2 case refs → examples; **Everlyn-oracle passages genericized** ("on a live engagement" style): Oracles table rewritten as per-sink-class generic table (original → `examples/hunts/verification/dynamic-fuzz-testing/everlyn-oracle-passages.md`), everlyn example paths/functions/file:lines in Workflow steps 2/4/5 and Inputs genericized. References compacted; ALSO dropped a bullet citing `references/fuzz-oracles.md` — pre-existing dangling (file never landed). Django/trias-flavored pitfalls KEPT (reusable lessons, not in manifest for genericizing). "Linked Harnesses" bullets for `scripts/fuzz_*.py` remain pre-existing dangling (files never landed) | everlyn-fuzz-harnesses, trias-fuzz-2026-08 |
| verification/poc-reverification | verify only — refs are playbooks (csrf-hardened-nextauth-pivot.md, nextauth-probe-playbook.md KEPT). Body carries two Everlyn.ai symptom-pattern examples — ruled verify-only by the manifest, left in place | — |
| verification/requesting-code-review | verify only — clean, target-agnostic | — |
| verification/systematic-debugging | verify only — clean | — |
| verification/test-driven-development | verify only — clean | — |

## Scrubs (law 3) — applied during the moves

Known = already reported in S2a (TokenHarbor thk_live_*, APIKU sk-961*/sk-hXN*, plasma SPONSOR/COMMITTER/PROOF_COORD/OWNER hex keys). Everything below is on top of that.

### NEW full-length live secrets found — REDACTED AND FLAGGED — ROTATION/REVOCATION ADVISED

| # | Secret | Where found | Action |
|---|---|---|---|
| 1 | **Wyze HMAC signing secrets x3** (32-char, exposed in frontend JS per the reports; the reports themselves say "rotate immediately") | wyze-signature-forging-2026-08.md (moved), wyze-web-app-audit-2026-08.md (moved), services-wyze-api-enumeration-2026-08.md (moved) | → `<redacted>` in all 3 (5 occurrences) |
| 2 | **Wyze OAuth clientSecret** (base64, paired with clientId `bfc07c95-…` — client_id kept, it is public-by-design in auth URLs) | wyze-multi-service-audit-2026-08.md (moved) | → `<redacted>` |
| 3 | **ED3 apiKey x2** (UUID-shaped, one live-on-prod per the report) | ed3-xyz-cdc-hunt-2026-08.md (moved) | → `<redacted>` |
| 4 | **Naoris admin-panel password + Firebase password** (full, captured during the hunt) | layer1-batch-scan-2026-08-14.md (moved); elided form in naoris-architect-a1-2026-08-11.md (moved) | → `<redacted>` (2 full + 1 elided) |
| 5 | **go-abey `--singlenode` devnet private key** (FULL 64-hex `229ca04f…64036`, upstream-committed devnet default; skill text says "test for prod reuse") | abey-foundation-trust-graph.md (moved) **and the KEPT `references/geth-debug-rpc-file-write-vector.md`** | → `<redacted>` in both |
| 6 | **MultiVAC test-fixture key material**: 2 full BIP39 24-word mnemonics, 2 "Expected secret key" (128-hex), 7 hardcoded 128-hex private keys from Offline-Tools tests (real-format; drainability unverified but full material) | multivac-redteam-agent2-2026-08-17.md (moved) | → `<redacted>` (11 x 128-hex + 2 mnemonics) |

**These six existed in git history — treat as live until rotated.** Items 1-4 are
third-party targets' secrets (report to those programs is the operator's call);
items 5-6 are upstream-repo key material worth on-chain monitoring.

### Known/elided shapes redacted (no new-flag)

| Shape | Files |
|---|---|
| Elided plasma key prefixes `0xffd79033…`/`0x385c5464…`/`0x39725efe…`/`0x941e1033…` (known S2a keys) | plasma-ethrex-audit-2026-08-14.md (moved) x4; cdc-blockchain-audit SKILL.md (KEPT) x1 |
| Elided abey singlenode key `229ca04fb…64036` / `229ca04f…` / bare `229ca04f` (incl. grep anchors) | 6 moved abey refs + multivac-ecosystem ref; blockchain-node-audit SKILL.md (KEPT); multi-target-cdc-audit SKILL.md (KEPT) |
| MultiVAC genesis byte-array key bytes (`{158, 139, …}` partial key material) | multivac-ecosystem-trust-graph.md (moved) x2; blockchain-node-audit SKILL.md (KEPT) x1 |

Kept as public data (not secrets): contract addresses, tx hashes, EIP-1967
slots, Transfer topics, signature r/s values, public keys, OAuth client_id,
block-explorer UUIDs. Zero `.ts.net`/`vm-0-3` hits in the three categories.

### Out-of-scope secret residue found (NOT touched — flag only)

- **The same Wyze HMAC x3 + OAuth clientSecret remain in
  `soul/skills/web2/web2-api-security-patterns/` (SKILL.md + references/wyze-signature-forging-2026-08-24.md)** —
  web2 category is outside this batch. The web2 owner should apply the same
  redactions.
- Elided abey-key fragments remain in
  `examples/hunts/cdc/cdc-multi-target-audit/references/abey-go-abey-debug-filewrite-2026-08-16.md`
  (S2a-moved folder, do-not-touch list).

## Section cuts + genericizations (other than per-skill table above)

| Type | Count |
|---|---|
| Body sections cut verbatim to examples + pointer left | 10 (cdc-device-audit 1, multi-target 2, rate-limited 3, rust-p2p 4 groups) |
| Sections/pitfalls genericized in place, originals preserved to examples | 6 (cdc-web-app 3 pitfalls, audit-verification 2 sections, dynamic-fuzz oracles) |
| New example section-files written | 11 (meraki-patterns, aelf-ebridge-berachain-case-sections, sonic-ft-target-worth-matrix, gimo-lsaas-stakepool-redteam, naoris-governance-re-read, epixnet-live-pitfalls, epixnet-live-exploitation-peer-enumeration, epixnet-full-exploit-chain, epixnet-economic-proven-2026-08, epixnet-references-list, case-derived-pitfall-originals, ebridge-auditor1-sections, everlyn-oracle-passages — 13 total) |

## Left in place while torn (noted for the record)

- l2-rollup-audit: "Update: EIP-7702 Funds Forwarding (Session 2026-08-15)" body section (Plasma session log; manifest listed only the ref).
- custom-chain-rpc-exploit: U2U/Naoris/Berachain/MultiVAC Case Study body sections (manifest listed only refs + fuzzer script).
- on-chain-forensics: Gimo 0G LSD trust-graph, Sonic/FlyingTulip, Vault-chain, Camp Blockscout body sections (manifest listed only refs).
- on-chain-exploit-workflow: "Example: Plasma Audit" / "Viction Case Study" / "Plasma Case Study" inline examples (kept; the eip7702 pattern ref is the generic carrier).
- audit-verification-methodology: Alpenglow "REAL-WORLD EXAMPLE" tables + version history (manifest named only eBridge/AUDITOR-1).
- rust-p2p-edge-case-audit: "User communication preferences (EpixNet campaign)" (operator preference, KEEP precedent) and Workflow step 6's `/root/epixnet-src` deposit path (case color in kept body).
- sovereign-ops-protocol: JS Bundle Recon section's Klarna fingerprints (operator preference content, ruled KEEP).
- poc-reverification: two Everlyn.ai symptom-pattern examples (verify-only skill).
- defi-protocol-analysis P1 pitfall's T3tris inline example; blockchain-node-audit / blockchain-rpc case-colored pitfalls (instructed to keep methodology body).
- rate-limited-chain-recon: `bsc-rpc-50block-limit-2026-08-14.md` moved as case under LAW 4 (named chain + date + session specifics) though the manifest text said "Sonic-FT/Gimo/Naoris" refs — flagged here.
- cdc-web-app frontmatter description still names case programs (trigger text).
- multi-target-cdc-audit: 4 ledger citations to never-landed files (pre-existing dangling, left).

## Verification (results)

- `cd app && PYTHONPATH=src python -m pytest tests/test_skills.py tests/test_install.py -q` — **20 passed** (run after the full pass, 2026-09-07).
- Spot-checks: `examples/hunts/web3/blockchain-node-audit/references/multivac-redteam-agent2-2026-08-17.md`, `examples/hunts/web3/rust-p2p-edge-case-audit/scripts/epixnet-ws-exploit.py`, and `examples/hunts/cdc/cdc-web-app-bug-bounty/references/wyze-signature-forging-2026-08.md` all present in examples; the source dirs now contain only the kept files (`geth-debug-rpc-file-write-vector.md`; the 2 cdc-web-app methodology refs). `git status` confirms **140 renames** out of the three categories + 1 `git rm` (web3-next-targets.md). 15 emptied `references/`-family dirs removed from the working tree (git does not track empty dirs).
- Required grep `grep -rn "0x[0-9a-fA-F]\{64\}\|sk-\|thk_live" soul/skills/web3 soul/skills/cdc soul/skills/verification | grep -v redacted` → 22 hits, **ALL false positives**: EIP-1967 impl/admin/beacon slots and the ERC-20 Transfer topic (public standard constants), one public tx hash, and `sk-` substrings inside `task-*.log` / `disk-safety`. Zero private keys, zero API keys, zero thk_live.

---

# Follow-up pass (same day) — flagged-residue completion

Five items from the S2b-2 report's "left in place while torn" list, plus one
explicit NO-CHANGE. Same laws: verbatim preservation, pointer line, scrub, no
commit.

| # | Item | Action |
|---|---|---|
| 1 | web3/l2-rollup-audit — "Update: EIP-7702 Funds Forwarding (Session 2026-08-15)" body section | Cut verbatim (incl. leading `---` separator) → `examples/hunts/web3/l2-rollup-audit/eip7702-session.md` + pointer section left (`## Update: EIP-7702 Funds Forwarding`), noting Pitfall 6 carries the reusable lesson. The section had NO raw key material (addresses + tx hash only — public). |
| 2 | web3/custom-chain-rpc-exploit — per-target Case Study body sections | All 4 (U2U chain 39, Naoris NaoX 46512, Berachain mainnet 80094, MultiVAC mainnet 62621) cut verbatim → `examples/hunts/web3/custom-chain-rpc-exploit/case-studies.md` + `## Case Studies` pointer. Generic methodology (Triggers / Report Style / Recon Pattern / Severity by Module / Custom Module Method Fuzzing / Pitfalls) stays self-contained. |
| 3 | web3/on-chain-forensics — Gimo/Sonic/Camp per-target body sections | 4 sections cut verbatim → ONE combined `examples/hunts/web3/on-chain-forensics/target-sessions.md` (Gimo 0G LSD trust graph 2026-08-12; Camp dead-RPC Blockscout-proxy 2026-08; Sonic FlyingTulip FT OFT case 2026-08-08; FlyingTulip 7127 vault-chain/Safe-nesting 2026-08-09) + `## Target Sessions` pointer. Forensics method KEPT: Phase 0-3 workflows, selector/squatter detection, Signature-Mint recon, custom-error brute force, L2-exec-client patterns, proxy bytecode analysis, multi-chain zero-bytecode check, operator-preference sections. |
| 4 | verification/audit-verification-methodology — Alpenglow worked example | `## REAL-WORLD EXAMPLE (This Session)` (claims-vs-reality + independent findings tables) cut verbatim → `examples/hunts/verification/audit-verification-methodology/alpenglow-example.md` + one-line pointer. The method's steps (TRUTH ENFORCEMENT, EXTERNAL REPORT AUDIT WORKFLOW, CLAIM CLASSIFICATION, CROSS-AUDIT FILTER, RE-AUDIT, AUDIT WORKFLOW INTEGRATION, ANTI-HYPERBOLE CHECKLIST) all stay. |
| 5 | web3/rust-p2p-edge-case-audit — operator-communication section | `## User communication preferences (EpixNet campaign)` moved verbatim → `docs/operator/rust-p2p-operator-notes.md` (operator notes, not hunting methodology; extraction note at top) + pointer line in SKILL.md. |
| 6 | verification/poc-reverification | **NO-CHANGE** — worked examples marked as such are legal per `soul/skills/README.md` ("Carry worked examples — real commands and real output shapes, marked as such"). Untouched. |

**Follow-up totals: 5 body sections cut/moved verbatim (5 new preserved files: 4 under
examples/hunts/ + 1 under docs/operator/), 5 pointer lines left, 0 files git-mv'd, 0
new scrubs needed (re-grep below).**

## Follow-up secret re-grep (whole scope: 29 skills + owned examples trees + new docs/operator file)

Searched for every NEW secret shape found this pass, exact values and generic forms:

| Shape | Result |
|---|---|
| Wyze HMAC secrets x3 (`gbJojEBVi…`, `obb2ZnAz…`, `5Z1Bg7wM…`) | **0 hits** — no other skill quotes them (in-scope) |
| Wyze OAuth clientSecret base64 (`WMNpD2qN…`) + `atob("…")` shapes | **0 hits** |
| ED3 apiKey UUIDs (`d9b2d63d…`, `97428467…`) + generic apiKey-UUID shapes | **0 hits**; the 3 remaining Wyze `client_id bfc07c95-…` UUIDs are OAuth client_ids (public by design, embedded in auth URLs) — paired secrets are already `<redacted>` |
| Naoris admin + Firebase passwords (`HHrF4KOJ…`, `WtkyB-…`) | **0 hits** |
| 64-hex devnet-key shapes (`229ca04f…` full + all elisions/prefixes) | **0 hits**; the 6 remaining 64-hex strings in scope are public data: MultiVAC tx signature r/s values, NaoX genesis hash, the PAUSER role-name keccak constant, Gimo tx hashes/topic |
| BIP39 mnemonics (the 2 exact phrases + generic 12/24-word line shapes) | **0 hits** |
| 128-hex keys | **0 hits** |

Still out of scope (unchanged flags from the main pass): the same Wyze secrets remain
in `soul/skills/web2/web2-api-security-patterns/` (web2 category — web2 owner to
redact), and elided abey-key fragments remain in the do-not-touch
`examples/hunts/cdc/cdc-multi-target-audit/references/abey-go-abey-debug-filewrite-2026-08-16.md`.

## Follow-up verification (results)

- `cd app && PYTHONPATH=src python -m pytest tests/test_skills.py tests/test_install.py -q` — **20 passed** (rerun after the follow-up edits).
- Spot-check: all 5 new preserved files exist (`eip7702-session.md`, `case-studies.md`, `target-sessions.md`, `alpenglow-example.md`, `docs/operator/rust-p2p-operator-notes.md`); each cut SKILL.md carries its one-line pointer and keeps its methodology sections; no empty sections or broken markdown at the cut seams.
