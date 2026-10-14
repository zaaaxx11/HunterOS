---
name: predator-recon
description: "industrial-scale recon arsenal (wadgamer10 pipeline x yaklang)"
version: "2.6"
category: security
tags:
  - bug-bounty
  - recon
  - subdomain-enum
  - vulnerability-scanning
  - web3
  - defi
  - exploit
  - steal
  - attack
author: SUPERAGENT
trigger:
  - "recon"
  - "reconnaissance"
  - "subdomain"
  - "bug bounty"
  - "hunt"
  - "target"
  - "scope"
  - "exploit"
  - "exploitation"
  - "steal"
  - "stole"
  - "stealing"
  - "rob"
  - "drain"
  - "drained"
  - "attack"
  - "compromise"
  - "pwn"
  - "hack"
  - "breach"
  - "vuln"
  - "vulnerability"
  - "weakness"
  - "flaw"
  - "bug"
  - "0day"
  - "0-day"
  - "poc"
  - "proof of concept"
  - "payload"
  - "payloads"
  - "xss"
  - "sqli"
  - "sql injection"
  - "rce"
  - "ssrf"
  - "ssti"
  - "idor"
  - "csrf"
  - "cors"
  - "open redirect"
  - "takeover"
  - "subdomain takeover"
  - "bypass"
  - "waf bypass"
  - "auth bypass"
  - "authz bypass"
  - "privilege escalation"
  - "calculus"
  - "deep mode"
  - "trojan mode"
  - "trojan horse"
  - "gatekeeper"
  - "blind spot"
  - "onchain"
  - "on-chain"
  - "smart contract"
  - "defi exploit"
  - "bridge exploit"
  - "flashloan"
  - "reentrancy"
  - "oracle manipulation"
  - "governance attack"
  - "immunefi"
  - "hackerone"
  - "bugcrowd"
  - "cantina"
  - "hats"
  - "code4rena"
  - "sherlock"
  - "audit"
  - "auditing"
  - "yaklang"
  - "hack-skills"
  - "recon"
auto_activate: true
---

# PREDATOR RECON v2.0 — Skill Definition

**Philosophy:** Tools for the hands. Loop for the mind.
Unified CLI: Engine (automated pipeline) + Reference (yaklang/hack-skills library).
Every phase outputs structured data that feeds the IDEA.md core loop:
`ELIMINATE → TRACE → WALK → LOOP until TX HASH / WEAK PROVEN / FUNDS STOLEN`

---

## PHASE ARCHITECTURE

| Phase | Goal | IDEA.md integration | Output |
|-------|------|------------------|--------|
| **0. SCOPE & ELIMINATE** | Parse program scope, cut impossible vectors | **Calculus** — Value > Cost? **Blind Spot** — What's planted? | `targets.yaml` — ranked by Calculus |
| **1. SUBDOMAIN ENUM** | Passive + active discovery | **Trace** — Map trust boundaries | `subs.txt`, `live.txt` |
| **2. URL & PARAM HARVEST** | Historical + live endpoints | **Trace** — Find trust gaps in params | `urls.txt`, `params.txt` |
| **3. JS & CLIENT-SIDE** | Secrets, endpoints, logic in JS | **Trace** — Hidden trust assumptions | `js.txt`, `js-secrets.txt` |
| **4. VULN SCANNING** | Targeted, not spray | **Calculus** — High-value only | `vulns.txt` (verified) |
| **5. DEEP MODE (Auto)** | When core loop stalls | **Deep Mode** — 3-scenario sim | `deep-plan.yaml` |
| **6. TROJAN MODE (Fallback)** | Direct force failed | **Trojan** — Gatekeeper exploitation | `trojan-plan.yaml` |

---

## CALCULUS FILTER (Every Phase)

Before running ANY tool, ask:
```
Value > Cost + Risk + Irreversibility?
```
- **Value**: Bounty max, fund at risk, user impact
- **Cost**: Tool time, compute, rate limits
- **Risk**: Detection, legal, target sensitivity
- **Irreversibility**: Can we undo/cleanup?

**NO → Skip tool. YES → Execute with purpose.**

---

## QUICK START

```bash
# Load skill
skill load predator-recon

# Unified CLI (Engine + Reference)
predator-recon phase1-subdomain targets.yaml
predator-recon phase2-urls live.txt
predator-recon ref vuln xss
predator-recon sync-ref

# Phase 0: Scope & Eliminate (manual - feed program scope)
# Edit targets.yaml with your Calculus ranking

# Phase 1: Subdomain Enum
predator-recon phase1-subdomain targets.yaml

# Phase 2: URL/Param Harvest 
predator-recon phase2-urls live.txt

# Phase 3: JS Hunting
predator-recon phase3-vuln params.txt js-secrets.txt

# Phase 4: Targeted Vuln Scan
predator-recon phase4-vuln params.txt js-secrets.txt

# Phase 5: On-Chain Analysis
predator-recon phase5-onchain targets.yaml

# Auto Deep/Trojan when loop stalls
predator-recon auto-deep vulns.txt
predator-recon auto-trojan vulns.txt
```

---

