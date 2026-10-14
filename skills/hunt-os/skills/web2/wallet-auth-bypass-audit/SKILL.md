---
name: wallet-auth-bypass-audit
description: "audit wallet-based auth flows for bypass"
metadata:
  version: 1.0.0
  hermes:
    tags: [web3, auth, wallet, signature, jwt, crypto-js, cdc, bug-bounty]
    category: security
---

# Wallet Auth Bypass Audit — Signature-Less Login Class

## Triggers
- Login endpoint that mints tokens from a wallet address with no `personal_sign`/SIWE proof
- Bundles leaking AES/RC4 passphrases behind an "encryption" layer
- `/users`, `/user/me`, `/status`, `/stake`, `/balance` reachable with a forged/dumped login
- Products sharing one backend codebase (Web3 app families) where SOME services auth correctly
- Operator hands a Web3/custodial app and asks for account-takeover / wallet-impersonation hunt

## The core idea
A Web3 app family often ships one auth library to several backends; some get the wallet-signature
check right (SIWE + HMAC x-signature), others mint a session on just the address. That inconsistency
is the highest-yield finding. It is also the proven #1 class bug: on messier.app (2026-09) 4/4
backends (virgo, p2p, openhatch, innovatorhub) took a bare address/base_token at login.

## Step 1 — Fingerprint the login endpoint (find the crack, don't guess)
Load the SPA bundle and look for the auth call. Signals:
- `POST /auth/entryUser` with a `base_token` / raw-token string like `"open_<ADDRESS>_<suffix>"`
- `POST /api/v1/auth/login` (or `/api/v1/auth`) with `{"address":"<0x...>"}`
- Response keys distinguish the scheme: `access`/`refresh`/`session` (JWE) vs `accessToken`/`refreshToken` (JWT) vs `access`+`secret` (HMAC signing key per login)
- Any 200/201 + token with NO nonce/signature/challenge = account takeover of any wallet
- The `"email verification has been sent"` string is often a LIE — the token works immediately (confirm via `GET /user/me`)

Probe matrix (messier, all live-proven):
| Backend | Request | Result |
|---|---|---|
| virgo-api | `POST /auth/entryUser {"base_token":"open_<addr>_virgo","info":{}}` | 201 JWT; admin wallet from /users dump → admin profile |
| p2p-api-v2 | `POST /api/v1/auth/login {"address":"<0x...>"}` | JWE access/refresh/session, no nonce/rate-limit → victim withdraw logic reachable (400 validation not 401) |
| openhatch | `POST /auth/entryUser {"base_token":"open_<addr>_hatch","code":"000000",...}` | `code:"000000"` hardcoded in bundle = 2FA bypass at login |
| innovatorhub | `POST /api/v1/auth {"address":"<0x...>"}` | access/refresh/**secret** (HMAC key per login → attacker can sign ANY request) |

Method: probe with a FRESH random wallet (never a real victim) unless the operator supplied a test
address. Mint → hit `GET /user/me` with the token → 200 profile = proof.

## Step 2 — Cross-link to /users dump + admin wallet
Common companion: `GET /users` (or `/user/status`, `/stake`, `/balance`) reachable with a
bundle-hardcoded `authorization: <static-key>` header (no Bearer prefix). Returns
`{address, role, active, username}`. Grep the bundle for `authorization:` + `IH="..."`-style
constants to find the static key. The dump yields the ADMIN wallet address → use it in Step 1
to mint an admin-profile login and prove privilege.

## Step 3 — Crack CryptoJS RC4→AES transport "encryption" (keys in public bundle)
Response bodies beginning `"U2FsdGVkX1/..."` = CryptoJS `Salted__` header, OpenSSL MD5-EVP KDF.
Recover keys by grepping the bundle for the pair `AES.decrypt(` + `RC4.decrypt(` near `Utf8` and
`JSON.parse`; passphrases are adjacent string literals.
- Decrypt order (outer→inner): `RC4.decrypt(body, RC4KEY)` → `AES.decrypt(→, AESKEY)` → JSON
- Key derivation: CryptoJS uses EVP_BytesToKey with MD5 (`prev = md5(prev + passphrase + salt)`)
- Keys are often REUSED across sibling backends (virgo + horizon shared the same RC4 key)
- No nonce/timestamp → replay unlimited; once cracked, craft arbitrary encrypted request bodies
  with the matching encryptor (outer RC4 over inner AES over JSON), usually under `{"data": ...}`
- Different app = different keys. innovatorhub is env-gated (`ENC_KEY_1/2`, ENC=true to enable);
  openhatch has its own pair. Extract per-app before assuming a shared key.
- Working decryptor + request-shadow example: `examples/hunts/web2/wallet-auth-bypass-audit/messier-signatureless-login-2026-09.md`

## Step 4 — Balance sweep WITHOUT RPC ghost false-positives
When quantifying impact (dump addresses + balances), the number one trap is a load-balancer RPC
answering `eth_getBalance` for a known burn/pool address to an unrelated wallet, or a seed node
returning stale/garbage values → fake aggregates like "13,632 ETH", "4,002 ETH", "16.6M BNB ($9.6B)"
(none real). Honest rules:
1. Read every wallet on a SINGLE stable RPC (a failover list is what bleeds wrong balances in)
2. Pull the top-1 wallet individually first; if it dominates >70% of an aggregate that's a red flag
3. Explicitly exclude `0x0000...dEaD` (burn) / pool LP addresses; report them separately
4. Verify the RPC is reachable AND honest before a big sweep: `eth_blockNumber` + one known-funded
   wallet (e.g. vitalik.eth) returning a plausible number
5. Dump-addresses is not a finding by itself — the honest deliverable is verified per-wallet
   balances with whales and burn-addresses flagged separately

## Honest verdict discipline (operator rule)
- Web2 impersonation / governance vote injection / PII dump = solid CRITICAL when PROVEN with
  request+response. Redeem read access → account takeover of every wallet.
- On-chain fund theft attempts often still get BLOCKED by an ecrecover gate at the very last hop
  (self-signed sigs revert). When that happens, report "web2 BOBOL total; on-chain TAHAN" honestly —
  the operator writes the rules and accepts an honest "no fund theft" without complaint. Do NOT
  fabricate a tx hash or claim a withdrawal succeeded just to satisfy a fund-theft ask.
- Recommend the org ports their OWN correct pattern (SIWE + HMAC, which some of their backends
  already use) to every backend — that's the constructive mitigation.

## Fallback: self-funded PoC for the tx-hash proof
If the operator wants an on-chain tx hash as proof but won't, and you won't, move live user funds:
offer a SELF-FUNDED proof — operator funds a burner wallet, you deposit→withdraw through the
forged-JWT path with YOUR OWN capital. Tx hash appears with zero victim. If they decline that too,
the honest close is the proven read/impersonation chain + the verified on-chain gate blocking
fund move.