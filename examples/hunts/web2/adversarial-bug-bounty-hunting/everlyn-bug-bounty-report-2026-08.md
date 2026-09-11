# Everlyn Bug Bounty Report — August 2026
## Report template, live retest workflow, and user preferences

## Finding Summary
5 issues found on everlyn.ai / vapi.everlyn.ai:
1. Admin orders page leaks customer PII (emails, plan, price, dates) without auth
2. GPU order endpoint accepts SHA-512(email) as identity — anyone can create orders
3. Order status/check_ai endpoint readable without auth (MongoDB ObjectId enumeration)
4. User history endpoint no access control
5. OpenAPI schema public (37 endpoints) + internal AWS error leak

## Live Retest Pattern (August 2026)
When retesting, always verify against live endpoints — don't assume the old PoC still works:
- Issue 1: `/api/admin/orders` now returns HTML (Next.js RSC) instead of JSON, but data is still embedded in the page source. Check `__next_f.push` payloads for order data.
- Issue 2: `/order` still accepts `user_hash = SHA-512(email)` with `credits_to_lock: 0`, `need_watermark: false`, `user_limit: 999`. Order IDs are returned as `{"order_id": "...", "message": "Ok"}`.
- Issue 3: `/check_ai/<order_id>` returns `{"video_path": null, "message": "Queuing, please wait..."}` without auth.
- Issue 5: `/openapi.json` returns all 37 endpoints including `/order`, `/check_ai/{order_id}`, `/check_discord/{order_id}`, `/stream/{order_id}`, `/discord_order`, `/api/files`.

## Report Template (for Harry)
Hi,

Yes, please send the bug report. It would be helpful to include the
steps to reproduce, expected vs actual behavior, device/browser, and
any screenshots or screen recording if available.

Best,
Harry

### Response format:
- Start with a friendly summary
- List each issue with: severity, steps to reproduce (copy-paste curl commands), expected vs actual, impact
- Include live order IDs as proof
- Suggest fixes
- Sign off professionally

## the operator Preferences
- User prefers "dummy PoC first" before live testing
- User wants copy-paste terminal commands they can run locally
- User says "kalau misal nanti output jelek aku jalanin sendiri" — offer to run live as fallback
- Use "lo/gue" casual Indonesian when chatting, but formal English for the report to Harry