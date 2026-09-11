# eBridgeServer Web2 Weakness Audit — ABP (AElf CrossChainServer) 2026-08-15

Source: `/tmp/ebridge2/ebridge-server-master` (783K, 16 src: HttpApi, HttpApi.Host, AuthServer, ContractEventHandler, EntityHandler, Worker, Domain, Application, etc.) + `ebridge-contracts.aelf-dev/protobuf/bridge_contract.proto` (off-chain server, no on-chain contract in repo).

## 1) Anonymous GETs — Every HttpApi controller lacks [Authorize]

ABP ConventionalControllers `HttpApi.Host/CrossChainServerHttpApiHostModule.cs:99 Create(typeof(CrossChainServerApplicationModule).Assembly)` + `Application` services `[RemoteService(IsEnabled=false)]` → only explicit `HttpApi/Controllers/*.cs` exposed. Permissions empty (`Permissions/CrossChainServerPermissions.cs` GroupName only, `PermissionDefinitionProvider` no-op).

| Controller:Line | Route | Method |
|---|---|---|
| `CrossChainTransferController.cs:27` | `GET /api/app/cross-chain-transfers` | `GetListAsync(GetCrossChainTransfersInput)` — Term/Terms filter on FromChainId/ToChainId/FromAddress/ToAddress/Addresses/Status/Type → `CrossChainTransferAppService.cs:69-183` NEST `GetListAsync(Filter, limit:MaxResultCount, skip:SkipCount, sort TransferTime DESC)` + `CountAsync` |
| `:33` | `GET .../status` | `GetStatusAsync(GetCrossChainTransferStatusInput Ids List<Guid>)` → `Ids` filter |
| `ChainController.cs:24` | `GET /api/app/chains` | `GetChainsAsync(GetChainsInput Type?)` |
| `CrossChainLimitController.cs:24/31` | `GET /api/app/limiter/dailyLimits|rateLimits` | `GetCrossChainDaily/RateLimitsAsync` — reveals bucket caps |
| `CrossChainIndexingController.cs:29` | `GET /api/app/cross-chain-indexing/progress` | `CalculateProgressAsync` |
| `TokenController.cs:22` | `GET /api/app/tokens` | `GetAsync(GetTokenInput ChainId/Symbol/Address)` — if not found inserts via `BlockchainAppService.GetTokenInfoAsync` (external node call) |
| `TokenAccessController.cs:30,38,126,133,140,147` | `GET /api/ebridge/application/token/config, token-white-list, pool-overview?addresses=, pool-list, pool-detail, token/price` | 6 anon vs 10 `[Authorize]` endpoints (`:45 tokens, :53 token-detail, :61 commit-basic-info, :69 user-token-access-info, :77 check-chain-access-status, :85 add-chain, :93 prepare-binding-issue, :101 issue-binding, :109 list, :118 detail, :154 admin trigger-order-status-change`) |

Verdict: by-design public explorer → `info` privacy/scrape, not fund theft. `pool-overview?addresses=a,b` same anon enumeration as transfer.

## 2) CORS — wildcard subdomain + AllowCredentials

`HttpApi.Host/CrossChainServerHttpApiHostModule.cs:181-199` + `AuthServer/AElfCrossChainServerAuthServerModule.cs:158-173`:
```csharp
WithOrigins(CorsOrigins.Split(",")).SetIsOriginAllowedToAllowWildcardSubdomains().AllowAnyHeader().AllowAnyMethod().AllowCredentials()
```
Config: `HttpApi.Host/appsettings.json:3 "App:CorsOrigins":"https://*.CrossChainServer.com,http://localhost:4200"` / `AuthServer/appsettings.json:5 "...,https://localhost:44336,44389"`. `*.CrossChainServer.com` + credentials → subdomain takeover required. Not `*`.

## 3) AppSettings Defaults — secrets in repo

