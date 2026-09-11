# Berachain-specific + AElf/eBridge case-residue sections (cut from multi-target-cdc-audit SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/cdc/multi-target-cdc-audit/SKILL.md` during the
S2b-2 content pass. Case-specific target data, preserved not deleted. The eight
case refs that moved with this skill live in
`examples/hunts/cdc/multi-target-cdc-audit/references/`.

---

### Berachain-Specific Patterns
- WBERA vault: `0x6969696969696969696969696969696969696969`
- Honey/BEX selector: `0xe21fd0e9` (swap-like functions)
- Chain ID: `0x138de` (80094)
- Default insecure config: `polaris/eth/node/node.go:67-78` (`DefaultGethNodeConfig`)
- Public RPCs: `berachain-rpc.publicnode.com`, `rpc.berachain.com`, `berachain.drpc.org`

---

## AElf / eBridge Specific Patterns (proven 2026-08-15)

### Bridge Address Discovery on tDVV (when no explorer API)
`tdvv-public-node.aelf.io` and `aelfscan.io/api` do not expose user-contract lists. Do not waste time on `systemContractAddressByName` for Bridge (it is a user contract, always 500). Proven path:
```bash
# 1. Get from web config
curl -s https://raw.githubusercontent.com/eBridgeCrosschain/ebridge-web/master/src/constants/platform/tDVV.ts | grep BRIDGE_CONTRACT
# → GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd
curl -s https://raw.githubusercontent.com/eBridgeCrosschain/ebridge-web/master/src/constants/platform/tDVV.ts | grep TOKEN_POOL
# → ttm4YsRRTV2zWx7hDpBV5gfLfWhqtde8N4XYQtZyoTyKi3tq9
# 2. Verify live via view list (anon, no sign)
curl -s "https://tdvv-public-node.aelf.io/api/contract/contractViewMethodList?address=GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd"
# should contain GetContractAdmin, GetContractController, etc. (32 methods)
curl -s "https://tdvv-public-node.aelf.io/api/blockChain/contractFileDescriptorSet?chainId=tDVV&address=GZs6wyPDfz3vdEmgVd3FyrQfaWSXo9uRvc7Fbp5KSLKwMAANd" | wc -c
# → 37086 if contract exists
```

### AElf View Call via SDK Craft (no dotnet/protoc needed)
`ExecuteRawTransaction` requires `RawTransaction` (hex of protobuf Transaction) + `Signature` (65B secp256k1 recoverable). Craft with Python `coincurve + base58` mimicking `AElf.Types/Base58.cs` and `Transaction.cs:GetHash()`:

1. Ephemeral key: `priv = secrets.token_bytes(32)` → `pub = PrivateKey(priv).public_key.format(compressed=False)` (65B 0x04)
2. Address: `addr_bytes = sha256(sha256(pub)).digest()` → `addr_b58 = base58.b58encode_check(addr_bytes)` (AElf Base58Check = double-sha256, 4B checksum, same as Bitcoin)
3. Get ref block: `GET /api/blockChain/chainStatus` → `LongestChainHeight` + `LongestChainHash`
4. Create raw: `POST /api/blockChain/rawTransaction` body `{From: addr_b58, To: "GZs6...", RefBlockNumber, RefBlockHash, MethodName:"GetContractAdmin", Params:"{}"}` → `RawTransaction` hex
5. Sign: `h = sha256(bytes.fromhex(RawTransaction))` → `sig = pk.sign_recoverable(h, hasher=None)` (65B, last byte recid)
6. Execute: `POST /api/blockChain/executeRawTransaction` body `{RawTransaction: raw_hex, Signature: sig.hex()}` → returns `"2ZnuXv..."` JSON string. Works for view methods with `Empty` input (`Params:"{}"`). Non-Empty params (e.g. GetCrossChainConfig) need protobuf JSON, will 403 if `"{ }"` wrong.

Pip: `pip install -q coincurve base58` (protobuf 3.20.3 not needed for this path).

### Info Leak Pattern Across aelf Ecosystem (proven anon)
All `HttpApi` controllers in `ebridge-server` lack `[Authorize]` by default (ABP). Check:
```
GET /api/app/cross-chain-transfers?MaxResultCount=10   (CrossChainTransferController.cs:27)
GET /api/app/search/accountrecoverindex?SkipCount=0&MaxResultCount=100  (aa-portkey, 10000 records)
GET /api/app/trade-records?ChainId=tDVV  (awaken, 498369 trades)
POST https://cms-v2.awaken.finance/graphql { activityList { id status whitelist } }  (Directus, draft leak)
```
All `MaxResultCount/SkipCount` paginable without token. Do not claim fund theft from dump alone — bridge mint needs `Ramp.cs:41 Assert(Sender==RampContract)` + dedup. Classify as HIGH privacy/GDPR + spear-phish ammo.

### Disk Safety During Long Hunts (user hard requirement 2026-08-15)
Disk was 96% (20G). Never delete `/root/.hermes` (1.4G, holds subagent summaries + live logs). Safe cleanup:
```bash
du -sh /tmp/* | sort -rh | head -20
rm -rf /tmp/aioz_scan /tmp/aptos-core-mainnet /tmp/beacon-kit* /tmp/bk*  # keep /tmp/aelf2 /tmp/bridge_unzipped /tmp/ebridge.zip /tmp/aelf.zip
du -sh /root/* | sort -rh
rm -rf /root/berachain-chains /root/shopify-recon /root/node_modules  # keep /root/go /root/.hermes /root/audit
df -h /  # verify 85% after
```

### Output Style Enforcement (learned from corrections 2026-08-15)
- User wants `jelasin santai` warung analogy (pusat/dapur/kasir/brankas/kurir) + tables, lo/gue, emojis natural, short paragraphs. Fragmented reports → flagged `laporanmu acak adut`.
- When asked for report, use human tone: `Hei, aku menemukan sebuah bug di platform mu, bug nya ..., aku harap kau bisa meninjau nya. thanks.` No AI slop. Reduce em dashes `—`, use commas or periods.
- Always include POC (real curl) + truncated redacted samples. For multi-platform asks, produce **one file per platform** (`report_eBridge.md`, `report_Portkey.md`, `report_Awaken.md`, `report_aelf.md`), not one merged file.
- `sdk buat apa?` → answer concept first (SDK = formulir resmi + tanda tangan for ExecuteRawTransaction) before executing checks. Keep `menyamar` (Mozilla UA, single req, throttle 0.6-1.2s) for web2 hunts.
