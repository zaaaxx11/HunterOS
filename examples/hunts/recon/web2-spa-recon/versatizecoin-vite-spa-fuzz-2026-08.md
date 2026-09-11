# VersatizeCoin Vite SPA Fuzz — 2026-08-16

**Target:** `www.versatizecoin.com` (VTCN / BC Hyper Chain) — Agent 3 FUZZ-ENGINEER session.

## Stack
- Vite `index-CXmqaNgO.js` 969,660 bytes (639 lines minified) + `cdn.tailwindcss.com` + `index.css`
- Cloudflare hosting; SPA fallback returns `200 text/html 2519B <!DOCTYPE><div id=root>` for every unknown path
- Router: `react-router-dom@7.10.1` paths `/`, `/PrivacyPolicy`, `/blog`, `/brand-assets`, `/community`, `/docs`, `/ecosystem`, `/listings`, `/tokenomics`; `useParams/useSearchParams 0 hits`
- Imports: `@google/genai@1.33.0`, `react@19.2.3`, `recharts@3.6.0`, `lucide-react@0.561`

## Bundle Split (critical for triage)
- Offset 0–521,115: Google GenAI SDK (`JV`/`KV`/`VH`/`@google/genai`) — 521 KB
- Offset 521,115–969,567: app code — 448 KB
- Whole-bundle counts lie: `innerHTML 24 / dangerouslySetInnerHTML 17 / __proto__ 5 / .prototype 51` are React internals (`case "dangerouslySetInnerHTML": a.innerHTML=u`)
- App-only: `innerHTML 2 / dangerouslySetInnerHTML 0 / __html 0 / eval 0 / postMessage 0 / localStorage 0 / 0xAddr 0`
- App innerHTML both on one line: `t="@#%&*+=<>[]{}"` → `i.innerHTML=Array(20).fill…join("<br>")` matrix-rain + `r.innerHTML="@keyframes matrix-fall"` — static, no user input. Always `js.indexOf('const XV=""')` slice first.

## Gemini Client Flaw
```js
const XV="",ZV=new JV({apiKey:XV})
const QV=n=>`You are the official AI Assistant for VersatizeCoin... Total Supply: ${e}...` // KB: explorer bchscan.io, DEX bcswap.org 1CR, Tokenomics V2: Supply ${e}, AscendEX/Blofin upcoming, Private Staking 12-25% APY offline, Allocation CEX20/Public15/Seed10/Team15(1yr cliff 2yr vest)/Marketing15/Staking15/Treasury10`
eG=async(e,t=[])=>{let n="10,576,406 VTCN"; try{o=await(await fetch("https://aggrigator.bchscan.io/api/coinprice")).json(); n=parseFloat(o.totalSupplies.VTCN).toLocaleString(...)}catch{}; return(await ZV.chats.create({model:"gemini-2.5-flash",config:{systemInstruction:QV(n)},history:t}).sendMessage({message:e})).text}
```
- `XV=""` empty → `if(t.apiKey==null) throw "An API Key must be set when running in a browser"` — chat DoS today, key-theft + $$ quota drain if ever populated. `tools/codeExecution` not enabled → prompt-leak only, not RCE. Fix: server proxy `/api/chat`.

## Real Backends (off-domain)
- `aggrigator.bchscan.io/api/coinprice` → `{"prices":{"VTCN_per_VUSD":"0.05944...","VTCN_per_USDT":0.06025,"VTCN_per_SVTCN":"0.2436"},"totalSupplies":{"VTCN":"616140.861573871371256766","VUSD":"10000000.0","SVTCN":"10000000.0","USDT":"207066.11"},"marketCaps":{"VTCN_in_USDT":37128.26}}` — `Server: nginx/1.24.0 Ubuntu / X-Powered-By: Express`, `Access-Control-Allow-Origin: *` (wildcard), `?amount/price/id/admin/role/__proto__/redirect` all 200 same JSON (fail-open), `NaN/Infinity/null/999...` ignored. Precision bug: `parseFloat` loses 8 digits on 18-decimals → use BigInt. `api.bchscan.io/api?module=account&action=balance&address=0x00…` → `4298337465400000000000`, `tokenlist` → `[]`, `stats/ethprice` → `ethusd 0.199821`.
- `rpc.bchscan.io` Geth 1.22.3 — `eth_chainId 0x17ac (6060) net_version 6060 gasPrice 0x746a528800 gasLimit 0x1c9c380 latest 0x1575a56` empty block 0 txs, `extraData 0xd883010100846765746888676f312e32322e3…`. Fuzz: `eth_getBlockByNumber(max_uint256)` → `hex number > 64 bits`; `eth_getBalance("-1")` → `hex string without 0x prefix`; `eth_getBalance(null)` → `cannot unmarshal non-string`; `""`→`hex length 0 want 40`; `eth_estimateGas value=max_uint256` → `insufficient funds supplied gas 12510499`.
- `bchscan.io` Next.js explorer (`/_next/static/chunks/*` UA-gated, need `Mozilla/5.0` + Referer), `bcswap.org` Vite `index-C8vV5JXw.js` 8KB no sinks, `docs.bchscan.io` ok.

## SPA Trap Signals
- Identical 2519B body for `/.env /.git/HEAD /assets/*.map /api/* /admin /graphql /openapi.json /api/coinprice?* /?id=0/-1/1e308?admin=true?redirect=evil.com?q=<script>` — compare Content-Length, not status. Host `evil.com` → Cloudflare 403 correctly; `X-Forwarded-Host/For/Original-URL` → 200 no effect; CORS on main: no ACAO; aggrigator: `ACAO:*`. Missing headers: `CSP/X-Frame-Options/HSTS/X-Content-Type-Options/X-XSS-Protection/Referrer-Policy all MISSING` → clickjack/MIME sniff.

## Host Header / Open Redirect
- `Host: evil.com` blocked 403; `location.href/assign/replace` only in iframe sandbox check; `?redirect/url/next/returnTo` no redirect; `__proto__[polluted]` no effect; `?callback=alert(1)` inert; no `postMessage` listener.

## Repro
```bash
curl -sk https://www.versatizecoin.com/assets/index-CXmqaNgO.js | grep -o 'XV=""' # empty key
curl -sk https://aggrigator.bchscan.io/api/coinprice | jq .
curl -skI https://www.versatizecoin.com/.env | grep Content-Length # 2519 = trap
curl -sk -H "Origin: https://evil.com" https://aggrigator.bchscan.io/api/coinprice -i | grep -i access-control
curl -sk -X POST https://rpc.bchscan.io -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# RPC edge
python3 -c "import urllib.request,json,ssl;print(urllib.request.urlopen(urllib.request.Request('https://rpc.bchscan.io',data=json.dumps({'jsonrpc':'2.0','method':'eth_getBalance','params':[None,'latest'],'id':1}).encode(),headers={'Content-Type':'application/json'}),context=ssl._create_unverified_context()).read().decode())"
```

## Verdict
No pre-auth RCE. Top actionable: never ship Gemini key client-side (proxy), tighten CORS `ACAO:*→allowlist`, add CSP/HSTS/XFO, fix `parseFloat` precision, return 400 on unknown query params.
