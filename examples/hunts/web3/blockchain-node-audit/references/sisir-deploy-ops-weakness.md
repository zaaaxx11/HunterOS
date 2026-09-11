# Sisir Deploy-Ops Weakness Checklist — AElf Launcher + ebridge-contracts.aelf

Source session: 2026-08-15 AGENT-C DEPLOY-OPS-WEAKNESS. Targets: `/tmp/aelf2` (AElf node) + `/tmp/bridge_unzipped/ebridge-contracts.aelf-dev` (pure on-chain contracts). Grep anchors and evidence table are directly reproducible.

## Why this checklist exists

ebridge is *contracts only* — no `appsettings.json`, no Kestrel, no off-chain secrets — so a naive audit finds nothing. The real weakness surface is in the sibling `AElf.Launcher` that operators deploy with the contracts. Always audit both.

## 9-point grep recipe

```bash
# Enumerate deploy configs
find /tmp/aelf2 -name "appsettings*.json" -o -name "nuget.config" -o -name "Directory.Build.props" | xargs ls -la
find /tmp/bridge_unzipped -name "appsettings*.json" | head   # expect empty — false-positive guard

# 1 secrets
grep -rn "Pwd\|Password\|Secret\|ConnectionStrings\|Redis\|RabbitMQ\|StringEncryption\|Swagger.*secret\|MySql" /tmp/aelf2 --include="*.json" --include="*.cs"

# 2 CORS
grep -rn "CorsOrigins\|AllowAnyOrigin\|AddCors" /tmp/aelf2 --include="*.cs" --include="*.json"

# 3 internal IPs
grep -rn "192\.168" /tmp/aelf2 /tmp/bridge_unzipped

# 4 TLS
grep -rn "Kestrel\|RequireHttps\|TlsHelper\|ChainNodeApis" /tmp/aelf2 --include="*.cs" --include="*.json"
cat /tmp/aelf2/src/AElf.Launcher/appsettings.json | grep -A3 Kestrel

# 5 admin keys
grep -rn "Admin\|Controller\|PauseController\|NodeAccount\|keyStore\|PrivateKey" /tmp/bridge_unzipped/contract --include="*.cs" | head -n 60
grep -rn "NodeAccount\|KeyStoreDir\|CreateAccount" /tmp/aelf2/src --include="*.cs" | head -n 40

# 6 upgradeability
grep -rn "ContractDeploymentAuthority\|ValidateOrganizationExist\|Parliament\|Association" /tmp/bridge_unzipped --include="*.cs"
grep -rn "ContractDeploymentAuthority\|Genesis" /tmp/aelf2/src --include="*.cs" | head -n 40

# 7 logs
grep -rn "Serilog\|UseSerilog\|Log.*Password\|Log.*PrivateKey" /tmp/aelf2 --include="*.cs"

# 8 supply chain
cat /tmp/aelf2/nuget.config; cat /tmp/aelf2/Directory.Build.props; cat /tmp/aelf2/common.props
cat /tmp/bridge_unzipped/ebridge-contracts.aelf-dev/nuget.config

# 9 Dockerfile
find /tmp/aelf2 -name "Dockerfile*" | xargs cat 2>/dev/null | head -n 30
cat /tmp/aelf2/docker/docker-compose.yml
ls /tmp/bridge_unzipped/ebridge-contracts.aelf-dev/scripts/*.sh | head
```

## Evidence table (fill per target)

| # | Check | File:line | Finding | Impact | Confidence |
|---|-------|-----------|---------|--------|------------|
|1|Secrets|`src/AElf.Launcher/appsettings.json:8 NodeAccountPassword=""`|Empty password → `AElfKeyStore.EncryptAndGenerateDefaultKeyStoreAsJson("", privKey)` scrypt cost trivial|HIGH if host fs exposed|PROVEN|
|1b|Redis|`appsettings.json:8 redis://localhost:6379?db=1`|No auth, no TLS|HIGH if `bind 0.0.0.0`|PROVEN|
|2|CORS|`appsettings.json:6 CorsOrigins:*` `Startup.cs:53-66`|Wildcard + Always AllowAnyHeader/Method|MEDIUM-HIGH (API CSRF)|PROVEN|
|3|IPs|`docs/tutorials/setup/docker-multi-node.md:92 192.168.1.70`|Doc example, not runtime|LOW|INFO|
|4|TLS|`appsettings.json:22 http://*:8000/` `TlsHelper.cs:50 SetNotAfter MaxValue`|Plain HTTP + 9999-year self-signed|HIGH|PROVEN|
|5|Admin EOA|`BridgeContract.cs:43 ChangeAdmin` only `Admin`|Single EOA takeover, `PauseController` DOS, `TokenPool.cs:20` author check commented out|CRITICAL|PROVEN|
|6|Upgrade|`MainChainAElfModule.cs:39 Required=false` `BridgeContract.cs:92 ValidateOrganizationExists` only for 2 setters|No DAO gate on most admin setters|MEDIUM|PROVEN|
|7|Logs|`Program.cs:45 ClearProviders` no Serilog|Only password-oracle log|LOW|PROVEN|
|8|Feed|`nuget.config:6 int.nugettest.org/api/v2`|Dependency confusion vector|MEDIUM|PROVEN|
|9|Dockerfile|`Dockerfile:1 sdk:3.1` EOL + `COPY . .` + `docker login -p` in `ps`|Patch lag + secret leak|MEDIUM|PROVEN|

## False-positive guards

- `ebridge-contracts` has **no** `appsettings.json`, no `Serilog`, no `123456` — search negative is expected, not a pass. Note it explicitly.
- `192.168.67.*` specific request: report negative with actual `192.168.*` found (docs only).
- `ChainNodeApis http://` not present in this codebase — the HTTP finding is `Kestrel http://*:8000/`.
- `StringEncryption / MySQL Pwd 123456 / RabbitMQ / Swagger secret` — none in either repo; report as not found, don't invent.

## Reporting template

For each positive, emit: `VULNERABILITY: [Deploy-Ops / CORS / TLS ...] ENTRY: [pre-auth via HTTP API] CHAIN: [appsettings.json:6 * → Startup.cs:53 WithOrigins → any origin fetch /api] IMPACT: [CSRF / fund params via Admin EOA / RCE via Redis] EVIDENCE: [file:line] CONFIDENCE: [PROVEN] MITIGATION: [set CorsOrigins to allowlist / Kestrel Https + cert / ContractDeploymentAuthorityRequired=true / multisig Admin]`
