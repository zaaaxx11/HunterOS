# AbeyFoundation Fuzz-Engineer Findings — Cross-Stack (2026-08-16)

Source: FUZZ-ENGINEER pass over AbeyFoundation 12 repos (go-abey 807 Go files + Safe-fork Python/TS + Dart wallet). Workspace `/tmp/abey/`. Three fuzz scripts `/tmp/abey_fuzz.py` (336L), `abey_fuzz2.py` (210L), `abey_fuzz3.py` (179L) all executed.

## Verified High-Risk Sinks

### 1. PrivateAdminAPI arbitrary file R/W — go-abey [HIGH]
`abey/api.go:328 ExportChain(file) → os.OpenFile(file,O_CREATE|O_WRONLY|O_TRUNC,0777)` + `abey/api.go:360 ImportChain(file)→os.Open(file)→rlp.NewStream→InsertChain` + `abey/api_tracer.go:383 TraceBlockFromFile→ioutil.ReadFile(file)` — zero `filepath.Clean`/prefix check, 0777 perms, gzip branch on `.gz` suffix. Gated `Namespace:"admin" Public:false` (`abey/backend.go:362`) but reachable with `--http.api admin` or `--ws.exposeall` (then `rpc.StartHTTPEndpoint` whitelist includes admin). Fuzz payloads validated: `/etc/cron.d/pwn`, `../../../../tmp/pwn`, `/proc/self/environ`, `/dev/null`, `""`, `A*5000`, `/tmp/file\x00.png`. Fix: confine to datadir (`Clean`+`HasPrefix`), 0600, IPC-only.

### 2. SSRF via tokenURI — safe-transaction-service [HIGH]
`safe_transaction_service/history/services/collectibles_service.py:219 _retrieve_metadata_from_uri` — `uri` from on-chain `tokenURI` (attacker-mintable) → `ipfs_to_http(uri)` (`urljoin(settings.IPFS_GATEWAY, uri.replace("ipfs://",""))`) → `if not uri.startswith("http"): raise` → `requests.get(uri, timeout=10, stream=True)` with no private-IP check. Verified 0 hits for `is_private|169.254|ipaddress` in file. Mitigations present: content-length ≤0.2MB, content-type must contain `application/json`, 10s timeout. Missing: RFC1918/link-local/loopback/reserved deny-list, redirect cap, DNS re-resolution. PoCs: `http://169.254.169.254/latest/meta-data/iam/security-credentials/` (IMDSv1 theft on EC2), `http://localhost:8080/admin`, `http://127.0.0.1:8545`, `http://[::ffff:127.0.0.1]/debug`, `http://0.0.0.0:5000`, `ipfs://evil.com/../../etc/passwd → https://ipfs.io/etc/passwd` (urljoin traversal verified).

### 3. pickle.loads on Redis — safe-transaction-service [MEDIUM]
`history/services/transaction_service.py:73,91` (`pickle.loads` on `redis.mget`) + `history/views.py:357,369` (`pickle.loads` on `redis.hget` → `pickle.dumps((page,count))` on `hset`). Not direct user input — requires Redis compromise/cache-poisoning. Cache key `tx-service:{safe_address}:{tx_hash}` user-influenced. Payload `pickle.dumps(__reduce__=(os.system,('id',)))` 40B verified; safe `print` demo executed via `pickle.loads`. Fix: replace with `json` or HMAC-sign blobs.

### 4. Duktape arbitrary JS fallback — go-abey [MEDIUM]
`abey/tracers/tracer.go:New(code string)` — `if tracer,ok:=tracer(code);ok{code=tracer}` whitelist (`all` map: callTracer/4byteTracer etc. from `abey/tracers/internal/tracers/*.js` 9 files) else `vm.PevalString("("+code+")")` evals raw `TraceConfig.Tracer *string` from RPC. Sandboxed globals only: `toHex,toWord,toAddress,toContract,isPrecompiled,slice` + `bigInt` lib (`EvalString(bigIntegerJS)`). No `require/os/fs/net`. Timeout `defaultTraceTimeout=5s` → `tracer.Stop`. Not host RCE, DoS/sandbox-escape. Requires `debug` module whitelisting (same gating as admin).

