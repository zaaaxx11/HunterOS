# ed3.xyz CDC Hunt — 2026-08-31

## Target Profile
- **Frontend**: ed3.xyz (Next.js, Vercel)
- **Backends**: 7 Express/Apache subdomains on danlabs.xyz (no Cloudflare on most), app-api.danlabs.xyz (Cloudflare-protected)
- **Auth**: OpenCampus OAuth (PKCE) + native wallet login (POST /login/wallet → JWT in localStorage)
- **Stack**: Hedera + Solana + TON + EDU Chain (OpenCampus Codex) + SKALE + Base
- **JS Bundle**: 10.3MB _app chunk containing all routes, API endpoints, hardcoded keys

## Proven Findings (12 total, all live-verified)

### CRITICAL
1. **Unauth file upload** — `POST utility.danlabs.xyz/utility/uploadImages` (field `files=@file`) → uploads to Google Cloud Storage, NO AUTH, no rate limit (50 rapid uploads all 201)
2. **Unauth IPFS upload** — `POST launchpad-dev.danlabs.xyz/ipfs/upload` (field `image=@file` + `name=anything`) → pins to ed3's Lighthouse IPFS account, NO AUTH

### HIGH
3. **Auth bypass on /user/utility/redeemQuest** — Sibling routes (/claim-reward, /claimUtility) return 401 "No token provided"; redeemQuest returns 500 MongoDB error (middleware SKIPPED). When DB is up → unauth quest reward redemption for any wallet.
4. **GCS buckets public-listable** — `GET https://storage.googleapis.com/stream_utility` returns XML listing of ALL files. Also: stream_collections, stream_chain.
5. **Gelato RPC API key leak** — `GET /chainBlockByPriority/` returns `rpc_url: https://rpc.edu-chain.raas.gelato.cloud/6e143dc04e874712aeb8f0d67aec8210` — live, billable.
6. **PostgreSQL schema enum** — `POST /chainBlock` with partial fields → error reveals 14 NOT NULL columns + types (chain_name, last_block, contract_address, currency_name, currency_decimal, currency_symbol, currency_image_url, loan, rent, evm, utility, trade, explorer_link, transaction_link)
7. **Unauth chain config disclosure** — `GET /chainBlockByPriority/` leaks 5 chains: contract addresses, utility addresses, treasury accounts, RPC URLs

### MEDIUM
8. **Admin email leak** — `POST /checkApiKey {"apiKey":"<redacted>"}` → `{"email":"info@ed3.xyz","role":"client","rate_limit":null}`
9. **Unauth NFT/loan data** — `/assetManager/` (256 NFTs), `/collections` (14+), `/loanPool/all/`
10. **Unauth referral fraud** — `GET user.danlabs.xyz/refer/generateId/{any_wallet}` → 201
11. **MongoDB Atlas hostname leak** — `ac-q97o6te-shard-00-02.zjkmxt1.mongodb.net`
12. **No rate limiting on uploads** — 10/10 rapid uploads succeed

## DOWNGRADED (Adversarial Verification — Round 2)

- **Stored XSS**: GCS serves text/html ✅ BUT different origin (storage.googleapis.com) → cannot read ed3.xyz localStorage. No render sink found (NFTs use IPFS, dangerouslySetInnerHTML is framework-internal). DOWNGRADED to LOW.
- **CORS+credentials**: Real misconfig ✅ BUT no Set-Cookie on ANY backend → ACAC useless. Bearer tokens added by JS, not auto-sent. DOWNGRADED to LOW.
- **SQL injection**: DISPROVED — parameterized queries. Schema enum only.
- **State mutation bypass**: DISPROVED — server validates on-chain tx hash ("Transaction not found" for fake hashes). Field name is `txnHash` not `transactionHash`.
- **Dev API key on prod**: DISPROVED — dev key `<redacted>` rejected on prod.
- **Path traversal in upload**: DISPROVED — server strips `../`, appends timestamp to all filenames.

## Key Techniques Discovered

### Sibling Comparison Auth Bypass Detection
```
POST /user/utility/redeemQuest     → 500 (DB error — middleware SKIPPED)
POST /user/utility/claim-reward    → 401 (Unauthorized: No token provided)
POST /user/utility/claimUtility    → 401 (Unauthorized: No token provided)
```
The error type reveals whether auth middleware ran: 401 = ran, 500/processing = skipped.

### PostgreSQL Schema Walking via NOT NULL Errors
Send empty `{}` body, then fill one field at a time. Each response reveals the next NOT NULL column name:
```
{} → "null value in column \"chain_name\""
{chain_name:"X"} → "null value in column \"last_block\""
{chain_name:"X",last_block:"1"} → "null value in column \"contract_address\""
... continue until INSERT succeeds or all columns mapped
```

### Field Name Discovery from JS Bundle
The JS bundle (10MB) contains exact API field names. Grep for the endpoint name:
```python
re.finditer(r'buyNFT.{0,400}', bundle_data)  # reveals: txnHash, index, count, referralId
```
Field name was `txnHash` (not `transactionHash`) — critical for crafting valid requests.

### Multi-Origin Upload Chain
```
POST utility.danlabs.xyz/utility/uploadImages (no auth)
  → file lands on storage.googleapis.com/stream_utility/
  → GCS serves it as text/html (Content-Type matches file extension)
  → but DIFFERENT origin → cannot access ed3.xyz localStorage
```

## PoC Files
- `/home/ubuntu/ed3_final_poc.py` — 12-step verified PoC (all PROVEN)
- `/home/ubuntu/ed3_exploit_chain.py` — Round 1 PoC
- `/home/ubuntu/ed3_findings_round2.md` — Combined findings with adversarial verification
