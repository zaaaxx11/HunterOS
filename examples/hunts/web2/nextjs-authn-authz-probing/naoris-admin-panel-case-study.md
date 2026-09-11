# Naoris Protocol — Admin Panel + Backend Leak Case Study (2026-08)

## Target: naox.org / naorisprotocol.com

## Discovery Chain
1. `GET /admin` → 307 redirect to `/admin/login`
2. `GET /admin/login` → 200 OK, 66KB HTML admin login page
3. Extracted JS chunk: `app/admin/login/page-ba7482e441033e85.js` (8.4KB)
4. JS chunk contained hardcoded backend URL: `https://naoris-backend-qxphd44csq-ew.a.run.app`
5. Auth logic extracted:
   - `POST /api/admin/login` with `{site:"protocol", password}`
   - JWT returned, stored in `auth-token` cookie
   - Client-side check: `checkAuthStatus()` parses `header.expiry.signature` from cookie
   - Server-side: `Authorization: Bearer <jwt>` validated by backend
6. Backend fingerprint: Google Cloud Run, Helmet.js, rate limit 200/900s
7. Protected endpoint: `/api/blogs` → 401 (exists, needs valid JWT)

## curl Commands

```bash
# Discover admin page
curl -sk -4 -D - https://www.naox.org/admin
# → 307 → /admin/login

# Get admin login page
curl -sk -4 -L -o admin.html https://www.naox.org/admin/login

# Extract JS chunks
grep -oE 'app/admin/[a-zA-Z0-9/_-]+\.js' admin.html

# Download admin chunk
curl -o chunk.js https://www.naox.org/_next/static/chunks/app/admin/login/page-*.js

# Extract backend URL
grep -oE 'https?://[^"'\'' ]+\.run\.app' chunk.js

# Direct backend probe
curl -X POST https://naoris-backend-qxphd44csq-ew.a.run.app/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"site":"protocol","password":"test"}'
# → {"error":"Invalid credentials"}

# Protected endpoint check
curl -H "Authorization: Bearer <token>" \
  https://naoris-backend-qxphd44csq-ew.a.run.app/api/blogs
# → 401 without valid token → endpoint exists
```

## Key Lessons
- **307 redirects are NOT a dead end** — follow them to the real admin page
- **Admin JS chunks are goldmines** — they contain hardcoded backend URLs, auth logic, endpoint paths
- **Google Cloud Run backends** — recognizable by `.run.app` domain, Helmet.js headers, rate-limit headers
- **Client-side auth check ≠ server-side auth** — the client may check cookie expiry, but the backend validates JWT signature
- **Rate-limit fingerprinting** — `/health` endpoint returns `ratelimit-policy` headers for free