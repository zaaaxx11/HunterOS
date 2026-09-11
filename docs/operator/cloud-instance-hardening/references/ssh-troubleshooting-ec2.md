# SSH Troubleshooting — EC2 Instance Connection Failures

## Systematic Diagnostic Checklist

When `ssh user@ip` times out or fails, check **in order**:

### 1. Instance State & Network Basics
```bash
aws ec2 describe-instances --instance-ids i-xxxxx \
  --query 'Reservations[].Instances[].[State.Name,PublicIpAddress,PrivateIpAddress,SubnetId,VpcId]'
```
- State = `running`
- Has public IP (or use SSM/VPN for private-only)
- Subnet has `MapPublicIpOnLaunch = true`

### 2. Security Group (Instance-Level Firewall)
```bash
aws ec2 describe-security-groups --group-ids sg-xxxxx \
  --query 'SecurityGroups[].IpPermissions[?FromPort==`22`]'
```
**Must have**:
- Ingress rule: TCP port 22 from **your IP only** (`x.x.x.x/32`)
- ❌ **Never** `0.0.0.0/0` on port 22

### 3. Network ACL (Subnet-Level Stateless Firewall)
```bash
aws ec2 describe-network-acls --filters Name=vpc-id,Values=vpc-xxxxx \
  --query 'NetworkAcls[].Entries[?PortRange.From==`22`]'
```
- NACLs are **stateless** — need **both** inbound AND outbound allow rules
- Default NACL allows all; custom NACLs often block return traffic

### 4. Route Table (Internet Gateway Path)
```bash
aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-xxxxx \
  --query 'RouteTables[].Routes[?GatewayId!=null]'
```
- Subnet route table must have `0.0.0.0/0` → `igw-xxxxx` (Internet Gateway)
- No IGW = no public internet access

### 5. Key Pair (Authentication)
```bash
aws ec2 describe-instances --instance-ids i-xxxxx \
  --query 'Reservations[].Instances[].KeyName'
```
- Instance **must** have a KeyName at launch
- You **must** have the matching `.pem` private key
- User: `ubuntu` (Ubuntu), `ec2-user` (Amazon Linux), `admin` (Debian), `centos` (CentOS)

### 6. SSH Service Running (OS-Level)
Check via **EC2 Console Output** (no SSH needed):
```bash
aws ec2 get-console-output --instance-id i-xxxxx --query 'Output' --output text
```
Search for: `Started OpenBSD Secure Shell server` or `sshd`

If missing: SSH not installed/enabled → use **User Data** to install on next boot:
```bash
#!/bin/bash
apt-get update && apt-get install -y openssh-server
systemctl enable --now ssh
```

### 6b. SSH Config Hardening (If Connected)
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

---

## Alternative Access Methods (When SSH Fails)

### A. EC2 Instance Connect (Browser SSH)
- **Console → Instance → Connect → EC2 Instance Connect**
- Zero config, uses IAM auth, works if SG allows 22 from AWS IP ranges
- Requires: Instance Connect package installed (default on Ubuntu 20.04+/AL2023)

### B. AWS Systems Manager Session Manager
```bash
# Prereqs: IAM role with AmazonSSMManagedInstanceCore + SSM Agent running
aws ssm start-session --target i-xxxxx
```
- **No port 22 open** (SG can deny all inbound)
- Full audit trail in CloudTrail
- IAM-based access control (not keys)

### C. Serial Console (Emergency)
- Console → Instance → Connect → EC2 Serial Console
- Requires: Nitro-based instance, IAM permission, GRUB config
- Works even if network/SSH completely broken

### D. User Data Key Injection (Reboot Required)
If you lost the key pair:
1. Stop instance
2. Modify User Data with your public key:
```bash
#!/bin/bash
echo "ssh-rsa AAAA... your-public-key" >> /home/ubuntu/.ssh/authorized_keys
chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
chmod 600 /home/ubuntu/.ssh/authorized_keys
```
3. Start instance → SSH with your private key

---

## Debugging Console Output (Boot Logs)

```bash
# Get full console output (includes multiple boots)
aws ec2 get-console-output --instance-id i-xxxxx --query 'Output' --output text
```

**Look for**:
- `[  OK  ] Started OpenBSD Secure Shell server`
- `cloud-init: Cloud-init v. xx.x-xubuntu1.xx running 'init'`
- `ci-info: | ens5 | True | 172.31.xx.xx | ...`
- `[  OK  ] Reached target Network is Online`
- Error messages: `"Failed to start..."`, `"Permission denied"`, etc.

**Multiple boot sequences** in output = instance was rebooted/stopped-started since launch.

---

## Common Failure Patterns & Fixes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `Connection timed out` | SG/NACL/Route Table | Check 2→4 above |
| `Permission denied (publickey)` | Wrong user / wrong key / key not in authorized_keys | Verify KeyName, user, .pem file |
| `Connection refused` | SSH not running / wrong port | Check console output, install ssh |
| `Host key verification failed` | Instance replaced, known_hosts stale | `ssh-keygen -R <ip>` |
| `No supported authentication methods` | Password auth disabled, no key | Use correct .pem or Instance Connect |
| Works from browser (Instance Connect) but not CLI | Local SSH config / key format | Use `-i /path/key.pem`, check permissions 600 |

---

## Session Learnings (2026-07-22)

**Instance**: `i-0f31e81f4e401c681` (t4g.small, Ubuntu 22.04 ARM64, us-east-1)

**Findings**:
- SG `sg-0eea8aacf3bc4b5f8` had `0.0.0.0/0` on port 22 ⚠️
- NACL `acl-0bd32632d5b581f54` default allow all ✓
- Route table `rtb-0e2e2bd71c4aca082` had IGW ✓
- Key pair: `crypto-agent-key` — **user lacked private key** ← **ROOT CAUSE**
- Console output showed **two boot sequences** (instance rebooted since launch)
- SSH service confirmed running: `[  OK  ] Started OpenBSD Secure Shell server`
- SSM Agent installed but failing: `AccessDeniedException: Systems Manager's instance management role is not configured` (no IAM role)

**Resolution Path**: EC2 Instance Connect (browser) → or attach IAM role + SSM Session Manager

---

## ARM64 / Graviton Specific Notes

- `t4g.small` = ARM64 (Graviton2)
- User data scripts must be ARM64-compatible
- AWS CLI binary install: use `aarch64` URL (`awscli-exe-linux-aarch64.zip`)
- `pip3 install awscli` works universally (architecture-independent)

---

## TencentOS Server 4 (This Session's Host OS)

- Base: RHEL/CentOS compatible (`dnf`/`yum`)
- `awscli` **not in default repos** → use `pip3 install awscli`
- ARM64 support: standard

---

## Quick Reference Card

```
SSH TIMEOUT?
├─ 1. SG: Port 22 from MY IP?          → aws ec2 describe-security-groups
├─ 2. NACL: Inbound 22 + Ephemeral?    → aws ec2 describe-network-acls
├─ 3. Route Table: 0.0.0.0/0 → IGW?    → aws ec2 describe-route-tables
├─ 4. Instance: running + KeyName?     → aws ec2 describe-instances
├─ 5. Console Output: SSH started?     → aws ec2 get-console-output
└─ 6. Key Pair: Have matching .pem?    → ls ~/.ssh/ | grep KeyName

NO KEY? → EC2 Instance Connect (Browser) OR SSM Session Manager
```