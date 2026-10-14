# Pre-Launch Protocol Detection & Reality Check

**Context:** Before investing hours in a deep audit, verify whether the protocol is actually LIVE with real TVL and users. Many protocols deploy contracts to mainnet but remain in pre-launch state (empty implementations, uninitialized proxies, 0 TVL). Auditing these is wasted effort — no funds = no bug bounty.

---

## Why This Matters

**Case Study: aPriori (July 2026)**
- Spent 2+ hours on reconnaissance
- Found GitBook docs, JS bundles, multi-chain addresses
- Deep bytecode analysis revealed: **proxy delegates to EMPTY address**
- TVL = 0, TotalSupply = 0, TotalStaked = 0
- Protocol is PRE-LAUNCH — not a viable bug bounty target

**Opportunity Cost:** Time spent on pre-launch protocols = time NOT spent on live targets with real funds at risk.

---

## Reality Check Workflow (5 Minutes Max)

### Step 1: Check TVL (30 seconds)

```bash
# DefiLlama API
curl -s "https://api.llama.fi/protocol/apriori" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tvl = data.get('tvl', 0)
print(f'Current TVL: ${tvl:,.0f}')
if tvl < 100000:  # Less than $100K
    print('WARNING: Pre-launch or dead protocol')
    sys.exit(1)
"
```

**Decision Rule:**
- TVL > $1M → Proceed with audit
- TVL $100K–$1M → Proceed with caution (small bounty)
- TVL < $100K or API error → **REALITY CHECK REQUIRED**

### Step 2: Check Implementation Code (1 minute)

```bash
# Read implementation slot (EIP-1967)
IMPL_SLOT="0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"

curl -X POST $RPC_URL \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getStorageAt\",\"params\":[\"$PROXY\",\"$IMPL_SLOT\",\"latest\"],\"id\":1}" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
impl_addr = '0x' + data['result'][-40:]
print(f'Implementation: {impl_addr}')
"

# Check if implementation has code
curl -X POST $RPC_URL \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getCode\",\"params\":[\"$IMPL_ADDR\",\"latest\"],\"id\":1}" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
code = data['result']
size = len(code[2:]) // 2 if code != '0x' else 0
print(f'Bytecode size: {size} bytes')
if size < 100:
    print('CRITICAL: Implementation is EMPTY or minimal stub')
    print('VERDICT: PRE-LAUNCH — skip audit')
    sys.exit(1)
"
```

**Decision Rule:**
- Implementation bytecode > 1KB → Normal, proceed
- Implementation bytecode < 100 bytes → **PRE-LAUNCH — skip**
- Implementation = 0x000... → **BROKEN — report but don't audit**

### Step 3: Check Admin Slot (1 minute)

```bash
# Read admin slot (EIP-1967)
ADMIN_SLOT="0xb53127684a568b3173ae13b9f8a6016e24aa342e"

curl -X POST $RPC_URL \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getStorageAt\",\"params\":[\"$PROXY\",\"$ADMIN_SLOT\",\"latest\"],\"id\":1}" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
admin = '0x' + data['result'][-40:]
print(f'Admin: {admin}')
if admin == '0x' + '0' * 40:
    print('WARNING: Admin slot is ZERO')
    print('Could be: uninitialized OR renounced')
"
```

**Decision Rule:**
- Admin = multi-sig → Normal
- Admin = EOA → Risky but live
- Admin = 0x0 + Implementation empty → **PRE-LAUNCH — skip**
- Admin = 0x0 + Implementation exists → **VULNERABLE but live** (initialization attack possible)

### Step 4: Check Total Supply / Users (1 minute)

```bash
# Check totalSupply() — selector 0x18160ddd
curl -X POST $RPC_URL \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_call\",\"params\":[{\"to\":\"$PROXY\",\"data\":\"0x18160ddd\"},\"latest\"],\"id\":1}" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
supply = int(data['result'], 16) if data['result'] != '0x' else 0
print(f'Total Supply: {supply}')
if supply == 0:
    print('NO USERS — pre-launch or dead')
"
```

