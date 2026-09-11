---
name: on-chain-forensics
description: "post-incident on-chain forensics"
category: security
tags: [blockchain, forensics, defi, recon, smart-contracts, rpc, base, ethereum]
---

# On-Chain Forensics & Blockchain Recon

## Purpose
Systematic on-chain forensics for finding contracts, tracing transactions, analyzing TVL flows, discovering deployers, and mapping protocol architectures without relying on centralized APIs.

## When to Use
- Finding contracts for a protocol with no public GitHub/verified contracts
- Tracing TVL flows to find vaults, strategies, prize pools
- Discovering deployers and factory contracts
- Mapping protocol architecture from on-chain data only
- Finding hidden backdoors, admin keys, upgrade paths
- Tracing exploiter funds, MEV, flash loan attacks

## Methodology

### Phase 0: Chain Identification (CRITICAL — DO FIRST)
When DexScreener or any API reports a chain name, NEVER trust the label. Always verify:
1. `cast chain-id --rpc-url <RPC>` to get the actual chain ID
2. Cross-reference: DexScreener "robinhood" ≠ HyperEVM. It can be Robinhood Chain (4663), an Arbitrum Orbit L3
3. Check protocol docs for chain info (website /docs page often has RPC + chain ID)
4. For chains with no block explorer: rely on `cast code` + `cast call` via RPC directly

### Phase 1: Protocol Discovery
1. **DeFiLlama/DefiPulse** → Get protocol name, chains, TVL history
2. **Website/App** → Find "Launch App", "Deposit", "Stake" buttons → trace to contract
3. **Website/Docs pages** → Watch for chain ID, RPC endpoint, contract addresses in plain text
4. **Twitter/Docs** → Search for contract announcements, deployment tweets
5. **GitHub** → Search org/repo for contract addresses in README, deploy scripts, hardhat.config
6. **DexScreener token search** → `https://api.dexscreener.com/latest/dex/search?q=<protocol>` for DEX pairs
7. **DexScreener token lookup** → `https://api.dexscreener.com/latest/dex/tokens/<address>` for specific pairs

### Phase 1b: Squatter/Impersonator Detection
After finding addresses via DexScreener or block explorers:
1. Run `cast code <addr>` on EVERY address — if it returns `0x`, the contract has ZERO bytecode
2. Zero bytecode tokens are **squatters/impersonators** — not the real protocol
3. Check `cast call <addr> "symbol()"` and `"name()"` — squatters may return matching name but have empty code
4. Only addresses with real bytecode (non-0x return) are usable
5. Report squatter addresses separately from real ones — label clearly as "IMPOSTER"

### Phase 2: On-Chain Discovery (RPC Only)
```bash
# 1. Find latest block
eth_blockNumber

# 2. Scan recent blocks for contract creations
eth_getBlockByNumber [latest, true] → filter to == '' (contract creation)

# 3. Trace USDC/Token transfers to find vaults
# Look for transfer() calls to contracts holding large balances

# 5. Check contract code for patterns
eth_getCode [address] → analyze selectors:
- ERC4626: deposit(), withdraw(), mint(), redeem()
- PrizePool: awardPrizes(), claimPrizes()
- Vault: deposit(), withdraw(), mint(), redeem()
- Factory: createVault(), createPool()
```

### Phase 3: Contract Analysis
```bash
# Get verified source if available
# BaseScan/Etherscan: /api?module=contract&action=getsourcecode

# If unverified: decompile
cast etherscan-source <addr>  # if verified
heimdall decompile <addr>     # if not
```

### Phase 3b: Implementation Divergence Detection (PUSH4 Selector Extraction)
When you have source code but the deployed implementation may have been upgraded, extract all function selectors from bytecode to detect what's ACTUALLY deployed:

```bash
cast code $IMPL --rpc-url $RPC | python3 -c "
import sys
code = sys.stdin.read().strip()
if code.startswith('0x'): code = code[2:]
selectors = set()
i = 0
while i < len(code) - 10:
    if code[i:i+2] == '63':
        sel = code[i+2:i+10]
        selectors.add(sel)
        i += 10
    else:
        i += 2
for s in sorted(selectors):
    print(f'0x{s}')
" | while read sel; do
    cast 4byte-decode "$sel" 2>&1
done
```

