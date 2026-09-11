# aelf + eBridge Hunt — 2026-08-15 Case Study

## Targets
- aelf main chain (AELF) + sidechain tDVV (`tdvv-public-node.aelf.io`, height ~333647k)
- eBridge: `eBridgeCrosschain/ebridge-contracts.aelf` (Bridge `GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd`, Pool `ttm4YsRRTV2zWx7hDpBV5gfLfWhqtde8N4XYQtZyoTyKi3tq9`), `ebridge-server` (16 proj, net8.0), `ebridge-web` (config leak)
- Portkey `aa-portkey.portkey.finance`, Awaken `app.awaken.finance` + `cms-v2.awaken.finance` (Directus), aelfscan/aelf.com

## Live Verification Performed
- `contractViewMethodList` on Bridge → 32 methods (GetContractAdmin/Controller/PauseController etc.), `contractFileDescriptorSet` 37086 bytes
- Signed view via rawTransaction: ephemeral key → `sha256(sha256(pub))` → base58check → `POST /rawTransaction` → `sha256(raw)` → `coincurve sign_recoverable` → `POST /executeRawTransaction` → Admin `2ZnuXvCiv4M8NC3HhcxyKxKzUmXh9H8q8pc3eYuLP9BcACdWvn` (same for Pool), Controller `2EAiv...`, Pause `xyye...`
- Anon dumps: Portkey `accountrecoverindex` 10000 + `accountregisterindex` 10000 (caHash/caAddress/deviceInfo/guardian signatures), Awaken `trade-records` 498369, CMS graphql draft+whitelist, ebridge `cross-chain-transfers` ReceiptId mass

## Contract Verdict (1.906 lines)
- Blocked: replay (`Already claimed` Helpers:110 + `ReceiptHashRecordStatus` Ramp:85), overflow (`decimal.ToInt64` throw + `checked Add`), unauthorized CreateSwap (`Sender==Admin` TokenSwap:26), spoof receiver (`Sender==RampContract` Ramp:41)
- Open conditional: TokenPool `Initialize` author check commented `TokenPoolContract.cs:19` (// Assert Sender==author) → drain on fresh deploy, blocked on live by `!IsInitialized`; limit not persisted (`ConsumeReceiptAmount` Helpers:190 no `State.ReceiptDailyLimit=`) → unlimited if Ramp compromised
- IsValidAmount `Helpers:98` allows 19-30 digit → only gas grief (revert), not wrap

## Chain Assessment
- No pre-auth fund theft on live. Path is `info leak → spear-phish Admin (maintainer-1@example.invalid, commit author) → `ChangeSwapRatio/SetCrossChainConfig` → mint via Ramp`. Classified HIGH privacy/GDPR, not pre-auth RCE.
- Reports delivered per platform: `report_eBridge.md`, `report_Portkey.md`, `report_Awaken.md`, `report_aelf.md` + SDK POC commands.

## Repro
```bash
curl -s "https://tdvv-public-node.aelf.io/api/contract/contractViewMethodList?address=GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd"
curl -s "https://aa-portkey.portkey.finance/api/app/search/accountrecoverindex?SkipCount=0&MaxResultCount=1"
# SDK craft: pip install -q coincurve base58 ; use steps in SKILL.md AElf View Call
```

## Pitfalls
- `systemContractAddressByName` always 500 for Bridge (user contract, not SystemContract 14 names)
- `GetCrossChainConfig` needs protobuf params, `Params:"{}"` → 403
- Next.js App Router `__NEXT_DATA__=0`, chunks need Mozilla UA or 403
- aelfscan per-address tx list 404, blockByHeight only generic