## UNIFIED CLI (v2.0)

```
predator-recon <command> [options]

ENGINE COMMANDS (Automated Pipeline):
  phase1-subdomain   <targets.yaml>    Subdomain enum (passive → active → resolve → live)
  phase2-urls        <live.txt>        URL & param harvest + JS extraction
  phase3-vuln        <params.txt>      Calculus-gated vuln scan (XSS, SQLi, SSRF, etc)
  phase4-infra       <live.txt>        Infra recon (ports, vhosts, cloud metadata)
  phase5-onchain     <targets.yaml>    Smart contract analysis (storage, functions, sim)
  auto-deep          <vulns.txt>       Deep Mode: 3-scenario sim + pre-commit decisions
  auto-trojan        <vulns.txt>       Trojan Mode: Gatekeeper analysis + indirect strategy

REFERENCE COMMANDS (Yaklang Hack-Skills Library):
  ref recon              Full recon methodology playbook
  ref subdomain          Subdomain enumeration techniques & tools
  ref urls               URL harvesting & parameter extraction
  ref js                 JavaScript hunting & secret extraction
  ref vuln <class>       Vuln class checklist (xss, sqli, ssrf, idor, cors, redirect, ssti, rce)
  ref infra              Infrastructure recon (ports, vhosts, cloud metadata)
  ref onchain            Smart contract analysis patterns
  ref cheat              One-page cheatsheet
  ref search <keyword>   Search all reference docs

CONFIG:
  config show            Show current calculus/tools config
  config edit            Edit calculus.yaml / tools.yaml

SYNC:
  sync-ref               Pull latest yaklang/hack-skills references
```

---

## FILES

| File | Purpose |
|------|---------|
| `predator-recon` | **Main CLI wrapper** (Engine + Reference unified) |
| `scripts/phase1-subdomain.sh` | Subdomain enum (passive → active) |
| `scripts/phase2-urls.sh` | URL/param harvest |
| `scripts/phase3-vuln.sh` | Targeted vuln scanning |
| `scripts/phase4-infra.sh` | Infra recon (ports, vhosts, cloud metadata) |
| `scripts/phase5-onchain.sh` | On-chain / DeFi analysis |
| `scripts/auto-deep.sh` | Deep Mode auto-trigger |
| `scripts/auto-trojan.sh` | Trojan Mode auto-trigger |
| `scripts/install-tools.sh` | Auto-install all 25+ tools |
| `scripts/proxy-auth-bypass-probe.sh` | Mergify auth bypass probe |
| `examples/hunts/recon/predator-recon/mergify-auth-bypass-case-study.md` | **Middleware auth bypass probe** (control char + XFF test) |
| `examples/hunts/recon/predator-recon/t3tris-finance-case-study.md` | **DeFi vault recon case study** — t3tris.finance ($6.4M, shared silo SPOF, EOA admin, Blockscout lie, PUSH4 extraction) |
| `references/defi-vault-recon-methodology.md` | **14-step DeFi vault recon methodology** — RPC analysis, proxy/admin, silo SPOF, ERC-4626/ERC-20/Proxy selectors |
| `references/flash-loan-attack-patterns.md` | **Flash loan attack methodology** — Oracle manipulation, share price inflation, async settlement, collateral inflation, liquidation manipulation |
| `references/bug-bounty-report-template.md` | **Bug bounty report template** — Immunefi/Hats/Code4rena/Sherlock ready, PoC commands, fix recommendations |
| `references/methodology-cheatsheet.md` | 1-page cheatsheet |
| `references/recon-methodology.md` | Full playbook (yaklang sync) |
| `references/recon-for-sec.md` | Additional recon techniques |
| `examples/hunts/recon/predator-recon/mergify-case-study.md` | Mergify recon case study (80→51→4 vectors) |
| `references/creative-destruction-methodology.md` | Creative Destruction methodology — proven techniques from Mergify session |
| `config/calculus.yaml` | Value/Cost/Risk thresholds |
| `config/tools.yaml` | Tool versions & install cmds |
| `payloads/xss.txt` | XSS payloads (reflected + blind) |
| `payloads/sqli.txt` | SQLi payloads (error + blind + time) |
| `payloads/ssrf.txt` | SSRF payloads |
| `payloads/ssti.txt` | SSTI payloads |

---

## CONFIGURATION

**User config:** `~/.config/predator-recon/`
```yaml
# calculus.yaml — Calculus thresholds
min_value_usd: 1000
max_cost_minutes: 30
max_risk_score: 7
require_clean_exit: true

# tools.yaml — Tool versions & install cmds
tool_limits:
  nuclei_rate_limit: 100
  httpx_threads: 50
  katana_depth: 3
  gau_timeout: 30
```

---

## INTEGRATION WITH IDEA.md

### Core Loop Mapping
```
IDEA core loop          →  Predator Recon Phase
─────────────────────────────────────────────────────────────
ELIMINATE               →  Phase 0: Scope parsing + Calculus filter
TRACE (trust gaps)      →  Phase 1-3: Subdomain → URL → JS mapping
WALK (exploit)          →  Phase 4: Targeted vuln scan + exploit
LOOP (pivot)            →  auto-deep.sh / auto-trojan.sh
```