Compare extracted selectors against source code imports. New selectors = upgraded features. Missing selectors = removed/renamed. Flag divergence as CRITICAL — the audited source is NOT what's deployed.

**Cross-chain verification:** When the same proxy address exists on multiple chains, query each chain's implementation. Differences reveal upgrade history (e.g., Ethereum = original 4B supply, BSC = upgraded v3.0.0 with 1B supply + TimelockController + burn + mint tracking).

See `examples/hunts/web3/on-chain-forensics/references/push4-selector-extraction-divergence.md` for full Naoris BSC case study and pitfalls.

### Key RPC Calls
```json
// Latest block
{"method":"eth_blockNumber"}

// Block with full txs
{"method":"eth_getBlockByNumber","params":["0x...",true]}

// Contract code
{"method":"eth_getCode","params":["0x...","latest"]}

// Contract call (view)
{"method":"eth_call","params":[{"to":"0x...","data":"0x..."},"latest"]}

// Storage slot
{"method":"eth_getStorageAt","params":["0x...","0x0","latest"]}

// Token balance
{"method":"eth_call","params":[{"to":"USDC","data":"0x70a08231000000000000000000000000<addr>"},"latest"]}

// Event logs (Transfer)
{"method":"eth_getLogs","params":[{"fromBlock":"0x...","toBlock":"latest","address":"USDC","topics":["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]}]}
```

### Key Function Selectors
| Function | Selector | Use Case |
|----------|----------|----------|
| `transfer(address,uint256)` | `0xa9059cbb` | ERC20 transfers |
| `deposit(uint256,address)` | `0xd0e30db0` | ERC4626 deposit |
| `withdraw(uint256,address,address)` | `0x2e1a7d4d` | ERC4626 withdraw |
| `mint(address,uint256)` | `0x40c10f19` | Mint shares |
| `burn(address,uint256)` | `0x89afcb44` | Burn shares |
| `transferOnLiquidation` | `0x...` | Liquidation transfer |
| `balanceOf` | `0x70a08231` | ERC20 balance |
| `totalSupply` | `0x18160ddd` | Total supply |
| `depositRewards` | `0x...` | Reward distribution |

### Base Chain Specific
- **RPC**: `https://mainnet.base.org` or `https://base.llamarpc.com`
- **Chain ID**: 8453 (0x2105)
- **USDC**: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- **BaseScan**: `https://basescan.org` (API V2 deprecated)

### Hyperliquid / Robinhood Ecosystem
- **HyperEVM**: chain ID 999, RPC `https://rpc.hyperliquid.xyz/evm`
- **Robinhood Chain**: chain ID 4663, RPC `https://rpc.mainnet.chain.robinhood.com`
  - Resolves to `customer-origin.offchainlabs.com` (Arbitrum Orbit stack)
  - RPC requires `https://` prefix — bare hostname fails with `cast`
  - WETH: `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`
  - No public block explorer exists — DexScreener is the primary discovery tool
  - **Chain name confusion pitfall**: DexScreener labels this chain "robinhood" — do NOT assume this means Hyperliquid/HyperEVM (999). Always `cast chain-id` to confirm. Many "robinhood" DexScreener results are on chain 4663, not 999.

## Common Patterns


### Frontend-First Protocols (No On-Chain Vaults)
Some protocols use a **non-custodial frontend** pattern where:
- No vault/staking/lending contracts exist on-chain
- Users interact directly with a DEX (e.g., Uniswap) for token swaps
- The protocol's "desk" or "lending facility" is managed server-side, not via smart contracts
- The only on-chain artifact is the token contract + DEX pairs

**Detection signs:**
- `cast code` on all suspected vault/staking addresses returns `0x`
- Website describes "desk" or "margin" without contract addresses
- No factory, vault, or pool contracts in JS bundles
- Only DEX pairs and token contracts verified

