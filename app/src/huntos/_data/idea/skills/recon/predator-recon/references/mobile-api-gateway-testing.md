# Mobile API Gateway Testing Methodology

## Overview
Mobile applications (iOS/Android) communicate with backend APIs through API gateways. These gateways often have different security controls than web endpoints and can expose additional attack surface.

## Discovery

### 1. App Store Intelligence
```bash
# iOS - App Store ID
# https://apps.apple.com/tw/app/coupang/id1567026344
# Bundle ID: com.coupang.mobile.lightspeed

# Android - Play Store
# https://play.google.com/store/apps/details?id=com.coupang.mobile.lightspeed
# Package: com.coupang.mobile.lightspeed
```

### 2. Certificate Pinning Check
```bash
# Test if certificate pinning bypass is needed
curl -k --proxy http://burp:8080 https://api-gateway.tw.coupang.com
# If fails with SSL error → certificate pinning active
```

### 3. Network Traffic Analysis
```bash
# Use mitmproxy/burp with mobile device
# Export CA cert to device, configure proxy
# Capture all API calls during app usage
```

## API Gateway Endpoints

### Common Patterns
| Endpoint Type | Path Patterns | Purpose |
|---------------|---------------|---------|
| App Config | `/v1/app/init`, `/v1/app/config`, `/config` | Feature flags, version, endpoints |
| Auth | `/api/v1/auth/token`, `/auth/login`, `/auth/register` | Login, token refresh, registration |
| Device | `/api/v1/device/register`, `/api/v1/device/verify` | Device fingerprinting, registration |
| User | `/api/v1/user/profile`, `/api/v1/user/info` | User data, preferences |
| Product | `/api/v1/product/list`, `/api/v1/category`, `/api/v1/search` | Catalog, search |
| Cart | `/api/v1/cart`, `/api/v1/cart/items` | Shopping cart |
| Order | `/api/v1/order`, `/api/v1/checkout` | Order placement |
| Payment | `/api/v1/payment/methods`, `/api/v1/payment/process` | Payment processing |

### Discovery Commands
```bash
# Root endpoint
curl -s "https://api-gateway.tw.coupang.com/"

# With mobile headers
curl -s -H "User-Agent: Coupang/2.0 (iOS 17.0; iPhone 15; Scale/3.0)" \
  -H "Accept: application/json" \
  -H "Accept-Language: zh-TW" \
  -H "X-App-Version: 2.0.0" \
  -H "X-Platform: ios" \
  -H "X-Device-Id: test-device-id" \
  "https://api-gateway.tw.coupang.com/"

# Common paths
for path in /v1/app/init /v1/app/config /api/v1/app/init /api/v1/config /config /version /health /ready; do
  echo "Testing $path..."
  curl -s -H "User-Agent: Coupang/2.0 (iOS 17.0)" "https://api-gateway.tw.coupang.com$path"
done
```

## Mobile-Specific Headers

### iOS
```http
User-Agent: Coupang/2.0 (iOS 17.0; iPhone 15; Scale/3.0)
Accept: application/json
Accept-Language: zh-TW
X-App-Version: 2.0.0
X-Platform: ios
X-Device-Id: <UUID>
X-Device-Model: iPhone15,2
X-OS-Version: 17.0
```

### Android
```http
User-Agent: Coupang/2.0 (Linux; Android 14; Pixel 8)
Accept: application/json
Accept-Language: zh-TW
X-App-Version: 2.0.0
X-Platform: android
X-Device-Id: <ANDROID_ID>
X-Device-Model: Pixel 8
X-OS-Version: 14
```

## Testing Checklist

### 1. Unauthenticated Endpoints
```bash
# Test without any auth headers
for path in /v1/app/init /v1/config /api/v1/config /health /version; do
  curl -s -H "User-Agent: Coupang/2.0 (iOS 17.0)" "https://api-gateway.tw.coupang.com$path"
done
```

### 2. Device Registration
```bash
# Test device registration without auth
curl -X POST "https://api-gateway.tw.coupang.com/api/v1/device/register" \
  -H "User-Agent: Coupang/2.0 (iOS 17.0)" \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test-123", "platform": "ios", "model": "iPhone15,2", "os_version": "17.0"}'
```

### 3. Device Verification / Fingerprinting
```bash
curl -X POST "https://api-gateway.tw.coupang.com/api/v1/device/verify" \
  -H "User-Agent: Coupang/2.0 (iOS 17.0)" \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test-123", "fingerprint": "test-fp", "platform": "ios"}'
```

