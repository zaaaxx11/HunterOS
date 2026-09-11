---
name: cloud-instance-hardening
description: "harden cloud instances post-audit"
category: devops
tags:
  - aws
  - ec2
  - imdsv2
  - security-hardening
  - infrastructure
  - compliance
  - imds
  - metadata-service
---

# Cloud Instance Hardening Skill

## Scope
Defensive security hardening for cloud compute instances. **Not** offensive recon/exploitation — that belongs to `predator-recon` or `bug-bounty-agent`. This skill is for **operators securing their own infrastructure**.

## Core Hardening Checklist (AWS EC2)

### 1. IMDSv2 Enforcement (Critical)
**Risk**: IMDSv1 (`Optional`) allows SSRF → credential theft via `http://169.254.169.254/latest/meta-data/iam/security-credentials/`
**Fix**: Require session token (PUT → GET)
```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxxxx \
  --http-tokens required \
  --http-endpoint enabled \
  --region <region>
```
**Note**: Modern EC2 (2024+) often applies `required` → `applied` **without stop/start** on running instances. Older instances require **Stop → Start** (reboot insufficient). Check `State` field: `pending` → `applied` confirms active enforcement.

### 2. IMDS Hop Limit (Defense in Depth)
```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxxxx \
  --http-put-response-hop-limit 1 \
  --region <region>
```
Prevents metadata access from containers/pods (hop limit 1 = only host).

### 3. Disable IMDS Entirely (If Unused)
```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxxxx \
  --http-endpoint disabled \
  --region <region>
```
Only if instance doesn't need instance metadata (no IAM role, no user-data scripts).

### 4. Security Groups — Least Privilege
- **Ingress**: Only required ports (22/SSH → your IP only, 443/HTTPS → world)
- **Egress**: Restrict to required destinations (deny all → allowlist)
- **No 0.0.0.0/0 on port 22** ever

### 5. SSH Hardening
```bash
# /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
```
Then: `systemctl reload sshd`

### 6. IAM Instance Profile — Least Privilege
- Attach **only** required permissions (e.g., `AmazonSSMManagedInstanceCore` for Session Manager)
- **No** `AdministratorAccess`, `PowerUserAccess`, or broad `*` policies
- Use condition keys: `aws:SourceVpce`, `aws:SourceIp` where possible

### 7. SSM Session Manager (Replace SSH)
```bash
# Install SSM Agent (Amazon Linux 2023 / RHEL / Ubuntu)
dnf install -y amazon-ssm-agent  # or apt/yum
systemctl enable --now amazon-ssm-agent
```
Then connect via: `aws ssm start-session --target i-xxxxx`
- No open port 22
- Full audit trail in CloudTrail
- IAM-based access control

### 8. User Data / Cloud-init — No Secrets
- Never put API keys, passwords, tokens in user-data
- Use **Secrets Manager** / **Parameter Store (SecureString)** + IAM role
- Retrieve at runtime via AWS SDK / CLI

### 9. EBS Encryption & Snapshots
- Root volume: encrypted (default on new accounts)
- Snapshots: encrypted, not public
- `aws ec2 describe-snapshots --owner-ids self --query 'Snapshots[?Encrypted==`false`]'`

### 10. Automated Compliance Checks
```bash
# Quick audit script
aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,State.Name,MetadataOptions.HttpTokens,MetadataOptions.HttpEndpoint,IamInstanceProfile.Arn,SecurityGroups[*].GroupId]' --output table
```

---

## AWS CLI Installation (Per-Distro)

| Distro | Command |
|--------|---------|
| **Amazon Linux / RHEL / CentOS / Fedora / TencentOS** | `pip3 install awscli --upgrade` (dnf/yum often lacks `awscli` package) |
| **Ubuntu / Debian** | `apt update && apt install -y awscli` |
| **Alpine** | `apk add aws-cli` |
| **Universal (binary)** | `curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && sudo ./aws/install` |

**ARM64 (Graviton / t4g)**: Use `aarch64` binary URL: `https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip`

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| `aws: command not found` | CLI not installed | Use distro-specific install above |
| `Unable to locate credentials` | No `aws configure` / no IAM role | Run `aws configure` or attach instance profile |
| `modify-instance-metadata-options` returns `pending` but never `applied` | Instance running, not stopped | **Stop → Start** instance (reboot insufficient) |
| IMDSv2 breaks user-data scripts | Scripts use `curl http://169.254.169.254/...` | Update scripts to use IMDSv2: `TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600") && curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/...` |
| SSM Agent not connecting | Instance profile missing `AmazonSSMManagedInstanceCore` | Attach managed policy to instance role |

---

## Verification Commands

```bash
# 1. IMDSv2 status
aws ec2 describe-instances --instance-ids i-xxxxx \
  --query 'Reservations[].Instances[].MetadataOptions.{HttpTokens:HttpTokens,HttpEndpoint:HttpEndpoint,State:State}'

# 2. Security groups with 0.0.0.0/0 on port 22
aws ec2 describe-security-groups \
  --query 'SecurityGroups[?IpPermissions[?FromPort==`22` && IpRanges[?CidrIp==`0.0.0.0/0`]]].GroupId'

# 3. Instances without IAM role
aws ec2 describe-instances \
  --query 'Reservations[].Instances[?IamInstanceProfile==null].[InstanceId,State.Name]'

# 4. Unencrypted EBS volumes
aws ec2 describe-volumes --query 'Volumes[?Encrypted==`false`].[VolumeId,State]'

# 5. Public snapshots
aws ec2 describe-snapshots --owner-ids self --query 'Snapshots[?Encrypted==`false`].[SnapshotId,VolumeSize]'
```

---

## References
- `references/aws-imdsv2-hardening.md` — Deep dive: IMDSv1 vs v2, token TTL, hop limit, container implications
- `references/aws-cli-install-per-distro.md` — Extended install matrix, version pinning, virtualenv best practices
- `references/ssm-session-manager-setup.md` — Full SSM setup: hybrid activations, VPC endpoints, KMS encryption
- `references/ssh-troubleshooting-ec2.md` — Systematic SSH connection failure diagnosis: SG, NACL, Route Table, Key Pair, Console Output, alternative access methods (Instance Connect, SSM, Serial Console)

---

## Related Skills
- `predator-recon` — Offensive counterpart (recon → exploit). Use for *testing* your hardening.
- `bug-bounty-agent` — Full-spectrum offensive agent. Not for defensive ops.
- `session-hygiene` — Hermes session maintenance (unrelated but same category).