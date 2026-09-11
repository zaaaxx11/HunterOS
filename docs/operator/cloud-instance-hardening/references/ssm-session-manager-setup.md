# AWS Systems Manager Session Manager — Complete Setup

## Why Session Manager?

- **No SSH keys** — no key management, rotation, or leakage risk
- **No open port 22** — SG can be 0 inbound; SSM uses outbound HTTPS (443)
- **Full audit trail** — every session logged to CloudWatch/S3
- **IAM-based access** — RBAC via IAM policies, not SSH keys
- **Works over Internet or PrivateLink** — no bastion needed

---

## Architecture

```
User (AWS CLI) → SSM API → SSM Agent (on instance) → Shell
     │                                        │
     │ IAM: ssm:StartSession                  │ IAM: AmazonSSMManagedInstanceCore
     ▼                                        ▼
CloudTrail/S3/CloudWatch Logs           Instance Profile
```

---

## Prerequisites

### 1. Instance Profile (IAM Role)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:DescribeAssociation",
        "ssm:GetDeployablePatchSnapshotForInstance",
        "ssm:GetDocument",
        "ssm:DescribeDocument",
        "ssm:GetManifest",
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:ListAssociations",
        "ssm:ListInstanceAssociations",
        "ssm:PutInventory",
        "ssm:PutComplianceItems",
        "ssm:PutConfigurePackageResult",
        "ssm:UpdateInstanceInformation",
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
        "ec2messages:AcknowledgeMessage",
        "ec2messages:DeleteMessage",
        "ec2messages:FailMessage",
        "ec2messages:GetEndpoint",
        "ec2messages:GetMessages",
        "ec2messages:SendReply"
      ],
      "Resource": "*"
    }
  ]
}
```
**Easier**: Attach AWS managed policy `AmazonSSMManagedInstanceCore` to instance role.

### 2. SSM Agent Installed & Running
- **Amazon Linux 2/2023, Ubuntu 20.04+, RHEL 8+**: Pre-installed
- **Others**: `dnf/yum/apt install amazon-ssm-agent` or snap
- **Verify**: `systemctl status amazon-ssm-agent`

### 3. Network Connectivity (Outbound HTTPS)
| Region Type | Endpoint |
|-------------|----------|
| Public | `ssm.{region}.amazonaws.com:443`, `ssmmessages.{region}.amazonaws.com:443`, `ec2messages.{region}.amazonaws.com:443` |
| VPC Endpoints (PrivateLink) | Create 3 Interface VPC Endpoints: `com.amazonaws.{region}.ssm`, `com.amazonaws.{region}.ssmmessages`, `com.amazonaws.{region}.ec2messages` + enable Private DNS |

**SG Rule**: Outbound 443 to 0.0.0.0/0 (or to VPC endpoint prefix list)

---

## User IAM Policy (Who Can Connect)

### Minimal Policy (StartSession only)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ssm:StartSession"],
      "Resource": [
        "arn:aws:ec2:*:*:instance/i-*",
        "arn:aws:ssm:*:*:document/SSM-SessionManagerRunShell"
      ],
      "Condition": {
        "StringEquals": {
          "ssm:resourceTag/Environment": "production"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": ["ssm:TerminateSession"],
      "Resource": ["arn:aws:ssm:*:*:session/*"]
    }
  ]
}
```

### With Tag-Based Access Control
```json
"Condition": {
  "StringEquals": {
    "ssm:resourceTag/Team": "platform",
    "ssm:resourceTag/Environment": "${aws:PrincipalTag/Environment}"
  }
}
```

---

## Connection Methods

### 1. AWS CLI (Interactive Shell)
```bash
# Basic
aws ssm start-session --target i-0f31e81f4e401c681 --region us-east-1

# With specific document (Linux vs Windows)
aws ssm start-session --target i-xxx --document-name AWS-StartInteractiveCommand --parameters command="bash"

# Port forwarding (tunnel)
aws ssm start-session --target i-xxx --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3306"],"localPortNumber":["3306"]}'

# Port forwarding to remote host (via instance)
aws ssm start-session --target i-xxx --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["rds-endpoint"],"portNumber":["3306"],"localPortNumber":["3306"]}'
```

