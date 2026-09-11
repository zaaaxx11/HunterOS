# Meraki Pre-Auth RCE Chain Architecture -- CDC Round 1 Synthesis

## Chain Template: Pre-Auth RCE Anatomy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PRE-AUTH RCE CHAIN TEMPLATE (Meraki)                         │
├─────────────────┬──────────────────┬─────────────────┬────────────────┬─────────┤
│  ENTRY VECTOR   │ TRUST BOUNDARY   │ PRIVILEGE       │ CODE EXECUTION │PERSISTEN│
│  (Unauth)       │ HOPS             │ ESCALATION      │ (Shell)        │CE       │
├─────────────────┼──────────────────┼─────────────────┼────────────────┼─────────┤
│ LSP: Default    │ LAN -> Device    │ Configure Tab   │ Proxy URL      │ Firmware│
│ Creds + DNS     │ Web Server       │ Injection       │ Command Inj.   │ Downgrade│
│ Intercept       │ (Digest MD5)     │ (Proxy/WAN/IP)  │ -> Shell       │ / Implant│
├─────────────────┼──────────────────┼─────────────────┼────────────────┼─────────┤
│ API IDOR        │ Org A -> Org B   │ Device Claim    │ LSP Default    │ Config  │
│ (Cross-Org)     │ Data Access      │ -> Serial Access│ Creds -> Shell │ Implant │
├─────────────────┼──────────────────┼─────────────────┼────────────────┼─────────┤
│ Splash SSRF     │ Guest WiFi ->    │ Cloud Metadata  │ ikarem.io      │ Supply  │
│ (splashUrl)     │ Meraki Cloud/    │ -> Internal Svc │ ArgoCD/Artif.  │ Chain   │
│                 │ Device Fetch     │ (Argo/Arti)     │ Deploy/Inject  │         │
├─────────────────┼──────────────────┼─────────────────┼────────────────┼─────────┤
│ Splash XSS      │ Untrusted HTML   │ Admin Session   │ Dashboard API  │ API Key │
│ (Theme Asset)   │ -> Dashboard     │ Hijack          │ -> Firmware    │ Theft / │
│                 │ Origin           │ (Cookie/Key)    │ Push -> Shell  │ Implant │
├─────────────────┼──────────────────┼─────────────────┼────────────────┼─────────┤
│ Subdomain       │ Attacker Infra   │ Splash Supply   │ Guest Comprom. │ Pivot   │
│ Takeover        │ -> Trusted       │ Chain           -> Cred Harvest  │ to LSP  │
│ (network-auth)  │ Splash Domain    │                 -> MDM Enroll    │         │
└─────────────────┴──────────────────┴─────────────────┴────────────────┴─────────┘
```

## Required Handoff Points (Bug A Output -> Bug B Input)

| ID | Name | From Bug | To Bug | Required Output | Validation |
|----|------|----------|--------|-----------------|------------|
| HP-LSP-001 | LSP Default Creds -> Configure Tab | LSP auth bypass | Configure tab CMDi | Auth session cookie, device serial, model, firmware | POST /configure with Proxy URL cmd injection |
| HP-LSP-002 | Configure Tab -> Shell Persistence | CMDi in Proxy/WAN | Firmware downgrade/implant | Root shell, writable partition, boot persistence | Survives reboot, config push, firmware update |
| HP-API-001 | API IDOR -> Cross-Org Device Access | IDOR on /orgs/{orgId}/devices | Device claim/LSP access | Target serial, MAC, LAN IP, orgId | DNS intercept + default creds works |
| HP-API-002 | Cross-Org -> Splash Config Write | IDOR + API key | Splash theme XSS/SSRF | Victim orgId, valid API key, networkId, ssidNum | POST /splash/settings triggers fetch |
| HP-SPLASH-001 | Splash Theme XSS -> Admin Session | Stored XSS in theme | Admin session hijack | XSS payload steals session/key, admin victim | Stolen session pushes firmware |
| HP-SPLASH-002 | Splash SSRF -> ikarem.io Internal | SSRF via splashUrl | Internal service compromise | SSRF endpoint, exfil channel, internal target | SSRF returns JWT/token/firmware from internal |
| HP-SUBDOMAIN-001 | Subdomain Takeover -> Splash Supply | Dangling CNAME | Guest compromise -> pivot | Controlled subdomain, victim orgs, harvest payload | Guest loads attacker content from network-auth.com |
| HP-FIRMWARE-001 | Firmware Supply Chain -> Device RCE | Artifactory/ArgoCD compromise | Device boots malicious fw | Malicious firmware, target serial, delivery vector | Device boots malicious fw; shell persists |

## Cross-Domain Trust Boundaries

```
*.network-auth.com (guest) -> *.meraki.com (admin)     : XSS in theme preview
*.network-auth.com (guest) -> *.meraki.com (cloud)     : SSRF via splashUrl fetch
*.meraki.com (admin)    -> hardware (device)           : Firmware push / config
*.meraki.com (admin)    -> *.ikarem.io (internal)      : ArgoCD deploy / Artifactory
hardware (LAN)          -> hardware (shell)            : LSP default creds + inj.
*.ikarem.io (internal)  -> hardware (fleet)            : Malicious firmware deploy
*.network-auth.com (att) -> hardware (guest)           : Subdomain takeover -> LSP pivot
```

## Validated Cross-Domain Chains (This Session)

### Chain Alpha: LSP-First (Highest Probability, Pure Pre-Auth)
```
DNS Intercept (mx.meraki.com)
    -> LSP Port 80/8092 (LAN)
    -> Default Creds (admin/serial)
    -> Configure Tab: Proxy URL = `http://proxy:port` + Command Injection
    -> Root Shell on Device
    -> [Optional] Firmware Downgrade for Persistence
