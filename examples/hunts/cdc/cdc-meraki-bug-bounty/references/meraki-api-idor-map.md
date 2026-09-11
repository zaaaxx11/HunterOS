# Meraki API IDOR / Cross-Org Access Map

## Base URL
```
https://api.meraki.com/api/v1
```

## Authentication
- Header: `X-Cisco-Meraki-API-Key: <key>`
- Org-scoped keys (key belongs to org, can only access that org's resources)
- Rate limits: per org + per source IP
- No JWT/session — API key only

## Critical Endpoints for IDOR Testing

### Organizations
```
GET    /organizations                           # List orgs key has access to
GET    /organizations/{organizationId}          # Org details
GET    /organizations/{organizationId}/networks # Networks in org
GET    /organizations/{organizationId}/devices  # Devices in org
GET    /organizations/{organizationId}/admins   # Admin list (PII)
GET    /organizations/{organizationId}/apiKeys  # API keys (if perm)
GET    /organizations/{organizationId}/samlIdp  # SAML config
GET    /organizations/{organizationId}/license  # License info
```

### Networks
```
GET    /networks/{networkId}                    # Network details
GET    /networks/{networkId}/devices            # Devices in network
GET    /networks/{networkId}/clients            # Client list (PII: MAC, IP, user)
GET    /networks/{networkId}/traffic            # Traffic analysis
GET    /networks/{networkId}/events             # Event logs
GET    /networks/{networkId}/wireless/ssids     # SSID configs
GET    /networks/{networkId}/wireless/ssids/{number}/splash/settings  # Splash
GET    /networks/{networkId}/appliance/firewall/l3FirewallRules        # FW rules
GET    /networks/{networkId}/appliance/vpn/siteToSiteVpn               # VPN config
```

### Devices
```
GET    /devices/{serial}                        # Device details
GET    /devices/{serial}/clients                # Connected clients
GET    /devices/{serial}/switch/ports           # Switch port config
GET    /devices/{serial}/switch/ports/{portId}  # Specific port
GET    /devices/{serial}/cellular/sims          # MG SIM info
GET    /devices/{serial}/camera/video/link      # MV video link (HIGH VALUE)
GET    /devices/{serial}/liveTools/ping         # Live ping tool
GET    /devices/{serial}/liveTools/arpTable     # ARP table
```

### Wireless-Specific
```
GET    /organizations/{organizationId}/wireless/devices/connectionStats
GET    /organizations/{organizationId}/wireless/clients/connectionStats
GET    /networks/{networkId}/wireless/ssids/{number}/splash/settings
PUT    /networks/{networkId}/wireless/ssids/{number}/splash/settings
GET    /organizations/{organizationId}/splash/themes
POST   /organizations/{organizationId}/splash/themes
POST   /organizations/{organizationId}/splash/themes/{themeId}/assets
```

### Systems Manager (ikarem.io integration)
```
GET    /networks/{networkId}/sm/devices         # MDM devices
GET    /networks/{networkId}/sm/devices/{id}    # Device details
GET    /networks/{networkId}/sm/profiles        # Config profiles
POST   /networks/{networkId}/sm/profiles        # Create profile
GET    /networks/{networkId}/sm/apps            # Managed apps
```

## IDOR Test Matrix

### Test Cases (PRE-AUTH — no valid key)
| Test | Expected | Actual (if vuln) |
|------|----------|------------------|
| `GET /organizations/{other_org_id}` w/o key | 401/403 | 200 + data |
| `GET /organizations/{other_org_id}` w/ expired key | 401 | 200 + data |
| `GET /organizations/{other_org_id}` w/ key from org A | 403 | 200 + org B data |
| `GET /networks/{other_net_id}` w/ org A key | 403/404 | 200 + net data |
| `GET /devices/{other_serial}` w/ org A key | 403/404 | 200 + device data |
| `GET /devices/{serial}/camera/video/link` w/o perms | 403 | 200 + video URL |

### Rate Limit Bypass for Enumeration
- Per org: ~5 req/sec burst, sustained lower
- Per source IP: stricter
- Bypass: Distributed IPs, sequential orgId enumeration (numeric, predictable)
- Org IDs: numeric, sequential allocation (e.g., 123456, 123457)
- Network IDs: `N_` + base64-ish (less predictable)
- Device serials: `Q2XX-XXXX-XXXX` format, MAC-derived

### Dashboard Shard Isolation
- Shards: n1, n88, n100, n1063, n1126, n1152+, n1153+, n1154+, n1155+, n1156+
- Each shard = separate Dashboard instance
- Test cross-shard IDOR: n1 key -> n88 API endpoint

## High-Value Data Targets (Scope)
| Data | Endpoint | Bounty Tier |
|------|----------|-------------|
| Device secrets / crypto keys | `/devices/{serial}` + config | P1 |
| MV camera footage | `/devices/{serial}/camera/video/link` | P1 |
| Customer credentials / PII | `/networks/{netId}/clients`, `/orgs/{orgId}/admins` | P1 |
| Full secure boot compromise | Firmware signing keys | P1 |
| AWS keys in Accounts | `/organizations/{orgId}/accounts` (if exists) | P1 |

## Cross-Org Chain Potential
```
API Key (org A) --IDOR--> Org B data --device claim--> Device C --LSP default creds--> Shell
API Key (org A) --IDOR--> Network D --splash config--> SSRF/XSS --> Admin E
```

## References
- API Docs: https://developer.cisco.com/meraki/api-v1/
- OpenAPI Spec: https://create.meraki.io/api-docs/
- Scope: *.meraki.com, *.ikarem.io, *.network-auth.com