# NestJS + Prisma GraphQL backend audit (pencilfinance.io case study, 2026-09)

Class: decentralized lending / RWA dApp backend exposing a **Prisma-generated GraphQL API**
(NestJS `@nestjs/graphql` + Prisma). Distinct from Apollo/handwritten GraphQL — the schema types
(average/max/min/count aggregates, `*WhereInput`/`*OrderByWithRelationInput`, compound
`*CompoundUniqueInput`) are Prisma's auto-generated shapes and are a reliable fingerprint.

## Stack fingerprint (1 min)
- Frontend: Next.js App Router on Vercel — static chunks carry `?dpl=dpl_...` (deployment).
- Backend: separate Origin — `x-powered-by: Express`, `server: Google Frontend` (GCP Cloud Run).
  Root often `Hello World`, `/health` returns 200. Aggressive rate-limit (spacing <1.5s → curl
  timeout 000).
- `grep -oaE 'https?://[a-z0-9.-]+\.(io|com|xyz|net|cloud)' *.js` on downloaded chunks reveals
  the API base (here `api.pencilfinance.io/graphql`). GraphQL endpoint is the ONLY real API
  surface — REST fuzzing timed out on every path.

## The recon workflow that worked (order matters)
1. **Download all Next.js chunks** (grab `src="..."` from HTML, strip `?dpl=`, fetch each with
   `curl -4`). The chunks carry the full query/mutation set as inline GraphQL strings — grep
   them FIRST; they leak the exact fields, auth token names (`access_token`/`refresh_token`),
   and the `Authorization: Bearer` header wiring.
2. **Full introspection is usually open** — `POST /graphql` with
   `{"query":"{__schema{queryType{fields{name}}}}"}` → every Query field pre-auth. Then
   `mutationType{fields{name args{...}}}` → every Mutation. Then `__type(name:"X"){inputFields{...}}`
   to get exact input shapes. Use `inputFields` not `fields` for INPUT_OBJECT (they come back null
   on `fields`).
3. Auth flow: `getNonce(address)` (public) → `loginWithWallet(input:{address,chainId,walletType,
   nonce,signature,message})`. The signature IS genuinely verified (ethers v6 `recoverAddress` —
   error "invalid raw signature length ... version=6.13.5" is the tell). JWT issued = HS256,
   32-byte sig, payload `{sub(userId), tokenType:"LOGIN", iat, exp}` — **no role claim**; authz is
   by `sub` → DB role lookup, so forging `sub` to an admin CUID needs the HS256 secret (weak-secret
   brute usually fails — "invalid signature").

## Confirmed finding classes on this target (post-auth, wallet-sig login is free)
1. **Mass PII + KYC deanonymization — `users` list query.** `query{ users{ address kycStatus } }`
   returned 1,208 users (all wallet addresses), 49 with full KYC objects (`kycStatus` leaking
   `guid`, `blockPassID`, `recordId`, `clientId`, `approvedDate/inreviewDate/waitingDate`,
   `status:approved`), plus 2 admin CUIDs + roles. Blockpass `blockPassID`/`guid` = authoritative
   real-person identity handle → wallet↔KYC deanonymization. **Probe trigger:** any plural `X`/`Xs`
   query that returns other users when caller only "should" see `me`.
2. **Cross-user financial disclosure — `transactionHistory(input:{})`.** Default (no `onlyMe`)
   returned ALL 30 platform transactions: `from`/`to` wallets, amounts (up to 542000), txHash,
   operation, status. The `onlyMe:Boolean` filter in `TransactionHistoryQueryInput` exists but is
   NOT enforced server-side by default. **Probe trigger:** a read query with a `where`/`input`
   filter that includes an `onlyMe`-style boolean — send `{}` and confirm you see others' rows.
3. **Unrestricted ledger write — `createTransactionHistory`.** `mutation{ createTransactionHistory(
   input:{operation:Invest assetsType:JuniorPool status:Success amount:9999999 ...}) }` persisted a
   fabricated "Success invest" record. `from` overwritten to caller's wallet (good), but
   `to`/`amount`/`status`/`txHash` attacker-controlled → ledger/manifest poisoning. A prior tester
   already injected `txHash:"0xprobe"` (visible in leaked history). **Probe trigger:** any
   `createX`/`upsertX` mutation accepting a `status` enum + `amount` + `txHash` for a *financial*
   record — those must never be client-supplied.
4. **Deterministic signing oracle — `ocidNftSignature`.** Returns `{msg, signature}` constant across
   calls = platform hot-wallet signing a fixed message on demand to any authed caller. **Probe
   trigger:** any `*Signature`/`*Sign` mutation returning a signature — call twice, identical
   msg+sig = fixed-key oracle; check if that sig authorizes a `mint*`/`*Nft` mutation.

## Adversarially validated NON-findings (safe — don't burn rounds re-testing)
- `invest` ownerAddress spoof → "You can only invest with your own wallet address".
- `repayment`/`withdraw`/`approve`/`deleteBundle`/`upsertBundle`/`upsertOrganization` → all
  role/owner-gated with precise error strings.
- `claimInterest`/`claimPrincipal`/`redeem`/`refund`(assetId) → assetId lookup + owner scope.
- `connectOcid(idToken)` alg:none/forged → "OCID not found" (parses sub, no sig bypass).
- CORS: `access-control-allow-credentials: true` + `vary: Origin` but NO `allow-origin` reflected
  for evil.com → cross-origin theft BLOCKED (report as misconfig, not exploitable).
- JWT weak-secret brute (26 candidates) → all "invalid signature" → forge BLOCKED.
- Nonce random per call → replay BLOCKED.

## Enum gotchas (Prisma/NestJS GraphQL)
- Enums capitalized: `PoolType { Junior, Senior }`, `TransactionAssetsType { Bundle, JuniorPool,
  SeniorPool, LoanRepayment, JuniorPoolAsset, SeniorPoolAsset }`, `TransactionStatus { Pending,
  Success, Reverted }`, `PublishStatus { Draft, Published, Review, Decline }`, `TransactionAction {
  Create, Update, Approve, Publish, Unpublish, Invest, CancelInvest, Redeem, ReceiveAirdrop, Refund,
  Withdraw, Repay, ClaimInterest, EarlyRedeem, MarkAsEnded }`.
- Paginated list types (`bundles`/`juniorAssets`/`seniorAssets`) return `{total, data:[...]}` — must
  select `data { ... } total`, not resource fields directly.
- `testUser`/`fetchTestToken`/`shareGenesisBadge`/`markKycPopup` return SCALAR (String/Boolean) —
  "must not have a selection since type ... has no subfields" = no `{ }` selection.

## Minimal login helper (eth-account available on the box)
```python
from eth_account import Account
from eth_account.messages import encode_defunct
# getNonce -> sign nonce text -> loginWithWallet -> Bearer token -> run any authed query/mutation
# msg format is loose: backend only does recoverAddress(sig, message)==address; nonce in message
# not strictly checked, but nonce itself is random per session.
```
Full session transcript + probe files under `/tmp/pencil/*.py` (login_test, auth2, jwtforge, priv,
funds, kyc_tx, pii, kycfull, write, ocid, ocid2, cors).

## Report discipline for this class
- 0 live TVL on-chain (junior/senior/funding contracts `eth_getBalance` = 0x0 and growToken
  `balanceOf` = 0) while off-chain NAV ≈ $1M → protocol PRE-LAUNCH. Do NOT claim fund theft; the
  data-leak + ledger-write findings stand on their own. Always check on-chain balances before
  claiming a fund-drain impact.