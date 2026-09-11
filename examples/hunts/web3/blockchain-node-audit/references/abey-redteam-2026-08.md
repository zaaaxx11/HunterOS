# AbeyFoundation Red-Team 2026-08 — Go-Abey + Wallet Module + Safe Forks

Source: `/tmp/abey/` 16 Aug 2026, 11 repos via `api.github.com/orgs/AbeyFoundation/repos` → zipball fallback (TencentOS 4 missing `git-remote-https`). `gh` missing.

## Org Recon (noise filter critical)
- `orgs/AbeyFoundation/repos` returned 11: `documents` (66K), `go-abey` (4.5M), `abey-wallet-module` (3.6M), `safe-smart-account` (4.6M), `safe-deployments`, `safe-client-gateway` (2M), `safe-transaction-service` (654K), `safe-events-service`, `safe-config-service`, `safe-wallet-web` (2.4M), `safe-infrastructure` (142K), `safe-eth-py` (889K)
- 9/11 are vanilla `safe-global` forks: `fork:true`, `pushed 2024-06/07`, 0 stars, TS/Python — skip via `fork==true && parent ∈ safe-global/safe-fndn && size<10K && pushed<2024-08` (saves 75%). Core = `go-abey` (Go 780 files, 131k code) + `abey-wallet-module` (Dart 210 files, 25k code) via `pygount`.
- `users/AbeyFoundation/repos` needed too (org endpoint 403 on some GHE). Tarball fallback: `curl -L https://github.com/<org>/<repo>/archive/refs/heads/main.tar.gz || master.tar.gz`; per-file `raw.githubusercontent.com/<org>/<repo>/main/<path>` when API 403.

## Go-Abey (geth fork) — Dual-Chain
- **Fast** chain + **Snail** chain (fruits/snailblocks). ChainID 179 mainnet / 178 testnet. Consensus `Minerva` (PoW) + `TBFT` + `election`. EVM `core/vm` with `extimpawn/impawn`.
- **Signer:** `core/types/transaction_signing.go:141-244` `TIP1Signer{chainId, chainIdMul: chainId*2}` — `V = sig[64]+35+chainId*2` (+8 offset), `Sender()` does `V - chainIdMul -8 → recoverPlain`, `Hash()` RLP includes `chainId,0,0` and conditionally `Payer,Fee`. `Payer()` verifies `addr == tx.data.Payer` (`ErrPayersign` at `:89-91`). No EIP155 fallback (commented out `:247-348`) — `MakeSigner()` always `NewTIP1Signer` (`:48-51`).
- **Trust boundaries:** G1 JSON-RPC `:8545/:8546`, G2 P2P `:30313` `MaxPeers:100`, G3 wallet (mnemonic/keystore→sqflite), G4 CLI `--rpcapi --rpccorsdomain --wsorigins`, G5 IPC `gabey.ipc` (fs ACL only), G6 consensus gossip.

### High-Risk Sinks (file:line)
- `personal_unlockAccount` `internal/abeyapi/api.go:404` `TimedUnlock(addr,passwd,duration)` default 300s, max `MaxInt64` → brute→ `signTransaction`
- `personal_importRawKey`/`newAccount` `:377,392` hex → keystore, weak passwd, no rate limit
- `eth/abey_sendRawTransaction` `:1925,2554` `hex→rlp.Decode→SendTx` `Public:true` → RLP bomb, replay if ChainID unchecked
- `personal/eth_sendTransaction` `:1882` `PublicTransactionPoolAPI.SendTransaction` **no passwd** when module exposed
- `admin_*` `:321` `ExportChain(file)` `os.OpenFile(O_CREATE)`, `ImportChain→rlp→InsertChain`; `node/api.go PrivateAdminAPI AddPeer/AddTrustedPeer/StartRPC` → file write/read, chain bomb, eclipse
- `miner_*` `abey/api.go:194` `Start/Stop/SetEtherbase/SetGasPrice` → coinbase manipulation
- `debug_*` `abey/api.go:416` `PublicDebugAPI.DumpBlock→stateDb.RawDump()` → state leak if `debug` in HTTPModules
- `--singlenode` `:100` `crypto.HexToECDSA("<redacted>")` hardcoded → `cmd/utils/flags.go` `BftKeyHex/NodeKeyHex` `HexToECDSA` from CLI → `ps aux` leak
- `bftkey`/`nodekey` `node/config.go:39-40,440-469` `SaveECDSA` plaintext file `0700` → validator hijack (`consensus/tbft/node.go:355`)
- P2P `p2p/server.go:348,634` `AddTrustedPeer` bypasses `MaxPeers` → single trusted eclipse

### Exposure Resolution
- `node/defaults.go:DefaultConfig` `HTTPModules=[net,web3]` safe vs `cmd/gabey/config.go:defaultNodeConfig()` appends `[abey,eth,impawn,shh]` + `WSModules+[abey]` + `IPCPath=gabey.ipc`. Flags `cmd/utils/flags.go:RPCCORSDomainFlag/RPCApiFlag` override. `--singlenode` forces `[db,abey,net,web3,personal,admin,miner,eth]`.

## Wallet Module (Flutter/Dart) — Plaintext at Rest
- `lib/model/wallet_model.dart:43-46,62,75` `mnemonic=""`, `privateKey=""` → `toJson()` → `SharedPreferences` (`lib/utils/preferences_util.dart:26` `SharedPreferences.getInstance()`) + `sqflite`. `lib/utils/chain_util.dart:91-108` `CommonUtil.encrypt` via `bee_encryption/abey_encryption` only covers `tokenI`, model fields remain plaintext in JSON. `wallet_chain.dart`/`wallet_create_mnemonic.dart` flow. `adb backup` → plaintext.
- Mitigant claimed: `lib/utils/common_util.dart:77` `BeeEncryption.encryptString(token,getKey(authKey))` + `lib/utils/password_util.dart:21` `ENC.AES(key)` — check if key derived from user passwd with scrypt (likely weak if passwd empty).

