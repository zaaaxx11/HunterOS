# AIOZ Explorer Echo Audit — 2026-08-15 (aioz-explorer / w3s-gateway / s3-examples)

Source: `/tmp/aioz_scan/aioz-explorer-main` (server + backend), `w3s-gateway-main`, `aioz-w3s-s3-examples-main`
Archive gaps: `server/middleware/` and `server/*/repository/cockroachdb/` absent (main.go:39 import missing, tar lists incomplete). `w3s-gateway.tar.gz` = README only. No live Next.js target in scan dir.

## Route inventory (Echo)

```bash
grep -rn "New.*Handler\|g\\.GET\|g\\.POST\|g\\.PUT\|g\\.DELETE" server --include="*.go"
# server/main.go:200 g:=e.Group("/api") + 11 handler registrations
# v1:=e.Group("/api/admin"); v1.Use(mw.BasicAuth(middleware.ValidateUser)) — only admin gated
# All other groups: block, delegator, device, msgs, nodeInfo, staking, statistic, transaction, validator, wallet — pre-auth
# Swagger: e.GET("/swagger/*", echoSwagger.WrapHandler) + e.GET("/websocket", wsserver.ServeWebsocket)
```

`main.go:179-181` global auth commented out (`//auth := middleware.NewAuthRepo` / `//e.Use(mdl.Authorize)`) — intentional public explorer. Only `/api/admin/blacklist|whitelist/*` under BasicAuth (unverifiable — ValidateUser missing).

## Findings (file:line)

| ID | File:Line | Trigger | Effect | Pre-auth | Verdict |
|---|---|---|---|---|---|
| E1 | `server/ws/hub.go:154-173`, `server/ws/client.go:66-99`, `server/ws/websocket.go:30` | `GET /websocket` (CheckOrigin:true) → `{"msg_type":"wallet.subscribe","msg_data":["a"*1M]*N}` | Append unbounded `[]string` to `client.wallets/msgs`, forward to Tendermint WS; no SetReadLimit/SetMaxBytes | YES | DoS pre-auth (OOM). Fix: SetReadLimit(1<<20), MaxBytesReader, cap len 100 |
| E2 | `server/utils/blacklisting.go:17-27` | `X-Forwarded-For: 1.1.1.1, 8.8.8.8` (any request) | Takes `addrs[len-1]` as remoteIP with no trusted proxy → attacker controls remoteIP → bypass RateLimit + blacklist | YES | Pre-auth rate-limit/IP bypass |
| E3 | `server/wallet/usecase/wallet_usecase.go:351`, `server/wallet/delivery/http/wallet_handler.go:196` | `POST /api/key/encrypt {"priv_key":"<amino JSON>","password":"12345678"}` | `w.cdc.UnmarshalJSON` into `crypto.PrivKey` interface with attacker JSON | YES | DoS only. cdc= `aiozapp.MakeCodec()` registers only tendermint/PrivKeySecp256k1+ed25519 → no gadget → no RCE |
| E4 | `backend/domain/repository/walletRepo.go:37`, `backend/gob.go:129-155` | Internal indexer Bulk UPSERT via `fmt.Sprintf("('%v','%v',%v,...)", addr, coins, ...)` | String-interpolated SQL, violates PrepareStmt | NO (not HTTP) | Code-quality. Not injectable — data is Bech32 + sdk.Coins (no `'`). Fix: `?` + Exec args |
| E5 | `server/main.go:197`, `server/ws/websocket.go:30` | `Origin: https://evil.com` | CORS `AllowOrigins:["*"]` + WS `CheckOrigin:true` | YES | Info/CSRF/pollution enabler. Fix: allowlist |
| E6 | `server/devices/delivery/http/device_handler.go:64-84`, `server/nodeInfo/delivery/http/nodeinfo_handler.go:71-90`, `server/wallet/usecase/wallet_usecase.go:184` | `POST /device/register`, `POST /node_info/update {"node_id":"x","hardware_info":...}`, `POST /wallet/contacts {"addresses":[...]}` | Unbounded write to PnTokenDevice/NodeInfo + N+1 DB queries per address (no cap) | YES | Pre-auth DB pollution / DoS. No RCE — stored as text/json, not executed |
| E7 | `server/statistic/usecase/stat_usecase.go:40-65` via `domain/lcd_client.go:10` | `GET /statistic` → `lcdUsecase.Request(host,port,"GET","/minting/inflation",nil)` | Generic `Request(host,port,method,path,payload)` primitive | NO | Not SSRF — host/port from `viper lcdserver.*` config, not user input. No handler forwards user path to it |

## Triage one-liner

```bash
grep -rn "ioutil.ReadAll\|json.Unmarshal.*Request\|cdc.UnmarshalJSON\|fmt.Sprintf.*UPSERT\|AllowOrigins\|CheckOrigin\|GetRealIP\|X-Forwarded-For\|RateLimitWithConfig" server --include="*.go"
```

## Negatives (verified)

- SSTI: 0 hits for `text/template`/`html/template` — not present.
- Path traversal / file upload RCE: 0 hits for `os.Open.*user|FileHeader|SaveToFile` in server — not present.
- SSRF: no handler forwards user URL to `http.Get`/`Fetch`; LCD primitive not user-controlled.
- Hardcoded secrets: `os.Getenv("ACCESS_KEY")` pattern only (s3-examples), not hardcoded.

## w3s-gateway / s3-examples

- `w3s-gateway` no code to audit.
- `s3-examples/example-apps/file-manager/file_manager/main.py:28` regex `^[a-zA-Z0-9_-]+\.[a-zA-Z0-9]+$` blocks `../` — no traversal. Boto3 `put` only. Presigned URLs via `generate_presigned_url` — if bucket serves `*.html/*.svg` → stored XSS but no server RCE.

## Fixes

- Cap slices (100), `http.MaxBytesReader`, `SetReadLimit` on WS + all handlers.
- Trusted-proxy for GetRealIP (only trust XFF if RemoteAddr in proxy CIDR).
- `CreateInBatches` / `Exec("UPSERT ... VALUES(?,?,?)", args...)` instead of Sprintf.
- Allowlist CORS origins, remove WS `CheckOrigin:true`.
- Gate `/device/*`, `/node_info/update`, `/key/*` if not intended public; disable `/swagger/*` in prod.
