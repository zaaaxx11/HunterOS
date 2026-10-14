# Live EVM Token-Contract Recon — BSC $LYN (Everlyn) 2026-08-13

Session detail for `adversarial-bug-bounty-hunting` → "LIVE EVM TOKEN-CONTRACT
RECON VIA RAW RPC". Target: Everlyn Token (LYN) on BSC, provided by operator as a
geckoterminal pool link + contract address (CA).

## Inputs given by operator
- Pool:  https://www.geckoterminal.com/bsc/pools/0x302642976506d247c7017b85ddc89e3956f96ba1
- Token: 0x302dfaf2cdbe51a18d97186a7384e87cf599877d

## Market context (geckoterminal public API, no key)
```
GET https://api.geckoterminal.com/api/v2/networks/bsc/tokens/<CA>
GET https://api.geckoterminal.com/api/v2/networks/bsc/pools/<pool>
```
Result: name Everlyn Token, symbol LYN, 18 decimals, supply 1B, FDV ~$35.1M,
MC ~$7.3M, pool LYN/USDT 0.3% with ~$29.6K reserve. Liquidity is THIN — any
adversarial plan must account for huge slippage; also means the token's value is
almost purely narrative/trust.

## Raw-RPC probes (bsc-dataseed.binance.org, no key)

| Probe | Selector | Result | Verdict |
|---|---|---|---|
| eth_getCode | — | 2,433 bytes | minimal standard contract, not proxy-heavy |
| selector scan | — | transfer, transferFrom, approve, balanceOf, allowance, totalSupply, name, symbol, decimals, mint, burn, owner, transferOwnership, renounceOwnership | OpenZeppelin ERC20 + Ownable |
| owner() | 0x8da5cb5b | 0x0000...0000 | **ownership renounced** — no admin mint/pause lever |
| paused() | 0x5c975abb | `execution reverted: 0x` | no live pause switch |
| pool slot0() | 0x3850c7bd | returned sqrtPriceX96 etc. | live V3 pool |

**Contract-side verdict: CLEAN.** No honeypot, no backdoor, renounced. Stated
honestly to operator and pivoted to off-chain surface instead of fabricating a
contract bug. (Note: `mint` selector exists in bytecode from OZ template, but
with owner renounced it is unreachable — verify caller-auth before alarming.)

## Web2 → token kill-chain (the actual finding value)
The token contract was clean, but the same session proved the everlyn.ai backend
accepts pre-auth job orders via hash(email) IDOR (see
`nextjs-authn-authz-probing` §14-§20 reference). Extensions proven this session:

1. **Ghost-account acceptance**: `POST /order` with
   `user_id=ghost-never-registered-operator@gmail.com` (never registered) →
   `{"order_id":"6a7ccd6ce96345e804e5c094","message":"Ok"}`. Backend never checks
   user existence → **infinite sybil identity space**.
2. **Points→TGE framing**: UI strings promise "earn points on every video",
   "your videos on chain", "use $LYN autonomous agents"; roadmap (mined from
   about-page RSC flight data) describes "Lyn Protocol" storing video latents
   on-chain Q3-Q4 2026. If off-chain points convert to $LYN at TGE, the pre-auth
   order IDOR = **airdrop supply dilution at scale**.
3. **Cosmos testnet dead**: rpc/api.testnet.everlyn.ai → HTTP 000. Reported as
   infra finding, not exploited.

## Roadmap mining trick
Marketing/roadmap copy lives in the Next.js RSC flight payload even when the
visible page is thin. Extract:
```bash
curl -s -L https://TARGET/en/about -o /tmp/about.html
python3 - <<'EOF'
import re
h = open('/tmp/about.html').read()
p = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', h, re.S)
full = ''.join(x.encode().decode('unicode_escape', errors='replace') for x in p)
for kw in ['token','agent','on-chain','protocol','roadmap']:
    for m in re.finditer(kw, full, re.I):
        print(full[max(0,m.start()-200):m.start()+280][:420]); print('---')
        break
EOF
```
This is how "Lyn Protocol... autonomous Web3 video agents that generate,
transact, and collaborate on-chain" was recovered — the token's promised utility,
straight from the horse's flight data.

## Operator-correction worth remembering
Operator asked "admin ada token $LYN, apakah ada integrate nya?" — the instinct
to chase ONLY the contract would have missed the point. The integration that
matters is **economic**: off-chain points backend ↔ future token conversion.
When a web3 project has a web2 backend, always map the value flow between them
before declaring "contract clean, nothing to do."
