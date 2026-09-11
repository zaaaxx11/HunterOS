# Crypto Payment Flow Analysis — ShipAny Integration (Not Smart Contracts)

**Validated:** 2026-08-04 on everlyn.ai

## Executive Summary

**"Web3" payment (USDT/USDC multi-chain) = ShipAny hosted checkout, NOT smart contracts.**

Zero contract addresses, ABIs, or on-chain logic found in frontend. The entire payment flow is Web2 with a Web3 payment gateway.

## Payment Flow Architecture

```
USER CLICKS "PAY WITH CRYPTO"
         ↓
FRONTEND → /api/checkout (POST) with {plan, paymentMethod}
         ↓
BACKEND → ShipAny API (create checkout session)
         ↓
SHIPANY → Returns hosted checkout URL (ShipAny domain)
         ↓
USER → Redirected to ShipAny → Pays with MetaMask (USDT/USDC)
         ↓
SHIPANY → Webhook to Everlyn backend (order confirmed)
         ↓
BACKEND → Updates credits in DB → User gets access
```

## Key Findings

| Component | Reality |
|-----------|---------|
| **Payment Processor** | ShipAny (https://shipany.io) |
| **Payment Methods** | Stripe (Card) + Crypto via ShipAny |
| **Crypto Currencies** | USDT/USDC on Ethereum, BSC, Polygon, Arbitrum, etc. |
| **Smart Contracts** | **NONE** — Zero addresses, ABIs, on-chain logic |
| **Wallet Connect** | Standard MetaMask `eth_requestAccounts` only |
| **Refund Flow** | ShipAny API → wallet address provided by user |

## Endpoints Discovered

| Endpoint | Type | Status |
|-----------|------|--------|
| `/api/checkout` | Regular API | ✅ Exists (405 GET, 200 POST) — strict validation |
| `/api/refund` | Regular API | ✅ Exists (405 GET, 200 POST) — strict validation |
| `/api/webhook/shipany` | Webhook | ❌ Not found (handled by ShipAny dashboard) |
| `/stripe_success` | Success page | ❌ 404 |
| `/payment/success` | Success page | ❌ 404 |

## Refund Flow Details (from RSC messages)

```javascript
// User selects refund type
"refund_by_card": "Refund by Card"
"refund_by_crypto": "Refund by Crypto"

// Crypto refund requires wallet address
"refund_crypto_info": "For crypto payments, please update your preferred wallet address on our website as soon as possible so we can send your refund there."

// Bonus reward for updating wallet
"reward_description": "Please update your MetaMask wallet address to receive an additional reward as compensation within a few days."
```

## Attack Vectors

| Vector | Feasibility | Requirements |
|--------|-------------|--------------|
| **Refund Wallet Manipulation** | HIGH | Order ID + bypass auth + attacker wallet |
| **Checkout Amount Tampering** | MEDIUM | `/api/checkout` param schema reverse engineering |
| **Webhook Replay/Forge** | MEDIUM | ShipAny webhook secret |
| **Wallet Reward Abuse** | MEDIUM | Social engineering |

## Why Smart Contract Exploits Won't Work

| Assumption | Reality |
|------------|---------|
| "USDT/USDC on-chain = smart contract" | ShipAny custody → off-chain settlement |
| "Can exploit payment contract" | No contract — ShipAny API |
| "Can manipulate on-chain logic" | All logic in Web2 backend |
| "Refund via smart contract" | Refund = ShipAny API call → wallet |

## Detection Commands

```bash
# Check for contract addresses in frontend
curl -s https://everlyn.ai | grep -o '0x[a-fA-F0-9]\{40\}'

# Check for ethers.js/web3.js contract interaction
curl -s https://everlyn.ai/_next/static/chunks/main-app-*.js | \
  grep -i 'ethers\|web3\|contract\|abi\|provider.*contract'

# Check payment page for contract interaction
curl -s https://everlyn.ai/pricing | \
  grep -i 'contract\|0x[a-fA-F0-9]\{40\}\|abi\|ethers'
```

## Evidence of No Smart Contracts

```bash
# 0 contract addresses found
curl -s https://everlyn.ai | grep -c '0x[a-fA-F0-9]\{40\}'
# Returns: 0

# 0 ABI references
curl -s https://everlyn.ai/_next/static/chunks/main-app-*.js | \
  grep -c -i 'abi\|ethers\.Contract\|web3\.eth\.Contract'
# Returns: 0

# Payment flow uses ShipAny
curl -s https://everlyn.ai | grep -i 'shipany'
# Returns: "orders paid with ShipAny"
```

## Conclusion

**The "Web3" integration is a marketing layer.** The actual payment engine is Web2 (ShipAny). Attack surface = ShipAny API integration, not blockchain.

## References

- ShipAny: https://shipany.io
- Validated on everlyn.ai production
- Zero smart contract artifacts in frontend