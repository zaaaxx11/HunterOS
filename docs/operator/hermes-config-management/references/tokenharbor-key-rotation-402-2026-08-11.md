# TokenHarbor Key Rotation 402 — 2026-08-11 Evening

## Context
User rotated TokenHarbor API key at 2026-08-11 03:07 CST:
- Old: `<redacted>` — worked for `kimi-k3`, `gpt-5.6-sol/terra/luna` via curl + hermes (`hermes -m kimi-k3 --provider tokenharbor -z` OK)
- New: `<redacted>` — config updated correctly (`providers.tokenharbor.api_key` matches), but live test shows regression

## Live Test Results (new key, 2026-08-11)
```
curl -s https://tokenharbor.ai/v1/models -H "Authorization: Bearer $NEW_KEY" → 200, 21 models (same list)
curl POST /v1/chat/completions model=kimi-k3      → 402 We can't serve our models on this account right now. (code TH-JAWFH4Q9)
curl POST model=kimi-k3:free                      → 402 TH-JAWFH4Q9
curl POST model=gpt-5.6-sol                       → 402 TH-JAWFH4Q9
curl POST model=th-orchestra                      → OK (choices with reasoning_content)
hermes -m kimi-k3 --provider tokenharbor -z       → HTTP 402 TH-JAWFH4Q9
hermes -m gpt-5.6-sol --provider tokenharbor -z   → HTTP 402 TH-JAWFH4Q9
```

Old key pattern was identical except code TH-HPQK7K8Q (earlier session). New key hits same 402 but only th-orchestra passes.
GET /models always 200 — so base_url + api_key wiring is correct. POST /chat is account-level gating.

## Diagnosis
- NOT a config bug (providers map, api_mode: openai_chat, base_url correct)
- NOT a ghost model (`gpt-5.6` already removed earlier; tested models are all live)
- IS account suspension / quota / confidence-level gating — requires Discord verification at https://discord.gg/uBTckEReb5 with code TH-JAWFH4Q9 (or TH-HPQK7K8Q for old key)
- Key rotation does NOT fix 402; both keys hit same gating. Do NOT rotate again as fix.

## Action for Agent
1. Verify wiring: `curl -s https://tokenharbor.ai/v1/models -H "Authorization: Bearer $KEY"` must return 200 with `kimi-k3` etc.
2. If 402 with TH-... code, tell user to join Discord and send code. Keep provider in config, do not delete.
3. Suggest fallback: use `th-orchestra` for now (only model passing) or switch provider (APIKU, hcnsec, dashscope-intl).
4. Config file already correct — no edit needed. Confirm with `grep -A3 tokenharbor ~/.hermes/config.yaml` with wide context (api_key visible per user preference).

## Related
- Pitfall row "TokenHarbor 402 confidence_level_required" in SKILL.md
- Previous file: references/tokenharbor-2026-08-11-ghost-model.md
