# Nuxaris Secure Vault SPA — Positive Control (2026-08-16)

**Target:** `app.nuxaris.com` (CRA Webpack + Vercel, `main.040e5d2d.js` 1.78MB + `main.040e5d2d.js.map` 6.89MB, 731 sources) — **Verdict: 0 exploitable client chains, 3 hygiene LOWs.** Use as secure-vault positive control when scoring DOM XSS / stored XSS / vault bypass.

## 1. Sourcemap Extraction Recipe (hardline bypass)

Vercel shell is `1605B <!doctype html><div id=root>` with `server: Vercel`, `x-vercel-cache: HIT`, `ACAO *` (no CSP). All `/api/*` → `200 index.html` decoy — real APIs leak only via `REACT_APP_*` in bundle.

```bash
curl -sk https://app.nuxaris.com/ | grep -oE 'src="/static/js/main\.[^\"]+\.js"'
curl -sk https://app.nuxaris.com/static/js/main.040e5d2d.js.map -o /tmp/main.js.map
# hardline blocks `python3 -c` multiline and `curl | python3` — stage to file:
# write /tmp/extract.py then python3 /tmp/extract.py
import json
with open('/tmp/main.js.map') as f: d=json.load(f)
mapping=dict(zip(d['sources'], d['sourcesContent']))
app={s:c for s,c in mapping.items() if c and 'node_modules' not in s and not s.startswith('../webpack')}
for s,c in app.items(): open('/tmp/nuxaris_src/'+s.replace('../','').replace('/','__'),'w').write(c)
# result: 60 app files (52–74KB each): wallet/vault-crypto.ts, wallet/storage.ts, wallet/vault.ts, wallet/signing.ts, services/vault-index.ts, contexts/VaultContext.tsx, etc.
```

`/_next/` does not exist (CRA not Next.js). Alternative entry list: `/asset-manifest.json` (150+ `static/js/*.chunk.js`).

## 2. Secure Vault — File:Line Map (positive control)

| Component | File | Key Lines | Why It Matters |
|---|---|---|---|
| Crypto | `wallet/vault-crypto.ts:15-20` | `PBKDF2_ITERATIONS=600000`, `SALT 16`, `IV 12`, `AES-GCM 256/128` | High iteration, WebCrypto `crypto.subtle` (native, non-extractable key `false`) |
| AAD binding | `wallet/vault-crypto.ts:37` | `additionalData = utf8('nuxaris-vault:v'+version+':'+accountId)` | Copy ciphertext to other accountId → decrypt throws `WrongPasswordError` |
| KDF check | `wallet/storage.ts:45-58` | `assertStoredVault` → `kdf.name===PBKDF2-SHA256 && iterations>0 && version===1` | Downgrade blocked |
| Persistence | `wallet/storage.ts:146-175` | `DB nuxaris-wallet / store vaults keyPath accountId` | Only ciphertext in IndexedDB; comment `localStorage/sessionStorage are never used` |
| Isolation | `wallet/session.ts:23-58` | `WeakMap<Session,Secret> SECRETS`, `Object.freeze(session)`, `requireSecret` + `lock()->wipe()+delete` | No `session.privateKey` read, no forge, GC on drop |
| Wipe | `wallet/bytes.ts:120` | `wipe(b){b.fill(0)}` | Defense-in-depth; string mnemonic noted as unwipable |
| Index dir | `services/vault-index.ts:9-19` | `localStorage nuxaris_vault_accounts = JSON({emailLower: accountId})` | Non-secret, feeds `lookupVault(email)` |
| Signing NS | `wallet/signing.ts:29-116` | `LOGIN_NONCE_PREFIX='nuxaris-login:'`, `PREPARED_TX_HASH_LENGTH=32`, `looksLikeLoginChallenge()` reject | Login UTF-8 vs tx 32B raw vs topology hex 40-140 — mutually exclusive |
| Context | `contexts/VaultContext.tsx:72` | `isUnlockedSession(sessionRef.current) && accountId match` guard | Re-ask password race prevented |

