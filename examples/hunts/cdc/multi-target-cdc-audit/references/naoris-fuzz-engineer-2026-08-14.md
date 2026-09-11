# Naoris Protocol (NaoX) — FUZZ-ENGINEER Case Study

**Date:** 2026-08-14  
**Targets:** naox.org (Next.js), NaorisTokenV3 (Solidity), bridge.naorisprotocol.network (React/Vite)  
**Style:** Bahasa Indonesia santai, edge-case → hasil table

## Target Architecture

| Layer | Detail |
|-------|--------|
| **Frontend** | Next.js App Router (Vercel), no API routes exposed, pure static/dynamic rendering |
| **Token** | ERC-1967 Proxy `0x1b379A79c91a540b2bcd612b4d713f31De1b80cc` → NaorisTokenV3 `0x9658905B1A4106DEEF53181251BcDdaE7BCBa7CF` |
| **Bridge** | React SPA (Vite), nginx, thirdweb SDK, supports ETH/BSC/Polygon |
| **Chain** | NaoX L1, chainId 46512, RPC `rpc.naorisprotocol.network`, custom modules: `dposec`, `mesh`, `otkdp` |
| **Docs** | GitBook at `docs.naoxprotocol.com` |

## Key Techniques Used

### 1. Contract Source via Blockscout API
When Etherscan API v2 returns `NOTOK` without API key, Blockscout API v2 works:
```python
import urllib.request, json
url = f"https://eth.blockscout.com/api/v2/smart-contracts/{proxy_addr}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
data = json.loads(urllib.request.urlopen(req).read())
# proxy_type: "eip1967", implementations: [{address_hash, name}]
# Then fetch implementation: /api/v2/smart-contracts/{impl_addr}
# source_code field contains full Solidity
```

### 2. RPC Endpoint Discovery
- Guess common RPC subdomains: `rpc.<domain>`, `rpc.<project>.network`
- Probe with `eth_chainId` → confirm chain ID
- `rpc_modules` → enumerate exposed modules (dangerous: `admin`, `debug`, `personal`)
- NaoX returned `{"admin":"1.0","debug":"1.0","dposec":"1.0","eth":"1.0","mesh":"1.0","miner":"1.0","net":"1.0","otkdp":"1.0","rpc":"1.0","txpool":"1.0","web3":"1.0"}`

### 3. Bridge JS Bundle Scanning
```bash
curl -s https://bridge.naorisprotocol.network/ | grep -oP 'src="[^"]*\.js[^"]*"'
curl -s https://bridge.naorisprotocol.network/assets/<hash>.js | grep -oP '0x[a-fA-F0-9]{40}' | sort -u
```
Extracted: all supported token addresses across chains, RPC URLs, chain configs.

### 4. Security Headers Diff
Main site (naox.org): `HSTS`, `x-powered-by: Next.js`, `x-vercel-cache: HIT` — no CSP, no X-Frame-Options.  
Bridge (bridge.naorisprotocol.network): `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block` — better posture.

### 5. Rate Limiting Probe
20 rapid requests to `/api/health` — all returned 404 without throttling. Rate limiter absent.

### 6. Solidity Audit (NaorisTokenV3)
- Compiler: 0.8.22 + optimizer 200 runs
- `_pause()` called in `initialize()` — token starts paused
- `_authorizeUpgrade` only checks `onlyRole(DEFAULT_ADMIN_ROLE)` — no timelock, no multisig
- `revokeRole`/`renounceRole` cannot remove own DEFAULT_ADMIN_ROLE (anti-lockout)
- `permit` overridden with `whenNotPaused` modifier
- TOTAL_SUPPLY = 4_000_000_000, decimals = 18

## Findings Summary

| Severity | Count | Key Finding |
|----------|-------|-------------|
| 🔴 HIGH | 2 | Bridge contracts source not available; RPC `admin`/`debug` modules exposed |
| 🟠 MEDIUM | 4 | No CSP/X-Frame; no rate limiting; single-admin UUPS upgrade; token starts paused |
| 🟡 LOW | 5 | `robots.txt` leaks `/admin/`; Vercel cache headers; Firebase storage bucket exposed; RSC payload leaks contract address; bridge nginx last-modified |
| ✅ SAFE | 10+ | No JS secrets; no GraphQL; no .env exposure; no source maps; all parameter pollution safe; 0 amount transfer safe; max uint256 guarded; no precision loss; permit non-malleable; initializer safe |

## Output Format
Edge case table: `| # | Edge Case | Hasil | Severity |` with bahasa Indonesia santai.