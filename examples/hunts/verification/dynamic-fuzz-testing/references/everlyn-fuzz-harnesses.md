# Everlyn Wasserstein-VQ Fuzz Session (2026-08-07)

## Targets (resolved via search_files — prefix is Wasserstein-VQ/)
- `Wasserstein-VQ/data/dataloader.py:60` pil_loader
- `Wasserstein-VQ/model/base_quantizer.py:16-64` calc_wasserstein_loss*
- `Wasserstein-VQ/model/wasserstein_quantizer.py:28-77` forward
- `Wasserstein-VQ/config.py:15-82` parse_arg (81-82 ms_token_size, codebook_dim)
- `Wasserstein-VQ/metric/loss.py:20-46` download/get_ckpt_path

## Harnesses written to /tmp
- /tmp/fuzz_pil_loader.py (+ /tmp/fuzz_pil_loader2.py fallback, executed)
- /tmp/fuzz_wasserstein.py (+ /tmp/fuzz_wasserstein2.py fallback, executed)
- /tmp/fuzz_config.py (executed)
- /tmp/fuzz_ssrf.py (+ /tmp/fuzz_ssrf2.py fallback, executed)

## Key execution output (fallback runs)
- PIL 8000x8000 (64M px): SUCCESS -> 192 MB alloc, VULN; 15000x15000 -> DecompressionBombError; symlink followed (TOCTOU)
- Wasserstein N=1: loss 3.82 S_min=0 fake 1e-8 diag; N=0: LinAlgError; NaN/Inf: LinAlgError; constant: S=0 masked
- Config: '' / '1__2' / '1_2_abc' -> ValueError; '999999' -> OOM; 101 levels -> loop bomb; latent_reso 15->0 dim
- SSRF live server: attacker URL write true, traversal /tmp/traversal_*.txt exists, redirect /evil followed

## Technique
- search_files first to resolve prefix mismatches (model/wasserstein_quantizer.py not at root)
- torch-free fallbacks mandatory (host has no torch/numpy in default sys.path; pip torch fails on tencent mirror)
- Small inputs only; report file:line + input per crash

## Fix pointers
- pil_loader: Image.MAX_IMAGE_PIXELS, getsize+dimension check, verify()
- base_quantizer: guard N==0, isnan/isinf on z, don't F.relu-mask negative eigenvalues
- config: validate ms_patch_size tokens, clamp codebook_dim, sanitize path args
- loss download: allowlist, timeout, no redirects, canonicalize local_path, validate MD5 before use
