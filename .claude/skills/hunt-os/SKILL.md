---
name: hunt-os
description: HUNT-OS hunting router — 51 security skills across recon, web2, web3, CDC, and verification. Load this first for any authorized assessment hunt.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Agent, WebSearch, WebFetch
---

# HUNT-OS — Native Claude Code Hunting Router

RoE-first security doctrine. This router indexes 51 skills across 5 categories.
**Never bulk-load. Pick the category matching your target, then load ONE skill at a time.**

## RULES OF ENGAGEMENT (Always Active)

Before any observation or test, confirm an owner-approved Rules of Engagement (RoE):
in-scope assets and accounts, dates, permitted methods, data handling, limits,
contacts, and stop conditions. If any part is missing or ambiguous, **default-deny**
and ask the authorized contact. The RoE is the maximum permitted activity. Do not
broaden scope, access unrelated data, use credentials found incidentally, or perform
disruptive, deceptive, evasive, persistent, or irreversible actions.

## THE SESSION LOOP

```text
Authorize → Observe → Model → Minimal reversible test → Verify → Report
```

Observe before acting. Record facts, assumptions, unknowns, expected impact, and an
abort condition. Use the least invasive test, preferably read-only, dry-run, synthetic,
local, and reversible. Verify independently against a baseline.

## CATEGORY INDEX

### 🔍 recon/ — Targeting & Attack-Surface Discovery (4 skills)
| Skill | When to Load |
|-------|-------------|
| `hunt-recon-predator-recon` | Industrial-scale recon pipeline (subdomain→URL→JS→vuln→deep) |
| `hunt-recon-web2-spa-recon` | SPA-decoy Next/Nuxt/Vite, real-API extraction from JS chunks |
| `hunt-recon-web2-admin-takeover` | Automated admin takeover via JS bundle analysis |
| `hunt-recon-cloudflare-waf-graphql-recon` | CF-challenge bypass + GraphQL single-endpoint recon |

### 🌐 web2/ — Web Application & API Attack (17 skills)
| Skill | When to Load |
|-------|-------------|
| `hunt-web2-web2-attack-surface-audit` | Full web2 attack-surface audit (architect default) |
| `hunt-web2-adversarial-exploit-chains` | Exploit chain construction (chainer default) |
| `hunt-web2-bug-bounty-agent` | Bug bounty agent workflow |
| `hunt-web2-business-logic-invariant-hunt` | Payment/refund/IDOR/race invariants |
| `hunt-web2-nextjs-authn-authz-probing` | Next.js authn/authz probing |
| `hunt-web2-nextauth5-detection` | NextAuth v5 deployments and version weaknesses |
| `hunt-web2-spa-live-backend-discovery` | CDP-driven real API base discovery |
| `hunt-web2-frontend-security-audit` | Client-side audit (XSS and friends) |
| `hunt-web2-js-secret-scanner` | Secrets in shipped JS bundles |
| `hunt-web2-github-secret-hunt` | Leaked secrets across GitHub |
| `hunt-web2-saas-supply-chain-exploitation` | SaaS integrations and third-party trust |
| `hunt-web2-wallet-auth-bypass-audit` | Wallet-based auth bypass |
| `hunt-web2-adversarial-bug-bounty-hunting` | Adversarial posture for bounty programs |
| `hunt-web2-mcp-security-audit` | MCP server audit (path traversal, ReDoS) |
| `hunt-web2-web-blocked-page-recovery` | 403/429/paywall/bot-wall recovery |
| `hunt-web2-web2-api-security-patterns` | HMAC/OAuth/CORS API patterns |
| `hunt-web2-disk-space-session-safety` | Disk/session safety for long runs |

