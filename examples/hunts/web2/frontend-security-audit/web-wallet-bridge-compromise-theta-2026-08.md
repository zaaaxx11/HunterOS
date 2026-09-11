# Theta Web Wallet — Pre-Auth Compromise Chain (2026-08, static analysis)

Source: `/root/theta-hunt/wallet` (Theta web wallet, React SPA). Session artifacts: `/root/theta-hunt/findings-theory2.md`, `/root/theta-hunt/poc-theory2.html`.

## The 4-link chain (all confirmed by code read)

### Link 1 — Origin-less postMessage RPC bridge
`src/services/Web3Bridge.js`:
- L42 `window.addEventListener('message', async (event) => {` — L43-44 origin check is a commented-out TODO.
- L16 `this.targetOrigin = '*'` default; L75 `sourceFrame.postMessage(JSON.stringify(response), this.targetOrigin)` — responses (signed msgs, tx hashes, address) leak to whatever origin sent the request unless a DAppModal overwrote targetOrigin.
- Reachable privileged methods: `wallet_switchEthereumChain` (L91), `eth_requestAccounts` (L110, leaks selectedAddress), `personal_sign` (L137), `eth_sendTransaction` (L161).
- L82-84 `wallet_sendDomainMetadata` stores attacker metadata → shown in confirm modal via `ProjectInfoCard` (spoofable dapp name/icon).

### Link 2 — Embed mode: credentials in URL, dead passwords
- `src/Pages.js:25-47` — `/embed?k=<b64 keystore>&p=<b64 password>` auto-unlocks; password stashed via `TemporaryState.setWalletData`.
- `src/controllers/theta-wallet.js:341-378` `_importAccount` → raw private key into in-memory `SimpleKeyring` (`src/keyrings/simple/index.js:19-31`) for the whole session.
- `src/modals/ConfirmTransactionModal.js:52-53` password auto-filled `config.isEmbedMode ? TemporaryState.getWalletData().password : ''`; L267 hides the password field in embed mode → one Confirm click signs+broadcasts.
- `src/modals/PersonalSignModal.js:69-74` — `onConfirmClick` calls `executeSignMessage(message)` and NEVER passes the password state (dead variable at L60-62). Signing path: `transactionsController.executeSignMessage` → `keyring.signMessage` → in-memory wallet, zero auth.

### Link 3 — URL-driven dapp iframe injection
- `src/index.js:11-12` — `?after-unlock=` query param stored raw on `window.afterUnlock` (no decodeURIComponent; `&` in the URL would break parsing, so use param-free URLs).
- `src/state/actions/Wallet.js:85-94` — post-unlock, `window.afterUnlock.replace('show-dapp-','')` becomes iframe `src` in `src/modals/DAppModal.js:70`. Attacker page framed inside wallet chrome AND positioned as a child window that can drive Link 1.
- Non-embed tx modal still demands password, but user types it thinking they're using a legit dapp.

### Link 4 — WYSINWYS gap
`src/modals/ConfirmTransactionModal.js:155-191` — SmartContract tx display decodes `data` ONLY as TNT20 `transfer(address,uint256)`; catch block silently swallows failures → renders truncated contract addr + raw hex `Data` row. Blind signing for any other call.

## Best chain (embed one-click drain)
```
attacker page iframes https://wallet.thetatoken.org/embed?k=...&p=...   (auto-unlock)
→ parent.postMessage({type:'request', request:{method:'eth_sendTransaction', params:[{to,value,data}]}}, '*')
→ ConfirmTransactionModal: password pre-filled + field hidden
→ one Confirm click → approveTransactionRequest → in-memory key signs → broadcast
```
personal_sign variant: zero password involved at all.

## Adversarial checks that did NOT break the chain
- No origin check anywhere on the listener (verified — commented TODO).
- `verifyPassword` (Wallet.js:300) passes in embed mode because TemporaryState holds the real password.
- No DOM XSS needed: zero `dangerouslySetInnerHTML`/`innerHTML`/`eval`/`new Function`/`document.write` in src; React escapes TNS names/token symbols/metadata; `<img src={metadata.icon}>` = tracking only (property assignment, `javascript:` inert). The bridge is the chain, not XSS.
- No CSP meta in `public/index.html`; hardening gap, not a chain link.

## Remediation anchors
1. Web3Bridge.js:42 — enforce event.origin allowlist, bind listener to active DAppModal session.
2. PersonalSignModal.js:69 — actually consume/verify the password.
3. ConfirmTransactionModal.js:52 — never auto-fill from TemporaryState.
4. state/actions/Wallet.js:85 — allowlist show-dapp URLs.
5. frame-ancestors / X-Frame-Options on `/embed`.

## Reusable grep set for this class
```bash
rg -n "addEventListener\(['\"]message|onmessage" src
rg -n "targetOrigin|postMessage" src
rg -n "isEmbedMode|TemporaryState" src            # auto-password paths
rg -n "after-unlock|afterUnlock|show-dapp" src    # URL → iframe src
rg -n "getQueryParameters|URLSearchParams" src    # what else the URL controls
# then READ the confirm handler: does onConfirmClick actually pass the password?
```
