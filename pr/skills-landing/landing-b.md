# Landing report B — category 03 (web3/blockchain) → `soul/skills/web3/`

Branch `land-b`, worktree `HunterOS-land-b`. Source:
`the operator_Skills_Master/03-web3-blockchain.zip` (extracted to the system temp
directory, never inside the repo). Not committed — working-tree changes only.

## Result

35 source folders in the zip → **34 landed + 1 skipped + 1 authored flagship**
(35 skill folders total under `soul/skills/web3/`).

### Landed (34)

0g-storage-node-audit, blockchain-consensus-audit, blockchain-node-audit,
blockchain-rpc-attack-surface-audit, cdc-blockchain-audit,
consensus-integration-audit, consensus-protocol-audit,
cosmos-evm-deserialization-audit, cosmos-hook-audit,
cosmos-live-chain-verification, cosmwasm-contract-audit,
cross-contract-chain-builder, custom-chain-rpc-exploit,
defi-audit-verification, defi-protocol-analysis, erc4337-bundler-audit,
evm-contract-audit, go-edge-case-audit, hypervisor-trust-boundary-audit,
kubernetes-security-audit, l2-rollup-audit, lending-protocol-fork-audit,
octopus-deploy-audit, on-chain-exploit-workflow, on-chain-forensics,
rate-limited-chain-recon, rust-l1-node-audit, rust-p2p-edge-case-audit,
smart-contract-exploit-pocs, solana-anchor-audit,
spring-oauth-rbac-gate-audit, spring-rbac-oauth-audit, token-transfer-audit,
wasm-vm-sandbox-audit.

### Skipped (1)

- `ec2-instance-hardening` — present in the 03 zip but misfiled: the KATALOG
  indexes it under categories 06 (infra-osint) and 08 (devops-cloud), and it
  is not a web3 hunting skill. Skipped here to avoid a duplicate when those
  categories land; nothing web3-specific was lost.

### Format conversions / normalization

- Source format was already the target shape: one folder per skill with a
  `SKILL.md` (YAML frontmatter `name:` + `description:` + trigger keywords)
  plus `references/`, `scripts/`, `templates/` text assets. Landed as-is.
- One folder renamed to match its own frontmatter and the KATALOG:
  `smart-contract-audit-templates/` → `smart-contract-exploit-pocs/`
  (frontmatter `name: smart-contract-exploit-pocs`).
- No functional-name violations: no source folder or skill name carried
  persona branding; persona strings inside file bodies were neutralized (see
  `web3-hygiene.md`).
- Asset policy: `references/` and `scripts/` kept alongside SKILL.md (they
  carry the real-hunt case data the skills cite). Python scripts and one
  JSON audit asset kept; no binaries, nothing size-excluded.

## Flagship: `black-swan-engine`

**Landed at exactly `soul/skills/web3/black-swan-engine/SKILL.md`** — closing
the dangling reference at `soul/SOUL.md:813`
(`skill_view(name='black-swan-engine')`). CI pins the SOUL.md section
("BLACK SWAN ENGINE", `.github/workflows/ci.yml:43`); the skill itself now
exists at the import target documented in `soul/skills/README.md`.

### Where its content came from — IMPORTANT DEVIATION

**The pack contains no standalone `black-swan-engine` file.** The KATALOG
lists it under category 03 ("19 universal laws EVM vulnerability, CDC
backbone"), but:

- the 03 zip has 35 folders and none is black-swan-engine;
- a content grep across **all 12 category zips** and the master zip found no
  file carrying the 19 laws (only tangential hits: a "Black Swan / Moriarty
  Analysis — Post-CDC Extension" appendix inside category 02's
  `adversarial-exploit-chains`, and lowercase "blackswan" risk mentions in
  Sonic case references);
- a workspace-wide search for any `*swan*` file or "19 universal laws" text
  found nothing beyond the KATALOG one-liner.

So the 19 laws **are not truncated in the source — they are absent from the
source entirely**. To satisfy the MUST-land requirement without inventing
attribution, the flagship was **reconstructed**: the SKILL.md documents its
own provenance in a "Provenance" section, and the 19 laws were derived from
first principles and consolidated from the landed web3 corpus — every law
cites the landed skill(s) carrying its worked patterns (evm-contract-audit,
on-chain-forensics, blockchain-node-audit, l2-rollup-audit,
lending-protocol-fork-audit, custom-chain-rpc-exploit, cdc-blockchain-audit,
defi-audit-verification, cross-contract-chain-builder, erc4337-bundler-audit,
smart-contract-exploit-pocs, defi-protocol-analysis, rate-limited-chain-recon,
blockchain-consensus-audit, cosmos-live-chain-verification,
blockchain-rpc-attack-surface-audit). Per repo doctrine, the skill instructs
that any law not yet backed by a confirmed finding stays `theoretical`. If a
genuine source file for the 19 laws surfaces later, it should replace the
reconstruction and this note.

### Structure of the landed skill

Frontmatter per `soul/skills/README.md` (`name:`, `lanes: architect,red-teamer`,
`scope: contract`), then:

- **Engine loop (CDC backbone)**: derive → classify → chain → falsify → prove,
  with stall=BLOCKED and the anti-hyperbole protocol.
- **The 19 universal laws**, each with a name, a one-line statement, and a
  pointer to the landed skill carrying its worked patterns:

  1. The Unverified Assumption Is the Attack Surface
  2. A Token Is a Program, Never a Number
  3. Arithmetic Is Where Trust Goes to Die
  4. Storage Layout Is a Writable Interface
  5. Access Control Is a Path, Not a Modifier
  6. Signatures Are Data, Not Authority
  7. Oracles Are the Cheapest Object on the Chain to Move
  8. Ordering Is Permission
  9. Upgradability Converts Trust into a Pending Transaction
  10. The Chain Boundary Is a Trust Boundary
  11. Defaults Are Secrets
  12. Deterministic Derivation Means Leaked Once, Drained Forever
  13. Infrastructure Endpoints Are Contract Surface
  14. The Fork Is a Fossil Record
  15. Liquidity Is an Attack Multiplier
  16. Time and Finality Assumptions Fail Under Stress
  17. Replay Is the Default, Uniqueness Is the Exception
  18. A Verifier You Cannot Run Is a Claim You Cannot Trust
  19. Unproven Impact Is Not Impact

- **Applying the engine** (route divergence, two-law priority rule, blocked
  marking, per-hunt law attribution) and **when a law is missing** (law
  admission rule: CDC + adversarial loop, one confirmed finding required).

No extra assets were landed with the flagship (no laws/case files exist in
the source to carry over).

## Hygiene

All redactions and persona neutralizations are itemized in
`pr/skills-landing/web3-hygiene.md`: 8 redaction targets (3 real-format
ethrex private keys across 5 files + a keyed Infura RPC endpoint in 1 file),
9 persona-edit files. Post-pass verification: zero hits for `the operator`/`the operator`
(case-insensitive) and for every secret pattern in the landed tree.
