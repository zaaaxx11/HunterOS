# APIKU funnel: https vs http:20128 (2026-08-15)

## User report
"itu pake funnel, kalo url tertulisnya ini: http://<internal-endpoint>:20128/v1"
`cek model` showed provider `meta-ai` active; user said APIKU not visible in Telegram `/model` picker.

## Diagnosis steps

1. `cat ~/.hermes/config.yaml` showed:
   - `custom_providers: [{name: APIKU, base_url: https://<internal-endpoint>/v1, api_key: <redacted>}]`
   - `providers.APIKU: {base_url: http://<internal-endpoint>:20128/v1, api_key: <redacted> truncated, models: 28}`
2. `get_compatible_custom_providers()` merges both sections; dedup key is `(provider_key,(name,base_url,model))` lowercased — `https://.../v1` vs `http://...:20128/v1` counted distinct → both survived.
3. `list_picker_providers()` showed APIKU with 29 models locally (no restart) but that used explicit `models:` fallback; live `fetch_api_models` still tried to probe the configured `base_url`.
4. Live probes:
   - `curl -s -m 10 http://<internal-endpoint>:20128/v1/models -H "Authorization: Bearer $KEY"` → timeout 10s, empty, exit 0
   - `curl --connect-timeout 8 http://103.84.155.217:20128/v1/models` → `ipv4 connect timeout after 10000ms`, `TCP 20128: TIMEOUT`
   - `ping 103.84.155.217` OK (73ms), `80 OPEN`, `443 OPEN` — only 20128 closed from this VPC.
   - `curl -sk https://<internal-endpoint>/v1/models -H "Authorization: Bearer $KEY"` → `200` with `{"object":"list","data":[74 models]}` (Executor., exploit, cf/@cf/meta/...)
   - Same over raw `http.client.HTTPSConnection` → 200, 74 models.
   - `curl -sv http://<internal-endpoint>:80/` → 302 → `https://<internal-endpoint>/` (funnel terminates at 443)

Conclusion: public funnel is https 443 without port; `:20128` is Tailscale/internal (unreachable from VPS internet egress).

## Fix applied

```python
import yaml, urllib.request, json, ssl
ssl._create_default_https_context = ssl._create_unverified_context
cfg = yaml.safe_load(open('/root/.hermes/config.yaml'))
apiku = cfg['providers']['APIKU']
apiku['base_url'] = 'https://<internal-endpoint>/v1'
apiku['api_key'] = '<REDACTED-API-KEY>'  # full 35
# live models: GET /v1/models on https → 74; merge with curated 28 → 61
req = urllib.request.Request('https://<internal-endpoint>/v1/models',
  headers={'Authorization': 'Bearer <REDACTED-API-KEY>'})
j = json.loads(urllib.request.urlopen(req, timeout=10, context=ssl._create_unverified_context()).read())
live = [x['id'] for x in j['data']]
curated = ["DeepSeek-V4-Pro","Executor.","Executor_2","Hcnsec/Kimi-K2.6",...]
apiku['models'] = {k:{} for k in sorted(set(live[:60]) | set(curated))}  # final 61
cfg.pop('custom_providers', None)  # remove stale https entry with truncated key
open('/root/.hermes/config.yaml','w').write(yaml.safe_dump(cfg, sort_keys=False))
```

Verified:

```python
from hermes_cli.config import load_config, get_compatible_custom_providers
from hermes_cli.model_switch import list_picker_providers
cfg=load_config(); cp=get_compatible_custom_providers(cfg)
provs=list_picker_providers(current_provider=cfg['model']['provider'], user_providers=cfg['providers'], custom_providers=cp, max_models=80, include_moa=True)
apiku=[p for p in provs if 'apiku' in p['slug'].lower()][0]
assert apiku['api_url']=='https://<internal-endpoint>/v1' and len(apiku['models'])>=60
# → APIKU-> https://<internal-endpoint>/v1 61 models (local), 74 when live probed
```

`cat ~/.hermes/config.yaml | grep -A3 APIKU` now shows `base_url: https://<internal-endpoint>/v1` (no port).

## Remaining step

Restart from **external shell** only:

```
hermes gateway restart
# or systemctl --user restart hermes-gateway
```

Inside Telegram `hermes gateway restart` / `systemctl restart` is blocked (`Blocked: cannot restart ... from inside the gateway process`) — likewise `at`/`nohup`/`cron` wrappers for gateway lifecycle are blocked (#30719) so local list_picker test is the only in-session verification until external restart.

## Lesson

Before adding a new provider on `http://host:20128`, `grep -r host ~/.hermes/config.yaml` + `curl https://host/v1/models` vs `curl http://host:20128/v1/models` with same key — if same host with different scheme/port already exists, fix the URL in place, don't duplicate.
