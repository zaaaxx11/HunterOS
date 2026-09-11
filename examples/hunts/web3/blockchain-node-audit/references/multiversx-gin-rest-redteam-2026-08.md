# MultiversX Gin REST Red-Team — Theory B (2026-08-15)

Source: `/tmp/mvx_analysis/mx-chain-go-master` (16M, master 2026-08-10) + `/tmp/mvx_analysis/mx-chain-proxy-go-master` (5.2M, 2025-10-29) → full report `/tmp/mvx_red_api.md` (34.7KB). Targets: `mx-chain-go` `facade`+`api/gin`+`api/groups`, `mx-chain-proxy-go` `api`+`data/api.go`+`process/baseProcessor.go`, `gateway.multiversx.com` (proxy v1.0).

## Route tables

**chain-go**: `api/gin/webServer.go:createGroups()` → 11 groups, all `Open=true` (`cmd/node/config/api.toml`), no `Secured` field exists:
- `/address` (16 routes: `/:address`, `/bulk` POST, `/:address/balance|username|code-hash|keys`, `/iterate-keys` POST, `/:address/key/:key`, `guardian-data`, `esdt*`, `nft`, …) — `ShouldBindJSON` on `/bulk`/`/iterate-keys` (typed `[]string`)
- `/block` (5), `/internal` (17 raw/json metablock/shardblock/miniblock — should be internal but open), `/hardfork` (`/trigger` POST), `/network` (15 inc. `genesis-balances`, `gas-configs`), `/node` (15: `heartbeatstatus`, `status`, `p2pstatus`, `metrics`, `/debug` POST, `peerinfo`, `epoch-start`, `managed-keys*`), `/proof` (4), `/transaction` (8 with throttler middleware on `send|simulate|cost-scr|pool|send-multiple|:txhash`), `/validator` (2), `/vm-values` (4: `hex|string|int|query` POST), `/log` WS (`/log` GET), `/debug/metrics/prometheus` (flag), `/debug/pprof/*` (flag), CORS `*`

**proxy-go**: `data/api.go:RouteConfig{Name,Open,Secured,RateLimit}` + `cmd/proxy/config/apiConfig/v1_0.toml` — 15 packages, ~70 routes, only **4 Secured=true**: `/actions/reload-observers`, `/actions/reload-full-history-observers`, `/network/direct-staked-info`, `/network/delegated-info` (BasicAuth `gin.Accounts`+SHA256 `hasher.Compute`, `api/api.go:137-196`). Rest unauth. Versioned under `/v1.0/<pkg>`. `proof/*` `Open=false` (disabled). `swagger` `static.ServeRoot("/", "config/swagger")` if `shouldStartSwaggerUI`, pprof global `if isProfileModeActivated{pprof.Register}`.

## Gate code (single point)

```go
// chain-go: api/groups/baseGroup.go:27-93
func (bg *baseGroup) RegisterRoutes(ws *gin.RouterGroup, apiConfig config.ApiRoutesConfig) {
  for _, h := range bg.endpoints {
    props := getEndpointProperties(ws, h.Path, apiConfig) // lookup APIPackages[basePath].Routes[Name]
    if !props.isOpen { log.Debug("endpoint is closed"); continue }
    ws.Handle(h.Method, h.Path, h.Handler) // + optional throttler
  }
}
// config/config.go:575-596 ApiRoutesConfig{APIPackages map[string]APIPackageConfig{Routes []RouteConfig{Name,Open}}}

// proxy-go: api/groups/baseGroup.go:82-149
func (bg *baseGroup) RegisterRoutes(ws *gin.RouterGroup, apiConfig data.ApiRoutesConfig, auth gin.HandlerFunc, ...) {
  props := getEndpointProperties(ws, h.Path, apiConfig) // isOpen,isSecured,isFoundInConfig
  if !props.isFoundInConfig { log.Warn("endpoint not found in config"); ws.Handle(path, handler); continue } // ← FALLBACK-OPEN
  if !props.isOpen { continue }
  // isSecured → auth, RateLimit → rateLimiter
}
// proxy: if isSecured { middlewares+=auth } — only 4 routes ever hit this
```

Engine: `api/gin/webServer.go:101` `engine.Use(cors.Default())` (AllowAllOrigins:*), `api/api.go:34` same. `facade/nodeFacade.go:38-41` `DefaultRestPortOff="off"` / `DefaultRestInterface="localhost:8080"`.

## Deep dives (pre-auth, no RCE sink, VM-adjacent)

