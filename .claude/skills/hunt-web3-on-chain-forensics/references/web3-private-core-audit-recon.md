# Web3 Private-Core / Audit-Only Org Recon — RootsFi Pattern (2026-08-13)

When `GET /orgs/{org}/repos` returns only `roots-audits` (1 public repo) and core is private (`roots-fi/roots-core` 404), reconstruct from audit PDFs + docs/site instead of stopping.

## REST Fallback (no `gh` CLI)

```bash
curl -s -H "Accept: application/vnd.github+json" "https://api.github.com/orgs/{org}" | head -n 50
curl -s -H "Accept: application/vnd.github+json" "https://api.github.com/orgs/{org}/repos?per_page=100&page=1" \
 | python3 -c "import json,sys; d=json.load(sys.stdin); [print(r['name'],r['language'],r['html_url']) for r in d]"
curl -s "https://api.github.com/repos/{org}/{audits}/contents?ref=main" \
 | python3 -c "import json,sys; d=json.load(sys.stdin); [print(x['name'],x['type'],x['size']) for x in d]"
```

Paginate `page=2` to confirm. Record `public_repos` count — RootsFi = 1.

## Raw Download Fallback (git-remote-https missing)

Container error: `git: 'remote-https' is not a git command`.
```bash
mkdir -p /root/recon/pdfs
for f in Roots-security-review_2025-02-09.pdf 2025_04_16_SBSecurity_full_audit.pdf 2025_05_06_Sherlock_rBGT 2025_09_20_Final_Roots_Collaborative_Audit_Report_1758380911.pdf; do
  curl -sL -o "/root/recon/pdfs/$f" "https://raw.githubusercontent.com/{org}/{audits}/main/$f"
done
# Note: Sherlock_rBGT is a file without .pdf ext (type file, not dir) — handle both.
```

## Audit PDF Mining (pymupdf)

```python
import fitz, re
doc = fitz.open(pdf)
full = "\n".join(doc[i].get_text() for i in range(len(doc)))
addrs = re.findall(r"0x[a-fA-F0-9]{40}", full)          # BGT 0x656b..., BGTStaker 0x6371..., BEX pools
sols  = set(re.findall(r"[\w/]+\.sol", full))           # Factory.sol, TroveManager.sol, etc.
commits = re.findall(r"[a-f0-9]{7,40}", full)           # review commit hashes prove private core exists
# grep 300 chars around each address for context (BGT/BGTStaker labels, chainId)
for m in re.finditer(r"0x[a-fA-F0-9]{40}", full):
    print(full[max(0,m.start()-300):m.end()+300].replace("\n"," "))
```

RootsFi union across 4 audits → 13 contracts: `Factory`, `TroveManager`, `BorrowerOperations`, `StabilityPool`, `SortedTroves`, `LiquidationManager`, `DebtToken` (MEAD), `PriceFeed`/`BexPriceFeed`, `Staker`, `BeraAdapter`, `EmissionScheduler`, `BGTHandler`, `RootsBGT` (+ `RootsCore`). Solidity/Foundry, Liquity-fork CDP 120% MCR.

## Chain Inference When No Addresses Published

- Scrape `https://{project}.com` + `https://docs.{project}.com/cims` — Next.js skeleton returns 0 hits on `grep 0x`; search rendered text for `chain ID 84532` / `Berachain`.
- RootsFi: docs `CIMS Overview` → `Current implementation ... on Base Sepolia (chain ID 84532)` plus Berachain BGT `0x656b95E550C07a9ffe548bd4085c72418Ceb1dba` (chainId 80094) from audit snippets + `berascan.com`/`bex.berachain.com` refs. No MEAD/Roots deployment addresses published — gap to report.

## Trust Graph Synthesis (no source)

User → `BorrowerOperations.openTrove` / `StabilityPool.provideToSP` / `Staker.setValidator` / `BGTHandler.queueBoost` / `RootsBGT.requestRedemption` / `DebtToken.flashLoan`
Admin → `Factory.deployNewInstance`, `TroveManager.setParameters`, `StabilityPool.enableCollateral/sunset`, `PriceFeed.setPrice` (Pyth)
External → Berachain BGT/RewardVault (`IGauge` vs `IRewardVault` arity mismatch = C-01), Pyth, BEX pools, HONEY token

High-risk sinks to rank: `BGTHandler` permissionless `activateBoost`/`dropBoost` storage corruption (H-1), `executeRedemption` O(n) DoS, `StabilityPool` off-by-one index + gains overwrite, `BexPriceFeed` `totalSupply` vs `getActualSupply`, `EmissionScheduler` over-transfer.

## Gap Reporting

Always state: `No deployed MEAD/Roots addresses in public org/audits/site/docs — need authenticated roots-core or frontend bundle scrape (app.rootsfi.com → VITE_* constants) + Berascan/BaseScan V2 verification.` Do not fabricate.

## Pitfalls

- `gh: command not found` → use REST, don't stop.
- Sherlock rBGT file ext missing → check `type=file` not `dir`.
- Next.js docs need text extraction, not raw `grep 0x`.
- Explorer impl slot may lie — trust factory storage `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`.
