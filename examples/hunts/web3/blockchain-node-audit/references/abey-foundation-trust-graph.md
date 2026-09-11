# AbeyFoundation Trust Graph — Go-Ethereum Dual-Chain Reference (2026-08)

Source: `https://github.com/AbeyFoundation` — 12 repos via `api.github.com/orgs` + `/users` (page1=12, page2=0). Workdir `/tmp/abey`, git `remote-https` missing on TencentOS 4 → tarball fallback. Pygount verified: go-abey 807 .go / 131k code / 247k lines; wallet 210 .dart / 25.8k.

## 1. Repo Inventory (9 Safe forks = noise)

| repo | lang | bytes | size | branch | fork parent | core |
|------|------|-------|------|--------|-------------|------|
| go-abey | Go | Go10.1M C674K JS561K |14864| main | — | YES |
| abey-wallet-module | Dart | Dart1.2M |3412| main | — | YES |
| documents | — | docs only |320| master| — | docs/RPC |
| safe-smart-account | TS | TS393K Sol164K |7570| main | safe-fndn | NO |
| safe-client-gateway | TS | TS2.9M |9653| main | safe-global | NO |
| safe-transaction-service | Python | Py2.8M |4413| main | safe-global | NO |
| safe-events-service | — | TS74K |727| main | safe-global | NO |
| safe-config-service | Python | Py264K |1225| main | safe-global | NO |
| safe-deployments | TS | TS55K |1247| main | safe-global | NO |
| safe-wallet-web | — | TS3.3M |17691| dev | safe-global(monorepo)| NO |
| safe-infrastructure | Shell | 729 |185| main | safe-global | NO |
| safe-eth-py | Python | Py2.5M |3034| main | safe-global | NO |

Safe-fork noise filter: `fork==true && parent∈{safe-global,safe-fndn} && pushed 2024-06/07 && stars 0 && size<10000` → skip 75% clones.

## 2. File Tree (core only)

```
go-abey/ 807go 18M
 core/121go (23k) blockchain.go state/ vm/impawn.go snailchain/ types/transaction.go
 p2p/102go (17k) server.go:30313 discover/discv5 enode/enr nat rlpx
 consensus/96go (15k) minerva/ tbft/state.go election/
 accounts/59go abi/ keystore/keystore.go hd.go usbwallet/trezor
 crypto/64go secp256k1 bls12381 bn256 ecies blake2b
 rpc/23go (2.5k) server.go http.go(endpoints) 
 internal/abeyapi/ 3go 2.9k api.go:2721 backend.go addrlock.go
 abey/55go backend.go:APIs() api.go downloader/ filters/ pbft_agent.go
 node/ config.go defaults.go node.go api.go
 cmd/gabey/ main.go config.go:defaultNodeConfig() accountcmd chaincmd
 miner/7go worker.go
 params/config.go ChainID 179/178 genesis hashes snailGenesis
abey-wallet-module/ 210dart 5.4M
 lib/wallet/web3dart/ json_rpc.dart client.dart credentials/
 lib/pages/ wallet_create_mnemonic wallet_import_* wallet_token_transfer
 lib/utils/ chain_util.dart:encrypt common_util.dart:77 crypto_util bip32
 lib/vender/crypto/ aes cdsa/ristretto
 plugins/ bee_encryption abey_encryption getx
 lib/common/ constant.dart global.dart wordlist.dart
documents/ 21files 256K RPC/json_rpc.md Installation/ Usage/ DPOS/ Whitepaper/
```

Largest files: `tests/state_test.go:10076` `internal/abeyapi/api.go:2721` `core/blockchain.go:1939` `consensus/tbft/state.go:1853` `core/vm/impawn.go:1622`.

## 3. Core Identity

- go-abey = go-ethereum fork + dual chain (fast blocks + snailchain fruits/snailblocks). ChainID 179 mainnet (rpc.abeychain.com, abeyscan.com), 178 testnet (testrpc). Minerva PoW (MinimumDifficulty 3M) + TBFT + election. EVM core/vm with extimpawn. Only Solidity: contracts/ens (4 sol).
- Wallet = Flutter 3.1.3+313 web3dart+dio, sqflite/shared_preferences, pointycastle/encrypt, local_auth, firebase, flustars.
- Documents RPC ref = grep anchor for `abey_*`/`eth_*` method list.

## 4. Data Flow

```
Wallet(mnemonic) → Flutter encrypt(bee_abey) → sqflite
                → web3dart dio → JSON-RPC 2.0 batch → go-abey rpc.Server
P2P rlpx/discv5 → p2p.Server:30313 → core.BlockChain → LevelDB(rawdb) → event.TypeMux → RPC subs
                → TxPool/SnailPool → miner.Worker → consensus TBFT/Minerva → broadcast
                → state.StateDB → EVM → Receipts
```

