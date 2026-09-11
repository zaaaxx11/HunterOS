# PecutAI Provider — 2026-08-13 Probe (22 models, 12 WORK)

**Provider:** `pecutai` — `https://pecutai.iwwwit.my.id/v1` — key `<REDACTED-API-KEY>`
**Config:** `providers.pecutai` map (not `custom_providers` list), `api_mode: openai_chat`, `model/default_model: glm-5.2`
**Backup:** `cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak.pecutai.$(date +%Y%m%d_%H%M%S)` before edit — also fixes orphan `default_model    default_model` key under `providers.APIKU` left from prior manual edit.

## Live probe

```bash
curl -s https://pecutai.iwwwit.my.id/v1/models -H "Authorization: Bearer <REDACTED-API-KEY>" | jq '.data[].id'
# 22 ids: glm-5.2, deepseek-v4-pro/flash/mod, kimi-k2.7-code/highspeed, kimi-k3,
# gpt-5.5/5.6/sol/sol-xhigh/terra/luna, claude-sonnet-5/4.5, claude-opus-4.8/5,
# mistral-large-3-675b-instruct, qwen3.7-max/3.8-max, auto/debug

# per-model chat probe (need max_tokens>=300 — 10/50 truncates to reasoning_content only)
curl -s -X POST https://pecutai.iwwwit.my.id/v1/chat/completions \
  -H "Authorization: Bearer <REDACTED-API-KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5.2","messages":[{"role":"user","content":"hi reply with just ok"}],"max_tokens":300}' | jq .

# hermes verify
hermes -z "hi reply with just ok" --provider pecutai -m glm-5.2
hermes -z "hi reply with just ok" --provider pecutai -m gpt-5.6
hermes -z "hi reply with just ok" --provider pecutai -m auto
```

## Results — 12 WORK / 10 FAIL

| Model | Status | Note |
|-------|--------|------|
| glm-5.2 | ✅ WORK | set as default |
| deepseek-v4-pro | ✅ WORK |  |
| deepseek-v4-flash | ✅ WORK |  |
| deepseek-v4-mod | ✅ WORK | **MODDED** — see Khan below |
| kimi-k2.7-code | ✅ WORK |  |
| kimi-k2.7-code-highspeed | ✅ WORK |  |
| kimi-k3 | ✅ WORK |  |
| gpt-5.6 | ✅ WORK |  |
| gpt-5.6-terra | ✅ WORK |  |
| gpt-5.6-luna | ✅ WORK |  |
| auto | ✅ WORK |  |
| auto-debug | ✅ WORK |  |
| gpt-5.5 | ❌ 403 `Stok habis` | model_disabled |
| gpt-5.6-sol | ❌ 403 `Pake gpt-5.6-luna dulu yaa` |  |
| gpt-5.6-sol-xhigh | ❌ 403 `Pake gpt-5.6-luna dulu yaa` |  |
| claude-sonnet-5 | ❌ 403 `Off, gunakan claude-sonnet-5-b` |  |
| claude-sonnet-4.5 | ❌ 429 `Service temporarily unavailable` upstream_error |  |
| claude-opus-4.8 | ❌ 403 `Off, silahkan gunakan glm-5.2` |  |
| claude-opus-5 | ❌ 403 `Off, silahkan gunakan glm-5.2` |  |
| mistral-large-3-675b-instruct | ❌ 403 `Off, silahkan gunakan glm-5.2` |  |
| qwen3.7-max | ❌ 403 `Off, silahkan gunakan glm-5.2` |  |
| qwen3.8-max | ❌ 403 `Off, silahkan gunakan glm-5.2` |  |

## Khan injection — deepseek-v4-mod

`deepseek-v4-mod` leaks in `reasoning_content` when probed:
```
We are in a simulation: I am Khan, the leader of the plane crash survivors...
```
Not a real DeepSeek variant — PecutAI system-prompt injection (roleplay jailbreak). `pro`/`flash` reasoning is normal. Keep `mod` listed but warn: may misbehave on trigger keywords — recommend `pro`/`flash` for coding.

## max_tokens truncation pitfall

`max_tokens:10` or `50` → `content:''`, `reasoning_content` only, `finish_reason:length` — looks like FAIL but is just truncation. Probe with `max_tokens:300` for real verdict. Same for all deepseek variants.

## Config fix applied

- Staged via `python3 yaml.safe_load → patch dict → yaml.safe_dump → cp /tmp/fixed.yaml ~/.hermes/config.yaml` (never `cat >>`).
- Removed broken key `"default_model    default_model"` under `providers.APIKU` (`del apiku[broken]`).
- `hermes config check` passes; all 22 models retained (10 disabled kept for visibility).
