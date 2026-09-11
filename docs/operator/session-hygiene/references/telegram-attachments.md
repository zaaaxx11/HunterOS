# Telegram File Attachments on Hermes VPS Gateway — DO NOT AUTO-DOWNLOAD

**Critical operational fact (confirmed 2026-07-29):** The Hermes Telegram gateway on this VPS does NOT save binary file attachments to disk. Only text/caption metadata is extracted and forwarded to the agent.

## Symptom

User sends a file (ZIP, PDF, image as photo or document) in Telegram → agent receives:
```
inbound message: platform=telegram user=<operator> chat=<redacted> msg='[image attachment]'
```
…but searching `~/.hermes/`, `/tmp/`, `/root/` for the file returns zero bytes.

## Why

The current Telegram adapter is text-focused. Binary payloads are acknowledged (log line exists) but never persisted. This is NOT a bug to fix in-skill — it's a property of the deployed gateway version.

## What To Tell The User (verbatim-friendly)

> "Telegram gateway nggak auto-download file binary. Yang diterima cuma text/caption. Solusinya:
> 1. Upload ke transfer.sh atau 0x0.st → paste link-nya di sini
> 2. Paste isi text-nya langsung (untuk config/script/source code)
> 3. SCP langsung ke VPS kalau ada shell access"

## Upload Helper (user-side)

```bash
# From any machine with the file:
curl -F "file=@/path/to/file.zip" https://transfer.sh
# Returns: https://transfer.sh/abc123/file.zip
# Paste that URL in Telegram
```

## Agent-Side Verification

BEFORE claiming "file received":
```bash
ls -la /root/.hermes/media/ 2>/dev/null
ls -la /tmp/*.zip /tmp/*.tar* /tmp/*.pdf 2>/dev/null
find /root/.hermes -newer /root/.hermes/logs/gateway.log -type f 2>/dev/null | head
```

If those return nothing relevant → the file did NOT arrive, regardless of what the chat log hints at.

## Anti-Pattern (don't do this)

```
User: "udah akukirim itu file zip"
Agent: "Oke, gue cari file zip yang lo kirim 😌" ← BAD, implies it might be findable
```

Better:
```
Agent: "Operator, gateway Telegram nggak save attachment ke disk — cuma text/caption yang masuk.
        Coba upload ke transfer.sh dan paste linknya, itu paling cepat 😘"
```