### 5. VHost/CORS bypass — go-abey [LOW-MEDIUM]
`rpc/http.go:244-267 virtualHostHandler.ServeHTTP` — `if r.Host=="" → allow` + `if net.ParseIP(host)!=nil → allow` (any IP including `192.168.x`, `169.254.x` bypasses), `vhosts["*"]` → allow all. `--rpcvhosts=*` disables. CORS `rpc/http.go:225 cors.New(cors.Options{})` = AllowAll when empty. Browser-only mitigation.

### 6. Dart wallet cleartext + WebView — abey-wallet-module [LOW]
`abey-wallet-module/lib/common/constant.dart: Base_Url='http://54.255.45.202:8010'` (AWS Singapore, no TLS) → MITM DApp list injection. `lib/pages/discover_search.dart` + `discover.dart` load `searchEC.text` into `CommonWebviewPage` if `startsWith("http://"/"https://")` with no allowlist. `chain_evm_util.dart`/`chain_trx_util.dart` correctly use HTTPS (sepolia-rollup, ankr).

### 7. secp256k1 unsafe.Pointer panic — go-abey [LOW]
`crypto/secp256k1/secp256.go` 8× `(*C.uchar)(unsafe.Pointer(&slice[0]))` at lines 65,71,81,103-104,106,118-120,131,134,147,150 — 4 missing `len>0` guard (71,81,103-104,120,147) → empty slice panic `index out of range` (no recover → daemon crash). Not RCE, DoS via malformed pubkey/sig.

### 8. exec.Command no-shell — go-abey [INFO]
`common/compiler/solidity.go` `exec.Command(solc,"--version")` + `cmd/internal/browser/browser.go` `exec.Command(os.Getenv("BROWSER"),url)` — `exec.Command` without `sh -c`, so `; rm` not injectable; but `--solc` flag / `$BROWSER` env = arbitrary binary if attacker controls CLI/env (requires local `gabey bug` invocation, expected).

## Repro Recipe
```bash
# clone fallback (git remote-https missing on TencentOS 4)
curl -L https://github.com/AbeyFoundation/go-abey/archive/refs/heads/main.tar.gz -o /tmp/go-abey.tar.gz && tar xzf /tmp/go-abey.tar.gz -C /tmp/abey/
curl -L https://github.com/AbeyFoundation/abey-wallet-module/archive/refs/heads/main.tar.gz -o /tmp/wallet.tar.gz && tar xzf /tmp/wallet.tar.gz -C /tmp/abey/
# sink hunt
grep -rn "os\.exec\|exec\.Command\|CommandContext" go-abey --include="*.go"
grep -rn "RegisterName\|NewServer\|ServeHTTP" go-abey/rpc --include="*.go"
grep -rn "PrivateAdminAPI\|ExportChain\|ImportChain\|TraceBlockFromFile" go-abey --include="*.go" -n
grep -rn "duktape\|Tracer:" go-abey/abey --include="*.go" -n
grep -rn "MaxMessageSize\|maxRequestContentLength" go-abey --include="*.go" -n
grep -rn "eval\|pickle\|yaml\.load\|subprocess" safe-transaction-service --include="*.py" -n
grep -rn "dangerouslySetInnerHTML\|innerHTML\|__proto__" safe-client-gateway safe-wallet-web --include="*.ts" --include="*.js" -n
# fuzz scripts
python3 /tmp/abey_fuzz.py; python3 /tmp/abey_fuzz2.py; python3 /tmp/abey_fuzz3.py
# verify SSRF gap
grep -rn "is_private\|169\.254\|ipaddress\|is_reserved" safe-transaction-service/safe_transaction_service/history/services/collectibles_service.py
# verify pickle
grep -rn "pickle\.loads\|pickle\.dumps" safe-transaction-service --include="*.py" -n
# verify vhost
grep -n "ParseIP\|vhosts\[\"\*\"\]\|r.Host == \"\"" go-abey/rpc/http.go
# verify secp256k1 guards
grep -n "unsafe.Pointer(&" go-abey/crypto/secp256k1/secp256.go -B2
```