### 3. Token Refresh / Auth Bypass
```bash
# Test token refresh without valid refresh token
curl -X POST "https://api-gateway.tw.coupang.com/api/v1/auth/refresh" \
  -H "User-Agent: Coupang/2.0 (iOS 17.0)" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "invalid", "device_id": "test-123"}'
```

### 4. IDOR / BOLA Testing
```bash
# Test if user ID in path is validated
curl "https://api-gateway.tw.coupang.com/api/v1/user/profile" \
  -H "Authorization: Bearer <victim_token>" \
  -H "X-User-Id: <attacker_id>"

# Test cart/order access
curl "https://api-gateway.tw.coupang.com/api/v1/cart" \
  -H "Authorization: Bearer <victim_token>"

# Test order access
for i in {1..100}; do
  curl "https://api-gateway.tw.coupang.com/api/v1/order/$i" \
    -H "Authorization: Bearer <victim_token>"
done
```

### 5. Payment/Checkout Logic
```bash
# Test coupon/price manipulation
curl -X POST "https://api-gateway.tw.coupang.com/api/v1/checkout/preview" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"items": [{"id": "PROD123", "qty": 1, "price": 1}], "coupon": "TEST"}'

# Test payment method bypass
curl -X POST "https://api-gateway.tw.coupang.com/api/v1/payment/process" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"method": "card", "amount": 1, "currency": "TWD"}'
```

### 6. CORS / Origin Validation
```bash
for origin in "https://evil.com" "https://tw.coupang.com" "null" "file://"; do
  curl -X OPTIONS "https://api-gateway.tw.coupang.com/" \
    -H "Origin: $origin" \
    -H "Access-Control-Request-Method: POST" \
    -v 2>&1 | grep -i "access-control-allow-origin"
done
```

### 7. Rate Limiting
```bash
# Test rate limits
for i in {1..50}; do
  curl -s -o /dev/null -w "%{http_code} " "https://api-gateway.tw.coupang.com/api/v1/app/init" &
done
wait
echo
```

### 8. API Versioning
```bash
# Test multiple versions
for ver in v1 v2 v3; do
  for path in /app/init /config /health; do
    curl -s -o /dev/null -w "%{http_code} " "https://api-gateway.tw.coupang.com/$ver$path"
  done
  echo "v$ver"
done
```

## Certificate Pinning Bypass (if needed)

### Frida Script (iOS)
```javascript
// disable-ssl-pinning.js
Interceptor.attach(Module.findExportByName("Security", "SSLCreateContext"), {
  onLeave: function(retval) {
    console.log("[*] SSLCreateContext called");
  }
});

Interceptor.attach(Module.findExportByName("Security", "SSLHandshake"), {
  onEnter: function(args) {
    console.log("[*] SSLHandshake called");
  }
});

// TrustKit / Alamofire / URLSession pinning bypass
Java.perform(function() {
  var OkHostnameVerifier = Java.use("okhttp3.OkHostnameVerifier");
  OkHostnameVerifier.verify.overload('java.lang.String', 'javax.net.ssl.SSLSession').implementation = function(hostname, session) {
    console.log("[*] OkHostnameVerifier.verify called for: " + hostname);
    return true;
  };
  
  var CertificatePinner = Java.use("okhttp3.CertificatePinner");
  CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
    console.log("[*] CertificatePinner.check called for: " + hostname);
    return;
  };
});
```

### Frida Script (Android)
```javascript
// disable-pinning-android.js
Java.perform(function() {
  // OkHttp
  var CertificatePinner = Java.use("okhttp3.CertificatePinner");
  CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
    console.log("[*] CertificatePinner.check bypassed for: " + hostname);
    return;
  };
  
  // TrustManager
  var TrustManager = Java.use("javax.net.ssl.X509TrustManager");
  TrustManager.checkServerTrusted.implementation = function(chain, authType) {
    console.log("[*] TrustManager.checkServerTrusted bypassed");
    return;
  };
  
  // HostnameVerifier
  var HostnameVerifier = Java.use("javax.net.ssl.HostnameVerifier");
  HostnameVerifier.verify.implementation = function(hostname, session) {
    console.log("[*] HostnameVerifier.verify bypassed for: " + hostname);
    return true;
  };
  
  // SSLContext
  var SSLContext = Java.use("javax.net.ssl.SSLContext");
  SSLContext.init.overload('[Ljavax.net.ssl.KeyManager;', '[Ljavax.net.ssl.TrustManager;', 'java.security.SecureRandom').implementation = function(keyManagers, trustManagers, secureRandom) {
    console.log("[*] SSLContext.init called");
    return this.init(keyManagers, trustManagers, secureRandom);
  };
});
```

