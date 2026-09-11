# Meraki-Specific Patterns (cut from cdc-device-audit SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/cdc/cdc-device-audit/SKILL.md` during the S2b-2
content pass (target-specific notes preserved, not deleted). The four meraki
case files that accompanied this section live in
`examples/hunts/cdc/cdc-device-audit/references/`:
meraki-lsp-command-injection.md, meraki-splash-ssrf.md, meraki-ikarem-recon.md,
meraki-cdc-final-report.md.

---

## Meraki-Specific Patterns (Reference)

### Local Status Page (LSP)
- **Default creds**: `admin` + Serial Number (per firmware table)
- **DNS Interception**: `mx.meraki.com`, `setup.meraki.com`, `ap.meraki.com` → local IP
- **Fixed IPs**: MR `10.128.128.126`, MS `1.1.1.100`, MX LAN gateway
- **Configure Tab Inputs**: Proxy URL, WAN IP, PPPoE, IPv6 → command injection targets
- **TLS**: Port 8092, self-signed `*.devices.meraki.direct` cert

### Splash Page SSRF
- Custom `splashUrl` may be fetched server-side by device/cloud
- Test: `http://169.254.169.254/latest/meta-data/` (AWS IMDS)

### ikarem.io Internal Services
- Protected by Okta SSO + VPN + firewall
- Only exploitable post-LSP compromise (network pivot)

## References (as listed in the SKILL.md at cut time)
- `examples/hunts/cdc/cdc-device-audit/references/meraki-lsp-command-injection.md` — LSP command injection details
- `examples/hunts/cdc/cdc-device-audit/references/meraki-splash-ssrf.md` — Splash SSRF test methodology
- `examples/hunts/cdc/cdc-device-audit/references/meraki-ikarem-recon.md` — ikarem.io internal services recon
- `examples/hunts/cdc/cdc-device-audit/references/meraki-cdc-final-report.md` — Full CDC audit report