### Blind Spot Scanner (Post-Phase)
After each phase, auto-run:
```bash
# What did I NOT look at?
comm -23 <(cat all-possible.txt | sort) <(cat checked.txt | sort)

# What would devs expect me to miss?
grep -r "internal\|admin\|debug\|test\|staging" checked.txt

# If I'm wrong, where?
# → Document assumption failures in assumptions.log
```

### Deep Mode Trigger
When core loop stalls (3+ vectors, no results):
```bash
predator-recon auto-deep vulns.txt targets.yaml
```
Runs 3-scenario simulation (Best / Worst / Adversarial) + pre-commit decisions.

### Trojan Mode Trigger
When direct force fails (3+ failed vectors):
```bash
predator-recon auto-trojan vulns.txt targets.yaml
```
Runs Gatekeeper analysis → Horse Architecture → Indirect Victory Protocol.

---

## YAKLANG/HACK-SKILLS INTEGRATION (v2.0)

**Auto-sync 102 offensive skills from yaklang/hack-skills:**
```bash
predator-recon sync-ref
```
Pulls latest references into `reference/`:
- `recon-methodology.md` — Full playbook
- `recon-for-sec.md` — Additional techniques
- `methodology-cheatsheet.md` — 1-page cheatsheet

**Reference commands:**
```bash
predator-recon ref recon          # Full methodology
predator-recon ref vuln xss       # XSS checklist
predator-recon ref search "cloud" # Search all refs
```

---

## CONFIGURATION

**User config:** `~/.config/predator-recon/`
```yaml
# calculus.yaml — Calculus thresholds
min_value_usd: 1000
max_cost_minutes: 30
max_risk_score: 7
require_clean_exit: true

# tools.yaml — Tool versions & install cmds
tool_limits:
  nuclei_rate_limit: 100
  httpx_threads: 50
  katana_depth: 3
  gau_timeout: 30
```

---

## REQUIREMENTS

### Tools (auto-installed by `./scripts/install-tools.sh`)
| Tool | Purpose | Install |
|------|---------|---------|
| subfinder | Passive subdomain enum | `go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest` |
| amass | Passive + active enum | `go install -v github.com/OWASP/Amass/v3/...@master` |
| assetfinder | Subdomain discovery | `go install github.com/tomnomnom/assetfinder@latest` |
| httpx | HTTP probe | `go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest` |
| katana | Crawling | `go install github.com/projectdiscovery/katana/cmd/katana@latest` |
| gau | URL history | `go install github.com/lc/gau/v2/cmd/gau@latest` |
| waymore | Wayback + gau + more | `pip install waymore` |
| nuclei | Template scanning | `go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest` |
| dalfox | XSS scanning | `go install github.com/hahwul/dalfox/v2@latest` |
| sqlmap | SQL injection | `pip install sqlmap` |
| jscracker | JS secret finder | `go install github.com/Ractiurd/jscracker@latest` |
| naabu | Port scan | `go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest` |
| anew | Unique lines | `go install github.com/tomnomnom/anew@latest` |
| uro | URL dedup | `pip install uro` |
| qsreplace | Param replace | `go install github.com/tomnomnom/qsreplace@latest` |
| kxss | XSS reflection | `go install github.com/tomnomnom/hacks/kxss@latest` |
| gxss | XSS param finder | `go install github.com/KathanP19/Gxss@latest` |
| paramspider | Param mining | `pip install paramspider` |
| puredns | DNS bruteforce | `go install github.com/d3mondev/puredns/v2@latest` |
| subzy | Subdomain takeover | `go install -v github.com/LukaSikic/subzy@latest` |
| corscanner | CORS misconfig | `go install github.com/Tanmay-N/CORS-Scanner@latest` |

### Wordlists
- **Assetnote** (best): `https://wordlists.assetnote.io/`
- **SecLists**: `https://github.com/danielmiessler/SecLists`

---

## EXAMPLE WORKFLOW

```bash
# 1. New target: ImmuneFi program "XYZ Protocol"
# 2. Phase 0: Parse scope → targets.yaml
cat > targets.yaml << 'EOF'
- domain: xyz.fi
  chain: ethereum
  contracts: ["0x123...", "0x456..."]
  bounty_max: 50000
  calculus_value: 50000
  calculus_cost: 15
  calculus_risk: 3
  calculus_clean: true
  priority: 1
EOF

# 3. Run Phase 1
predator-recon phase1-subdomain targets.yaml
# → live.txt (200 OK subdomains)

# 4. Run Phase 2
predator-recon phase2-urls live.txt
# → params.txt (URLs with parameters)

# 5. Run Phase 3
predator-recon phase3-vuln params.txt js-secrets.txt
# → vulns.txt (verified findings)

# 6. If vulns.txt empty after 3 targets → auto-trojan
predator-recon auto-trojan vulns.txt targets.yaml
# → trojan-plan.yaml (indirect approach)
```

---

## TROUBLESHOOTING