| File:Line | Value |
|---|---|
| `HttpApi.Host/appsettings.json:6` | `Server=127.0.0.1;Uid=root;Pwd=123456;` |
| `AuthServer/appsettings.json:19` | `Pwd=;` (empty) |
| `ContractEventHandler/appsettings.json:3` / `EntityHandler/appsettings.json:3` | `Pwd=123456` / `DbMigrator/appsettings.json:3 Pwd=12345678` |
| `*:Redis:Configuration 127.0.0.1` (Host:9, Auth:34, Handler:6) | unauth Redis |
| `HttpApi.Host:27-34 RabbitMQ admin/123456` / `Handler:11-18 same` / `AuthServer guest/guest` / `EntityHandler guest/guest` | weak AMQP |
| `HttpApi.Host:25 Or7FKveUF7w9PuVs` / `AuthServer:37 DVb2B8QjyeArjCTY` / `Handler:9 RDjeywn1asnmJgNm` | `StringEncryption:DefaultPassPhrase` — Abp DataProtection |
| `HttpApi.Host:15 SwaggerClientSecret 1q2w3e*` + `DbMigrator:181,186,191,196 4× ClientSecret 1q2w3e*` | `OpenIddict:Applications` placeholder; Swagger is `Public` type (`OpenIddictDataSeedContributor.cs:116`) — not confidential |
| `HttpApi.Host:58-60 ChainApi 192.168.67.47:8000` + `GraphQLClients http://192.168.67.84:8083` | internal IP disclosure |
| `Artifacts appsettings.secrets.json {}` + `DbMigrator/HttpApi.Host/tempkey.jwk|rsa` committed | prod should use Apollo (`ApolloConfigurationExtension.cs`) — defaults only if misconfigured |

Auth: `HttpApiHostModule.cs:43 DisableTransportSecurityRequirement()` negates `RequireHttpsMetadata true`. `TimeRange 1440` (24h) + `SignatureGrantHandler.cs:89 time < UtcNow ±1440m` → 24h replay window.

## 4) Missing Rate Limits — no AspNetCoreRateLimit

`grep RateLimit/Throttle/IpRate` only business `CrossChainRateLimit`. Vectors: `GetListAsync limit: input.MaxResultCount` unbounded (ABP `PagedAndSortedResultRequestDto` no cap) vs `LiquidityAppService.cs:12 MaxMaxResultCount=1000`; `Addresses.Split(',')` unbounded Terms explosion; `TokenController GetAsync → GetTokenInfoAsync` external call per anon request; `pool-overview?addresses=` same. Fixed PoC: `?MaxResultCount=2147483647` → ES large payload DoS.

## 5) IDOR — address enumeration without CurrentUser

`CrossChainTransferAppService:80-120` `FromAddress/ToAddress/Addresses` Bool Should/Must with ETH lowercase + TON raw conversion, no `CurrentUser` check → bulk victim history. `GetStatusAsync Ids` batch, `LiquidityAppService GetPoolOverview/PoolList/PoolDetail(Address)` same. Not strict IDOR — public explorer `info`.

## 6) GraphQL/ES Injection — SAFE

NEST typed DSL `q.Term(i=>i.Field(f=>f.X).Value(input.X))` parameterized, not concat. `IndexerAppService.cs:160 Query=static + Variables=new{chainId,txId}` via `GraphQL.Client.Serializer.Newtonsoft` escaped. `Sorting` input ignored (hardcoded `sortExp: o=>TransferTime`). No injection; max risk DoS.

## 7) Swagger / Info Disclosure

`HttpApiHostModule.cs:229 UseSwagger(); 230 UseAbpSwaggerUI("/swagger/v1/swagger.json")` with `227 // if (env.IsDevelopment())` commented → enabled prod anon. `HomeController.cs:10 Redirect("~/swagger")` → `/` discovery. Verdict `info`.

## 8) bridge_contract.proto validation

`CreateReceiptInput Symbol/TargetChainId/Amount:long / TargetChainType`, `SwapTokenInput SwapId/ReceiptId/OriginAmount:string/receiver` — no `(validate.rules)`; `Amount int64` negative unchecked at proto level (must `Assert(Amount>0)` + `TryParse+SafeMath.Add` on-chain).

## Repro

```bash
grep -rn "Authorize\|HttpGet\|Route" src/AElf.CrossChainServer.HttpApi/Controllers/*.cs
grep -rn "WithOrigins\|SetIsOriginAllowed\|AllowAny" src --include="*.cs"
cat src/AElf.CrossChainServer.HttpApi.Host/appsettings.json
grep -rn "MaxResultCount\|GetListAsync" src/AElf.CrossChainServer.Application/CrossChain/CrossChainTransferAppService.cs
# CORS live: curl -H "Origin: https://evil.CrossChainServer.com" https://target -I | grep -i access-control
# Rate limit: curl "https://target/api/app/cross-chain-transfers?MaxResultCount=100000&Addresses=addr1,addr2,..."
# GraphQL check: verify GraphQLRequest Variables usage in IndexerAppService.cs
```

Fix order: gate Swagger with env, add rate limiting + MaxResultCount ≤100 + Addresses max 20, externalize secrets, tighten CORS exact origins, optional auth on My queries.
