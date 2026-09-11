# AElf Bridge Address Sniff — 4-Agent Quartet (2026-08-15 tDVV)

## Context
After exhaustive weakness sweep (0 PROVEN pre-auth fund theft) and info leak trio (Portkey 10k, Awaken 498k, ebridge cross-chain-transfers anon), user pivoted to **privileged pivot**: find Bridge Admin address on tDVV chain. Command: `sniff spawn 4 agent untuk saling audit`.

## Real Finding: Bridge Live on tDVV
- **BRIDGE_CONTRACT** = `GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd`
- **TOKEN_POOL** = `ttm4YsRRTV2zWx7hDpBV5gfLfWhqtde8N4XYQtZyoTyKi3tq9`
- Source: `eBridgeCrosschain/ebridge-web:src/constants/platform/tDVV.ts:10` (Sniffer-C)
- Verified live via `tdvv-public-node.aelf.io`:
  - `GET /api/blockChain/contractFileDescriptorSet?chainId=tDVV&address=GZs6...` → 37086 bytes base64 FileDescriptorSet (proof contract exists)
  - `GET /api/contract/contractViewMethodList?address=GZs6...` → 32 methods including `GetContractAdmin`, `GetContractController`, `GetTokenPoolContract`, `GetSwapInfo` etc.
  - TOKEN_POOL verify: `GET /api/contract/contractViewMethodList?address=ttm4...` → `["GetTokenPoolInfo","GetLiquidity","GetRemovableLiquidity","GetAdmin","GetBridgeContract"]`

## 4-Agent Design

### A — aelfscan XHR Sniffer
- `curl -A Mozilla/5.0 https://aelfscan.io/tDVV` → 555k HTML, App Router RSC (not pages), `__NEXT_DATA__=0`
- `buildId: 765LcKFhazqx70vKx8g_p` extracted from RSC payload (unicode_escape decode)
- `_next/data/<buildId>/tDVV.json` → 200 but returns HTML (RSC page, not JSON)
- Chunks `/_next/static/chunks/9118-0e78938e50700981.js` contain API map `"/api/app/blockchain/blocks"` etc.
- **Pitfall**: chunks return 403 without `-A Mozilla/5.0`; `_next/data` returns HTML not JSON in App Router
- Found NO Bridge on tDVV via aelfscan (only DeprecatedBridge) — false negative because address lives in ebridge-web not aelfscan index

### B — RPC Direct Sniffer
- Nodes: `aelf-public-node.aelf.io` (AELF height 3504xxxx), `tdvv-public-node.aelf.io` (tDVV 333640xxx) live
- `GET /swagger/v1/swagger.json` → 27 paths: `/api/blockChain/{block,blockByHeight,chainStatus,contractFileDescriptorSet,executeTransaction,executeRawTransaction}` + `/api/contract/{contractViewMethodList,systemContractAddressByName}`
- Tested `GET /api/blockChain/systemContractAddressByName?chainId=tDVV&systemContractName=Bridge` → 500 (Bridge is USER contract, not system)
- `GET /api/blockChain/blockByHeight?includeTransactions=false` only returns txHash strings, requires per-tx fetch
- `GET /api/blockChain/transactionResult?transactionId=` → Status MINED with Logs[Address,Name]
- Negative: tDVV has only 10 genesis system contracts + 11 DeploySystemSmartContract txs, no Bridge in genesis — confirms user-contract nature

### C — GitHub Config Sniffer
- `GET /repos/eBridgeCrosschain/ebridge-contracts.aelf/contents?ref=dev` → scripts/, protobuf/, contract/, src/AElf.Boilerplate.* (dynamic deployment, no hardcoded address)
- `GET /orgs/eBridgeCrosschain/repos` → 14 repos enumerated
- `GET /search/code` → 401 Requires authentication (anon search now auth-required, workaround via `GET /git/trees/<branch>?recursive=1` + raw fetches)
- Hit: `eBridgeCrosschain/ebridge-web:src/constants/platform/tDVV.ts:10` BRIDGE_CONTRACT + tDVV.ts TOKEN_CONTRACT=7RzVG..., CROSS_CHAIN=2snH... + `ebridge-contracts.aelf` CHAIN_INFO rpcUrl
- **Address prefix trap**: BRIDGE uses `G` prefix (`GZs6...`), TOKEN_POOL uses `t` (`ttm4...`), not `2` — grep `2[0-9A-Za-z]{40,}` misses it

### D — Verifier (Cross-Audit)
- Proved Bridge = USER contract via `AElf.Sdk.CSharp/SmartContractConstants.cs` allowlist 14 names only (Token, Consensus, Parliament, etc.) — 0 hits for Bridge/EBridge
- Live probe: `systemContractAddressByName(Token)=200` + address, `Bridge/EBridge/Oracle=500` always
- Correct admin retrieval: `bridge_contract.proto:28 rpc GetContractAdmin(Empty) returns (Address) is_view=true` → `BridgeContract_Views.cs:15 return State.Admin.Value`
- Method: `GET contractViewMethodList?address=<BRIDGE>` (anon, confirms ABI) then `POST rawTransaction {From,To,RefBlockNumber,RefBlockHash,MethodName:"GetContractAdmin",Params:"{}"} → executeRawTransaction {RawTransaction, Signature}` → `{"value":"<admin base58>"}`
- **Auth gate**: public nodes return 403 `Invalid params` for anon `executeRawTransaction` — not encoding bug but auth wall. Need local node `192.168.67.*:8000` or aelf SDK signing (`TransactionAppService.cs:117 VerifySignature + CallReadOnlyAsync`)
- `GET /api/blockChain/block*` can enumerate CreateReceipt txs without knowing address (alternative path via Bloom/Logs)

## Verification Template (once address known)
```bash
# 1. Confirm ABI exists (anon)
curl -sk "https://tdvv-public-node.aelf.io/api/contract/contractViewMethodList?address=GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd" | grep GetContractAdmin
# 2. Confirm descriptor (anon)
curl -sk "https://tdvv-public-node.aelf.io/api/blockChain/contractFileDescriptorSet?chainId=tDVV&address=GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd" | wc -c
# 3. Call view (requires signing - local SDK)
# Use aelf Python/JS SDK: create Transaction(From=any, To=GZs6..., Method=GetContractAdmin, Params=Empty) → sign → POST /api/blockChain/executeRawTransaction
# aelfscan alternative (if endpoint exists): GET /api/app/blockchain/blocks?chainId=tDVV&pageSize=5&page=1 includes producerAddress but not per-contract tx filter (404 for /api/app/transaction/list?address=)
```

## Lessons
- User contracted Bridge is NOT SystemContract — systemContractAddressByName always fails for user contracts
- AElf addresses not always `2` prefix — include `G`, `t`, `ELF_` variants
- Next.js App Router: buildId in RSC payload, _next/data returns HTML, chunks need Mozilla UA
- Public RPC auth-gated for view calls — confirm via contractViewMethodList first, then SDK