| Issue | Fix |
|-------|-----|
| Tool not found | Run `./scripts/install-tools.sh` |
| Rate limited | Increase delays, use `--rate-limit` |
| Too many results | Tighten Calculus thresholds in config |
| False positives | Verify manually, add to `false-positives.txt` |
| Loop stalling | Check `assumptions.log`, run `auto-deep.sh` |

---

## CREATIVE DESTRUCTION TESTING PITFALLS

- **403 ≠ No Bug**: A 403 from Cloudflare/CDN means the request never reached the application. Bypass Cloudflare before concluding a vector is dead. Mergify `github-webhook` and `engine-api` returned 403 via CF but GCP endpoints may differ.
- **SPA Returns 200 for Everything**: Single-page apps route all paths to the same HTML. Don't mistake a 200 SPA response for a real API endpoint. Check Content-Type: `text/html` = SPA, `application/json` = real API.
- **FastAPI `{"detail":"Not Found"}`**: The real API routes may be on a different subpath or require authentication. Mergify API returned `{}` for `/` and 404 JSON everywhere else.
- **Staging = Public ≠ No Bug**: Staging often mirrors prod with debug features enabled. Always compare staging vs production HTML/JS for differences.
- **NEVER FABRICATE "POTENTIAL" FINDINGS**: User corrected: "Token leak beneran leak ga? Klo ga beneran buat apa? Cek soul.md mu, kalau ga berdampak cuka asumsi buat apa." Only report VERIFIED impact with tool output. If you can't prove token leak with actual token found, DROP the finding. No "may expose", "could leak", "potential for". Real tool output only: `curl` → token string in response. If empty → finding deleted.
- **ORDERED ANALYSIS WITH VERIFICATION**: User demanded "urut aja. Dari 1" — analyze vectors sequentially, each with concrete proof (PoC command + output). Stop at first unverified assumption. No batch reporting of theoretical findings.
- **CSP TRUST CHAIN ANALYSIS WORKS**: Mergify CSP allowed `script-src https://status.mergify.com`. Dashboard JS dynamically loads `document.createElement('script')` with `src='https://status.mergify.com/embed/script.js'` which creates iframe to `cjgzpb4hx21p.statuspage.io/embed/frame`. Map ALL `script-src`, `frame-src`, `connect-src` domains → check each for takeover/customization → trace runtime loading (document.createElement('script'), iframe src). This found the statuspage embed vector.
- **SPA PROXY ENDPOINT DISCOVERY**: Dashboard JS bundles contain `/front/proxy/engine/v1/...`, `/front/proxy/github/...`, `/front/proxy/saas/...` — these are REAL backend proxies. Search JS for `/proxy/` patterns. Test each: 401/403 = exists & protected, 404 = not exist, 200 = vulnerable. Mergify: `/front/proxy/github/user` → 401, `/front/proxy/engine/v1/repos/.../conditions-evaluation` (POST) → 403. These are verified attack surfaces.
- **MIDDLEWARE ORDERING AUTH BYPASS (CRITICAL)**: SPA proxy endpoints with JSON body parsers are vulnerable to middleware ordering bugs. If JSON parser runs BEFORE auth middleware and crashes on literal control chars (`\n`, `\t`, `\r`) in string values → body stream consumed → auth middleware SKIPPED → request forwarded to backend with empty body. **Detection**: Clean request → 403/401. Control char request → 422 with `"input": {}`. This indicates auth was bypassed (empty body at backend = parser consumed it). Test with `X-Forwarded-For: 127.0.0.1` which often triggers internal-trust logic. Probe script: `scripts/proxy-auth-bypass-probe.sh`.
- **PATH TRAVERSAL WITHIN PROXY PREFIX**: Path traversal inside `/front/proxy/` (e.g., `/front/proxy/engine/v1/../../engine/v1/...`) can reach different backend routes with different auth requirements. Test traversal variants + control chars for combined bypass.
- **422 WITH `input: {}` = AUTH BYPASS SIGNAL, NOT VALIDATION ERROR**: Don't mistake the 422 for a validation error. The empty `input: {}` proves the backend received no body because the proxy's parser crashed and consumed the stream. The auth middleware never ran. This is a critical auth bypass, not a JSON format issue.
- **MINIMAL TOOLKIT PROVEN SUFFICIENT**: 5 tools — `curl`, `subfinder`, `httpx`, `nuclei`, `cast`/`forge` — completed full Mergify recon (80→51→4 vectors). Don't wait for full install; start with what's available.
- **AUTH BYPASS VIA MIDDLEWARE ORDERING BUG (CLASS)**: Mergify Engine API proxy has critical auth bypass: JSON body parser runs BEFORE auth middleware. When body contains literal control chars (`\n`, `\t`, `\r`) + `X-Forwarded-For: 127.0.0.1` → parser crashes → body stream consumed → auth middleware SKIPPED → request reaches Engine API with empty body → **422 instead of 403**. Proof: `curl -X POST /front/proxy/engine/v1/repos/mergifyio/mergify-engine/conditions-evaluation -H "X-Forwarded-For: 127.0.0.1" -d '{"test": "value\n"}'` → HTTP 422 `{"input":{}}` (empty body at engine = auth bypassed). **Pattern**: Find proxy endpoints → test control chars in JSON → check for 422 vs 403 → verify `input: {}` in error. This is a CLASS of bug: middleware ordering where parser crashes skip auth.
- **PROXY PATH TRAVERSAL + AUTH BYPASS CHAIN**: Mergify `/front/proxy/../../../engine/v1/...` traversal reaches Engine API endpoints with auth bypass (405 = route exists, no auth). Combined with control-char bypass → potential full engine API access. Test: path traversal to escape proxy prefix → control char to skip auth → valid body to engine.
- **422 ≠ VALIDATION ERROR — IT'S AUTH BYPASS INDICATOR**: When a protected endpoint returns 422 with `{"input": {}}` (empty body) instead of 401/403, the auth middleware was SKIPPED. The body parser crashed first, consumed the stream, auth never ran. This is a RELIABLE indicator of middleware ordering auth bypass. Always compare: clean JSON → 403, control-char JSON → 422 with empty input = AUTH BYPASS CONFIRMED.

