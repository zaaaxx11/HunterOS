# Admin Panel Discovery in Lazy-Loaded Routes (July 2026 — ColibriSwap case study)

## Signal: Target Uses TanStack Start / React SSR with Route-Based Chunking

TanStack Start uses file-based routing with lazy-loaded bundles. Admin panels can be hidden in routes NOT linked in the main navigation.

## How to Discover

### Step 1: Extract All Routes from the SSR Barrier
```bash
# In TanStack Start, the streaming barrier contains the full route manifest
curl -s 'https://TARGET/' | grep -oP '\$R\[\d+\]=\{.*?\}' | head -5
# Look for route keys in the manifest: "/panel-X", "/admin", "/_dash", etc.

# Alternative: download all route bundles
for route in /admin /panel /dashboard /manage /_admin /panel-x7k9m2q3; do
  code=$(curl -s -w '%{http_code}' -o /dev/null "https://TARGET$route")
  echo "$code $route"
done
```

### Step 2: Test Non-Standard Route Patterns
```bash
# Admin panels often use:
# - Non-Standard patterns: /panel-x7k9m2q3 → random-ish suffix
# - Numeric-like paths: /cp1960, /mg004_0
# - Word variations: /dash, /panele, /_admin, /board
# - Multi-segment: /s/admin/console

# Search for admin-title patterns in HTML returned
for path in /panel /admin /manage /board /dashboard /console /webmaster; do
  title=$(curl -sL "https://TARGET$path" | grep -oP '<title>[^<]+</title>')
  [ ! -z "$title" ] && echo "$path → $title"
done
```

### Step 3: Analyze Bundle Preloads for Hidden Routes
```bash
# Every page with unique content has its own chunk
# Check if any preloaded chunk has name that doesn't match visible routes
curl -s 'https://TARGET/' | grep -oP '/assets/[a-z0-9_-]+-[A-Za-z0-9]+\.js' | sort -u | while read chunk; do
  name=$(echo "$chunk" | sed 's/.*\/assets\///; s/-[A-Za-z0-9]\+\.js//')
  # Check if this chunk name is a route
  curl -sI "https://TARGET/$name" 2>/dev/null | grep -q 'HTTP/2 200' && echo "ROUTE: $name"
done
```

### Step 4: Check Relative Robots/SEO Meta
```bash
curl -s 'https://TARGET/HIDDEN-PANEL' | grep -i 'robots'
# Look for: <meta name="robots" content="noindex, nofollow"> — intentional hiding
# Look for: <title>Admin</title> or <title>Panel</title> — admin confirmation
```

## Found Admin Panel → What to Do Next

### 1. Extract the Admin Bundle
```bash
# The page loads via a lazy chunk
curl -s 'https://TARGET/HIDDEN-PANEL' | grep -oP '/assets/[a-z0-9_-]+\.js' | sort -u | while read f; do
  curl -sL "https://TARGET$f" -o "/tmp/$(basename $f)"
done
```

### 2. Analyze the Auth Mechanism
```javascript
// Pattern: queryKey-based auth check (TanStack Server Fns)
queryKey: ["admin-me"]       // → server! function that checks if user is admin
t?.admin ? <AdminPanel/>      // → client-side gating after server verification

// Pattern: email+password login form
mutationFn: () => t({data: {email, password}})  // → direct Supabase/Privy auth

// Pattern: session-based sign out
logout → clear session → redirect
```

### 3. Identify Admin Panel Capabilities
From the admin bundle (after login):
- `queryKey=["admin-stated"]` → stats: active users, visits, swaps, providers
- `queryKey=["admin-swaps", q]` → full swap catalog with search/filter
- `queryKey=["admin-visits"]` → visitor log: path, country, session, IP hash, referrer, user agent
- `action="refresh"` → refresh order status from external provider

### 4. Post-Login Exploitation
Once admin access is gained:
- Extract all swap data: amounts, addresses, provider IDs
- Extract visitor analytics: IP addresses (hashed), geolocation, session patterns
- Potentially: modify swap statuses, refunds, rate configurations
- If ChangeNOW/HoudiniSwap API keys are accessible: **FULL PROVIDER ACCOUNT TAKEOVER**

## ColibriSwap Real-World Results (July 2026)

| Finding | Detail |
|---------|--------|
| Admin panel | `/panel-x7k9m2q3` — 200 OK, SSR renders login form |
| Bundle | `/assets/panel-x7k9m2q3-D3ybod6N.js` — 14.3KB |
| Auth mechanism | Email + password → TanStack server fn → Supabase JWT |
| Login endpoint | Via TanStack `f(g)` mutation — can't call directly (SSR gating) |
| Post-login tabs | Swaps, Visitors, Stats (4 channels: provider 7d, route 7d) |
| Swaps display | Provider order IDs, statuses, sender/receiver/confidence, tx hashes, amounts |
| Risk: brute-force | No CAPTCHA, no MFA, no rat limit visible in client-side code |
| Risk: credential leak | Admin panel accessible to any authenticated admin user |