# CSRF-Hardened NextAuth Pivot (2026-07-29)

When a saved PoC chain worked (signup → auto-login → admin RSC leak) but live re-verification shows CSRF hardening has shut down the credential callback, the old curl-only path is dead. The open-signup class is still alive — you need a new escalation vector.

## Pivot Options (in efficiency order)

1. **Browser Automation (Playwright)** — navigate the actual signup + login flow with a real browser session. The browser naturally handles CSRF tokens and redirects. This is the most direct pivot since the only thing blocking curl is CSRF validation.

2. **CSRF Token Race** — if the CSRF token is short-lived (< 5 min), race signup + callback in the same session window by fetching the signin page, extracting the CSRF cookie, and using it in the same sub-second window.

3. **NEXTAUTH_SECRET Leak** — if the secret is found (GitHub repos, env leaks), forge a valid session token directly via JWE decryption + re-encryption, bypassing the entire auth flow.

4. **Third-Party OAuth** — if Google/GitHub OAuth is properly configured, trigger an OAuth flow with a controlled client to link a fake provider identity to the target account. But if OAuth is NOT configured (returns `Configuration` error), this is a dead end.

## Post-Patch Assessment Protocol

When you re-verify and the old chain is broken:

1. **Downgrade the finding, not the entire target.** "CRITICAL auto-login → admin RSC leak" becomes:
   - Class still open: open signup (MEDIUM — account spam, user pollution)
   - Specific chain broken: auto-login → admin RSC (was CRITICAL, now patched to MISSING)

2. **Don't delete the old PoC.** Archive it with a `PATCHED.md` note documenting: date found, date patched, what changed, and the live evidence the patch is in place.

3. **Don't waste time retrying curl headers.** One `MissingCSRF` redirect with a legitimate CSRF token is proof the server validates. 20 more attempts won't change the outcome.

4. **Document the patch mechanism.** "NextAuth no longer permits credential callback without a valid __Host-authjs.csrf-token cookie" is a useful detail for future target profiling — other NextAuth v4 instances may have the same hardening.