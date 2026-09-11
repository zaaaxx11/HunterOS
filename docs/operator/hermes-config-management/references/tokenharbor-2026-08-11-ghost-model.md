# TokenHarbor ghost-model diagnosis — 2026-08-11

## Symptom
User: "cek config.yaml, ada provider tokenharbor, kok gabisa ku pake, cek modelnya"
`hermes -m gpt-5.6 --provider tokenharbor -z "hi"` → `HTTP 404: Model 'gpt-5.6' is not available`

## Config before fix (`~/.hermes/config.yaml`)
```yaml
tokenharbor:
  name: tokenharbor
  base_url: https://tokenharbor.ai/v1
  api_mode: openai_chat
  api_key: <redacted>
  model: kimi-k3:free
  default_model: kimi-k3:free
  models:
    kimi-k3: {}
    kimi-k3:free: {}
    gpt-5.6-sol: {}
    gpt-5.6-terra: {}
    gpt-5.6-luna: {}
    gpt-5.6: {}          # ← ghost
    th-orchestra: {}
```

## Live check (source of truth)
```bash
curl -s https://tokenharbor.ai/v1/models \
  -H "Authorization: Bearer <redacted>" | python3 -c "import json,sys; print([m['id'] for m in json.load(sys.stdin)['data']])"
```
Response 2026-08-11: 21 ids, including `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `kimi-k3`, `kimi-k3:free`, `th-orchestra`,
`mimo-v2.5-pro`, `mimo-v2.5`, `deepseek-v4-pro`, `deepseek-v4-flash`, `gemini-3.1-pro-preview`, `gemini-3.6-flash`,
`claude-sonnet-5`, `claude-opus-5`, `claude-fable-5`, `grok-4.5`, `glm-5.2`, `qwen3.8-max`, `minimax-m3`, etc.
No bare `gpt-5.6`.

## Per-model hermes test (`hermes -m <id> --provider tokenharbor -z "hi"`)
- `kimi-k3` → OK (2 tokens)
- `kimi-k3:free` → exit 0 but empty stdout via hermes (colon breaks arg parsing) — curl OK, hermes fails
- `gpt-5.6-sol` / `terra` / `luna` → OK
- `th-orchestra` → `safety refusal` + `reasoning_content` only — virtual orchestrator (plan→build→review), not a chat model
- `gpt-5.6` → 404 model_not_found

## Root causes
1. `gpt-5.6` does not exist on TokenHarbor; only `gpt-5.6-{sol,terra,luna}` do. Any default/request with `gpt-5.6` fails 100%.
2. `kimi-k3:free` colon in YAML key/model name breaks `hermes -m kimi-k3:free` parsing (shell/hermes splits on `:`). Use `kimi-k3` as default.
3. `th-orchestra` is not usable for simple chat — user will see refusal and think provider broken.
4. Config had 7 models but live had 21 — 14 live models missing from config, so user cannot discover them.

## Fix applied (diagnosis-only session, patch proposed not auto-applied)
- Remove `gpt-5.6:` from `models:`
- Change `model:` and `default_model:` from `kimi-k3:free` → `kimi-k3`
- Optionally add missing live models (`mimo-v2.5-pro`, `deepseek-v4-pro`, `gemini-3.1-pro-preview`, `claude-sonnet-5`, `claude-opus-5`, etc.) or at least document diff.
- Verification: `hermes -m kimi-k3 --provider tokenharbor -z "jawab 1+1 berapa?"` → `1+1 = 2`, `hermes -m gpt-5.6-sol --provider tokenharbor -z "hi"` → `OK`

## Repro for future sessions
```bash
# 1. diff live vs config
live=$(curl -s https://tokenharbor.ai/v1/models -H "Authorization: Bearer $KEY" | python3 -c "import json,sys; print(' '.join(sorted(m['id'] for m in json.load(sys.stdin)['data'])))" )
cfg=$(python3 -c "import yaml; print(' '.join(sorted(yaml.safe_load(open('/root/.hermes/config.yaml'))['providers']['tokenharbor']['models'].keys())))")
echo "live: $live"; echo "cfg: $cfg"
# 2. test each
for m in kimi-k3 gpt-5.6-sol gpt-5.6; do echo "--- $m ---"; timeout 15 hermes -m "$m" --provider tokenharbor -z "hi" 2>&1 | head -n 5; done
```

## Lesson for skill
Always `GET /v1/models` with the stored key before declaring a provider broken. A single ghost entry (`gpt-5.6`) poisons the whole provider in user perception. Colon-containing model IDs need quoting in YAML and testing via both `curl` and `hermes` paths.
