# eBridge CHAINER — Blocked Web2→Contract Chain (2026-08-15)

## Question
`GET /api/app/cross-chain-transfers` anon leaks `ReceiptId/SwapId/ReceiverAddress` via `GetListAsync` → can it feed `SwapToken` replay? Map handoff: indexer leak → contract call. Check `CrossChainTransferAppService.TransferAsync` hidden but indexer may auto-receive.

## Verdict: CHAIN BLOCKED — 1 honest info-leak, 0 pre-auth theft/RCE

## Architecture
- **Web2 leak:** `AElf.CrossChainServer.HttpApi/Controllers/CrossChainTransferController.cs:18` — `[Route("api/app/cross-chain-transfers")]` with `[HttpGet] GetListAsync` + `[HttpGet("status")] GetStatusAsync`, **NO `[Authorize]`**. Host `CrossChainServerHttpApiHostModule.cs:222` has `UseAuthentication+UseAuthorization` but **NO `FallbackPolicy`**, `CrossChainServerPermissions` empty. All read controllers (`ChainController`, `CrossChainLimitController`, `CrossChainIndexingController`) same — design-intent anon.
- **Dto:** `CrossChainTransferIndexDto.cs:7` + `CrossChainTransferBase.cs` — leaks `ReceiptId, TransferTransactionId, ReceiveTransactionId, From/ToAddress, TransferAmount/ReceiveAmount, TransferToken/ReceiveToken, Status/Type/Progress` via `INESTRepository<CrossChainTransferIndex>` (Nest ES) with `MaxResultCount/SkipCount` pagination.
- **Hidden write:** `CrossChainTransferAppService.cs:23` — `[RemoteService(IsEnabled=false)]`. Host `ConfigureConventionalControllers()` creates conventional controllers for `CrossChainServerApplicationModule` but ABP skips `IsEnabled=false`. **No `POST /api/app/cross-chain-transfers/transfer` route** — `CrossChainTransferController` has no transfer endpoint. Workers that call it (`EvmNewReceiptSyncProvider`, `EvmTokenSwapSyncProvider`, `NewReceiptEventProcessor`, `TokenSwappedEventProcessor`, `CrossChainTransferIndexerSyncProvider:88/122`) are internal indexer→server trusted paths.
- **Contract:** `BridgeContract.g.cs:233,5049` — `SwapTokenInput{SwapId:Hash, ReceiptId:string, OriginAmount:string, ReceiverAddress:Address}`. Requires `SwapId`.

## 3 Gates That Block the Chain

### Gate 1 — Field-Mapping (decisive)
`grep SwapId` hits ONLY `BridgeContract.g.cs`; zero hits in `Domain/CrossChain/CrossChainTransferBase.cs`, `CrossChainTransferIndex`, `CrossChainTransferInput`, `CrossChainReceiveInput`, `AddCrossChainTransferIndexInput`. Leak → contract handoff **breaks**: web2 DTO has no `SwapId` to feed `SwapToken`. Attacker can derive via `GetSwapIdByToken(chainId,symbol)` using leaked `TransferToken.Symbol`, but that's extra on-chain RPC, not direct web2→contract.

### Gate 2 — Routing
`TransferAsync(CrossChainTransferInput{TransferTransactionId,ReceiptId})` has no controller route. ABP conventional routing disabled. Only internal sync providers call it, each re-validates via `GetPendingReceipt/Transaction` + `DeleteCrossChainTransferAsync` if `crossChainTransferInfo==null` (`CheckTransferTransactionConfirmedAsync:722`) and via merkle proof in `HomogeneousCrossChainTransferProvider.SendReceiveTransactionAsync:63` (`GetMerklePathAsync`+`CrossChainReceiveTokenAsync`).

### Gate 3 — On-chain binding
Even with `ReceiptId+SwapId`, contract enforces `Receipt{Owner,TargetAddress,Amount,TargetChainId}` binding + single-use dedup (`ReceiptHashMap`/`GetSwappedReceiptIdList`). Replaying leaked `ReceiptId` with attacker `ReceiverAddress` fails `TargetAddress` check; second swap fails dedup.

## What IS Proven
`anon GET /api/app/cross-chain-transfers?MaxResultCount=1000` → mass dump all receipts across chains → cross-chain de-anonymization + frontrun intel + TON raw→friendly correlation. **Stops at info-leak.**

## CHAINER Detection Kit (reusable)

```bash
# 1. Anon vs hidden
grep -rn "AllowAnonymous\|Authorize" src/HttpApi/Controllers --include="*.cs"
grep -rn "RemoteService.*IsEnabled" src --include="*.cs"
grep -n "ConfigureConventionalControllers\|UseAuthorization" src/HttpApi.Host/*Module.cs

# 2. Field parity
grep -rn "SwapId\|ReceiptId" src/Application.Contracts --include="*.cs" | grep -v BridgeContract.g
grep -rn "class CrossChainTransfer.*Input\|CrossChainTransferIndexDto" src --include="*.cs" -A 15

# 3. No route
grep -rn "TransferAsync\|ReceiveAsync" src/HttpApi --include="*.cs"
grep -rn "CrossChainTransferController" src --include="*.cs" -A 20

# 4. Internal callers vs client callers
grep -rn "crossChainTransferAppService\.TransferAsync\|ReceiveAsync" src --include="*.cs" | grep -v test
```

**Rule:** CHAINER must report `CHAIN BLOCKED` with gate+evidence when leak DTO field set ⊄ contract input field set, or when write method has `IsEnabled=false` with no route. Don't inflate to theft.

## Reporting Pattern
```
Entry: anon GET /api/app/cross-chain-transfers (no Authorize, no FallbackPolicy) → PagedDto<ReceiptId,ToAddress,Amount>
Step1: elastic dump via NEST (MaxResultCount/SkipCount)
Step2: BLOCKED at field-mapping — SwapId ∉ DTO, and at routing — TransferAsync IsEnabled=false no route
Gate evidence: file:line + grep counts
Impact: MEDIUM info-leak (mass cross-chain de-anon), NOT pre-auth theft/RCE
```

## Gotcha
`contract/AElf.Contracts.CrossChain` (1627 lines, `SideChainCreationRequest`) is native sidechain indexing, NOT eBridge. eBridge logic is in `ebridge-server/src/**/BridgeContract.g.cs` + `TokenPoolContract` + `EvmBridgeContractProvider`. Don't mislabel.
