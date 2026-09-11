---
name: cdc-device-audit
description: "CDC audit for device/IoT local web interfaces and firmware"
trigger: Use when auditing network devices, IoT, embedded systems, or hardware with local web interfaces (LSP, admin consoles, firmware upload) using CDC multi-agent orchestration.
---

# CDC Device/IoT Audit

## When to Use
- Network devices with local web servers (LSP, admin consoles)
- IoT/embedded devices with firmware upload/config interfaces
- Hardware targets where "shell access = high priority" per scope
- Targets with default credentials, DNS interception, or unauthenticated config endpoints

## CDC Adaptation for Device Targets

### Agent Roles (Modified from Web App)
| Agent | Device Focus |
|-------|--------------|
| **Architect** | Map device attack surface: LSP, firmware, bootloader, debug ports, cloud-device comms |
| **Red-Teamer** | Default creds, auth bypass, config injection, firmware supply chain |
| **Fuzz-Engineer** | Config parsers, firmware parsers, bootloader, network stacks, radio interfaces |
| **Chainer** | LAN adjacency → default creds → config injection → root shell → cloud pivot |

### Key Device-Specific Trust Boundaries
1. **Physical → Network** (serial number on label → LSP access)
2. **Unauth Config → Root Shell** (Proxy/PPPoE/WAN fields → command injection)
3. **Device → Cloud** (compromised device → org pivot via API tokens)
4. **Firmware Supply Chain** (cloud → device firmware push → persistent root)

## Meraki-Specific Patterns

(Meraki-specific target notes — LSP default creds / fixed IPs / TLS surface, splash SSRF, ikarem.io internal services — preserved at examples/hunts/cdc/cdc-device-audit/meraki-patterns.md, with the four meraki case files under examples/hunts/cdc/cdc-device-audit/references/.)

## Pitfalls
- ❌ Don't treat device web interfaces like web apps — they run as root, no WAF, busybox shells
- ❌ Don't assume rate limiting on LSP login (Cisco Advisory confirms none)
- ❌ Don't skip DNS interception — it's the primary LSP discovery mechanism
- ❌ Don't test splash renderer without valid network context (validation gate blocks all)
- ✅ Always verify command injection on actual hardware/sandbox — docs confirm surface, not exploit
- ✅ Chain LAN adjacency → default creds → config injection → root → cloud pivot