# Reference: dApp Infrastructure Analysis & Exploit Vectors

> Analyzing dApps that rely on external infrastructure (APIs, relayers, co-processors, wallet providers).
> These are often the real attack surface — not the smart contracts themselves.

---

## Common External Infrastructure Patterns

| Component | What It Does | Typical Attack Vectors |
|-----------|--------------|------------------------|
| **Swap Relayer / RFQ API** | Accepts signed intents, executes on-chain | Signature replay, unsigned execution, parameter injection |
| **Price / Data API** (DragonSwap, 0x, 1inch) | Provides pool data, quotes, token lists | Cache poisoning, IDOR on pool data, rate limit bypass |
| **Wallet Infrastructure** (Turnkey, Magic, Privy) | MPC/embedded wallets, transaction signing | API key exposure, session hijacking, cross-origin signing |
| **Indexer / Subgraph** | Query protocol state | GraphQL injection, DoS via complex queries, data staleness |
| **Bridge Relayer / Executor** | Listens for events, executes cross-chain | Message replay, validator compromise, finality assumption |
| **Co-processor / ZK Prover** | Off-chain computation with on-chain verification | Proof forgery, constraint system bugs, input validation |

---

## Saphyre.xyz Case Study (2026-07-19)

**Target**: Saphyre (SEI chain DEX / swap aggregator)
**Stack**: Vite.js SPA → Vercel → DragonSwap API + Swap Relayer + Turnkey
**Result**: Fortress — no exploitable vectors found

### Reconnaissance Methodology

```bash
# 1. Subdomain enumeration
subfinder -d saphyre.xyz -all -silent

# 2. HTTP probe
httpx -l subs.txt -ports 80,443 -tech-detect -status-code

# 3. JS bundle download & analysis
curl -s https://app.saphyre.xyz/ | grep -oP 'src="[^"]*\.js"' | head -1
# Download bundle
curl -s "https://app.saphyre.xyz/assets/index-<hash>.js" > bundle.js

# 4. Extract endpoints from bundle
grep -oP 'https?://[a-zA-Z0-9./\-_]+' bundle.js | sort -u
grep -oP 'swap-relayer|RFQ|settlement|permit2|turnkey' bundle.js
```

### Key Findings

| Component | Address / URL | Analysis |
|-----------|---------------|----------|
| **Swap Relayer** | `https://swap-relayer.saphyre.xyz/relay` | POST `/relay` with EIP-712 signed intent (`exactInput`/`exactOutput`) |
| **RFQ Settlement** | `0x6aE46fc725605f2eBb0126646f8318A069d328A2` | 7KB contract, has `owner()` but **no** `withdraw`, `transferOwnership`, `pause` |
| **Permit2** | `0xC6b7aC7Bbd8b456b67e8440694503cAC2Afb1d98` | Standard Uniswap Permit2 |
| **Steer Periphery** | `0xfF42cD42d8a5812CB38fb3C0720Dfc490912f48B` | 2KB wrapper |
| **DRG/WSEI Pool** | `0x481b7a494e565be3666ac34cca2fa9304611ef0a` | 11KB custom AMM, **no admin**, immutable |
| **DragonSwap API** | `https://sei-api.dragonswap.app/api/v1/pools` | Read-only pool data, CORS `*`, no auth |
| **Turnkey Wallet** | API paths in bundle (`/api/public/v1/...`) | MPC wallet infra, not directly exploitable |

### Contract Storage Decoding (Sei EVM RPC)

```bash
# RFQ Settlement - slot 0 = owner, slot 1 = trustedRouter, slot 2 = paused flag
cast storage 0x6aE46fc725605f2eBb0126646f8318A069d328A2 0 --rpc-url https://evm-rpc.sei-apis.com
# → 0x1eaef8dc95b0f966df2fde86d1a9be6f6890a6a4

# DRG/WSEI Pool - slots 5,6 = token0, token1; slots 8,10 = reserves
cast storage 0x481b7a494e565be3666ac34cca2fa9304611ef0a 5 --rpc-url ...
```

