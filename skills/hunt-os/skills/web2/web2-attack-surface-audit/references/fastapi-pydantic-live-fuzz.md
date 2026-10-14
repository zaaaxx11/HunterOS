# FastAPI / Pydantic Live Fuzz Playbook (Canton Wallet Backend 2026-08)

Class-level playbook for fuzzing Python FastAPI + Pydantic v2 APIs over HTTP — no source needed, black-box via the auto-generated `/openapi.json`. Case study: Canton Wallet Backend (uvicorn), Agent 3 FUZZ-ENGINEER (CDC protocol).

## Why FastAPI is a distinct target class
- Auto-serves `/openapi.json` + `/docs` (Swagger UI) + `/redoc` — full schema, request bodies, param constraints, and every route. This is the #1 recon asset: fetch it first and derive the entire attack surface + exact Pydantic constraints (minLength/maxLength, patterns, required fields) without guessing.
- Pydantic v2 enforces types/constraints **before** the handler — so most type-confusion, boundary, and injection probes die with a clean `422` (not a 500). Expect far fewer crashes than a hand-rolled parser.
- Auth is usually a FastAPI **dependency** (`Depends(get_current_user)`). Critical question: does it run before or after body parsing? (See §3.)

## 0) Recon — pull the schema, derive constraints
```bash
curl -sk https://<target>/openapi.json -o /tmp/openapi.json
python3 - <<'PY'
import json; d=json.load(open('/tmp/openapi.json'))
for p,ms in d['paths'].items():
  for m,i in ms.items():
    if m in('get','post'):
      print(m.upper(),p)
      for pr in i.get('parameters',[]): print('  param',pr['name'],pr['in'],json.dumps(pr.get('schema',{})))
      rb=i.get('requestBody',{})
      if rb: print('  body',rb['content']['application/json']['schema'].get('$ref'))
# then resolve $ref -> components.schemas to get required[] + per-field types
PY
# Also: /docs (Swagger UI), /redoc — confirm FastAPI + version; server header usually 'uvicorn'
```
Param schema tells you the exact fuzz boundary: `{"type":"string","minLength":1,"maxLength":100}` → fuzz 100 (accept) vs 101 (expect 422 `string_too_long`). If 101 returns 422 with a clean Pydantic message, validation is enforced — mark BLOCKED, don't brute-force length.

## 1) Query-param / GET sink fuzz (e.g. `/api/tags/query?tag=`)
Probe classes, log status + body + **timing**:
- SQL: `'` `'; DROP TABLE users--` `' OR 1=1--` `' UNION SELECT null--`
- NoSQL: `{"$gt":""}` `{"$ne":null}` `{"$where":"1"}`
- Regex DoS: `(a+)+$` shape = `'a'*25+'!'`, `'a'*30+'X'` — compare timing to a benign baseline. **If the sink does an exact-match DB lookup (not regex), timing is flat (~0.53s for all) → BLOCKED.** ReDoS only bites if input reaches a `re` engine.
- SSTI/template: `{{7*7}}` `${7*7}` `${jndi:ldap://x}` — if never evaluated/reflected → BLOCKED.
- Prototype pollution: `__proto__`, `constructor`, `prototype` as values.
- Boundary: maxLength, maxLength+1.
- Unicode: emoji, RTL override, combining chars, fullwidth, ZWJ — test for normalization bypass on lookup oracles.
- **Null byte `%00`** — high-value: often crashes the DB driver / string C-binding even when Pydantic passes the string through. In this campaign `tag=ali%00ce` (any `%00` position) → deterministic `500 Internal Server Error`, plain text, **no traceback**. Only payload to break the 200/422 pattern. Not a code leak (debug off) but a reliable error oracle / minor DoS primitive. Always probe `%00` at start/mid/end/only/double.

### Enumeration-oracle characterization (the real finding class)
A lookup endpoint that returns different bodies for hit vs miss is an unauth enumeration oracle. Characterize it precisely to show exploitability:
- exact-match case-SENSITIVE? (`alice`=hit, `ALICE`/`Alice`=miss)
- no unicode normalization (`alicé`, fullwidth, ZWJ → miss)
- no trimming (`alice ` / ` alice` → miss)
- each hit leaks a distinct record (here: full `ref_party_id` + description) → enumerable
Report as REFLECTED/info-leak with the exact-match semantics — that precision is what makes it actionable.

