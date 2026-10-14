#!/usr/bin/env python3
"""CryptoJS RC4->AES envelope decrypt/encrypt for Web3 backend transport "encryption"
(messier virgo/horizon family pattern). Cross-compatible with the on-disk Python flow.

Server response body = "U2FsdGVkX1/..." (CryptoJS Salted__, OpenSSL MD5-EVP KDF).
Decrypt (outer->inner):  RC4.decrypt(body, RC4KEY) -> AES-256-CBC.decrypt(->, AESKEY) -> JSON
Encrypt (matching request): outer RC4 over inner AES over JSON, under {"data": ...}

Self-contained (stdlib + pycryptodome). Replace the two passphrases with the ones you
grep out of each app's bundle (they differ per app; virgo+horizon shared the RC4 key).
"""
import base64, hashlib, json, os, sys
from Crypto.Cipher import AES, ARC4

AESKEY = b"bQeShVmYq3t6w9z$C&F)J@NcRfUjWnZr"          # AES passphrase (from bundle)
RC4KEY = b"G-KaPdSgVkYp3s6v9y$B?E(H+MbQeThWmZq4t7w!z%C*F)J@NcRfUjXn2r5u8x/A"  # RC4 passphrase

def _kdf(pw, salt, key_len=32, iv_len=16):
    # OpenSSL EVP_BytesToKey, MD5, iteration 1 (CryptoJS default)
    d, prev = b"", b""
    while len(d) < key_len + iv_len:
        prev = hashlib.md5(prev + pw + salt).digest()
        d += prev
    return d[:key_len], d[key_len:key_len + iv_len]

def rc4_decrypt(b64: str, pw: bytes) -> bytes:
    raw = base64.b64decode(b64)
    if raw[:8] != b"Salted__":
        raise ValueError("not CryptoJS Salted__ format")
    salt, ct = raw[8:16], raw[16:]
    key, _ = _kdf(pw, salt, 32, 0)
    return ARC4.new(key).decrypt(ct)

def aes_decrypt(b64: str, pw: bytes) -> bytes:
    raw = base64.b64decode(b64)
    if raw[:8] != b"Salted__":
        raise ValueError("not CryptoJS Salted__ format")
    salt, ct = raw[8:16], raw[16:]
    key, iv = _kdf(pw, salt)
    pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
    pad = pt[-1]
    if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
        pt = pt[:-pad]
    return pt

def decrypt_envelope(body: str) -> str:
    """body = the JSON-quoted vector 'U2FsdGVkX1/...' (strip surrounding quotes first)."""
    s = body.strip().strip('"')
    rc4_out = rc4_decrypt(s, RC4KEY).decode("utf-8", "replace").strip()
    rc4_out = rc4_out.strip('"')           # inner layer is itself a Salted__ b64 string
    return aes_decrypt(rc4_out, AESKEY).decode("utf-8", "replace")

def encrypt_envelope(obj) -> str:
    """Build the {'data': <envelope>} request body for a JSON payload object."""
    inner_salt = os.urandom(8)
    key, iv = _kdf(AESKEY, inner_salt)
    js = json.dumps(obj, separators=(",", ":")).encode()
    pad = 16 - (len(js) % 16)
    aes_b64 = base64.b64encode(b"Salted__" + inner_salt + AES.new(key, AES.MODE_CBC, iv).encrypt(js + bytes([pad]) * pad)).decode()
    outer_salt = os.urandom(8)
    okey, _ = _kdf(RC4KEY, outer_salt, 32, 0)
    return base64.b64encode(b"Salted__" + outer_salt + ARC4.new(okey).encrypt(aes_b64.encode())).decode()

def request_body(obj) -> str:
    return json.dumps({"data": encrypt_envelope(obj)})

if __name__ == "__main__":
    # demo: decrypt a caught body
    if len(sys.argv) > 1:
        print(decrypt_envelope(sys.argv[1]))
    else:
        print(request_body({"base_token": "open_<wallet>_virgo", "info": {}}))