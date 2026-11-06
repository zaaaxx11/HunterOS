# Web3/Web2 Hunt Pitfalls & Techniques

## SOLIDITY LINE-BY-LINE LOOP = CONTEXT WASTE

**Anti-pattern**: Using 20+ incremental `read_file` calls extracting `sed -n 'N,Mp'` ranges from a Solidity file.

**Correct pattern**: 
```bash
# Step 1: Identify target lines
cat file.sol | grep -n "function\|modifier\|require\|only"

# Step 2: Extract specific range
cat file.sol | sed -n 'START,ENDp'
```

**Why**: The user will call you out ("Sampai mana tadi? Kenapa lo berhenti? Maslaah apa?") when you waste context window on incremental reads. SkateNFT.sol = 140 lines, extracted in 20+ calls = terrible vs 1 `cat | grep -n` + 1 `sed`.

## RUST SOURCE ANALYSIS (SOLANA/CUBIST)

When target has Rust code:
- `lib.rs`: Anchor programs — check `#[program]` for missing signature verification (look for commented-out `ed25519::verify_ed25519_ix`)
- `constants.rs`: Dummy/placeholder values in production (`DELEGATED_CONTRACT_ADDRESS = "0x"`, `IPFS_BASE_URL = "https://ipfs"`)
- `functions.rs`: External HTTP calls with hardcoded URLs

**Example**: `polymarket_skate::withdraw_order` — signature verification was commented out, allowing anyone to drain expired orders.

## DEPLOYMENT ADDRESS EXTRACTION VIA DOCS MCP

When docs use Mintlify, the MCP server's `query_docs_filesystem` tool exposes deployment address tables.

```bash
# Step 1: Discover MCP server
curl -s "https://docs.target.com/.well-known/mcp/server-card.json"

# Step 2: List tools (requires SSE accept header)
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Step 3: Explore filesystem
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"query_docs_filesystem_...","arguments":{"command":"cat /deployments/core-contracts.mdx"}},"id":2}'
```

**Result**: Full deployment addresses across all chains (Skate, Arbitrum, Base, BSC, Mantle, HyperEVM, Plume, 0G).

## WEB2 RECON QUICK TECHNIQUES

### Subdomain brute force (no tools needed)
```bash
for sub in dev staging admin internal dashboard api2 app2 test prod beta v1 v2 alpha sandbox; do
  host "$sub.domain.com" 2>/dev/null | grep -q "has address" && echo "FOUND: $sub"
done
```

### AWS API Gateway discovery
When `api2.domain.com` returns `{"message":"Not Found"}` with `apigw-requestid` header:
```bash
for stage in prod staging dev v1 api graphql; do
  curl -s "https://api2.domain.com/$stage"
done
```

### Next.js fingerprinting
```bash
# Extract buildId
curl -s https://target.com | grep -o '"buildId":"[^"]*"'

# Discover page routes
curl -s https://target.com | grep -o 'app/[^"]*page-[^"]*\.js'
```

### Mintlify MCP probe
```bash
# Check for MCP server card
curl -s "https://docs.target.com/.well-known/mcp/server-card.json"
curl -s "https://docs.target.com/.well-known/agent-card.json"
curl -s "https://docs.target.com/llms.txt"
```