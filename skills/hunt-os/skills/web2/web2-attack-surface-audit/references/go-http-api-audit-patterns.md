# Go HTTP API Security Audit — Recurring Vulnerability Patterns

Distilled from the U2U dhcp2p red-team assessment (Aug 2026): a Go HTTP API
(chi router + pgx + Redis + libp2p signature auth) for IP lease management.
These patterns generalize to ANY Go HTTP API with signature-based auth,
a cache-aside Redis layer, and rate limiting.

## 1. Signature payload does not bind to the request (request-tampering / pre-emption)

**Pattern:** The auth middleware signs only `sha256(nonce_id)` — the HTTP
method, path, query params, and body are NOT part of the signed payload.

**Why it matters:** A single valid `(pubkey, nonce, signature)` header set
authorizes ANY operation, not just the one the client intended.

**Two attack shapes:**
- **MITM request tampering:** attacker in the middle rewrites the request
  line from `POST /allocate-ip` to `POST /release-lease?tokenID=<victim>`
  keeping headers/body identical. Signature still verifies → unauthorized
  state change.
- **Pre-emption / nonce racing:** nonce is single-use (consumed on first
  verify). Attacker who captures the headers can fire their own malicious
  request FIRST; the victim's legitimate request then fails with
  "nonce already used" — DoS + hijack in one move.

**Detection grep:**
```bash
grep -rn "sha256.Sum256" internal/ --include="*.go"
# Then read the auth service: does the payload include method/path/body?
grep -rn "VerifyAuth\|VerifySignature" internal/ --include="*.go" -A 10
```

**Fix:** sign `method || path || sha256(body) || nonce_id`; server
recomputes the same composite before verify.

## 2. Public read endpoints leak lease/state data (enumeration)

**Pattern:** `GET /lease/peer-id/{peerID}` and `GET /lease/token-id/{tokenID}`
mounted OUTSIDE the auth-protected route group.

**Impact:** full enumeration of active leases, mapping peer_id ↔ token_id ↔
expiry. Reconnaissance for targeted release-blocking or social engineering.

**Detection:**
```bash
grep -rn "r.Get\|r.Post" internal/app/adapters/handlers/http/router.go
# Diff which routes sit inside `r.Group(...WithAuth...)` vs outside.
```

## 3. Rate-limiter cleanup wipes ALL limiters periodically

**Pattern (real code, dhcp2p `middleware/rate_limiter.go`):**
```go
func (rl *RateLimiter) cleanupUnusedLimiters() {
    rl.limiters.Range(func(key, value interface{}) bool {
        rl.limiters.Delete(key)   // deletes EVERYTHING every 5 min
        return true
    })
}
```
**Impact:** global rate-limit reset every cleanup tick. Sustained attacker
throughput = burst × (window / cleanup period), regardless of per-IP intent.

**Fix:** track last-access per limiter and only evict idle entries.

## 4. Cache-aside inconsistency windows (stale reads after release)

**Pattern:** hybrid repo writes DB first, then deletes cache:
```go
err := r.dbRepo.ReleaseLease(...)      // DB updated
cacheErr := r.cache.DeleteLease(...)   // cache deleted AFTER, failure only logged
```
If cache delete fails, stale entries serve until TTL. Same class for nonce
consume: DB consumed, cache delete fails → stale nonce readable.

**Audit checklist for cache-aside:**
- Is the cache write/delete failure swallowed (logged as Warn) while the
  primary op returns success? → stale-data window.
- Is the delete ordered AFTER the DB write? → classic race window.
- Does the read path fall back to DB on cache miss and repopulate? → at
  least it's self-healing; flag the TTL-bound stale window.

## 5. What the DB layer got RIGHT (don't report as findings)

Verified-safe patterns from dhcp2p's `queries.sql.go` — checking these first
avoids false positives:
- `UPDATE alloc_state SET last_token_id = last_token_id + 1 ... RETURNING`
  — atomic counter, no token_id race.
- `SELECT ... FOR UPDATE SKIP LOCKED` on expired-lease reuse — two
  concurrent allocators cannot grab the same expired row.
- `PRIMARY KEY (token_id)` — duplicate assignment impossible at INSERT.
- `UPDATE nonces SET used=true ... WHERE used=false AND expires_at>now()`
  — atomic single-use consume.
- `RenewLease`/`ReleaseLease` `WHERE token_id=$1 AND peer_id=$2` — peer_id
  comes from auth context, not request body → no direct IDOR/hijack.

**Audit order:** check DB constraints FIRST; only claim race/dup findings
if the schema lacks them.

## 6. No server-side authentication of responses (rogue-server / MITM)

**Pattern:** plain HTTP, auth is one-way (client proves identity to server;
server never proves identity to client). No response signing, no TLS pin.

**Impact:** rogue server / MITM can return any lease payload; client trusts
HTTP 200 + valid JSON. Finding holds for ANY API with this shape — check
`r.TLS != nil` guards in header middleware and absence of a response-signing
middleware.

## Audit workflow for this target class

1. Map the router: which routes are inside the auth group, which are public.
2. Read the auth service: what EXACTLY is signed? (nonce only vs full request)
3. Read the SQL: constraints, `FOR UPDATE`, atomic counters → kill false
   positives early.
4. Read the cache layer: write/delete ordering, error swallowing, TTLs.
5. Read the rate limiter: keying (per-IP? per-peer?), trusted-proxy logic,
   cleanup behavior.
6. Read the config defaults: pool size (`max_token_id`), TTLs, rate limits
   → size the starvation/exhaustion math.

## Report-format note (multi-agent red-team briefs)

When the operator assigns a numbered attack-vector brief ("for each finding:
exploit steps + code lines; if it failed, say why"), the expected output is
per-vector verdicts with file:line citations — blocked vectors MUST name the
exact defense (constraint, lock clause, atomic op) that killed them. Blocked
is a result, not a failure.
