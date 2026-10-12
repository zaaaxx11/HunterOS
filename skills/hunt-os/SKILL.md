---
name: hunt-os
description: HUNT-OS hunting router - RoE-first security, bug-bounty, and audit doctrine. Load for any authorized assessment hunt.
allowed-tools: Read, Grep, Glob, Bash
---

# HUNT-OS — hunting skills router

RoE-first doctrine (see `${CLAUDE_PLUGIN_ROOT}/always-on-rules.md`, injected at
SessionStart). This router is the map; the corpus behind it is the HunterOS
skills tree (5 categories, 50 skills). Never bulk-load: pick the category that
matches the target, then load ONE skill at a time, only what the lane needs.

Scope note: this skill covers HunterOS lanes (architect, red-teamer,
fuzz-engineer, chainer, lane-runner, adversary, verifier). Lane/agent details
live in this plugin's `agents/` directory.

## THE SESSION LOOP

```text
Authorize → Observe → Model → Minimal reversible test → Verify → Report
```

## CATEGORY INDEX (skill name → when to load it)

### recon/ — targeting and attack-surface discovery
- predator-recon — industrial-scale recon pipeline
- web2-spa-recon — SPA-decoy Next/Nuxt/Vite, real-API extraction from JS chunks
- web2-admin-takeover — automated admin takeover via JS bundle analysis
- cloudflare-waf-graphql-recon — CF-challenge bypass + GraphQL single-endpoint

### web2/ — web application and API attack
- web2-attack-surface-audit — full web2 attack-surface audit (architect default)
- adversarial-exploit-chains — exploit chain construction (chainer default)
- bug-bounty-agent — bug bounty agent workflow
- business-logic-invariant-hunt — payment/refund/IDOR/race invariants
- nextjs-authn-authz-probing — Next.js authn/authz probing
- nextauth5-detection — NextAuth v5 deployments and version weaknesses
- spa-live-backend-discovery — CDP-driven real API base discovery
- frontend-security-audit — client-side audit (XSS and friends)
- js-secret-scanner — secrets in shipped JS bundles
- github-secret-hunt — leaked secrets across GitHub
- saas-supply-chain-exploitation — SaaS integrations and third-party trust
- wallet-auth-bypass-audit — wallet-based auth bypass
- adversarial-bug-bounty-hunting — adversarial posture for bounty programs
- mcp-security-audit — MCP server audit (path traversal, ReDoS)
- web-blocked-page-recovery — 403/429/paywall/bot-wall recovery
- web2-api-security-patterns — HMAC/OAuth/CORS API patterns
- disk-space-session-safety — disk/session safety for long runs

### web3/ — blockchain and protocol audit
- black-swan-engine — 19 universal EVM vulnerability laws
- evm-contract-audit — EVM audit against hack patterns
- smart-contract-exploit-pocs — exploit PoC library
- token-transfer-audit — token transfer paths and hooks
- defi-protocol-analysis — DeFi economic/mechanism analysis
- defi-audit-verification — verify audit claims vs source
- lending-protocol-fork-audit — lending-fork playbook
- on-chain-exploit-workflow — end-to-end on-chain exploit workflow
- on-chain-forensics — post-incident forensics
- cross-contract-chain-builder — cross-contract chains (chainer default)
- custom-chain-rpc-exploit, blockchain-node-audit,
  blockchain-rpc-attack-surface-audit, rust-p2p-edge-case-audit,
  l2-rollup-audit, erc4337-bundler-audit, cdc-blockchain-audit,
  rate-limited-chain-recon — chain/RPC/node specialties

### cdc/ — multi-agent hunt methodology
- multi-target-cdc-audit — batched CDC audit, multi-target ecosystems
- cdc-web-app-bug-bounty — CDC web app bounty, 4-agent orchestration
- cdc-lending-audit-foundry-poc — CDC lending-fork audit with Foundry PoC
- cdc-device-audit — device/IoT local web interfaces and firmware
- sovereign-ops-protocol — persistence contract for long hunts

### verification/ — evidence discipline
- audit-verification-methodology — verify audit claims vs source (verifier)
- poc-reverification — re-verify saved PoCs vs live target (verifier)
- dynamic-fuzz-testing — fuzz/property-based testing (fuzz-engineer default)
- systematic-debugging — 4-phase root-cause debugging (fuzz-engineer default)
- test-driven-development — RED-GREEN-REFACTOR discipline
- requesting-code-review — pre-commit review, security scan, quality gates

## LANE LOADOUTS (one line per dispatched lane)
- Architect ← web2-attack-surface-audit
- Red-Teamer ← web2-admin-takeover, nextjs-authn-authz-probing,
  business-logic-invariant-hunt
- Fuzz-Engineer ← dynamic-fuzz-testing, systematic-debugging
- Chainer ← adversarial-exploit-chains, cross-contract-chain-builder
- Verifier (review role, NOT a fifth lane) ← audit-verification-methodology,
  poc-reverification

## CLAIM DISCIPLINE

Strong claims (PROVEN, EXPLOITABLE, "admin takeover") must name their ledger
record (e.g. PROVEN[F-3]) or the Stop-hook claim gate vetoes the turn. A PoC
must be EXECUTED (`hunt poc run`), existence is not execution.
