# Hyperliquid / Robinhood Ecosystem — On-Chain Reference

## Chain Identification

### HyperEVM (Hyperliquid's EVM Layer)
- **Chain ID**: 999
- **RPC**: `https://rpc.hyperliquid.xyz/evm`
- **Explorer**: `https://hyperliquid.vescan.com/` (may be unavailable)
- **Blockscout**: `https://hyperliquid.blockscout.com/` (may 503)
- **Known issue**: Privy RPC (`https://hyperevm-mainnet.rpc.privy.systems`) returns 404 — use the main RPC

### Robinhood Chain (Arbitrum Orbit L3)
- **Chain ID**: 4663
- **RPC**: `https://rpc.mainnet.chain.robinhood.com`
- **Resolution**: DNS → `customer-origin.offchainlabs.com` (Arbitrum Orbit)
- **WETH**: `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73` (18 decimals, ~20.3K supply as of July 2026)
- **Explorer**: NO public block explorer — use DexScreener API for trading data
- **Note**: `cast` requires `https://` prefix — bare hostname fails with "No such file or directory"

## Critical Pitfall: Chain Name Confusion

DexScreener labels this chain **"robinhood"** — it is NOT HyperEVM (999). 
When DexScreener returns pairs on chain "robinhood", those contracts are on chain 4663, not 999.

**ALWAYS run `cast chain-id --rpc-url <RPC>` to confirm which chain you're on.**

## On-Chain Verification Command

```bash
RPC="https://rpc.mainnet.chain.robinhood.com"
cast chain-id --rpc-url "$RPC"              # Should return 4663
cast code 0x7e072b... --rpc-url "$RPC"      # Verify bytecode
cast call 0x7e072b... "symbol()(string)" --rpc-url "$RPC"
```

## Example: Pops Finance (July 2026)
- Website: `https://www.popsfinance.xyz/`
- Docs reveal: Chain ID 4663, RPC `rpc.mainnet.chain.robinhood.com`
- Real POPS token: `0x7e072b05163bE1B8009071d0449187c39fFa04d6` (1B supply, verified bytecode)
- 3 of 4 DexScreener "POPS" tokens returned `0x` on cast code — all squatters
- No vault/staking/lending contracts — frontend-only protocol