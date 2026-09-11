---
name: dynamic-fuzz-testing
description: "dynamic fuzz and property-based testing for Python/ML codebases"
metadata:
  version: 1.0.0
  hermes:
    tags: [fuzzing, property-testing, dynamic-analysis, ml-security, ssrf, oom, nan]
    category: security
---

# Dynamic Fuzz / Property Testing

## Triggers
- fuzz / fuzzer / property test / property-based
- pil_loader bomb / decompression bomb / MAX_IMAGE_PIXELS / OOM
- wasserstein loss NaN / Inf / eigh / covariance degenerate
- config parser type confusion / ms_patch_size / codebook_dim
- SSRF download / requests.get without timeout / path traversal / TOCTOU

## Inputs
- **target_dir** — codebase root of the codebase under test (e.g. `/tmp/target-src`)
- **targets** — list of `file:line` sinks to harness
- **out_dir** — where to write `/tmp/fuzz_*.py` (default `/tmp`)
- **deps** — whether torch/numpy available (auto-detect, build fallback if not)

## Workflow

### 1. Resolve real paths
`search_files(target='files')` first — task descriptions often omit a prefix
(e.g. `Wasserstein-VQ/`). Read the 4 sinks to confirm signatures before writing harnesses.

### 2. Write one harness per sink to `/tmp/fuzz_*.py`
Each harness must:
- replicate the vulnerable function exactly (copy the original function under test verbatim — e.g. the image loader, the loss math, or the download helper)
- define a `test_case(name, input)` helper that prints `file:line` and input on crash/OOM/TOCTOU
- use **small inputs** (tiny, edge, bomb, corrupt) — not large corpora
- report VULN vs ok per oracle (DecompressionBombError, LinAlgError, ValueError, traversal write)

### 3. Torch-free fallback (mandatory)
Host may lack `torch`/`numpy` in default `sys.path` (pip installs to `/tmp/pylibs` or fails
on large wheels/retries). Every harness that imports `torch` must have a `*2.py` fallback:
- PIL bomb: no torch needed — test `PIL.Image` directly
- Wasserstein: numpy simulation (`np.linalg.eigh` + `F.relu` → `np.maximum(S,0)`)
- SSRF: local `download()` reimplementation with `requests` + `http.server` on `127.0.0.1:0`
- Config: pure-Python `tuple(map(int, s.split('_')))` simulation, no argparse import
Detect missing dep by trying import; if `ModuleNotFoundError`, switch to fallback.

### 4. Execute with small inputs
`python3 /tmp/fuzz_*.py 2>&1 | head -n 120` per harness. Capture:
- crashes with their `file:line` — e.g. `UnidentifiedImageError` at the image
  loader, `ValueError` at the config parser, `LinAlgError: Eigenvalues did not
  converge` at the loss math
- OOM: `64000000 px → 192 MB`, `999999` token → `F.interpolate` bomb
- TOCTOU: symlink followed, `makedirs` + `open` arbitrary path, traversal `../` write

### 5. Report per sink: file:line + input + oracle
one row per sink — `file:line` + input + oracle. (The concrete sink-to-line oracle map from the original ML-target engagement is preserved at examples/hunts/verification/dynamic-fuzz-testing/everlyn-oracle-passages.md.)

## Oracles (per sink class)

Build one oracle row per sink on a live engagement — sink `file:line`, the input classes to fire, and the observable that distinguishes VULN from ok:

| Sink class | Inputs to fire | Typical oracle |
|------------|----------------|----------------|
| Image/file loader | tiny, oversized (px bombs), truncated, non-image, symlink | `DecompressionBombWarning`/`Error`, OOM MB, `UnidentifiedImageError` |
| Loss / linear-algebra math | N=1, N=0, constant, large 1e6, NaN, Inf, degenerate dims | `LinAlgError`, silent zero/fake-diag loss, NaN hidden by clamps |
| Config parser (string → dims/ints) | empty string, missing separators, `999999`, huge ints, wrong types | `ValueError`, OOM on downstream allocation, deep loops |
| Downloader / fetch | attacker URL, `../` traversal path, `/redirect`, slowloris | traversal write, redirect followed, no-timeout hang |
(The full Everlyn Wasserstein-VQ sink-to-line oracle table — `pil_loader` / `base_quantizer.py` / `config.py` / `metric/loss.py` with exact file:line and inputs — is preserved at examples/hunts/verification/dynamic-fuzz-testing/everlyn-oracle-passages.md, with the session transcript at examples/hunts/verification/dynamic-fuzz-testing/references/everlyn-fuzz-harnesses.md.)

## Pitfalls
- Do not `pip install torch` blindly — 170 MB wheel fails on Tencent mirror (resume retries). Use fallback first, then `pip install --target /tmp/pylibs` + `PYTHONPATH=/tmp/pylibs:$PYTHONPATH` if needed.
- `Image.MAX_IMAGE_PIXELS` default is ~89M; test both `None` (bomb) and capped (DecompressionBombError) paths.
- `config.py` imports `numpy`/`torch` at top — CLI fuzz via `subprocess` will fail if deps missing; fuzz `ms_patch_size` logic inline instead.
- SSRF `download()` needs `requests` + `tqdm` live server; bind `HTTPServer(('127.0.0.1',0))` and use `server.server_port`.
- **Django 1.11 on Python 3.11 compat** — `collections.Iterator/Mapping/Sequence/MutableMapping` moved to `collections.abc` and `DjangoTranslation.set_output_charset` removed. Patch before `django.setup()`: `for attr in ['Iterator','Mapping','Sequence','MutableMapping','MutableSequence','MutableSet','Set','Counter']: if not hasattr(collections,attr) and hasattr(collections.abc,attr): setattr(collections,attr,getattr(collections.abc,attr))`. Avoid full `django.setup()` if only testing `Paginator` — configure minimal `settings` and import `Paginator` directly.
- **Django Paginator `len(qs)` vs `count()` DoS** — `len(queryset)` evaluates all rows; `queryset.count()` does `COUNT(*)`. Flag `len(total_data)` in paginated views (trias-explorer `block_transactions` loads all rows into memory).
- **Proving negatives for `order_by` SQLi** — Django 1.11 `order_by()` validates field names against model and raises `FieldError: Invalid order_by arguments` for any `; -- /* ' "` payload. Live-test with SQLite in-memory DB to prove SQLi is blocked before claiming bypass.
- **Container `git remote-https` missing → tarball fallback** — Minimal containers ship `git` without curl-linked `git-remote-https` → `git clone https://` fails. Use `curl -L --max-time 60 https://github.com/org/repo/archive/refs/heads/main.tar.gz -o /tmp/repo.tar.gz && tar -xzf` and `api.github.com/repos/org/repo/contents/<path>` for dir listing (trias-explorer, berachain, 69 repos verified).

## References
- Case evidence (everlyn fuzz-harness session transcript; trias Django 1.11 + TRYSimple fuzz) is preserved at `examples/hunts/verification/dynamic-fuzz-testing/references/` — moved out of the product layer 2026-09-07.

## Linked Harnesses (templates)
- `scripts/fuzz_pil_loader.py` — standalone PIL bomb harness (no torch)
- `scripts/fuzz_wasserstein.py` — numpy Wasserstein NaN harness
- `scripts/fuzz_ssrf.py` — local HTTP SSRF+traversal harness