### 2. SSH via Session Manager (Transparent Proxy)
**~/.ssh/config**:
```ssh
Host i-* mi-*
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
    IdentityFile ~/.ssh/id_rsa  # Optional (not used for auth)
```

Then: `ssh -i ~/.ssh/id_rsa ec2-user@i-0f31e81f4e401c681`

**Requires**: SSM document `AWS-StartSSHSession` (AWS managed) + instance has SSH server running.

### 3. Session Manager Plugin (Required for CLI)
```bash
# Linux x86_64
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "session-manager-plugin.deb"
sudo dpkg -i session-manager-plugin.deb

# Linux ARM64
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_arm64/session-manager-plugin.deb" -o "session-manager-plugin.deb"

# macOS
brew install --cask session-manager-plugin

# Windows
https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe
```

**Verify**: `session-manager-plugin --version`

---

## Logging & Auditing

### CloudWatch Logs
```bash
# Enable in Session Manager preferences (Console) or CLI:
aws ssm update-service-setting \
  --setting-id arn:aws:ssm:us-east-1:123456789012:servicesetting/ssm/session-manager/run-as-enabled \
  --setting-value "true" \
  --region us-east-1

# Log group: /aws/ssm/session-manager
# Log stream: <instance-id>/<session-id>
```

### S3 Logging (Encrypted)
```json
{
  "SessionManager": {
    "S3BucketName": "my-ssm-session-logs",
    "S3KeyPrefix": "session-logs/",
    "S3EncryptionEnabled": true,
    "KmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/..."
  }
}
```

### CloudTrail
All `StartSession`, `TerminateSession`, `ResumeSession` logged automatically.

---

## Advanced: RunAs Support (Non-root Users)

### 1. Enable in Session Manager Preferences
```bash
aws ssm update-service-setting \
  --setting-id arn:aws:ssm:us-east-1:123456789012:servicesetting/ssm/session-manager/run-as-enabled \
  --setting-value "true"
```

### 2. IAM Policy for RunAs
```json
{
  "Effect": "Allow",
  "Action": ["ssm:StartSession"],
  "Resource": "arn:aws:ec2:*:*:instance/i-*",
  "Condition": {
    "StringEquals": {
      "ssm:RunAs": ["ec2-user", "ubuntu", "ssm-user"]
    }
  }
}
```

### 3. Connect as Specific User
```bash
aws ssm start-session --target i-xxx --run-as ec2-user
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `SessionManagerPlugin not found` | Plugin not installed | Install plugin (see above) |
| `TargetNotConnected` | SSM agent not running / no network | Check agent status, SG outbound 443, VPC endpoints |
| `AccessDenied` on StartSession | Missing IAM permissions | Add `ssm:StartSession` + instance ARN |
| `InvalidInstanceId` | Instance not managed | Wait 5-10 min after agent start, check `aws ssm describe-instance-information` |
| Session hangs/freezes | MTU / packet loss | Reduce MTU on instance: `ip link set dev eth0 mtu 9001` |
| Port forwarding fails | Local port in use | Change `localPortNumber` |

---

## Verification Checklist

- [ ] Instance has IAM role with `AmazonSSMManagedInstanceCore`
- [ ] SSM agent running: `systemctl status amazon-ssm-agent`
- [ ] Instance appears in `aws ssm describe-instance-information`
- [ ] Outbound 443 to SSM endpoints (or VPC endpoints created)
- [ ] User has `ssm:StartSession` permission on instance ARN
- [ ] Session Manager plugin installed locally
- [ ] Test connection: `aws ssm start-session --target i-xxx`
- [ ] CloudWatch/S3 logging enabled and verified
- [ ] Port 22 removed from all SGs (optional but recommended)

---

## References

- AWS Docs: [Session Manager Setup](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started.html)
- AWS Docs: [VPC Endpoints for SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/vpc-endpoints.html)
- AWS Blog: [SSH over Session Manager](https://aws.amazon.com/blogs/mt/tunneling-ssh-over-session-manager/)
- GitHub: [SSM Agent](https://github.com/aws/amazon-ssm-agent)