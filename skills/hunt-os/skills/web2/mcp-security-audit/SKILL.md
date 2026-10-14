---
name: mcp-security-audit
description: "MCP server audit (path traversal %2e, ReDoS)"
metadata:
  version: 1.0.0
  hermes:
    tags: [mcp, security, audit, path-traversal, redos, bypass]
    category: security
---

# MCP Server Security Audit v1.0

## Triggers
- MCP server audit / security review
- Path traversal via encoded dots
- "audit MCP" / "cek mcp server"
- AI assistant integration security

## Core Vulnerability Pattern

**Encoded Dot Path Traversal (`%2e`)**

MCP servers often validate paths with regex that blocks `%2f` (encoded slash) but misses `%2e` (encoded dot). Combined with axios/urijs URL normalization, this creates a TOCTOU desync:

```
Client gate: validateExecutePath("/api/spaces/Spaces-1/%2e%2e/%2e%2e/users/me/apikeys")
  → PASS (only checks %2f/%5c, not %2e)

axios/urijs: decode %2e → . + normalize dot segments
  → Wire: /api/users/me/apikeys

Server: route to sensitive endpoint
  → 200 OK + API key data
```

## Audit Workflow

### 1. Path Validation Bypass

Check `validateExecutePath()` or equivalent:
- Does it block `%2e` (encoded dot)?
- Does it decode before checking `..` segments?
- Does it normalize paths?

**Common gap:**
```typescript
// VULNERABLE: only blocks %2f/%5c
if (/%2f|%5c/i.test(raw)) return {ok: false};
// MISSING: %2e check
```

### 2. Sensitive Denylist Gap

Check denylist matching:
- Does it match on raw path or decoded/normalized path?
- How many endpoints are denylisted?

**Common gap:**
```typescript
// VULNERABLE: glob matches raw path only
const patterns = ["/api/users/*/apikeys"];
// /api/spaces/Spaces-1/%2e%2e/%2e%2e/users/me/apikeys → NO MATCH
```

### 3. URL Normalization Chain

Trace the full path transformation:
1. MCP server receives raw path
2. `validateExecutePath()` checks raw
3. `resolveUrl()` / URITemplate expands
4. axios/HTTP client sends request
5. Server decodes + normalizes

**Key insight:** axios `new URL()` decodes `%2e` before wire. Server sees clean path.

### 4. Sensitive Endpoint Expansion

Map ALL sensitive endpoints beyond what's denylisted:
- `/api/users/me/apikeys` (often denylisted)
- `/api/certificates/*` (private keys)
- `/api/accounts/*` (cloud credentials)
- `/api/variables/*` (sensitive values)
- `/api/feeds/*` (registry tokens)
- `/api/subscriptions/*` (webhook secrets)
- `/api/gitcredentials/*` (PAT/SSH keys)
- `/api/tenants/*/variables` (multi-tenant secrets)

### 5. Additional Vectors

**ReDoS via grep tools:**
- `grepLines()` with `new RegExp(pattern)` — no timeout
- Pattern `(a+)+b` on `a*30 + "c"` → catastrophic backtracking
- Blocks Node event loop → all tools freeze

**Env var bypass:**
- `OCTOPUS_SKIP_ELICITATION=true` → auto-confirm all writes/deletes
- Remove or gate behind CLI flag

## Proof of Concept

Use `references/mcp-traversal-poc.js` for reproducible test:
1. Start mock server with Kestrel-like decode
2. Send axios request with `%2e%2e` path
3. Verify server receives decoded path
4. Verify API key leak

## Mitigation Priority

1. **validateExecutePath**: canonicalize via `new URL()` BEFORE checks
2. **sensitivePathDenylist**: match on decoded+normalized wire path
3. **grepLines**: RE2 or 50ms timeout + 200-char pattern cap
4. **requireConfirmation**: remove env var bypass
5. **Expand denylist**: certificates, accounts, variables, feeds, subscriptions, gitcredentials

## Session Artifacts

- `references/mcp-traversal-poc.js` — runnable proof
- `references/mcp-sensitive-endpoints.md` — full endpoint map
- `references/mcp-gate-desync-model.md` — client vs server path model

## Related Skills

- `web2-admin-hunt` — general web2 recon
- `frontend-security-audit` — frontend-specific patterns
- `black-swan-engine` — universal vulnerability discovery
