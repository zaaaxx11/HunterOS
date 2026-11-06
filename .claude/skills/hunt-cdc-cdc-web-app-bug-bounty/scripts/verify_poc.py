#!/usr/bin/env python3
"""
Minimal PoC Verification Script Template
Usage: python verify_poc.py --target <url> --chain <chain_json>
"""

import argparse
import json
import sys
import requests
import subprocess
from typing import Dict, Any, List


class PoCVerifier:
    def __init__(self, target: str, chain: Dict[str, Any]):
        self.target = target.rstrip('/')
        self.chain = chain
        self.session = requests.Session()
        self.session.timeout = 30

    def verify_step(self, step: Dict[str, Any]) -> bool:
        """Verify a single chain step."""
        method = step.get('method', 'POST').upper()
        path = step.get('path', '')
        payload = step.get('payload', {})
        headers = step.get('headers', {})
        expected = step.get('expected', {})

        url = f"{self.target}{path}"

        try:
            if method == 'GET':
                resp = self.session.get(url, params=payload, headers=headers)
            elif method == 'POST':
                if headers.get('Content-Type') == 'multipart/form-data':
                    resp = self.session.post(url, files=payload, headers=headers)
                else:
                    resp = self.session.post(url, json=payload, headers=headers)
            else:
                resp = self.session.request(method, url, json=payload, headers=headers)

            # Check expected conditions
            if 'status' in expected and resp.status_code != expected['status']:
                print(f"  FAIL: Expected status {expected['status']}, got {resp.status_code}")
                return False

            if 'contains' in expected:
                if expected['contains'] not in resp.text:
                    print(f"  FAIL: Expected '{expected['contains']}' not in response")
                    return False

            if 'not_contains' in expected:
                if expected['not_contains'] in resp.text:
                    print(f"  FAIL: Unexpected '{expected['not_contains']}' in response")
                    return False

            print(f"  OK: {method} {path} → {resp.status_code}")
            return True

        except Exception as e:
            print(f"  ERROR: {e}")
            return False

    def verify_chain(self) -> bool:
        """Verify entire exploit chain."""
        steps = self.chain.get('steps', [])
        print(f"Verifying chain with {len(steps)} steps...")

        for i, step in enumerate(steps, 1):
            print(f"\nStep {i}: {step.get('description', 'unnamed')}")
            if not self.verify_step(step):
                print(f"CHAIN BROKEN at step {i}")
                return False

        print("\n✓ CHAIN VERIFIED - All steps passed")
        return True


def main():
    parser = argparse.ArgumentParser(description='Verify exploit chain PoC')
    parser.add_argument('--target', required=True, help='Target base URL')
    parser.add_argument('--chain', required=True, help='Path to chain JSON file')
    args = parser.parse_args()

    with open(args.chain) as f:
        chain = json.load(f)

    verifier = PoCVerifier(args.target, chain)
    success = verifier.verify_chain()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()