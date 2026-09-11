# ikarem.io Internal Services Recon

## Overview
`*.ikarem.io` — Meraki internal services domain. Scope says: "higher reward range." Systems Manager (MDM) runs here.

## Live Subdomains (from passive enumeration)
| Subdomain | Service | Notes |
|-----------|---------|-------|
| `argo-eshard.ikarem.io` | ArgoCD (GitOps) | 403, Envoy gateway |
| `argo-eshard-spare.ikarem.io` | ArgoCD spare | 403 |
| `argo-outpost.ikarem.io` | ArgoCD outpost | 403 |
| `argo-outpost-spare.ikarem.io` | ArgoCD outpost spare | 403 |
| `argo-spare.ikarem.io` | ArgoCD spare | 403 |
| `argo-test-runner-usw.ikarem.io` | Argo test runner | 403 |
| `argo-envoy.ikarem.io` | Envoy gateway | 403 |
| `artifactory.ikarem.io` | JFrog Artifactory | 403, AWS ELB |
| `artifactory.int.ikarem.io` | Internal Artifactory | 403 |
| `artifactory.prod.ikarem.io` | Prod Artifactory | 403 |
| `closest.artifactory.ikarem.io` | Artifactory replica | 403 |
| `closest-replica.artifactory.ikarem.io` | Artifactory replica | 403 |
| `docker.artifactory.ikarem.io` | Docker registry | 403 |
| `docker-prod.closest.artifactory.ikarem.io` | Docker prod replica | 403 |
| `cnn.artifactory.ikarem.io` | CNN Artifactory | 403 |
| `cnw.artifactory.ikarem.io` | CNW Artifactory | 403 |
| `ai-marketplace.ikarem.io` | AI Marketplace | 403, Envoy |
| `netbox.staging.infra.ikarem.io` | NetBox (IPAM/DCIM) | HTTP, staging |
| `squire.dev.ikarem.io` | Squire (Meraki app?) | 301->Okta auth |
| `data-squire.dev.ikarem.io` | Data Squire | Okta auth |
| `envoy-default.shared-gateways.usw.staging.k8s.ikarem.io` | Envoy staging | 400 |
| `envoy-megaproxy.shared-gateways.use.development.k8s.ikarem.io` | Envoy dev | 404 |
| `jira.sec.ikarem.io` | Jira (security) | 403, JSON |
| `account.50k-aldi.ephemeral.exp.ikarem.io` | Ephemeral account | Dev |
| `ahmed1.dev.ikarem.io` | Dev account | Dev |
| `alejandroww.meraki-go.ikarem.io` | Meraki Go dev | Dev |
| `annika.dev.network-auth.ikarem.io` | Network-auth dev | Dev |

## Key Services Analysis

### ArgoCD (GitOps / Deployment)
- Multiple instances: eshard, outpost, spares
- Likely manages Meraki cloud deployments
- **Attack Vector:** If accessible, could deploy malicious configs to production
- **Check:** ArgoCD UI exposure, RBAC bypass, repo injection

### Artifactory (Binary Repository)
- Multiple: prod, int, closest, docker, cnn, cnw
- Stores: Firmware images, container images, libraries
- **Attack Vector:** Firmware supply chain — inject malicious firmware
- **Check:** Anonymous access, token leakage, repo permissions

### NetBox (IPAM / DCIM)
- Staging instance exposed via HTTP (not HTTPS)
- **Attack Vector:** Network topology disclosure, credential storage
- **Check:** Anonymous API access, webhook secrets

### Squire / Data-Squire
- Okta SSO integration (client_id: `0oa1u59ng8xNodPNr358`)
- Redirect URI: `https://squire.dev.ikarem.io/auth`
- **Attack Vector:** OAuth flow, token exchange, session fixation

### Jira Security
- `jira.sec.ikarem.io` — security team Jira
- 403 but JSON response suggests API endpoint
- **Attack Vector:** Issue tracking disclosure, internal vuln details

## Systems Manager (MDM) Integration

### Splash Page `sentryEnrollment`
- Configurable via `/networks/{networkId}/wireless/ssids/{number}/splash/settings`
- Fields: `sentryEnrollment` object in splash settings
- **Flow:** Guest connects -> splash page -> MDM enrollment via ikarem.io
- **Attack Vector:** Malicious splash page -> forced MDM enrollment -> device compromise

### Meraki Go Integration
- `alejandroww.meraki-go.ikarem.io` — Meraki Go (SMB product) uses ikarem.io
- **Attack Vector:** Cross-product data leakage

## Network Architecture
- All services behind Envoy gateways (`envoy-default.shared-gateways.*.k8s.ikarem.io`)
- Kubernetes-based (`.k8s.ikarem.io` in hostnames)
- Environments: staging, development, production (usw, use regions)
- TLS termination at Envoy, mTLS likely between services

## Attack Vectors to Validate

| Vector | Test | Priority |
|--------|------|----------|
| ArgoCD UI access | Browse `https://argo-eshard.ikarem.io` with auth bypass | Critical |
| Artifactory anonymous read | `curl -I https://artifactory.ikarem.io/artifactory/` | Critical |
| NetBox API exposure | `curl https://netbox.staging.infra.ikarem.io/api/` | High |
| Okta/OAuth misconfig | Test Squire redirect_uri validation, PKCE | High |
| Jira API info leak | `curl https://jira.sec.ikarem.io/rest/api/2/serverInfo` | Medium |
| MDM enrollment spoof | Craft splash page with malicious `sentryEnrollment` | Critical |
| Firmware in Artifactory | Search for `.bin`, `.img`, `.fw` files in repos | Critical |
| K8s API exposure | Check `https://<subdomain>/api/v1/namespaces/default/pods` | High |

## References
- Scope: `*.ikarem.io` (higher reward)
- Systems Manager docs: Meraki SM / MDM enrollment
- ArgoCD: https://argo-cd.readthedocs.io/
- Artifactory: https://jfrog.com/artifactory/
- NetBox: https://netbox.dev/