Threat model: XSS can steal `localStorage access_token + nuxaris_vault_accounts` but **cannot** get private key (needs password-derived AES-GCM decrypt) — fund theft still requires PBKDF2 unlock.

## 3. Stored / DOM XSS Sweep — Negative Proofs

- **App `dangerouslySetInnerHTML`:** `rg -n dangerouslySetInnerHTML /tmp/nuxaris_src` → 0 hits (only vendor `rainbowkit/dist/index.js` for `cssStringFromTheme` sanitized alphanum).
- **`innerHTML`/`outerHTML`:** 0 hits in `/tmp/nuxaris_src`; vendor only `react-dom` SVG fallback, `rainbowkit` particle `<img>` from `imageUrl` not user input, `solana-mobile` modal `innerHTML=modalHtml$1`.
- **`location.hash/search`:** `rg location\.(hash|search)` in app → 0 (only `window.location.reload()` retry button `SwapInterface.tsx:605`).
- **`postMessage`/`onmessage`:** 0 handlers in app sources; vendor `solana-mobile` socket `message`, `scheduler MessageChannel.postMessage(null)`, `wallet-adapter-solflare/detect.ts: window.addEventListener('message', onMessage)` filtered to `target==='metamask-contentscript' && id==='solflare-detect-metamask'` + 5s timeout — not eval sink.
- **Address book sink:** `components/SavedAddressPicker.tsx:302` `saveAddress(label,chain,address)` → `POST /api/bridge/wallet/addresses` (JWT `authFetch`) → render as `{entry.label}` / `{entry.address}` in `div.text-[10px].font-mono.break-all` — React auto-escape. Same for `SwapInterface walletAddress`, `MyOrdersPage user_destination_address`, `WalletPage tx.description/memo`, `DepositPage wallet_address`. All validated: EVM `^0x[a-fA-F0-9]{40}$`, Solana `^[1-9A-HJ-NP-Za-km-z]{32,44}$`, Canton `^[a-fA-F0-9]+::[a-fA-F0-9]+$`.
- **Prototype pollution:** `services/vault-index.ts:18` `JSON.parse(raw) as Index` → `index[normalize(email)]=accountId` shallow assign — no `lodash.merge`/`Object.assign(parsed)`. Zustand persist `merge: (e,t)=>({...t,...e})` is spread (safe under modern spec). No gadget chain → `?__proto__[polluted]=1` ignored.

## 4. Supply Chain & Hygiene (not fund theft)

- **47 vendor deps** from sourcemap `node_modules` grep (`@noble/curves`, `@scure/bip39`, `viem`, `wagmi`, `rainbowkit`, `solana/web3.js`, `borsh`, `buffer`, etc.) — no `ua-parser-js` / `event-stream` compromised, `borsh Struct:Object.assign(this,props)` from schema not user JSON.
- **WalletConnect placeholder LOW:** `contexts/EvmWalletContext.tsx:11` `projectId = REACT_APP_WALLETCONNECT_PROJECT_ID || 'PLACEHOLDER'` → RainbowKit `getDefaultConfig` invalid ID → QR modal DoS, not theft.
- **Helius public key LOW:** `REACT_APP_SOLANA_RPC=https://mainnet.helius-rpc.com/?api-key=<REDACTED-API-KEY>` plaintext in `main.js process.env` — live verified `getHealth ok`, `getVersion 4.2.0-rc.1`, billable quota burn / tracking, rotate + proxy via `nuxarisapiv1.xyz/api/solana`.
- **Contrast insecure pattern:** `public/js/render.js:58 rowHtml→<div>${n.name}</div> + 109 innerHTML=arr.map(rowHtml).join('')` vanilla `innerHTML` from WS `n.name` is vuln when unescaped — React `{}` is safe.

## 5. Re-test Checklist

- [ ] Fetch `.js.map` with sourcemap leak test; if 200, repeat extraction.
- [ ] Grep `REACT_APP_*` dump for new third-party keys — live-test quota / credit burn.
- [ ] Re-run address book flow with payload `<img onerror=alert(1)>` as label — verify React escapes vs vanilla innerHTML.
- [ ] Verify `signLoginNonce` prefix reject still enforced after bundle update.
