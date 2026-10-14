# Custom Provider Configuration — Hermes Agent

## Adding a Custom Provider (List-Append Pattern)

Hermes's `custom_providers` config is a **YAML list**, not a map. `hermes config set custom_providers.NAME.key` fails because NAME is treated as a numeric list index.

### Working Method: Python YAML Manipulation

```bash
cd ~/.hermes && python3 << 'PYEOF'
import yaml

with open('config.yaml') as f:
    cfg = yaml.safe_load(f)

# Check existing providers
print("BEFORE:", cfg.get('custom_providers', []))

# Append new provider
new_provider = {
    'name': 'provider_name',        # e.g. 'makora'
    'base_url': 'https://api.example.com/v1',
    'api_key': 'sk-...',
    'model': 'org/model-name'        # e.g. 'moonshotai/Kimi-K3'
}

if 'custom_providers' not in cfg:
    cfg['custom_providers'] = []
cfg['custom_providers'].append(new_provider)

with open('config.yaml', 'w') as f:
    yaml.safe_dump(cfg, f)

print("AFTER:", cfg['custom_providers'])
PYEOF
```

### Usage After Adding

```bash
# Verify
hermes config get custom_providers.1.name
hermes config get custom_providers.1.base_url
hermes config get custom_providers.1.model

# Use in chat
hermes chat --provider custom:provider_name --model full/model-id -q "prompt" --quiet
```

### Pitfall: `hermes config set` fails on list entries

`hermes config set custom_providers.makora.base_url "https://..."` throws:
```
TypeError: Cannot navigate into list at key 'custom_providers.makora.base_url': 
segment 'makora' is not a numeric index
```

This is because custom_providers is a YAML list, not a map. Numeric indices like `custom_providers.1.name` can work IF the index already exists — but you cannot create new entries this way. Always use the Python YAML append method for new providers.

## Makora Provider Example (2026-07-29)

```
Provider: custom:makora
Base URL: https://inference.makora.com/v1
API Key:  <REDACTED-API-KEY>...
Model:    moonshotai/Kimi-K3
Context:  1,048,576 tokens

Sample models:
  - moonshotai/Kimi-K3 (1M context, text+image, tools, reasoning, $0.003/$0.015)
  - moonshotai/Kimi-K2.7-Code (262K, text+image, tools, FP4 quantization)
  - deepseek-ai/DeepSeek-V4-Pro (1M context, tools, reasoning)
  - deepseek-ai/DeepSeek-V4-Flash (1M context)
  - zai-org/GLM-5.2-FP8 (980K context)
  - zai-org/GLM-5.2-NVFP4 (1M context)