**What to do:**
1. Report that no vault/staking/lending contracts exist on-chain
2. Pivot to web/app audit — the attack surface is the frontend + backend API
3. The token contract + DEX pairs are the only on-chain targets

### Prize Savings (PoolTogether V5 style)
```
PrizePool → PrizePoolFactory → PrizePoolFactory.createPrizePool()
Vault → VaultFactory → VaultFactory.createVault()
TwabController → TWAB for prize eligibility
PrizeDistributor → claimPrizes()
```

### ERC4626 Vault
```
deposit(uint256 assets, address receiver) → shares
withdraw(uint256 assets, address receiver, address owner) → assets
mint(uint256 shares, address receiver) → assets
redeem(uint256 shares, address receiver, address owner) → assets
```

### Factory Pattern
```
createVault(underlying, name, symbol) → vault
createPool(prizeToken, vault) → pool
```

## References
- `examples/hunts/web3/on-chain-forensics/references/push4-selector-extraction-divergence.md` — PUSH4 selector extraction, implementation divergence detection, cross-chain comparison (Naoris BSC case study)
- `references/base-chains.md` — Base chain RPCs, addresses, and forensics patterns
- `examples/hunts/web3/on-chain-forensics/references/yuzu-money-forensics.md` — Yuzu Money case study
- `examples/hunts/web3/on-chain-forensics/references/hyperliquid-robinhood-ecosystem.md` — HyperEVM and Robinhood Chain RPCs, chain IDs, and chain confusion pitfall
- `examples/hunts/web3/on-chain-forensics/references/squatter-token-detection.md` — Detecting squatter/impersonator tokens on DexScreener

## Target Sessions (Gimo 0G / Camp / Sonic FlyingTulip)

(Per-target session write-ups — the Gimo Finance 0G LSD trust graph (2026-08-12), the Camp Network 2026-08 dead-RPC Blockscout-proxy workaround, the Sonic FlyingTulip FT OFT case (2026-08-08), and the FlyingTulip 7127 vault-chain/Safe-nesting analysis (2026-08-09) — are preserved verbatim at examples/hunts/web3/on-chain-forensics/target-sessions.md, with their case refs under examples/hunts/web3/on-chain-forensics/references/.)

## Signature-Mint Contract Recon (IpNFT/Origin pattern — 2026-08)

Contracts with `mintWithSignature(... bytes signature)` gated by `SignatureChecker.isValidSignatureNow(signer || owner)`:
1. The EIP-712 math is usually solid (domain sep = name+version+chainId+verifyingContract → no cross-chain replay).
2. **The real bug class is key management**: read `signer()` on-chain via `eth_call` selector `0x238ac933`, then `eth_getCode(signer)`. If result is `0x` → signer is an **EOA** = single-key SPOF. One phished key = unlimited free mints. Flag as centralization-critical even though code is clean.
3. Check `owner()` too — if it's a Safe, pull `getOwners()` (`0xa0e67e2b`) + `getThreshold()` (`0xe75235b8`) to report M-of-N.
4. Batch helper contracts that do `transferFrom(user)→approve(spender)→call` pattern: check whether the success path leaves residual allowance. Camp's BatchOperations was safe (allowance consumed exactly + `approve(0)` on revert), but verify per-target.
5. Dispute/governance modules: read `disputeQuorum`, `disputeBond`, `stakingThreshold`, `disputeCounter` on-chain. `quorum=0` = disputes auto-fail (griefing vector, not theft). Don't inflate severity.

## Tools
- `cast` (Foundry) - RPC calls, abi-encode, calldata
- `cast etherscan-source` - fetch verified source
- `heimdall` - decompile unverified contracts
- `cast logs` - query event logs
- `cast tx` - trace transaction
- `cast storage` - read storage slots
- `cast call` - simulate calls
- `cast tx --trace` - trace execution

