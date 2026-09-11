# Stress 2026-08-11 03:44 — hcnsec Kimi-K2.6 wins, APIKU JSON corrupt

Source: /tmp/stress.log (sequential ping + concurrent x3 per provider, max_tokens 80-120, timeout 20s, prompts: "pong"/code/reason)

## Setup
- Providers tested: hcnsec (DeepSeek-V4-Pro, Kimi-K2.6, glm-5.2), APIKU (Executor_2, Hcnsec/DeepSeek-V4-Pro via <internal-endpoint>)
- Base: hcnsec https://api.hcnsec.cn/v1 , APIKU https://<internal-endpoint>/v1 (443, key <redacted>)
- http://<internal-endpoint>:20128/v1 : Network unreachable (0 bytes, curl timeout 8s) — not a public endpoint

## Results

| provider/model | ping single | concurrent x3 | verdict |
|---|---|---|---|
| hcnsec/Kimi-K2.6 | ✅ 4.12s tok61 stop pong | 2/3 @9.69s avg (9.65, 9.73, timeout 20.07) | **WINNER — fastest single** |
| hcnsec/DeepSeek-V4-Pro | ✅ 15.28s tok45 | 2/3 @6.65s avg (6.60, 6.70, timeout 20.37) | stable fallback, 3.7x slower single |
| hcnsec/glm-5.2 | ❌ 0/3 timeout 20.04-20.09s | 0/3 | DOWN |
| APIKU/Executor_2 | ❌ Extra data: line1 col984 / 977 / 1241 ; conc: All fusion panel models failed / Extra data 772/808 | 0/3 | **JSON corrupt — fusion proxy double-writes SSE** |
| APIKU/Hcnsec/DeepSeek-V4-Pro | ❌ timeout 20.43 + Extra data 938/1025 | — | same proxy |

## APIKU failure mode (repro)
```
POST /v1/chat/completions {"model":"Executor_2",...}
-> HTTP 200 but body is concatenated JSON + SSE:
{"id":"...","choices":[{"finish_reason":"stop"}]}data: [DONE]
-> response.json() -> json.decoder.JSONDecodeError: Extra data: line 1 column 984 (char 983)
```
GET /v1/models still OK (70 models). Indicates upstream fusion panel broken, not key.
Executor. requires exact trailing dot; Executor_2 is alias to kat-coder-pro-v2.5 internally (observed when it did work earlier returns model kat-coder-pro-v2.5).

## Ranking for hacking (prefer executor)
1. hcnsec/Kimi-K2.6 — keep as default while APIKU unstable (4s vs 15s, best under conc)
2. hcnsec/DeepSeek-V4-Pro — fallback
3. APIKU/Executor_2 only if `curl -s POST ... | python3 -m json.tool` parses without Extra data

## Action taken
- Did NOT patch config.yaml to Executor — kept hcnsec primary.
- Added to PITFALLS table in SKILL.md (Stress-test 2026-08-11 row).

## Repro script
See /root/stress_test_providers.py (sequential 3 prompts + ThreadPoolExecutor x3, 20s timeout).
Log at /tmp/stress.log (21 lines at kill, full at /tmp/stress.log).

## Related
- provider-worth-ranking-2026-08-11.md (6-provider health check earlier same night, same conclusion: hcnsec most stable)
- duplicate-provider-20128-check.md (port 20128 unreachable)
