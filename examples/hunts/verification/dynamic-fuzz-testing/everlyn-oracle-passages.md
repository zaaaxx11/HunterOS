# Everlyn-oracle passages (cut from dynamic-fuzz-testing SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/verification/dynamic-fuzz-testing/SKILL.md`
during the S2b-2 content pass and rewritten in place target-agnostically
("on a live engagement" style). The everlyn + trias case refs live at
`examples/hunts/verification/dynamic-fuzz-testing/references/`.

---

## Oracles (from Everlyn Wasserstein-VQ session)

| Sink | File:Line | Inputs | Oracle |
|------|-----------|--------|--------|
| pil_loader | `data/dataloader.py:60` `open(path).convert('RGB')` | 32×32, 8000×8000, 15000×15000, truncated, non-image, symlink | DecompressionBombWarning/Error, OOM MB, `UnidentifiedImageError` |
| wasserstein single | `model/base_quantizer.py:21,28-29` `/N`, `eigh`, `F.relu(S)` | N=1, N=0, constant, large 1e6, NaN, Inf, D=1 | `LinAlgError`, loss=0 fake `1e-8` diag, NaN hide |
| wasserstein full | `base_quantizer.py:54,58` `d_cov=z_cov@c_cov`, `F.relu(S)` | c_cov=0 constant codebook | non-PSD eigenvalues masked |
| ms_patch_size | `config.py:81` `map(int, split('_'))` | `1__2`, `""`, `999999`, `1_"*100`, `999999999999` | `ValueError`, OOM interpolate, 101-level loop |
| codebook_dim | `config.py:82` `int(lr/16)*int(lr/16)*ld` | 15,0,-16,"16",10000,256 | 0 dim, huge OOM, `TypeError` str/None |
| SSRF download | `metric/loss.py:22-31` `requests.get` | attacker URL, `../` path, `/redirect`, slowloris | write true, traversal exists, redirect followed, no timeout |

## Everlyn-specific workflow inline text (as it appeared)

- Inputs: **target_dir** — codebase root (e.g. `/tmp/everlyn-src`)
- Step 2: replicate the vulnerable function exactly (copy `pil_loader`, `calc_wasserstein_loss_single`, `download`)
- Step 4: crashes: `UnidentifiedImageError` at `dataloader.py:61`, `ValueError` at `config.py:81`, `LinAlgError: Eigenvalues did not converge` at `base_quantizer.py:28`
- Step 5: `pil_loader:60` / `base_quantizer.py:21,28,58` / `config.py:81-82` / `metric/loss.py:22-31`
