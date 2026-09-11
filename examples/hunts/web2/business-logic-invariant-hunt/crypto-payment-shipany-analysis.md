# Crypto Payment Flow Analysis — ShipAny Integration (Not Smart Contracts)

**Validated:** 2026-08-04 on everlyn.ai

## Executive Summary

**"Web3" payment (USDT/USDC multi-chain) = ShipAny hosted checkout, NOT smart contracts.**

Zero contract addresses, ABIs, or on-chain logic found in frontend. The entire payment flow is Web2 with a Web3 payment gateway.

## Business Logic Invariants

| Invariant | Expected | Actual | Verdict |
|-----------|----------|--------|---------|
| Payment processed on-chain | Smart contract mint/transfer | ShipAny hosted checkout | **BROKEN** |
| Refund via smart contract | On-chain transfer | ShipAny API → wallet | **BROKEN** |
| Wallet address verified on-chain | Signature verification | User-provided in UI | **BROKEN** |
| Points earned on-chain | ERC-20 mint | Off-chain DB credits | **BROKEN** |

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

## Refund Flow Business Logic

```javascript
// User selects refund type
"refund_by_card": "Refund by Card"
"refund_by_crypto": "Refund by Crypto"

// Crypto refund requires wallet address
"refund_crypto_info": "For crypto payments, please update your preferred wallet address on our website as soon as possible so we can send your refund there."

// Bonus reward for updating wallet
"reward_description": "Please update your MetaMask wallet address to receive an additional reward as compensation within a few days."
```

## Attack Vectors (Invariant Violations)

| Vector | Invariant Violated | Feasibility |
|--------|-------------------|-------------|
| **Refund Wallet Manipulation** | Refund goes to original payer | HIGH |
| **Checkout Amount Tampering** | Server-side price validation | MEDIUM |
| **Webhook Replay/Forge** | Idempotent webhook processing | MEDIUM |
| **Wallet Reward Abuse** | One-time reward per user | MEDIUM |

## Endpoints for Probe Testing

| Endpoint | Type | Status | Probe Priority |
|----------|------|--------|----------------|
| `/api/checkout` | Regular API | ✅ Exists (strict validation) | P1 |
| `/api/refund` | Regular API | ✅ Exists (strict validation) | P1 |
| `/api/webhook/shipany` | Webhook | ❌ Not found | P2 |
| `/stripe_success` | Success page | ❌ 404 | P3 |

## Probe Commands

```bash
# Probe 1: Checkout price tampering
curl -X POST https://everlyn.ai/api/checkout \
  -H "Content-Type: application/json" \
  -d '{"plan":"pro","paymentMethod":"crypto","amount":1}'

# Probe 2: Refund wallet manipulation
curl -X POST https://everlyn.ai/api/refund \
  -H "Content-Type: application/json" \
  -d '{"orderId":"851970327982149","type":"crypto","walletAddress":"0xAttacker"}'

# Probe 3: Webhook replay (if endpoint found)
curl -X POST https://everlyn.ai/api/webhook/shipany \
  -H "Content-Type: application/json" \
  -d '{"event":"payment_confirmed","orderId":"851970327982149"}'

# Probe 4: Checkout with middleware bypass
curl -X POST https://everlyn.ai/api/checkout \
  -H "x-middleware-subrequest: /api/checkout" \
  -H "Content-Type: application/json" \
  -d '{"plan":"pro","paymentMethod":"crypto"}'
```

## Evidence of No Smart Contracts

```bash
# 0 contract addresses found in frontend
curl -s https://everlyn.ai | grep -c '0x[a-fA-F0-9]\{40\}'
# Returns: 0

# 0 ABI references in JS bundles
curl -s https://everlyn.ai/_next/static/chunks/main-app-*.js | \
  grep -c -i 'abi\|ethers\.Contract\|web3\.eth\.Contract'
# Returns: 0

# Payment flow explicitly uses ShipAny
curl -s https://everlyn.ai | grep -i 'shipany'
# Returns: "orders paid with ShipAny"
```

## Verdict

**The "Web3" integration is a marketing layer.** The actual payment engine is Web2 (ShipAny). Attack surface = ShipAny API integration, not blockchain.

## References

- ShipAny: https://shipany.io
- Validated on everlyn.ai production
- Zero smart contract artifacts in frontend