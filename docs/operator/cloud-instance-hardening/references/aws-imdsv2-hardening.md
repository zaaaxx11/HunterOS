# AWS IMDSv2 Hardening — Deep Dive

## IMDSv1 vs IMDSv2

| Aspect | IMDSv1 (Optional) | IMDSv2 (Required) |
|--------|-------------------|-------------------|
| **Auth** | None (open) | Session token required |
| **Request** | GET only | PUT (get token) → GET (with token) |
| **Token TTL** | N/A | Configurable (1-21600 sec, default 21600 = 6h) |
| **Hop Limit** | N/A | Configurable (1-64, default 1) |
| **SSRF Risk** | **Critical** | **Mitigated** |

## Token Flow (IMDSv2)

```bash
# 1. Get token (PUT request)
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")

# 2. Use token (GET request with header)
curl -H "X-aws-ec2-metadata-token: $TOKEN" \
  "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
```

## Hop Limit — Container Defense

| Value | Effect |
|-------|--------|
| 1 (default) | Only host can reach IMDS (container packets TTL=1 → dropped) |
| 2+ | Containers/pods can reach IMDS (risky) |

**Set to 1** unless you explicitly need containers to access instance metadata.

## TTL (Token Time-to-Live)

- **Range**: 1 second to 21600 seconds (6 hours)
- **Default**: 21600
- **Trade-off**: Longer TTL = fewer PUT requests = better perf, but longer token validity if leaked
- **Recommendation**: 21600 (6h) for most workloads; lower for high-security

## Enforcement States

| State | Meaning |
|-------|---------|
| `pending` | Change requested, waiting for instance stop/start |
| `applied` | Active and enforced |

**Critical**: Running instances require **Stop → Start** (not reboot) for `pending` → `applied`.

## AWS CLI Commands

### Check Current State
```bash
aws ec2 describe-instances --instance-ids i-xxxxx \
  --query 'Reservations[].Instances[].MetadataOptions'
```

### Enforce IMDSv2 (Required)
```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxxxx \
  --http-tokens required \
  --http-endpoint enabled \
  --http-put-response-hop-limit 1 \
  --region us-east-1
```

### Disable IMDS Entirely
```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxxxx \
  --http-endpoint disabled \
  --region us-east-1
```

### Bulk Enforcement (All Instances)
```bash
aws ec2 describe-instances \
  --query 'Reservations[].Instances[?MetadataOptions.HttpTokens==`optional`].InstanceId' \
  --output text | xargs -I {} aws ec2 modify-instance-metadata-options \
  --instance-id {} --http-tokens required --http-endpoint enabled
```

## Impact on Applications

### Breaking Changes (IMDSv1 → v2)
| Pattern | Fix |
|---------|-----|
| `curl http://169.254.169.254/latest/meta-data/...` | Add token flow (see above) |
| AWS SDKs (old versions) | Upgrade SDK (v2+ auto-handles IMDSv2) |
| Custom user-data scripts | Update to IMDSv2 pattern |
| Container workloads (k8s, ECS) | Ensure hop limit = 1 (default) — containers blocked |

### SDK Compatibility
| SDK | IMDSv2 Support |
|-----|----------------|
| AWS SDK for Go v2 | ✅ Auto |
| AWS SDK for Java 2.x | ✅ Auto |
| AWS SDK for Python (boto3) | ✅ Auto (1.9.200+) |
| AWS SDK for JavaScript v3 | ✅ Auto |
| AWS CLI v2 | ✅ Auto |
| AWS CLI v1 | ⚠️ Manual (deprecated) |

## Terraform / IaC

```hcl
resource "aws_instance" "hardened" {
  # ...
  
  metadata_options {
    http_tokens               = "required"
    http_endpoint             = "enabled"
    http_put_response_hop_limit = 1
    instance_metadata_tags    = "disabled"
  }
}
```

## Compliance Checks

### Config Rule (AWS Config)
```json
{
  "ConfigRuleName": "ec2-instance-metadata-v2-enforced",
  "Description": "Checks if EC2 instances have IMDSv2 required",
  "Scope": { "ComplianceResourceTypes": ["AWS::EC2::Instance"] },
  "Source": {
    "Owner": "AWS",
    "SourceIdentifier": "EC2_INSTANCE_METADATA_V2_ENFORCED"
  }
}
```

### Security Hub Control
- **Control**: EC2.8 — "EC2 instances should have IMDSv2 enabled"
- **Standard**: AWS Foundational Security Best Practices

## Attack Scenarios Blocked

| Attack | IMDSv1 | IMDSv2 (Required) |
|--------|--------|-------------------|
| SSRF → `http://169.254.169.254/latest/meta-data/iam/security-credentials/` | ✅ Credentials stolen | ❌ 401 Unauthorized (no token) |
| SSRF → User data (secrets in user-data) | ✅ Exposed | ❌ 401 |
| Container escape → host metadata | ✅ If hop limit > 1 | ❌ Hop limit 1 drops container traffic |
| Token theft → replay | N/A | ⚠️ Valid for TTL (mitigate: short TTL) |

## References
- [AWS Docs: IMDSv2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html)
- [AWS Blog: IMDSv2](https://aws.amazon.com/blogs/security/defense-in-depth-open-firewalls-reverse-proxies-ssrf/)
- [Config Rule: EC2_INSTANCE_METADATA_V2_ENFORCED](https://docs.aws.amazon.com/config/latest/developerguide/ec2-instance-metadata-v2-enforced.html)