# aelfscan.io / tDVV sniff — 2026-08-15

## Target
`https://aelfscan.io/tDVV` and `https://aelfscan.io/AELF` (aelf Explorer). Goal: find Bridge contract address on tDVV side chain.

## What was tried (URLs + result)

| URL | Status | Body signal |
|-----|--------|-------------|
| `GET /tDVV` (Mozilla UA) | 200 555k | `__NEXT_DATA__=0`, `_next/data=0` — App Router RSC |
| `GET /AELF` | 200 | same shape |
| `GET /_next/data/<buildId>/tDVV.json` (id `765LcKFhazqx70vKx8g_p`) | 200 | `<!DOCTYPE html>` — fallback, not JSON |
| `GET /_next/data/<id>/AELF.json`, `/index.json` | 200 | same HTML |
| `GET /_next/static/chunks/*.js` via `urllib` | 403 | WAF/UA gate |
| `GET /_next/static/chunks/*.js` via `curl -A "Mozilla/5.0"` | 200 | 29 chunks enumerable from HTML `src="…"` |
| `GET /api/app/address/contracts?chainId=tDVV&pageSize=10&pageNum=1` | 200 JSON | `total:141` but `pageNum=2` returns identical first page |
| `GET /api/app/address/contracts?chainId=tDVV&SkipCount=0&MaxResultCount=50` | 200 JSON | correct pagination — 50+50+41 |
| `GET /api/app/address/contracts?chainId=AELF&SkipCount=0&MaxResultCount=50` | 200 JSON | `total:51` |
| `GET /api/app/address/contract/history?chainId=tDVV&address=…` | 200 | deploy/update history per contract |
| `GET /api/app/blockchain/transactions?chainId=tDVV&pageSize=20&pageNum=1` | 200 | `total:736M`, method `UpdateTinyBlockInformation` etc. |
| `GET /api/app/blockchain/search?chainId=tDVV&keyword=Bridge` | 200 | empty (search not indexed for contracts) |
| `GET /api/blockChain/chainStatus?chainId=tDVV` | — | not found on frontend `/api/app/*` path |

## BuildId extraction
RSC flight payload embeds JSON with double-escaped quotes. Reliable extraction:
```python
import re, codecs
t = pathlib.Path('/tmp/aelfscan_tDVV.html').read_text()
# after unicode_escape decode, buildId is plain JSON
decoded = codecs.decode(t.encode().decode('unicode_escape') if False else t, 'unicode_escape')  # simpler: t.encode().decode('unicode_escape')
m = re.search(r'"buildId"\s*:\s*"([^"]+)"', decoded)
buildId = m.group(1)  # 765LcKFhazqx70vKx8g_p
```
Validate: `curl -sL -A "Mozilla/5.0" "https://aelfscan.io/_next/data/$buildId/tDVV.json" | head -c 200` → `<!DOCTYPE` confirms App Router.

## Chunk bulk fetch (UA-gated)
```bash
srcs=$(grep -oE 'src="(/_next/static/chunks/[^"]+)"' /tmp/aelfscan_tDVV.html | cut -d'"' -f2)
for s in $srcs; do curl -sL -A "Mozilla/5.0" "https://aelfscan.io$s" -o "/tmp/aelfscan_chunk_${s##*/}"; done
```
Key hit chunk: `9118-0e78938e50700981.js` (≈48k) contains
```js
let r="/api", c="".concat(a.env.NEXT_PUBLIC_API_URL,"/api")
s={getGlobalConfig: c+"/items/globalConfig?fields…"}
Object.entries({block:{getBlockList:r+"/app/blockchain/blocks",…},
 address:{getContractList:r+"/app/address/contracts",
          getServerContractList:c+"/app/address/contracts",…}})
```
Other chunks with `/api/` noise are docs links or portkey auth — filter by `aelfscan.io/api` or `"/app/address/contracts"` literal.

