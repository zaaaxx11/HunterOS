# Viction Web2 Findings — 2026-08-16

## Ghost CMS API Key Exposure

**Endpoint:** `https://tomochain.ghost.io/ghost/api/content/`
**Key:** `34907de7e6a16b2316b34188be` (Content API key, read-only)

**What it grants:**
- Read all 110+ blog posts
- Read author names (no email exposed)
- Read pages, tags, settings
- **Cannot:** Login, edit, delete, create users

**Verification:**
```bash
curl "https://tomochain.ghost.io/ghost/api/content/posts/?key=34907de7e6a16b2316b34188be"
# Returns 110 posts, author "Viction" (no email)
```

**Impact:** MEDIUM — Info disclosure, enables spear-phishing (author names known), but NOT direct admin takeover.

**Mitigation:** Revoke key, generate new one in Ghost admin panel.

---

## CORS Misconfigurations

### 1. gov-api.viction.xyz — Wildcard CORS

```bash
curl -sI -H "Origin: https://evil.com" https://gov-api.viction.xyz
# Access-Control-Allow-Origin: *
```

**Impact:** MEDIUM — Any website can make authenticated requests if user has session cookies.

### 2. stats.viction.xyz — Credentials + Reflect Origin

```bash
curl -sI -H "Origin: https://evil.com" https://stats.viction.xyz
# Access-Control-Allow-Origin: https://evil.com
# Access-Control-Allow-Credentials: true
```

**Impact:** HIGH — Session hijack possible if admin visits malicious page.

---

## Subdomain Takeover

**Dead subdomains (no CNAME, potential takeover):**
- `app.viction.xyz`
- `wallet.viction.xyz`
- `bridge.viction.xyz`
- `api.viction.xyz`

**Impact:** LOW — DNS records exist but no hosting. If Viction uses CDN (Cloudflare), takeover may not be possible.

---

## Swagger UI Exposure

**Endpoint:** `https://gov-api.viction.xyz/api-docs/`

**Status:** HTML-only (no JSON spec exposed)
**Impact:** LOW — API documentation visible, but no exploitable spec.

---

## Wallet Address Leakage

**RPC Method:** `eth_accounts`
**Result:** `0x3e03bc621579b2cc6b9d2aeb2691896471ccf905`

**Impact:** LOW — Wallet address visible, enables targeting/phishing.

---

## Summary

| Finding | Severity | Takeover Possible? |
|---------|----------|-------------------|
| Ghost Content API key | MEDIUM | ❌ No (read-only) |
| CORS wildcard (gov-api) | MEDIUM | ⚠️ Conditional (needs admin session) |
| CORS credentials (stats) | HIGH | ⚠️ Conditional (needs admin session) |
| Subdomain takeover | LOW | ❌ No (Cloudflare) |
| Swagger UI | LOW | ❌ No |
| Wallet address leak | LOW | ❌ No |

**Overall:** No direct admin takeover via web2. Findings enable reconnaissance + phishing, not technical exploitation.
