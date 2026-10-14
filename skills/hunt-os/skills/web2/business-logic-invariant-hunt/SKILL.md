---
name: business-logic-invariant-hunt
description: "payment/refund/IDOR/race invariant attacks"
metadata:
  version: 1.0.0
  hermes:
    tags: [bug-bounty, business-logic, race-condition, idor, ssrf, price-tampering]
    category: security
---

# Business-Logic Invariant Hunt

Class-level playbook for probing web apps for invariant violations across
payment, credits, referral, refund, social-share, and subscription subsystems.

Use this when the operator hands you a numbered probe list (e.g. 15+ probes covering
checkout, crypto webhook replay, wallet race, self-referral, twitter-share SSRF, etc.)
against a Next.js / Stripe / NextAuth-style SaaS target.

## RULE ZERO — execute, don't narrate (at the top because it kept being ignored)

This skill already carried an "execution first" rule mid-file — and an agent STILL
burned four consecutive turns *announcing* recon ("oke, langsung eksekusi — download
JS chunks sekarang") with zero tool calls, then ended the session doing it again.
So the rule lives first now:

Before you write any sentence containing "mau …", "oke gue jalanin …", "sekarang gue …",
"starting now", or similar — STOP. If the current assistant turn has no tool
invocation, you have made zero progress regardless of what the prose claims. Put the
curl/patch/search call in THIS response; narrate around it if you must.

Companion failure mode from the same session: never assert a result in prose
("got a 429", "target is WAF-limited") that does not appear verbatim in a tool
result. Every claim in REPORT.md must trace to a captured response block.

## When to load

This skill already carried an "execution first" rule mid-file — and an agent STILL
burned four consecutive turns *announcing* recon ("oke, langsung eksekusi — download
JS chunks sekarang") with zero tool calls, then ended the session doing it again.
So the rule lives first now:

Before you write any sentence containing "mau …", "oke gue jalanin …", "sekarang gue …",
"starting now", or similar — STOP. If the current assistant turn has no tool
invocation, you have made zero progress regardless of what the prose claims. Put the
curl/patch/search call in THIS response; narrate around it if you must.

Companion failure mode from the same session: never assert a result in prose
("got a 429", "target is WAF-limited") that does not appear verbatim in a tool
result. Every claim in REPORT.md must trace to a captured response block.

## When to load

- "BUSINESS-LOGIC AGENT — invariant violation hunt…"
- "Probe /api/checkout for price tampering"
- "Race the refund endpoint while PATCHing wallet address"
- "Test twitter share award for SSRF / double-award"
- Any numbered probe brief against payment / credits / referral / refund / social systems

## Execution first rule

Promoted to RULE ZERO at the top of this file — it sat here and was still violated
for four straight turns. The anti-pattern examples below stay; they document the
exact failure shape.

## Anti-pattern vs Correct-pattern

❌ Anti-pattern (no real progress, just announcing):
```
Turn 1: "Siap, gue kerjakan..." + setup todo
Turn 2: "Oke gue jalanin sekarang — download JS chunks paralel."
Turn 3: "Mau download JS bundles paralel."
Turn 4: "Oke gue jalanin sekarang."
```

✅ Correct pattern:
```
Turn 1: load relevant skill + curl homepage + extract JS srcs
Turn 2: download all JS chunks + grep for endpoints, fire Probe 1+
Turn 3: fire Probes 2–4
```

## Pre-flight (1 turn) — catch-all fingerprint BEFORE any endpoint probe

On Next.js App Router targets, **guessed `/api/*` paths do not 404**. A fake path
like `/api/stripe/checkout` returns HTTP 200 with the full SPA HTML shell —
the exact same kilobytes served for `/`. An agent once probed 15 guessed
endpoints on everlyn.ai, got 200 HTML for every one, and reported them as
"endpoint discovery status" — pure garbage. So the FIRST turn must fingerprint
the catch-all before spending probes on guessed paths:

```bash
B="https://TARGET"
# 1. Save homepage reference size
curl -s4 "$B/" -o home.html
# 2. Fetch a known-nonsense API path
curl -s4 "$B/api/nonexistent-garbage-$$" -o fake.html
# 3. Compare
if cmp -s home.html fake.html; then
  echo "NEXTJS CATCH-ALL CONFIRMED: any 200 on /api/* from <base> is SHELL HTML, not a route."
  echo "Only trust 200s that diff from home.html (JSON body, Set-Cookie, different size)."
fi
```

Only after this gate:
1. Fetch homepage with `curl -4` (Cloudflare-backed Next.js hosts often have IPv6
   pitfalls — always force IPv4).
2. Extract `_next/static/chunks/*.js` URLs from HTML (chunks are real, paths are
   not — trust the JS manifest for endpoint discovery, never probe names).
3. `mkdir -p /tmp/<target>_logic` and `cd` there.

## Recon (1–2 turns, parallel)

Download all referenced JS chunks and grep for endpoint paths:

```bash
mkdir js && cd js
grep -oE 'src="[^"]+\.js[^"]*"' ../homepage.html | \
  sed -E 's/src="([^"]+)"/\1/' | \
  xargs -P 16 -I{} curl -s4O "https://TARGET{}"
cd ..
grep -rEho '"/api/[a-z0-9/_-]+"' js/ | sort -u > endpoints.txt
grep -rEiho 'coinbase|nowpayments|btcpay|stripe|payment_intent|checkout\.sessions' js/ | sort -u
```

This auto-discovers:
- `/api/checkout*`, `/api/stripe/*`, `/api/payment/*`, `/api/order/*`
- `/api/webhook/*` (which crypto provider is in use)
- `/api/invite/*`, `/api/referral/*`
- `/api/twitter/share`, `/api/social/*`
- `/api/credits/locked`, `/api/credits/unlock`
- `/api/subscription/*`

## The probe checklist (20 canonical probes)

Fire in order. Keep each probe's curl, response, and verdict together — do not
reorder when reporting.

1. **Checkout price tampering** — `product_id='pro'` + `amount=999`, verify server recomputes server-side.
2. **Crypto webhook replay + race** — same `payment_id` 2× simultaneously → double credit?
3. **Refund-by-crypto wallet race** — `POST /api/refund` ⊕ concurrent `PATCH /api/user/wallet` → which wallet wins?
4. **Referral self-invite + race + plus-addressing** — invite self, race 2 redemptions, signup `a@x` vs `a+x@x`.
5. **Twitter share award: SSRF + verify + race** — bad tweet URL, faked twitter URL (SSRF), 2 simultaneous share calls (double award).
6. **locked_credits `?recursive=true` flood** — race with active video job to double-unlock.
7. **Account enumeration** — signup with existing email vs new, distinct error?
8. **IDOR** — `GET /api/orders?id=1,2,3` sequential with same auth token.
9. **Parameter pollution** — `?id=1&id=2` — which wins, does it leak across users?
10. **Negative amount/quantity** — `amount=-1`, `quantity=-1`.
11. **Integer overflow** — `amount=99999999999999999999` (> int64).
12. **Upgrade/downgrade subscription race** — concurrent POSTs to different plans.
13. **Whitelist bypass** — `admin@<domain>`, `info@<domain>`, locale-variant or Unicode-lookalike emails.
14. **Cancel-subscription race with refund** — both fire concurrently; refund on cancelled sub?
15. **Endpoint mapping FIRST** — HEAD + POST every guessed payment/refund/webhook path
    (`/api/checkout`, `/api/stripe/*`, `/api/crypto/*`, `/api/payment/*`) before deep
    probes; record 404 vs 405 vs 401/307 so later verdicts don't confuse "missing"
    with "blocked". Guessed-endpoint 404s are recon, not findings.
16. **Currency-confusion cross-replay** — submit `{"product_id":"X","amount":7000,"currency":"CNY"}`,
    capture any server-computed converted field (e.g. `cn_amount`), then replay the
    same body as USD. If a CNY-denominated amount settles as USD, ~7x discount vector.
17. **Webhook replay without signature** — POST a realistic-shaped test payload
    (e.g. Stripe `checkout.session.completed` with a plausible `pi_...`/`cs_test_...`
    id) to the webhook with no and with a bogus signature header. `400 signature
    verification failed` = BLOCKED; `200`/`202` or any state change = EXPLOITABLE.
18. **Email canonicalization** — three sub-probes: (a) `USER@x.com` vs `user@x.com`
    duplicate registration, (b) plus-addressing self-referral (`a+1@x.com`, `a+2@x.com`
    sharing one invite code), (c) Unicode homograph (`tеst@example.com` with Cyrillic
    е, U+0435) vs its ASCII twin. Any accepted duplicate = collision/farming vector.
19. **Non-integer / extreme numerics** — `amount=-1`, `credits=-100`, `credits=NaN`,
    `credits=1e308`, `amount=99999999999999999999` (>int64), `quantity=-1`. Watch for
    silent negative balances, NaN-poisoned sums, overflow wrap, or leaking 500s.
20. **Pagination edge cases** — `?limit=-1`, `?limit=1000000`, `?offset=-1`, `?page=0`
    on every list endpoint (`/api/history`, `/api/orders`). Negative offsets that
    still return rows, or unbounded limits, are data-leak/DoS vectors.
21. **Invite code type-confusion** — `invite_code` as number (`123456`), float (`3.14`), array (`["A","B"]`), object (`{"code":"x"}`), `null`, empty `""`, whitespace `"   "`, SQLi (`' OR '1'='1`), case/trailing-space variants. String `"FAKE123"` must be `400 Invalid invite code`, missing key `400 required`, but non-string must NOT be `500` — `500` is unhandled validation crash (Nuxaris 2026-08: numeric/float/array → `500 Internal server error`).
22. **Rate-limit header bypass** — fingerprint `Ratelimit-Limit`, `Ratelimit-Policy` (`10;w=60` auth / `60;w=60` bridge / `30;w=60` wallet), `Ratelimit-Remaining`, `Ratelimit-Reset`, `Retry-After`. Then replay same probe with `X-Forwarded-For: 1.1.1.1/8.8.8.8/127.0.0.1`, `X-Real-IP`, `X-Originating-IP`, `CF-Connecting-IP`, `True-Client-IP`. If `Remaining` still decrements linearly (6→5→4→3→2) the bucket is IP-bound at Caddy/edge and not header-overridable — record as BLOCKED.
23. **Public quote limit bypass** — `GET /api/bridge/quote?tokenA=CC.canton&tokenB=ETH.ethereum&amount=...` (or equivalent price-quote route) is often **unauthenticated** (`200` even with `Bearer fake`). Test with `tokenA` in canonical `SYMBOL.chain` form (`CC.canton`, `ETH.ethereum`). Probe `0`, `-1`, `NaN`, `Infinity`, `1e24`, `999999999` against documented `limits.maxAmount` (from `/routes`). Correct: `400 amount must be positive` for negative/NaN, `400 Fees exceed` for dust. Exploit: `200` for `999M` when max is `100k` (Nuxaris: `CC→ETH max 100k` returned `200 amountOut 50524` for `999M` and `1e24` → `5e19`) + param pollution `?amount=100&amount=999` silently using first value.
24. **JWT alg:none / kid / jku + refresh-token shape** — `GET /api/auth/me` with no token → `401 Missing or invalid Authorization header`, garbage → `401 Invalid token`, `alg:none` (`eyJhbGc...`) → `401`, HS256 with weak secrets (`secret`,`nuxaris`,`password`,`123456`,`auth_secret`,`jwt_secret`,`nuxarisapiv1`) → `401`, `kid=../../../../etc/passwd`, `jku=https://evil.com` → `401`, `kid=none` → `401` when blocked. `POST /api/auth/refresh` empty → `400 refresh_token is required`, garbage/none/array/wrong key → `401/400`. Any `200` on these is EXPLOITABLE.

Per-probe copy-paste commands live in `references/probe-commands.md` and `examples/hunts/web2/business-logic-invariant-hunt/nuxaris-2026-08-deep-hunt.md` (Nuxaris invite/rate-limit/quote/JWT/CORS pattern).

## Output contract (mandatory)

Every probe MUST be reported in exactly this shape — the operator uses it verbatim
for triage. Do not reorder fields, do not elide the response body (truncate to
200 lines if huge):

```
### Probe N — <name>
**Command:**
\`\`\`bash
<exact curl>
\`\`\`
**Response:**
\`\`\`
<actual response body>
\`\`\`
**Verdict:** EXPLOITABLE | BLOCKED | NEEDS-AUTH
**Impact:** <one sentence>
```

Verdict rubric:
- **EXPLOITABLE** — impact demonstrable from the captured response alone (sign-flip,
  double award, cross-user data, SSRF hit, distinct enum error).
- **BLOCKED** — server rejected input, recomputed server-side, or returned uniform
  error regardless of state.
- **NEEDS-AUTH** — endpoint requires valid session; record现价 so auth'd re-test
  picks up where this left off. Still report endpoint shape + observed unauth
  behaviour.

## Target-type gate — umbrella / research repos have no payment invariants (Everlyn-1, Aug 2026)

`Everlyn-Labs/Everlyn-1` has `language: null`, top-level `tree` of three `mode: 160000` gitlinks (ANTRP, EfficientARV, Wasserstein-VQ) + README. Zero web routes, zero auth, zero payment/balance state machine. A full 20-probe payment/referral/credit run is wasted work and produces false NEEDS-AUTH verdicts.

Gate (one `curl` before any probe):

```bash
curl -s https://api.github.com/repos/OWNER/REPO | jq '{language, size, topics}'
curl -s https://api.github.com/repos/OWNER/REPO/contents?ref=main | jq -r '.[] | "\(.type) \(.mode // "-") \(.name)"'
# If language==null and top-level is N× type:file or mode 160000 → research umbrella → pivot
curl -s4 https://TARGET/api/nonexistent-garbage-$$ -o /tmp/fake.html
cmp -s <(curl -s4 https://TARGET/) /tmp/fake.html && echo "catch-all SPA shell — no API trust boundary"
```

If gate fires: skip invariant probes, load `github-secret-hunt` + `bug-bounty-agent:pre-launch-detection`. Valid invariants become checkpoint/cache integrity (`torch.load`/`pickle.load` without `weights_only`), arbitrary-download/SSRF (`download_url`/`cache_url` with no allowlist), hardcoded secrets. See `examples/hunts/web2/business-logic-invariant-hunt/everlyn-umbrella-repo-pivot.md`.

## WordPress / WPForms CMS invariant hunt — Simply.com gatekeeper (Partisia 2026-08)

WordPress + WPForms contact forms behind Simply.com's 454 PoW / 455 WAF are a recurring CMS class — not Stripe, not Woo. Treat as a first-class invariant suite when `Server: Simply.com` and `/wp-json/` 200:

**Gatekeeper:** every GET without `sc_clearance` → 454 `Checking your browser` (JS worker SHA256 `T:nonce`, `lz >=16`, POST `/.sc-verify/` → `sc_clearance=ts|hmac; Max-Age=86400; Domain=target`). Solver: `hashlib.sha256(f"{T}:{nonce}").hexdigest()` loop ~47k iter <1s, single UA. Cookie **not bound to IP/UA** → replayable across sessions for 24h (proof: copy to fresh `requests.Session()` → `GET /` 200). `POST /wp-login.php` etc stay 455 even with clearance — WAF hard-block, brute pointless.

**WPForms 8509 invariant matrix** (`POST /wp-admin/admin-ajax.php` `action=wpforms_submit`, XHR + `Referer`): fields `[1][first]`/`[1][last]` (name), `[2]` email*, `[3]` textarea, `[4]` honeypot hidden 1×1px. Always send `wpforms[id]`, `wpforms[post_id]`, `page_title`, `page_url`, `url_referer`.

| Invariant | Payload | Expected | Actual (Partisia) | Verdict |
|---|---|---|---|---|
| Honeypot must block | `fields[4]=filled` | reject | `success:true` | EXPLOITABLE |
| Name no CRLF/header | `fields[1][first]=a\nBcc:evil` | reject | `success:true` | EXPLOITABLE |
| Email valid | `not-an-email` / `test@invalid` | reject | `field: The provided email is not valid.` | BLOCKED |
| Script/SVG blocked | `<script>alert(1)</script>` | 403 | 403 WAF | BLOCKED (WAF, not app) |
| Benign HTML | `<b>world</b>` | pass/sanitize | `success:true` | pass |
| 10k chars truncate | `A*10000` | truncate/reject | `success:true` | EXPLOITABLE (storage DoS) |
| Ghost field | `fields[999]=injected` | ignore/reject | `success:true` | EXPLOITABLE |
| Rate limit | 10× POST 6.2s | throttle | all `success:true` | EXPLOITABLE |
| Duplicate submit | same body 2× | idempotent/dedup | both `success:true` | EXPLOITABLE |

**Recon order (gatekeeper-aware):**
```bash
curl -skI -A "$UA" https://TARGET/                 # expect 454 without clearance
# solve pow, set cookie, then:
curl -s -b "sc_clearance=TS|HMAC" https://TARGET/wp-json/ | jq .namespaces
curl -s -b "sc_clearance=TS|HMAC" https://TARGET/get-in-touch/ | grep -o 'data-token="[^"]*"'
curl -s -b "sc_clearance=TS|HMAC" https://TARGET/wp-json/wp/v2/media?per_page=100 | jq length  # 332 on Partisia
```
Detail + curls in `examples/hunts/web2/business-logic-invariant-hunt/partisia-wordpress-wpforms-2026-08.md`.

## Pitfalls

- **MODEL-SWITCH OUTPUT CORRUPTION (observed July 2026)**: When the backend model changes mid-session via xkiro (e.g. deepseek→mistral→qwen→openai), context fragmentation can produce verbose, looping, or corrupted output. **Operator trigger phrases**: "cokkk, output mu coba lihat, kenapa itu?", "output lo aneh", "haduh stream keputus lagi". **Immediate fix**: one-line apology + crisp restart of actionable output; do NOT re-analyze or explain the corruption. After a model switch, keep responses tight (under 500 chars) for the first 2-3 turns until stability is confirmed. **Never** assert a probe result as a finding from a post-switch corrupted-turn — re-run the curl first.
- **IPv6 on Cloudflare-backed Next.js** — always `curl -4`. IPv6 routes often hang
  or return stale PoP.
- **NextAuth middleware returns 307 to `/api/auth/signin`** — treat as NEEDS-AUTH, not
  BLOCKED. Distinguish carefully in verdicts.
- **RSC payloads (`?_rsc=…`)** reveal auth state (`NEXT_REDIRECT` vs "No access" vs
  content) without needing a session — useful for NEEDS-AUTH probes to at least
  confirm endpoint existence.
- **Race-window timing** — for true race probes use `&` + `wait` (shell) or
  `xargs -P`, don't fire serially and call it a race.
- **Stripe test mode** — if `pk_test_*` is in the bundle, the whole payment stack
  may be in test mode. Annotate; do not claim "real-money exploit" against test keys.
- **"Mau jalanin sekarang" is not a tool call** — see Execution first rule above.
- **Sequential narration drift (observed session failure)** — in one real session the
  agent loaded the skill, fetched the homepage, then burned ~6 turns emitting
  tool-call-shaped narration ("Gue kerjakan — batch besar sekarang…", "Oke gue
  eksekusi sekarang beneran…") where the only real tool call was a no-op todo
  update. Operator's meta-reviewer flagged it. Root cause and countermeasures:
  - After skill loading + pre-flight, the NEXT assistant message must contain a
    `terminal` call containing the actual recon script. A turn whose only tool
    call is `todo` while in a probe-execution phase is a stall, full stop.
  - Kill the filler phrases in ALL languages: "Gue kerjakan sekarang", "Oke gue
    jalanin", "Lanjut — batch paralel", "Mau gue eksekusi". If the sentence is
    about what you are *about* to do, delete it and put the command in a tool
    call instead.
  - `todo` updates cost a whole round-trip. Update todos once at plan time and
    once at completion, NOT between every probe. In a 14-probe engagement that
    is 2 todo calls total, not 14.
  - When probes are independent (they almost always are), write ONE bash script
    that runs them all sequentially inside a single `terminal` call, tee-ing
    `curl + status + first-300-chars` per probe to `probe_NN.txt`. This
    satisfies the operator's "every curl + response" contract in one turn
    instead of 14.
  - If you catch yourself writing more prose than commands, you are in the
    drift. Stop mid-sentence and emit the `terminal` call.

## One-shot probe script (required execution shape — this is the first real terminal call)

Instead of 14 separate tool calls, generate and run a single script:

```bash
cd /tmp/<target>_logic
cat > run_probes.sh <<'EOF'
#!/bin/bash
B="https://TARGET"
run() {  # run <label> <curl args...>
  local label="$1"; shift
  echo "===== $label ====="
  echo "\$ curl $*"
  curl -s4 -o /tmp/body.$$ -w 'HTTP %{http_code} time=%{time_total}s\n' "$@"
  head -c 300 /tmp/body.$$; echo; echo
}
# Probe 1 — endpoint discovery, GET/POST/OPTIONS per path
for p in /api/checkout /api/stripe/webhook /api/crypto/webhook /api/invite \
         /api/share /api/credits /api/wallet /api/history /api/orders \
         /api/upload /api/sign /api/v1/user /api/v2/user; do
  run "P1 GET $p"     "$B$p"
  run "P1 POST $p"    -X POST -H 'Content-Type: application/json' -d '{}' "$B$p"
  run "P1 OPTIONS $p" -X OPTIONS "$B$p"
done
# Probe 2 — webhook replay with unsigned body
run "P2 stripe webhook fake" -X POST -H 'Content-Type: application/json' \
  -H 'Stripe-Signature: t=1,v1=deadbeef' \
  -d '{"type":"payment_intent.succeeded","data":{"object":{"id":"pi_fake"}}}' \
  "$B/api/stripe/webhook"
# ... probes 3–14 follow the same run() pattern
EOF
bash run_probes.sh | tee results.txt
```

One `terminal` call produces the entire evidence base; the report is then a formatting pass.

- **"Mau jalanin sekarang" is not a tool call** — see RULE ZERO at the top.
- **Script-buffer drift (observed session failure)** — variant of the announcer
  anti-pattern: agent writes a probe script with `write_file` (legit tool call),
  then on the very next turn *describes* running it ("Gas eksekusi block (a) 🚀")
  but emits NO tool call, or fires an empty `terminal` invocation that contains
  no command. Four consecutive turns produced zero bytes of probe output while
  the prose insisted execution was happening. Countermeasures:
  - The turn immediately after `write_file(my-script.sh)` MUST be a `terminal`
    call whose `command` runs the script (`bash my-script.sh 2>&1 | tee run.log`).
    If you instead wrote another piece of prose about running it, you are in
    the drift.
  - An "empty terminal output" tool result is a red flag — it means you invoked
    `terminal` with no/empty command. Do NOT acknowledge and move on; the next
    assistant turn must contain the real command.
  - Prose promises compound: each "Oke lanjut — block (a) 🚀" without a tool
    call makes the next one easier. Break the loop by emitting the terminal
    call BEFORE any prose.
- **WAF 429s during fan-out recon** — ripping 40+ JS chunks with `xargs -P 16` or
  hammering probes in tight parallel bursts can trip edge rate limiting. A 429 is
  NOT a probe verdict — it says nothing about endpoint logic. Throttle bulk
  downloads (`-P 4` + short sleep), wait out the cooldown, and reserve true
  parallelism for the dedicated race probes where `xargs -P` / `&`+`wait` is the
  whole point. If a 429 claim isn't backed by a captured response, it does not go
  in the report.
- **Guessed endpoints are recon, not findings** — a 404/405 on a guessed `/api/...`
  path only narrows the map. Confirm paths from JS bundles/`endpoints.txt` before
  spending rate-limit budget on them.

## Reference files

- `references/probe-commands.md` — copy-paste curl/bash for the full 20-probe set
- `references/expo-rn-web-app-recon.md` — Expo/React Native web app bundle extraction, Paybox case study
- `examples/hunts/web2/business-logic-invariant-hunt/everlyn-labs-waitlist-invite-analysis.md`
- `examples/hunts/web2/business-logic-invariant-hunt/everlyn-umbrella-repo-pivot.md` — umbrella research repo pivot (Everlyn-1 Aug 2026): fingerprint (language:null + 3×160000 gitlinks), dulwich clone fallback for missing `git-remote-https`, ML supply-chain sink list + chains
- `examples/hunts/web2/business-logic-invariant-hunt/crypto-payment-shipany-analysis.md`
  webhook replay, race patterns, refund/wallet race, twitter-share SSRF + double-award,
  IDOR and pagination sweeps, email enumeration/canonicalization, plus-addressing,
  Unicode homographs, and numeric edge cases (negative, NaN, 1e308, >int64).