**Decision Rule:**
- TotalSupply > 0 → Users exist, proceed
- TotalSupply = 0 → **NO USERS — skip**

### Step 5: Check Native Balance (30 seconds)

```bash
curl -X POST $RPC_URL \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBalance\",\"params\":[\"$PROXY\",\"latest\"],\"id\":1}" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
bal = int(data['result'], 16)
print(f'Native balance: {bal}')
# High balance with 0 TVL = deployment funds, not user funds
"
```

**Decision Rule:**
- High native balance + 0 TVL + 0 supply → **Deployment funds only — pre-launch**
- Low native balance + high TVL → **Normal operation**

---

## Pre-Launch Indicators (Checklist)

Before starting a deep audit, verify ALL of these:

| Indicator | Live Protocol | Pre-Launch |
|-----------|---------------|------------|
| TVL | > $100K | < $10K or error |
| Implementation bytecode | > 1KB | < 100 bytes or empty |
| Admin slot | Multi-sig or EOA | 0x0 (zero address) |
| TotalSupply | > 0 | 0 |
| TotalStaked/Deposits | > 0 | 0 |
| Recent transactions | Yes (last 24h) | None or only deployment |
| Website status | Live | Under construction / "coming soon" |
| Social activity | Active | Silent or "testnet" mentions |

**If 3+ indicators show PRE-LAUNCH → SKIP and find another target.**

## Anti-Pattern: Micro-Cap Tokens Masquerading as Protocols

**Case: POPs Finance (July 2026)** — A lending/CDP protocol at `popsfinance.xyz` on Robinhood chain with a live website, full NextJS SPA with RainbowKit wallet connect, and DeFi functionality. On-chain reality: a single Uniswap V3 POPS/WETH pool with **$7,334 liquidity and $9,243 FDV**. No lending vaults, no CDP contracts, no margin/position contracts. Just a token on a DEX.

**The crucial shortcut — DexScreener API:** the DexScreener search API returns the live token data in one request:
```bash
curl -s "https://api.dexscreener.com/latest/dex/search?q=POPS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for pair in data.get('pairs', [])[:3]:
    print(f\"{pair['baseToken']['name']} @ {pair['chainId']}\")
    print(f\"  TVL: \${pair.get('liquidity', {}).get('usd', 0):.0f}\")
    print(f\"  FDV: \${pair.get('fdv', 0):.0f}\")
    print(f\"  24h volume: \${pair.get('volume', {}).get('h24', 0):.0f}\")
    print()
"
```

**Combined reality check from this session:** POPs was identified in **20 minutes** instead of 3+ hours:
1. Fetch homepage → confirmed NextJS + Vercel
2. DexScreener API → found POPS token with $9K FDV
3. `eth_getCode` on POPS CA → confirmed deployed but trivial
4. **Decision: PASS** — liquidity < $10K is not a viable bug bounty target

**Micro-cap indicators (PASS immediately):**
- Liquidity < $10,000 on all pairs
- FDV < $50,000
- No vault/strategy/staking/lending contracts beyond the token
- Token is the ONLY deployed contract
- 24h volume < $50K (unless anomalous pump)

**The lesson:** Not every live contract is a viable bug bounty target. With < $10K in liquidity, even a critical find would typically max out at under $1K bounty. A $50K/quarter hunter should PASS these immediately.

**Time saved:** 2.5+ hours vs full audit (POPs) + 3.5 hours (ColibriSwap) = **~6 hours recouped.**

---

## Case Study: POPs Finance (July 2026) — Post-Mortem

| Check | Result |
|-------|--------|
| DexScreener FDV | $9,243 (single POPS/WETH Uniswap V3) |
| Liquidity | $7,334 |
| 24h volume | $131K (suspiciously correlated to FDV) |
| Vault/CDP contracts | NONE found — only the token |
| POPS Token bytecode | Deployed but trivial |
| JS bundle contract claim | `0x9513263...` — 0x bytecode on ALL chains |
| Wallet connect | RainbowKit (live) |
| Vercel hosting | Live, authenticated |
| `null` backend | No Supabase/admin panel found (NextJS SPA only) |
| Operator time invested | ~20 minutes, decision to pass |
| Verdict | **PASS — micro-cap token, no exploitable funds** |

