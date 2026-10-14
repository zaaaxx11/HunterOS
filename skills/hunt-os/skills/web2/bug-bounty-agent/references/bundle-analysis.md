# JS Bundle Analysis Methodology for Minified SPAs

## When to Use
- Vite.js / Next.js / Webpack single-page applications
- No public source code available
- Need to find: contract addresses, API endpoints, chain configs, function names

---

## Phase 1: Download & Identify Bundle

```bash
# 1. Get main HTML
curl -s https://target.com/ | grep -o '/assets/index-[^"]*\.js'
# Or for Next.js:
curl -s https://target.com/ | grep -o '/_next/static/chunks/[^"]*\.js'

# 2. Download bundle
curl -s "https://target.com/assets/index-<hash>.js" -o bundle.js

# 3. Check size
ls -lh bundle.js
# Typical: 1-10MB minified
```

---

## Phase 2: Extract All 0x Addresses

```bash
# Extract ALL 40-char hex addresses
grep -oE '0x[a-fA-F0-9]{40}' bundle.js | sort -u > all_addresses.txt

# Count
wc -l all_addresses.txt
# Typical: 500-2000 addresses

# Filter known tokens (WETH, USDC, WBTC, etc.)
# Create known_tokens.txt with common addresses
grep -v -f known_tokens.txt all_addresses.txt > candidate_contracts.txt
```

### Known Token Filter List (Mainnet + Major L2s)
```bash
cat > known_tokens.txt << 'EOF'
0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2  # WETH Ethereum
0x7BeA0982A3490D6E589Be3b59BeBCe52289D4A1d  # WMATIC
0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913  # USDC Polygon
0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb  # DYDX
0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599  # WBTC
0x6B175474E89094C44Da98b954EedeAC495271d0F  # DAI
0xdAC17F958D2ee523a2206206994597C13D831ec7  # USDT Ethereum
0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48  # USDC Ethereum
0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE  # Native ETH
0x4200000000000000000000000000000000000006  # WETH Optimism/Base
0x4200000000000000000000000000000000000014  # WBT Optimism
EOF
```

---

## Phase 3: Find Embedded API Endpoints

```bash
# Extract all URLs
grep -oE 'https?://[^"\'`\s]{10,}' bundle.js | sort -u > urls.txt

# Filter for API-like patterns
grep -iE 'api|relay|bridge|swap|relayer|settle|rfq' urls.txt

# Common patterns to look for:
# - swap-relayer.domain.com/relay
# - api.domain.com/v1/*
# - service-dev.domain.com/*
# - turnkey.com/api/v1/*
# - chain RPC URLs
```

---

## Phase 4: Identify Chain Configs

```bash
# Search for chainId references
grep -oE 'chainId[^}]*' bundle.js | head -20

# Look for chain config objects
grep -oE '"chainId"\s*:\s*[0-9]+' bundle.js

# Map known chainIds:
# 1 = Ethereum, 137 = Polygon, 42161 = Arbitrum
# 10 = Optimism, 8453 = Base, 534352 = Scroll
# 34443 = Mode, 57073 = Ink, 1329 = Sei Arctic-1
```

---

## Phase 5: Extract Function Names (Minified but Readable)

```bash
# Find function definitions (even minified)
grep -oE 'function[^{]{0,100}' bundle.js | grep -iE 'swap|relay|settle|route|fee|sign|nonce|route|amount'

# Look for method names in objects
grep -oE '\w{2,20}:\s*function' bundle.js | grep -iE 'swap|route|relay|settle|fee|quote'

# EIP-712 domain separators
grep -oE 'DOMAIN_SEPARATOR|domainSeparator|EIP712|eip712' bundle.js

# Nonce / replay protection
grep -oE 'nonce[^}]*' bundle.js
```

---

## Phase 6: Wallet / Auth Infrastructure

```bash
# Turnkey
grep -i turnkey bundle.js

# Privy — also extract appId and check for misconfigurations
grep -i privy bundle.js
#   See full Privy auth attack playbook: references/privy-auth-attack-playbook.md

# Dynamic / Thirdweb / Magic Link
grep -iE 'dynamic|thirdweb|magic.link|web3auth' bundle.js

# Project IDs / API keys (may be in config objects)
grep -oE 'projectId|apiKey|clientId[^}]*' bundle.js
```

---

## Phase 7: Cross-Reference with On-Chain

```bash
# For each candidate contract address:
# 1. Check bytecode size
cast code <address> --rpc-url <rpc>

