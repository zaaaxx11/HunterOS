# AIOZ Proof Discipline 2026-08 — per-command stepwise + provenance honesty

## User corrections captured
- `jelasin santai` + perumpamaan warung = default for findings explainer; keep santai Indonesian analogy style
- `gausah ditambahi keterangan, cukup command dan output saja` = proof mode: raw terminal command + output + dark-bg PNG/JPG only, no narration
- `gausah terburu-buru, per command dan per output, sampe jadi root` = one probe per turn, show output before next step; don't batch 5 SSRF payloads
- `lu kasih tutor aku, ntar aku jalanin manual di laptop` = tutor mode: docker mediamtx.yml -> curl -> Shodan dork port:8554/8888 -> TARGET=IP; don't auto-scan 20 payloads
- Frustration `apa sih output nya njing` = too verbose; output is 2 files: /tmp/pwned_aioz (uid=0) + /tmp/hook.log (pwned)

## Provenance rule
- uid=0 on <redacted> is lab VPS, not AIOZ infra. Never imply lab eval = remote AIOZ root
- mediamtx RCE is PROVEN-IN-CODE (externalcmd/cmd.go:45 os.Expand + cmd_unix.go:16 shellquote.Split -> exec.Command) but PROVEN-LIVE requires 1 real DePIN IP via Shodan port:8554 mediamtx / port:8888 aioz with authorized target
- If no live IP found, report proven-in-code + local docker proof, not fabricated remote root

## SSRF classification (from rpc-proxy.aioz.services)
- Open proxy (CORS bypass): https://example.com -> Example Domain OK, api-explorer/status -> JSON OK
- Localhost/metadata: 127.0.0.1:8545/3000 -> connection refused, 169.254.169.254 -> not found, metadata.google.internal -> no such host = container empty, not WAF block

## Real APIs vs SPA decoy
- Real: api-explorer.aioz.network /api/status {"success":true}, /api/blocks, /api/transactions, /api/token/aioz/all (404 vs 200 JSON distinguishes)
- Decoy: aioz.network / wallet / bridge / explorer all /api/* -> 200 text/html <!DOCTYPE (Next.js catch-all) -> false positive in web2-deep.py