**The pattern:** a polished website + live token + DEX listing falsely suggests a rich protocol with TVL. Reality: a pump group launched a Uniswap pool. No lending, no collateral, no margins — just a token and marketing.

**Deep audit of POPs Finance (entire session, ~20 minutes):**
- JS bundle extraction → `0x9513263...` = 0x bytecode everywhere- Tokens: `UniversalSwap` background, Pure SPA structure
- DexScreener API match → POPS token at `0x7e072b0516...` with 11.5K HYPE

**6-hour capacity expected**: ~20 min per checker, 12 verifications per hour = **240+ projects filtered in a 20-hour session**

---

**Case: ColibriSwap (July 2026)** — The website prominently displayed a contract address `0xDe8dA85...` in a red "CA" marquee banner that users could click to copy. On-chain inspection revealed 0x bytecode on ALL chains (ETH, Base, Arbitrum, BSC, OP, Polygon, Robinhood/HyperEVM).

**The trap:** A flashy UI element with a "contract address" label creates the illusion of a deployed protocol. The address may be a placeholder, a future deploy address, or purely cosmetic.

**Rule:** NEVER trust a contract address displayed in the UI. Always verify with `eth_getCode` on the actual chain. The UI is marketing; the chain is reality.

**Deep audit of ColibriSwap (9 agents, 3.5+ hours, FULL EXHAUSTION):**
- Supabase project `iksrzursefxjttnhfyju.supabase.co` → DNS NXDOMAIN (project paused/deleted)
- Edge Functions gateway still resolves but returns "Project not specified" on all paths
- COLIBRI token ERC-20 → 0x bytecode on every chain tested
- Admin panel discovered at `/panel-x7k9m2q3` (TanStack lazy-loaded route) but login requires email+password against the dead Supabase
- Privy auth: appId extracted, NO CAPTCHA on OTP, but Privy origin-gates all non-browser requests (`"Invalid Privy app ID"`)
- TanStack Start SSR: ALL non-HTML POST requests are rejected server-side (`"Only HTML requests are supported here"`)
- ChangeNOW/HoudiniSwap as swap backends — no ColibriSwap custody of funds

**The lesson:** A frontend can look fully live — 100+ chains, live rates, ability to swap in browser — while having zero on-chain deployment, a paused database, and no admin funds. The entire protocol exists only as a static HTML website fronting third-party APIs.

**Cost: ~3.5 hours × 9 agents = ~31.5 agent-hours.** This is the maximum penalty for not doing 5-minute reality check first.

**Rule:** Do reality check BEFORE spawning ANY agents. 5 minutes now saves 2-4 hours later.

**Dead protocol indicators (immediate walk-away):**
- Contract address 0x bytecode on ALL claimed chains
- Supabase DNS NXDOMAIN (project paused)
- Admin panel present but backend dead
- All value flow goes to third-party providers (ChangeNOW, HoudiniSwap)

---

## Case Study: aPriori Post-Mortem

### What We Found (After 2+ Hours)

| Check | Result |
|-------|--------|
| TVL (DefiLlama) | $65.5M (but this was WRONG — see below) |
| Implementation bytecode | 24,286 bytes at `0x7d2f8dc5...` |
| **BUT**: Proxy delegates to | `0x58221220...` (EMPTY!) |
| Admin slot | 0x0 |
| TotalSupply | 0 |
| TotalStaked | 0 |
| Native balance | 725 MON (~$290K) — deployment funds |

### The Trap

1. DefiLlama showed $65.5M TVL → seemed live
2. GitBook docs showed full ABI → seemed complete
3. Implementation at `0x7d2f8dc5...` had 24KB bytecode → seemed deployed
4. **BUT**: The proxy DELEGATECALLs to a DIFFERENT address (`0x58221220...`) which is EMPTY