## 2) Pre-auth POST body fuzz — establish WHERE auth runs FIRST
Send a **broken-JSON-syntax** body (`{"a":`) vs a **valid-syntax-but-wrong-type** body to each auth endpoint:
- `422 json_invalid` on broken syntax → only the raw JSON tokenizer runs before auth.
- `401 Missing/invalid Authorization` on valid-syntax-but-wrong-type → **auth dependency fires BEFORE Pydantic body-model parsing.** Once confirmed, ALL parser-DoS / type-confusion on that endpoint is unreachable pre-auth — mark BLOCKED and stop burning requests.

If auth runs before body-parse, these are all neutralized (confirmed flat 401, ~0.5s):
- deep nesting 100/500/1000/5000 levels (no stack exhaustion — body never parsed)
- huge base64 (~2.7MB field) → 401 (body buffered, slow ~25s, but still 401, no 413/500)
- wrong types (array where string, huge number 10^400, negative/huge amount, object where string)
- unicode bomb (combining char ×5000), null-byte field, `__proto__`/`constructor` keys
Conclusion to report: "parser-DoS surface is gated behind auth; no pre-auth 500/traceback."

## 3) Debug-mode / traceback oracle
Check every 500 and 422 for code-path leakage:
- `debug=True` → 500 contains a Python traceback with `File "...", line N` and source. CRASH-LEAK.
- `debug=False` (production default) → plain `Internal Server Error` text, no internals.
- Probe BOTH prod and dev/staging — dev instances often run `debug=True`. Here dev == prod (both clean) → debug=False confirmed on both. Pydantic 422s leak only field names + constraint ctx (e.g. `{"ctx":{"max_length":100}}`) — that's schema info, not code paths; LOW.

## 4) Path traversal on route params
`/api/command/{id}/status` with `..%2f..%2fstatus`, `....//....//status`, `%2e%2e%2f...`, `..%00/`, `..;`:
- uvicorn/starlette normalizes `%2f`-traversal before routing → 404. BLOCKED.
- A param that happens to match the route shape (`..;`) may 401 (auth) — that's routing, not traversal.
Don't over-iterate; 5-6 representative payloads, all 404 → mark BLOCKED.

## 5) `/api/metrics` (Prometheus) — label-injection / cardinality-DoS
Fetch and inspect label VALUES:
```bash
curl -sk https://<target>/api/metrics | grep -oE '\{[^}]*\}' | sort -u
```
- If all label values are **server-side enums** (`code`, `reason∈{ok,http_409}`, `result∈{success,failed}`) → no user-controlled label values → no cardinality-DoS / label injection via this endpoint. BLOCKED.
- Cardinality DoS only exists if a USER-controlled string (path param, query, party id) is used as a label value. Grep the label set for anything that looks attacker-influenced. Server-only enums = safe.

## 6) Custom/optional header fuzz
FastAPI endpoints often declare optional headers (e.g. `x-feat-decimals: string|null`). Probe with long (5000-char), null-byte, SQLi, negative, huge-num, `{"$gt":""}`:
- If the handler ignores it (opaque optional string) → all return normal 200, never reflected, never error → BLOCKED.
- Note: Python's `urllib`/`http.client` rejects non-latin-1 header bytes (combining unicode) client-side — use curl for raw-byte header probes.

## Reporting discipline
- Every probe → CRASH-LEAK / REFLECTED / BLOCKED + exact request + status + timing + body evidence.
- Uniform 401/422/404 across a class = BLOCKED; say so and name the defense (Pydantic maxLength, auth-before-parse, uvicorn normalization, server-side label enums).
- The recurring real findings on FastAPI targets: (a) unauth enumeration oracle on a GET lookup, (b) `%00`→500 robustness bug. Injection/type-confusion usually dies at Pydantic.
- Honest severity: a deterministic 500 with no traceback is a robustness/DoS note, NOT RCE; an exact-match case-sensitive oracle is a real info-leak but bounded by match semantics.
