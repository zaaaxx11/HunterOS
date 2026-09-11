# Meraki Local Status Page (LSP) Attack Surface

## Overview
The LSP is a "light web server for uplink config" on every Meraki device. Scope explicitly states: "any way of obtaining shell access on a Meraki device is an interesting finding — as there should be no way for a user to meaningfully authenticate to a device."

## Access Vectors

### DNS Interception (Primary)
Devices intercept DNS for these hostnames and resolve to device LAN IP:
- `mx.meraki.com` / `wired.meraki.com` (MX)
- `switch.meraki.com` (MS)
- `ap.meraki.com` (MR)
- `setup.meraki.com` / `my.meraki.com` (All)
- `mg.meraki.com` (MG)
- `mcg.meraki.com` (Campus Gateway)

### Direct IP Access (Fallback)
| Device | Default LSP IP | Client Config |
|--------|---------------|---------------|
| MS (most) | 1.1.1.100 | 1.1.1.99/24, DNS 1.1.1.100 |
| MS390/C9300-M (CS16+) | 198.18.0.1 | 198.18.0.2/28, DNS 198.18.0.1 |
| MS390 (CS15.21.1-) | 10.128.128.130 | 10.128.128.132/8, DNS 10.128.128.130 |
| MR | 10.128.128.126 | 10.128.128.125/24 |
| MX/Z | LAN gateway (DHCP) | DHCP client |
| Campus Gateway | 198.18.0.1 | 198.18.0.2/28, DNS 198.18.0.1 |
| MG | LAN gateway (DHCP) | DHCP client |
| vMX (Azure/AWS) | Public IP + NSG/SG rule TCP 80 | Cloud config |

### Wireless Access (MR Only)
- Must connect to AP's SSID (configured or default: `meraki`, `meraki-<MAC>`, `meraki-setup`)
- No wired access to LSP on MR (security design)

## Default Credentials (Per Firmware)

| Product | Firmware | Username | Password |
|---------|----------|----------|----------|
| MX | 19+ | admin | Serial (e.g., Q2XX-XXXX-XXXX) |
| MS | 17+ | admin | Serial |
| MS390/C9300-M | CS 17+ | admin | Serial |
| MR | 32+ | admin | Serial |
| MR | 31.7.1+ | admin | Serial |
| MG | 4.1.1+ | admin | Serial |
| All (older) | Pre-above | Serial | (empty) |
| vMX | Any | Q2XX-XXXX-XXXX | q2xx-xxxx-xxxx |

**Key Properties:**
- Serial = Cloud ID = on device label, in DHCP Option 60, derivable from MAC OUI
- No MFA, no rate limit, no account lockout documented
- Digest auth (MD5) — weak, susceptible to replay
- Password change optional pre-Aug-2025; mandatory for new networks post-Aug-2025
- Reset: delete password via API/UI -> reverts to default on next config fetch

## Configure Tab — Injection Surface

### MX Security & SD-WAN
- WAN 1/2: IP, Subnet, Gateway, DNS (IPv4/IPv6)
- **Proxy URL** — `http://proxy:port` — **PRIMARY INJECTION TARGET**
- PPPoE: Username, Password, Service Name, IPv6 link-local
- IPv6: Static link-local address (PPP)
- WAN port 2 enable (single-WAN models)

### MR Wireless
- Static IP, Subnet, Gateway, DNS
- **Proxy URL** (HTTP proxy for mgmt traffic)
- Site Survey: channel, power, radio mode (deprecated MR32+)

### MS Switches
- Management IP, Subnet, Gateway, DNS

### All Devices
- **Download Support Data (SDB)** — generates diagnostic bundle
- Potential: firmware upload, config import (not documented but may exist for recovery)

## TLS / HTTPS Details
- MX 19.1+ / MR 31.1+: HTTP (80) -> HTTPS (8092) redirect
- Self-signed cert: CN = `*.devices.meraki.direct` (MAC-based)
- Cert valid for MAC-based domain only
- Bypass: `--insecure` / `-k` / browser accept
- Port 8092 may have different attack surface than port 80

## Remote Access Control
- Default: LAN only
- Configurable: Network-wide > Configure > General > Device configuration
- Firewall: Security & SD-WAN > Configure > Firewall > Layer 3 > WAN appliance services > Web (local status & configuration): None / Any / CIDR list
- vMX: Requires NSG/SG inbound rule TCP 80
- Concentrator/passthrough: May permit AutoVPN client access if MGMT IP in advertised subnet

## Scope Alignment
- Shell access = P1 ($6k-$10k)
- Config injection -> command execution = shell access
- Default creds + command injection = PRE-AUTH RCE chain

## References
- Meraki docs: "Using the Cisco Meraki Device Local Status Page" (page 584)
- "Configuring the Local Status Page" (page 11915)
- "Cisco Meraki Local Status Page: Security and SD-WAN" (page 13405)
- "Cisco Meraki Local Status Page: MR Wireless" (page 14441)