### The Lesson

**Always trace the FULL delegation path:**
1. Read proxy storage slot 0 (implementation slot)
2. Check if THAT address has code
3. Check if proxy has custom delegation logic (DELEGATECALL in proxy bytecode)
4. Verify the ACTUAL implementation being used, not just "an" implementation

### Correct Reality Check (What We Should Have Done)

```python
# 1. Check TVL first
# 2. Check proxy bytecode for DELEGATECALL
# 3. Trace delegation target
# 4. Verify target has code
# 5. Check totalSupply
# 6. ONLY THEN start deep audit
```

**Time required: 5 minutes.**
**Time we spent: 2+ hours.**

---

## Multi-Chain Reality Check Script

When a protocol claims multi-chain deployment:

```bash
#!/usr/bin/env python3
"""Quick reality check across multiple chains"""
import json, subprocess

CHAINS = {
    "eth": "https://eth.drpc.org",
    "arb": "https://arb1.arbitrum.io/rpc",
    "base": "https://mainnet.base.org",
    "monad": "https://monad.drpc.org",
    "bnb": "https://bsc-dataseed.binance.org",
}

def check_chain(chain, rpc, address):
    # Check code
    r = subprocess.run(["curl", "-s", "-X", "POST", rpc,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"jsonrpc":"2.0","method":"eth_getCode",
        "params":[address,"latest"],"id":1})], capture_output=True, text=True)
    d = json.loads(r.stdout)
    code = d.get("result", "0x")
    size = len(code[2:])//2 if code != "0x" else 0
    
    # Check balance
    r2 = subprocess.run(["curl", "-s", "-X", "POST", rpc,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"jsonrpc":"2.0","method":"eth_getBalance",
        "params":[address,"latest"],"id":1})], capture_output=True, text=True)
    d2 = json.loads(r2.stdout)
    bal = int(d2.get("result", "0x0"), 16)
    
    return {"chain": chain, "code_size": size, "balance": bal}

address = sys.argv[1]
for chain, rpc in CHAINS.items():
    result = check_chain(chain, rpc, address)
    status = "LIVE" if result["code_size"] > 100 else "EMPTY"
    print(f"{chain}: {status} ({result['code_size']} bytes, {result['balance']} wei)")
```

---

## When to Walk Away

**Immediately skip if:**
1. Implementation bytecode < 100 bytes
2. TotalSupply = 0 AND TotalStaked = 0
3. Proxy delegates to empty address
4. No transactions in last 30 days (check Etherscan)
5. Website shows "coming soon" or "testnet"

**Exception:** If the protocol has a bug bounty program with a deadline, report the pre-launch issues (empty implementation, uninitialized proxy) as findings — but don't invest deep audit time.

---

## Reporting Pre-Launch Issues

If you encounter a pre-launch protocol with a bug bounty:

```markdown
## [P0] Protocol Not Yet Deployed — Empty Implementation

**Severity:** Informational (no funds at risk)
**Status:** Pre-launch

The protocol proxy at `0x...` delegates to implementation `0x...` which has no bytecode.
All calls to the proxy currently revert.

**Recommendation:**
- Deploy implementation contract before launch
- Initialize proxy with proper admin
- Verify all contracts on explorer
- Re-audit after deployment

**Note:** This is not exploitable (no funds), but should be fixed before mainnet launch.
```

---

## Integration with CDC Audit Methodology

**Before spawning multi-agent CDC audit:**

1. Run Reality Check (5 minutes)
2. If LIVE → spawn agents
3. If PRE-LAUNCH → skip or report pre-launch issues only
4. If UNCERTAIN → run extended reality check (check recent txs, social activity)

**Never spawn 4 agents on a pre-launch protocol.** The opportunity cost is too high.

---

*Methodology developed from aPriori audit session, July 2026 — lesson learned: always verify on-chain reality BEFORE deep analysis.*
