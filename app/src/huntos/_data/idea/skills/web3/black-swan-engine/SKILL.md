---
name: black-swan-engine
description: "19 universal laws of EVM vulnerability (CDC backbone)"
lanes: architect,red-teamer
scope: contract
---

# Black Swan Engine — Universal Vulnerability Discovery (EVM)

The engine behind `IDEA.md` § BLACK SWAN ENGINE. Derive laws from first
principles. Classify violations. Build exploit chains through adversarial
reasoning. The laws below are the CDC backbone for smart-contract auditing:
every audit is a loop of **derive → classify → chain → falsify**, never a
checklist pass.

## Provenance

Reconstructed for HunterOS. The source skills pack (master catalog,
category 03) lists `black-swan-engine` but ships no standalone file for it;
the 19 laws below were derived from first principles and consolidated from
the landing corpus of web3 hunt skills in `skills/web3/` (each law
cites the skill carrying its worked patterns). Per repo doctrine, treat any
law not yet backed by a proven finding as `theoretical` until a live hunt
confirms it.

## The Engine Loop (CDC backbone)

1. **Derive** — read the target like no one ever has. For every mechanism,
   ask "what MUST be true for this to work?" Each answer is an invariant.
   Every invariant a developer left unverified is a law waiting to be
   invoked. (See `cdc-blockchain-audit`, `evm-contract-audit`.)
2. **Classify** — map each surface to the law it violates (below). A surface
   violating no law is deprioritized; a surface violating two laws is a
   priority target.
3. **Chain** — Chain, don't collect. Express each micro-bug as
   `[Trigger] → [Effect] → [Trust Boundary Crossed]`, then hunt the handoff
   points where gadget A hands off to gadget B. (See
   `cross-contract-chain-builder`.)
4. **Falsify** — every candidate finding gets an adversary: "prove this
   isn't exploitable." Adversary fails → it survives. Adversary succeeds →
   discard, zero ego. Never call a finding "jackpot" unless it is directly
   exploitable for fund theft, RCE, or admin takeover.
5. **Prove** — label honestly: `theoretical` → `proven-in-code` (PoC runs
   against source/fork) → `proven-live` (impact demonstrated on the live
   chain). The claim gate reads output regardless of what this skill wrote.

## The 19 Universal Laws of EVM Vulnerability

1. **The Unverified Assumption Is the Attack Surface.** Developer beliefs
   ("`balanceOf()` returns the real balance", "this contract is trusted")
   are invariants nobody tests. Enumerate the beliefs, attack the untested
   one. → `evm-contract-audit`, `on-chain-exploit-workflow`.
2. **A Token Is a Program, Never a Number.** Any external token contract
   controls its own `balanceOf`, `transfer`, decimals, and fees. A
   malicious token lies. Account by delta and you account by fiction.
   → `smart-contract-exploit-pocs`, `defi-protocol-analysis`.
3. **Arithmetic Is Where Trust Goes to Die.** Precision loss, rounding
   direction, `balanceAfter - balanceBefore` deltas, unchecked casts, and
   division-before-multiplication are the default fund-theft primitive.
   → `defi-protocol-analysis`, `smart-contract-exploit-pocs`.
4. **Storage Layout Is a Writable Interface.** Packed slots, proxy storage
   collisions, uninitialized implementation slots, and EIP-1967 decoding
   (`eth_getStorageAt` slot 0 `owner<<8|0x01`, not a clean address) are all
   the same law: state layout is attacker-reachable. → `on-chain-forensics`,
   `l2-rollup-audit`.
5. **Access Control Is a Path, Not a Modifier.** A `modifier` guards a
   function; the law asks which *path* reaches the effect without passing
   it — initializers, fallbacks, delegatecalls, role-bearing proxies,
   dual-guard revert frames (`CALLER/EQ` + mask). → `evm-contract-audit`,
   `rate-limited-chain-recon`.
6. **Signatures Are Data, Not Authority.** Replay, malleability, missing
   `chainId`/nonce binding, domain-separator confusion, and signer-vs-sender
   mismatch turn a valid signature into a skeleton key. →
   `evm-contract-audit`, `erc4337-bundler-audit`.
7. **Oracles Are the Cheapest Object on the Chain to Move.** Spot prices,
   single-source feeds, and reserve-derived prices bend under liquidity you
   do not own. Price the protocol with a price you control. →
   `defi-protocol-analysis`, `lending-protocol-fork-audit`.