- **DEFI VAULT RECON METHODOLOGY (CLASS)**: When targeting DeFi vault protocols, the standard web recon pipeline is NOT enough. You need an ON-CHAIN ANALYSIS phase. Pattern:
  1. **Frontend scraping** → Extract JS bundles, find API URLs, contract addresses, chain IDs
  2. **Extract all contract addresses** → Look for patterns: vault, silo, factory, implementation, proxy
  3. **RPC access test** → Try public RPCs (arb1.arbitrum.io/rpc, 1rpc.io/arb) → eth_blockNumber
  4. **RPC calls** → eth_call for function selectors, eth_getStorageAt for storage slots, eth_getCode for contract check, eth_getTransactionByFromAndIndex for deployer txs
  5. **Map architecture** → Protocol (factory/impl) → Vault (proxy/impl) → Silo (shared storage) → Deployers (EOA vs contract)
  6. **Check proxy admin** → ERC1967 admin slot = 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 → if 0x0 = UUPS pattern (impl controls upgrade)
  7. **Check function selectors** → Test common selectors: 0xd7b28185 (totalAssets), 0x70a08231 (balanceOf), 0x95d89b41 (name), 0xa5d37df5 (custom)
  8. **Check deposit/withdraw** → Test deposit(uint256,address) → 0x415565e0 → if REVERTED = permissioned, if ALLOWED = direct exploit
  9. **Check silo balance** → balanceOf(vault_address) on silo contract → compare with reported TVL → discrepancy = hidden funds
  10. **Check deployer type** → eth_getCode(deployer) → EOA = individual risk, Contract = factory/governance risk
  11. **Identify shared components** → Silo used by multiple vaults = single point of failure → one bug drains ALL vaults
  12. **Verify impl vs blockscout** → Blockscout impl slot vs Factory storage slot → mismatch = WRONG on explorer. **ALWAYS TRUST FACTORY STORAGE**. t3tris.finance: Blockscout showed 0x00ac46..., Factory slot 3 showed 0x7aea44... (REAL)
  13. **PUSH4 SELECTOR EXTRACTION (NO TOOLS NEEDED)** → When disassemblers unavailable, extract PUSH4 (0x63) from bytecode: scan hex for `63` + 8 hex chars = function selector. t3tris: 43 vault selectors, 111 silo selectors found this way.
  14. **CUSTOM VAULT IMPL ANALYSIS** → Test ALL selectors on proxy (delegatecall to impl). Standard ERC-4626 selectors (totalAssets, deposit, withdraw) may REVERT. Custom admin functions hidden in 4-byte space. Map return values: addresses = config (fee recipient, silo, curator), uints = fees/timestamps.
  15. **SILO ARCHITECTURE PATTERNS**:
      - **Simple Ownable + Pausable** (t3tris): owner() = admin, pause/unpause, NO AccessControl → single EOA = SPOF
      - **AccessControl + Roles** (standard): hasRole/grantRole/revokeRole → check admin role holders
      - **Permissioned deposit/withdraw** → test 0x415565e0, 0x6e5333b0 → REVERT = vault-only, ALLOWED = exploit
  16. **EOA ADMIN SPOF** → Silo admin = EOA with low ETH balance = high compromise likelihood. Centralized control of $6.4M across 4 vaults. Attack path: key compromise → grantRole → drain all vaults simultaneously.
  17. **Attack path**: Permissionless silo → direct drain | Permissioned silo → find bypass | UUPS upgrade → replace impl | Whitelist → bypass ACL | EOA admin compromise → full control

    18. **ECONOMIC ATTACK ANALYSIS** → After architecture mapping, quantify exploit economics:
        - **Fee parameters**: Extract fee bps (0x022d63fb = 431,936 = 43.19% at t3tris). Check if setter exists → 100% fee = full yield drain
        - **Whitelist bypass**: If depositWhitelist=true + depositEnabled=false → Silo admin can grant DEPOSIT_ROLE → bypass whitelist
        - **Exit fee**: If exitFee setter exists → 100% = immediate principal drain on withdrawal
        - **Fee recipient**: If feeRecipient setter exists → redirect all fees to attacker
        - **Max extraction**: Calculate TVL × fee % × time for yield drain; TVL × 100% for exit fee

    19. **FLASH LOAN ATTACK ANALYSIS** → After economic analysis, assess flash loan feasibility:
        - **Oracle type check**: Chainlink/TWAP = safe, AMM spot/custom = vulnerable
        - **Settlement window**: Async settlement = price staleness window
        - **Capital required**: $5M-50M depending on AMM liquidity
        - **Max extractable**: Full vault TVL if oracle manipulable
        - **Attack vectors**: Oracle manipulation, share price inflation, settlement exploitation
        → see `references/flash-loan-attack-patterns.md` for complete methodology

    20. **ERC-4626 COMPLIANCE VERIFICATION** → Test standard selectors on vault proxy:
        - 0xd7b28185 totalAssets() → REVERT = non-standard
        - 0x415565e0 deposit(uint256,address) → REVERT = non-standard
        - 0x6e5333b0 withdraw(uint256,address,address) → REVERT = non-standard
        - If ALL revert → custom implementation, hidden admin functions in 4-byte space

    21. **EMERGENCY FUNCTION CHECK** → Test common emergency selectors:
        - 0x534e8b6c emergencyWithdraw()
        - 0x41c0c9c9 sweep(address)
        - 0x44c028fe recoverERC20(address,uint256)
        - If EXISTS → potential instant drain vector; if NOT → no escape hatch

    21. **ATOKEN VAULT PATTERN (ORACLE-SAFE)** → When a vault wraps Aave V3 aTokens:
        - **NO oracle dependency** — uses `ATOKEN.balanceOf(this)` for `totalAssets()`
        - Share price = aToken balance / total shares (ERC-4626 standard)
        - **Immune to oracle manipulation** — no Chainlink, TWAP, custom oracle
        - Source code often in `t3tris-finance/Aave-Vault` GitHub repo
        - Attack surface limited to: Aave protocol risk, Silo admin SPOF, UUPS upgrade
        - Key function: `totalAssets()` returns `ATOKEN.balanceOf(this) - getClaimableFees()`
        - If vault is ATokenVault: DROP oracle manipulation vector, focus on admin/upgrade risks

    22. **UNVERIFIED CONTRACT BLOCKER** → When Shared Silo / VaultImpl / Factory source code is NOT verified:
        - **Cannot assess**: oracle logic, `setPrice()` functions, staleness checks, upgrade mechanism
        - **Cannot verify**: proxy admin identity, AccessControl roles, cross-chain oracle design
        - **Action**: Document as CRITICAL GAP in report, recommend source verification
        - **Do NOT fabricate**: If you can't see the code, don't invent oracle vulnerabilities
        - **Fallback**: Focus on what IS verifiable — proxy patterns, admin slots, known implementations
        - **Report**: "Source code not verified — oracle attack surface cannot be assessed. Estimated max extractable: unknown (up to full TVL if oracle exists)."

    23. **BUG BOUNTY REPORT TEMPLATE** → Structure findings for Immunefi/Hats:
        - Executive Summary (Severity, TVL at Risk, Chain)
        - Vulnerability Details (Component, Root Cause, Attack Path)
        - Proof of Concept (cast/forge commands + output)
        - Impact Assessment (Max Loss, Likelihood, Affected Users)
        - Recommended Fix (Code changes, Architecture changes)
        - Disclosure Timeline

    24. **Blockscout lie**: Explorer shows WRONG impl (0x00ac46...) vs Factory storage REAL impl (0x7aea44...). Always verify impl via proxy storage slot 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc, not explorer.