## 5. Trust Boundaries (6)

G1 JSON-RPC: :8545/:8546/ipc `rpc.Server.RegisterName(namespace)` + `node.startHTTP/WS/IPC` + whitelist `HTTPModules/WSModules` + `rpc/http.go:newCorsHandler/newVHostHandler`
G2 P2P: :30313 rlpx `p2p.Config{MaxPeers100 TrustedNodes NoDiscovery}`
G3 Wallet: mnemonic/keystore/passwd/QR → `chain_util.getPrivateKeyFromKeystore` + `CommonUtil.encrypt` → sqflite
G4 Config/CLI: `gabey --config TOML` + flags `--rpcapi --rpccorsdomain --wsorigins` → `cmd/gabey/config.go:defaultNodeConfig` + `cmd/utils/flags.go`
G5 IPC: `gabey.ipc` UNIX socket `node/IPCEndpoint()` no CORS
G6 Consensus: block/fruit gossip → `consensus/tbft/reactor.go` `core/block_validator.go`

Default modules: `node/DefaultConfig=[net,web3]` safe, but `cmd/gabey/config.go:defaultNodeConfig()` appends `[abey,eth,impawn,shh]` HTTP + `[abey]` WS + `IPCPath=gabey.ipc`. `--singlenode` forces `[db,abey,net,web3,personal,admin,miner,eth]` + hardcoded key.

## 6. 10 High-Risk Sinks (file:line)

G1 personal_unlockAccount `internal/abeyapi/api.go:404` TimedUnlock default 300s max MathMaxInt64 → indefinite unlock
G2 personal_importRawKey `api.go:377,392` hex→keystore file
G3 eth/abey_sendRawTransaction `api.go:1925,2554` hex→rlp.Decode→SendTx Public:true
G4 eth_sendTransaction public no passwd `api.go:1882` PublicTransactionPoolAPI vs personal 446
G5 admin_* `abey/api.go:321` ExportChain os.OpenFile O_CREATE, ImportChain rlp.NewStream InsertChain; `node/api.go:PrivateAdminAPI` AddPeer(enode) AddTrustedPeer StartRPC
G6 miner_* `abey/api.go:194` PrivateMinerAPI Start/Stop SetEtherbase/SetGasPrice/SetExtra/SetElection
G7 debug_* `abey/api.go:416` PublicDebugAPI.DumpBlock RawDump Public:true if enabled
G8 --singlenode hardcoded key `cmd/gabey/config.go:100` `<redacted>`
G9 P2P trusted bypass `p2p/server.go:348,634` not counted in MaxPeers
G10 wallet weak encrypt `lib/utils/common_util.dart:77` CommonUtil.encrypt via bee_encryption + dio no pinning

APIs() registration: `abey/backend.go:321` abey/eth 4 public (AbeychainAPI MinerAPI DownloaderAPI FilterAPI) + miner/admin/debug/net; `internal/abeyapi/backend.go:GetAPIs` abey/eth + abey(PublicTxPool) eth(PublicTxPool2) txpool/fruitpool/debug plus personal(Private) impawn(Public).

## 7. Recon Workflow (tarball fallback)

```bash
curl -s -A "Mozilla/5.0 ..." https://api.github.com/orgs/AbeyFoundation/repos?per_page=100 | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))"
curl -s -A "..." https://api.github.com/users/AbeyFoundation/repos?per_page=100  # fallback when org 403
curl -L -A "..." https://github.com/AbeyFoundation/go-abey/archive/refs/heads/main.tar.gz -o go-abey.tar.gz
# master fallback for documents
tar xzf go-abey.tar.gz
# per-file when API 403: raw.githubusercontent.com/AbeyFoundation/repo/main/path
pygount --format=summary go-abey --suffix=go  # 780Go 131k
find go-abey -name "*.go" -exec wc -l {} \; | sort -rn | head -15
grep -rn "GetAPIs\|APIs()\|Namespace:" internal/abeyapi abey node --include="*.go"
grep -rn "TimedUnlock\|ImportRawKey\|SendRawTransaction" internal/abeyapi --include="*.go"
grep -rn "<redacted>\|SingleNodeFlag" cmd --include="*.go"
```

Documents anchors: `params/config.go:MainnetChainConfig ChainID 179`, `node/defaults.go:DefaultHTTPPort 8545 DefaultWSHost localhost`, `rpc/http.go:225 cors.New`, `p2p/server.go:113 TrustedNodes`.