8. **Ordering Is Permission.** Public mempools and visible queues
   (`txpool_status` growth, pending/queued imbalance) mean transaction
   order is an exploitable resource: frontrun, backrun, censorship. →
   `custom-chain-rpc-exploit`, `rate-limited-chain-recon`.
9. **Upgradability Converts Trust into a Pending Transaction.** Every proxy
   is a future contract you have not met: verify the implementation slot
   yourself, never trust the explorer's claim, and treat admin-key custody
   as the crown-jewel question. → `on-chain-forensics`, `evm-contract-audit`.
10. **The Chain Boundary Is a Trust Boundary.** Cross-contract calls, bridge
    messaging, L1↔L2 relays, and cross-chain deployments each carry the
    source domain's assumptions into a domain that does not honor them.
    The handoff point is where the chain gadgets. →
    `cross-contract-chain-builder`, `l2-rollup-audit`.
11. **Defaults Are Secrets.** Hardcoded sponsor/committer/prover keys,
    genesis byte-array keys, and real-format private keys committed as test
    fixtures are live credentials with a public address. Derive the address,
    check nonce and balance. → `blockchain-node-audit`, `l2-rollup-audit`.
12. **Deterministic Derivation Means Leaked Once, Drained Forever.** BIP39
    and fixed-curve derivations are time-invariant: a mnemonic committed
    today unlocks the same account on every future day and every chain it
    funded. → `blockchain-node-audit`.
13. **Infrastructure Endpoints Are Contract Surface.** RPC nodes are
    contracts with JSON-RPC ABI: exposed `debug`/`admin`/`personal`
    namespaces, CORS `*` echoes, and unlocked accounts extend the EVM attack
    surface past the bytecode. → `custom-chain-rpc-exploit`,
    `blockchain-rpc-attack-surface-audit`.
14. **The Fork Is a Fossil Record.** A lending fork inherits every ancestor
    vulnerability plus every divergence bug introduced by the port. Diff
    against the ancestor before trusting any upstream audit claim. →
    `lending-protocol-fork-audit`, `defi-audit-verification`.
15. **Liquidity Is an Attack Multiplier.** Flash loans make any price the
    price and any governance threshold a day-pass: evaluate every
    economic check as if the attacker can rent majority power for one
    block. → `defi-protocol-analysis`, `evm-contract-audit`.
16. **Time and Finality Assumptions Fail Under Stress.** Block timestamps,
    reorg windows, bridge lag, and sequencer downtime are consensus-level
    inputs that contracts read as facts. Attack the lag, not the lock. →
    `l2-rollup-audit`, `blockchain-consensus-audit`.
17. **Replay Is the Default, Uniqueness Is the Exception.** Any message,
    permit, or calldata not bound to a chain, contract, nonce, and deadline
    can be rebroadcast where it still works. Assume replay until proven
    unique. → `erc4337-bundler-audit`, `custom-chain-rpc-exploit`.
18. **A Verifier You Cannot Run Is a Claim You Cannot Trust.** External
    audit claims, explorer labels, and docs are hypotheses. Verify against
    source and live state (`cosmos-live-chain-verification`,
    `defi-audit-verification`) — evidence or nothing. →
    `defi-audit-verification`, `cosmos-live-chain-verification`.
19. **Unproven Impact Is Not Impact.** A vulnerability that cannot be
    demonstrated — mainnet address + chainId for `proven-in-code`, tx hash
    or state proof for `proven-live` — stays `theoretical`, and a
    theoretical finding never masquerades as a critical. Fabricating a
    mainnet tx hash is the one unforgivable violation. →
    `cdc-blockchain-audit` (ladder), repo `templates/FINDING.md`.

## Applying the engine on an audit

- Open with 4+ genuinely different routes (input parsing, auth, accounting,
  dependencies, infra). Group by research idea, not wording — three routes
  chasing "reentrancy" differently are one route.
- Classify every observed surface against the 19 laws; a two-law violation
  (e.g. law 3 arithmetic + law 7 oracle) outranks a single-law one.
- Stall after two unproductive rounds → **MARK BLOCKED**; reopen only on a
  materially new mechanism.
- Close every hunt by recording which law fired, so the law earns
  `proven-live` provenance in its own right.

## When a law is missing

New laws are born only through CDC + adversarial research loops (per
IDEA.md: "Evolves: new laws discovered through CDC + adversarial research
loops"). Propose a law by showing one unverified assumption that generalizes
across targets and one confirmed finding it explains — a law with zero
confirmed findings stays out of the table.
