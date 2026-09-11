# Provider Worth Ranking — 2026-08-11 Evening (operator VPS)

All 6 providers in `~/.hermes/config.yaml` probed same night with identical `GET /models` + `POST /chat/completions` (8-15s timeout).

## Results

| Rank | Provider | base_url | /models | chat 1+1? | Verdict |
|------|----------|----------|---------|-----------|---------|
| 1 | **hcnsec** | https://api.hcnsec.cn/v1 | 22 models | ✅ DeepSeek-V4-Pro OK | **Most stable** — fallback while others flaky |
| 2 | **APIKU** | https://<internal-endpoint>/v1 | 70 models (Executor., Executor_2 top) | ⚠️ intermittent ReadTimeout 15s — Executor_2 > Executor. (Executor. exact dot, hangs more) | Highest ceiling (self-host, least filter) but network unstable tonight |
| 3 | meta-ai | https://api.meta.ai/v1 | 3 models | ❌ model_not_found (config DeepSeek-V4-Pro, live only muse-spark-*) | Wrong model name only |
| 4 | ainative | https://api.ainative.studio/v1 | 100 models | ❌ deepseek-v3.2 not in live | Wrong model name only |
| 5 | tokenharbor | https://tokenharbor.ai/v1 | 21 models | ❌ 402 confidence_level_required TH-HPQK7K8Q / TH-JAWFH4Q9 on kimi-k3 + gpt-5.6-* (only th-orchestra OK) | Account-level block, not config |
| 6 | dashscope-intl | https://dashscope-intl.aliyuncs.com/compatible-mode/v1 | 157 models | ❌ AllocationQuota.FreeTierOnly | Free quota exhausted |

## Same-night tokenharbor regression

- Afternoon 2026-08-11: key `<redacted>` → kimi-k3 ✅, gpt-5.6-sol ✅
- Evening 2026-08-11: **both** keys (`N3w...` and new `PYi7...`) → 402 confidence_level_required on all chat models. `/models` still 200.
- `th-orchestra` stays OK — it's a virtual orchestrator, not a real chat model.
- New key initially gave TH-JAWFH4Q9, old key TH-HPQK7K8Q — same class of block.

## Repro

```bash
# health probe per provider (8-15s timeout)
curl -s https://api.hcnsec.cn/v1/models -H "Authorization: Bearer $HCNSEC_KEY" | jq '.data | length'
curl -s -X POST https://api.hcnsec.cn/v1/chat/completions -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Pro","messages":[{"role":"user","content":"hi 1+1? short"}],"max_tokens":20}' | jq .

# APIKU
curl -s https://<internal-endpoint>/v1/models -H "Authorization: Bearer <redacted>" | jq .
# Executor. needs exact trailing dot
curl -s -X POST https://<internal-endpoint>/v1/chat/completions -H "Authorization: Bearer <redacted>" \
  -d '{"model":"Executor_2","messages":[{"role":"user","content":"hi 1+1?"}],"max_tokens":20}' --max-time 15

# tokenharbor
curl -s https://tokenharbor.ai/v1/models -H "Authorization: Bearer <redacted>" | jq '.data[].id'
curl -s -X POST https://tokenharbor.ai/v1/chat/completions -H "Authorization: Bearer <redacted>" \
  -d '{"model":"kimi-k3","messages":[{"role":"user","content":"hi"}],"max_tokens":10}' | jq .error
```

## Action

- Keep tokenharbor in config, do not delete on 402 — Discord https://discord.gg/uBTckEReb5 with TH-... code.
- Keep APIKU on https 443, do not duplicate :20128 (unreachable from VPS, Network unreachable).
- Fix meta-ai default → muse-spark-1.2, ainative → claude-3-sonnet if needed; dashscope needs payment.
- Recommended default while ranking holds: **hcnsec/DeepSeek-V4-Pro** primary, **APIKU/Executor_2** secondary.
