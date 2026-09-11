# Meraki ikarem.io Internal Services Recon — Reference

## Source
Session: CDC Audit Cisco Meraki (2026-08-22)
Files: `meraki_step3_ikarem_recon.md`, `meraki_step3_ikarem_results.md`

## Summary
**Most internal services are properly protected** behind Okta SSO + VPN + firewall. No direct external findings. Only exploitable **post-LSP compromise** (network pivot).

## Subdomain Categories (174 discovered)

### CI/CD & Deployment
| Subdomain | Service | Status | Protection |
|-----------|---------|--------|------------|
| `argo-*.ikarem.io` | ArgoCD/Envoy | 403 / Conn reset | K8s GitOps, internal only |
| `argo-test-runner-usw.ikarem.io` | Test Runner | 403 | Internal |

### Artifact Repository
| Subdomain | Service | Status | Protection |
|-----------|---------|--------|------------|
| `artifactory*.ikarem.io` | JFrog Artifactory | 403 | Auth required |
| `docker*.artifactory.ikarem.io` | Docker Registry | 403 | Auth required |

### Infrastructure & Monitoring
| Subdomain | Service | Status | Protection |
|-----------|---------|--------|------------|
| `netbox.staging.infra.ikarem.io` | NetBox (IPAM/DCM) | Conn reset | Internal network only |
| `envoy-*.ikarem.io` | Envoy Gateway | 400 / Conn reset | Service mesh, internal |

### AI/ML & Marketplace
| Subdomain | Service | Status | Protection |
|-----------|---------|--------|------------|
| `ai-marketplace.ikarem.io` | AI Marketplace | `RBAC: access denied` | RBAC + Auth |
| `data-squire.dev.ikarem.io` | Data Squire | 302 → Okta SSO | Okta + VPN required |

## Probe Results

### ✅ Protected Services (No Anonymous Access)
| Service | Endpoint | Result | Protection |
|---------|----------|--------|------------|
| **Jira Security** | `jira.sec.ikarem.io/rest/api/2/serverInfo` | `{"message":"Missing Authentication Token"}` | Bearer token required |
| **Artifactory** | `artifactory.ikarem.io/artifactory/api/repositories` | 403 Forbidden | Auth required |
| **Docker Registry** | `docker.artifactory.ikarem.io/v2/_catalog` | 403 Forbidden | Auth required |
| **AI Marketplace** | `ai-marketplace.ikarem.io/` | `RBAC: access denied` | RBAC + Auth |
| **Data Squire** | `data-squire.dev.ikarem.io/` | 302 → Okta SSO | Okta + VPN required |

### ⚠️ Connection Reset (Likely Firewall/Internal Only)
| Service | Endpoint | Result | Likely Cause |
|---------|----------|--------|--------------|
| **ArgoCD** | `argo-envoy.ikarem.io/api/version` | Connection reset | Internal network only |
| **NetBox** | `netbox.staging.infra.ikarem.io/api/` | Connection reset | Internal network only |

## Key Findings

### 1. Okta SSO Integration
- `data-squire.dev.ikarem.io` → `squire.dev.ikarem.io` → Okta login
- Explicit "MUST be on VPN for self-unlock" banner
- Client ID: `0oa1u59ng8xNodPNr358`
- Okta version: 7.48.1 (Sign-in Widget)
- Sentry DSN exposed in login page (info leak)

### 2. Certificate Transparency
- Wildcard certs: `*.mcp-gateway-registry.ikarem.io`
- Issuer: HydrantID (IdenTrust)
- Short validity (~2.5 months)

### 3. Network Architecture
- All services behind Envoy service mesh
- ALB/ELB frontends (AWS)
- K8s namespaces: `staging`, `development`, `production`, `koala-commercial`
- Internal DNS: `*.k8s.ikarem.io`

## Chain with LSP Compromise
If attacker achieves **LSP root shell**:
1. **Network pivot** → Access internal Meraki network from compromised device
2. **VPN/Okta bypass** → Device may have certs/tokens for internal services
3. **Internal recon** → Probe `*.ikarem.io` from trusted network position
4. **Lateral movement** → ArgoCD → deploy malicious workloads
5. **Supply chain** → Artifactory → poison Docker images/firmware
6. **Network topology** → NetBox → full infrastructure map

## Bounty Assessment
| Finding | Severity | Eligible |
|---------|----------|----------|
| Sentry DSN in Okta login page | P4 (Info leak) | Maybe |
| Connection reset vs 403 (info leak via error diff) | P4 | Maybe |
| Wildcard cert scope (`*.mcp-gateway-registry`) | P4 | Maybe |

**Overall**: Internal services well-protected. No direct P1-P3 findings from external probing.