```
**Domains**: hardware only (meraki.com for DNS intercept)
**Pre-Auth**: YES
**Evidence Needed**: CMDi in Proxy URL field confirmed on target firmware

### Chain Bravo: API-IDOR -> LSP (Pre-Auth if IDOR Unauth)
```
API IDOR: GET /organizations/{victim_org}/devices (no auth / expired key / cross-org)
    -> Extract target_device_serial + MAC
    -> DNS Intercept / Direct IP to LSP
    -> Default Creds (admin/serial)
    -> Configure Tab Injection -> Shell
```
**Domains**: meraki.com (API) -> hardware (LSP)
**Pre-Auth**: YES if IDOR works without valid key
**Evidence Needed**: Unauthenticated / cross-org IDOR on /organizations/{orgId}/devices

### Chain Charlie: Splash SSRF -> ikarem.io -> Firmware Supply Chain
```
Splash Config: useSplashUrl=true, splashUrl=http://169.254.169.254/latest/meta-data/
    -> Meraki Cloud/Device FETCHES splashUrl SERVER-SIDE
    -> AWS/GCP IMDS credentials exfiltrated
    -> Pivot to ikarem.io (ArgoCD/Artifactory) via cloud creds
    -> Inject malicious firmware into Artifactory
    -> ArgoCD deploys to fleet
    -> Devices auto-update -> Root Shell Fleet-Wide
```
**Domains**: network-auth.com -> meraki.com -> ikarem.io -> hardware
**Pre-Auth**: Requires splash config write (API key) OR self-registration abuse
**Evidence Needed**: Server-side fetch CONFIRMED; ikarem.io accessible with cloud creds

### Chain Delta: Splash XSS -> Dashboard Admin -> Firmware Push -> Device RCE
```
Attacker: API key with wireless:config:write (stolen/phished/IDOR)
    -> POST /orgs/{id}/splash/themes + assets (continue.html with XSS)
    -> Admin views Preview in Dashboard (nXXX.meraki.com)
    -> XSS steals _meraki_session / API key
    -> Attacker uses admin session: PUT /networks/{netId}/devices/{serial}/upgrade
    -> Malicious firmware pushed to device
    -> Device boots -> Root Shell
```
**Domains**: network-auth.com -> meraki.com -> hardware
**Pre-Auth**: NO (requires compromised API key or admin account)

### Chain Echo: Subdomain Takeover -> Splash Supply Chain -> Guest -> LSP Pivot
```
Attacker controls evil.network-auth.com (dangling CNAME / wildcard)
    -> Victim orgs use *.network-auth.com for splash hosting
    -> Guests connect to victim SSID -> load attacker splash page
    -> Splash page: credential harvest / drive-by / sentryEnrollment (MDM)
    -> Harvested creds -> Dashboard access -> Firmware push -> LSP -> Shell
    -> OR: Direct LSP pivot via guest network access to device LAN
```
**Domains**: network-auth.com (attacker) -> meraki.com (guest auth) -> hardware (LSP)
**Pre-Auth**: YES for guest compromise; NO for full RCE