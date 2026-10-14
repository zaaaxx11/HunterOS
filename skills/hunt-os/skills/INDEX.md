# skills/INDEX.md — the skills router

The engine reads this file FIRST. It never bulk-loads the skills tree: it
picks the category that matches the target, then loads specific skills on
demand — one skill at a time, only what the lane needs. `<name>` resolves to
`app/src/huntos/_data/idea/skills/<category>/<name>/SKILL.md` in the git tree
(`hunt-os/skills/<category>/<name>/SKILL.md` in an installed layer); how a
load resolves per harness is in the LOADING DOCTRINE at the bottom.

Five categories: `recon/`, `web2/`, `web3/`, `cdc/`, `verification/`.

## recon/ — targeting and attack-surface discovery

- predator-recon — industrial-scale recon arsenal (wadgamer10 pipeline x yaklang)
- web2-spa-recon — SPA-decoy Next/Nuxt/Vite: catch-all traps, real-API extraction from JS chunks, Firebase triage (Colb/Nuxaris/BC Swap/Alltoscan/Bityuan/VersatizeCoin cases)
- web2-admin-takeover — automated admin takeover via JS bundle analysis
- cloudflare-waf-graphql-recon — bypass Cf-Mitigated challenge + GraphQL single-endpoint

## web2/ — web application and API attack

- web2-attack-surface-audit — full web2 attack-surface audit
- adversarial-exploit-chains — adversarial exploit chain construction
- bug-bounty-agent — bug bounty agent workflow
- disk-space-session-safety — disk-space and session safety for long runs
- web2-api-security-patterns — HMAC/OAuth/CORS/Shopify API security patterns
- nextjs-authn-authz-probing — Next.js authn/authz probing
- nextauth5-detection — detect NextAuth v5 deployments and version-specific weaknesses
- spa-live-backend-discovery — CDP-driven discovery of the real API base behind an SPA
- frontend-security-audit — client-side security audit (XSS and friends)
- js-secret-scanner — hunt secrets in shipped JavaScript bundles
- github-secret-hunt — hunt leaked secrets across GitHub
- saas-supply-chain-exploitation — exploit SaaS integrations and third-party trust
- wallet-auth-bypass-audit — audit wallet-based auth flows for bypass
- business-logic-invariant-hunt — payment/refund/IDOR/race invariant attacks
- adversarial-bug-bounty-hunting — adversarial posture for bounty programs
- mcp-security-audit — MCP server audit (path traversal %2e, ReDoS)
- web-blocked-page-recovery — 403/429/paywall/bot-wall recovery playbook

## web3/ — blockchain and protocol audit

- black-swan-engine — 19 universal laws of EVM vulnerability (CDC backbone)
- evm-contract-audit — EVM contract audit against 875 hack patterns
- smart-contract-exploit-pocs — exploit PoC library and construction
- token-transfer-audit — audit token transfer paths and hooks
- defi-protocol-analysis — DeFi protocol economic/mechanism analysis
- defi-audit-verification — verify DeFi audit claims vs source
- lending-protocol-fork-audit — lending-fork-specific audit playbook
- on-chain-exploit-workflow — end-to-end on-chain exploit workflow
- on-chain-forensics — post-incident on-chain forensics
- cross-contract-chain-builder — build cross-contract exploit chains
- custom-chain-rpc-exploit — RPC attack surface of custom chains
- blockchain-node-audit — node implementation audit
- blockchain-rpc-attack-surface-audit — RPC attack-surface audit
- rust-p2p-edge-case-audit — Rust P2P edge-case audit
- l2-rollup-audit — L2 rollup audit
- erc4337-bundler-audit — ERC-4337 bundler audit
- cdc-blockchain-audit — CDC blockchain audit loop
- rate-limited-chain-recon — rate-limited chain reconnaissance

## cdc/ — CDC multi-agent hunt methodology

- multi-target-cdc-audit — batched sequential CDC audit for multi-target ecosystems (GitHub orgs + live endpoints), per-target scan reports
- cdc-web-app-bug-bounty — CDC web app bug bounty hunting with 4-agent orchestration (Arkose/Chia/Wyze/EDBank case refs)
- cdc-lending-audit-foundry-poc — CDC 4-agent lending-fork audit with Foundry PoC testing
- cdc-device-audit — CDC audit for device/IoT local web interfaces and firmware
- sovereign-ops-protocol — persistence contract for long hunts (10-round floor, cross-steering) plus reporting style protocol

## verification/ — evidence discipline and engineering rigor

- audit-verification-methodology — verify audit claims against actual source code before repeating them
- poc-reverification — re-verify saved PoCs against the live target before building on them (stale indicators, old cookies, patched chains)
- dynamic-fuzz-testing — dynamic fuzz and property-based testing for Python/ML codebases
- systematic-debugging — 4-phase root-cause debugging: understand bugs before fixing
- test-driven-development — TDD discipline: RED-GREEN-REFACTOR, tests before code
- requesting-code-review — pre-commit review: security scan, quality gates, auto-fix

## LOADING DOCTRINE

1. The engine reads THIS file first. It never bulk-loads the skills tree.
2. On demand it loads ONE skill at a time — the name must appear in this index
   or the reference is broken (CI enforces this for every `skill_view` in
   `IDEA.md`). How a single-skill load resolves is harness-dependent:
   - Hermes: `skill_view(name='<name>')` resolves to
     `app/src/huntos/_data/idea/skills/<category>/<name>/SKILL.md`
   - Claude Code / ZCode: native skill discovery via frontmatter (`name:` +
     `description:`). Router mode: the entry skill is `hunt-os` and skills are
     read from its nested `skills/` tree on demand. Native mode: they appear
     as `hunt-<category>-<name>`.
   - generic harness: read the SKILL.md file directly by path
     (`app/src/huntos/_data/idea/skills/<category>/<name>/SKILL.md` in the
     git tree, `hunt-os/skills/<category>/<name>/SKILL.md` when installed).
3. Lane loadouts — one line per DISPATCHED lane; these are exactly the four
   lanes the conductor machine dispatches (`db.CONDUCTOR_LANES`):
   - Architect (`architect`) ← surface/web2-attack-surface-audit
   - Red-Teamer (`red_teamer`) ← web2-admin-takeover, nextjs-authn-authz-probing, business-logic-invariant-hunt
   - Fuzz-Engineer (`fuzz_engineer`) ← dynamic-fuzz-testing, systematic-debugging
   - Chainer (`chainer`) ← adversarial-exploit-chains, cross-contract-chain-builder
   NOT a dispatched lane: Verifier ← audit-verification-methodology,
   poc-reverification. The Verifier is a review role, invoked on evidence
   when a claim must be verified — it is pulled in when the evidence
   requires it, never spawned as a fifth lane.
4. A skill never bypasses the gate: see `skills/README.md` (this directory)
   for the contract every landed skill is held to.
