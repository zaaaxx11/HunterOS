# api.noise.xyz Authenticated Fuzz — Privy SIWE — 2026-08-12

## Target
`noise.xyz` (Vite+React+Privy) + `api.noise.xyz/api/*` REST. Two burner wallets via Privy SIWE.

## Auth Reverse — Privy SIWE
- App: `cmm9myejp00ug0ci8qxky5ocd` client `client-WY6WjKbTDAVtj3TDMsyvpqq355bF5ZRKbugDf1E8k4z3j`
- `POST https://auth.privy.io/api/v1/siwe/init {address}` → `{nonce, expires_at}`
- SIWE message MUST use `domain: noise.xyz` + `uri: https://noise.xyz` (NOT privy.io):
  ```
  noise.xyz wants you to sign in with your Ethereum account:
  0x...
  By signing, you are proving you own this wallet and logging in...
  URI: https://noise.xyz
  Version: 1
  Chain ID: 1
  Nonce: <from init>
  Issued At: 2026-08-12T06:50:43.000Z
  Resources:
  - https://privy.io
  ```
- `domain privy.io + uri https://auth.privy.io` → `400 SIWE message domain is not allowed by the app`
- `POST /api/v1/siwe/authenticate {message, signature:0x..., chainId:"eip155:1", walletClientType:"metamask", connectorType:"injected", mode:"login-or-sign-up"}` → `mode: login` invalid enum, must be `login-or-sign-up` or `no-signup`
- Success → `{user:{id:did:privy:..., linked_accounts:[{address, chain_type:ethereum}]}, token: identity JWT ES256, privy_access_token, refresh_token, is_new_user}`. Use `token` (identity) as `Authorization: Bearer` for api.noise.xyz; `privy_access_token` → 401 on api.
- Throttle 0.8-1.1s per privy call, 0.8-1.2s per api call.

## Public Fuzz (50+ req 0.8-1.2s)
- `/api/health 200`, `/api/trends` 200 (ignores limit/offset always 123720B vs `/api/posts?limit=999999` 400 strict `<=100`), `/api/trends/:idOrSlug` 200/404 reflects id JSON (no SQL/XSS), `/api/posts?limit=1` 200, traversal `../../` 400 nginx, CORS `ACAO=https://noise.xyz` only (evil.com empty).

## Authenticated Fuzz (burner A cmspqcyso + B cmspqgl9g, throttle 0.9-1.2s)
| Test | Payload | Result |
|---|---|---|
| POST /api/posts create | `{assetId:771f317a..., content:"test", title:"x"}` | 201 own userId forced |
| BOLA DELETE other's post | B DELETE 653f412b (A's) | 400 `VALIDATION_ERROR You can only delete your own comments` |
| BOLA PATCH other's post | B PATCH same | 400 `You can only edit your own comments` |
| Mass assignment | `{userId:fake, score:9999, authorAddress:0xdead}` | Ignored → returned caller userId, score 0, authorAddress null |
| Rate limit | 4th POST/min | 429 `RATE_LIMIT_EXCEEDED 3/min` 35s wait |
| Vote endpoints | POST /api/posts/:id/vote|upvote|like | 404 not exposed |
| Stored XSS content | `content:"<script>alert(1)</script>"` | 201 stored raw 1bae42f3, GET returns raw unescaped |
| Stored XSS title | `title:"<img src=x onerror=alert(1)>"` | 201 stored raw e5d54c90 |
| Reply | `{parentPostId: postA}` | Works; cross-asset parent rejected? not tested |

## Verdict
- BOLA BLOCKED (ownership check server-side), mass assignment BLOCKED, rate limit GOOD.
- **Stored raw HTML** — backend no sanitization; trusts frontend. React default escapes via `{content}` but `dangerouslySetInnerHTML` would execute. Rate MEDIUM pending DOM render check. Cleanup verified DELETE 204 all test posts → 0 own remain.

## Files
`/tmp/siwe_auth*.py`, `/tmp/auth_fuzz*.py`, `/tmp/privy_token.json`, `/tmp/userB_token.json`, `/tmp/auth_fuzz_report.md`
