---
name: hunter-harness-core
description: HunterOs Harness universal engine — loop, state, tools, and workflow. Load when you need daemon-free hunting, state-driven loop, or the full HunterOs attack surface.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, WebSearch
---
# HUNTEROS HARNESS — Universal Core Engine

Extracted from `zaaaxx11/HunterOsHarnessOsHarness v0.7`. Portable skills usable by any harness
(Claude Code, Hermes Agent, OpenCode, Codex, etc.) — just fill the templates,
point at a target, and the loop runs.

## Architecture

```
hunter loop <target> --time 6h --goals rce-min:1,findings-min:500
```

- **No daemon, no queue** — each cycle is a subprocess hunt
- **State-driven** — `state.json` survives crashes, resume from last checkpoint
- **Time > goals** — wall clock always wins; summary in state file

## QUICK START

```bash
# Install the harness
pip install git+https://github.com/zaaaxx11/HunterOsHarnessOsHarness.git

# Start a 6-hour loop hunt against a local directory
hunter loop /path/to/repo --time 6h --goals exploitable-min:1,findings-min:1000 --engine llm --yes
```

## Tool Categories

### 1. Local Tools (file system, code reading)
- `search_files` — regex search across source tree
- `read_file` — paginated file read with line numbers  
- `patch_write` — targeted find-and-replace edits

### 2. Network Tools (recon, probing)
- `dns_resolve` — DNS lookup (A, AAAA, CNAME, MX, TXT)
- `crt_sh` — certificate transparency log enumeration
- `headers_audit` — security header inspection
- `recon_subdomains` — subdomain discovery

### 3. Web3 Tools (blockchain, smart contracts)
- `contract_read` — eth_call, getStorageAt, getBalance
- `contract_source_fetch` — verified source from Etherscan/Snowtrace/etc
- `abi_decode_hint` — ABI detection from bytecode

### 4. Heavy Tools (static analysis, compiled audits)
- `slither_audit` — Solidity static analysis (200+ detectors)
- `cast_call` — RPC call via Foundry's cast

### 5. Verification Tools
- `verify_finding` — re-read and confirm a finding claim
- `derive_targets` — generate follow-up URLs from findings
- `wonder_targets` — LLM-driven target discovery

## GOALS VOCABULARY

| Goal | Meaning |
|------|---------|
| `rce-min:N` | At least N pure RCE findings (code-exec/command-injection) |
| `exploitable-min:N` | At least N live-exploitable (RCE + reentrancy + access-control) |
| `findings-min:N` | At least N total findings |
| `verified-min:N` | At least N VERIFIED+ findings |

Set with `--goals rce-min:1,exploitable-min:1,findings-min:500`

## LOOP LIFECYCLE

```
start → load_mission → [cycle: subprocess hunt → count_findings → check goals/time → save state] → stop
```

State file: `<state_dir>/hunt_runs/<target_slug>/state.json`

## TOOL REGISTRY FORMAT (adapter for any harness)

Every tool follows a JSON-Schema-compatible spec:

```json
{
  "name": "read_file",
  "description": "Read a text file",
  "parameters": {
    "properties": {
      "path": {"type": "string", "description": "File path"},
      "offset": {"type": "integer", "default": 1},
      "limit": {"type": "integer", "default": 2000}
    },
    "required": ["path"]
  },
  "result": {"type": "object", "properties": {"content": "string", "total_lines": "integer"}}
}
```

All 43 tools in the harness follow this shape. Load individual tool specs via:
- `hunter tools list` (CLI)
- `tools/*.json` (manifest files bundled with the harness)

## AGENT / LANE SYSTEM

Multi-agent lanes dispatched by the orchestrator:

| Lane | Role | Tools |
|------|------|-------|
| Architect | Attack-surface mapping | read_file, search_files, derive_targets |
| Red-Teamer | Auth/authz testing | dns_resolve, headers_audit, recon |
| Fuzz-Engineer | Property-based testing | patch_write, dynamic-fuzz |
| Chainer | Exploit construction | slither_audit, contract_read |
| Verifier | Evidence checking | verify_finding, read_file, search_files |

Lane specifications live in `ai_skills/` within the repo root.
Default LLM model drives all lanes; the orchestrator is `devora-01/stepfun-5-preview`.