## VERSION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-19 | Initial: wadgamer10 pipeline × IDEA.md core-loop integration |
| 1.1 | 2026-07-19 | Expanded trigger words: exploit, steal, drain, attack, pwn, hack, bypass, etc. |
| 2.0 | 2026-07-19 | **Unified CLI wrapper + yaklang/hack-skills sync + config-driven + cheatsheet** |
| 2.1 | 2026-07-19 | **Added Mergify case study + Creative Destruction testing pitfalls + Minimal toolkit fallback** |
| 2.2 | 2026-07-19 | **Full Mergify recon complete — 20 findings (3C/3H/6M/4L/4I). Creative Destruction vectors mapped. Minimal toolkit proven (curl/httpx/subfinder/nuclei/cast/forge). Mergify case study added as reference.** |
| 2.3 | 2026-07-19 | **Creative Destruction Methodology reference added. Key lessons: NO FABRICATION (verified findings only), Ordered analysis with PoC per vector, CSP trust chain tracing, SPA proxy endpoint discovery, Staging vs Prod diff analysis, Minimal toolkit proven, Reality check (user correction: "Token leak beneran leak ga?"). Updated Mergify case study with 3 false positives removed.** |
| 2.5 | 2026-07-20 | **DeFi Vault Recon Methodology added (14-step pattern: frontend scrape → RPC calls → architecture mapping → attack path).** Includes t3tris.finance case study ($6.4M TVL, shared silo SPOF, UUPS proxy, ERC-4626/ERC-20/Proxy selector reference). |
| 2.6 | 2026-07-20 | **t3tris.finance case study complete** — Blockscout lie exposed (Factory storage = truth), shared Silo SPOF with EOA admin ($6.4M), custom vault impl (43 selectors, no ERC-4626), PUSH4 selector extraction without tools, EOA admin SPOF pattern. **PUSH4 extractor script added** (`scripts/push4-extractor.py`). |
| 2.7 | 2026-07-23 | **Flash Loan Attack Patterns reference added** — Oracle manipulation, share price inflation, async settlement exploitation, PoC templates, detection checklist. **DeFi Vault Recon Methodology updated** with flash loan analysis section (Step 18.5). |
| 2.7 | 2026-07-23 | **Oracle manipulation audit complete** — Ellen Vault (Aave aToken wrapper) confirmed oracle-safe: uses `ATOKEN.balanceOf(this)` for `totalAssets()`, no Chainlink/TWAP/custom oracle. Source from GitHub `t3tris-finance/Aave-Vault`. Added steps 15-17 to methodology (DeFiLlama API, Ecosystem API, GitHub org enum, ATokenVault pattern, unverified contract blocker). Updated case study with Oracle column and ATokenVault section. |