# 2. If > 1KB, analyze storage
for slot in {0..50}; do
  cast storage <address> $slot --rpc-url <rpc>
done

# 3. Test function selectors
cast call <address> "owner()(address)" --rpc-url <rpc>
cast call <address> "pause()(bool)" --rpc-url <rpc>
cast call <address> "withdraw()(bool)" --rpc-url <rpc>
```

---

## Phase 8: Document Findings

Create structured report:
```markdown
# Bundle Analysis: <target>

## Bundle Info
- Framework: Vite / Next.js / Webpack
- Size: X MB
- Minified: Yes/No
- Source map: Available/Not available

## Contract Addresses Found
| Address | Context | Bytecode Size | Type |
|---------|---------|---------------|------|

## API Endpoints
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|

## Chain Configs
| Chain | ChainId | RPC | Contracts |
|-------|---------|-----|-----------|

## Wallet / Auth
| Provider | Config Found | Project ID |
|----------|--------------|------------|

## Critical Functions Identified
| Function | Context | Risk |
|----------|---------|------|
```

---

## Saphyre.xyz Case Study Results

| Metric | Value |
|--------|-------|
| Bundle size | 7.45 MB |
| Unique 0x addresses | 809 |
| After token filter | ~50 candidate contracts |
| Saphyre-specific contracts | 4 (RFQ Settlement, Pool, Steer Periphery, Permit2) |
| API endpoints | 50+ (turnkey, relayer, DragonSwap, bridge, DEV) |
| Chains configured | 7 (Sei, Base, Scroll, Mode, Ink, Arbitrum, Optimism) |
| Wallet infra | Turnkey (project IDs in bundle) |
| EIP-712 domains | Found (swap relayer) |

---

## Phase 9: TanStack Start / TanStack Router SSR Analysis\n\nTanStack Start apps use a unique server function protocol with framed responses. The server functions are NOT traditional REST endpoints — they use a binary framing protocol.\n\n### Identifying TanStack Start\n```bash\n# Look for telltale bundle names\ncurl -s target.com/ | grep -oP '"/assets/createServerFn-[^\"]*\\.js\"'\n# → If found, it's TanStack Start\n\n# Look for TSS protocol markers\ncurl -s target.com/ | grep -oP 'x-tss-serverFn|x-tsr-serverFn'\n# → If found, server functions are active\n```\n\n### Enumerating Server Functions\n```bash\n# 1. Download main bundle\ncurl -s target.com/ | grep -oP '"/assets/index-[^\"]*\\.js\"' | head -1\n\n# 2. Find SHA256 server function IDs (64 hex chars in createServerFn calls)\ngrep -oP '[a-f0-9]{64}' bundle.js | sort -u\n\n# 3. These are the server function IDs. The URL pattern is:\n#    /_serverFn/<hash>\n```\n\n### Calling Server Functions Directly\n```bash\n# Example from ColibriSwap explorer endpoint:\ncurl -sv 'https://target.com/_serverFn/<HASH>' \\\n  -X POST \\\n  -H 'Content-Type: application/json' \\\n  -H 'Accept: application/x-tss-framed, application/x-ndjson, application/json' \\\n  -H 'x-tsr-serverFn: true' \\\n  -d '{\"data\":{\"<param>\":\"<value>\"}}'\n\n# Key headers:\n#   x-tsr-serverFn: true — must be present\n#   Accept: application/x-tss-framed — the framed protocol\n#   Payload format: {\"data\": { ... }}\n\n# Response will be seroval-encoded JSON (framed protocol) or plain error\n# Look for: \"t\":25 (error frame), \"t\":0 (success frame with data)\n```\n\n### Seroval Error Decoding\nWhen you get a seroval error response:\n```json\n{\"t\":25,\"i\":0,\"s\":{\"message\":{\"t\":1,\"s\":\"Seroval Error (step: 3)\"}},\"c\":\"$TSR/Error\"}\n```\n- `t`: frame type (25 = Custom Plugin / Error)\n- `s.message.t`: 1 = string error\n- `s.message.s`: \"Seroval Error (step: 3)\" → step 3 = deserialization\n- **Deserialization errors usually mean the server expected a different param format**\n\n### Server Function Types\nFrom index bundles, server functions come in flavors:\n- `r(`...`)` = GET handler (read queries)\n- `handler(r(`...`))` = wrapped function with custom logic\n- Functions can be nested via `.handler()`, `.validator()`, `.middleware()`\n\n### Finding Internal API Discovery\n\nTanStack Start servers may also have:\n```bash\n# Analytics proxy at ~ paths\ncurl -sv 'https://target.com/~api/analytics' -X POST -d '{}'\n# If \"Accepted\" → analytics ingestion endpoint\n\n# Check for ~flock.js (Tinybird parcel-built analytics)\ncurl -s 'https://target.com/~flock.js'\n# Contains: data-proxy-url, data-host, data-token\n# These reveal analytics platform used and potential data endpoints\n```\n\n### Tinybird Analytics Proxy Pattern (Discovered at colibriswap.com)\n\nWhen you see `~flock.js` with `data-proxy-url=\"/~api/analytics\"`:\n1. The proxy endpoint accepts ANY POST payload and returns \"Accepted\"\n2. The `~flock.js` script is Parcel-built, contains Tinybird API SDK\n3. It collects: user-agent, locale, location, pathname, href, referrer, web vitals\n4. If the proxy is misconfigured, ANY page data could leak through\n5. Check if the proxy is backed by an actual Tinybird token (data-token attrib)\n\n```bash\n# Test if analytics proxy accepts arbitrary payload\ncurl -sv 'https://target.com/~api/analytics' \\\n  -X POST \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"action\":\"test\",\"payload\":\"{}\"}}'\\''\n# If returns \"Accepted\" with no validation, the proxy is wide open\n```\n\n## Backend Provider Extraction from Bundles\n\nMany crypto swap aggregators embed their provider info in client-side code:\n\n```bash\n# Look for known swap provider identifiers\ngrep -oP 'provider:[\"\\'']([a-z]+)[\"\\'']' bundle.js\n# Common: \"changenow\", \"houdiniswap\", \"exolix\", \"simpleswap\"\n\n# Look for deposit/payout address patterns in swap bundles\ngrep -oP 'payinAddress|payoutAddress|depositAddress|payinExtraId' bundle.js\n# If found → actual swap execution happens off-chain through partner API\n\n# Trace the whole swap flow from bundle\ngrep -oE 'fromAmount|toAmount|fromCurrency|toCurrency' bundle.js\n```\n\n## Tooling Shortcuts

