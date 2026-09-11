# Nyantai Brutal Throttled Recon — Sonic RPC (Validated 2026-08-09)

User phrase: `oke lanjut, nyantai aja, biar gausah request API kecepetan, tapi tetep brutal carinya`
Sequential phrase: `coba 1 dulu deh, baru 2`

## Sonic RPC constraints (rpc.soniclabs.com)

- `eth_blockNumber` OK, `eth_getLogs` with >400k window → timeout 40-60s (exit 124).
- 100k chunk = 130-230 logs, reliable.
- Headers required: `Content-Type: application/json` + `User-Agent: Mozilla/5.0`, timeout 12-15s.
- `eth_call`/`eth_getCode`/`eth_getStorageAt` sequential with 0.6-0.7s sleep survives 60+ calls. Parallel burst → 403/timeout.
- Fallback: `https://sonic.drpc.org` or Etherscan V2 `chainid=146` (needs API key).

## Pattern (Python)

```python
sonic="https://rpc.soniclabs.com"
topic="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def rpc(m,p, timeout=15):
    d=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode()
    req=urllib.request.Request(sonic, data=d, headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())

# 800k scan = 8×100k chunks, sleep 1.0-1.2s between
holders=set()
for i in range(8):
    hi=latest - i*100000
    lo=hi - 100000 + 1
    j=rpc("eth_getLogs",[{"address":ft,"topics":[topic],"fromBlock":hex(lo),"toBlock":hex(hi)}])
    for lg in j.get("result",[]):
        holders.add("0x"+lg["topics"][1][-40:].lower())
        holders.add("0x"+lg["topics"][2][-40:].lower())
    time.sleep(1.2)
# then balanceOf per holder, sleep 0.6s, checkpoint every 10
```

Validated: 800k → 111 holders, 39 with bal >0. Paus 1.72M FT (87% supply) at `0xccac...0bd` (UniswapV3/Shadow pool).

## Git clone fallback (headless env)

`git clone https://` fails: `git: 'remote-https' is not a git command` (exit 128). Fix:

```bash
for branch in main master develop; do
  curl -L "https://github.com/<org>/<repo>/archive/refs/heads/$branch.tar.gz" -o "/tmp/$repo-$branch.tar.gz"
  file "/tmp/$repo-$branch.tar.gz"  # gzip vs HTML
  tar -xzf "/tmp/$repo-$branch.tar.gz" -C /tmp && break
done
```

FT = main, escrow/security = master. Validate with `file` before `tar -xzf`.

## Sequential discipline

When user says `coba 1 dulu deh, baru 2` → finish Option 1 (recon+decompile+4byte) fully, confirm, then start Option 2. Do not parallelize.

## Santai tone

`jelasin santai` → casual Indonesian lo/gue + emoji 😘💕, tables per finding, one-line per theory BLOCKED. Full CDC `VULNERABILITY/CHAIN/...` only when user sends `ROLE & OBJECTIVE ... BEGIN.`
