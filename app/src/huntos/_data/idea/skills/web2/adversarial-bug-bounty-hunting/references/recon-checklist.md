# RECON CHECKLIST — COMPLETE

## Phase 1: Target Identification (5 min max)

### Gossip Protocol Dump
```bash
# Connect to entrypoint
solana-gossip dump entrypoint.mainnet-beta.solana.com:8001 > gossip_dump.json

# Extract all validator identities
jq -r '.contact_info[].pubkey' gossip_dump.json > identities.txt
# Each line = validator identity_pubkey
```

### RPC Enumeration
```bash
# ALL vote accounts (validators + stake)
curl -X POST <RPC_URL> \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getVoteAccounts"}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data['result']['current']:
    print(f'{v[\"nodePubkey\"]} -> {v[\"votePubkey\"]} : {v[\"activatedStake\"]/1e9:.2f} SOL')
"

# ALL cluster nodes (gossip IPs)
curl -X POST <RPC_URL> \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getClusterNodes"}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for n in data['result']:
    if n['gossip'] != 'N/A':
        print(f'{n[\"pubkey\"]} : {n[\"gossip\"]}')
"
```

### Cross-Reference Map
```python
# Build identity_pubkey -> vote_pubkey -> gossip_ip -> stake
# This is your COMPLETE TARGET DOSSIER
```

---

## Phase 2: Attack Surface Mapping

### Cloud Provider Fingerprinting
| IP Range | Provider | Metadata Endpoint |
|----------|----------|-------------------|
| `35.x.x.x` | **GCP** | `http://metadata.google.internal/computeMetadata/v1/` |
| `141.95.x.x` | **DigitalOcean** | `http://169.254.169.254/metadata/v1.json` |
| `207.241.x.x` | **DigitalOcean** | Same |
| `160.202.x.x` | **DigitalOcean** | Same |
| `152.236.x.x` | **DigitalOcean** | Same |
| `170.23.x.x` | **DigitalOcean** | Same |
| `64.130.x.x` | **Choopa/Vultr** | `http://169.254.169.254/v1/` |
| `67.20x.x.x`, `67.21x.x.x` | **Choopa/Vultr** | Same |
| `198.13.x.x` | **Leaseweb** | `http://169.254.169.254/metadata/` |
| `86.54.x.x` | **Leaseweb** | Same |
| `88.216.x.x` | **Leaseweb/Hetzner** | Varies |
| `188.42.x.x` | **Hetzner** | `http://169.254.169.254/metadata/` |
| `94.158.x.x` | **Hetzner** | Same |
| `23.109.x.x` | **Unknown** | Investigate |

### Port Exposure Matrix
| Port | Service | Risk |
|------|---------|------|
| 8000/8001 | Gossip | **HIGH** — validator identity, network topology |
| 8899 | RPC | **HIGH** — full node control if exposed |
| 8002-8003 | TPU/TVU | **MEDIUM** — transaction ingestion |
| 22 | SSH | **CRITICAL** — if key auth, leads to keypair |
| 80/443 | HTTP/HTTPS | **LOW** — usually monitoring only |

### Stake Concentration Analysis
```python
# Top N validators = X% of total stake
# If top 10 = 40%+, targeting them gives disproportionate impact
# If 20% stake = 10 validators, each ~2% = achievable compromise
```

---

## Phase 3: Key Location Profiling

### Priority Matrix by Cloud Provider

| Provider | P0 (Immediate) | P1 (If Network) | P2 (Passive) |
|----------|----------------|-----------------|--------------|
| **GCP** | Secret Manager, GCS buckets | Metadata server, IAM roles | Cloud Logging, Build artifacts |
| **DigitalOcean** | Spaces buckets, Droplet metadata | VPC, Load balancer configs | DO API tokens in CI/CD |
| **Choopa/Vultr** | Object Storage, Instance metadata | Vultr API, Firewall rules | Backup snapshots |
| **Leaseweb** | Object Storage, Server metadata | Leaseweb API, Private networks | Backup configs |
| **Hetzner** | Storage Box, Robot API, Server metadata | Hetzner Cloud API, Firewall | Backup space |

### File Patterns to Hunt
```
validator-keypair.json
vote-account-keypair.json
identity.json
solana-identity.json
keypair.json
private-key.json
secret.json
.env
config.yaml
docker-compose.yml
```

---

## Recon Output Template
```
TARGET DOSSIER
==============
Validator: <identity_pubkey>
Vote Account: <vote_pubkey>
Stake: <X> SOL (<Y>%)
Gossip IP: <IP:PORT>
Cloud Provider: <Provider>
Metadata Endpoint: <URL>
Exposed Ports: [8000, 8899, 22, ...]
Key Locations (Probability):
  - GCS Bucket: HIGH
  - Metadata: MEDIUM
  - Docker: LOW
Acquisition Priority: P0/P1/P2
```