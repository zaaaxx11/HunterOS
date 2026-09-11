# Partisia JVM Reader — 2026-08-16 Case Study

## Target
Partisia Blockchain — JVM (not Go/EVM), 3 shards (Shard0/1/2), sharded L1 with MPC + BYOC bridges. Domains: `partisiafoundation.com (94.231.103.176, Simply.com WAF 455 + 16-bit PoW sc-challenge)` blocked, `partisia.com` (Astro v7 marketing), docs at `partisiablockchain.gitlab.io/documentation` (mkdocs-material), GitHub `partisiablockchain` (9 repos, mirror of `gitlab.com/partisiablockchain/language/*`), JS browser at `browser.partisiablockchain.com` → `conf/config.js`.

## Infra Discovery
- `browser.partisiablockchain.com/conf/config.js` leaks `serverUrl: https://backend.browser.partisiablockchain.com (91.107.206.69)`, reown `projectId 95f6a...`, 7 withdrawalContracts / 7 depositContracts / 4 priceOracles, 30+ `addressNames` (BYOC pairs: BNB/ETH/USDT/WBTC/MATIC + System Update).
- `reader.partisiablockchain.com (159.69.115.9, nginx/1.31.1)` = live reader, `backend.browser` is 404-only.
- OpenAPI 3.0.3 v4.39.0 at `/openapi/spec.json` → 16 ops: `GET /chain`, `GET /chain/contracts/{addr}`, `GET /chain/shards/{id}/blocks`, `GET /chain/shards/{id}/jars/{jarId}`, `PUT /chain/transactions {payload:base64}`, `PUT /chain/shards/{id}/events`, `GET /health`.
- `GET /chain` → `{chainId:"Partisia Blockchain", shards:[Shard0,1,2], blockTime:4610621, governanceVersion:64687}`.
- `GET /chain/shards/Shard0/blocks` → `{parentBlock:..., producer:11, committeeId:39}`; genesis `blockTime:0` works.

## RPC Attack Surface (fuzz matrix)
| Probe | Payload | Result |
|---|---|---|
| `PUT /chain/transactions {payload: gadget}` | `rO0ABXNyABpvcmcuc3By...` (Spring BeanDefinition) | `400 Could not deserialize SignedTransaction from byte data / BYTES_NOT_DESERIALIZABLE` |
| Same | `""`, `not-base64!!!`, `A*1MB`, `00*10`, `ff*100` | `400` uniform, `not-base64` leaks `Failed to decode VALUE_STRING as base64 (MIME-NO-LINEFEEDS): Illegal character '-'` + `com.partisiablockchain.server.rest.model.SerializedTransaction["payload"]` |
| `PUT /chain/shards/Shard0/events {fake:1}` | `{}` | `400 Missing required creator property 'payload'` / same Jackson redaction `StreamReadFeature.INCLUDE_SOURCE_IN_LOCATION disabled` |
| `XXE Content-Type` | `<?xml ...><!ENTITY xxe SYSTEM "file:///etc/passwd">` | `415` for `application/xml,text/xml,application/yaml`, `400 Unexpected character '<'` for `application/json` — correct |
| `GET /chain/shards/{id}/blocks` | `Shard99,Shard3,Shard-1` | `500` empty | `Shard%00` → `400 nginx`, `Shard0` → `200` — shard-existence oracle |
| `GET /chain/contracts/{addr}` | `01ZZZZ`, `../../../etc/passwd`, `%00` | `400` ; `A*40` → `500` |
| CORS | `Origin:https://evil.com` on `GET /chain/contracts/...` and `PUT /chain/transactions` | `Access-Control-Allow-Origin: *`, `Allow-Headers: Content-Disposition, Content-Type, Accept, Authorization`, `Allow-Methods: GET,POST,PUT,DELETE` — wildcard on all |
| Rate limit | `5× GET /chain` | `200` all, no `X-RateLimit-*`/`Retry-After` |
| Path traversal | `../etc/passwd` in contract addr | `400` |

## JAR Disclosure
`GET /chain/shards/Shard1/jars/e09199850ff1c67c9054b13d5b6432192f3fe8b4a4ae24cf8ce39688a85b19a2` → `200 {data:base64 ZIP 33625B magic 504b0304}`. Entries: `com/partisiablockchain/governance/mpctoken/*.class`, `*.abi (PBCABI)`, `com.partisiablockchain.governance.mpc-token-git.properties` (`git.build.version=6.86.0`, `2025-12-11T13:43:25+0000`, `commit 485eb59`), `main`. No `..` ZipSlip but full bytecode + ABI leaked. Same for BYOC `047e1c96...` (618k storage) and `045dbd...`.

## Contract Logic (audit via raw.githubusercontent)
- `voting/src/lib.rs`: `vote` checks `result.is_none && block_production_time < deadline && voters.contains(sender)`, `count` checks `>=deadline`, `voters_approving > voters.len()/2`. Correct.
- `petition/src/lib.rs`: `signed_by.insert(sender)` — no double-sign guard needed (Set).
- `access-control/src/lib.rs`: diamond `Admin>ModeratorA/B>User` PartialOrd via ORDERINGS, `update_data` needs `user_level >= level`, `update_level` only `HIGHEST_LEVEL`. Uses `assert!` panics (gas waste).
- `MpcTokenContractState` ABI: `icedStakings,locked,stakeDelegations,transfers`; 30+ `OnBehalfOf` callbacks (`stakeTokensOnBehalfOf`, `transferOnBehalfOf`) delegate via `appointCustodian` — custodian confusion if frontend not validating `target`.

## Frontend Bundle
`browser.partisiablockchain.com/main.eec3f0337ce1f827b3ad.js` 6.8MB. Grep hits: `PrivateKey`, `secretSerializer`, `projectId`, 5× `0x` EVM addrs, `partisiablockchain.com`. No hardcoded API key.

## Git Acquisition Pitfall
`git clone https://github.com/partisiablockchain/*` fails with `git: 'remote-https' is not a git command` — image `/usr/local/libexec/git-core` missing `git-remote-https`. Fix: `curl -L https://codeload.github.com/<org>/<repo>/zip/<commit> -o /tmp/x.zip` or `curl -sL https://raw.githubusercontent.com/...`. Do not `dnf install git-core` on TencentOS 4. Verified via `curl -sL https://api.github.com/repos/.../contents?ref=main` + raw.

## Recommendations
- CORS: allowlist `browser.partisiablockchain.com`, not `*`; remove `Access-Control-Allow-Methods: PUT` if not needed cross-origin.
- Shard handler: map invalid shardId to `404` not `500`; avoid oracle.
- Error handling: strip `com.partisiablockchain.server.rest.model.SerializedTransaction` from 400, return generic `invalid payload`.
- Rate limit: nginx `limit_req` on `PUT /chain/transactions` + `GET /chain`.
- JAR: consider not serving raw bytecode; if needed, strip `git.properties` and set `Cache-Control: no-store` already present — keep.
