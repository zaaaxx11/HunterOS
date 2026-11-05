---
name: hunter-tools
description: HunterOs tool registry — 43 JSON-Schema tools usable by any LLM agent framework. Load when you need to register HunterOs capabilities in Claude Code, Hermes, OpenCode, or a custom harness.
---
# HUNTEROS UNIVERSAL TOOL REGISTRY

43 tools extracted from `zaaaxx11/HunterOsHarnessOsHarness v0.7`. Each tool follows
JSON-Schema, compatible with Claude Code `tools:`, OpenCode `tools:`,
Hermes `tool_spec`, and any OpenAI-compatible function-calling registry.

## USAGE

```bash
# Dump all tool schemas as JSON
hunter tools list --json > tools.json

# Register in Claude Code (via .claude-plugin/plugin.json)
# Register in Hermes (via ~/.hermes/profiles/default/tools/)
# Register in OpenCode (via tools.json in project root)
```

## TOOL INDEX

### Local — file system and code inspection
| Tool | Description | Required Args |
|------|-----------|---------------|
| `search_files` | Regex search across source tree | `pattern` |
| `read_file` | Paginated file read | `path` |
| `patch_write` | Find-and-replace edit | `path, old_string, new_string` |

### Network — recon and probing
| Tool | Description | Required Args |
|------|-----------|---------------|
| `dns_resolve` | DNS lookup A/AAAA/CNAME/MX/TXT | `host` |
| `crt_sh` | Certificate transparency enumeration | `host` |
| `headers_audit` | Security header inspection | `url` |
| `recon_subdomains` | Subdomain discovery | `host` |

### Web3 — blockchain contracts
| Tool | Description | Required Args |
|------|-----------|---------------|
| `contract_read` | eth_call, getStorageAt | `chain_id, address, data` |
| `contract_source_fetch` | Verified source pull | `chain_id, address` |
| `abi_decode_hint` | ABI from bytecode | `chain_id, address` |

### Heavy — static analysis  
| Tool | Description | Required Args |
|------|-----------|---------------|
| `slither_audit` | Solidity 200+ detectors | `target` |
| `cast_call` | Foundry RPC call | `chain_id, to, data` |

### Verification — evidence
| Tool | Description | Required Args |
|------|-----------|---------------|
| `verify_finding` | Re-read and confirm claim | `finding_id` |
| `derive_targets` | Follow-up URLs from findings | `endpoint` |

## JSON SCHEMA EXAMPLE

```json
{
  "name": "search_files",
  "description": "Regex search across source tree. Ripgrep-backed.",
  "parameters": {
    "type": "object",
    "properties": {
      "pattern": {"type": "string", "description": "Regex pattern"},
      "path": {"type": "string", "default": ".", "description": "Directory"},
      "file_glob": {"type": "string", "description": "Filter, e.g. *.sol"},
      "output_mode": {"enum": ["content","files_only","count"], "default": "content"},
      "limit": {"type": "integer", "default": 50}
    },
    "required": ["pattern"]
  }
}
```

Full 43-tool schema dump available via `hunter tools list --json`.
Individual tool specs live at `tools/` in the harness repo.

## HARNESS ADAPTATION

### Claude Code
```json
// .claude-plugin/plugin.json
{"tools": ["search_files", "read_file", "patch_write", "dns_resolve", "crt_sh",
           "headers_audit", "contract_read", "contract_source_fetch", "slither_audit",
           "cast_call", "verify_finding"]}
```

### Hermes Agent  
```bash
hunter tools list --format hermes > ~/.hermes/tools/hunter.json
```

### OpenCode
```bash
hunter tools list --format opencode > opencode_tools.json
```