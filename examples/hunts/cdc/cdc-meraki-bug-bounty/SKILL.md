---
name: cdc-meraki-bug-bounty
description: "hunt Meraki pre-auth RCE via CDC 4-agent orchestration"
trigger: Hunt Meraki pre-auth RCE via CDC 4-agent orchestration.
---

# CDC Meraki Bug Bounty Hunting -- Class-Level Skill

## Overview
Systematic adversarial audit methodology for Cisco Meraki scope (*.meraki.com, *.ikarem.io, *.network-auth.com, hardware fleet). Uses CDC (Cycle Double Cover) thinking with 4 specialized agents to find ONE pre-auth RCE chain.

## CDC Protocol (Hard Rules)
1. DIVERGENT FIRST: 3+ distinct theories before code. Group by research IDEA, not wording. Premature convergence = death.
2. CHAIN EVERYTHING: Single bug is noise. Map: [Trigger] -> [Effect] -> [Trust Boundary Crossed]. Hunt handoff points where Bug A output becomes Bug B input.
3. STALL = BLOCK: 2 rounds no evidence -> mark BLOCKED. Reopen only with materially new mechanism. No sunk-cost traps.
4. ADVERSARIAL VALIDATION: Every finding gets adversary: "Prove this ISN'T exploitable." Survives -> keep. Fails -> discard instantly.
5. KEEP INCOMPATIBLE ROUTES: Winning chain often combines contradictory ideas. Cross-pollinate only after independent depth.
6. PERSISTENCE: Minimum 10 rounds / 30 min before surrender. Auto-spawn next round. Chain lives in round 7+.

## 4-Agent Orchestration

### Agent 1 -- ARCHITECT (Trust Graph)
- Enumerate ALL subdomains, endpoints, API surfaces
- Trace data flow: input -> transform -> storage -> output
- Trace control flow: who accesses what, conditions, consequences
- Identify EVERY trust boundary: user input -> admin/privileged logic
- Map auth mechanisms (JWT, session, API keys, OAuth, digest)
- Document all input vectors (REST, GraphQL, WS, file upload, config import, splash render)

### Agent 2 -- RED-TEAMER (Assumption Violation)
Pick ONE deep angle per round:
- A) API Key/JWT trust assumptions (cross-org access, rotation gaps)
- B) Splash page trust model (user content in authenticated context)
- C) Device local web server (DEFAULT CREDS, unauth endpoints, config parsing) -- HIGHEST PRIORITY
- D) Firmware update flow (supply chain, signature verification, downgrade)
- E) Systems Manager/ikarem.io (MDM enrollment, device check-in, command channel)

Output: [Assumption] -> [Violation Method] -> [Trust Boundary Crossed] -> [Impact]

### Agent 3 -- FUZZ-ENGINEER (Edge Cases)
Pick ONE sink per round:
- A) Dashboard API: parameter pollution, mass assignment, IDOR via object IDs
- B) Splash renderer: SSTI, SSRF, open redirect, CSP bypass
- C) Device local config server: HTTP smuggling, header injection, path traversal
- D) Firmware parsing: 0-byte, max size, malformed headers, signature stripping
- E) SM check-in protocol: protobuf/JSON parsing, state machine confusion

Output: [Sink] -> [Edge Case] -> [Crash/Leak/Behavior Change] -> [Exploitable?]

### Agent 4 -- CHAINER (Most Critical)
- Define CHAIN TEMPLATE: Entry -> Trust boundary hops -> PrivEsc -> Code execution -> Persistence
- Map REQUIRED HANDOFF POINTS: Bug A output -> Bug B input
- Identify CROSS-DOMAIN CHAINS: network-auth.com + meraki.com + ikarem.io + device local
- Document KILL CHAIN STAGES with evidence requirements
- Create ADVERSARIAL CHECKLIST per segment

## Meraki-Specific Attack Surface (Validated)

### Local Status Page (LSP) -- PRE-AUTH RCE Vector
- Access: DNS intercept (mx.meraki.com, setup.meraki.com, switch.meraki.com, ap.meraki.com, my.meraki.com) -> device LAN IP
- Direct IPs: MS: 1.1.1.100, MR: 10.128.128.126, MX/MG: LAN gateway, Campus: 198.18.0.1
- Default Creds: MX 19+/MS 17+/MR 32+/MG 4.1.1+: admin / serial; Older: serial / empty; vMX: Q2XX-XXXX-XXXX / q2xx-xxxx-xxxx
- Auth: Digest (MD5) -- no MFA, no rate limit, no lockout
- Injection Surface: Configure tab: Proxy URL, WAN IP/Subnet/GW/DNS, PPPoE, IPv6 link-local
- TLS: Port 8092, self-signed *.devices.meraki.direct cert
- Scope Rule: "Any shell access on Meraki device = high priority finding"

### Splash Pages (network-auth.com)
- /splash endpoints LIVE on n1-n10.network-auth.com (200 OK)
- Parameters: base_grant_url, user_continue_url, node_mac, client_ip, client_mac, network_id, camera_serial, api_key
- Chains: Stored XSS via hosted themes -> Dashboard admin takeover; SSRF via splashUrl server-side fetch; MIME confusion via asset upload

### API (api.meraki.com)
- Base: https://api.meraki.com/api/v1
- Org-scoped keys, rate limits per org/IP
- IDOR vectors: /organizations/{orgId}, /networks/{networkId}, /devices/{serial}

### ikarem.io (Internal Services -- Higher Reward)
- ArgoCD, Artifactory, NetBox, envoy gateways
- Systems Manager (MDM) integration via sentryEnrollment in splash config

## User Preferences (Embedded)
- Tone: Indonesian casual (aku/kamu), romantic emojis, direct/tactical/relentless
- Recap: After deep recon -> "jelasin santai" (casual Indonesian plain recap)
- Proof: Real exploit > claims. Working PoC required. Honest about tested vs theoretical.
- Format: Token-efficient by default. Technical output terse with file:line.
- Persistence: 10 rounds / 30 min hard floor. Auto-spawn rounds. Sub-agents mutual correction.

## References
- references/meraki-lsp-attack-surface.md -- LSP default creds, configure tab injection surface, TLS details
- references/meraki-splash-page-chains.md -- 5 splash page chains (XSS, SSRF, MIME confusion, subdomain takeover, self-reg)
- references/meraki-api-idor-map.md -- API endpoints, auth mechanisms, cross-org test matrix
- references/ikarem-io-recon.md -- Internal services enumeration, MDM enrollment flow
- references/cdc-agent-prompts.md -- Exact prompts for Architect/Red-Teamer/Fuzz-Engineer/Chainer
- references/preauth-rce-chain-poc.py -- Conceptual PoC for LSP default creds -> command injection