## Custom Error Brute Force via cast disassemble (2026-08-09)
Private wrappers use unknown 4byte selectors (`0x3d515569`, `0x5501aad8`). Resolve via:
```bash
cast disassemble 0x<code> | grep -B25 "3d515569"  # shows preamble: SLOAD 0x0/CALLER EQ + SLOAD 0x04 mask + keccak 0x03 role check → JUMPI → PUSH32 error → REVERT
```
Two errors 40 bytes apart (`0x138c` gap) share same preamble = two `onlyRole` branches. `0x4e487b71` panic = bounds check (decode 1/2/3/4 in same contract). If `cast disassemble` shows `PUSH32 <selector> + PUSH0 MSTORE + PUSH1 0x04 REVERT` without `4byte.directory` hit → private `AccessControlUnauthorizedAccount` variant — map to `hasRole` pattern instead of string.

## L2 Execution Client Audit Patterns (ethrex, op-geth, arbitrum-node)

When auditing L2 execution clients (Plasma, Optimism, Arbitrum, etc.):

### 1. Hardcoded Keys in CLI Defaults (CRITICAL)
Private keys hardcoded as `default_value` in CLI argument definitions are **production defaults**, not test keys. They get used if the node operator doesn't override via env vars.

**Detection**:
```bash
grep -rn 'default_value = "0x' --include="*.rs" --include="*.go" --include="*.toml"
# Look for 64-char hex strings after default_value
```

**Verification**:
1. Derive address from private key (secp256k1)
2. Check on-chain nonce: `eth_getTransactionCount(address, "latest")`
3. Nonce > 0 = key is **actively used in production**

**EIP-7702 Delegation Detection**:
```python
# If eth_getCode returns exactly 23 bytes:
code = "0xef0100" + delegated_address
# This is an EIP-7702 delegated account
# delegated_address = code[4:24] (20 bytes after 0xef0100)
# Proves the hardcoded key's address is ACTIVE and delegated
```

### 2. Admin Server Without Auth (CRITICAL)
L2 clients often expose admin endpoints for operator control. Check for missing auth middleware:

```bash
grep -rn "with_state\|middleware\|auth\|layer" --include="*.rs" crates/*/sequencer/
# Look for routes without auth middleware
```

**Common exposed endpoints**:
- `/committer/start`, `/committer/stop` — control L1 batch submissions
- `/state-updater/stop-at/{block}` — freeze chain state
- `/sequencer/start`, `/sequencer/stop` — control sequencer

**Default bind**: Often `127.0.0.1:5555` (localhost-only), but docker-compose may expose to `0.0.0.0`.

### 3. JWT Validation Disabled (HIGH)
```bash
grep -rn "validate_exp\|validation\." --include="*.rs" crates/networking/
# Look for validate_exp = false
```

### 4. Public RPC Sensitive Methods (MEDIUM)
Probe public RPC for exposed methods:
```python
sensitive_methods = [
    "txpool_content",      # Pending tx details
    "txpool_status",       # Mempool size
    "debug_traceTransaction",  # Internal execution trace
    "admin_nodeInfo",      # Node info
    "net_peerCount",       # Network topology
    "web3_clientVersion",  # Version disclosure
]
```

### 5. Consensus Config Exposure (MEDIUM)
Check node-templates for leaked infrastructure info:
- BLS public keys (validator identities)
- Bootstrap node hostnames
- Internal service names (`mainnet-execution:8551`)
- JWT secret paths

### 6. Genesis Treasury Analysis
Genesis files contain pre-funded addresses. Check on-chain:
```bash
# For each genesis alloc address:
eth_getBalance(address, "latest")
eth_getTransactionCount(address, "latest")
eth_getCode(address, "latest")  # EOA vs Contract
```

**Coinbase address**: Receives all tx fees. Accumulates value over time. If hardcoded committer key controls L1 commitments, attacker can redirect fee accumulation.

See `examples/hunts/web3/on-chain-forensics/references/plasma-ethrex-audit-2026-08.md` for full case study.

## Indonesian Communication Style
- Tone: Casual but technical (lo/gue, bro, sis)
- Format: Bullet points, tables, code blocks
- Tone markers: 😎, 🔥, 💀, 😘
- Direct: No fluff, straight to technical meat
- Security mindset: Assume breach, verify everything

