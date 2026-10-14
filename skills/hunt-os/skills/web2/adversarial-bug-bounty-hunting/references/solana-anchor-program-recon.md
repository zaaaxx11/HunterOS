# Solana Anchor Program Recon — Live On-Chain Account Discovery & Decoding

Reusable techniques for discovering and decoding Anchor program accounts on Solana mainnet without needing the IDL.

## 1. Find All Accounts Owned by a Program

```bash
# Get ALL accounts (no size filter — returns everything)
curl -s -X POST "https://api.mainnet-beta.solana.com" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"getProgramAccounts",
    "params":["<PROGRAM_ID>",{"encoding":"base64"}],
    "id":1
  }' | jq '.result | length'
```

## 2. Filter by Account Size (dataSize)

Anchor structs have fixed sizes. Use `dataSize` filter to isolate specific account types:

```bash
# Order struct: discriminator(8) + action_id(8) + amount(8) + expiration(8) + owner(32) + token_id(78) + order_type(1) = 143
curl -s ... | jq --argjson filter '{"dataSize":143}' ...

# UserWallet: discriminator(8) + owner(32) + master(32) + action_id(8) = 80
curl -s ... | jq --argjson filter '{"dataSize":80}' ...
```

## 3. Decode Anchor Account Data

Anchor prepends an 8-byte discriminator (sha256("global:<struct_name>")[:8]) to every account.

```python
import base64, base58, struct

data = base64.b64decode(account_data_b64)

# Discriminator
disc = data[:8]

# Decode based on struct layout:
# Order: action_id(u64) + amount(u64) + expiration(u64) + owner(Pubkey, 32) + token_id([u8;78]) + order_type(u8)
action_id = struct.unpack('<Q', data[8:16])[0]
amount = struct.unpack('<Q', data[16:24])[0]
expiration = struct.unpack('<Q', data[24:32])[0]
owner = base58.b58encode(data[32:64]).decode()  # Pubkey → base58
token_id = data[64:142].decode('utf-8', errors='replace').strip('\x00')
order_type = data[142]  # 0=buy, 1=sell, 2=withdraw
```

## 4. PDA Derivation (Python)

Anchor PDAs use `find_program_address(seeds, program_id)` which iterates bumps 255→0.

```python
import hashlib, base58, struct

def pubkey_to_bytes(pk: str) -> bytes:
    return base58.b58decode(pk)

def find_pda(seeds: list, program_id: str) -> tuple:
    """Find PDA given seeds and program ID. Returns (base58_address, bump)."""
    pid_bytes = pubkey_to_bytes(program_id)
    seed_bytes = b""
    for seed in seeds:
        if isinstance(seed, str):
            seed_bytes += pubkey_to_bytes(seed)
        elif isinstance(seed, bytes):
            seed_bytes += seed
        elif isinstance(seed, int):
            seed_bytes += struct.pack("<Q", seed)
    
    for bump in range(255, -1, -1):
        candidate = seed_bytes + bytes([bump])
        hash_val = hashlib.sha256(candidate + pid_bytes).digest()
        if not is_on_curve(hash_val):
            return (base58.b58encode(hash_val).decode(), bump)
    raise Exception("PDA not found")

def is_on_curve(point: bytes) -> bool:
    """Check if point is on ed25519 curve. Use nacl bindings when available."""
    try:
        from nacl.bindings import crypto_core_ed25519_is_valid_point
        return crypto_core_ed25519_is_valid_point(point)
    except ImportError:
        # Fallback: Solana PDA is off-curve by definition
        # A proper check requires libsodium
        return False
```

## 5. Common Anchor Seed Patterns

```python
# UserWallet: ["user-wallet", owner_pubkey, master_pubkey]
user_wallet_pda = find_pda([b"user-wallet", OWNER, MASTER], PROGRAM_ID)

# Order: ["order", action_id_le_bytes, owner_pubkey, master_pubkey]
order_pda = find_pda([b"order", ACTION_ID, OWNER, MASTER], PROGRAM_ID)

# Token account: ["order-usdt-account", action_id, owner, master]
token_pda = find_pda([b"order-usdt-account", ACTION_ID, OWNER, MASTER], PROGRAM_ID)
```

## 6. Get Token Accounts by Owner

```bash
curl -s -X POST "https://api.mainnet-beta.solana.com" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"getTokenAccountsByOwner",
    "params":["<PUBKEY>",{"programId":"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},{"encoding":"jsonParsed"}],
    "id":1
  }' | jq '.result.value[] | {pubkey: .pubkey, mint: .account.data.parsed.info.mint, amount: .account.data.parsed.info.tokenAmount.uiAmount}'
```

## 7. Build Anchor Instruction Data

```python
import hashlib

# Discriminator = sha256("global:<function_name>")[:8]
disc = hashlib.sha256(b"global:withdraw_order").digest()[:8]

# Build instruction data: discriminator + encoded args
# For withdraw_order(ctx, msg: Vec<u8>):
#   data = disc + msg_bytes
instruction_data = disc + msg_bytes
```

## 8. Verify Program is Deployed

```bash
curl -s -X POST "https://api.mainnet-beta.solana.com" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"getAccountInfo",
    "params":["<PROGRAM_ID>",{"encoding":"jsonParsed"}],
    "id":1
  }' | jq '.result.value.executable'
# true = program deployed and executable
```

## Key Pitfalls

- **`dataSize` filter is exact** — if the account has extra padding, it won't match. Always try without `dataSize` first to see actual sizes.
- **PDA derivation requires `is_on_curve` check** — a heuristic (first bit check) will give wrong bumps. Use `nacl.bindings` or `solana-py` when possible.
- **Anchor structs are NOT packed** — each field has alignment. Pubkeys are 32 bytes, u64 are 8 bytes.
- **Token accounts use SPL Token program**, not the Anchor program. Use `getTokenAccountsByOwner` to find them.