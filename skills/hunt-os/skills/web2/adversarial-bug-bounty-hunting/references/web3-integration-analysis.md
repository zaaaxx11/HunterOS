# Web3 Integration Analysis — Distinguishing Marketing from Real Blockchain Integration

**Discovered:** 2026-08-04 | **Target:** Everlyn.ai (AI Video Platform) | **Pattern:** Universal for Web2.5 SaaS claiming Web3

---

## THE PROBLEM

Many Web2 SaaS platforms add "Web3" features for marketing/narrative without real blockchain integration. **Assume nothing — verify everything.**

---

## VERIFICATION CHECKLIST

### 1. Smart Contract Address Discovery
```bash
# Search frontend for contract addresses
curl -s https://target.com | grep -oE '0x[a-fA-F0-9]{40}' | sort -u

# Search JS bundles
for js in $(curl -s https://target.com | grep -o '_next/static/chunks/[^"]*\.js'); do
  curl -s "https://target.com$js" | grep -oE '0x[a-fA-F0-9]{40}' | sort -u
done

# Search for ABI/interface
curl -s https://target.com | grep -iE 'abi|interface|ethers|web3|contract'
```

### 2. Payment Flow Analysis
```bash
# Test crypto payment endpoint
curl -X POST https://target.com/api/payment/crypto \
  -H "Content-Type: application/json" \
  -d '{"plan":"pro","currency":"USDT","chain":"ethereum"}'

# Check response for:
# - Direct contract interaction (user signs tx)
# - Payment gateway redirect (Coinbase Commerce, ShipAny, etc.)
# - Backend-only processing (Web2 payment + Web3 narrative)
```

### 3. Wallet Integration Depth
```bash
# Check wallet connect implementation
curl -s https://target.com | grep -iE 'eth_requestAccounts|wallet_addEthereumChain|switchChain|signTypedData|personal_sign'

# Test wallet connect
# 1. Connect MetaMask
# 2. Check if signature is verified on-chain or just stored off-chain
# 3. Check if wallet address is used for anything beyond display
```

### 4. On-Chain State Verification
```bash
# Check for:
# - NFT minting (ERC-721/1155) for videos/assets
# - ERC-20 token for points/credits
# - Contract calls for video generation
# - Event logs for user actions

# Query Etherscan/Polygonscan for contract interactions
# If zero transactions from platform contracts → NO REAL INTEGRATION
```

---

## REALITY CHECK MATRIX

| Feature Claimed | Verification Method | Real Integration? |
|-----------------|---------------------|-------------------|
| "Pay with USDT/USDC" | User signs tx to contract? | Gateway redirect = FAKE |
| "Earn points on-chain" | ERC-20 contract with balanceOf? | Off-chain DB = FAKE |
| "Videos on chain" | NFT mint per video? | CDN storage = FAKE |
| "Wallet connect" | Signatures used for auth? | Display only = FAKE |
| "Kaito integration" | On-chain profile linking? | OAuth/API = FAKE |

---

## EVERLYN.AI CASE STUDY (2026-08-04)

| Component | Finding |
|-----------|---------|
| **Contract Addresses** | **0 found** in frontend/JS bundles |
| **Payment Crypto** | Via **Coinbase Commerce / ShipAny** (Web2 gateway) |
| **Wallet Connect** | MetaMask only, **display only** |
| **Points/Credits** | Off-chain PostgreSQL (no ERC-20) |
| **Video NFTs** | **None** — files on CDN |
| **Kaito Integration** | OAuth/API linking, not on-chain |

**Verdict:** **Marketing layer only** — Web2 backend + Web3 payment gateway + wallet display.

---

## ATTACK VECTORS THAT STILL WORK

| Vector | Why It Works |
|--------|--------------|
| **Crypto Payment Manipulation** | Frontend sends `{amount, currency, wallet}` → backend charges via gateway → manipulate params |
| **Webhook Forgery** | Coinbase/ShipAny webhook endpoints often unauthenticated → fake `payment_confirmed` |
| **Refund Wallet Override** | Admin panel shows order IDs + emails → request refund to attacker wallet |
| **Wallet Signature Replay** | `personal_sign` for "login" → replay to other endpoints |

---

## DETECTION SCRIPT

```bash
#!/usr/bin/env python3
# web3_reality_check.py

import requests, re, sys

def check_web3_integration(target):
    print(f"[+] Checking {target} for REAL Web3 integration...")
    
    # 1. Frontend scan
    resp = requests.get(target, timeout=10)
    contracts = re.findall(r'0x[a-fA-F0-9]{40}', resp.text)
    print(f"  Contract addresses in HTML: {len(contracts)}")
    
    # 2. JS bundle scan
    js_files = re.findall(r'_next/static/chunks/[^"]*\.js', resp.text)
    for js in js_files[:5]:  # Sample first 5
        js_resp = requests.get(f"{target}{js}", timeout=5)
        js_contracts = re.findall(r'0x[a-fA-F0-9]{40}', js_resp.text)
        if js_contracts:
            print(f"  Contract in {js}: {js_contracts[:3]}")
    
    # 3. Payment endpoint test
    payment_resp = requests.post(f"{target}/api/payment/crypto", 
        json={"plan":"test","currency":"USDT"}, timeout=10)
    print(f"  Crypto payment endpoint: {payment_resp.status_code}")
    if "coinbase" in payment_resp.text.lower() or "shipany" in payment_resp.text.lower():
        print("  → Third-party gateway detected")
    
    # 4. Wallet connect check
    wallet_terms = ['eth_requestAccounts', 'wallet_addEthereumChain', 'signTypedData']
    for term in wallet_terms:
        if term in resp.text:
            print(f"  Wallet method found: {term}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://everlyn.ai"
    check_web3_integration(target)
```

---

## BUG BOUNTY REPORTING TEMPLATE

```
VULNERABILITY: Web3 Marketing Misrepresentation / Crypto Payment Manipulation
ENTRY: Unauthenticated
CHAIN: Frontend claims Web3 → Payment via Web2 gateway → Parameter manipulation → Financial impact
IMPACT: Charge $0.01 for $100 plan, refund to attacker wallet, bypass payment verification
POC: curl -X POST -d '{"amount":0.01,"plan":"pro"}' https://target.com/api/payment/crypto
EVIDENCE: No contract addresses, third-party gateway, wallet connect display-only
CONFIDENCE: PROVEN
MITIGATION: Implement real on-chain verification, sign payment intents, validate webhooks
```

---

## KEY INSIGHT

> **"Web3 integration = narrative until proven by contract address + transaction hash."**

**If you can't find a contract address on Etherscan with transactions from the platform, it's not Web3 — it's Web2 with a wallet connect button.**

---

## REFERENCES

- Etherscan API: https://etherscan.io/apis
- Coinbase Commerce Webhooks: https://commerce.coinbase.com/docs/api/#webhooks
- ShipAny Documentation: https://docs.shipany.io
- Next.js Wallet Connect Patterns: https://nextjs.org/docs/app/building-your-application/authentication