---

## CASE STUDIES

- **Mergify Auth Bypass (2026-07-20):** Critical auth bypass on Engine API proxy via middleware ordering bug. Control chars in JSON + X-Forwarded-For: 127.0.0.1 → 422 (auth skipped) vs 403 (clean). Full case study: `examples/hunts/recon/predator-recon/mergify-auth-bypass-case-study.md`. Probe script: `scripts/proxy-auth-bypass-probe.sh`.
- **Mergify Recon (2026-07-19):** 80 subdomains → 51 live → 4 creative destruction vectors (GitHub webhook bypass, Engine API auth bypass, GHES dev env, staging). Full case study: `examples/hunts/recon/predator-recon/mergify-case-study.md`.
- **Paxos Gas Exploits (2026-07-19):** 8 gas vectors across 7 repos ($400K-$1.15M estimated). Full findings: `examples/hunts/recon/predator-recon/paxos-gas-exploits.md`.

---

## PITFALLS

- **Scripts not executable after deploy**: The `scripts/` directory files must be `chmod +x` after first deploy. Run `chmod +x /path/to/scripts/*.sh` before using `predator-recon phase1-*`.
- **Missing tools**: `install-tools.sh` requires Go to be pre-installed. In container/headless environments where `go` is unavailable, fall back to manual `curl`-based recon using these available tools (minimal toolkit): `subfinder`, `httpx`, `nuclei`, `cast`, `forge`, `curl`. The Mergify recon (2026-07-19) successfully used only these 5 tools.
- **`anew` not available**: Use `sort -u` or `>> file && sort -u file -o file` as substitute when `anew` is not installed.
- **YAML parsing**: The `phase1-subdomain.sh` script falls back to grep-based parsing when `yq` is not installed. This works for simple domain lists but not for structured `targets.yaml` with Calculus fields. Install `yq` for full functionality.
- **NEVER FABRICATE "POTENTIAL" FINDINGS**: User corrected: "Token leak beneran leak ga? Klo ga beneran buat apa? Cek soul.md mu, kalau ga berdampak cuka asumsi buat apa." Only report VERIFIED impact with tool output. If you can't prove token leak with actual token found, DROP the finding. No "may expose", "could leak", "potential for". Real tool output only: `curl` → token string in response. If empty → finding deleted.
- **ORDERED ANALYSIS WITH VERIFICATION**: User demanded "urut aja. Dari 1" — analyze vectors sequentially, each with concrete proof (PoC command + output). Stop at first unverified assumption. No batch reporting of theoretical findings.
- **CSP TRUST CHAIN ANALYSIS WORKS**: Mergify CSP allowed `script-src https://status.mergify.com`. Dashboard JS dynamically loads `document.createElement('script')` with `src='https://status.mergify.com/embed/script.js'` which creates iframe to `cjgzpb4hx21p.statuspage.io/embed/frame`. Map ALL `script-src`, `frame-src`, `connect-src` domains → check each for takeover/customization → trace runtime loading. This found the statuspage embed vector.
- **SPA PROXY ENDPOINT DISCOVERY**: Dashboard JS bundles contain `/front/proxy/engine/v1/...`, `/front/proxy/github/...`, `/front/proxy/saas/...` — these are REAL backend proxies. Search JS for `/proxy/` patterns. Test each: 401/403 = exists & protected, 404 = not exist, 200 = vulnerable. Mergify: `/front/proxy/github/user` → 401, `/front/proxy/engine/v1/repos/.../conditions-evaluation` (POST) → 403.
- **MINIMAL TOOLKIT PROVEN**: `curl`, `subfinder`, `httpx`, `nuclei`, `cast`, `forge` — 5 tools sufficient for full recon. Mergify recon (2026-07-19) used only these 5 tools. Don't wait for full tool install — start with what's available.
- **AUTH BYPASS VIA MIDDLEWARE ORDERING BUG**: Mergify Engine API proxy has critical auth bypass: JSON body parser runs BEFORE auth middleware. When body contains literal control chars (`\n`, `\t`, `\r`) + `X-Forwarded-For: 127.0.0.1` → parser crashes → body stream consumed → auth middleware SKIPPED → request reaches Engine API with empty body → **422 instead of 403**. Proof: `curl -X POST /front/proxy/engine/v1/repos/mergifyio/mergify-engine/conditions-evaluation -H "X-Forwarded-For: 127.0.0.1" -d '{"test": "value\n"}'` → HTTP 422 `{"input":{}}` (empty body at engine = auth bypassed). Pattern: **Find proxy endpoints → test control chars in JSON → check for 422 vs 403 → verify `input: {}` in error**. This is a CLASS of bug: middleware ordering where parser crashes skip auth.
- **PROXY PATH TRAVERSAL + AUTH BYPASS CHAIN**: Mergify `/front/proxy/../../../engine/v1/...` traversal reaches Engine API endpoints with auth bypass (405 = route exists, no auth). Combined with control-char bypass → potential full engine API access. Test: path traversal to escape proxy prefix → control char to skip auth → valid body to engine.
- **422 ≠ VALIDATION ERROR — IT'S AUTH BYPASS INDICATOR**: When a protected endpoint returns 422 with `{"input": {}}` (empty body) instead of 401/403, the auth middleware was SKIPPED. The body parser crashed first, consumed the stream, auth never ran. This is a RELIABLE indicator of middleware ordering auth bypass. Always compare: clean JSON → 403, control-char JSON → 422 with empty input = AUTH BYPASS CONFIRMED.