```bash
# One-liner for full extraction
curl -s https://target.com/ | grep -o '/assets/index-[^"]*\.js' | head -1 | xargs -I{} curl -s "https://target.com{}" | \
  grep -oE '0x[a-fA-F0-9]{40}' | sort -u > addresses.txt

# Quick contract verification
for addr in $(cat addresses.txt); do
  size=$(cast code $addr --rpc-url https://rpc.example.com | wc -c)
  if [ $size -gt 100 ]; then
    echo "$addr: $size bytes"
  fi
done
```

---

## TanStack Start / TanStack Router SSR Analysis

TanStack Start apps use a unique server function protocol. Server functions are NOT traditional REST endpoints — they go through an SSR RPC mechanism.

### Identifying TanStack Start
```bash
# Look for telltale bundle names
curl -s target.com/ | grep -oP '"/assets/createServerFn-[^\"]*\\.js"'
# → If found, it's TanStack Start (Vinxi builder)

# Look for TSR $R protocol in HTML
curl -s target.com/ | grep -oP '\$_TSR\.router|$TSS/serverfn'
# → Confirms TanStack Router with server functions active

# Check for SSR-only guard
curl -s -X POST target.com/swap \
  -H "Accept: text/x-component" \
  -H "Content-Type: application/json" \
  -d '{"data":{}}'
# → Response: {"error":"Only HTML requests are supported here"}
# → CONFIRMS SSR-only: server functions NOT directly callable via AJAX
```

### Architecture Discovery: SSR-Only vs Direct API
When the server returns `"Only HTML requests are supported here"` on POST:
- **Server functions are SSR-proxied** — the server calls external APIs (ChangeNOW, HoudiniSwap, etc.) internally
- **Direct curl exploitation is blocked** — must find the underlying provider API or use headless browser
- **Look for provider API URLs in bundles instead**:
```bash
grep -oP 'https?://[a-zA-Z0-9.-]+/(api|v[12])\S+' bundle.js | sort -u
grep -oP 'changenow|houdiniswap|exolix|simpleswap' bundle.js | sort -u
```

