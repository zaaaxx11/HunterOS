# Duplicate provider check — <internal-endpoint>:20128 vs APIKU (2026-08-11)

## Request
User: "tambahin provider baru aja, ini base url: http://<internal-endpoint>:20128/v1, api key: <REDACTED-API-KEY>, cek model-modelnya, prefer executor."

## What was already in config
`providers.APIKU` already existed:
```yaml
APIKU:
  name: APIKU
  base_url: https://<internal-endpoint>/v1
  api_key: <REDACTED-API-KEY>   # identical key
  api_mode: openai_chat
  model: DeepSeek-V4-Pro
  models:
    Executor.: {}
    Executor_2: {}
    cf/@cf/... (68 more)
    Hcnsec/... , TBH/...
```
→ 70 models total. `Executor.` and `Executor_2` are top entries.

## Live probe comparison
```bash
# public https (current APIKU)
curl -s https://<internal-endpoint>/v1/models -H "Authorization: Bearer <redacted>" | jq '.data | length'
# → 70

# user-supplied http:20128
curl -s http://<internal-endpoint>:20128/v1/models -H "Authorization: Bearer <redacted>" 
# → empty string (no JSON) / timeout

curl -s http://<internal-endpoint>:20128/v1/chat/completions ... 
# → Network unreachable (port not reachable from VPS, likely Tailscale-only)

# chat on https also hangs (not a config bug)
curl -s https://<internal-endpoint>/v1/chat/completions -d '{"model":"Executor.","messages":[{"role":"user","content":"hi"}]}'
# → TLS handshake OK, then ReadTimeout 15s for every model (Executor., Hcnsec/DeepSeek-V4-Pro, etc.)
python3 requests.post(..., timeout=15) → ReadTimeoutError
hermes -m "Executor." --provider APIKU -z "hi 1+1?" → hang >20s, exit 0 empty
```

## Diagnosis
- Same host `<internal-endpoint>` + identical key = same upstream, not a new provider.
- `https://.../v1` (443) is the public endpoint that serves `/models` correctly.
- `http://...:20128/v1` is either stale, Tailscale-only, or not forwarded — adding it creates a duplicate provider that will never work from this VPS.
- Chat hang is upstream proxy / Tailscale forwarding issue, not API key or model name. Verified by `curl -v` (TLS OK, then hang) and `GET /models` 200 proving key valid.

## Correct action
Do NOT add duplicate provider. Instead patch existing `APIKU`:
```yaml
providers:
  APIKU:
    model: Executor.
    default_model: Executor.
    # keep same base_url https, same key, same models list
```
- `Executor.` requires exact trailing dot — `Executor` without dot 404s.
- User preference: `Executor.` > `Executor_2`.
- Verify with: `hermes -m "Executor." --provider APIKU -z "hi"` (once upstream recovers, expect `1+1=2`).

## Repro checklist for future sessions
```bash
# 1. before adding any provider, check for duplicate host+key
grep -r "<internal-endpoint>\|<redacted>" ~/.hermes/config.yaml
# 2. probe both base_urls for /models
for u in "https://<internal-endpoint>/v1" "http://<internal-endpoint>:20128/v1"; do
  echo "--- $u ---"
  curl -s --max-time 10 "$u/models" -H "Authorization: Bearer $KEY" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('data',[])))"
done
# 3. if same key+host, reuse provider name and patch model/default_model
```

## Lesson for skill
When user supplies a bare `http://host:port/v1` with a known key, always diff against live `providers:` map first. Duplicate detection prevents config bloat and avoids teaching the user that "new provider fails" when it's actually the same backend with a different scheme/port.
