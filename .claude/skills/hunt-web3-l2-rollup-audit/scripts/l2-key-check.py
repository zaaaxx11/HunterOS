#!/usr/bin/env python3
"""
L2 Rollup Key Verification Script

Usage:
  python3 l2-key-check.py --rpc <L2_RPC_URL> --keys <comma-separated-keys>

Example:
  python3 l2-key-check.py --rpc https://rpc.plasma.to \
    --keys 0x1234...,0x5678...

Output:
  For each key:
  - Derived address
  - Balance
  - Nonce
  - Contract status (EOA vs Contract)
  - EIP-7702 delegation (if applicable)
"""

import argparse
import json
import sys
import urllib.request
from eth_account import Account


def eth_rpc(rpc_url: str, method: str, params: list = None, rid: int = 1) -> dict:
    """Make JSON-RPC call to Ethereum node."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": rid
    }).encode()
    req = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def derive_address(private_key: str) -> tuple:
    """Derive address from private key."""
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    account = Account.from_key(private_key)
    return account.address, account.key


def check_address(rpc_url: str, address: str) -> dict:
    """Check address balance, nonce, and code."""
    balance = eth_rpc(rpc_url, "eth_getBalance", [address, "latest"])
    nonce = eth_rpc(rpc_url, "eth_getTransactionCount", [address, "latest"])
    code = eth_rpc(rpc_url, "eth_getCode", [address, "latest"])

    bal_val = int(balance.get("result", "0x0"), 16)
    nonce_val = int(nonce.get("result", "0x0"), 16)
    code_hex = code.get("result", "0x")
    code_len = len(code_hex) - 2

    result = {
        "address": address,
        "balance_wei": bal_val,
        "balance_eth": bal_val / 1e18,
        "nonce": nonce_val,
        "code_length": code_len,
        "is_contract": code_len > 0,
        "is_eip7702": False,
        "delegated_to": None,
    }

    # Check for EIP-7702 delegation
    # Format: 0xef0100{address} (20 bytes)
    if code_len == 22 and code_hex.startswith("0xef0100"):
        result["is_eip7702"] = True
        result["delegated_to"] = "0x" + code_hex[10:52]

    return result


def prove_ownership(private_key: str, message: str = "L2 Audit - Key Verification") -> dict:
    """Prove key ownership by signing a message."""
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    account = Account.from_key(private_key)
    signed = Account.sign_message(message, account.key)

    return {
        "address": account.address,
        "message": message,
        "signature": signed.signature.hex(),
        "verified": Account.recover_message(
            message, signature=signed.signature
        ) == account.address,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verify L2 rollup private keys against on-chain state"
    )
    parser.add_argument(
        "--rpc",
        required=True,
        help="L2 RPC URL (e.g., https://rpc.plasma.to)"
    )
    parser.add_argument(
        "--keys",
        required=True,
        help="Comma-separated private keys (hex format)"
    )
    parser.add_argument(
        "--message",
        default="L2 Audit - Key Verification",
        help="Message to sign for ownership proof"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )

    args = parser.parse_args()

    keys = [k.strip() for k in args.keys.split(",") if k.strip()]

    results = []
    for i, key in enumerate(keys):
        try:
            address, _ = derive_address(key)
            chain_data = check_address(args.rpc, address)
            proof = prove_ownership(key, args.message)

            result = {
                "index": i,
                "private_key_prefix": key[:10] + "..." if len(key) > 10 else key,
                "address": address,
                "chain_data": chain_data,
                "proof": proof,
            }
            results.append(result)

        except Exception as e:
            results.append({
                "index": i,
                "error": str(e),
            })

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n{'='*70}")
        print(f"L2 KEY VERIFICATION REPORT")
        print(f"RPC: {args.rpc}")
        print(f"{'='*70}\n")

        for r in results:
            if "error" in r:
                print(f"[{r['index']}] ERROR: {r['error']}")
                continue

            cd = r["chain_data"]
            status = "ACTIVE" if cd["nonce"] > 0 else "INACTIVE"

            print(f"[{r['index']}] Address: {r['address']}")
            print(f"      Key: {r['private_key_prefix']}")
            print(f"      Status: {status}")
            print(f"      Nonce: {cd['nonce']}")
            print(f"      Balance: {cd['balance_eth']:.6f} ETH")
            print(f"      Code: {cd['code_length']} bytes")

            if cd["is_eip7702"]:
                print(f"      EIP-7702: YES → {cd['delegated_to']}")
            elif cd["is_contract"]:
                print(f"      Type: Contract")
            else:
                print(f"      Type: EOA")

            print(f"      Verified: {cd['proof']['verified']}")
            print()

        # Summary
        active_count = sum(1 for r in results if "chain_data" in r and r["chain_data"]["nonce"] > 0)
        print(f"{'='*70}")
        print(f"SUMMARY: {active_count}/{len(results)} keys ACTIVE")
        print(f"{'='*70}")


if __name__ == "__main__":
    main()