## Correct XHR endpoints (from chunk map)
- Client (Next.js proxy): `r="/api"` → `GET /api/app/address/contracts`
- Server (direct): `c="https://aelfscan.io/api"` → `GET https://aelfscan.io/api/app/address/contracts`
- Headers that matter: `-A "Mozilla/5.0"` mandatory; `-H "Accept: application/json"` helps for non-browser fetch; `Referer: https://aelfscan.io/tDVV` for CORS-sensitive calls.
- Pagination: ABP style `SkipCount`/`MaxResultCount`, NOT `pageNum`/`pageSize`. Loop:
```bash
skip=0; step=50
while true; do
  curl -s -A "Mozilla/5.0" "https://aelfscan.io/api/app/address/contracts?chainId=tDVV&SkipCount=$skip&MaxResultCount=$step" -o /tmp/cc.json
  len=$(python3 -c "import json,pathlib; print(len(json.loads(pathlib.Path('/tmp/cc.json').read_text())['data']['list']))")
  [ "$len" -lt "$step" ] && break
  skip=$((skip+step))
done
```

## Env leaked in RSC
Decoded snippet around `BASE_URL`:
```
NEXT_PUBLIC_API_URL=https://aelfscan.io
NEXT_PUBLIC_CMS_URL=http://aelf-explorer-cms-svc:8055  (internal, not public)
rpcUrlAELF=https://aelf-public-node.aelf.io
rpcUrltDVV=https://tdvv-public-node.aelf.io
rpcUrltDVW=https://tdvw-public-node.aelf.io
GRAPHQL_SERVER=https://dapp-aa-portkey.portkey.finance/aefinder-v2/api/app/graphql/portkey
BASE_URL=https://aa-portkey.portkey.finance
```

## Contract harvest result (tDVV 141 vs AELF 51)
tDVV named contracts (29) filtered for bridge-like:
- `x4CTSuM8typUbpdfxRZDTqYVa42RdxrwwPkXX7WUJHeRmzE6k` — `ETransfer.Contracts.TokenPool` (26,410 txns, v2.11.0.0) — live TokenPool
- `8XmxcaQGCRzrfP4ij3C6SR4nDbHkYBnKJxcAoWPtFofvtmahL` — `DeprecatedBridge` (910 txns, balance 16,865, v1.3.0.0)
- `2snHc8AMh9QMbCAa7XXmdZZVM5EBZUUPDdLjemwUJkBnL6k8z9` — `AElf.ContractNames.CrossChain` (7,673,231 txns, SYSTEM)
- `ZaLtsjGhzZ2KP9UEm4ABN3XgMT8DgV8q6BQJgpKHuyrfwit4c` — `EBridge.Contracts.StringAggregator`
- `2LhQEonaz...`, `2nkBV...`, `2j6mj...`, `299H2...` — `DeprecatedEBridge{Report,MerkleTree,Oracle,Regiment}`
- `BGhrBNTPcLccaxPv6hHJrn4CHHzeMovTsrkhFse5o2nwfvQyG` — `AetherLink.Contracts.Oracle`

**Negative result:** no active `EBridge.Contracts.Bridge` on tDVV. On AELF that contract exists at `2dKF3svqDXrYtA5mYwKfADiHajo37mLZHPHVVuGbEDoD9jSgE8` (41,014 txns, v1.8.0.0) alongside `2w13Dqbuui...` TokenPool, `owZisa...` Report, etc. — confirms Bridge lives on AELF main chain, tDVV only has deprecated instance + TokenPool + CrossChain system contract.

Saved artifacts: `/tmp/tDVV_all_141.json` (full list), `/tmp/aelfscan_chunk_*.js`.

## Pitfall to carry forward
1. Don't trust `pageNum`; always probe `SkipCount` first on ABP-style APIs (`aelfscan` is ABP backend).
2. Don't filter addresses by `2*` prefix — all aelf addresses are base58 `2*`/`x*`/`...`; use `contractName` keyword (`bridge|ebridge|tokenpool|crosschain|oracle`).
3. 112/141 rows have `contractName: null` — a null name doesn't mean not-a-bridge; check history/codeHash or on-chain `GetContractInfo` if needed, but keyword on named set was sufficient here.
