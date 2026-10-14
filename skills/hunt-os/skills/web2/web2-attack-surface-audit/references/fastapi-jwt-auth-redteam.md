# FastAPI JWT auth red-team — error oracles, dual-stack diff, unauth inventory
# (Canton Wallet Backend, CDC Agent 2 RED-TEAMER, 2026-08-14)

Targets: prod `https://wallet-backend.main.digik.cantor8.tech`, dev `https://wallet-backend.dev.digik.cantor8.tech`.
All tests GET/safe, ~1 req/sec throttle. Outcome: **0 bypass, 12 oracle-leaks, 25+ blocked.**

---

## 1. Error-oracle battery — exact transcripts (the reusable part)

FastAPI + HTTPBearer dependency splits auth failures into TWO messages. Record both — the split
itself is the finding (it proves the token reached the verifier vs failed parsing).

### User stack (`/api/balance`, `/api/register/status_v2`, `/api/register/finalise_v3`, `/api/register/post_confirm_v2`)
| Request variant | Response |
|---|---|
| no `Authorization` header | `401 {"detail":"Missing or invalid Authorization header"}` |
| `Authorization: garbage` (no Bearer prefix) | `401 {"detail":"Missing or invalid Authorization header"}` |
| `Authorization: Bearer ` (empty) | `401 {"detail":"Missing or invalid Authorization header"}` |
| `Authorization: Basic dGVzdA==` | `401 {"detail":"Missing or invalid Authorization header"}` |
| `Authorization: Bearer garbage` | `401 {"detail":"Invalid or expired token"}` |
| `Authorization: bearer garbage` (lowercase scheme) | `401 {"detail":"Invalid or expired token"}` (scheme IS case-insensitive) |
| duplicate `Authorization` headers | `401 {"detail":"Invalid or expired token"}` (first one wins) |
| `Bearer garbage, Bearer valid` (comma) | `401 {"detail":"Invalid or expired token"}` |
| token + `;` / `%0a` / `%09` / `%00` suffix | `401 {"detail":"Invalid or expired token"}` (all reach verifier) |

### M2M stack (`/api/balance_m2m`, `/api/register/party/{id}/contract-setup_m2m`, `/api/swap/beneficiary_m2m`)
| Request variant | Response |
|---|---|
| no header | `401 {"detail":"Missing Authorization header"}` |
| `Bearer garbage` | `401 {"detail":"Invalid token"}` |

**The four distinct strings = two separate middleware/verifier implementations.** Diffing them is a
30-second test that maps the auth architecture black-box. If the m2m stack ever answers a user-token
(or vice versa), that's the cross-scope bypass — here both rejected everything → BLOCKED.

## 2. Unauthenticated endpoint inventory (from `/openapi.json` `security: []` walk)

```
GET /api/config/version_v2   → full instrument list + admin party IDs + signups_guarded flag
GET /api/metrics             → Prometheus: internal ledger URLs (/v2/users/validator-backend@clients),
                               party IDs in url= labels, reconcile/swap operational counters
GET /api/tags/query?tag=test → PROD: {"exists":true,"ref_party_id":"1525633c6c...","description":"teat"}
                               = pre-auth user enumeration oracle (tag → party_id)
GET /api/vaults/config       → DEV leaks real provider party_id b52fc476...; PROD empty strings
GET /healthz, /docs, /redoc, /openapi.json → all 200 pre-auth on BOTH envs
```

## 3. Dev-vs-prod diff (verified, not assumed)

- `signups_guarded: false` (dev) vs `true` (prod) — BUT all register endpoints still 401 without JWT
  on both. Flag divergence = ORACLE-LEAK (config disclosure), NOT a bypass. Always fire the actual
  request before upgrading severity.
- OpenAPI paths/schemas identical (73 paths, 0 diff) — same build, only config differs.
- No debug routes exposed on dev; `/docs` identical on both.

## 4. JWT confusion battery — all BLOCKED

Crafted via a standalone script (smart-approval blocks inline `python3 -c`; see Pitfalls in SKILL.md):
| Token | prod `/api/balance` | prod `/api/balance_m2m` |
|---|---|---|
| `alg:none` empty sig | 401 Invalid or expired token | 401 Invalid token |
| HS256 + `kid: ../../dev/null` | 401 Invalid or expired token | 401 Invalid token |
| HS256 empty signature | 401 Invalid or expired token | 401 Invalid token |

Uniform rejection across stacks = alg allowlist + signature enforced. (Agent 4's RS256/bad-kid
battery on the same target also uniform → naive forgery fully closed.)

## 5. Register flow probing

- `POST /api/register/finalise_v3` with `{}`, `{"signed_transactions":[]}`, `[{"foo":"bar"}]` → all
  401 before body parse (auth runs first — same ordering oracle as Agent 3's broken-JSON test).
- **Ghost endpoint:** metrics referenced `/api/auth/challenge`; 14 path variants
  (`/api/auth/*`, `/api/register/challenge*`, `/api/challenge`, ...) ALL 404 on both envs.
  JWT issuance lives in a different service (likely the mobile client + external IdP) — pivot there.

## 6. Transport findings

- Trailing slash `/api/balance/` → `307 Location: http://wallet-backend.main.../api/balance`
  (uvicorn emits absolute http:// URL — scheme downgrade). Same on `/api/metrics/`, `/healthz/`, dev too.
- Direct port-80 access: prod = connection timeout (firewall kills it), dev = nginx 308 → https.
  Net: downgrade exists at app layer but is not network-exploitable → report LOW/config issue.
- `X-Forwarded-For`/`X-Real-IP: 127.0.0.1`, `X-Original-URL`, `X-Rewrite-URL`, `X-API-Key`,
  `Cookie: token=`, PUT/DELETE/HEAD method override → all uniform 401/405. No proxy-trust bug.

## 7. Report format that worked (CDC verdict table)

One table per test class, columns: Test | Endpoint | Exact response | Verdict.
Verdict vocabulary: BYPASS-FOUND / ORACLE-LEAK / BLOCKED. Summary counts up top
(0 / 12 / 25+), then numbered key findings, then recommendations keyed to the oracle leaks
(standardize 401 messages, auth-guard /api/metrics + /api/tags/query, hide /docs in prod,
fix absolute-URL redirects, align dev/prod flags). Zero-bypass with documented oracles is a
complete, honest red-team result — resist inflating oracles into bypasses.