## Safe Forks — High-Value Solidity Surfaces (safe-smart-account v1.4.1)
- `contracts/Safe.sol:78` `threshold=1` in constructor → singleton `setup` protected. `contracts/SafeProxy.sol:43` `delegatecall(gas(), _singleton, 0, calldatasize())` slot 0 immutable.
- `contracts/Safe.sol:313,317` `ecrecover` without `s ≤ n/2` (go `crypto.go:205` has check, Solidity doesn't) → malleability, `GS026` only checks ordering.
- `contracts/libraries/MultiSend.sol:62` `delegatecall` + `StorageAccessible.sol:46` `delegatecall(gas(), targetContract, calldataPayload)` → if `Operation.DelegateCall` allowed (`Executor.sol:32` `delegatecall(txGas, to, ...)`), RCE in Safe context.
- `contracts/base/GuardManager.sol:86` + `SafeToL2Migration.sol:46,122` `MIGRATION_SINGLETON` delegatecall storage collision risk.

## Adjacent Services (AbeyFoundation)
- `safe-wallet-web/src/services/private-key-module/pk-popup-store.ts:14` `STORAGE_KEY='privateKeyModulePK'` + `sessionItem` → `sessionStorage` plaintext `privateKey` (`src/services/private-key-module/index.ts:14` `new Wallet(privateKey, provider)` + `PkModulePopup.tsx:16`). XSS/Safe-App iframe exfil. `provider.destroy()` on `updateProvider` but no `sessionStorage.clear()` on disconnect beyond `pk-popup-store`.
- `safe-client-gateway/src/routes/common/auth/basic-auth.guard.ts:13` `request.headers['authorization'] === 'Basic '+token` — no `timingSafeEqual`, no `Bearer`, single `AUTH_TOKEN` (`src/config/entities/configuration.ts:34` `process.env.AUTH_TOKEN`, `container_env_files/cgw.env:14` `your_privileged_endpoints_token`) → `POST /v1/hooks/events` (BasicAuthGuard) brute.
- `safe-client-gateway/src/datasources/jwt/jwt.module.ts:40` `jwt.verify(token, secret)` HS256 (`src/datasources/jwt/configuration/jwt.configuration.ts:11-12` `JWT_SECRET/JWT_ISSUER` env, `secret?: string`), `jwt.service.ts:18` `getOrThrow` no entropy check, `auth.guard.ts:36` trusts `verifyToken` → forge `AuthPayloadDto` if weak.
- `safe-transaction-service/config/settings/base.py:312` `DEFAULT_PERMISSION_CLASSES: ("AllowAny",)` + `config/urls.py:21` `AllowAny` → `history/views*.py`/`tokens/` unauth; only `analytics/views_v2.py:17` `IsAuthenticated`. `container_env_files/txs.env:3` `DJANGO_SECRET_KEY='Very-secure-secret-string'`, `cfg.env:3` `insecure_key_for_dev`, `events.env:7` `amqp://general-rabbitmq:5672` no creds — dev defaults shipped.
- `rpc/http.go:225` `AllowedHeaders:["*"]`, `cors.Options{}` empty = `AllowAll`; `node/config.go:HTTPCors` default `localhost` but `--rpccorsdomain "*"` → any origin `personal_unlockAccount`.

## Grep Anchors (abey-specific)
```
grep -rn "TimedUnlock|UnlockAccount|ImportRawKey|SendRawTransaction|PrivateAdminAPI|ExportChain|<redacted>" go-abey --include="*.go"
grep -rn "TIP1Signer|chainIdMul|big8|SignatureValues|recoverPlain" core/types --include="*.go"
grep -rn "BftCommitteeKey|bftkey|nodekey|HexToECDSA" node cmd --include="*.go"
grep -rn "shared_preferences|sqflite|bee_encryption|CommonUtil.encrypt" abey-wallet-module/lib --include="*.dart"
grep -rn "privateKeyModulePK|sessionStorage|PK.*Popup" safe-wallet-web/src --include="*.ts" --include="*.tsx"
grep -rn "AllowAny|DEFAULT_PERMISSION|BasicAuthGuard|timingSafeEqual" safe-*/src safe-*/config --include="*.py" --include="*.ts"
```

## Exploitability Matrix (validated 2026-08)
| Finding | Trigger→Effect→TrustBoundary | File:line | Validated |
|---------|------------------------------|-----------|-----------|
| SingleNode key | `gabey --singlenode` → `crypto.HexToECDSA(<redacted>)` → every node same key → sign as validator | `cmd/gabey/config.go:100` | proven-in-code, devnet test |
| Session PK | XSS `sessionStorage.getItem('privateKeyModulePK')` → `ethers.Wallet` → fund theft | `pk-popup-store.ts:14` | proven (read storage) |
| Wallet plaintext | `adb backup` → `SharedPreferences` JSON `mnemonic/privateKey` | `wallet_model.dart:43` | proven |
| AllowAny | `curl /api/v1/safes/` 200 unauth → enumerate safes/txs | `base.py:312` | proven |
| CORS * | `fetch(https://victim:8545, {method:POST, body:eth_sendTran...})` from evil.com when `--rpccorsdomain *` | `rpc/http.go:225` | proven |
