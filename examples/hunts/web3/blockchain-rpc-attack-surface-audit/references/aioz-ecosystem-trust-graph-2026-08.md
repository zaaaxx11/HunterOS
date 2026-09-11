# AIOZ Ecosystem Trust-Graph Audit — 2026-08

Scan root: `/tmp/aioz_scan/` — 5 repos: aioz-explorer-main, w3s-gateway-main (stub), mediamtx-main, cosmos-sdk-main, ethermint-main. Output: `AIOZ_TRUST_MAP.md`.

## Per-repo anchor findings (file:line)

### aioz-explorer (Echo + CockroachDB + Cosmos key management)
- `server/main.go:179` `//e.Use(mdl.Authorize)` disabled, `197 AllowOrigins ["*"]` + `189 echo.Group("/api")` = every `/api` route unauth (except `/api/admin` BasicAuth `228` — middleware file missing from tar, creds unverifiable).
- `server/wallet/delivery/http/wallet_handler.go:28 NewWalletHandler` registers `GET /wallet/:address`, `GET /wallet/txs/:address`, `POST /wallet/contacts`, `POST /key/new|recover|encrypt|decrypt`. Each: `ioutil.ReadAll` → `json.Unmarshal` → usecase. No auth.
- `server/wallet/usecase/wallet_usecase.go:264 CreateWallet`: `bip39.NewEntropy(128)→NewMnemonic→ComputeMastersFromSeed→DerivePrivateKeyForPath→secp256k1.PrivKeySecp256k1` → `cdc.MustMarshalJSON(privKey)` + `mintkey.EncryptArmorPrivKey` → returns `KeyResponse{PrivKey,Mnemonic,PrivArmor}` pre-auth. `309 RecoverWallet`, `346 EncryptKey(cdc.UnmarshalJSON(privKey))`, `364 DecryptKey(mintkey.UnarmorDecryptPrivKey)` — oracle for brute-force.
- `server/ws/websocket.go:27 Upgrader{CheckOrigin:true}` + `server/ws/client.go:78 readPump` (no SetReadLimit) + `server/ws/hub.go:154 hub.run` appends `[]string` without cap → OOM. `MapWalletNotification` poison via `server/devices/delivery/http/device_handler.go:33/82` → Firebase push `hub.go:228`.
- Pagination `server/block/delivery/http/block_handler.go:48 QueryParam limit/offset → ParseInt` no clamp → `GetLatestBlocks`. Same in tx/msgs/wallet handlers. `wallet_handler.go:256 POST /wallet/contacts {addresses}` loops `184 wallet_usecase.go` N×2 DB queries.
- Coverage note: `server/middleware/` and `server/*/repository/cockroachdb/` absent from tar (`main.go:39 "swagger-server/middleware"` missing) — enumerated via delivery/http + domain + ws instead.

### w3s-gateway — empty tar (only README.md 1-5) = phantom dependency, no verifiable boundary. Mark as false-coverage, not LOW.

### mediamtx — `internal/conf/conf.go:123 defaultAuthInternalUsers User:"any" Pass:"" Path:""` + `internal/auth/manager.go:165 skip pass when any` → remote unauth media publish. `conf.go:338,356,388,401 AllowOrigin "*"` + `internal/api/api.go:274 middlewareOrigin` + `internal/playback/server.go:74` → CSRF. `api.go:161 /v3/config/*` PATCH/POST + `internal/core/path.go:611 ExternalCmdEnv` → runOn* shell RCE if loopback `any` creds bypassed via TrustedProxies. `servers/{rtsp,hls,webrtc,playback}/` accept TCP before auth.

### cosmos-sdk — `server/api/server.go:139 PathPrefix("/").Handler(GRPCGatewayRouter)` catch-all + `server/grpc/server.go:40,58 reflection` + `server/config/config.go:100 EnableUnsafeCORS` → CORS AllowAll path. `server/api/server.go:121 handlers.CORS`, `108 MaxBodyBytes 1_000_000`, `157 /metrics`, `24 statik` Swagger. `baseapp/abci.go:240 CheckTx / 269 DeliverTx → x/auth/ante/ante.go:25 NewAnteHandler` is sole gate.

### ethermint — `server/json_rpc.go: r.HandleFunc("/", rpcServer.ServeHTTP)` + `cors.AllowAll` when EnableUnsafeCORS. `rpc/apis.go:GetRPCAPIs` selects namespaces via `config.JSONRPC.API`. `rpc/namespaces/ethereum/eth/api.go:164 SendRawTransaction Public:true → rpc/backend/call_tx.go:102 UnmarshalBinary → BroadcastTx` unauth ingest. `rpc/namespaces/ethereum/personal/api.go:62 ImportRawKey/70 NewAccount/191 Sign → rpc/backend/sign_tx.go:104` — `Public:false` in code but public if operator includes "personal" in config. `filters/api.go eth_newFilter` Public:true → filter exhaustion. `app/ante/ante.go` + `app/app.go:602 setAnteHandler` + `call_tx.go:SetTxDefaults` + `AllowUnprotectedTxs` gate.

## Method note — incomplete tar handling
Grepping handler registration (`New*Handler` + `g.GET/POST`) recovers full route map even when repository impl is missing. Wiring in `server/main.go` (initCockroachDB url fmt, limit/burst File scan, SDK Bech32 config) traces input→transform→storage even without DB layer.
