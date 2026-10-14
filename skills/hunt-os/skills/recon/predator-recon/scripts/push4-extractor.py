#!/usr/bin/env python3
"""
PUSH4 Selector Extractor — Extract function selectors from EVM bytecode
without disassembly tools (heimdall, evmdasm, etc.).

Usage:
    python3 push4-extractor.py <bytecode_file>
    python3 push4-extractor.py --rpc <RPC_URL> <contract_address>

Output:
    List of 4-byte function selectors (0x + 8 hex chars)
"""

import sys
import re
import argparse
import json
import subprocess

# Known function selectors for labeling
KNOWN_SELECTORS = {
    # ERC20 / ERC4626
    "0x18160ddd": "totalSupply()",
    "0x70a08231": "balanceOf(address)",
    "0x95d89b41": "symbol()",
    "0x06fdde03": "name()",
    "0x313ce567": "decimals()",
    "0xa9059cbb": "transfer(address,uint256)",
    "0x23b872dd": "transferFrom(address,address,uint256)",
    "0x095ea7b3": "approve(address,uint256)",
    "0xd7b28185": "totalAssets()",
    "0xa495071d": "previewRedeem(uint256)",
    "0x6006c3eb": "maxMint(address)",
    "0x3659cfe6": "maxWithdraw(address)",
    "0x8680bb1f": "maxRedeem(address)",
    "0xb6f9c9a9": "previewMint(uint256)",
    
    # Ownable / AccessControl
    "0x8da5cb5b": "owner()",
    "0xf2fde38b": "transferOwnership(address)",
    "0x715018a6": "renounceOwnership()",
    "0x3659cfe6": "hasRole(bytes32,address)",
    "0x214d377b": "grantRole(bytes32,address)",
    "0x36568abe": "revokeRole(bytes32,address)",
    "0x84b0196e": "getRoleAdmin(bytes32)",
    "0x9d1c8b83": "getRoleMember(bytes32,uint256)",
    "0xcaf3a6f9": "getRoleMemberCount(bytes32)",
    
    # Pausable
    "0x5c975ea4": "paused()",
    "0x8456cb59": "pause()",
    "0x3f4ba83a": "unpause()",
    
    # UUPS Upgradeable
    "0x5b1d1de2": "upgradeTo(address)",
    "0xb274a710": "upgradeToAndCall(address,bytes)",
    "0x1a3598b2": "_implementation()",
    
    # Gnosis Safe
    "0x9d1c8b83": "getOwners()",
    "0x7e7d5e4b": "getThreshold()",
    
    # ERC165
    "0x01ffc9a7": "supportsInterface(bytes4)",
    
    # Custom (t3tris)
    "0xac946fce": "initialize(...)",
    "0xa5d37df5": "createVault(address,bytes32)",
    "0x022d63fb": "fee_basis_points()",
    "0x01e1d114": "config_1()",
}

def extract_push4_selectors(bytecode_hex: str) -> list:
    """
    Extract PUSH4 (0x63) selectors from bytecode.
    PUSH4 opcode = 0x63, followed by 4 bytes (8 hex chars).
    """
    selectors = []
    i = 0
    bytecode = bytecode_hex.lower().replace('0x', '')
    
    while i < len(bytecode):
        if bytecode[i:i+2] == '63':  # PUSH4
            if i + 10 <= len(bytecode):
                selector = '0x' + bytecode[i+2:i+10]
                selectors.append(selector)
                i += 10
            else:
                i += 2
        else:
            i += 2
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in selectors:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    
    return unique

def fetch_bytecode(rpc_url: str, address: str) -> str:
    """Fetch contract bytecode from RPC."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_getCode",
        "params": [address, "latest"],
        "id": 1
    })
    result = subprocess.run(
        ["curl", "-s", "--max-time", "10", rpc_url, "-X", "POST",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, timeout=30
    )
    data = json.loads(result.stdout)
    return data.get('result', '0x')

def main():
    parser = argparse.ArgumentParser(description="Extract PUSH4 selectors from EVM bytecode")
    parser.add_argument("input", nargs="?", help="Bytecode file or contract address")
    parser.add_argument("--rpc", help="RPC URL for live fetching")
    parser.add_argument("--label", action="store_true", help="Label known selectors")
    parser.add_argument("--output", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    if not args.input:
        parser.print_help()
        return 1
    
    # Get bytecode
    if args.rpc and args.input.startswith('0x') and len(args.input) == 42:
        print(f"Fetching bytecode from {args.rpc} for {args.input}...", file=sys.stderr)
        bytecode = fetch_bytecode(args.rpc, args.input)
        if bytecode == '0x':
            print("ERROR: No bytecode found (not a contract or wrong network)", file=sys.stderr)
            return 1
    else:
        # Read from file
        with open(args.input, 'r') as f:
            bytecode = f.read().strip()
    
    # Extract selectors
    selectors = extract_push4_selectors(bytecode)
    
    # Output
    out_lines = []
    for sel in selectors:
        if args.label and sel in KNOWN_SELECTORS:
            out_lines.append(f"{sel}: {KNOWN_SELECTORS[sel]}")
        else:
            out_lines.append(sel)
    
    output = "\n".join(out_lines)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Written {len(selectors)} selectors to {args.output}", file=sys.stderr)
    else:
        print(output)
    
    print(f"\nTotal unique selectors: {len(selectors)}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())