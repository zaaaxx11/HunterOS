# Skills cull — S2b-1 content pass A (2026-09-07): recon (4) + web2 (19) + osint (1)

> FOLLOW-UP SECTION AT BOTTOM (Wyze secret scrub P0, adversarial-bug-bounty-hunting
> manifest-gap cleanup, residue moves, new key flag). Pass-1 record below.

Executed on branch `conductor` after S2a (structure). Manifest was
operator-approved; this log records, per skill: files moved (from -> to),
body sections cut + where they landed, dedups removed, scrubs applied.
Case material is PRESERVED in `examples/hunts/`; SKILL.md bodies were kept
self-contained for a different target (verbatim cut text, one-line pointers).

## Totals (this pass, this agent's scope only)

| Metric | Count |
|---|---|
| Files moved to examples/hunts/ (git mv) | 116 |
| Body sections/blocks cut to examples or docs/operator | 42 (23 spa-recon pitfall sections, 7 ZERO-DAY SNIFF, 5 exploit-chain walkthrough blocks, 4 persona-operations, 1 Upwork pitfalls, 1 trias-lab comment block, 1 ed3 origin) |
| Dedup twins `git rm`'d | 9 (1 predator `reference/`, 5 exploit-chains underscore twins, 3 js-secret-scanner near-dups) |
| Scrubs applied | 5 files + 1 hostname (see Scrubs) |
| NEW full-length live keys found | **0** (only previously-reported elided shapes; all redacted) |
| Ghost refs removed | 8 (files that never existed anywhere in git history) |

## Per-skill record

### recon/predator-recon
- Moved: `references/mergify-auth-bypass-case-study.md`, `references/mergify-case-study.md`, `references/t3tris-finance-case-study.md` -> `examples/hunts/recon/predator-recon/`.
- DEDUP: `reference/methodology-cheatsheet.md` verified byte-identical (`diff` clean) to `references/methodology-cheatsheet.md` -> whole `reference/` dir `git rm -r`'d (contained only that file).
- Pointers updated: 3 table rows + 2 CASE STUDIES bullets -> examples paths.
- Left in place (torn, per manifest "all other refs = tool/methodology"): `references/paxos-gas-exploits.md` (Paxos 2026-07-19 findings table — reads case-ish; manifest classified it keep).

### recon/web2-spa-recon
- BODY CUT: 23 per-target "Pitfalls — <target> 2026-08" sections (AIOZ, aelfscan, Bityuan, BC Swap, VersatizeCoin x2, partisiafoundation, Alltoscan x4, trias.one Umi, Trias Umi isolation, GenesisL1 x2, Nuxaris x8, Colb Finance) -> combined `examples/hunts/recon/web2-spa-recon/pitfalls-per-target.md` (per-target headers preserved; `references/` paths inside rewritten to `./`).
- Pointer line left in body + References section reduced to the same pointer line.
- Kept generic sections (no target in heading; torn -> keep): Architect Trust-Graph Checklist (versatizecoin-annotated), Pitfalls — JSON-RPC Proxy Discovery, Pitfalls — API `id=0` -> 500, Red-Teamer Evidence Format, Decision: When to Claim SSRF.
- Moved: all 33 `references/*.md` (dated per-target case refs) -> `examples/hunts/recon/web2-spa-recon/`.
- Cross-skill pointer in kept checklist re-pointed to `examples/hunts/recon/web2-admin-takeover/versatizecoin-admin-localstorage-bypass-2026-08.md`.

### recon/web2-admin-takeover
- Moved: `references/bcswap-admin-takeover-2026-08.md`, `references/versatizecoin-admin-localstorage-bypass-2026-08.md` -> `examples/hunts/recon/web2-admin-takeover/`; 3 body pointers updated. Kept `references/debug-api-exploitation.md` + scripts.