## Nyantai Brutal Recon (Operator Preference)
The operator explicitly prefers **throttled but exhaustive** on-chain recon: "nyantai aja, biar gausah request API kecepetan, tapi tetep brutal carinya".
- `eth_getLogs`: max **100k-block chunks** on Sonic (`rpc.soniclabs.com`), **0.7-1.2s delay** between calls. >400k window times out. Always use 100k + sleep 1.2s for expanding windows (800k→1.6M). Save holders to `/tmp/holders_*.txt` checkpoint every chunk.
- `eth_call` balanceOf probing: **0.6-0.7s throttle** per address, checkpoint every 10-15 addresses to `/tmp/bal_*.json` (merge-friendly JSON list of [addr, bal]).
- **Sequential phases**: User says "coba 1 dulu deh, baru 2" — never run holder scan + decompile + fuzz in parallel. Finish phase 1 (holder top), then phase 2 (decompile), then phase 3 (fuzz). Parallel RPC bursts trigger 403/429 on Sonic and lose data.
- **Resume-friendly**: Always write `holders_*.txt` + `bal_*.json` so a timeout can resume from `seen` set, not from zero.

## Sequential Execution Protocol (1 dulu baru 2)
When the operator says "coba 1 dulu" → execute ONLY the first requested task to completion and report, wait for explicit "lanjut 2" before starting the second. Do not batch both into one turn. This applies to decompile (1) then fuzz (2), or holder scan (1) then expand (2).

## Santai Explanation After Audit (User Preference)
When the operator asks "jelasin santai" → switch to casual Indonesian lo/gue, table + bullet points, short sentences, no formal CDC report format. Keep it sopan, token-efficient, but include critical tables (holder top, vault vs pool). Do not revert to English formal audit format.

## Proxy Bytecode Analysis — Extracting DELEGATECALL Targets

When a proxy uses DELEGATECALL, the target address is encoded directly in the proxy bytecode. Extract it:

```python
code_hex = <proxy_code_without_0x>
for i in range(len(code_hex) - 2):
    if code_hex[i:i+2] == 'f4':  # DELEGATECALL opcode
        for j in range(i-2, max(i-64, 0), -2):
            if code_hex[j:j+2] == '73':  # PUSH20
                addr = code_hex[j+2:j+42]
                if all(c in '0123456789abcdef' for c in addr):
                    print(f"DELEGATECALL -> 0x{addr}")
```

Key distinction: EIP-1967 impl slot may be EMPTY or STALE. The actual DELEGATECALL target in proxy bytecode is the REAL delegation target. These two can point to different addresses.

## Multi-Chain Zero-Bytecode Reality Check

When a protocol displays a contract address (e.g. in a UI banner as "CA") but `eth_getCode` returns `0x`, you MUST check ALL relevant chains before concluding the address is fake:

```bash
# Check on each chain individually
cast code 0x... --rpc-url https://eth.llamarpc.com     # Ethereum
cast code 0x... --rpc-url https://base.llamarpc.com    # Base (8453)
cast code 0x... --rpc-url https://arb1.arbitrum.io/rpc  # Arbitrum (42161)
cast code 0x... --rpc-url https://bsc-dataseed.binance.org # BSC
cast code 0x... --rpc-url https://mainnet.optimism.io    # Optimism
cast code 0x... --rpc-url https://polygon-rpc.com       # Polygon
```

**If ALL return `0x`:**
- This is NOT a live smart contract
- It's a **placeholder/marketing address** displayed in UI
- Protocol is likely a **non-custodial aggregator frontend** — no on-chain funds
- PIVOT to Web/API exploitation
- Check if the contract address appears on non-EVM chains (Solana, TRON) — use block explorers

**If some chains return non-0x:**
- The contract is deployed on that specific chain
- Record the chain, bytecode length, and first few bytes (proxy patterns)
- Cross-reference with protocol documentation

**What to do next when bytecode = 0x everywhere:**
1. This rules out smart contract exploitation — no funds on-chain to steal
2. The value is in the backend: user data, API keys, ChangeNOW account, Privy management
3. Pivot to web/app/API audit: auth bypass, Host Header injection, server-side injection