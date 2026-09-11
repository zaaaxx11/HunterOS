# U2U network-stats 2026-08 — Hunt Detail (Go API + React Dashboard)

Static red-team review of `/root/u2u-hunt/network-stats` (fork of ethereum/node-crawler). Go backend (gorilla/mux + modernc.org/sqlite), React/TS frontend (Chakra UI + recharts). No live target — all findings file:line static.

## Findings (file:line verified)

### 1. Unauthenticated dashboard API — HIGH
- `pkg/api/api.go:51-58` — `HandleRequests()` mounts `/v1/dashboard` with NO middleware; `http.ListenAndServe(a.address, router)` bare.
- `cmd/crawler/flags.go:15-19` — `apiListenAddrFlag` default `0.0.0.0:10000`.
- `pkg/api/api.go:180` — `handleDashboard` returns clients/languages/OS/versions/countries (aggregated node intel).
- PoC: `curl http://target:10000/v1/dashboard` → full JSON pre-auth.
- Not just data leak — it's network-topology intel for targeting vulnerable node versions.

### 2. Filter query builder — SQLi NEAR-MISS (BLOCKED by whitelist)
- `pkg/api/api.go:65-98` `addFilterArgs()`: user `?filter=[["key:value:comp"]]` JSON → `inner += fmt.Sprintf("(%v %v ?) ", key, comp)` — **key and comp string-concat into SQL**, value parameterized.
- `pkg/api/api.go:200-258`: `fmt.Sprintf("... FROM nodes %v ...", where)` — WHERE clause raw-concat into 5 query templates.
- Saved by `validateKey()` (api.go:306-324) — 13-key map lookup (`id,name,version_*,os_*,language_*,country`). Comparator whitelist in `unmarshalFilterArgs` (api.go:103-127, default falls through to `=`).
- **KEY LESSON:** a whitelist on the concat'd identifier is the ONLY thing between this and full SQLi. Any future key addition or case-folding bug = injection. Also note `nameCountInQuery = strings.Count(vars["filter"], "\"name:")` (api.go:186) — raw substring count on user JSON to branch query shape; fragile.
- SQLite (modernc.org/sqlite) — even if injected, no `ATTACH` via database/sql multi-statement (single stmt only), but UNION/exfil still in play.

### 3. Cache-key DoS (panic via type assertion)
- `pkg/api/api.go:151-162` `toQuery()`: `res += whereArgs[idx].(string)` — unchecked type assertion. All current callers pass strings, but one non-string arg (e.g. JSON number routed through) = panic per request. Concurrent map risk too: `a.cache` pointer swapped in `dropCacheLoop` goroutine (api.go:38-49) while readers access it — data race on the pointer itself.
- Cache mixup bug (api.go:177): `storeCache` stores `r.Countries` under key built from `versionQuery` — wrong-cache-poisoning, correctness not security.

### 4. pprof + expvar + memsize debug server — MEDIUM (conditional)
- `cmd/crawler/setup.go:155-167` `StartPProf()`: `http.Handle("/memsize/", ...)` + `http.ListenAndServe(address, nil)` on DefaultServeMux → also exposes `/debug/pprof/*` and `/debug/vars` (expvar via `exp.Exp(metrics.DefaultRegistry)`). No auth. Gated by `--pprof` CLI flag.
- Heap/goroutine dumps = memory scraping for keys, plus profiling-DoS.

### 5. Stored-XSS surface — ANALYZED, mostly mitigated by React
- Taint source: remote P2P node controls `ClientType` string → `pkg/crawlerdb/db.go:113-134` insert → `pkg/apidb/database.go:97-114` re-insert parsed name → API JSON.
- Sink check: frontend renders `{name}` in JSX (`Home.tsx:112,126`, `Filtering.tsx:84`) — React auto-escapes. SVG `<text>` via recharts label render also text-node only. **No dangerouslySetInnerHTML/innerHTML anywhere** (verified by grep). Verdict: dormant stored-XSS, real impact only if a raw-HTML sink is added; report as hardening note (sanitize at crawler ingest), not active XSS.

## Negative results (verified by grep)
- Command injection: no `os/exec` anywhere.
- Path traversal: no HTTP file serving; `LoadNodesJSON`/`WriteNodesJSON` (`pkg/common/nodes.go:55,63`) are CLI-local only.
- Security headers: none set (no CSP/XFO/XCTO) — flag as hardening.
- CORS: none configured — same-origin by default, but no auth means moot for reads.

## Tooling note
- `search_files` (ripgrep backend) chokes on unescaped `(` / `\(` alternation groups in pattern — falls back to `grep -rnE` in terminal with proper escaping. Multi-pattern grep: use `grep -rn "pat1\|pat2"` (BRE alternation) not extended group syntax.