### recon/cloudflare-waf-graphql-recon
- BODY CUT: "Pitfalls — Upwork 2026-08-19" -> `examples/hunts/recon/cloudflare-waf-graphql-recon/upwork-pitfalls.md` + pointer line.
- Added 1 generalized line (reusable WAF-bypass insight): TLS-emulation clients (cloudscraper) do not pass CF *managed* challenges — real browser or pivot.
- GHOST removed: `references/upwork-cf-graphql-2026-08-19.md` (never existed anywhere in git history).

### web2/adversarial-bug-bounty-hunting
- BODY CUT: 7 "ZERO-DAY SNIFF — <target>" sections (Everlyn 2026-08-09, 375.ai, GIMO, NOISE.XYZ, Keeta x2, Modulo) -> combined `examples/hunts/web2/adversarial-bug-bounty-hunting/zero-day-sniff-notes.md` + pointer. (Manifest said ~12; exactly 7 headings existed. 3 "ZERO-DAY FINDINGS" sections (naox/everlyn/shopify) + the ~54 unlisted case-dated refs in `references/` were NOT in the manifest cut list -> left, flagged to supervisor.)
- Left torn: `references/skate-org-2026-08.md` (dated target case ref, unlisted in manifest).

### web2/adversarial-exploit-chains
- BODY CUT (case-validated chain walkthroughs with file:line) -> 5 new files in `examples/hunts/web2/adversarial-exploit-chains/`:
  - `everlyn-pickle-chain-walkthrough.md` (ANTRP/chair.py lines 463-465 chain)
  - `tare-nav-inflation-chain-walkthrough.md`
  - `alpenglow-chain-walkthroughs.md` (6 chains, two near-duplicate copies — both preserved, copies were not byte-identical)
  - `vote-pool-destroy-button-walkthrough.md` (## VOTE POOL CROSS-TYPE CONFLICT section)
  - `aioz-cross-component-handoff-walkthrough.md` (Handoff Map + Chains Proven (3) + Stub Repo Pitfall; CHAINER grep kit kept in body)
  - 10 Shopify Hydrogen/Dawn chains + Tare/Alpenglow blocks removed from "Chain Construction"; pointer lines left at all 4 cut sites.
- Moved: 21 dated/target case refs -> examples (aioz-mediamtx, alpenglow-consensus-exploit-chain, alpenglow-zero-day-patterns, epixnet-preauth, everlyn x5, helios-chains, hybrid-defi-cdc-hunt (RootsFi), paybox-moonpay, shopify-hydrogen-open-redirect, tare-nav-inflation-exploit, theta-token, u2u x3, versatize x2, vote-pool-cross-type-conflict).
- DEDUP (underscore twins `git rm`'d, kebab kept — kebab version is the longer/refined rewrite, verified near-identical in substance):
  1. `4_agent_cross_audit_pattern_refined.md` (kept `4-agent-cross-audit-pattern.md`)
  2. `doomsday_scenario_synthesis.md` (kept `doomsday-scenario-synthesis.md`)
  3. `mathematical_brute_force_unified_audit.md` (kept `mathematical-brute-force-unified-audit.md`)
  4. `real_proof_extraction.md` (kept `real-proof-extraction.md`)
  5. `validator_key_leak_destroy_button.md` (kept `validator-key-leak-destroy-button.md`)
- KEPT methodology refs: 4-agent-cross-audit-pattern, alpenglow-validator-recon (torn -> keep; phase-6 recon methodology), blackswan-moriarty, ci_cd_leak_hunter_validator_keys, deserialization-rce, doomsday-scenario-synthesis, github-actions-rce, mathematical-brute-force-unified-audit, model-selection-guide, nextjs-turbopack-decompile, real-proof-extraction, saas-platform-recon, solana_rust_audit_patterns_alpenglow (torn -> keep; pattern library), template-injection, validator-key-leak-destroy-button, the operator-direct-execution (torn -> keep; operator behavior protocol, flagged).
- Kept body "Hybrid DeFi CDC Hunt (RootsFi 2026-08)" section (reads as generalized pattern; only the reference twin moved).
- Body already contains 3x duplicated copies of several class sections (MATHEMATICAL BRUTE FORCE / DOOMSDAY / REAL PROOF / 4-AGENT) — pre-existing editing artifact, out of scope, left.

### web2/adversarial-persona-operations
- Cut "SOUL.MD PERSONA CONFIGURATION" + "persona MODE ACTIVATION PROTOCOL" -> NEW `docs/operator/persona-config.md` (extraction note at top).
- Cut "TARGET: EVERLYN.AI — OPERATIONAL CONTEXT" + "DELIVERY VECTORS FOR EVERLYN" -> `examples/hunts/web2/adversarial-persona-operations/everlyn-op.md`.
- Pointers left for both sites. `references/everlyn-intel.md` NOT in manifest -> left in skill, flagged to supervisor.

### web2/bug-bounty-agent
- Moved: `coupang-taiwan-case-study.md`, `coupang-zero-day-case-study.md`, `injective-cosmwasm-exploit-patterns.md`, `saphyre-audit-methodology.md` -> `examples/hunts/web2/bug-bounty-agent/`; 1 pointer updated.
- Torn -> kept + flagged: `nextauth-admin-takeover.md`, `github-secret-leakage-playbook.md`, `non-web3-target-pivot.md` (all everlyn-derived but methodology-shaped).
- SCRUB in kept `references/github-secret-leakage-playbook.md`: `sk-Jvx...B47f`, `Bearer sk-JvxB47f`, `sk-zk2...2bbc` -> `<redacted>`; zhizengzeng.com / api.zhizengzeng.com / apikeyplus.com URLs -> `<third-party-endpoint>`.
- Coupang-derived body lessons ("Critical Methodology Updates (From Coupang Taiwan Audit)" etc.) not in manifest cut list -> left.

### web2/business-logic-invariant-hunt
- Moved: `everlyn-labs-waitlist-invite-analysis.md`, `everlyn-umbrella-repo-pivot.md`, `nuxaris-2026-08-deep-hunt.md`, `partisia-wordpress-wpforms-2026-08.md`, `crypto-payment-shipany-analysis.md` (everlyn 2026-08-04 case; differs from the S2a nextauth-authz-probe twin) -> `examples/hunts/web2/business-logic-invariant-hunt/`; 6 pointers updated.
- Kept: all nextauth-boundary checklists x6, probe-commands, authjs-v5-endpoint-fingerprints. Torn -> kept + flagged: `drift-autopsies.md` (RULE ZERO session autopsies — operator-discipline log), `expo-rn-web-app-recon.md`.
- SCRUB in moved `everlyn-umbrella-repo-pivot.md`: elided keys `sk-zk25…`, `sk-Jvx…` -> `<redacted>`; zhizengzeng/apikeyplus -> `<third-party-endpoint>`.

### web2/disk-space-session-safety
- Moved: `keeta-local-first-disk-budget-2026-08-12.md` -> `examples/hunts/web2/disk-space-session-safety/`; pointer updated.
- SCRUB (SKILL.md, Hermes-session specifics genericized to "agent runtime session errors (see docs/operator/session-hygiene)"): trigger bullets ("ilag" / hermes unresponsive / `~/.hermes/sessions/` + Errno 28 merged to one generic line), workflow pre-flight path, and the "Why" Errno-28 passage.
- Kept (not in manifest): the body "Local-First Disk Budget (2026-08-12 Keeta)" section + "From ops (Everlyn/Colibri 2026-07-29)" provenance — flagged.

### web2/frontend-security-audit
- Moved all 7 case refs -> `examples/hunts/web2/frontend-security-audit/` (dawn-custom-liquid, everlyn-stored-xss, hydrogen x2, nuxaris, quilt, theta); pointers updated.
- GHOSTS removed (never existed): `references/shopify-hydrogen-dawn-xss-chain.md` (template clause + bullet), `references/klarna-xss-hunt-2026-08.md` (bullet; a klarna file lives only under examples/hunts/cdc/sovereign-ops-protocol/).

### web2/github-secret-hunt
- Moved: `injective-labs-scan-case-study.md`, `pickle-deserialization-rce-antrp.md`, `trias-lab-org-enumeration-case-study.md` -> `examples/hunts/web2/github-secret-hunt/`; 2 pointers updated.
- BODY CUT: trias-lab validation comment blocks (IP-with-context topology examples, frontend-env-file + deploy-script SSH-leak annotations) -> `examples/hunts/web2/github-secret-hunt/trias-lab-validation-notes.md`; body keeps the generic technique directives + IP_RE line + pointer. (IP_RE regex restored byte-exact after an editing incident; verified.)
- KEPT: `cicd-leak-hunting-methodology.md`, `cicd-leak-hunter-validator-keys.md`, `api-quota-theft-methodology.md`.
- SCRUB in kept `api-quota-theft-methodology.md` (manifest-ordered): `sk-zk2...2bbc`, `sk-Jvx...B47f` -> `<redacted>`; zhizengzeng.com / apikeyplus.com (incl. the "requires its own key format" result line) -> `<third-party-endpoint>`.

### web2/human-intelligence-osint
- Moved: `injective-labs-hi-case-study.md` -> `examples/hunts/web2/human-intelligence-osint/`; pointer updated. Kept `crypto-email-hunt-vectors.md` (methodology).

### web2/js-secret-scanner
- DEDUP of the 5 near-dup `nextjs-build-manifest*` refs (all variants of the same everlyn.ai 2026-07-29 buildConfig admin-route leak):
  - KEPT `nextjs-build-manifest-admin-leak.md` (generalized class doc + FP guards) and `nextjs-build-manifest-route-leak.md` (richest session evidence: 22 routes + verification checklist).
  - `git rm`'d: `nextjs-build-manifest-leak.md`, `nextjs-buildconfig-admin-leak.md`, `nextjs-buildmanifest-route-leak.md`.
- Moved: `375ai-api-enum-2026-08-12.md`, `naox-2026-08-rsc-firebase-storage-sibling.md` -> `examples/hunts/web2/js-secret-scanner/`.
- GHOST fixed: body transcript pointer `references/everlyn-ai-2026-01.md` (never existed) -> re-pointed at the kept `references/nextjs-build-manifest-route-leak.md`. Cross-skill pointers updated (genesisl1 -> examples/hunts/recon/web2-spa-recon/).

### web2/nextauth5-detection
- Moved: `everlyn-case-study.md` -> `examples/hunts/web2/nextauth5-detection/`; pointer updated.

### web2/nextjs-authn-authz-probing
- Moved: `everlyn-ai-case-study.md`, `everlyn-ai-supply-chain-case-study.md`, `everlyn-vapi-backend-idor-2026-08-13.md`, `naoris-admin-panel-case-study.md` -> `examples/hunts/web2/nextjs-authn-authz-probing/`; pointers updated. Kept `weaponized-pickle-technique.md` + merged script.

### web2/saas-supply-chain-exploitation
- Moved: `everlyn-labs-case-study.md`, `supply-chain-antrp-pickle-rce.md` -> `examples/hunts/web2/saas-supply-chain-exploitation/`; pointers updated (incl. cross-ref inside kept `deep-developer-osint-methodology.md`).
- Kept: deep-developer-osint-methodology, ml-research-dynamic-testing, ml-researcher-phishing-templates, nextjs-middleware-bypass-cve-2025-29927, personalized-wordlist-generation, refund-hijack-vector (all everlyn-validated methodology; torn -> keep, flagged).

### web2/spa-live-backend-discovery
- BODY COMPRESSED: "Why this skill exists (2026-09 ed3.xyz lesson)" origin narrative -> 2-sentence class lesson + pointer; full story verbatim -> `examples/hunts/web2/spa-live-backend-discovery/ed3-origin.md`.
- Moved: `ed3-xyz-unauth-ipfs-upload-2026-09.md` -> examples.
- GHOST fixed: References bullet pointed at `references/ed3-xyz-live-backend-discovery-2026-09.md` (never existed) -> now points at the real moved case file with a note.

### web2/wallet-auth-bypass-audit
- Moved: `messier-balance-ghost-pitfall-2026-09.md`, `messier-signatureless-login-2026-09.md` -> `examples/hunts/web2/wallet-auth-bypass-audit/`; pointers updated.

### web2/web2-api-security-patterns
- Moved: `wyze-signature-forging-2026-08-24.md` -> `examples/hunts/web2/web2-api-security-patterns/` (SKILL.md never referenced it; no pointer change needed).

### web2/web2-attack-surface-audit
- Moved 19 case refs -> `examples/hunts/web2/web2-attack-surface-audit/`: aioz-explorer-echo, u2u x5 (dhcp2p, network-stats, web2-chains, web2-redteam, web2-remote-fuzzing — manifest said x6, only 5 exist on disk), trias x2, helios x3, qtum x2, nuxaris x2, theta-token, django-explorer-trust-graph, ebridge-server, ghost-cms.
- KEPT methodology refs: fastapi-jwt-auth-redteam, fastapi-pydantic-live-fuzz, firebase-client-auth-bypass, go-http-api-audit-patterns (x2 bullets in SKILL.md pre-duplicated), report-writing-style, cdc-multi-agent-batch-workflow, mintlify-mcp-sandbox-escape (unlisted; torn -> keep, flagged).
- GHOSTS removed (never existed): `references/nextjs-images-wildcard-ssrf.md`, `references/nestjs-cors-wildcard.md`, inline `references/u2u-l1-rpc-debug-2026-08.md` clause. Cross-ref `llm-hallucinated-shell-trap.md` re-pointed to its real home `web3/defi-protocol-analysis/references/`. Stale cross-ref to S2a-attic'd `go-edge-case-audit` re-pointed to `soul/skills-attic/web3/go-edge-case-audit/references/`.
- Cross-skill pointers to files moved in this pass all updated (bcswap x2, partisia, ghost-cms).
- NOT in manifest -> left + flagged: `templates/helios-docker-manager-exploit.sh` (case-weaponized exploit template).

### osint/infrastructure-osint
- Moved: `epixnet-sweep-2026-08-17.md`, `injective-labs-case-study.md`, `partisia-foundation-case-study.md`, `trias-archive-hunt-case-study.md` -> `examples/hunts/osint/infrastructure-osint/` (dir created per the examples/<category>/<skill-name> law; the pre-existing `examples/hunts/web2/epixnet-ui-redteam/` holds the S2a whole-skill move, untouched).
- Kept 10 methodology refs; live pointers updated; changelog lines left as historical records. Cross-ref inside kept `live-p2p-node-probe.md` re-pointed to the moved epixnet sweep.

## Scrubs (S2b-1)

| File (state after pass) | Scrub |
|---|---|
| web2/github-secret-hunt/references/api-quota-theft-methodology.md (kept) | Manifest-ordered: truncated keys `sk-zk2...2bbc`, `sk-Jvx...B47f` -> `<redacted>`; reseller URLs zhizengzeng.com/apikeyplus.com -> `<third-party-endpoint>`. |
| web2/bug-bounty-agent/references/github-secret-leakage-playbook.md (kept) | Same elided key shapes (`sk-Jvx...B47f`, `Bearer sk-JvxB47f`, `sk-zk2...2bbc`) -> `<redacted>`; same reseller URLs -> `<third-party-endpoint>`. Bare vendor-name mentions in prose left (not URLs/keys). |
| web2/business-logic-invariant-hunt — moved `everlyn-umbrella-repo-pivot.md` (examples) | Elided keys `sk-zk25…` / `sk-Jvx…` -> `<redacted>`; zhizengzeng/apikeyplus -> `<third-party-endpoint>`. |
| web2/disk-space-session-safety/SKILL.md (kept) | Hermes-session specifics ("ilag", `~/.hermes/sessions/` / `/root/.hermes/sessions/` + `Errno 28` passages) genericized to "agent runtime session errors (see docs/operator/session-hygiene)"; operator-hostname specifics removed. |
| examples/hunts/web2/adversarial-exploit-chains/everlyn-pickle-chain-walkthrough.md (cut text) | Operator fleet hostname `<redacted>` in PoC output -> `<redacted>`. |

New full-length live keys found: **NONE**. All key-shaped hits in scope were
previously-reported elided/truncated forms (sk-zk2*/sk-Jvx* family) or regex
patterns — the elided forms were redacted as listed above; test-suite grep for
`sk-[A-Za-z0-9]{20,}` / thk_live / .ts.net / vm-0-3 over the three categories
is clean (exit 1, zero hits).

## Ghost refs removed in this pass (files never existed in git history)

1. cloudflare-waf-graphql-recon: `references/upwork-cf-graphql-2026-08-19.md`
2. frontend-security-audit: `references/shopify-hydrogen-dawn-xss-chain.md` (2 mentions)
3. frontend-security-audit: `references/klarna-xss-hunt-2026-08.md`
4. github-secret-hunt body: `references/everlyn-ai-2026-01.md` (re-pointed to kept session ref)
5. spa-live-backend-discovery: `references/ed3-xyz-live-backend-discovery-2026-09.md`
6. web2-attack-surface-audit: `references/nextjs-images-wildcard-ssrf.md`
7. web2-attack-surface-audit: `references/nestjs-cors-wildcard.md`
8. web2-attack-surface-audit: inline `references/u2u-l1-rpc-debug-2026-08.md`

Pre-existing ghosts left as-is (out of scope, for the record): bug-bounty-agent
`bridge-api/bridge-architecture/bridge-contracts/custodial-wallets/eth-call-api/
foundry-testing/smart-contract-testing` pointers; `unionlabs-ibc-bridge-audit-patterns.md`
name-mismatch in adversarial-bug-bounty-hunting; `nextauth-authz-probe.md` /
`vercel-nextjs-spa-takeover.md` cross-refs in kept methodology files;
mcp-security-audit ghost refs (skill outside this pass's list).

## Left in place while torn (kept + flagged to supervisor)

- adversarial-bug-bounty-hunting: `references/` still holds ~54 dated case refs
  (everlyn/keeta/gimo/noise/naox/naoris/u2u/helios/shopify/skate-org/viction...)
  plus 3 "ZERO-DAY FINDINGS" body sections — the S2b-1 manifest listed only the
  ZERO-DAY SNIFF cut for this skill.
- adversarial-persona-operations: `references/everlyn-intel.md` (target intel).
- web2-attack-surface-audit: `templates/helios-docker-manager-exploit.sh`
  (case-weaponized template).
- predator-recon: `references/paxos-gas-exploits.md` (classified keep by manifest).
- disk-space-session-safety: body "Local-First Disk Budget (2026-08-12 Keeta)" section.
- saas-supply-chain-exploitation: 6 everlyn-validated methodology refs.
- adversarial-exploit-chains: `the operator-direct-execution.md` (operator behavior
  protocol, not case-not-methodology in the hunting sense).

---

# FOLLOW-UP PASS (same day, S2b-1 residue completion)

Four operator-ordered items. Same laws. Tests re-run green (20 passed).

## F1. P0 — Wyze secret scrub (web2-api-security-patterns + scope re-grep)

The full-length secrets lived in the moved case file (examples), plus a
truncated shape in the kept SKILL.md pattern table:

| File (state) | Scrub |
|---|---|
| examples/hunts/web2/web2-api-security-patterns/wyze-signature-forging-2026-08-24.md | 3x 32-char HMAC-MD5 signing secrets (`gbJojEB…`, `obb2Zn…`, `5Z1Bg7…`) -> `<redacted>`; base64 OAuth clientSecret `atob("WMNpD2qNPC6id5zz9PcLJmGRQKAGUA")` -> `atob("<redacted>")`. Test-vector MD5 output and the public Shopify `client_id` kept (not secrets). |
| web2-api-security-patterns/SKILL.md (kept) | Truncated example `atob("WMNpD2qNPC...")` -> `atob("<redacted-oauth-client-secret>")` (placeholder style per order). |

Scope-wide re-grep for the same shapes found the secrets surviving in exactly
one OUT-OF-SCOPE file the cull may not touch:
**`soul/skills-attic/cdc/web-audit-report-delivery/references/wyze-poc2-forge.md`
(lines 14-16, 29) still carries all 3 live Wyze HMAC signing secrets.**
FLAGGED to the supervisor — attic/cdc belongs to the S2a/web3 agent's scope.

## F2. adversarial-bug-bounty-hunting manifest-gap cleanup

- Moved 46 dated/target case refs -> `examples/hunts/web2/adversarial-bug-bounty-hunting/`
  (375ai x2, noise-xyz x2 api + x2, camp-network, everlyn x4, naox/naoris x4
  incl. human-disclosure, flyingtulip, gimo, helios x2, immutable-zkevm,
  jvm-stackoverflow-proof-tencentos, keeta x14, kinto, modulo x2,
  nyantai, shopify-hydrogen-open-redirect, skate-org, u2u-hunt,
  unionlabs-re-audit, viction).
- Cut the 3 "ZERO-DAY FINDINGS" body sections (naox/naoris Firebase BaaS
  takeover, everlyn.ai 2026-08-04, Shopify ecosystem WAVE 1-4) verbatim ->
  `examples/hunts/web2/adversarial-bug-bounty-hunting/zero-day-findings-notes.md`
  + pointer line. SKILL.md 1043 -> 798 lines.
- KEPT methodology refs (23): admin-dashboard-ssr-exposure-bug-bounty,
  anti-hyperbole, bug-bounty-evidence-format, cdc-thinking, chain-synthesis,
  ci-cd-leak-hunting, everlyn-report-template (generic human-tone report
  template; "everlyn" only in the filename), evm-token-contract-recon,
  key-acquisition, math-brute-force, ml-research-pickle-deserialization,
  ml-research-static-taint-audit (Everlyn-1 pattern technique),
  nextjs-middleware-bypass-case-study (public CVE), nextjs-server-actions-exposure,
  poc-template.rs, recon-checklist, rsc-payload-extraction,
  solana-anchor-program-recon, target-matrix, union-labs-ibc-audit-patterns
  (CosmWasm IBC pattern library), web3-exploitation-mastery-curriculum,
  web3-integration-analysis, web3-web2-hunt-pitfalls.
- 13 body pointers re-pointed to examples; pre-existing name-mismatch ghost
  `unionlabs-ibc-bridge-audit-patterns.md` fixed to the real
  `union-labs-ibc-audit-patterns.md`.
- SCRUB during move (NEW KEY FLAG — see F5): full 64-hex `seed_hex` of the
  funded Keeta hemat wallet redacted in keeta-local-hemat-wallet-faucet AND
  keeta-funded-wallet-live-publish; 375.ai committed Solana secret-key byte
  arrays (`[190,79,…]`, `[89,135,…]`) -> `<redacted>` in both 375ai refs and
  in the pass-1 cut file zero-day-sniff-notes.md. Base58 public keys kept.

## F3. Small residue moves (all case material per the cull law)

| From -> To | Note |
|---|---|
| adversarial-persona-operations/references/everlyn-intel.md -> examples/hunts/web2/adversarial-persona-operations/ | Target-intel dossier; REFERENCES bullet updated. |
| web2-attack-surface-audit/templates/helios-docker-manager-exploit.sh -> examples/hunts/web2/web2-attack-surface-audit/ | Case-weaponized template; body bullet updated. |
| predator-recon/references/paxos-gas-exploits.md -> examples/hunts/recon/predator-recon/ | Paxos 2026-07-19 findings; CASE STUDIES bullet updated. |
| disk-space-session-safety body "Local-First Disk Budget (2026-08-12 Keeta)" -> examples/hunts/web2/disk-space-session-safety/keeta-local-first-disk-budget-section.md | Kept a generic 2-line disk-budget note + pointer; cut text verbatim. |
| adversarial-exploit-chains/references/the operator-direct-execution.md -> docs/operator/direct-execution-protocol.md | Operator-behavior protocol; extraction note prepended. The SKILL.md never pointed at the file (body has its own "Direct Execution Protocol (the operator-Specific)" section, left intact as class-core text). |

## F4. Dangling/stale pointer repairs found by the post-pass resolver

- js-secret-scanner SKILL.md: naox firebase-takeover cross-ref -> examples path.
- web2-admin-takeover SKILL.md: jwt-bcrypt workflow cross-ref -> `web2/js-secret-scanner/references/…` (legacy `security/` path).
- abbh admin-dashboard-ssr-exposure-bug-bounty.md + exploit-chains saas-platform-recon.md: `references/nextauth-authz-probe.md` -> `examples/hunts/web2/nextauth-authz-probe/SKILL.md` (S2a whole-skill move); nextjs-rsc-recon -> js-secret-scanner copy; admin-dashboard-ssr-exposure -> osint copy.
- osint admin-dashboard-ssr-exposure.md: nextauth-authz-probe -> examples SKILL.md.
- osint nextjs-chunk-static-analysis.md: vercel-nextjs-spa-takeover -> `web2/bug-bounty-agent/references/…`.
- Unfixable pre-existing ghosts left (never existed anywhere): bug-bounty-agent
  bridge-api/bridge-architecture/bridge-contracts/custodial-wallets/eth-call-api/
  foundry-testing/smart-contract-testing; mcp-security-audit mcp-* refs
  (skill outside this pass's list).

## F5. NEW SECRET FLAG (loud)

**Full-length live key found during the follow-up scrub: the funded Keeta
hemat wallet's 64-hex `seed_hex` (`edfbd84e…c1886`)** — an ed25519 seed that
was proven signable in the 2026-08-12 Keeta sessions (live publish on
mainnet/testnet universal). It appeared in TWO files
(`keeta-local-hemat-wallet-faucet-2026-08-12.md` line 50,
`keeta-funded-wallet-live-publish-2026-08-12.md` line 5) and both are now
`<redacted>`. Repo-wide grep confirms zero remaining copies of the seed.
**ROTATION ADVISED: the wallet is a low-value test faucet wallet, but the key
predates this commit in git history — treat as live; rotation is the
operator's job.** Also redacted: 375.ai's committed devnet keypair byte arrays
(elided forms) in 3 refs + the pass-1 zero-day-sniff-notes.md.

## Follow-up totals

| Metric | Count |
|---|---|
| Files moved (git mv) | 51 (46 abbh + 5 residue) |
| Body sections cut | 4 (3 ZERO-DAY FINDINGS + Keeta disk-budget) |
| Scrub actions | 8 (wyze examples file, SKILL.md placeholder, 2 keeta seed files, 2 375ai files, sniff-notes, plus shape-verified clean) |
| Stale/dangling pointers repaired | 19 |
| NEW full-length live keys found | **1** (Keeta seed_hex — redacted + flagged, rotation advised) |
| Out-of-scope secret residue flagged | 1 (attic wyze-poc2-forge.md — 3 live Wyze HMAC secrets) |
| Tests | `test_skills.py` + `test_install.py`: **20 passed** |
