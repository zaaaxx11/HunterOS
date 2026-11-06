# HunterOS Tools — Essential Toolkit

Minimal, non-overlapping tools for the full HUNT-OS pipeline.
Each tool solves a unique problem class — no duplicates.

## Installed (Essential 9)

| Tool | Category | Install | Use |
|------|----------|---------|-----|
| **go** | Runtime | `winget install GoLang.Go` | Required by subfinder, nuclei |
| **jq** | Parsing | `winget install jqlang.jq` | JSON query/transform |
| **subfinder** | Recon | `go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest` | Passive subdomain enum |
| **nuclei** | Vuln Scan | `go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest` | Template-based vuln scanning |
| **httpx** | HTTP | `go install github.com/projectdiscovery/httpx/cmd/httpx@latest` | HTTP probing |
| **paramspider** | Params | `pip install paramspider` | Parameter discovery/mining |
| **cast** | Web3 RPC | (Foundry suite) | Ethereum RPC calls |
| **forge** | Web3 Test | (Foundry suite) | Smart contract testing, PoC |
| **curl** | HTTP | (system) | Raw HTTP requests |

## Web3 Suite (Foundry)

| Tool | Use |
|------|-----|
| `cast` | RPC calls, tx analysis, storage slots |
| `forge` | Contract testing, fuzzing, PoC verification |
| `anvil` | Local testnet node for exploit simulation |
| `chisel` | Solidity REPL |

## Skipped (Overlap)

| Skipped | Because | Replaced By |
|---------|---------|-------------|
| amass | Heavier, slower | subfinder |
| assetfinder | Not maintained | subfinder |
| puredns | DNS brute only | subfinder |
| katana | Crawler | httpx + curl + paramspider |
| gau | URL history | paramspider |
| waymore | Heavy, many deps | paramspider |
| anew | Dedup lines | `sort -u` |
| uro | URL dedup | `sort -u` |
| qsreplace | Param replace | `sed` |
| naabu | Port scan | curl |
| corscanner | CORS check | curl one-liner |
| dalfox | XSS scan | nuclei (xss templates) |
| kxss | XSS reflection | nuclei |
| gxss | XSS params | nuclei |
| sqlmap | SQL injection | Install only if SQLi found |
| jscracker | JS secrets | grep-based |
| subzy | Subdomain takeover | nuclei templates |

## Tool Matrix by Hunt Phase

| Phase | Tools Used |
|-------|-----------|
| Subdomain enum | subfinder, httpx |
| URL discovery | paramspider, httpx |
| Vuln scanning | nuclei |
| JS analysis | curl, grep, jq |
| Live probing | curl, httpx |
| Web3 audit | cast, forge, anvil |
| PoC verification | forge, cast, curl |
| Report writing | (Claude Code native) |

## Install All Essential Tools

```bash
# Windows (winget)
winget install --source winget GoLang.Go jqlang.jq

# Unix (brew)
brew install go jq

# Go tools (~5 min)
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest

# Python tools
pip install paramspider

# Foundry (Web3)
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

## Verify

```bash
go version
jq --version
subfinder -version
nuclei -version
httpx -version
cast --version
forge --version
```