### TanStack Server Function Discovery in Minified Bundles
```bash
# 1. Look for the TSS serverfn serializer marker
grep -boP '.{0,40}\$TSS/serverfn.{0,60}' main-bundle.js

# 2. Server function IDs are 64-char hex strings embedded in createServerFn()
grep -oP '[a-f0-9]{64}' bundle.js | sort -u | head -20

# 3. Extract queryKey patterns to reverse-engineer function names
grep -oP 'queryKey:\[`[a-z-]+`' route-bundle.js | sort -u
# Example: queryKey:[`cn-estimate`] → ChangeNOW estimate function
#          queryKey:[`cn-min`] → ChangeNOW minimum amount
#          queryKey:[`route-status`] → HoudiniSwap route status

# 4. From the import chain, trace obfuscated serverFn vars to their source
# In route-bundle: s=oe(ie) → ie is H from main-index → H = createServerFn variant
grep -oP '[A-Z] as [a-z]{2}' route-bundle.js | sort -u
```

### Extracting Wallet/Auth Provider Config from Minified Bundles
```bash
# Privy — look for the client class with appId getter
grep -oP 'get appId\(\)\{return this\.\w+\.appId\}' bundle.js
# → Found: means appId is exposed by the client SDK at runtime
# → The actual ID string may be in a config object, not a bare string
# → It's sent as privy-app-id header: grep 'privy-app-id' bundle.js

# Check if auth endpoints exist on the server
for ep in "/api/auth" "/auth/login" "/api/auth/token"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "target.com$ep")
  echo "[$code] target.com$ep"
done
# → If all 404, auth is purely client-side (browser wallet SDK)
```

### Extracting Swap Provider API Details
When the server proxies to ChangeNOW / HoudiniSwap / etc:
```bash
# The client sends structured payloads to server functions
# Extract the field names to understand the API schema
grep -oP '(fromCurrency|fromNetwork|toCurrency|toNetwork|fromAmount|address|timezone|preferredAccount)' swap-bundle.js | sort -u

# Look for the actual swap creation flow
grep -oP 'mutationFn|mutationKey|onSuccess' swap-bundle.js
# → Reveals: createSwap mutation, then store to internal DB on success

# Internal DB tracking
grep -oP 'save.*order|saveOrder|storeTx|meta:\{' bundle.js
# → If found, the app has its own tracking system
```

### Analytics Beacon Leakage Pattern (Flock.js / Tinybird)
When the HTML includes `<script defer src="/~flock.js" data-proxy-url="/~api/analytics">`:
```bash
# 1. Download the read.report.config
curl -s target.com/~flock.js | head -c 2000
# → Parcel-built; check for host URL, tracker API endpoint, web vitals collection

# 2. Test the analytics proxy
curl -s -X POST target.com/~api/analytics \
  -H "Content-Type: application/json" \
  -d '{"event":"swap","amount":100,"wallet":"0xtest"}'
# → If "Accepted" with no validation → open analytics sink
# → Can leak arbitrary payloads through the proxy to analytics backend

# 3. Check for data-token attribute in the script tag
curl -s target.com/ | grep -oP 'data-token="[^"]*"'
# → If present, the Tinybird API token is exposed in client HTML
```

## Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Fix |
|--------------|---------|-----|
| Only checking top 10 addresses | Misses peripheral contracts | Extract ALL, filter systematically |
| Ignoring DEV/test endpoints in prod bundle | Info leak, attack surface | Flag all non-prod URLs |
| Not checking token balances on contracts | Misses "empty vault" pattern | Always `balanceOf` on major tokens |
| Assuming owner = drain | Owner may only config | Verify `withdraw`/`transfer` exist |
| Skipping EIP-712 domain extraction | Can't test replay/forgery | Extract from domain, test sig validation |
| **Trying to extract Prinary appIds by searching for bare \"cl...\" strings** | Vite-inlined env vars use `var <short> = \`cm...\`` pattern;  | Use `grep -oP \"var [a-z]{3}\\s*=\\s*['\x60](cl|cm)[a-z0-9]+\" bundle.js` |
| **Assuming query params == server-side estimates** | SSR pages are static shells | Verify server response body has actual estimate data before fuzzing |
| **Skipping the analytics proxy (`/~api/analytics`)** | Potential data exfiltration point | Always test POST to analytics proxy — often "Accepted" with no validation |