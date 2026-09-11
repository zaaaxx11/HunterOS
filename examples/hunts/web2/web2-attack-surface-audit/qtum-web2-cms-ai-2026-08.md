# Qtum Web2/CMS/AI-API Findings — 2026-08
**Skill:** web2-attack-surface-audit. Live-verified, no auth on any.

## AI inference API with zero auth (qtum.ai, Express behind CF)
SPA served by Express (`x-powered-by: Express`), all unknown paths fall back to index.html (SPA trap — check content-type, not 200). Real API routes:
- `POST /api/ollama/chat` — model `gpt-oss:20b` live (all others 404). Streams SSE. Leaks raw `thinking` field (chain-of-thought). No auth, no rate limit.
- `POST /api/tts/synthesize` — `{text}` → real WAV bytes. Command-injection in `text` (`";id#`, `` `id` ``, `$(id)`, `|id`) all sanitized to audio (no exec). Extra params (`voice`, `output_file`, `filename`, `path`) ignored.
- `POST /api/process-file` — multipart `file`. Parses PDF/PNG/DOCX server-side, returns base64/extracted. XXE blocked by xmldom (entity not resolved). 50k×50k PNG bomb → worker timeout (60s) not crash. Traversal filename → 500 but no write. No auth.
- `POST /api/fooocus/generate` — image gen. Backend Forge 503 (offline) at time of test. Accepts `input_image`/`image_prompt`/`output_filename` — UNTESTED SSRF/file-write because backend down. Re-test when Forge is up.
- `GET /api/generation/progress/<generation_id>` — SSE. `generation_id` = `gen_<unix_ms>_<rand8>` (predictable). **IDOR**: no ownership check → iterate timestamps to spy on other users' prompts/outputs.
- `GET /api/health` — leaks unix socket path `/tmp/qtumai.sock`.

## Custom Next.js CMS (cms.qtum.org, Next.js 15.5.9 + NextAuth credentials)
- `GET /api/articles?published=false` — **unpublished draft leak** pre-auth (2 internal drafts recovered). Dashboard JS does `fetch("/api/articles?published=false")`; the param works for anyone.
- `GET /api/media` — 38 files + uploader user IDs, no auth.
- `GET /api/health` — env, uptime, redis status, memory.
- `GET /api/auth/providers` — leaks internal `http://localhost:3001` URLs (NEXTAUTH_URL misconfig).
- `GET /api/auth/signin?callbackUrl=https://evil.com` — 302 reflects external callbackUrl → open-redirect primitive.
- All write endpoints (POST/PUT/DELETE) correctly 401. Next.js 15.5.9 → CVE-2025-29927 (middleware bypass) PATCHED. RSC has no `$ACTION_ID`. No user enum (uniform CredentialsSignin error). bcrypt → brute-force not worth it.
- `/api/users`, `/api/pages`, `/api/search`, `/api/navigation`, `/api/redirects`, `/api/cache`, `/api/debug` → 401.

## Exposed .git (snap.qtum.org, nginx)
- `/.git/HEAD`, `/config`, `/index`, `/logs/HEAD` readable (200).
- `logs/HEAD` leaks `root@host-173-201-36-78` → origin IP 173.201.36.78 (GoDaddy), bypasses Cloudflare.
- `config` leaks private repo `git@github.com:davesolation/snap.qtum.org.git`.
- `index` (v2) parses to full 32-file inventory (all static .js/.html/.css — no secrets).
- Pack files `/objects/pack/*` → 404 (GC'd), `info/refs` smart-HTTP off → NO full source recovery. Impact = info disclosure + origin-IP leak only.

## Lessons
- **Next.js RSC probe:** `GET <page> -H "RSC: 1"` returns the flight payload → reveals `static/chunks/app/<route>/...js` chunk paths. Download those to enumerate client-called API routes (`fetch("/api/...")`).
- **JS bundle recon:** grep the SPA bundle for `"/api/..."` literals to find undocumented pre-auth endpoints. qtum.ai had 4 (ollama/tts/process-file/fooocus) none linked from robots/sitemap.
- **Generation/job IDs** built as `<prefix>_<unixms>_<shortrand>` are IDOR-prone when the progress/status channel has no ownership check.
- **Git index parse:** v2 entries = 62-byte fixed + name, padded to multiple of 8. SHA from `logs/HEAD` or `packed-refs`. If pack 404s, source recovery is dead but inventory + hostname leak stands.