## Common Vulnerabilities in Mobile APIs

### 1. Broken Object Level Authorization (BOLA/IDOR)
- User ID in URL path not validated against token
- Cart/order access without ownership check

### 2. Broken Authentication
- Weak password reset flow
- Token not invalidated on logout/password change
- JWT without expiration or with weak signing

### 3. Excessive Data Exposure
- API returns more fields than UI needs
- PII in response (phone, email, address, payment info)

### 4. Lack of Rate Limiting
- Brute force on login/OTP
- Cart/checkout abuse
- Coupon enumeration

### 5. Broken Function Level Authorization
- Admin endpoints accessible to regular users
- Debug endpoints in production

### 6. Mass Assignment
- Mass assignment in profile update
- Price/quantity manipulation in cart

### 7. Security Misconfiguration
- Missing security headers
- CORS misconfiguration
- Debug endpoints enabled

### 8. Injection
- SQLi in search/filter parameters
- NoSQL injection in MongoDB-backed APIs
- Command injection in file upload

## Testing Tools

### Burp Suite Extensions
- **Mobile Assistant** - Intercept mobile traffic
- **AutoRepeater** - Retry requests with modifications
- **AuthMatrix** - Test authorization matrix
- **Bambda** - Custom analysis scripts

### Frida Scripts
- `codeshare/frida/ios-ssl-pinning-bypass`
- `codeshare/frida/android-ssl-pinning-bypass`
- `codeshare/frida/ios-keychain-dump`
- `codeshare/frida/android-keystore-dump`

### Mobile Testing Frameworks
- **objection** - Runtime exploration
- **frida** - Dynamic instrumentation
- **mobsf** - Static analysis
- **jadx** - APK decompilation

## Reporting Template

```
Title: Mobile API [Vulnerability Type] - [Impact]
Severity: [Critical/High/Medium/Low]
Platform: [iOS/Android/Both]
Endpoint: [Full URL with method]
Headers Used: [List of headers]
Payload: [Request body]
Response: [Relevant response]
Impact: [Data exposed, actions possible, users affected]
Reproduction:
1. Configure proxy on mobile device
2. Open app, navigate to [feature]
3. Capture request to [endpoint]
4. Modify [parameter] to [value]
5. Observe [impact]
Fix: [Specific fix recommendation]
```

## Coupang Taiwan Specific Findings

### API Gateway (`api-gateway.tw.coupang.com`)
- **Root**: Returns version info (nginx, build date)
- **Mobile headers**: Required for proper responses
- **Endpoints tested**: All return 404/403 except root
- **Certificate pinning**: Not tested (no auth endpoints found)

### Core E-commerce (Behind Akamai)
- **checkout.tw.coupang.com** - 403 (Akamai)
- **payment.tw.coupang.com** - 403 (Akamai)
- **cart.tw.coupang.com** - 403 (Akamai)
- **cart-front-api.tw.coupang.com** - 503 (Down)
- **All auth endpoints** - 403 (Akamai)

### Salesforce Community (Marketplace)
- **marketplace.tw.coupangcorp.com** - Live (Salesforce Siteforce)
- **REST API**: `/services/data/` accessible (guest)
- **API versions**: 31.0 - 67.0 (37 versions)
- **sobjects**: Accessible in older versions (now 401)
- **Guest user**: Can query some objects (now blocked)

### File Upload
- **fileupload.tw.coupang.com** - 403 (Akamai)
- **fileupload-video.tw.coupang.com** - 404

## Tools Used in This Assessment
```bash
# Passive recon
subfinder -d tw.coupang.com -silent
amass enum -passive -d tw.coupang.com

# Active probing
httpx -l subs.txt -title -tech-detect -status-code
katana -u https://target.com -d 3 -jc -kf

# API testing
for path in /v1/app/init /v1/config /api/v1/config; do
  curl -H "User-Agent: Coupang/2.0 (iOS 17.0)" https://api-gateway.tw.coupang.com$path
done

# Salesforce API
curl https://marketplace.tw.coupangcorp.com/tw/services/data/v59.0/sobjects/
curl "https://marketplace.tw.coupangcorp.com/tw/services/data/v59.0/query/?q=SELECT+Id+FROM+Account+LIMIT+5"
```