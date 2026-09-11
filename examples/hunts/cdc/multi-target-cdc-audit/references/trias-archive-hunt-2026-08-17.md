# Trias Archive Hunt — Finding Dead Host Evidence (2026-08-17)

Session goal: prove theft path LIVE. Result: host dead, archive proves it WAS live 2018-2022.

## Archive hunt results

### crt.sh cert timeline (wallet.trias.one)
| Cert ID | Not Before | Not After |
|---------|-----------|----------|
| 746428199 | 2018-09-14 | 2019-09-14 |
| 1857588464 | 2019-09-04 | 2020-10-03 |
| 3367245695 | 2020-09-07 | 2021-09-08 |
| 5175814691 | 2021-09-07 | 2022-09-09 |

→ wallet.trias.one was live from Sep 2018 to Sep 2022 (4 years). DNS removed after last cert expiry.

### crt.sh all trias.one subdomains (33 unique)
`aaa, abc, btcwallet, docs, exchange, explorer, geonswap, grant, hackathon, mining, mis, monitor, monitorv2, nft, rpc01, rpc02, rpc1, rpc2, staking, tc, test, trh, triathon, triathonm, twd, wallet` — vast ecosystem, now mostly dead.

### HackerTarget hostsearch
```
trias.one,52.194.163.139
docs.trias.one,104.18.40.47
grant.trias.one,18.208.88.157
rpc01.trias.one,13.159.122.78
www.trias.one,13.158.57.218
```
Only 5 hosts in HackerTarget vs 33 in crt.sh — HackerTarget gap-fills but misses many.

### urlscan historical snapshot
```
wallet.trias.one Sep 7, 2020
IP: 119.28.116.31 (Tencent AS132203, SG)
Server: nginx, TLS: TrustAsia TLS RSA CA
Screenshot: https://urlscan.io/screenshots/8645b768-9cdc-462c-a8a9-d611c83f7428.png
```

### vhost probe on historical IP (119.28.116.31)
IP still alive (port 80/443 respond), but ALL paths return `404 page not found` with both `Host: wallet.trias.one` and `Host: explorer.trias.one`. Server running, app uninstalled. No vhost config remaining.

### CommonCrawl WARC extraction
```
Explorer 2020-11-24: CC-MAIN-2020-50, status 200, IP 119.28.116.31
Explorer 2022-01-20: CC-MAIN-2022-05, status 200, IP 119.28.116.31
→ Same IP for both snapshots. nginx serving React SPA HTML shell.
→ JS bundles, conf.json, api paths NOT captured by CommonCrawl.
```

WARC extraction technique:
- `data.commoncrawl.org/{filename}` works (S3 URL 403s)
- `zlib.decompressobj(31)` for partial gzip (gzip.decompress raises EOFError)
- Body after `\r\n\r\n`; chunked encoding strip hex length header

### Failed archive sources
| Source | Result |
|--------|--------|
| WayBack CDX | 429 permanent (all endpoints: cdx, timemap, availability) |
| archive.today/ph/li/is | Connection error / no snapshots |
| Google cache | No results (JS-rendered search pages) |
| Bing / Yandex / DDG | No results for "wallet.trias.one" |
| CommonCrawl wallet.* | No captures (only explorer captured) |
| OTX AlienVault | 429 unauth |
| VirusTotal / SecurityTrails / Shodan | 401 (need API key) |

## Classification upgrade
- Theft path: **PROVEN IN CODE** (unchanged — archive didn't capture conf.json live)
- Host historical existence: **PROVEN WAS LIVE** (2018-2022, IP 119.28.116.31)
- Host current state: **PROVEN DEAD** (DNS NXDOMAIN, IP 404 all paths)

## Key takeaway
Archive hunting proved the backend WAS live for 4 years, but CommonCrawl only captured the SPA shell — not the Django API endpoints or static conf.json. Without a WayBack snapshot of `/static/conf.json`, the theft path cannot be upgraded beyond PROVEN-IN-CODE. The archive confirmed the timeline but did not change the exploitability classification.
