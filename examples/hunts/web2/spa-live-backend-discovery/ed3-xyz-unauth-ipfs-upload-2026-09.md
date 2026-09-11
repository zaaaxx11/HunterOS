# ed3.xyz — Unauth IPFS File Upload Verification (2026-09)

## How the upload endpoint was found & proven
The SPA bundle ships the upload route as a constant:
`UPLOAD_IMAGES:"/utility/uploadImages"`, `launchpadBaseURL` config, and an IPFS uploader
that `POST`s `${launchpadBaseURL}/ipfs/upload` with multipart fields, plus
`IC.post("/ipfs/upload", formData)`.

## The field-name trap (MulterError "Unexpected field")
Raw file-field names are NOT in the URL constants — they are in the FormData build. Extract
every `.append(...)` whose argument names a field, then use those exact names in the multipart.
```bash
grep -oE '\.append\([^)]{2,80}\)' app.js
# .append("name", eo) .append("tokenAddress", eT) .append("tokenId", e_)
# .append("image", es, {filename:..,contentType:..})   <-- the actual FILE field is "image", not "file"
# .append("metadata", JSON.stringify(...)) .append("teamImages", en.image)  <-- utility/GCS path
```
Trying field named `file` → 500 `MulterError: Unexpected field at wrappedFileFilter (/root/launchpad/server/node_modules/multer/index.js:40:19)`.
Swap to `name`+`image` (+ optional `tokenAddress`/`tokenId`) → endpoint accepts.

## Working PoC (no auth, no valid api-key needed)
```python
# multipart with fields {"name": str} and files {"image": (fname, data)}
POST https://launchpad.danlabs.xyz/ipfs/upload
→ 200 {"success":true,"ipfsUrl":"https://gateway.lighthouse.storage/ipfs/bafkrei..."}
# arbitrary content accepted: uploaded test.html, test.html with unique marker, malicious.js
# all returned 200. Field `image` accepts any content-type, filename, extension.
```
- uploadImages→GCS (utility host) returned 500 while MongoDB down — host/route exists,
  schema error strings leak the DB layer; cannot confirm file landing while DB is down.

## Gateways & honesty on readback
- `lighthouse`/`ipfs.io`/`cloudflare-ipfs.com` gateways returned 403 "Directory access denied" /
  "blocked" — IPFS gateway rate-limit/blocklisting can hide content even though the bare
  upload was 200 and the metadata URL was returned. Do NOT claim stored-XSS from the upload
  alone; access-readback is a SEPARATE condition (in-origin serve + `text/html` render sink).
- **Verdict: unauth arbitrary-file upload PROVEN (fixed size content, permanent IPFS); stored-XSS
  on the origin = NOT confirmed (different origin, gateway blocks, no render sink found).**

## Report classification (user asked "laporan mu ini fake? — verify first-hand")
- Re-verify subagent claims yourself before reporting: only GCS-list, chainBlockByPriority config,
  Postgres schema enum, and this IPFS upload replicated when I ran the curl/PoC directly.
- `POST /checkApiKey` (claimed "admin email info@ed3.xyz") → `Cannot POST /checkApiKey` on the
  host I probed — did NOT replicate; mark claim as unverified-on-my-host rather than confirmed.

## Impact
- Storage/CDN abuse + permanent IPFS hosting of arbitrary files, no auth no rate-limit.
- Multer error stack leaks server path (`/root/launchpad/server/node_modules/multer/`).