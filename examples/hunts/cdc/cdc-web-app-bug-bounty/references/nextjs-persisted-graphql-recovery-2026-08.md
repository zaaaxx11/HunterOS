# Next.js Persisted-Query GraphQL Hash Recovery (ad.nl / DPG Media, 2026-08)

## The problem
GraphQL endpoint returns `PersistedQueryOnly` + `PERSISTED_QUERY_NOT_IN_LIST`
for every inline query, introspection, and guessed hash. Direct query is dead.
The persisted-query hashes ARE recoverable from the client JS bundle — but only
if you reverse-engineer the transport format the client actually uses.

## What you need to find in the JS bundle
Next.js (pages router) exposes `/_next/static/<buildId>/_buildManifest.js` which
lists every page chunk + shared chunk filename (the `a,s,n,c,e,t...` argument
variables map to `"static/chunks/<id>-<hash>.js"` strings in the trailing
function call). Download ALL shared chunks — the GraphQL operations are split
across them, not in page chunks.

In the chunks, each persisted GraphQL document is embedded in TWO forms:
1. A raw template-literal string: `` `\n  query SharedAccessGetInvite($inviteKey: String!) {...}` ``
   (the `\\n`-escaped form inside `"...":t.dns` map entries).
2. A compiled AST with `hash:"sha256:<64hex>"` (NOT `__meta__.hash` — that was a
   false lead).

## The hash format (the actual gotcha)
The client sends, via GET:
```
/api/graphql?operationName=<Op>&variables=<urlenc>&extensions={"persistedQuery":{"sha256Hash":"sha256:<64hex>","version":1}}
```
Two trapdoors burned ~an hour each:
- Raw `sha256(query_string)` (and whitespace-normalized variants) → ALL rejected.
- The `__meta__:{hash:"sha256:..."}` AST values → rejected (those are node hashes).

The correct value is `hash:"sha256:<full-64-hex>"` extracted with regex
`hash:"sha256:([a-f0-9]{64})"` and paired to its operation via the nearest
`name:{kind:"Name",value:"..."}` downstream. The 64-hex IS accepted verbatim
when prefixed with `sha256:` in the `extensions.persistedQuery.sha256Hash` field.

## Fastest recovery when regex guessing stalls
Use browser_exec to capture the REAL request (don't rely on static analysis):
```
cdp('Page.addScriptToEvaluateOnNewDocument', source=hook)
# hook monkeypatches window.fetch to log url+body into window.__gql_log
cdp('Page.reload', ignoreCache=True)
js('JSON.stringify(window.__gql_log)')
```
The logged URL contains the exact `sha256:`-prefixed hash AND the request shape
(GET query-param form, not POST JSON). This confirms the format in seconds and
lets you back-fill every other hash from the bundle.

## What to do with recovered hashes
Send each op with correct var shape; the GraphQL layer's type errors are a
SCHEMA ORACLE: `Field "language" is not defined by type "ChatDpgAssistantInput"`
tells you exact required/optional fields. Required-field errors:
`Variable "$parameters" of required type "..." was not provided`.

Map authorization empirically by probing every recovered op pre-auth and
classifying the response:
- `UNAUTHORIZED_FIELD_OR_TYPE` → gated (properly auth'd)
- `was not provided` / `required type` → REACHABLE, fix vars and retry
- `{"data":{...}}` → REACHABLE + returns data (pre-auth surface)

## ad.nl results (this target)
93 persisted ops recovered. Pre-auth reachable: `getInvite` (PII oracle:
invitee.email + owner.name + subscription ids), `GetContactFormUploadLink`
(unauth S3 presigned PUT, content-type whitelist PNG/JPG/PDF), `chatDpgAssistant`
(self-bootstraps on random-UUID conversationId, no PII/tools), `SubmitContactForm`,
`ValidateAddress`. Everything else (`getLinkedSubscriptions`, `acceptInvite`,
`cof*`, payments, newsletters) returned `UNAUTHORIZED_FIELD_OR_TYPE` — solid
`@auth` directives. No pre-auth RCE/ATO. Hashes + query strings dumped to
`/tmp/full_hashes.json`, `/tmp/raw_gql_queries.json` for re-use.

## Pitfall recap
- Don't trust `__meta__.hash` — hunt `hash:"sha256:"` WITHOUT the `__meta__` wrapper.
- The transport may be GET-query-param, not POST-JSON; the `sha256:` prefix matters.
- Fragment/query bodies are split across chunks; `_buildManifest.js` gives the map.
- Confirm with browser network capture before burning time on hash derivation.