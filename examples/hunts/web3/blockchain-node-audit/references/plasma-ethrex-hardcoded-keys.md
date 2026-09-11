# Plasma ethrex — Hardcoded Key Exploit Pattern

## The Finding

Three hardcoded private keys in `cmd/ethrex/l2/options.rs` (PlasmaLaboratories/ethrex):

| Key | Default PK | Address | Purpose |
|-----|-----------|---------|---------|
| SPONSOR | `<REDACTED-PRIVATE-KEY:SPONSOR>` | `0x000e73282F60E2CdE0D4FA9B323B6D54d860f330` | Sponsors L2 user transactions |
| COMMITTER | `<REDACTED-PRIVATE-KEY:COMMITTER>` | `0x3D1e15a1a55578f7c920884a9943b3B35D0D885b` | Signs L1 commitBatch calls |
| PROOF_COORD | `<REDACTED-PRIVATE-KEY:PROOF-COORD>` | `0xE25583099BA105D9ec0A67f5Ae86D90e50036425` | TDX proof coordination |

## Key Ownership Proof Technique

When you find hardcoded private keys, prove ownership cryptographically:

```python
from eth_account import Account
from eth_account.messages import encode_defunct

# Sign a message — anyone can verify this proves key ownership
acct = Account.from_key(hardcoded_pk)
msg = encode_defunct(text="I control this key. Audit proof.")
signed = acct.sign_message(msg)
# Signature: signed.signature.hex()
# Verify: Account.recover_message(msg, signature=signed.signature)

# Then try to broadcast a tx — error message reveals key validity
# "insufficient funds" = valid key + valid sig
# "invalid signature" = wrong key
```

## On-Chain Verification

Always check:
1. `eth_getTransactionCount` → nonce > 0 = key was used in production
2. `eth_getBalance` → 0 balance doesn't mean unused (committer operates on L1)
3. `eth_getCode` → EIP-7702 delegation (0xef0100 prefix) = address is active
4. Check ALL networks: mainnet, testnet, devnet

## EIP-7702 Delegation Detection

When `eth_getCode` returns exactly 23 bytes (`0xef0100` + 20-byte address), this is an EIP-7702 delegated account. The address after `0xef0100` is the delegation target.

**Proven in Plasma session:**
```
Address: 0xE25583099BA105D9ec0A67f5Ae86D90e50036425
Code: 0xef0100ef7b31f45b19ffef6f1ff5ae684b78b1a86c1c0c
Delegated to: 0xef7b31f45b19ffef6f1ff5ae684b78b1a86c1c0c
```

The delegated contract has:
- 2079 bytes of Solidity 0.7.x code
- `execute(address,uint256,bytes)` function (selector `0xb61d27f6`)
- `transfer`, `transferFrom` functions
- Nonce = 1 (actively used)

**This is a smart contract wallet/relay pattern.** If you control the EOA, you control the delegated contract's execution.

## Admin Server Pattern

The ethrex admin server has NO auth middleware:
```rust
let http_router = Router::new()
    .route("/committer/stop", get(stop_committer))
    .route("/committer/start", get(start_committer_default))
    .route("/state-updater/stop-at/{block_number}", post(set_sequencer_stop_at))
    .route("/health", get(health))
    .with_state(admin.clone())  // ← NO auth layer!
    .fallback(not_found);
```

Default bind: `127.0.0.1:5555` (safe). But dev docker-compose overrides:
```yaml
ports:
  - 5555:5555
command:
  l2 --dev --admin-server.addr 0.0.0.0
```

Health endpoint leaks: `signer_status.address`, `on_chain_proposer_address`, `l1_chain_id`, `last_committed_batch`, `validium`, `based`.

## Public RPC Exposure

The public RPC (`https://rpc.plasma.to`) exposes:
- `txpool_content` — full pending tx details (from, to, value, input, gas)
- `debug_traceTransaction` — internal execution trace
- `net_peerCount` — network topology (87 peers)
- `web3_clientVersion` — `reth/v1.8.3` (version disclosure)

All accessible without authentication.

## Devnet Discovery

Custom chain devnets are discoverable via DNS brute force:
```bash
# Patterns to try
devnet.<domain>
testnet.<domain>
staging.<domain>
cs-<N>.<domain>
observer-cs-<N>.<domain>
validator-cs-<N>.<domain>
```

**Proven in Plasma session:**
- `devnet.plasmalabs.tech` → `3.21.220.26`
- Exposed methods: `txpool_content`, `debug_traceBlockByNumber`, `eth_getProof`
- Chain ID: 9747
- Client: `reth/v1.11.3-d6324d6/aarch64-unknown-linux-gnu`

Devnets often have **weaker security** than mainnet — debug APIs and admin endpoints may be enabled.

## Treasury Address Exposure

Genesis files pre-fund treasury/operator addresses. Check:
```bash
# In node-templates/config/*/genesis.json
# Look for alloc section
```

**Proven in Plasma session:**
| Address | Balance | Type |
|---------|---------|------|
| `0x0000...a11b004` | 5,293,874 XPL | Proxy |
| `0x0000...a11b005` | 785,985 XPL | Proxy (coinbase) |

Total: ~6M XPL in genesis addresses.

## Consensus Config Leaks

Node template configs leak:
- BLS public keys (static committee)
- Bootstrap node hostnames + peer IDs
- Validator hostnames (even in comments)
- Engine API URLs
- JWT secret paths
- P2P ports, consensus API ports

**Detection:**
```bash
grep -rn "bls_public_key\|bootstrap_nodes\|trusted_peers\|engine_api_url\|consensus_api_host" \
  --include="*.toml" --include="*.yaml" --include="*.yml"
```

## Lessons

1. **CLI `default_value` is a bug magnet** — every hardcoded default is a potential operator key leak
2. **Dev docker-compose != production** — but dev configs leak into testnet/staging
3. **Health endpoints leak internal state** — always serialize with `#[serde(skip)]` on sensitive fields
4. **0 balance ≠ unused** — check nonce, check all networks, check L1 activity
5. **Exploit-first, don't catalog** — prove ownership immediately, don't just list findings
6. **EIP-7702 delegation = proof of key usage** — if the address has delegated code, the key is active
7. **Devnet discovery via DNS** — custom chains often have discoverable devnets with weaker security