### ⛓️ web3/ — Blockchain & Protocol Audit (19 skills)
| Skill | When to Load |
|-------|-------------|
| `hunt-web3-black-swan-engine` | 19 universal EVM vulnerability laws (CDC backbone) |
| `hunt-web3-evm-contract-audit` | EVM audit against hack patterns |
| `hunt-web3-smart-contract-exploit-pocs` | Exploit PoC library |
| `hunt-web3-token-transfer-audit` | Token transfer paths and hooks |
| `hunt-web3-defi-protocol-analysis` | DeFi economic/mechanism analysis |
| `hunt-web3-defi-audit-verification` | Verify audit claims vs source |
| `hunt-web3-lending-protocol-fork-audit` | Lending-fork playbook |
| `hunt-web3-on-chain-exploit-workflow` | End-to-end on-chain exploit workflow |
| `hunt-web3-on-chain-forensics` | Post-incident forensics |
| `hunt-web3-cross-contract-chain-builder` | Cross-contract chains (chainer default) |
| `hunt-web3-crypto-attack-atlas` | 18 attack families routing atlas |
| `hunt-web3-custom-chain-rpc-exploit` | RPC attack surface of custom chains |
| `hunt-web3-blockchain-node-audit` | Node implementation audit |
| `hunt-web3-blockchain-rpc-attack-surface-audit` | RPC attack-surface audit |
| `hunt-web3-rust-p2p-edge-case-audit` | Rust P2P edge-case audit |
| `hunt-web3-l2-rollup-audit` | L2 rollup audit |
| `hunt-web3-erc4337-bundler-audit` | ERC-4337 bundler audit |
| `hunt-web3-cdc-blockchain-audit` | CDC blockchain audit loop |
| `hunt-web3-rate-limited-chain-recon` | Rate-limited chain reconnaissance |

### 🧬 cdc/ — Multi-Agent CDC Hunt Methodology (5 skills)
| Skill | When to Load |
|-------|-------------|
| `hunt-cdc-multi-target-cdc-audit` | Batched CDC audit, multi-target ecosystems |
| `hunt-cdc-cdc-web-app-bug-bounty` | CDC web app bounty, 4-agent orchestration |
| `hunt-cdc-cdc-lending-audit-foundry-poc` | CDC lending-fork audit with Foundry PoC |
| `hunt-cdc-cdc-device-audit` | Device/IoT local web interfaces and firmware |
| `hunt-cdc-sovereign-ops-protocol` | Persistence contract for long hunts |

### ✅ verification/ — Evidence Discipline (6 skills)
| Skill | When to Load |
|-------|-------------|
| `hunt-verification-audit-verification-methodology` | Verify audit claims vs source (verifier) |
| `hunt-verification-poc-reverification` | Re-verify saved PoCs vs live target (verifier) |
| `hunt-verification-dynamic-fuzz-testing` | Fuzz/property-based testing (fuzz-engineer default) |
| `hunt-verification-systematic-debugging` | 4-phase root-cause debugging (fuzz-engineer default) |
| `hunt-verification-test-driven-development` | RED-GREEN-REFACTOR discipline |
| `hunt-verification-requesting-code-review` | Pre-commit review, security scan, quality gates |

## LANE LOADOUTS

- **Architect** ← `hunt-web2-web2-attack-surface-audit`
- **Red-Teamer** ← `hunt-recon-web2-admin-takeover`, `hunt-web2-nextjs-authn-authz-probing`, `hunt-web2-business-logic-invariant-hunt`
- **Fuzz-Engineer** ← `hunt-verification-dynamic-fuzz-testing`, `hunt-verification-systematic-debugging`
- **Chainer** ← `hunt-web2-adversarial-exploit-chains`, `hunt-web3-cross-contract-chain-builder`
- **Verifier** (review role) ← `hunt-verification-audit-verification-methodology`, `hunt-verification-poc-reverification`

## AGENTS (available via Agent tool)

| Agent | Role |
|-------|------|
| `hunt-architect` | Attack-surface mapping, trust graph |
| `hunt-red-teamer` | Auth/authz testing, injection, invariant violation |
| `hunt-fuzz-engineer` | Edge cases, constraints, crash vectors |
| `hunt-chainer` | Exploit chain construction |
| `hunt-verifier` | Evidence checking, claim validation |
| `hunt-adversary` | Adversarial review |
| `hunt-lane-runner` | Lane dispatcher/coordinator |

## CLAIM DISCIPLINE

- Strong claims (PROVEN, EXPLOITABLE) must name their evidence
- PoC must be EXECUTED, not just theorized
- Findings require ≥1 bound evidence artifact
- File:line for every claim
- Distinguish: VERIFIED (code seen) vs THEORETICAL (logic only) vs FALSE (disproven)

## NATIVE TOOL MAPPING

Without CLI/MCP, all hunting uses native Claude Code tools:

| Task | Native Tool |
|------|------------|
| Code audit | Read, Grep, Glob |
| Live recon | Bash (curl, subfinder, httpx, etc.) |
| JS bundle analysis | Bash (grep, curl, jq) |
| RPC calls | Bash (curl -X POST with JSON-RPC) |
| Smart contract | Bash (cast, forge) |
| Report writing | Write |
| Multi-agent | Agent (spawn lane agents) |
| Web search | WebSearch, WebFetch |