1. **`POST /hardfork/trigger`** (`api/groups/hardforkGroup.go:44-66`): `HardforkRequest{Epoch uint32, WithEarlyEndOfEpoch bool}` `ShouldBindJSON` → `facade.Trigger` → `node.DirectTrigger`. No auth, `Open=true`. Consensus halt if `RestApiInterface` binds `0.0.0.0`.

2. **`POST /node/debug`** (`api/groups/nodeGroup.go:queryDebug`): `QueryDebugRequest{Name,Search string}` → `GetQueryHandler(name).Query(search)`. Arbitrary debug handler name; unauth.

3. **`POST /vm-values/query`** (`api/groups/vmValuesGroup.go:52-134`): `VMValueRequest{ScAddress,FuncName,Args []string hex,CallerAddr,CallValue string,SameScState,ShouldBeSynced}` → `createSCQuery` hex-decodes each arg, `big.NewInt(0).SetString(CallValue,10)` no cap → `ExecuteSCQuery` runs Wasmer2 (`vmhost/contexts/runtime.go:156 StartWasmerInstance` → `wasmer2/libvmexeccapi.so`). `FuncName` not allowlisted. Same for `POST /transaction/simulate` → `SimulateTransactionExecution`. **Any VM/WASMer bug = pre-auth RCE**; fuzz hex Args + huge CallValue + SameScState.

4. **pprof/Prometheus**: chain-go `webServer.go:230-236` `if PprofEnabled(){pprof.Register}` / `if P2PPrometheusMetricsEnabled(){GET /debug/metrics/prometheus}` (flags `config/config.go:327 FacadeConfig{PprofEnabled,P2PPrometheusMetricsEnabled}`); proxy `api.go:131` global pprof. No auth. When enabled → heap/goroutine/cmdline leak + `trace?seconds` CPU burn.

5. **`GET /log` WS** (`api/gin/common.go:79-101`): `upgrader.CheckOrigin = func(r *http.Request)bool{return true}`, `logs.NewLogSender(...).StartSendingBlocking()`. Enabled by `APIPackages["log"].Routes{Name="/log",Open:true}`. Unauth log streaming.

## Proxy forwarding (SSRF check)

```go
// process/baseProcessor.go:194-304
CallGetRestEndPoint(address, path string, value interface{}) {
  req, _ := http.NewRequest("GET", address+path, nil) // address = observer.Address from NodesProvider (shard-selected)
  req.Header.Set("User-Agent", "Multiversx Proxy / 1.0.0 ...")
  httpClient.Do(req) // DefaultClient mutated globally: mutHttpClient.Lock(){httpClient.Timeout=...}
}
```
- `address` from `observer.NodesProvider` (`GetObservers`/`circularQueueNodesProvider`), not user. `path` built via `common.BuildUrlWithAccountQueryOptions` (`url.URL{Path:path}`). No user host → **no arbitrary-host SSRF**. Raw `address+path` concat (no `url.Parse`/`JoinPath`) → second-order SSRF only if observer list poisoned (requires `Secured` bypass on `/actions/reload-observers` or config write — not found). `address+path` with `//evil` still host=`obs`. Verdict: architecture finding.

## Negatives (searched, not found)

- `grep -rn "os\.Exec|exec\.Command|syscall|template\.|filepath\.|ioutil\.ReadFile|multipart\.FormFile" api/ | grep -v swagger-ui-bundle` → 0 hits (chain-go), proxy only `filepath.Join(acp.baseDir, fmt.Sprintf("%s.toml", version))` where `version` is registry (not user). No command/template/file-upload RCE sink. JSON only `ShouldBindJSON`/`encoding/json` with typed structs, `skValidator` always `return true` (dummy).

## Gateway

`cmd/proxy/config/swagger/openapi.json:5` confirms `gateway.multiversx.com` == proxy `v1.0`; same `v1_0.toml`. `api.multiversx.com` is wrapper indexer, out of scope.

## Mitigations (high-signal)

- Gate pprof/metrics behind `Secured` or `127.0.0.1`; gate `hardfork/trigger`+`node/debug`+`internal/*` with `Secured` (add field to chain-go).
- Replace `cors.Default()` with allowlist.
- Fix `!isFoundInConfig` fallback-open → default closed.
- Fuzz `vm-values`+`transaction/simulate` (Wasmer boundary).
- Validate observer `address` allowlist at load; use `url.JoinPath`.

## Full report

`/tmp/mvx_red_api.md`