### Exploit Attempt Matrix

| Vector | Tested | Result |
|--------|--------|--------|
| Pool admin withdraw | ✅ | No owner/admin functions |
| RFQ settlement withdraw | ✅ | Owner exists but **no withdraw/pause/transferOwnership** |
| Swap relayer unsigned execution | ✅ | Requires valid EIP-712 signature from user |
| Swap relayer signature replay | ✅ | Nonce-based, chainId in domain separator |
| DragonSwap API cache poisoning | ✅ | Read-only GET endpoints |
| Turnkey session hijack | ❌ | Requires separate auth compromise |
| MEV/sandwich on DRG/WSEI | ✅ | Low liquidity, gas cheap, but no MEV bot surface |
| Bridge contract (if exists) | ⚠️ | Bridge page uses external providers |

### Why It's a Fortress

1. **Funds never sit in RFQ Settlement** — it's a stateless executor
2. **Pools are immutable** — no upgrade path, no admin keys
3. **All execution is user-signed** — relayer only broadcasts, cannot modify params
4. **External API is read-only** — no state-changing endpoints exposed

---

## Analysis Checklist for External Infrastructure

When you encounter a dApp using external services:

### 1. Map the Trust Boundaries
- [ ] What does the dApp trust the API for? (pricing, balances, allowlists)
- [ ] What does the relayer trust the user for? (valid signature, correct nonce)
- [ ] What does the wallet provider trust? (session, device, API key)

### 2. Test Each Boundary
- [ ] **API**: Parameter injection, IDOR, cache poisoning, rate limit bypass
- [ ] **Relayer**: Replay, unsigned execution, parameter mutation, nonce reuse
- [ ] **Wallet**: Cross-origin signing, session fixation, key extraction
- [ ] **Indexer**: GraphQL depth DoS, field aliasing, directive abuse

### 3. Check Contract ↔ Off-chain Consistency
- [ ] Does the contract enforce what the API claims? (e.g., "only admin can call" → check contract)
- [ ] Can the off-chain component be bypassed by calling contract directly?
- [ ] Are there functions in contract that off-chain component NEVER calls? (dead code = potential bug)

### 4. Verify Fund Flow
- [ ] Where do user funds actually sit? (pool, settlement contract, relayer, user wallet)
- [ ] Can the relayer/operator move funds without user signature?
- [ ] Is there a timelock / multisig / DAO controlling upgrades?

---

## Tooling for This Class of Analysis

```bash
# JS Bundle analysis
npx @babel/parser bundle.js --plugins=typescript,jsx  # parse minified
# or use: grep, strings, custom Python regex

# Contract storage
cast storage <addr> <slot> --rpc-url <rpc>
cast code <addr> --rpc-url <rpc> | cast 4byte-decode  # if verified

# API testing
curl -X POST <relayer> -H "Content-Type: application/json" -d '{}'
curl -H "Origin: https://evil.com" -v <api>  # CORS check

# EIP-712 signature verification
# Use foundry: vm.sign(keystore, digest) → test relayer acceptance
```

---

## Reporting Template for Infrastructure Findings

```
## [Severity] <Component> - <Vulnerability>

**Component**: Swap Relayer API / RFQ Settlement Contract / DragonSwap API / etc.
**Type**: API / Relayer / Wallet / Indexer / Contract-Offchain Inconsistency
**CVSS**: X.X (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N)

**Description**: 
The <component> accepts <input> without <validation>, allowing <attack>.

**Reproduction**:
1. <Step 1>
2. <Step 2>
3. Observe <result>

**Impact**: 
- Direct fund theft: $X
- User data exposure: Y users
- Protocol disruption: Z downtime

**PoC**: <code or curl command>
**Remediation**: <specific fix>
```