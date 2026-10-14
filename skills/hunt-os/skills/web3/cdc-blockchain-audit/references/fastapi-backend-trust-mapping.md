# FastAPI/Web2 Backend Trust-Graph Mapping Playbook

For CDC audits where the target is a web2 backend (FastAPI/Express/etc.) fronting a blockchain
ledger — wallet backends, relayers, bridges, custodians. Proven against a Canton Network wallet
backend (Aug 2026 session): 73-route FastAPI service with dual JWT issuers, public Prometheus
metrics, and interactive-submission ledger flow.

## 1. OpenAPI mining

FastAPI exposes `/openapi.json` by default (also `/docs`, `/redoc`). Extract:

```bash
python3 -c "
import json; spec = json.load(open('/tmp/openapi.json'))
for p, ops in sorted(spec['paths'].items()):
    for m, op in ops.items():
        if m in ('get','post','put','delete','patch'):
            print(m.upper(), p, 'sec=', op.get('security','INHERIT'))"
```

What to look for:
- **Public vs secured diff** — `security: []`-less ops and global INHERIT routes that are reachable
  without a token (config, version, health, metrics, query endpoints). Each is pre-auth surface.
- **Free-form JSON bodies** — schemas with `additionalProperties: true` (e.g. `commands[]`,
  `disclosed_contracts[]`). These frequently pass near-verbatim into ledger command structures;
  the bug class is fields the backend FAILS to overwrite (actAs/party/readAs/workflow_id).
- **Client-chosen idempotency keys** — `command_id`, `request_id`, `swap_id` strings on
  fund-moving prepare/execute endpoints → race/replay double-spend class, especially combined
  with batch endpoints and visible ledger 409 rates in metrics.
- **Suffix/prefix token classes** — `_m2m`, `/internal/`, `/admin/`. m2m routes that take a
  caller-supplied identity field (e.g. `sender_party_id`) mean one token operates many parties.

## 2. Prometheus `/metrics` mining (route & issuer archaeology)

Public metrics endpoints leak the deployment's history and topology. Extract:

```bash
# Full route inventory incl. REMOVED routes (high count + 404 = dead route, still hit by legacy clients)
grep -vE '^#' metrics.txt | grep 'request_total' | grep -oE '(method|path|status_code)="[^"]*"'

# JWT issuers & token classes
grep -oE '[a-z_]+validated_total\{[^}]*\}' metrics.txt   # e.g. {issuer="identity-service"} vs {issuer="keycloak"}

# Internal ledger users / party IDs / upstream hosts
grep -oE 'url="[^"]*"' metrics.txt | sort -u
grep -oE '[a-f0-9]{32}::[a-f0-9]+' metrics.txt | sort -u   # Canton party IDs

# Race-condition evidence
grep -E 'status_code="409"' metrics.txt
```

Findings that fell out in the live session:
- A removed `POST /api/auth/challenge` route with 8.8M hits all 404 — JWT issuance had moved to
  an external identity service; the backend only validates.
- A removed `POST /api/accounts/recovery_v3` (5.7k hits) — account-recovery endpoints are where
  pre-auth account takeover lives; check other environments (dev/staging/old APKs) for live copies.
- Dual JWT issuers on `_m2m` routes: `{issuer="identity-service"}` and `{issuer="keycloak"}` —
  each issuer is a separate trust root to probe (JWKS hosts, alg pinning, aud binding).
- Internal ledger user (`validator-backend@clients`) and its `/v2/users/.../rights` polling —
  reveals the backend holds its own privileged ledger identity for setup/delegation txs.

Verify removed routes on prod AND any dev/staging host before writing them off — route 404s on
both in the session, but that is target-specific, not a rule.

## 3. Live probing etiquette (production)

- GET-only (plus safe 401-triggering requests), ≤1 req/sec, no destructive actions.
- Probe unauthenticated variants of secured routes: expect uniform 401 + identical error text
  (different messages for missing-token vs bad-signature = oracle).
- Run `scripts/jwt_confusion_probe.py <jwks_url> <protected_url>` per accepted issuer.
- Record VERIFIED NEGATIVES in the report ("alg=none → 401", "HS256 confusion → 401",
  "SQLi on ?tag= parameterized") so downstream agents don't waste budget re-testing.
- Info-disclosure of a public metrics endpoint + party-enumeration oracles (e.g. an unauth
  tag/alias lookup returning real party IDs) are themselves reportable findings (CWE-200/359)
  even when they don't directly yield RCE/theft.

## 4. Typical ranked-vector shape for this class

1. Dual/multi-issuer JWT confusion (alg=none, RS256→HS256, kid-injection, missing aud binding
   between issuers) — m2m token = total impact when m2m routes accept arbitrary party fields.
2. Dev↔prod key/token reuse (same issuer trust on both hosts; weaker signup on dev).
3. Free-form command-JSON injection into ledger prepare/execute (party/actAs override).
4. Race/replay on client-chosen idempotency keys in batch/bridge/vault flows.
5. Public metrics + unauth enumeration oracles as recon/enabler findings.
