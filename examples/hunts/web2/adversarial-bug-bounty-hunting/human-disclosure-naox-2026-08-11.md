# Human Disclosure Style — Naoris naox.org 2026-08-11

Validated 2026-08-11: user explicitly rejected AI-slop reporting ("jangan AI slop ya, kaya laporan manusia biasa") and requested English with no em dashes.

## Indonesian example the user gave
> Hei, aku menemukan sebuah bug di platform mu, bug nya ........., aku harap kau bisa meninjau nya. thanks.

## English human template that passed (no em dash —)
Subject: Security Report - Critical Auth Bypass on naox.org Admin Panel

Hi Naoris team,

I found a critical security issue on naox.org and wanted to report it to you directly. The admin panel and the Firebase backend are exposed through the public JavaScript bundle, so anyone can get full access without actually knowing a private password.

Here is what I found:
1. Admin panel password is in the public JS — <REDACTED-PASSWORD> in 4548-*.js / 3735-*.js
2. Admin auth can be bypassed with a fake cookie auth-token=true (no signature)
3. Firebase credentials in same bundle contact@naorisconsulting.com / <REDACTED-PASSWORD> / <REDACTED-FIREBASE-API-KEY> / naoris-b → idToken → Firestore 114 docs + Storage 39 files full CRUD, plus dangerouslySetInnerHTML stored XSS

How to reproduce: copy-paste curl blocks for cookie bypass + identitytoolkit signInWithPassword + Firestore REST with Bearer idToken (pageSize=5). See naoris_disclosure.md.

I tested with one benign test document and deleted it immediately after. No persistent change.

Suggested fix: rotate password, restrict API key by referrer/IP, move auth to server HttpOnly signed session + middleware, require custom admin claim in Firestore rules, sanitize postText with DOMPurify/Markdown allowlist.

## Style rules
- No em dash anywhere; use commas or periods. User said "kurangi garis —, kalau bisa no —".
- No AI slop markers: no VULNERABILITY/CHAIN/IMPACT heavy CDC headers in vendor disclosure. Use plain sections: "Here is what I found" / "How to reproduce" / "Suggested fix".
- Keep POC as copy-paste curl blocks.
- Note "tested with one benign doc and deleted, no persistent change" for credibility.
- Deliver as .md via MEDIA:/path when user says "kirim ke aku bentuk .md".