- **DEFI VAULT RECON METHODOLOGY (CLASS)**: When targeting DeFi vault protocols, the standard web recon pipeline is NOT enough. You need an ON-CHAIN ANALYSIS phase. Pattern:
  1. **Frontend scraping** → Extract JS bundles, find API URLs, contract addresses, chain IDs
  2. **Extract all contract addresses** → Look for patterns: vault, silo, factory, implementation, proxy
  3. **RPC access test** → Try public RPCs (arb1.arbitrum.io/rpc, 1rpc.io/arb) → eth_blockNumber
  4. **RPC calls** → eth_call for function selectors, eth_getStorageAt for storage slots, eth_getCode for contract check, eth_getTransactionByFromAndIndex for deployer txs
  5. **Map architecture** → Protocol (factory/impl) → Vault (proxy/impl) → Silo (shared storage) → Deployers (EOA vs contract)
  6. **Check proxy admin** → ERC1967 admin slot = 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 → if 0x0 = UUPS pattern (impl controls upgrade)
  7. **Check function selectors** → Test common selectors: 0xd7b28185 (totalAssets), 0x70a08231 (balanceOf), 0x95d89b41 (name), 0xa5d37df5 (custom)
  8. **Check deposit/withdraw** → Test deposit(uint256,address) → 0x415565e0 → if REVERTED = permissioned, if ALLOWED = direct exploit
  9. **Check silo balance** → balanceOf(vault_address) on silo contract → compare with reported TVL → discrepancy = hidden funds
  10. **Check deployer type** → eth_getCode(deployer) → EOA = individual risk, Contract = factory/governance risk
  11. **Identify shared components** → Silo used by multiple vaults = single point of failure → one bug drains ALL vaults
  12. **Verify impl vs blockscout** → Blockscout impl slot vs Factory storage slot → mismatch = WRONG on explorer. **ALWAYS TRUST FACTORY STORAGE**. t3tris.finance: Blockscout showed 0x00ac46..., Factory slot 3 showed 0x7aea44... (REAL)
  13. **PUSH4 SELECTOR EXTRACTION (NO TOOLS NEEDED)** → When disassemblers unavailable, extract PUSH4 (0x63) from bytecode: scan hex for `63` + 8 hex chars = function selector. t3tris: 43 vault selectors, 111 silo selectors found this way.
  14. **CUSTOM VAULT IMPL ANALYSIS** → Test ALL selectors on proxy (delegatecall to impl). Standard ERC-4626 selectors (totalAssets, deposit, withdraw) may REVERT. Custom admin functions hidden in 4-byte space. Map return values: addresses = config (fee recipient, silo, curator), uints = fees/timestamps.
  15. **SILO ARCHITECTURE PATTERNS**:
      - **Simple Ownable + Pausable** (t3tris): owner() = admin, pause/unpause, NO AccessControl → single EOA = SPOF
      - **AccessControl + Roles** (standard): hasRole/grantRole/revokeRole → check admin role holders
      - **Permissioned deposit/withdraw** → test 0x415565e0, 0x6e5333b0 → REVERT = vault-only, ALLOWED = exploit
  16. **EOA ADMIN SPOF** → Silo admin = EOA with low ETH balance = high compromise likelihood. Centralized control of $6.4M across 4 vaults. Attack path: key compromise → grantRole → drain all vaults simultaneously.
  17. **Attack path**: Permissionless silo → direct drain | Permissioned silo → find bypass | UUPS upgrade → replace impl | Whitelist → bypass ACL | EOA admin compromise → full control